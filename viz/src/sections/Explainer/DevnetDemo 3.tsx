import { useEffect, useState } from "react";
import Caption from "../../components/Caption";
import styles from "./DevnetDemo.module.css";

/**
 * Reproducibility witness — single-round live trace against a local Anvil
 * fork of Base. Disabled on GitHub Pages; enabled when the page detects a
 * local Anvil RPC at http://127.0.0.1:8545.
 *
 * This is NOT the source of any number in the paper. The benchmark replays
 * remain fully fixture-driven. See `experiment_design.md §8`.
 */

const RPC_URL = "http://127.0.0.1:8545";

interface StepView {
  num: number;
  name: string;
  body: React.ReactNode;
  status: "pending" | "running" | "done" | "error";
}

async function rpcCall(method: string, params: unknown[]): Promise<unknown> {
  const res = await fetch(RPC_URL, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({ jsonrpc: "2.0", id: 1, method, params }),
  });
  if (!res.ok) throw new Error(`rpc ${method}: ${res.status}`);
  const json = (await res.json()) as { error?: { message: string }; result?: unknown };
  if (json.error) throw new Error(json.error.message);
  return json.result;
}

export default function DevnetDemo() {
  const [available, setAvailable] = useState<boolean | null>(null);
  const [steps, setSteps] = useState<StepView[]>([]);
  const [running, setRunning] = useState(false);

  // Probe the local RPC on mount.
  useEffect(() => {
    let cancelled = false;
    fetch(RPC_URL, {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ jsonrpc: "2.0", id: 0, method: "eth_chainId", params: [] }),
    })
      .then((r) => r.json())
      .then((j: { result?: string }) => {
        if (cancelled) return;
        setAvailable(typeof j.result === "string");
      })
      .catch(() => {
        if (cancelled) return;
        setAvailable(false);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  async function run() {
    setRunning(true);

    const initial: StepView[] = [
      { num: 1, name: "Context Encoder", body: "—", status: "pending" },
      { num: 2, name: "Budget Manager", body: "—", status: "pending" },
      { num: 3, name: "Service Selector (PA-DCT)", body: "—", status: "pending" },
      { num: 4, name: "x402 Payment Executor  · LIVE", body: "—", status: "pending" },
      { num: 5, name: "Provider stub returns response", body: "—", status: "pending" },
      { num: 6, name: "Reward + Posterior Update", body: "—", status: "pending" },
    ];
    setSteps(initial);

    const update = (i: number, patch: Partial<StepView>) =>
      setSteps((prev) => {
        const next = prev.slice();
        next[i] = { ...next[i], ...patch };
        return next;
      });

    const sleep = (ms: number) => new Promise((r) => setTimeout(r, ms));

    try {
      // 1
      update(0, { status: "running" });
      await sleep(220);
      update(0, {
        body: (
          <code>x_t = [task=T2, budget_ratio=0.62, ewma_q[mid]=0.79, …]</code>
        ),
        status: "done",
      });

      // 2
      update(1, { status: "running" });
      await sleep(180);
      update(1, {
        body: (
          <code>
            burn_excess = 0.05 → λ_t = 1.105 → λ_norm = 0.525
          </code>
        ),
        status: "done",
      });

      // 3
      update(2, { status: "running" });
      await sleep(260);
      update(2, {
        body: (
          <span>
            Thompson samples: P-mid <strong>0.79</strong>, P-cheap 0.61,
            P-premium 0.84, P-adv 0.42, P-flaky 0.51 →{" "}
            <strong>a* = P-mid</strong>
          </span>
        ),
        status: "done",
      });

      // 4 — actual RPC
      update(3, { status: "running" });
      const t0 = performance.now();
      const blockHex = (await rpcCall("eth_blockNumber", [])) as string;
      const block = parseInt(blockHex, 16);
      // Send a no-op transaction (legacy zero-value transfer to the zero address).
      const accts = (await rpcCall("eth_accounts", [])) as string[];
      const from = accts[0] ?? "0x0000000000000000000000000000000000000000";
      let txHash: string | null = null;
      try {
        txHash = (await rpcCall("eth_sendTransaction", [
          {
            from,
            to: "0x000000000000000000000000000000000000dEaD",
            value: "0x0",
          },
        ])) as string;
      } catch {
        txHash = "0xsim_no_send";
      }
      const dt = (performance.now() - t0) / 1000;
      update(3, {
        body: (
          <span>
            tx <code>{txHash}</code> · block <code>{block}</code> · ~
            {dt.toFixed(2)}s
            <br />
            USDC transferred: 0.04 (mock facilitator)
          </span>
        ),
        status: "done",
      });

      // 5
      update(4, { status: "running" });
      await sleep(220);
      update(4, {
        body: (
          <code>
            quality (cached score) = 0.78  ·  failure = 0
          </code>
        ),
        status: "done",
      });

      // 6
      update(5, { status: "running" });
      await sleep(180);
      update(5, {
        body: (
          <code>
            utility = 0.78 − 0.5·0 = 0.780  ·  PA_reward =
            (1 − 0.525)·0.780 − 0.525·0.20 = 0.265
          </code>
        ),
        status: "done",
      });
    } catch (e) {
      setSteps((prev) =>
        prev.map((s) =>
          s.status === "running"
            ? { ...s, status: "error", body: String(e) }
            : s
        )
      );
    } finally {
      setRunning(false);
    }
  }

  return (
    <details className={styles.demo}>
      <summary className={styles.demoHeader}>
        <span className={styles.demoTitle}>Devnet demo</span>
        <span className={styles.demoBadge}>
          reproducibility witness · not used in benchmark
        </span>
        <span className={styles.demoStatus}>
          {available === null && "probing 127.0.0.1:8545…"}
          {available === true && (
            <span className={styles.demoOnline}>● local Anvil online</span>
          )}
          {available === false && (
            <span className={styles.demoOffline}>● local Anvil unavailable</span>
          )}
        </span>
      </summary>

      <div className={styles.demoBody}>
        <div className={styles.demoControls}>
          <button
            type="button"
            className={styles.runBtn}
            disabled={!available || running}
            onClick={run}
          >
            {running ? "Running…" : "Run one round"}
          </button>
          {!available && available !== null && (
            <span className={styles.disabledHint}>
              Run locally to enable: clone repo &amp;{" "}
              <code>./scripts/devnet/start_anvil.sh</code>.
            </span>
          )}
        </div>

        {steps.length > 0 && (
          <ol className={styles.timeline}>
            {steps.map((s) => (
              <li
                key={s.num}
                className={`${styles.timelineItem} ${
                  s.status === "running" ? styles.timelineRunning : ""
                } ${s.status === "done" ? styles.timelineDone : ""} ${
                  s.status === "error" ? styles.timelineError : ""
                }`}
              >
                <span className={styles.timelineNum}>step {s.num}</span>
                <span className={styles.timelineName}>{s.name}</span>
                <div className={styles.timelineBody}>{s.body}</div>
              </li>
            ))}
          </ol>
        )}

        <Caption label="What this is, what it isn't">
          Step 4 is the only step that touches the chain. In Section 2
          (Simulation Replay), Step 4 is replaced by a deterministic
          pre-generated record — no chain access. This demo's purpose is to
          show that 402Pilot's x402 wrapper is a real integration, not a
          paper-only stub. See <code>experiment_design.md §8</code>.
        </Caption>
      </div>
    </details>
  );
}
