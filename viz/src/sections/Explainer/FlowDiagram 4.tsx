import { useState } from "react";
import Caption from "../../components/Caption";
import styles from "./Explainer.module.css";

/**
 * 6-step PA-DCT loop. Step 4 (x402 Payment Executor) is rendered grayed /
 * dashed and labeled "out of scope" — the boundary 402Pilot's contribution
 * stops at.
 */

type StepKey = "ctx" | "budget" | "selector" | "x402" | "evaluator" | "update";

interface Step {
  key: StepKey;
  label: string;
  oos?: boolean;
  title: string;
  body: string;
  code?: string;
}

const STEPS: Step[] = [
  {
    key: "ctx",
    label: "Context Encoder",
    title: "Context Encoder · §2.1",
    body:
      "Builds a fixed-dimension feature vector x_t from the task descriptor: " +
      "task type one-hot (T1/T2/T3a/T3b), difficulty estimate, " +
      "remaining-budget ratio, remaining-time ratio, per-provider EWMA " +
      "quality / cost / latency / failure, and time-since-last-update.",
    code: "x_t ∈ ℝ^d   (pure function; same input → same vector)",
  },
  {
    key: "budget",
    label: "Budget Manager",
    title: "Budget Manager · §2.2",
    body:
      "Tracks remaining budget B_remaining and remaining rounds T_remaining; " +
      "outputs the budget-pressure multiplier λ_t. Candidates whose cost " +
      "exceeds the remaining budget are blocked.",
    code: "λ_t = exp(α · burn_excess_t)        λ_norm = λ_t / (1 + λ_t) ∈ (0,1)",
  },
  {
    key: "selector",
    label: "Service Selector (PA-DCT)",
    title: "Service Selector · PA-DCT (§2.3, paper §5)",
    body:
      "Thompson-samples each arm's posterior over utility, computes a " +
      "forward-looking PA score (1 − λ_norm)·û − λ_norm·c̃ for every " +
      "candidate, and picks the argmax. Posteriors are updated with " +
      "utility (no λ inside) so they track intrinsic provider quality " +
      "independent of decision-time budget pressure.",
    code: "a* = argmax_k  (1 − λ_norm)·û_k − λ_norm·c̃_k",
  },
  {
    key: "x402",
    label: "x402 Payment Executor",
    oos: true,
    title: "x402 Payment Executor · OUT OF SCOPE (§2.4)",
    body:
      "Issues the paid HTTP request, attaches the payment proof, awaits the " +
      "response, handles timeouts. We wrap an existing x402 client; we do " +
      "not modify the protocol. The outcome (cost, latency, failure flag) " +
      "flows back into PA-DCT as bandit feedback.",
    code: "pay_and_call(provider_id, payload) → response, cost, latency, fail",
  },
  {
    key: "evaluator",
    label: "Evaluator",
    title: "Evaluator · §2.5",
    body:
      "Scores response quality q_t ∈ [0,1] per task type: pass@1 for " +
      "coding (T1), EM/F1 for closed-form QA (T2 / T3a), LLM-as-judge for " +
      "open-ended web search (T3b). Scores are deterministic at replay time.",
    code: "q_t = evaluator(task, response)",
  },
  {
    key: "update",
    label: "Reward + Posterior Update",
    title: "Reward Calculator + Policy Updater · §2.6, §2.7",
    body:
      "Computes utility = q − ν·f and PA_reward = (1 − λ_norm)·utility − " +
      "λ_norm·c̃. The arm's posterior sufficient statistics are discounted " +
      "by γ < 1 (non-stationary adaptation), then incremented with the " +
      "new utility sample.",
    code: "utility = q − ν·f          PA_reward = (1 − λ_n)·utility − λ_n·c̃",
  },
];

export default function FlowDiagram() {
  const [active, setActive] = useState<StepKey>("selector");
  const step = STEPS.find((s) => s.key === active)!;

  return (
    <div className={styles.flow}>
      <h2>One round of PA-DCT</h2>
      <p className="lede">
        The decision layer sits between the agent's planner and the x402
        executor. Click any step to expand. Step 4 is grayed because it is
        out of scope: 402Pilot does not modify x402; it decides{" "}
        <em>before</em> x402 is called and learns <em>after</em>.
      </p>

      <div className={styles.flowGrid}>
        {STEPS.map((s, i) => {
          const cls = [
            styles.flowStep,
            active === s.key ? styles.active : "",
            s.oos ? styles.oos : "",
          ]
            .filter(Boolean)
            .join(" ");
          return (
            <button
              key={s.key}
              type="button"
              className={cls}
              onClick={() => setActive(s.key)}
            >
              <div className={styles.flowStepNum}>step {i + 1}</div>
              <div className={styles.flowStepName}>{s.label}</div>
            </button>
          );
        })}
      </div>

      <div className={`${styles.flowDetail} ${step.oos ? styles.oos : ""}`}>
        <h3>{step.title}</h3>
        <p>{step.body}</p>
        {step.code && (
          <p>
            <code>{step.code}</code>
          </p>
        )}
      </div>

      <Caption label="Why this matters">
        Bandit, not RL: only the chosen arm is observed each round, payments
        are irreversible, and reward is immediate. PA-DCT's contribution is
        steps 1–3 and step 6. x402 (step 4) is the settlement boundary we
        deliberately do not cross.
      </Caption>
    </div>
  );
}
