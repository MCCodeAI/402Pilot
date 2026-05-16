"""Within-experiment market scenarios.

A ``Scenario`` is a deterministic pair of round-indexed transforms applied
between the pregen store and the runtime loop:

1. ``effective_price(round, provider_id, spec_price) -> float``
   What the wallet sees when checking affordability and (consistently) when
   recording the spend. Used by both ``run_one_seed`` and
   ``run_true_oracle_seed``.

2. ``transform_record(round, record) -> PregenRecord``
   What the runtime sees after ``PregenStore.get(...)``. May rewrite
   ``cost_usdc``, ``failure_flag``, ``failure_code``, or ``quality_score``.
   Pregen data on disk is never mutated.

Three scenarios are defined here, all locked at the M3.E design freeze
(2026-05-03):

* **S1 — Stationary.** Identity transforms; the calibrated baseline.

* **S2 — Mid Outage.** Round 3000–5500, P-mid ``failure_flag`` is forced
  on a deterministic 30% of rounds (timeout, q=0, cost still charged).
  Real-world precedent: Anthropic Sonnet outages, OpenAI 429 rate-limit
  spikes, Bedrock throttling. Targets ``AlwaysMid`` directly: it eats
  the failures, while a posterior-tracking policy can detect the
  reliability regression and migrate.

* **S3 — Premium Drop.** From round 1000 onwards, P-premium price is
  multiplied by 0.2 ($0.01 → $0.002). Quality and failure rate
  unchanged. Real-world precedent: GPT-4 → GPT-4o, Claude 3 Opus →
  3.5 Sonnet — new flagship tier renders the prior mid-tier
  cost-dominated. Targets ``AlwaysMid`` indirectly: Mid's absolute
  PA-reward is unchanged, but a payment-aware policy that re-weights
  toward the newly-affordable Premium captures regret AlwaysMid
  cannot.

Determinism contract
--------------------
Each scenario exposes its full state via construction args; randomness
flows from a single ``numpy.random.Generator`` passed in at build time.
The factory ``build_scenario`` derives that generator from a key that
*excludes* the ``run_id`` so that — for a fixed master seed — every
policy in a sweep observes the *same* outage pattern. Across seeds, the
master seed alone perturbs the scenario, giving us per-seed variance for
error-bar estimation.

Scenarios deliberately keep their effective-price and record-transform
methods stateless w.r.t. call order: a transform queried twice for the
same round returns the same answer. This lets the True Oracle peek at
every affordable arm in a round without polluting the scenario state.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from numpy.random import Generator

from pilot402.core import (
    FailureCode,
    PregenRecord,
    ProviderId,
    QualityScore,
    ScenarioConfig,
    ScenarioId,
    SeedSource,
)


class Scenario(ABC):
    """Abstract market scenario.

    Implementations MUST be deterministic given their constructor args.
    Methods MUST be safe to call out-of-order or repeatedly for the same
    ``round_idx`` (the True Oracle peeks at all arms each round).
    """

    name: ScenarioId

    @abstractmethod
    def effective_price(
        self,
        round_idx: int,
        provider_id: ProviderId,
        spec_price: float,
    ) -> float:
        """Return the price the wallet should see this round for this arm.

        For S1/S2 this is the unchanged ``spec_price``. For S3, P-premium is
        scaled after the shock round. Used both by ``Wallet.affordable`` and
        for charging via ``record_spend`` (we transform the record's
        ``cost_usdc`` consistently in ``transform_record``).
        """

    @abstractmethod
    def transform_record(
        self,
        round_idx: int,
        record: PregenRecord,
    ) -> PregenRecord:
        """Return the record the runtime should treat as observed.

        ``record`` is the verbatim output of ``PregenStore.get(...)``. The
        scenario may return a modified copy (S2 forces timeouts; S3 scales
        cost). Returned record MUST satisfy the same schema.
        """


# ---------------------------------------------------------------------------
# S1 — Stationary
# ---------------------------------------------------------------------------


class StationaryScenario(Scenario):
    """No-op identity. The calibrated baseline market."""

    name = ScenarioId.S1_STATIONARY

    def effective_price(
        self,
        round_idx: int,
        provider_id: ProviderId,
        spec_price: float,
    ) -> float:
        return spec_price

    def transform_record(
        self,
        round_idx: int,
        record: PregenRecord,
    ) -> PregenRecord:
        return record


# ---------------------------------------------------------------------------
# S2 — Mid Outage
# ---------------------------------------------------------------------------


class MidOutageScenario(Scenario):
    """Reliability regression on a single mid-tier provider.

    Within ``[outage_start, outage_end)``, a deterministic ``outage_failure_rate``
    fraction of rounds force ``target_provider``'s record into a synthetic
    timeout (failure_flag=True, failure_code=TIMEOUT, q=0, cost unchanged).
    Outside that window the scenario is identity.

    The flip pattern is pre-rolled at construction time from the supplied
    ``rng``: this ensures (a) every policy under the same master seed sees
    the same shock pattern and (b) querying the same round repeatedly (as
    the Oracle does, peeking at all arms) is free of side effects.

    Cost is intentionally NOT reduced on the synthetic timeout: in our
    pregen data, P-flaky timeouts also charge full price, so this matches
    the existing failure semantics. From AlwaysMid's perspective, an
    outage is a stream of full-price q=0 rounds — the worst case.
    """

    name = ScenarioId.S2_DEGRADATION

    def __init__(
        self,
        *,
        rng: Generator,
        outage_start: int = 3000,
        outage_end: int = 5500,
        outage_failure_rate: float = 0.30,
        target_provider: ProviderId = ProviderId.P_MID,
    ) -> None:
        if outage_start < 0:
            raise ValueError("outage_start must be non-negative")
        if outage_end <= outage_start:
            raise ValueError("outage_end must be > outage_start")
        if not (0.0 <= outage_failure_rate <= 1.0):
            raise ValueError("outage_failure_rate must lie in [0, 1]")

        self._outage_start = outage_start
        self._outage_end = outage_end
        self._outage_failure_rate = outage_failure_rate
        self._target_provider = target_provider

        # Pre-roll the flip sequence: one Bernoulli draw per round in the
        # outage window. Storing this dict (instead of re-drawing on
        # every call) makes transform_record idempotent for repeated
        # round queries — a hard requirement for the Oracle peek loop.
        n_rounds = outage_end - outage_start
        flips = rng.random(size=n_rounds) < outage_failure_rate
        self._flip_by_round: dict[int, bool] = {
            outage_start + i: bool(flips[i]) for i in range(n_rounds)
        }

    @property
    def outage_start(self) -> int:
        return self._outage_start

    @property
    def outage_end(self) -> int:
        return self._outage_end

    @property
    def outage_failure_rate(self) -> float:
        return self._outage_failure_rate

    def is_outage_round(self, round_idx: int) -> bool:
        """True iff the scenario forces a timeout for ``target_provider`` here."""
        return self._flip_by_round.get(round_idx, False)

    def effective_price(
        self,
        round_idx: int,
        provider_id: ProviderId,
        spec_price: float,
    ) -> float:
        return spec_price

    def transform_record(
        self,
        round_idx: int,
        record: PregenRecord,
    ) -> PregenRecord:
        if record.provider_id != self._target_provider:
            return record
        if not self.is_outage_round(round_idx):
            return record
        # Synthetic timeout: mirror the structure of P-flaky's pregen
        # timeouts. q=0, failure_flag=True, failure_code=TIMEOUT, cost
        # unchanged (provider still charges).
        new_quality = QualityScore(
            q=0.0,
            backend=record.quality_score.backend,
            judge_model_id=record.quality_score.judge_model_id,
            judge_seed=record.quality_score.judge_seed,
        )
        return record.model_copy(
            update={
                "failure_flag": True,
                "failure_code": FailureCode.TIMEOUT,
                "quality_score": new_quality,
            }
        )


# ---------------------------------------------------------------------------
# S3 — Premium Drop
# ---------------------------------------------------------------------------


class PremiumDropScenario(Scenario):
    """Permanent price cut on the premium tier (new-flagship release model).

    From ``shock_round`` onwards, ``target_provider``'s price is multiplied
    by ``price_multiplier`` (default 0.2 → $0.01 → $0.002). Quality, latency,
    failure rate are untouched.

    The transformation is applied to BOTH the affordability price (so
    Wallet.affordable sees the new price) AND ``record.cost_usdc`` (so
    Wallet.record_spend charges the new price). Otherwise the wallet's
    spend trajectory diverges from the affordability check.
    """

    name = ScenarioId.S3_PRICE_SHOCK

    def __init__(
        self,
        *,
        shock_round: int = 1000,
        price_multiplier: float = 0.2,
        target_provider: ProviderId = ProviderId.P_PREMIUM,
    ) -> None:
        if shock_round < 0:
            raise ValueError("shock_round must be non-negative")
        if price_multiplier <= 0:
            raise ValueError("price_multiplier must be > 0")

        self._shock_round = shock_round
        self._price_multiplier = price_multiplier
        self._target_provider = target_provider

    @property
    def shock_round(self) -> int:
        return self._shock_round

    @property
    def price_multiplier(self) -> float:
        return self._price_multiplier

    def _is_active(self, round_idx: int) -> bool:
        return round_idx >= self._shock_round

    def effective_price(
        self,
        round_idx: int,
        provider_id: ProviderId,
        spec_price: float,
    ) -> float:
        if self._is_active(round_idx) and provider_id == self._target_provider:
            return spec_price * self._price_multiplier
        return spec_price

    def transform_record(
        self,
        round_idx: int,
        record: PregenRecord,
    ) -> PregenRecord:
        if not self._is_active(round_idx):
            return record
        if record.provider_id != self._target_provider:
            return record
        return record.model_copy(
            update={"cost_usdc": record.cost_usdc * self._price_multiplier}
        )


# ---------------------------------------------------------------------------
# Tier Compression — Mid + Premium repricing (S3 variant for ablation)
# ---------------------------------------------------------------------------


class TierCompressionScenario(Scenario):
    """Both mid and premium prices drop simultaneously — tier-wide repricing.

    Unlike ``PremiumDropScenario`` (which only changes premium), this scenario
    models a market event in which the provider repositions multiple tiers
    at once. Real-world precedents:

    * **GPT-4o release (2024)**: simultaneous price cuts on GPT-4 turbo and
      GPT-4 — premium dropped ~50% and the prior mid tier was repositioned.
    * **Claude 3.5 Sonnet release**: launched at a price below Claude 3
      Opus, compressing the mid → premium gap.
    * **Anthropic / OpenAI tier consolidation**: as competition intensifies,
      providers compress their pricing ladder to keep the entire stack
      attractive vs. open-source alternatives.

    Default multipliers (0.75 mid, 0.25 premium) yield a post-shock cheap :
    mid : premium ratio of 1 : 3 : 5 (from the calibrated 1 : 4 : 20). This
    is "Path AB" in the M3.E exploration log: it widens the λ window where
    PA-DCT can prefer premium on its high-q task types (T3a, T3b, T1)
    without making AlwaysPremium bankrupt-free or globally dominant.
    """

    name = ScenarioId.S3_PRICE_SHOCK  # logged as S3; differentiate by run_id

    def __init__(
        self,
        *,
        shock_round: int = 3000,
        mid_multiplier: float = 0.75,
        premium_multiplier: float = 0.25,
        mid_provider: ProviderId = ProviderId.P_MID,
        premium_provider: ProviderId = ProviderId.P_PREMIUM,
    ) -> None:
        if shock_round < 0:
            raise ValueError("shock_round must be non-negative")
        if mid_multiplier <= 0 or premium_multiplier <= 0:
            raise ValueError("multipliers must be > 0")

        self._shock_round = shock_round
        self._mid_multiplier = mid_multiplier
        self._premium_multiplier = premium_multiplier
        self._mid_provider = mid_provider
        self._premium_provider = premium_provider

    @property
    def shock_round(self) -> int:
        return self._shock_round

    @property
    def mid_multiplier(self) -> float:
        return self._mid_multiplier

    @property
    def premium_multiplier(self) -> float:
        return self._premium_multiplier

    def _multiplier_for(self, provider_id: ProviderId) -> float | None:
        if provider_id == self._mid_provider:
            return self._mid_multiplier
        if provider_id == self._premium_provider:
            return self._premium_multiplier
        return None

    def _is_active(self, round_idx: int) -> bool:
        return round_idx >= self._shock_round

    def effective_price(
        self,
        round_idx: int,
        provider_id: ProviderId,
        spec_price: float,
    ) -> float:
        if not self._is_active(round_idx):
            return spec_price
        m = self._multiplier_for(provider_id)
        return spec_price * m if m is not None else spec_price

    def transform_record(
        self,
        round_idx: int,
        record: PregenRecord,
    ) -> PregenRecord:
        if not self._is_active(round_idx):
            return record
        m = self._multiplier_for(record.provider_id)
        if m is None:
            return record
        return record.model_copy(
            update={"cost_usdc": record.cost_usdc * m}
        )


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------


def build_scenario(cfg: ScenarioConfig, master_seed: int) -> Scenario:
    """Construct a Scenario from config + master seed.

    The scenario RNG is keyed on the scenario name *only* (``f"scenario/{name}"``),
    not the run_id — so for a given master seed every policy in a sweep sees
    the same shock pattern. Different master seeds (i.e. different seed
    indices) produce different but reproducible patterns, giving us
    per-seed statistical variance.

    ``cfg.kwargs`` is forwarded to the scenario constructor (e.g.
    ``{outage_start: 3000, outage_end: 5500}``). Stationary ignores it.
    """
    if cfg.name == ScenarioId.S1_STATIONARY:
        return StationaryScenario()
    if cfg.name == ScenarioId.S2_DEGRADATION:
        seeds = SeedSource(master_seed)
        rng = seeds.derive(f"scenario/{cfg.name.value}").rng
        return MidOutageScenario(rng=rng, **cfg.kwargs)
    if cfg.name == ScenarioId.S3_PRICE_SHOCK:
        return PremiumDropScenario(**cfg.kwargs)
    raise ValueError(f"Unknown scenario id: {cfg.name!r}")


__all__ = [
    "MidOutageScenario",
    "PremiumDropScenario",
    "Scenario",
    "StationaryScenario",
    "TierCompressionScenario",
    "build_scenario",
]
