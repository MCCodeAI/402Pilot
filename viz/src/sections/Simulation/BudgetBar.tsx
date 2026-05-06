import type { RoundRecord, ScenarioId } from "../../data/types";
import styles from "./Simulation.module.css";

interface Props {
  records: RoundRecord[];
  upToRound: number;
  scenario: ScenarioId;
  totalRounds: number;
  budget: number;
}

const EVENT_LINES: Record<ScenarioId, { round: number; label: string }[]> = {
  S1: [],
  S2: [
    { round: 3000, label: "P-prem drop" },
    { round: 5500, label: "P-flaky spike" },
  ],
  S3: [{ round: 1000, label: "S3 promo" }],
};

export default function BudgetBar({
  records,
  upToRound,
  scenario,
  totalRounds,
  budget,
}: Props) {
  // Latest spend at upToRound
  let remaining = budget;
  for (const r of records) {
    if (r.round > upToRound) break;
    remaining = r.budget_remaining;
  }
  const used = budget - remaining;
  const pct = Math.max(0, Math.min(100, (remaining / budget) * 100));

  return (
    <>
      <div className={styles.budgetBar}>
        <div className={styles.budgetFill} style={{ width: `${pct}%` }} />
        {EVENT_LINES[scenario].map((ev) => (
          <span key={ev.round}>
            <span
              className={styles.eventTick}
              style={{ left: `${(ev.round / totalRounds) * 100}%` }}
            />
            <span
              className={styles.eventLabel}
              style={{ left: `${(ev.round / totalRounds) * 100}%` }}
            >
              {ev.label}
            </span>
          </span>
        ))}
      </div>
      <div className={styles.budgetMeta}>
        <span>
          remaining <strong>${remaining.toFixed(3)}</strong> of ${budget.toFixed(2)}
        </span>
        <span>
          spent <strong>${used.toFixed(3)}</strong> · round {upToRound} / {totalRounds}
        </span>
      </div>
    </>
  );
}
