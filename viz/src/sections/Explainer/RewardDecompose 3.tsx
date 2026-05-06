import { useState } from "react";
import Caption from "../../components/Caption";
import styles from "./Explainer.module.css";

/**
 * Two-step reveal of the reward formula:
 *   Step A: utility = q − ν·f
 *   Step B: PA_reward = (1 − λ_norm) · utility − λ_norm · c̃
 *
 * Each term is clickable; the panel below explains what role it plays
 * and which ablation removes it.
 */

type Term = "q" | "nu_f" | "one_minus_lambda" | "lambda_c";

const EXPLAIN: Record<
  Term,
  { title: string; body: string; ablation?: string }
> = {
  q: {
    title: "q  ·  task quality",
    body:
      "Per-task evaluator score in [0, 1]. Pass@1 for coding, EM/F1 for " +
      "closed-form QA, LLM-as-judge for open-ended T3b. The only direct " +
      "signal of provider competence.",
  },
  nu_f: {
    title: "ν · f  ·  failure penalty",
    body:
      "Failure indicator f ∈ {0, 1}; ν = 0.5 (locked, not tuned per " +
      "experiment). This term is what tells PA-DCT P-flaky apart from " +
      "P-mid: both have the same nominal cost and base model, but " +
      "P-flaky times out 40% of the time and P-mid does not.",
    ablation:
      "ν is a locked reward constant, not a separately ablated component. " +
      "Sensitivity analysis for ν ∈ {0.1, 0.5, 1.0} lives in paper Appendix E.",
  },
  one_minus_lambda: {
    title: "(1 − λ_norm) · utility  ·  intrinsic-value weight",
    body:
      "Convex weight on utility. When the wallet is fresh (low " +
      "burn_excess), λ_norm ≈ 0 and the agent pays full attention to " +
      "quality. As the wallet drains, weight transfers to the cost term.",
  },
  lambda_c: {
    title: "λ_norm · c̃  ·  cost penalty",
    body:
      "λ_norm = sigmoid(α · burn_excess) ∈ (0, 1) — bounded, monotone " +
      "in budget pressure. c̃ is normalized cost. Together, this term " +
      "steers PA-DCT off premium-priced arms once the budget is at risk.",
    ablation:
      "Ablation A3 (no payment-aware) drops λ-aware cost weighting " +
      "entirely; without it cum_PA collapses to negative values across " +
      "scenarios — the single most load-bearing component of PA-DCT.",
  },
};

export default function RewardDecompose() {
  const [stage, setStage] = useState<"A" | "B">("A");
  const [term, setTerm] = useState<Term | null>(null);

  return (
    <div className={styles.reward}>
      <h2>Reward, in two steps</h2>
      <p className="lede">
        We separate intrinsic provider value from decision-time budget
        pressure. The posterior tracks the first; the selector applies the
        second.
      </p>

      <div className={styles.toggle}>
        <button
          type="button"
          className={`${styles.toggleBtn} ${
            stage === "A" ? styles.toggleBtnActive : ""
          }`}
          onClick={() => setStage("A")}
        >
          1 · utility
        </button>
        <button
          type="button"
          className={`${styles.toggleBtn} ${
            stage === "B" ? styles.toggleBtnActive : ""
          }`}
          onClick={() => setStage("B")}
        >
          2 · PA_reward
        </button>
      </div>

      <div className={styles.formulaCard}>
        {stage === "A" && (
          <div className={styles.formulaStep}>
            <div className={styles.formulaLabel}>
              intrinsic value · used to update the posterior
            </div>
            <div className={styles.formula}>
              <span>utility</span>
              <span> = </span>
              <span
                className={`${styles.term} ${
                  term === "q" ? styles.termSelected : ""
                }`}
                onClick={() => setTerm("q")}
              >
                q
              </span>
              <span> − </span>
              <span
                className={`${styles.term} ${
                  term === "nu_f" ? styles.termSelected : ""
                }`}
                onClick={() => setTerm("nu_f")}
              >
                ν·f
              </span>
              <span style={{ color: "#888", marginLeft: 14 }}>
                ∈ [−ν, +1]
              </span>
            </div>
          </div>
        )}

        {stage === "B" && (
          <div className={styles.formulaStep}>
            <div className={styles.formulaLabel}>
              payment-aware reward · used to rank arms at selection time
            </div>
            <div className={styles.formula}>
              <span>PA_reward</span>
              <span> = </span>
              <span
                className={`${styles.term} ${
                  term === "one_minus_lambda" ? styles.termSelected : ""
                }`}
                onClick={() => setTerm("one_minus_lambda")}
              >
                (1 − λ_norm)·utility
              </span>
              <span> − </span>
              <span
                className={`${styles.term} ${
                  term === "lambda_c" ? styles.termSelected : ""
                }`}
                onClick={() => setTerm("lambda_c")}
              >
                λ_norm·c̃
              </span>
              <span style={{ color: "#888", marginLeft: 14 }}>
                ∈ [−1, +1]
              </span>
            </div>
            <div className={styles.formula} style={{ fontSize: "0.92rem", color: "#888" }}>
              with λ_norm = λ_t / (1 + λ_t) = sigmoid(α · burn_excess)
            </div>
          </div>
        )}

        {term && (
          <div className={styles.termExplain}>
            <h4>{EXPLAIN[term].title}</h4>
            <p style={{ margin: "4px 0" }}>{EXPLAIN[term].body}</p>
            {EXPLAIN[term].ablation && (
              <p style={{ margin: "4px 0", color: "var(--c-text-muted)" }}>
                <strong>Ablation:</strong> {EXPLAIN[term].ablation}
              </p>
            )}
          </div>
        )}
      </div>

      <Caption label="Why this split">
        Earlier drafts used <code>r = q − λ·c̃ − μ·l̃ − ν·f</code>. We dropped
        the latency term (no provider or scenario was designed around
        latency) and replaced subtractive λ with a sigmoid convex
        combination. The result is bounded in [−1, +1], which is what
        standard contextual / discounted Thompson-sampling regret bounds
        expect. Source: <code>logs/reward_design_rationale.md</code>{" "}
        (2026-05-02).
      </Caption>
    </div>
  );
}
