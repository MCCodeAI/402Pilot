import { useEffect, useMemo, useState } from "react";
import ControlBar from "./ControlBar";
import ProviderArms from "./ProviderArms";
import BudgetBar from "./BudgetBar";
import RoundLog from "./RoundLog";
import DetectionBadge from "./DetectionBadge";
import Caption from "../../components/Caption";
import { loadRun, loadSummary } from "../../data/loaders";
import type {
  RoundRecord,
  ScenarioId,
  SummaryFixture,
  TaskType,
} from "../../data/types";
import styles from "./Simulation.module.css";

const TOTAL_ROUNDS = 10000;
const BUDGET = 50.0;  // USDC, per experiments/main.yaml

export default function Simulation() {
  const [scenario, setScenario] = useState<ScenarioId>("S1");
  const [taskType, setTaskType] = useState<TaskType | "all">("all");
  const [seed, setSeed] = useState(0);
  const [speed, setSpeed] = useState(5);
  const [playing, setPlaying] = useState(true);
  const [round, setRound] = useState(0);

  const [records, setRecords] = useState<RoundRecord[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [summary, setSummary] = useState<SummaryFixture | null>(null);

  // Load run fixture (currently seed 0 of S1/S2/S3 from the real
  // scenario_sweep export). Other seeds can be added by re-running
  // scripts/export_viz_data.py with a wider seed range.
  useEffect(() => {
    setError(null);
    loadRun(scenario, "padct", seed)
      .then(setRecords)
      .catch((e) => {
        setRecords([]);
        setError(String(e));
      });
  }, [scenario, seed]);

  useEffect(() => {
    loadSummary().then(setSummary).catch(() => setSummary(null));
  }, []);

  // Filtered records by task type
  const filtered = useMemo(() => {
    if (taskType === "all") return records;
    return records.filter((r) => r.task_type === taskType);
  }, [records, taskType]);

  const maxRound = filtered.length > 0
    ? filtered[filtered.length - 1].round
    : 0;

  // Auto-advance scrubber
  useEffect(() => {
    if (!playing || filtered.length === 0) return;
    const id = window.setInterval(() => {
      setRound((r) => {
        const next = r + speed;
        if (next > maxRound) return 0;
        return next;
      });
    }, 80);
    return () => window.clearInterval(id);
  }, [playing, filtered, maxRound, speed]);

  // Reset round when scenario / task changes
  useEffect(() => {
    setRound(0);
  }, [scenario, taskType, seed]);

  // Detection badges per task type, sourced from the summary fixture
  // (median across 30 seeds, computed by scripts/export_viz_data.py).
  // T3b is deliberately reported as "not detected" because its
  // LLM-as-judge evaluator occasionally accepts P-adv's fluent-but-wrong
  // responses — see paper §7 (evaluator-bounded limitation).
  const badges = useMemo(() => {
    const types: TaskType[] = ["T1", "T2", "T3a", "T3b"];
    return types.map((t) => {
      const cell = summary?.cells.find(
        (c) =>
          c.scenario === scenario && c.policy === "PA-DCT" && c.task_type === t
      );
      return {
        taskType: t,
        round: t === "T3b" ? null : cell?.detect_p_adv_round ?? null,
      };
    });
  }, [summary, scenario]);

  return (
    <section id="simulation" className="section">
      <div className="container">
        <div className="section-eyebrow">§2 — Simulation Replay</div>
        <h1>Watch one run</h1>
        <p className="lede">
          Round-by-round replay of a single seed across S1 / S2 / S3 with a
          task-type filter (T1 / T2 / T3a / T3b). Switch scenario or seed to
          re-load. Detection badges below mark when PA-DCT first stably
          avoids P-adv in each task type.
        </p>

        <ControlBar
          scenario={scenario}
          taskType={taskType}
          seed={seed}
          speed={speed}
          playing={playing}
          onScenario={setScenario}
          onTaskType={setTaskType}
          onSeed={setSeed}
          onSpeed={setSpeed}
          onTogglePlay={() => setPlaying((p) => !p)}
        />

        <div className={styles.scrubber}>
          <input
            type="range"
            min={0}
            max={Math.max(maxRound, 1)}
            value={Math.min(round, maxRound)}
            onChange={(e) => {
              setPlaying(false);
              setRound(Number(e.target.value));
            }}
          />
          <span className={styles.scrubberLabel}>t = {Math.min(round, maxRound)}</span>
        </div>

        {error && (
          <div className="card" style={{ background: "#fff3f0", borderColor: "#f0c8c0", color: "#9a3a2e" }}>
            Run fixture not available for {scenario} seed {seed}. Falling back
            to S1/seed0 once exported by <code>scripts/export_viz_data.py</code>.
            <div style={{ fontSize: "0.82rem", marginTop: 4, color: "#a06a5e" }}>
              {error}
            </div>
          </div>
        )}

        {!error && (
          <>
            <div className={styles.stage}>
              <div className={styles.panel}>
                <h3 className={styles.panelTitle}>Provider arms</h3>
                <ProviderArms
                  records={filtered}
                  upToRound={Math.min(round, maxRound)}
                />
              </div>

              <div className={styles.panel}>
                <h3 className={styles.panelTitle}>Wallet</h3>
                <BudgetBar
                  records={filtered}
                  upToRound={Math.min(round, maxRound)}
                  scenario={scenario}
                  totalRounds={TOTAL_ROUNDS}
                  budget={BUDGET}
                />
                <p
                  style={{
                    margin: "10px 0 0 0",
                    fontSize: "0.84rem",
                    color: "var(--c-text-soft)",
                  }}
                >
                  Always-P-premium would already be at zero by ~round 5,000
                  in S3. PA-DCT's λ_norm flips its preferences in time.
                </p>
              </div>

              <div className={styles.panel}>
                <h3 className={styles.panelTitle}>Round log</h3>
                <RoundLog
                  records={filtered}
                  upToRound={Math.min(round, maxRound)}
                />
              </div>
            </div>

            <div className={styles.panel}>
              <h3 className={styles.panelTitle}>
                P-adv detection · per task type
              </h3>
              <DetectionBadge badges={badges} />
              <Caption label="Why T3b lags">
                Detection = PA-DCT's selection probability for P-adv drops
                below 5% and stays there. T1 / T2 / T3a use deterministic
                evaluators (pass@1, EM/F1) — clean signal, fast detection.
                T3b uses LLM-as-judge for open-ended answers; the judge
                sometimes accepts P-adv's fluent-but-wrong responses, so the
                signal is noisier. This is the limitation made explicit in
                paper §7.
              </Caption>
            </div>
          </>
        )}
      </div>
    </section>
  );
}
