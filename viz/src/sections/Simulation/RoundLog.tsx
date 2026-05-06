import { useMemo } from "react";
import type { RoundRecord } from "../../data/types";
import styles from "./Simulation.module.css";

interface Props {
  records: RoundRecord[];
  upToRound: number;
  /** Maximum number of rows to render. */
  windowSize?: number;
}

const COLOR: Record<string, string> = {
  "P-cheap": "#6c8ebf",
  "P-mid": "#2e7df7",
  "P-premium": "#2da14a",
  "P-adv": "#d44b3a",
  "P-flaky": "#e8a13a",
};

/**
 * Streaming log of the last `windowSize` rounds. Rows where the agent
 * picked P-adv or where a failure occurred are flagged in red.
 */
export default function RoundLog({ records, upToRound, windowSize = 12 }: Props) {
  const rows = useMemo(() => {
    const upto = records.filter((r) => r.round <= upToRound);
    return upto.slice(Math.max(0, upto.length - windowSize)).reverse();
  }, [records, upToRound, windowSize]);

  return (
    <div className={styles.log}>
      <div className={`${styles.logRow} ${styles.logHeader}`}>
        <span>t</span>
        <span>task</span>
        <span>arm</span>
        <span>q</span>
        <span>cost</span>
        <span>util</span>
        <span>reward</span>
      </div>
      {rows.map((r) => {
        const flagged = r.arm === "P-adv" || r.failure === 1;
        return (
          <div
            key={r.round}
            className={`${styles.logRow} ${flagged ? styles.logRowFlagged : ""}`}
          >
            <span>{r.round}</span>
            <span>{r.task_type}</span>
            <span style={{ color: COLOR[r.arm], fontWeight: 600 }}>
              {r.arm}
            </span>
            <span>{r.quality.toFixed(2)}</span>
            <span>${r.cost.toFixed(3)}</span>
            <span>{r.utility.toFixed(2)}</span>
            <span>
              {r.reward >= 0 ? "+" : ""}
              {r.reward.toFixed(2)}
            </span>
          </div>
        );
      })}
    </div>
  );
}
