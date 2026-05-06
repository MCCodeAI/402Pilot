import { useEffect, useMemo, useRef, useState } from "react";
import * as d3 from "d3";
import type { PosteriorSnapshot, ProviderId } from "../../data/types";
import Caption from "../../components/Caption";
import styles from "./Explainer.module.css";

/**
 * HiddenTwinTest — the hero chart of Section 1.
 *
 * Three "twin" providers (P-mid / P-adv / P-flaky) share the same nominal
 * cost tier and base model. A rule-based router cannot tell them apart.
 * PA-DCT learns the difference from utility = q − ν·f alone.
 *
 * Each ridge is a Gaussian posterior density over utility, centered at the
 * round's posterior mean with σ = √var. The viewer scrubs across rounds
 * and watches the three ridges separate.
 */

const TWINS: ProviderId[] = ["P-mid", "P-adv", "P-flaky"];

const COLOR_HEX: Record<ProviderId, string> = {
  "P-cheap": "#6c8ebf",
  "P-mid": "#2e7df7",
  "P-premium": "#2da14a",
  "P-adv": "#d44b3a",
  "P-flaky": "#e8a13a",
};

// Reference utility levels (mean utility per arm, S1 PA-DCT seed_0,
// computed from results/scenario_sweep/S1/padct/seed_00.jsonl).  The
// "twin" gap is real but smaller than an analytical model would predict:
// P-adv's "fluent but wrong" answers still earn partial credit on
// objective evaluators, so its mean quality (~0.67) sits closer to
// P-cheap than to zero.  P-flaky's mean utility reflects 38.5% failures
// at ν = 0.5.
const TRUE_UTILITY: Record<ProviderId, number> = {
  "P-cheap": 0.671,
  "P-mid": 0.818,
  "P-premium": 0.887,
  "P-adv": 0.666,
  "P-flaky": 0.336,
};

interface Props {
  snapshots: PosteriorSnapshot[] | null;
}

export default function HiddenTwinTest({ snapshots }: Props) {
  const svgRef = useRef<SVGSVGElement | null>(null);
  const [idx, setIdx] = useState(0);
  const [playing, setPlaying] = useState(true);

  // Keep idx within bounds when snapshots arrive
  useEffect(() => {
    if (!snapshots) return;
    if (idx >= snapshots.length) setIdx(0);
  }, [snapshots, idx]);

  // Auto-play: 12 fps, loop
  useEffect(() => {
    if (!playing || !snapshots || snapshots.length === 0) return;
    const id = window.setInterval(() => {
      setIdx((i) => (i + 1) % snapshots.length);
    }, 90);
    return () => window.clearInterval(id);
  }, [playing, snapshots]);

  const round = snapshots?.[idx]?.round ?? 0;

  const dims = { w: 920, h: 300, m: { t: 28, r: 24, b: 36, l: 90 } };

  // Static x scale [0, 1] over utility
  const xScale = useMemo(
    () => d3.scaleLinear().domain([-0.2, 1.05]).range([dims.m.l, dims.w - dims.m.r]),
    []
  );

  // Three ridge baselines vertically stacked
  const ridgeY = useMemo(() => {
    const inner = dims.h - dims.m.t - dims.m.b;
    const step = inner / TWINS.length;
    return TWINS.map((_, i) => dims.m.t + step * (i + 0.65));
  }, []);

  // Render
  useEffect(() => {
    const svg = d3.select(svgRef.current);
    svg.selectAll("*").remove();
    if (!snapshots || snapshots.length === 0) return;

    const snap = snapshots[idx];

    // X axis (utility)
    const xAxis = d3
      .axisBottom(xScale)
      .tickValues([0, 0.286, 0.5, 0.81, 1])
      .tickFormat((d) => d3.format(".2f")(d as number));
    svg
      .append("g")
      .attr("transform", `translate(0,${dims.h - dims.m.b})`)
      .call(xAxis as any)
      .call((g) => g.selectAll(".domain").attr("stroke", "#bbb"))
      .call((g) => g.selectAll("text").attr("fill", "#666").style("font-size", "11px"));

    svg
      .append("text")
      .attr("x", dims.w / 2)
      .attr("y", dims.h - 6)
      .attr("text-anchor", "middle")
      .attr("font-size", 11)
      .attr("fill", "#666")
      .text("utility = q − ν·f");

    // For each twin, draw the Gaussian density
    TWINS.forEach((arm, i) => {
      const post = snap.arms[arm];
      const mean = post.mean;
      const sigma = Math.sqrt(Math.max(post.var, 1e-4));
      const baseline = ridgeY[i];

      // Sample density on a fine grid in utility space
      const xs = d3.range(-0.2, 1.05, 0.005);
      const density = xs.map((x) => {
        const z = (x - mean) / sigma;
        return Math.exp(-0.5 * z * z) / (sigma * Math.sqrt(2 * Math.PI));
      });

      // Height scaling — fixed per-row max so early rounds (huge variance,
      // short curves) and late rounds (tall narrow peaks) stay visible.
      const maxDensity = 6; // 1/(min sigma * sqrt(2π))
      const rowHeight = (dims.h - dims.m.t - dims.m.b) / TWINS.length - 12;
      const yScale = (d: number) =>
        baseline - Math.min(d, maxDensity) * (rowHeight / maxDensity);

      const area = d3
        .area<number>()
        .x((_, j) => xScale(xs[j]))
        .y0(baseline)
        .y1((d) => yScale(d))
        .curve(d3.curveBasis);

      svg
        .append("path")
        .attr("d", area(density)!)
        .attr("fill", COLOR_HEX[arm])
        .attr("fill-opacity", 0.32)
        .attr("stroke", COLOR_HEX[arm])
        .attr("stroke-width", 1.5);

      // True-value tick (dashed)
      const tx = xScale(TRUE_UTILITY[arm]);
      svg
        .append("line")
        .attr("x1", tx)
        .attr("x2", tx)
        .attr("y1", baseline)
        .attr("y2", baseline - rowHeight - 2)
        .attr("stroke", COLOR_HEX[arm])
        .attr("stroke-dasharray", "3,3")
        .attr("stroke-opacity", 0.65);

      // Provider label on the left
      svg
        .append("text")
        .attr("x", dims.m.l - 10)
        .attr("y", baseline - 2)
        .attr("text-anchor", "end")
        .attr("font-size", 12)
        .attr("font-weight", 600)
        .attr("fill", COLOR_HEX[arm])
        .text(arm);

      // Numeric annotation: posterior mean
      svg
        .append("text")
        .attr("x", dims.m.l - 10)
        .attr("y", baseline + 11)
        .attr("text-anchor", "end")
        .attr("font-size", 10)
        .attr("fill", "#888")
        .text(`μ ≈ ${mean.toFixed(2)}`);
    });

    // True-value legend (bottom-right)
    const legend = svg
      .append("g")
      .attr("transform", `translate(${dims.w - 230},${dims.m.t - 10})`);
    legend
      .append("line")
      .attr("x1", 0)
      .attr("x2", 18)
      .attr("y1", 6)
      .attr("y2", 6)
      .attr("stroke", "#888")
      .attr("stroke-dasharray", "3,3");
    legend
      .append("text")
      .attr("x", 24)
      .attr("y", 9)
      .attr("font-size", 11)
      .attr("fill", "#666")
      .text("dashed line = true utility");
  }, [snapshots, idx, xScale, ridgeY]);

  return (
    <div>
      <div className={styles.twinHeader}>
        <h2>Hidden Twin Test</h2>
        <div className={styles.twinControls}>
          <button
            type="button"
            className={`${styles.toggleBtn} ${styles.toggleBtnActive}`}
            onClick={() => setPlaying((p) => !p)}
            style={{ minWidth: 60 }}
          >
            {playing ? "Pause" : "Play"}
          </button>
          <input
            type="range"
            min={0}
            max={(snapshots?.length ?? 1) - 1}
            value={idx}
            onChange={(e) => {
              setPlaying(false);
              setIdx(Number(e.target.value));
            }}
          />
          <span className={styles.twinRound}>t = {round}</span>
        </div>
      </div>

      <svg ref={svgRef} viewBox={`0 0 ${dims.w} ${dims.h}`} className={styles.twinSvg} />

      <Caption label="What you're seeing">
        Sample-based estimate of <code>utility = q − ν·f</code> per arm
        per round, reconstructed from{" "}
        <code>results/scenario_sweep/S1/padct/seed_00.jsonl</code>. Three
        same-tier providers share cost and base model. PA-DCT must learn
        the gap from reward feedback alone:{" "}
        <span style={{ color: COLOR_HEX["P-mid"], fontWeight: 600 }}>P-mid</span>{" "}
        converges to ~0.82,{" "}
        <span style={{ color: COLOR_HEX["P-adv"], fontWeight: 600 }}>P-adv</span>{" "}
        to ~0.67 (its fluent-but-wrong answers still earn partial credit
        on objective evaluators), and{" "}
        <span style={{ color: COLOR_HEX["P-flaky"], fontWeight: 600 }}>P-flaky</span>{" "}
        to ~0.34 (38.5% failures × ν = 0.5 penalty). The gap to P-mid is
        small for P-adv (~0.15) but consistent — and that consistency is
        all PA-DCT needs.
      </Caption>
    </div>
  );
}
