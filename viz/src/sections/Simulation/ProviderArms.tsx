import { useEffect, useRef } from "react";
import * as d3 from "d3";
import type { RoundRecord } from "../../data/types";
import { PROVIDERS } from "../../data/types";
import styles from "./Simulation.module.css";

interface Props {
  records: RoundRecord[];
  upToRound: number;
}

const COLOR: Record<string, string> = {
  "P-cheap": "#6c8ebf",
  "P-mid": "#2e7df7",
  "P-premium": "#2da14a",
  "P-adv": "#d44b3a",
  "P-flaky": "#e8a13a",
};

/**
 * Per-arm running utility statistics (mean ± stderr) up to the current
 * round. Approximates the policy's posterior view of each provider — for
 * the actual posterior snapshots, see HiddenTwinTest.
 */
export default function ProviderArms({ records, upToRound }: Props) {
  const svgRef = useRef<SVGSVGElement | null>(null);

  useEffect(() => {
    const svg = d3.select(svgRef.current);
    svg.selectAll("*").remove();
    if (records.length === 0) return;

    // Build per-arm running statistics
    const stats: Record<string, { n: number; sum: number; sum2: number }> = {};
    for (const arm of PROVIDERS) {
      stats[arm] = { n: 0, sum: 0, sum2: 0 };
    }
    for (const r of records) {
      if (r.round > upToRound) break;
      const s = stats[r.arm];
      if (!s) continue;
      s.n += 1;
      s.sum += r.utility;
      s.sum2 += r.utility * r.utility;
    }
    const view = PROVIDERS.map((arm) => {
      const { n, sum, sum2 } = stats[arm];
      const mean = n > 0 ? sum / n : 0;
      const variance = n > 1 ? Math.max(0, sum2 / n - mean * mean) : 0.04;
      const stderr = n > 0 ? Math.sqrt(variance) / Math.sqrt(Math.max(n, 1)) : 0.2;
      return { arm, n, mean, lo: mean - 1.96 * stderr, hi: mean + 1.96 * stderr };
    });

    const dims = { w: 460, h: 220, m: { t: 14, r: 16, b: 24, l: 80 } };
    const x = d3
      .scaleLinear()
      .domain([-0.6, 1.05])
      .range([dims.m.l, dims.w - dims.m.r]);

    const y = d3
      .scaleBand<string>()
      .domain(PROVIDERS as unknown as string[])
      .range([dims.m.t, dims.h - dims.m.b])
      .padding(0.3);

    // Axes
    svg
      .append("g")
      .attr("transform", `translate(0,${dims.h - dims.m.b})`)
      .call(d3.axisBottom(x).ticks(5).tickFormat((d) => d3.format(".2f")(d as number)) as any)
      .call((g) => g.selectAll("text").attr("fill", "#666").style("font-size", "10px"))
      .call((g) => g.selectAll(".domain").attr("stroke", "#bbb"));

    svg
      .append("text")
      .attr("x", dims.w / 2)
      .attr("y", dims.h - 4)
      .attr("text-anchor", "middle")
      .attr("font-size", 10)
      .attr("fill", "#666")
      .text("running utility (mean, 95% stderr band)");

    // Zero reference
    svg
      .append("line")
      .attr("x1", x(0))
      .attr("x2", x(0))
      .attr("y1", dims.m.t)
      .attr("y2", dims.h - dims.m.b)
      .attr("stroke", "#ddd");

    // Bars (CI bands) + mean dots
    view.forEach((v) => {
      const yc = (y(v.arm) ?? 0) + y.bandwidth() / 2;
      svg
        .append("rect")
        .attr("x", x(Math.max(v.lo, -0.6)))
        .attr("y", yc - 6)
        .attr("width", Math.max(2, x(Math.min(v.hi, 1.05)) - x(Math.max(v.lo, -0.6))))
        .attr("height", 12)
        .attr("fill", COLOR[v.arm])
        .attr("fill-opacity", 0.22)
        .attr("stroke", COLOR[v.arm])
        .attr("stroke-width", 1);
      svg
        .append("circle")
        .attr("cx", x(v.mean))
        .attr("cy", yc)
        .attr("r", 4)
        .attr("fill", COLOR[v.arm]);
      svg
        .append("text")
        .attr("x", dims.m.l - 8)
        .attr("y", yc + 4)
        .attr("text-anchor", "end")
        .attr("font-size", 11)
        .attr("font-weight", 600)
        .attr("fill", COLOR[v.arm])
        .text(v.arm);
      svg
        .append("text")
        .attr("x", dims.w - dims.m.r)
        .attr("y", yc + 4)
        .attr("text-anchor", "end")
        .attr("font-size", 9)
        .attr("fill", "#999")
        .text(`n=${v.n}`);
    });
  }, [records, upToRound]);

  return <svg ref={svgRef} viewBox="0 0 460 220" className={styles.armSvg} />;
}
