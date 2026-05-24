r"""SW-TS — Sliding-window Thompson Sampling.

A per-arm Gaussian-posterior Thompson Sampling policy that estimates
each arm's expected reward from observations recorded within the most
recent ``W`` **global** rounds. The sliding window is wall-clock based,
not pull-count based: an arm that is not pulled for ``W`` rounds reverts
to its prior, mirroring PA-DCT's wall-clock multiplicative discount
(rather than the pull-conditional forgetting that a per-arm pull-count
deque would produce).

SW-TS is included in Appendix D to cover the non-stationary Thompson
sampling family (Trovò et al. 2020) in our experimental comparison,
specifically the "sliding-window" variant of the non-stationary bandit
literature that reviewers may expect when asking about
"sliding-window budgeted bandit" baselines. It is reported as one
component of a family-coverage argument together with the
LinCBwK-style adaptation (budget + context, no drift) and PA-DCT
(budget + context + drift); these three policies span the
budget × drift × context coverage that a fully featured budgeted
sliding-window contextual bandit would jointly require.

What SW-TS uses
---------------
* Per-arm sliding window of the most recent ``W`` observed utilities.
* Conjugate Normal-Normal posterior over each arm's mean reward
  computed from the window contents and a fixed prior.
* Thompson sampling: one posterior sample per affordable arm per round,
  argmax over the samples.

What SW-TS does NOT use
-----------------------
* No context. The window is per-arm, not per-(arm, bucket). This is
  faithful to the published SW-TS, which is non-contextual.
* No cost posterior. Realized cost passes through ``update`` and is
  ignored.
* No wallet pressure / dual variable. The affordable-set mask supplied
  by the runtime loop is the only budget signal.
* No knapsack constraint. SW-TS is not a budgeted bandit in its
  published form; we do not claim it covers the full budgeted
  sliding-window family on its own.

Hyperparameter alignment with PA-DCT
------------------------------------
The Gaussian prior (``prior_mean = 0.5``, ``prior_var = 1.0``,
``noise_var = 0.09``) matches PA-DCT's Q-posterior defaults so that the
only algorithmic differences in the family-coverage comparison are
(i) sliding-window instead of multiplicative discount on sufficient
statistics, (ii) no context, (iii) no cost posterior, (iv) no
wallet-pressure scaling.

Window length
-------------
``W = 1000`` global rounds is locked across all scenarios and seeds
(10% of the ``T = 10000`` evaluation horizon). This matches the
``most-recent-decile`` interpretation of PA-DCT's discount half-life
``ln(2) / (1 - 0.999) ≈ 693`` rounds within a factor of ~1.5 and does
not require per-scenario tuning.

Implementation notes
--------------------
Each arm stores ``(global_round_index, utility)`` tuples in a deque,
which is pruned at the head by any subsequent call whose current
global round exceeds the head's ``round_index + W``. Pruning is lazy
(done inside the posterior computation) to keep the ``update`` path
O(1).
"""

from __future__ import annotations

import math
from collections import deque
from dataclasses import dataclass, field

from numpy.random import Generator

from pilot402.core import ProviderId
from pilot402.core.interfaces import ContextVector


@dataclass
class SWTSPolicy:
    """Sliding-window Thompson Sampling.

    Args:
        rng:            NumPy ``Generator`` for posterior sampling.
        provider_ids:   Iterable of provider IDs the policy will see.
                        Used to pre-allocate per-arm sliding windows.
        window:         Sliding-window length ``W`` in **global rounds**
                        (wall-clock based, not per-arm pull count): an
                        observation falls out of the window once the
                        current global round exceeds its record by
                        ``W``, whether or not the arm has been pulled
                        since. Default 1000.
        prior_mean:     μ₀ for the per-arm reward posterior. Default 0.5
                        (matches PA-DCT).
        prior_var:      σ₀² for the prior. Default 1.0 (matches PA-DCT).
        noise_var:      σ² for the likelihood. Default 0.09
                        (matches PA-DCT).
    """

    rng: Generator
    provider_ids: tuple[ProviderId, ...]
    window: int = 1000
    prior_mean: float = 0.5
    prior_var: float = 1.0
    noise_var: float = 0.09

    _windows: dict[ProviderId, deque[tuple[int, float]]] = field(init=False)
    _global_round: int = field(init=False, default=0)

    def __post_init__(self) -> None:
        if self.window < 1:
            raise ValueError(f"window must be >= 1, got {self.window}")
        if self.prior_var <= 0:
            raise ValueError(f"prior_var must be > 0, got {self.prior_var}")
        if self.noise_var <= 0:
            raise ValueError(f"noise_var must be > 0, got {self.noise_var}")
        # Each entry is (round_index_when_observed, utility). The deque is
        # unbounded; pruning is by global-round cutoff in _posterior_params.
        self._windows = {arm: deque() for arm in self.provider_ids}

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _posterior_params(self, arm: ProviderId) -> tuple[float, float]:
        """Return ``(posterior_mean, posterior_var)`` from observations
        within the last ``W`` global rounds.

        Prunes any deque entries whose ``round_index`` is older than
        ``self._global_round - self.window``. Standard Normal-Normal
        posterior over the surviving observations; empty window → prior.
        """
        window = self._windows[arm]
        cutoff = self._global_round - self.window
        while window and window[0][0] <= cutoff:
            window.popleft()
        n = len(window)
        s = sum(u for _, u in window)
        precision = 1.0 / self.prior_var + n / self.noise_var
        post_var = 1.0 / precision
        post_mean = post_var * (self.prior_mean / self.prior_var + s / self.noise_var)
        return post_mean, post_var

    # ------------------------------------------------------------------
    # Policy Protocol
    # ------------------------------------------------------------------

    def select(
        self,
        context: ContextVector,  # noqa: ARG002 — SW-TS is non-contextual.
        affordable_arms: tuple[ProviderId, ...],
    ) -> ProviderId:
        if not affordable_arms:
            raise ValueError(
                "SWTSPolicy received an empty affordable set; the "
                "loop should detect bankruptcy before invoking the policy."
            )

        best_arm: ProviderId | None = None
        best_sample = float("-inf")
        for arm in affordable_arms:
            if arm not in self._windows:
                raise KeyError(
                    f"SWTSPolicy: unknown arm {arm.value!r}; "
                    f"provider_ids has {[a.value for a in self.provider_ids]}"
                )
            post_mean, post_var = self._posterior_params(arm)
            sampled = float(
                self.rng.normal(loc=post_mean, scale=math.sqrt(post_var))
            )
            if sampled > best_sample:
                best_sample = sampled
                best_arm = arm

        assert best_arm is not None  # affordable set is non-empty
        return best_arm

    def update(
        self,
        context: ContextVector,  # noqa: ARG002 — SW-TS is non-contextual.
        arm: ProviderId,
        utility: float,
        observed_cost: float,  # noqa: ARG002 — SW-TS does not learn cost.
    ) -> None:
        """Increment the global round counter and append the (round, utility)
        pair to the chosen arm's deque.

        The global round counter is incremented exactly once per round
        (the runtime loop calls ``update`` once per round, for the
        single chosen arm); this is what enables the wall-clock
        ``last-W-global-rounds`` semantics in ``_posterior_params``.
        """
        if arm not in self._windows:
            raise KeyError(
                f"SWTSPolicy.update: unknown arm {arm.value!r}; "
                f"provider_ids has {[a.value for a in self.provider_ids]}"
            )
        self._global_round += 1
        self._windows[arm].append((self._global_round, utility))

    # ------------------------------------------------------------------
    # Diagnostics
    # ------------------------------------------------------------------

    def posterior_state(self) -> dict[str, dict[str, float]]:
        """Snapshot of all per-arm posterior summaries.

        ``_posterior_params`` prunes the deque to the global-round window
        first, so ``n_samples`` reports the post-prune effective count.
        """
        out: dict[str, dict[str, float]] = {}
        for arm in self.provider_ids:
            post_mean, post_var = self._posterior_params(arm)
            out[arm.value] = {
                "n_samples": len(self._windows[arm]),
                "posterior_mean": post_mean,
                "posterior_var": post_var,
                "global_round": float(self._global_round),
            }
        return out


__all__ = ["SWTSPolicy"]
