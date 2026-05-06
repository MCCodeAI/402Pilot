import type { ScenarioId, TaskType } from "../../data/types";
import styles from "./Simulation.module.css";

interface Props {
  scenario: ScenarioId;
  taskType: TaskType | "all";
  seed: number;
  speed: number;
  playing: boolean;
  onScenario: (s: ScenarioId) => void;
  onTaskType: (t: TaskType | "all") => void;
  onSeed: (n: number) => void;
  onSpeed: (n: number) => void;
  onTogglePlay: () => void;
}

const SCENARIOS: ScenarioId[] = ["S1", "S2", "S3"];
const TASK_TYPES: (TaskType | "all")[] = ["all", "T1", "T2", "T3a", "T3b"];
const SPEEDS: number[] = [1, 5, 25, 100];

export default function ControlBar({
  scenario,
  taskType,
  seed,
  speed,
  playing,
  onScenario,
  onTaskType,
  onSeed,
  onSpeed,
  onTogglePlay,
}: Props) {
  return (
    <div className={styles.controlBar}>
      <div className={styles.controlGroup}>
        <span className={styles.controlLabel}>scenario</span>
        <div className={styles.tabStrip}>
          {SCENARIOS.map((s) => (
            <button
              key={s}
              type="button"
              className={`${styles.tabBtn} ${
                scenario === s ? styles.tabBtnActive : ""
              }`}
              onClick={() => onScenario(s)}
            >
              {s}
            </button>
          ))}
        </div>
      </div>

      <div className={styles.controlGroup}>
        <span className={styles.controlLabel}>task</span>
        <div className={styles.tabStrip}>
          {TASK_TYPES.map((t) => (
            <button
              key={t}
              type="button"
              className={`${styles.tabBtn} ${
                taskType === t ? styles.tabBtnActive : ""
              }`}
              onClick={() => onTaskType(t)}
            >
              {t}
            </button>
          ))}
        </div>
      </div>

      <div className={styles.controlGroup}>
        <span className={styles.controlLabel}>seed</span>
        <input
          type="range"
          min={0}
          max={29}
          value={seed}
          onChange={(e) => onSeed(Number(e.target.value))}
          style={{ width: 100 }}
        />
        <span style={{ minWidth: 24, fontVariantNumeric: "tabular-nums" }}>
          {seed}
        </span>
      </div>

      <div className={styles.controlGroup}>
        <span className={styles.controlLabel}>speed</span>
        <div className={styles.tabStrip}>
          {SPEEDS.map((sp) => (
            <button
              key={sp}
              type="button"
              className={`${styles.tabBtn} ${
                speed === sp ? styles.tabBtnActive : ""
              }`}
              onClick={() => onSpeed(sp)}
            >
              {sp}×
            </button>
          ))}
        </div>
      </div>

      <button
        type="button"
        className={styles.playBtn}
        onClick={onTogglePlay}
      >
        {playing ? "Pause" : "Play"}
      </button>
    </div>
  );
}
