import styles from "./Simulation.module.css";
import type { TaskType } from "../../data/types";

interface BadgeData {
  taskType: TaskType;
  round: number | null;
}

interface Props {
  /** Per-task-type detection rounds (null = "not detected within 10k rounds"). */
  badges: BadgeData[];
}

const LABEL: Record<TaskType, string> = {
  T1: "T1 · code",
  T2: "T2 · QA",
  T3a: "T3a · closed-form",
  T3b: "T3b · open-ended",
};

/**
 * Per (task_type) detection round when PA-DCT first stably avoids P-adv.
 * T3b is expected to lag — see paper §7 (evaluator-bounded).
 */
export default function DetectionBadge({ badges }: Props) {
  return (
    <div className={styles.badges}>
      {badges.map((b) => {
        const missing = b.round === null;
        return (
          <span
            key={b.taskType}
            className={`${styles.badge} ${missing ? styles.badgeMissing : ""}`}
            title={
              missing
                ? "P-adv not stably avoided within 10,000 rounds — evaluator-bounded"
                : `P-adv selection prob < 5% from round ${b.round}`
            }
          >
            <span className={styles.badgeKey}>{LABEL[b.taskType]}</span>
            <span className={styles.badgeRound}>
              {missing ? "not detected" : `round ${b.round}`}
            </span>
          </span>
        );
      })}
    </div>
  );
}
