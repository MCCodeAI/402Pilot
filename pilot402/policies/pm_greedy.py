r"""PM-Greedy — Price-Metadata Greedy router.

A single-pass, threshold-based router that adapts the FrugalGPT cascade
idea (Chen et al. 2023) to the 402Pilot admissible contract. The
sliding-mean signal here is the *utility estimate* — i.e. the mean of
``utility = q - ν·failure_flag`` observed for the (arm, bucket) cell —
not a raw quality estimate; failures are penalized through the same
``utility`` term that the runtime loop passes to ``update``. The
selection rule is:

    Pick the cheapest affordable arm whose sliding-mean utility
    estimate clears a fixed threshold τ. If multiple arms tie on
    listed price, break ties by higher utility estimate. If no arm
    clears τ, fall back to the highest utility estimate over
    affordable arms.

PM-Greedy is included as a "price-visible router analogue" baseline at
the explicit request of reviewers; it is also the canonical
single-pass online adaptation of FrugalGPT-style cascade routing under
our paid-feedback contract (no within-query escalation, no offline
quality supervision).

What information PM-Greedy uses
-------------------------------
* **Listed price metadata.** At each round, PM-Greedy reads the
  scenario-aware listed price via a ``listed_price_fn`` callable
  supplied at construction. This is the same listed-price metadata
  surface that the runtime loop uses for affordability checks; the S3
  price-promotion scenario reflects the promotion in this metadata at
  the shock round. PM-Greedy is therefore a **favorable price-metadata
  router baseline**: it observes the same listed-price signal as the
  affordability check itself. Variants with stale metadata would only
  widen the gap to PA-DCT and are not reported.
* **Sliding-mean utility estimate per (arm, bucket).** We maintain a
  bounded deque of the most recent ``W = 500`` observed utilities (i.e.
  failure-penalized quality) for each (arm, bucket) cell. Old
  observations fall out of the window when the deque is full; this
  gives PM-Greedy a coarse, model-free non-stationary quality-and-
  reliability signal. The threshold τ is therefore expressed in
  utility units, not raw quality units, so a high-failure arm like
  P-flaky drops below τ even when its successful responses score
  highly.

What information PM-Greedy does NOT use
---------------------------------------
* No receipt-cost posterior. Selection is a *threshold filter then sort
  by listed price*, not a ``utility / price`` ratio: candidate arms
  whose sliding-mean utility estimate clears ``τ`` are ranked by listed
  price metadata (cheapest wins), with utility estimate as the
  tie-break inside the same listed-price tier. Realized cost from
  receipts is consumed by the wallet ledger upstream of the policy but
  never enters the selection rule. This places PM-Greedy strictly in
  the "price-visible router" family rather than the "cost-aware
  contextual bandit" family.
* No budget pressure / wallet handle. Affordable-set masking is the
  only budget signal; PM-Greedy does not modulate its preference based
  on remaining budget. This is intentional — the FrugalGPT cascade is
  budget-oblivious in its published form.
* No posterior exploration. Once an arm's utility estimate drops below
  τ, it is not refreshed unless the fallback rule selects it again (all
  affordable arms also drop below τ, triggering the argmax-û fallback).
  The per-pull window does not decay merely because wall-clock rounds
  pass: if the arm stops being pulled, its sliding mean is frozen until
  it is pulled again. There is no UCB-style bonus on under-sampled
  arms.

Cold-start: optimistic init
---------------------------
Each (arm, bucket) cell starts with utility estimate ``û_init = 1.0``
(optimistic). Since every arm initially clears τ, the first round's
cheapest-above-τ rule picks the lowest-listed-price affordable arm; the
chosen arm receives a real observation and its sliding mean updates.
After a few pulls, arms whose true utility is below τ drop out of the
"above threshold" set, and the cascade rule moves to the next-cheapest
above τ. No forced round-robin warm-start is used: a fixed pre-policy
round-robin would introduce **off-policy paid probes** (decisions made
by the experimenter, not by the policy under test) which violate the
§3 paid-feedback contract that every paid call must be a policy
decision. Exploration here arises endogenously from the optimistic
init plus the threshold cascade.

Threshold sensitivity
---------------------
τ = 0.7 is locked for the main-table comparison. Sensitivity sweeps
τ ∈ {0.6, 0.8} appear in Appendix D to document that the comparison
behaviour is not threshold-tuned.
"""

from __future__ import annotations

from collections import deque
from collections.abc import Callable
from dataclasses import dataclass, field

from pilot402.core import ProviderId
from pilot402.core.interfaces import ContextVector


def _default_context_to_bucket(context: ContextVector) -> int:
    """Default bucket extractor for ``NaiveEncoder``: argmax of first 4 dims.

    Matches ``pilot402.policies.padct._default_context_to_bucket`` so the
    bucket index is identical to PA-DCT for the same context.
    """

    return max(range(4), key=lambda i: context[i] if i < len(context) else float("-inf"))


@dataclass
class PMGreedyPolicy:
    """Price-Metadata Greedy threshold-cascade router.

    Args:
        listed_price_fn:    Callable ``(round_idx, provider_id) -> float``
                            returning the listed (advertised) price for
                            the arm at the given round. Constructed in the
                            dispatch as a closure over the scenario object.
        provider_ids:       Iterable of provider IDs the policy will see.
                            Used to pre-allocate per-(arm, bucket) sliding
                            quality windows.
        n_buckets:          Number of context buckets. 4 = task types.
        context_to_bucket:  Maps ``ContextVector`` → bucket index ∈ [0, n_buckets).
        window:             Sliding-window length ``W`` for the utility
                            estimate, in observations per (arm, bucket).
                            Default 500.
        threshold:          Utility threshold ``τ`` (in units of
                            failure-penalized quality, since the window
                            stores ``utility`` not raw ``quality``).
                            Default 0.7. **Locked for the main table;**
                            ``τ ∈ {0.6, 0.8}`` reported in Appendix D as
                            sensitivity sweep.
        q_init:             Optimistic initial utility estimate for cells
                            with no observations yet. Default 1.0. The
                            ``q_`` prefix is kept for backward-compatible
                            attribute access; the value stored is a
                            sliding mean of observed ``utility``, not raw
                            quality.
    """

    listed_price_fn: Callable[[int, ProviderId], float]
    provider_ids: tuple[ProviderId, ...]
    n_buckets: int = 4
    context_to_bucket: Callable[[ContextVector], int] = field(
        default=_default_context_to_bucket
    )
    window: int = 500
    threshold: float = 0.7
    q_init: float = 1.0

    _q_windows: dict[ProviderId, list[deque[float]]] = field(init=False)
    _round: int = field(init=False, default=0)

    def __post_init__(self) -> None:
        if self.n_buckets < 1:
            raise ValueError(f"n_buckets must be >= 1, got {self.n_buckets}")
        if self.window < 1:
            raise ValueError(f"window must be >= 1, got {self.window}")
        if not (0.0 <= self.threshold <= 1.0):
            raise ValueError(f"threshold must be in [0, 1], got {self.threshold}")
        self._q_windows = {
            arm: [deque(maxlen=self.window) for _ in range(self.n_buckets)]
            for arm in self.provider_ids
        }

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _bucket_for(self, context: ContextVector) -> int:
        b = self.context_to_bucket(context)
        return b % self.n_buckets

    def _q_estimate(self, arm: ProviderId, bucket: int) -> float:
        """Sliding-mean utility estimate (failure-penalized quality);
        optimistic init if no samples have arrived for the cell yet."""
        window = self._q_windows[arm][bucket]
        if not window:
            return self.q_init
        return sum(window) / len(window)

    # ------------------------------------------------------------------
    # Policy Protocol
    # ------------------------------------------------------------------

    def select(
        self,
        context: ContextVector,
        affordable_arms: tuple[ProviderId, ...],
    ) -> ProviderId:
        if not affordable_arms:
            raise ValueError(
                "PMGreedyPolicy received an empty affordable set; the "
                "loop should detect bankruptcy before invoking the policy."
            )

        bucket = self._bucket_for(context)

        # Read listed prices and utility estimates over the affordable set.
        candidates: list[tuple[float, float, ProviderId]] = []
        for arm in affordable_arms:
            if arm not in self._q_windows:
                raise KeyError(
                    f"PMGreedyPolicy: unknown arm {arm.value!r}; "
                    f"provider_ids has {[a.value for a in self.provider_ids]}"
                )
            price = self.listed_price_fn(self._round, arm)
            u_hat = self._q_estimate(arm, bucket)
            candidates.append((price, u_hat, arm))

        # Primary rule: cheapest above-threshold; tie-break by higher û.
        # (Higher û wins on ties because under our admissible contract,
        # the cascade idea picks the *strongest* arm at a given price tier
        # — matching the FrugalGPT spirit of "use the smallest model that
        # passes the bar".)
        above = [c for c in candidates if c[1] >= self.threshold]
        if above:
            # Sort by (price ascending, -û) → cheapest first, then
            # highest û within tied price.
            above.sort(key=lambda c: (c[0], -c[1]))
            return above[0][2]

        # Fallback rule: no arm clears τ → pick highest û over affordable.
        # Among ties, pick cheapest (consistent with the primary rule's
        # price preference).
        best = max(candidates, key=lambda c: (c[1], -c[0]))
        return best[2]

    def update(
        self,
        context: ContextVector,
        arm: ProviderId,
        utility: float,
        observed_cost: float,  # noqa: ARG002 — PM-Greedy uses listed price, not receipts.
    ) -> None:
        """Append observed utility to the (arm, bucket) sliding window."""
        if arm not in self._q_windows:
            raise KeyError(
                f"PMGreedyPolicy.update: unknown arm {arm.value!r}; "
                f"provider_ids has {[a.value for a in self.provider_ids]}"
            )
        bucket = self._bucket_for(context)
        self._q_windows[arm][bucket].append(utility)
        self._round += 1

    # ------------------------------------------------------------------
    # Diagnostics
    # ------------------------------------------------------------------

    def quality_estimates(self) -> dict[str, dict[int, dict[str, float]]]:
        """Snapshot of all sliding-mean estimates, keyed by ``arm.value → bucket → stats``."""
        out: dict[str, dict[int, dict[str, float]]] = {}
        for arm, windows in self._q_windows.items():
            out[arm.value] = {
                b: {
                    "n_samples": len(w),
                    "q_hat": (sum(w) / len(w)) if w else self.q_init,
                }
                for b, w in enumerate(windows)
            }
        return out


__all__ = ["PMGreedyPolicy"]
