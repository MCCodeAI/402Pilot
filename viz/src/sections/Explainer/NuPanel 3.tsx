import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  ResponsiveContainer,
  XAxis,
  YAxis,
  Tooltip,
  ReferenceLine,
} from "recharts";
import Caption from "../../components/Caption";

/**
 * Mini bar chart: P-flaky's expected utility for ν ∈ {0, 0.1, 0.5, 1, 2}.
 * Numbers computed from S1 seed_0: P-flaky's mean quality on non-failure
 * is ~0.86 (effectively P-mid quality), failure rate 38.5%, so
 *     E[utility] = 0.615 · 0.86 − 0.385 · ν.
 */

const DATA = [
  { nu: 0.0, e_util: 0.529, label: "0.0" },
  { nu: 0.1, e_util: 0.490, label: "0.1" },
  { nu: 0.5, e_util: 0.336, label: "0.5  (locked)" },
  { nu: 1.0, e_util: 0.144, label: "1.0" },
  { nu: 2.0, e_util: -0.241, label: "2.0" },
];

export default function NuPanel() {
  return (
    <div style={{ marginTop: 36 }}>
      <h2>Why ν = 0.5</h2>
      <p className="lede">
        ν is the failure-penalty weight inside <code>utility = q − ν·f</code>.
        At ν = 0.5, P-flaky's expected utility (under 40% timeout rate)
        sits clearly below P-mid's 0.81 without the cost-vs-quality story
        being dominated by failures. Locked across all experiments — not
        tuned per scenario.
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
        <ResponsiveContainer width="100%" height={210}>
          <BarChart
            data={DATA}
            margin={{ top: 8, right: 16, left: 0, bottom: 26 }}
          >
            <CartesianGrid stroke="#eee" strokeDasharray="3 3" />
            <XAxis
              dataKey="label"
              tick={{ fontSize: 11, fill: "#666" }}
              label={{
                value: "ν  (failure penalty)",
                position: "insideBottom",
                offset: -10,
                fill: "#666",
                fontSize: 11,
              }}
            />
            <YAxis
              tick={{ fontSize: 11, fill: "#666" }}
              domain={[-0.5, 0.6]}
              label={{
                value: "E[utility] for P-flaky",
                angle: -90,
                position: "insideLeft",
                fill: "#666",
                fontSize: 11,
                dy: 70,
              }}
            />
            <Tooltip
              contentStyle={{ fontSize: 12 }}
              formatter={(v: number) => v.toFixed(3)}
              labelFormatter={(l) => `ν = ${l}`}
            />
            <ReferenceLine y={0.81} stroke="#2e7df7" strokeDasharray="3 3" />
            <ReferenceLine y={0} stroke="#aaa" />
            <Bar dataKey="e_util" radius={[3, 3, 0, 0]}>
              {DATA.map((d) => (
                <Cell
                  key={d.nu}
                  fill={d.nu === 0.5 ? "#1a6bff" : "#b6cdf6"}
                />
              ))}
            </Bar>
          </BarChart>
        </ResponsiveContainer>
        <div
          style={{
            fontSize: "0.78rem",
            color: "#888",
            textAlign: "right",
            marginTop: -8,
          }}
        >
          dashed line = E[utility] for P-mid (0.81)
        </div>
      </div>

      <Caption label="Why this value">
        With ν = 0 P-flaky's E[utility] ≈ 0.53 — close to P-cheap's 0.67
        and indistinguishable from a marginal-quality arm. ν = 2 lets a
        single failure swamp a round (E[utility] negative). ν = 0.5
        gives a 0.48-utility gap to P-mid (0.82 vs 0.34) while keeping
        the cost-vs-quality story intact. Numbers above are computed
        directly from S1 seed_0; sensitivity for ν ∈ {"{"}0.1, 0.5, 1.0{"}"}{" "}
        across all seeds lives in paper Appendix E.
      </Caption>
    </div>
  );
}
