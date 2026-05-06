/**
 * Type contracts for fixtures under `viz/public/data/`.
 *
 * The JSONL `RoundRecord` mirrors the system-design §3 logging contract:
 * `{round, context, arm, cost, latency, quality, failure, utility, reward,
 *   budget_remaining}`.
 *
 * Reward / utility convention (per `logs/reward_design_rationale.md`):
 *   utility   = q − ν · f                            ∈ [-ν, +1]
 *   λ_norm    = λ_t / (1 + λ_t)                       ∈ (0, 1)
 *   PA_reward = (1 − λ_norm) · utility − λ_norm · c̃   ∈ [-1, +1]
 */

export type ProviderId =
  | "P-cheap"
  | "P-mid"
  | "P-premium"
  | "P-adv"
  | "P-flaky";

export const PROVIDERS: readonly ProviderId[] = [
  "P-cheap",
  "P-mid",
  "P-premium",
  "P-adv",
  "P-flaky",
] as const;

export type ScenarioId = "S1" | "S2" | "S3";
export type TaskType = "T1" | "T2" | "T3a" | "T3b";

export type PolicyId =
  | "PA-DCT"
  | "A1-noContext"
  | "A2-noDiscount"
  | "A3-noPaymentAware"
  | "A4-noThompsonSampling"
  | "AlwaysPremium"
  | "AlwaysMid"
  | "AlwaysCheap"
  | "BudgetRule"
  | "Oracle"
  | "Random";

/** Display labels for PolicyId — keep in sync with summary.json. */
export const POLICY_LABEL: Record<PolicyId, string> = {
  Oracle: "Oracle",
  "PA-DCT": "PA-DCT",
  "A1-noContext": "A1 — no context",
  "A2-noDiscount": "A2 — no discount",
  "A3-noPaymentAware": "A3 — no payment-aware (no λ)",
  "A4-noThompsonSampling": "A4 — no Thompson sampling (greedy)",
  BudgetRule: "Budget rule",
  AlwaysPremium: "Always-P-premium",
  AlwaysMid: "Always-P-mid",
  AlwaysCheap: "Always-P-cheap",
  Random: "Random",
};

export const POLICY_COLOR: Record<PolicyId, string> = {
  "PA-DCT": "#1a6bff",
  Oracle: "#2da14a",
  "A1-noContext": "#9a59b5",
  "A2-noDiscount": "#d44b3a",
  "A3-noPaymentAware": "#e8a13a",
  "A4-noThompsonSampling": "#7a7a7a",
  BudgetRule: "#5d8aa8",
  AlwaysPremium: "#000000",
  AlwaysMid: "#3a7a78",
  AlwaysCheap: "#a07050",
  Random: "#b0b0b0",
};

/** One JSONL record from a run log. */
export interface RoundRecord {
  round: number;
  task_type: TaskType;
  arm: ProviderId;
  cost: number;
  latency: number;
  quality: number;
  failure: 0 | 1;
  /** utility = q − ν · f */
  utility: number;
  /** PA_reward = (1 − λ_norm) · utility − λ_norm · c̃ */
  reward: number;
  budget_remaining: number;
}

/** A posterior snapshot used by HiddenTwinTest and ProviderArms. */
export interface PosteriorSnapshot {
  round: number;
  /** Per-arm Gaussian posterior over utility (mean / variance). */
  arms: Record<ProviderId, { mean: number; var: number }>;
}

/** Per-cell aggregate metrics. */
export interface CellSummary {
  scenario: ScenarioId;
  policy: PolicyId;
  task_type: TaskType | "all";
  roi_mean: number;
  roi_std: number;
  success_rate_mean: number;
  success_rate_std: number;
  cumulative_regret_mean: number;
  cumulative_regret_std: number;
  /** Round at which P-adv selection probability first drops below 5%. */
  detect_p_adv_round?: number | null;
}

/** Top-level summary fixture. */
export interface SummaryFixture {
  /** Provenance: which run produced this fixture. */
  run_id: string;
  generated_at: string;
  /** Hyperparameters relevant to viz. */
  params: {
    nu: number;
    alpha: number;
    rounds: number;
    seeds: number;
    note: string;
  };
  cells: CellSummary[];
  /**
   * Cumulative regret curves used by RegretCurve.
   * Down-sampled to keep payload small (e.g. every 50 rounds).
   */
  regret_curves: {
    scenario: ScenarioId;
    policy: PolicyId;
    rounds: number[];
    mean: number[];
    ci_low: number[];
    ci_high: number[];
  }[];
  /** ROI-over-rounds curves used by ROIChart. */
  roi_curves?: {
    scenario: ScenarioId;
    policy: PolicyId;
    rounds: number[];
    mean: number[];
  }[];
  /** Provider-selection-frequency heatmaps used by HeatMap. */
  heatmaps?: {
    scenario: ScenarioId;
    providers: ProviderId[];
    buckets: {
      round_lo: number;
      round_hi: number;
      shares: Record<ProviderId, number>;
    }[];
  }[];
  /** Ablation deltas used by AblationBars. */
  ablations?: {
    scenario: ScenarioId;
    deltas: {
      policy: PolicyId;
      delta_roi: number;
      delta_success: number;
    }[];
  }[];
}
