const DATA = window.PILOT402_EXPLAINER_DATA;

const providers = ["P-cheap", "P-mid", "P-premium", "P-adv", "P-flaky"];
const providerColors = {
  "P-cheap": "#15905f",
  "P-mid": "#2563eb",
  "P-premium": "#d88912",
  "P-adv": "#d14b4b",
  "P-flaky": "#7c5bd6",
};

const policyColors = {
  "PA-DCT": "#2563eb",
  AlwaysMid: "#178b94",
  AlwaysCheap: "#15905f",
  AlwaysPremium: "#17202a",
  BudgetRule: "#d88912",
  Oracle: "#7c5bd6",
};

const state = {
  adaptationScenario: "S1",
  resultScenario: "S3",
  metric: "cumPA",
  roundIndex: 0,
  activeAblations: new Set(["noCostPosterior"]),
};

const metricConfig = {
  cumPA: { label: "cum_PA", suffix: "", decimals: 0 },
  roi: { label: "ROI", suffix: "", decimals: 0 },
  meanQ: { label: "mean q", suffix: "", decimals: 3 },
  failPct: { label: "fail %", suffix: "%", decimals: 1 },
};

const $ = (selector) => document.querySelector(selector);

function format(value, decimals = 0, suffix = "") {
  return `${Number(value).toLocaleString("en-US", {
    minimumFractionDigits: decimals,
    maximumFractionDigits: decimals,
  })}${suffix}`;
}

function svgEl(name, attrs = {}) {
  const node = document.createElementNS("http://www.w3.org/2000/svg", name);
  Object.entries(attrs).forEach(([key, value]) => node.setAttribute(key, value));
  return node;
}

function clear(node) {
  node.replaceChildren();
}

function buttonGroup(container, items, active, onClick) {
  clear(container);
  items.forEach((item) => {
    const button = document.createElement("button");
    button.type = "button";
    button.textContent = item.label;
    button.className = item.id === active ? "active" : "";
    button.addEventListener("click", () => onClick(item.id));
    container.appendChild(button);
  });
}

function renderProviderCards() {
  const container = $("#providerCards");
  clear(container);

  providers.forEach((provider) => {
    const spec = DATA.providers[provider];
    const card = document.createElement("article");
    card.className = "provider-card";
    card.style.setProperty("--accent", providerColors[provider]);
    card.innerHTML = `
      <h3>${provider}</h3>
      <p class="model">${spec.model}</p>
      <p class="signal">${spec.signal}</p>
      <div class="mini-metrics">
        <div class="mini-row">
          <span>cost</span>
          <div class="track"><span style="width:${Math.min(100, (spec.cost / 0.01) * 100)}%"></span></div>
          <b>$${spec.cost}</b>
        </div>
        <div class="mini-row">
          <span>quality</span>
          <div class="track"><span style="width:${spec.quality * 100}%"></span></div>
          <b>${Math.round(spec.quality * 100)}%</b>
        </div>
        <div class="mini-row">
          <span>reliable</span>
          <div class="track"><span style="width:${spec.reliability * 100}%"></span></div>
          <b>${Math.round(spec.reliability * 100)}%</b>
        </div>
      </div>
      <p class="note">${spec.note}</p>
    `;
    container.appendChild(card);
  });
}

function renderControls() {
  buttonGroup(
    $("#adaptationTabs"),
    [
      { id: "S1", label: "S1 baseline" },
      { id: "S2", label: "S2 outage" },
      { id: "S3", label: "S3 promo" },
    ],
    state.adaptationScenario,
    (id) => {
      state.adaptationScenario = id;
      state.roundIndex = 0;
      renderAdaptation();
      renderRoundTabs();
      renderRoundMicroscope();
    },
  );

  buttonGroup(
    $("#resultScenarioTabs"),
    [
      { id: "S1", label: "S1" },
      { id: "S2", label: "S2" },
      { id: "S3", label: "S3" },
    ],
    state.resultScenario,
    (id) => {
      state.resultScenario = id;
      renderResults();
    },
  );

  buttonGroup(
    $("#metricTabs"),
    Object.entries(metricConfig).map(([id, config]) => ({ id, label: config.label })),
    state.metric,
    (id) => {
      state.metric = id;
      renderResults();
    },
  );
}

function renderAdaptation() {
  const scenario = state.adaptationScenario;
  const scenarioMeta = DATA.scenarios[scenario];
  $("#scenarioNote").textContent = scenarioMeta.summary;
  drawArmShareChart(scenario);
  renderLegend($("#chartLegend"), providers, providerColors);
}

function renderLegend(container, keys, colorMap) {
  clear(container);
  keys.forEach((key) => {
    const item = document.createElement("span");
    item.innerHTML = `<i style="--accent:${colorMap[key]}"></i>${key}`;
    container.appendChild(item);
  });
}

function drawGrid(svg, plot, yTicks = [0, 0.25, 0.5, 0.75, 1]) {
  yTicks.forEach((tick) => {
    const y = plot.y + plot.h - tick * plot.h;
    svg.appendChild(svgEl("line", {
      x1: plot.x,
      x2: plot.x + plot.w,
      y1: y,
      y2: y,
      stroke: "#dde3ea",
      "stroke-width": "1",
    }));
    const label = svgEl("text", {
      x: plot.x - 10,
      y: y + 4,
      "text-anchor": "end",
      fill: "#657180",
      "font-size": "14",
    });
    label.textContent = `${Math.round(tick * 100)}%`;
    svg.appendChild(label);
  });
}

function drawValueGrid(svg, plot, minValue, maxValue, formatter) {
  const ticks = 4;
  for (let index = 0; index <= ticks; index += 1) {
    const ratio = index / ticks;
    const value = minValue + (maxValue - minValue) * ratio;
    const y = plot.y + plot.h - ratio * plot.h;
    svg.appendChild(svgEl("line", {
      x1: plot.x,
      x2: plot.x + plot.w,
      y1: y,
      y2: y,
      stroke: "#dde3ea",
      "stroke-width": "1",
    }));
    const label = svgEl("text", {
      x: plot.x - 10,
      y: y + 4,
      "text-anchor": "end",
      fill: "#657180",
      "font-size": "11",
    });
    label.textContent = formatter(value);
    svg.appendChild(label);
  }
}

function drawVerticalValueGrid(svg, plot, minValue, maxValue, formatter) {
  const ticks = 4;
  for (let index = 0; index <= ticks; index += 1) {
    const ratio = index / ticks;
    const value = minValue + (maxValue - minValue) * ratio;
    const x = plot.x + ratio * plot.w;
    svg.appendChild(svgEl("line", {
      x1: x,
      x2: x,
      y1: plot.y,
      y2: plot.y + plot.h,
      stroke: "#dde3ea",
      "stroke-width": "1",
    }));
    const label = svgEl("text", {
      x,
      y: plot.y + plot.h + 28,
      "text-anchor": "middle",
      fill: "#657180",
      "font-size": "14",
    });
    label.textContent = formatter(value);
    svg.appendChild(label);
  }
}

function drawArmShareChart(scenario) {
  const container = $("#armShareChart");
  clear(container);

  const data = DATA.armShares[scenario];
  const width = 920;
  const height = 390;
  const plot = { x: 70, y: 30, w: 802, h: 286 };
  const xMax = 10000;
  const scenarioMeta = DATA.scenarios[scenario];
  const x = (round) => plot.x + (round / xMax) * plot.w;
  const y = (share) => plot.y + plot.h - share * plot.h;
  const svg = svgEl("svg", { viewBox: `0 0 ${width} ${height}`, role: "img" });

  drawGrid(svg, plot);

  if (scenarioMeta.eventWindow) {
    const [start, end] = scenarioMeta.eventWindow;
    svg.appendChild(svgEl("rect", {
      x: x(start),
      y: plot.y,
      width: x(end) - x(start),
      height: plot.h,
      fill: scenario === "S2" ? "rgba(209,75,75,0.08)" : "rgba(216,137,18,0.1)",
    }));
    const eventLine = svgEl("line", {
      x1: x(start),
      x2: x(start),
      y1: plot.y,
      y2: plot.y + plot.h,
      stroke: scenario === "S2" ? "#d14b4b" : "#d88912",
      "stroke-width": "2",
      "stroke-dasharray": "5 5",
    });
    svg.appendChild(eventLine);
  }

  providers.forEach((provider) => {
    const points = data
      .map((row) => `${x(row.round).toFixed(1)},${y(row.shares[provider]).toFixed(1)}`)
      .join(" ");
    svg.appendChild(svgEl("polyline", {
      points,
      fill: "none",
      stroke: providerColors[provider],
      "stroke-width": provider === "P-mid" || provider === "P-premium" ? "3" : "2",
      "stroke-linecap": "round",
      "stroke-linejoin": "round",
      opacity: provider === "P-adv" || provider === "P-flaky" ? "0.7" : "0.95",
    }));
  });

  [0, 2500, 5000, 7500, 10000].forEach((round) => {
    const label = svgEl("text", {
      x: x(round),
      y: 358,
      "text-anchor": "middle",
      fill: "#657180",
      "font-size": "14",
    });
    label.textContent = String(round);
    svg.appendChild(label);
  });

  const examples = DATA.roundExamples.filter((item) => item.scenario === state.adaptationScenario);
  const example = examples[Math.min(state.roundIndex, examples.length - 1)];
  let cursor = data[0];
  data.forEach((row) => {
    if (Math.abs(row.round - example.round) < Math.abs(cursor.round - example.round)) cursor = row;
  });
  svg.appendChild(svgEl("line", {
    x1: x(example.round),
    x2: x(example.round),
    y1: plot.y,
    y2: plot.y + plot.h,
    stroke: "#17202a",
    "stroke-width": "2",
    opacity: "0.62",
  }));

  const cursorLabel = svgEl("text", {
    x: x(example.round),
    y: plot.y - 10,
    "text-anchor": "middle",
    fill: "#17202a",
    "font-size": "14",
    "font-weight": "800",
  });
  cursorLabel.textContent = `${example.label} · R${example.round}`;
  svg.appendChild(cursorLabel);

  providers.forEach((provider) => {
    svg.appendChild(svgEl("circle", {
      cx: x(example.round),
      cy: y(cursor.shares[provider]),
      r: provider === "P-mid" || provider === "P-premium" ? "5" : "4",
      fill: providerColors[provider],
      stroke: "#fff",
      "stroke-width": "1.5",
    }));
  });

  const tooltip = document.createElement("div");
  tooltip.className = "chart-tooltip";
  container.append(svg, tooltip);

  svg.addEventListener("mousemove", (event) => {
    const rect = svg.getBoundingClientRect();
    const localX = ((event.clientX - rect.left) / rect.width) * width;
    const round = Math.max(0, Math.min(xMax, ((localX - plot.x) / plot.w) * xMax));
    let nearest = data[0];
    data.forEach((row) => {
      if (Math.abs(row.round - round) < Math.abs(nearest.round - round)) nearest = row;
    });
    tooltip.classList.add("visible");
    tooltip.style.left = `${event.clientX - rect.left}px`;
    tooltip.style.top = `${event.clientY - rect.top}px`;
    tooltip.innerHTML = `
      <strong>round ${Math.round(nearest.round)}</strong>
      ${providers.map((provider) => `${provider}: ${Math.round(nearest.shares[provider] * 100)}%`).join("<br>")}
    `;
  });

  svg.addEventListener("mouseleave", () => tooltip.classList.remove("visible"));
}

function renderRoundTabs() {
  const examples = DATA.roundExamples.filter((item) => item.scenario === state.adaptationScenario);
  buttonGroup(
    $("#roundTabs"),
    examples.map((example, index) => ({ id: String(index), label: `${example.label} · R${example.round}` })),
    String(state.roundIndex),
    (id) => {
      state.roundIndex = Number(id);
      renderAdaptation();
      renderRoundMicroscope();
    },
  );
}

function renderRoundMicroscope() {
  const examples = DATA.roundExamples.filter((item) => item.scenario === state.adaptationScenario);
  const example = examples[Math.min(state.roundIndex, examples.length - 1)];
  const container = $("#roundMicroscope");
  clear(container);

  const minScore = Math.min(...example.candidates.map((item) => item.score));
  const maxScore = Math.max(...example.candidates.map((item) => item.score));
  const spread = Math.max(0.01, maxScore - minScore);
  const utilityWidth = Math.max(0, Math.min(100, ((example.utility + 0.5) / 1.5) * 100));
  const costPenalty = Math.min(100, (example.cost / 0.01) * 100 * example.lambdaNorm);
  const rewardWidth = Math.max(0, Math.min(100, ((example.reward + 1) / 2) * 100));

  const card = document.createElement("div");
  card.className = "microscope-card";
  card.innerHTML = `
    <div class="round-context">
      <strong>${example.label} · round ${example.round}</strong>
      <span>${example.reason} 左侧曲线的竖线标的就是这一轮。</span>
    </div>
    <div class="round-meta">
      <div class="meta-item"><span>scenario</span><strong>${example.scenario}</strong></div>
      <div class="meta-item"><span>task</span><strong>${example.taskType}</strong></div>
      <div class="meta-item"><span>chosen</span><strong>${example.chosen}</strong></div>
      <div class="meta-item"><span>budget</span><strong>$${example.budget}</strong></div>
    </div>
    <div class="lambda-block">
      <div class="lambda-head"><span>λ_norm budget pressure</span><strong>${example.lambdaNorm}</strong></div>
      <div class="lambda-track"><span style="width:${example.lambdaNorm * 100}%"></span></div>
    </div>
    <div class="candidate-list">
      ${example.candidates
        .map((candidate) => {
          const width = 20 + ((candidate.score - minScore) / spread) * 80;
          return `
            <div class="candidate-row ${candidate.provider === example.chosen ? "chosen" : ""}">
              <strong>${candidate.provider}</strong>
              <div class="score-bar" style="--accent:${providerColors[candidate.provider]};--w:${width}%"><span></span></div>
              <span>u ${candidate.utility}</span>
              <span>$${candidate.cost}</span>
              <span>${candidate.score}</span>
            </div>
          `;
        })
        .join("")}
    </div>
    <div class="reward-grid">
      <div class="reward-card">
        <div class="reward-head"><span>utility</span><strong>${example.utility}</strong></div>
        <div class="reward-track" style="--accent:#15905f"><span style="width:${utilityWidth}%"></span></div>
      </div>
      <div class="reward-card">
        <div class="reward-head"><span>cost penalty</span><strong>$${example.cost}</strong></div>
        <div class="reward-track" style="--accent:#d88912"><span style="width:${costPenalty}%"></span></div>
      </div>
      <div class="reward-card">
        <div class="reward-head"><span>quality</span><strong>${example.quality}</strong></div>
        <div class="reward-track" style="--accent:#2563eb"><span style="width:${example.quality * 100}%"></span></div>
      </div>
      <div class="reward-card">
        <div class="reward-head"><span>PA reward</span><strong>${example.reward}</strong></div>
        <div class="reward-track" style="--accent:${example.reward >= 0 ? "#15905f" : "#d14b4b"}"><span style="width:${rewardWidth}%"></span></div>
      </div>
    </div>
  `;
  container.appendChild(card);
}

function renderResults() {
  renderControls();
  renderMetricCards();
  drawResultChart();
}

function getRow(policy, scenario = state.resultScenario) {
  return DATA.headline[scenario].find((row) => row.policy === policy);
}

function renderMetricCards() {
  const container = $("#metricCards");
  clear(container);

  const padct = getRow("PA-DCT");
  const mid = getRow("AlwaysMid");
  const oracle = getRow("Oracle");
  const deltaMid = padct.cumPA - mid.cumPA;
  const gap = oracle.cumPA - padct.cumPA;

  const cards = [
    ["PA-DCT cum_PA", format(padct.cumPA), `± ${padct.cumStd}`],
    ["vs AlwaysMid", `${deltaMid >= 0 ? "+" : ""}${format(deltaMid)}`, state.resultScenario === "S1" ? "静态市场探索成本" : "冲击场景反超"],
    ["Oracle gap", format(gap), "在线策略仍有学习损耗"],
    ["fail rate", format(padct.failPct, 1, "%"), state.resultScenario === "S2" ? "AlwaysMid 为 7.5%" : "低失败选择"],
  ];

  cards.forEach(([label, value, note]) => {
    const card = document.createElement("div");
    card.className = "metric-card";
    card.innerHTML = `<span>${label}</span><strong>${value}</strong><p>${note}</p>`;
    container.appendChild(card);
  });
}

function drawResultChart() {
  const container = $("#resultChart");
  clear(container);
  const rows = [...DATA.headline[state.resultScenario]].sort((a, b) => b[state.metric] - a[state.metric]);
  const config = metricConfig[state.metric];
  const values = rows.map((row) => row[state.metric]);
  const minValue = Math.min(0, ...values);
  const maxValue = Math.max(...values);
  const width = 920;
  const height = 430;
  const plot = { x: 172, y: 28, w: 690, h: 342 };
  const svg = svgEl("svg", { viewBox: `0 0 ${width} ${height}`, role: "img" });
  const x = (value) => plot.x + ((value - minValue) / (maxValue - minValue || 1)) * plot.w;
  const zeroX = x(0);
  const rowGap = 10;
  const rowHeight = (plot.h - rowGap * (rows.length - 1)) / rows.length;

  drawVerticalValueGrid(svg, plot, minValue, maxValue, (value) => format(value, config.decimals, config.suffix));

  svg.appendChild(svgEl("line", {
    x1: zeroX,
    x2: zeroX,
    y1: plot.y,
    y2: plot.y + plot.h,
    stroke: "#17202a",
    "stroke-width": "1.2",
    opacity: "0.32",
  }));

  rows.forEach((row, index) => {
    const value = row[state.metric];
    const y = plot.y + index * (rowHeight + rowGap);
    const start = Math.min(x(value), zeroX);
    const width = Math.max(2, Math.abs(x(value) - zeroX));
    const color = policyColors[row.policy] || "#657180";
    svg.appendChild(svgEl("rect", {
      x: start,
      y,
      width,
      height: rowHeight,
      rx: "5",
      fill: color,
      opacity: row.policy === "PA-DCT" ? "1" : "0.78",
    }));

    const policyLabel = svgEl("text", {
      x: plot.x - 14,
      y: y + rowHeight * 0.65,
      "text-anchor": "end",
      fill: row.policy === "PA-DCT" ? "#17202a" : "#657180",
      "font-size": "15",
      "font-weight": row.policy === "PA-DCT" ? "800" : "650",
    });
    policyLabel.textContent = row.policy;
    svg.appendChild(policyLabel);

    const valueLabel = svgEl("text", {
      x: value >= 0 ? start + width + 8 : start - 8,
      y: y + rowHeight * 0.65,
      "text-anchor": value >= 0 ? "start" : "end",
      fill: "#17202a",
      "font-size": "15",
      "font-weight": "700",
    });
    valueLabel.textContent = format(value, config.decimals, config.suffix);
    svg.appendChild(valueLabel);
  });

  container.appendChild(svg);
}

function renderAblations() {
  const map = $("#ablationMap");
  clear(map);
  DATA.ablations.forEach((item) => {
    const chip = document.createElement("div");
    chip.className = `component-chip ${state.activeAblations.has(item.id) ? "broken" : ""}`;
    chip.innerHTML = `<span>${state.activeAblations.has(item.id) ? "removed" : "active"}</span><strong>${item.component}</strong>`;
    map.appendChild(chip);
  });

  const toggles = $("#ablationToggles");
  clear(toggles);

  DATA.ablations.forEach((item) => {
    const button = document.createElement("button");
    button.type = "button";
    button.className = `ablation-toggle ${state.activeAblations.has(item.id) ? "active" : ""}`;
    button.innerHTML = `
      <h3>${item.label}</h3>
      <p>${item.breaks}</p>
      <strong>${item.metric}</strong>
    `;
    button.addEventListener("click", () => {
      if (state.activeAblations.has(item.id)) state.activeAblations.delete(item.id);
      else state.activeAblations.add(item.id);
      renderAblations();
    });
    toggles.appendChild(button);
  });

  const active = DATA.ablations.filter((item) => state.activeAblations.has(item.id));
  const combined = active.reduce((score, item) => 1 - (1 - score) * (1 - item.severity), 0);
  $("#riskFill").style.width = `${Math.min(100, combined * 100)}%`;

  const summary = $("#ablationSummary");
  if (!active.length) {
    summary.innerHTML = "<h3>Full PA-DCT</h3><p>五个组件都在：先按上下文建 posterior，再用 λ 把预算压力带入选择，用 discount 适应市场变化。</p>";
    return;
  }

  summary.innerHTML = `
    <h3>${active.length} 个组件被移除</h3>
    <p>${active.map((item) => `${item.component}: ${item.impact}`).join(" ")}</p>
  `;
}

function init() {
  renderProviderCards();
  renderControls();
  renderAdaptation();
  renderRoundTabs();
  renderRoundMicroscope();
  renderResults();
  renderAblations();

  window.addEventListener("resize", () => {
    drawArmShareChart(state.adaptationScenario);
    drawResultChart();
  });
}

init();
