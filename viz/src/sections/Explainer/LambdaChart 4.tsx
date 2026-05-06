import { useMemo } from "react";
import {
  Area,
  CartesianGrid,
  ComposedChart,
  Line,
  ReferenceDot,
  ResponsiveContainer,
  XAxis,
  YAxis,
  Tooltip,
} from "recharts";
import Caption from "../../components/Caption";

/**
 * λ_norm vs. burn_excess.  λ_norm = sigmoid(α · burn_excess), with α = 2.
 * The S-curve makes explicit that early rounds favor utility and late
 * rounds favor cost suppression — the convex combination keeps PA_reward
 * bounded in [-1, +1].
 */

const ALPHA = 2.0;

export default function LambdaChart() {
  const data = useMemo(() => {
    const out: { burn_excess: number; lambda_norm: number }[] = [];
    for (let x = -0.3; x <= 1.5; x += 0.02) {
      const lam = Math.exp(ALPHA * x);
      out.push({
        burn_excess: Number(x.toFixed(2)),
        lambda_norm: Number((lam / (1 + lam)).toFixed(4)),
      });
    }
    return out;
  }, []);

  return (
    <div style={{ marginTop: 36 }}>
      <h2>Budget pressure → cost weight</h2>
      <p className="lede">
        λ_norm is how much weight the selector puts on cost relative to
        utility. It rises smoothly with budget pressure but never escapes
        (0, 1), so PA_reward stays bounded in [-1, +1] and standard
        Thompson-sampling regret bounds apply.
      </p>

      <div
        style={{
          background: "var(--c-surface)",
          border: "1px solid var(--c-border)",
          borderRadius: 10,
          padding: "16px 18px 8px 18px",
          marginTop: 14,
        }}
      >
        <ResponsiveContainer width="100%" height={240}>
          <ComposedChart
            data={data}
            margin={{ top: 8, right: 16, left: 0, bottom: 26 }}
          >
            <CartesianGrid stroke="#eee" strokeDasharray="3 3" />
            <XAxis
              dataKey="burn_excess"
              type="number"
              domain={[-0.3, 1.5]}
              tickFormatter={(v) => v.toFixed(1)}
              tick={{ fontSize: 11, fill: "#666" }}
              label={{
                value: "burn_excess  (positive = over-spending)",
                position: "insideBottom",
                offset: -10,
                fill: "#666",
                fontSize: 11,
              }}
            />
            <YAxis
              domain={[0, 1]}
              tick={{ fontSize: 11, fill: "#666" }}
              label={{
                value: "λ_norm",
                angle: -90,
                position: "insideLeft",
                fill: "#666",
                fontSize: 11,
                dy: 30,
              }}
            />
            <Tooltip
              contentStyle={{ fontSize: 12 }}
              formatter={(v: number) => v.toFixed(3)}
            />
            <Area
              type="monotone"
              dataKey="lambda_norm"
              stroke="#1a6bff"
              fill="#1a6bff"
              fillOpacity={0.12}
            />
            <Line
              type="monotone"
              dataKey="lambda_norm"
              stroke="#1a6bff"
              strokeWidth={2.4}
              dot={false}
            />
            {/* Annotations */}
            <ReferenceDot x={0} y={0.5} r={4} fill="#444" stroke="none" />
            <ReferenceDot x={0.5} y={0.731} r={4} fill="#444" stroke="none" />
            <ReferenceDot x={1.0} y={0.881} r={4} fill="#444" stroke="none" />
          </ComposedChart>
        </ResponsiveContainer>
      </div>

      <Caption label="How to read it">
        At <code>burn_excess = 0</code> (on plan), λ_norm = 0.5 — equal
        weight on utility and cost. By <code>burn_excess = 1.0</code>{" "}
        (running ~e² above plan), λ_norm ≈ 0.88 and the selector almost
        ignores quality differences in favor of cheap arms. Ablation A3
        (no payment-aware) drops λ-aware cost weighting entirely; cum_PA
        then collapses across all scenarios.
      </Caption>
    </div>
  );
}
