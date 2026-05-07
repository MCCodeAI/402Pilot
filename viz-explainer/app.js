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
  lang: "en",
  pathMode: "both",
  adaptationScenario: "S1",
  resultScenario: "S3",
  metric: "cumPA",
  roundIndex: 0,
  activeAblations: new Set(["noCostPosterior"]),
};

const metricConfig = {
  cumPA: { label: "cum_PA", zhLabel: "cum_PA", suffix: "", decimals: 0, higherBetter: true },
  roi: { label: "ROI", zhLabel: "ROI", suffix: "", decimals: 0, higherBetter: true },
  meanQ: { label: "mean q", zhLabel: "mean q", suffix: "", decimals: 3, higherBetter: true },
  failPct: { label: "fail %", zhLabel: "fail %", suffix: "%", decimals: 1, higherBetter: false },
};

const i18n = {
  en: {
    "hero.eyebrow": "402Pilot Interactive Explainer",
    "hero.title": "402Pilot: An x402 Decision Layer for Autonomous Agent Micropayments",
    "hero.subtitle": "A decision layer for agent micropayment markets: learn which provider is worth paying before x402 executes the call.",
    "architecture.title": "Select before x402, learn after feedback",
    "architecture.eyebrow": "System Architecture",
    "architecture.note": "The diagram is the paper figure. Use the path controls to highlight decision flow or learning flow.",
    "architecture.decisionPath": "Decision path",
    "architecture.learningPath": "Learning path",
    "formula.select": "select",
    "formula.learn": "learn",
    "formula.account": "account",
    "providers.title": "Price, quality, and reliability diverge",
    "providers.eyebrow": "Provider Market",
    "scenario.title": "Provider share plus adaptation summary",
    "scenario.eyebrow": "Scenario Replay",
    "microscope.title": "The selected round behind the chart cursor",
    "microscope.eyebrow": "Round Microscope",
    "results.title": "Metric matrix first, detailed bars second",
    "results.eyebrow": "Experiment Results",
    "ablation.title": "Remove one component, see the failure mode",
    "ablation.eyebrow": "Ablation",
    "footer.scope": "Independent implementation: viz-explainer/",
    "footer.data": "Data: S1/S2 scenario_sweep, S3 scenario_sweep_s3promo_v2",
    decision: "Decision",
    learning: "Learning",
    both: "Both",
    none: "None",
    cost: "cost",
    quality: "quality",
    reliable: "reliable",
    scenario: "scenario",
    task: "task",
    chosen: "chosen",
    budget: "budget",
    budgetPressure: "λ_norm budget pressure",
    linkedRound: "The vertical cursor in the chart marks this exact round.",
    before: "Before",
    event: "Event",
    after: "After",
    stable: "Stable",
    focusArm: "Focus arm",
    share: "share",
    delta: "delta",
    noShock: "No shock",
    metricMatrix: "Scenario × policy matrix",
    detailBars: "Detailed bars",
    paDctCum: "PA-DCT cum_PA",
    vsMid: "vs AlwaysMid",
    oracleGap: "Oracle gap",
    failRate: "fail rate",
    explorationCost: "stationary exploration cost",
    shockWin: "beats the fixed baseline",
    onlineGap: "remaining online learning gap",
    lowFailure: "low failure selection",
    utility: "utility",
    costPenalty: "cost penalty",
    paReward: "PA reward",
    removed: "removed",
    active: "active",
    fullPadct: "Full PA-DCT",
    fullPadctText: "All five components are active: contextual posteriors, λ-aware selection, discounting, Thompson sampling, and cost learning.",
    componentsRemoved: "components removed",
  },
  zh: {
    "hero.eyebrow": "402Pilot 交互式可视化",
    "hero.title": "402Pilot：面向自主 Agent 微支付的 x402 决策层",
    "hero.subtitle": "Agent 微支付市场中的支付决策层：在 x402 执行付款前，学习哪个 provider 值得调用。",
    "architecture.title": "在 x402 之前做选择，在反馈之后学习",
    "architecture.eyebrow": "系统架构",
    "architecture.note": "底图来自论文架构图。可以高亮选择路径或学习路径。",
    "architecture.decisionPath": "选择路径",
    "architecture.learningPath": "学习路径",
    "formula.select": "选择",
    "formula.learn": "学习",
    "formula.account": "计分",
    "providers.title": "价格、质量、可靠性不总是同向",
    "providers.eyebrow": "Provider 市场",
    "scenario.title": "Provider 选择比例与 adaptation 摘要",
    "scenario.eyebrow": "场景回放",
    "microscope.title": "曲线竖线对应的单轮决策",
    "microscope.eyebrow": "单轮显微镜",
    "results.title": "先看矩阵，再看细节条形图",
    "results.eyebrow": "实验结果",
    "ablation.title": "拿掉一个组件，看对应失败模式",
    "ablation.eyebrow": "消融实验",
    "footer.scope": "独立实现：viz-explainer/",
    "footer.data": "数据口径：S1/S2 scenario_sweep，S3 scenario_sweep_s3promo_v2",
    decision: "选择",
    learning: "学习",
    both: "全部",
    none: "关闭",
    cost: "成本",
    quality: "质量",
    reliable: "可靠性",
    scenario: "场景",
    task: "任务",
    chosen: "选择",
    budget: "预算",
    budgetPressure: "λ_norm 预算压力",
    linkedRound: "左侧曲线的竖线标的就是这一轮。",
    before: "之前",
    event: "事件期",
    after: "之后",
    stable: "稳定",
    focusArm: "关注臂",
    share: "占比",
    delta: "变化",
    noShock: "无冲击",
    metricMatrix: "场景 × 策略矩阵",
    detailBars: "细节条形图",
    paDctCum: "PA-DCT cum_PA",
    vsMid: "vs AlwaysMid",
    oracleGap: "Oracle gap",
    failRate: "失败率",
    explorationCost: "静态市场探索成本",
    shockWin: "冲击场景反超固定基线",
    onlineGap: "在线学习仍有差距",
    lowFailure: "低失败选择",
    utility: "效用",
    costPenalty: "成本惩罚",
    paReward: "PA reward",
    removed: "已移除",
    active: "启用",
    fullPadct: "完整 PA-DCT",
    fullPadctText: "五个组件都在：上下文后验、λ 感知选择、discount、Thompson sampling 和成本学习。",
    componentsRemoved: "个组件被移除",
  },
};

const $ = (selector) => document.querySelector(selector);

function tr(key) {
  return i18n[state.lang][key] ?? i18n.en[key] ?? key;
}

function localized(item, field) {
  if (state.lang === "zh") {
    const zhField = `zh${field.charAt(0).toUpperCase()}${field.slice(1)}`;
    return item[zhField] ?? item[field];
  }
  return item[field];
}

function applyStaticText() {
  document.documentElement.lang = state.lang === "zh" ? "zh-CN" : "en";
  document.querySelectorAll("[data-i18n]").forEach((node) => {
    node.textContent = tr(node.dataset.i18n);
  });
}

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
      <p class="signal">${localized(spec, "signal")}</p>
      <div class="mini-metrics">
        <div class="mini-row">
          <span>${tr("cost")}</span>
          <div class="track"><span style="width:${Math.min(100, (spec.cost / 0.01) * 100)}%"></span></div>
          <b>$${spec.cost}</b>
        </div>
        <div class="mini-row">
          <span>${tr("quality")}</span>
          <div class="track"><span style="width:${spec.quality * 100}%"></span></div>
          <b>${Math.round(spec.quality * 100)}%</b>
        </div>
        <div class="mini-row">
          <span>${tr("reliable")}</span>
          <div class="track"><span style="width:${spec.reliability * 100}%"></span></div>
          <b>${Math.round(spec.reliability * 100)}%</b>
        </div>
      </div>
      <p class="note">${localized(spec, "note")}</p>
    `;
    container.appendChild(card);
  });
}

function renderControls() {
  buttonGroup(
    $("#languageToggle"),
    [
      { id: "en", label: "EN" },
      { id: "zh", label: "中文" },
    ],
    state.lang,
    (id) => {
      state.lang = id;
      renderAll();
    },
  );

  buttonGroup(
    $("#pathModeTabs"),
    [
      { id: "decision", label: tr("decision") },
      { id: "learning", label: tr("learning") },
      { id: "both", label: tr("both") },
      { id: "none", label: tr("none") },
    ],
    state.pathMode,
    (id) => {
      state.pathMode = id;
      updatePathMode();
      renderControls();
    },
  );

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
    Object.entries(metricConfig).map(([id, config]) => ({
      id,
      label: state.lang === "zh" ? config.zhLabel : config.label,
    })),
    state.metric,
    (id) => {
      state.metric = id;
      renderResults();
    },
  );
}

function updatePathMode() {
  $(".layer-diagram").dataset.pathMode = state.pathMode;
}

function renderAdaptation() {
  const scenario = state.adaptationScenario;
  const scenarioMeta = DATA.scenarios[scenario];
  $("#scenarioNote").textContent = localized(scenarioMeta, "summary");
  renderAdaptationInsights(scenario);
  drawArmShareChart(scenario);
  renderLegend($("#chartLegend"), providers, providerColors);
}

function averageShare(scenario, provider, start, end) {
  const rows = DATA.armShares[scenario].filter((row) => row.round >= start && row.round < end);
  if (!rows.length) return 0;
  return rows.reduce((sum, row) => sum + row.shares[provider], 0) / rows.length;
}

function renderAdaptationInsights(scenario) {
  const container = $("#adaptationInsights");
  clear(container);
  const focus = scenario === "S3" ? "P-premium" : "P-mid";
  const windows = scenario === "S1"
    ? [
        [tr("stable"), 0, 3000],
        [tr("stable"), 3000, 6500],
        [tr("stable"), 6500, 10000],
      ]
    : scenario === "S2"
      ? [
          [tr("before"), 0, 3000],
          [tr("event"), 3000, 5500],
          [tr("after"), 5500, 10000],
        ]
      : [
          [tr("before"), 0, 1000],
          [tr("event"), 1000, 3000],
          [tr("after"), 3000, 10000],
        ];
  const baseline = averageShare(scenario, focus, windows[0][1], windows[0][2]);

  windows.forEach(([label, start, end]) => {
    const share = averageShare(scenario, focus, start, end);
    const delta = share - baseline;
    const card = document.createElement("div");
    card.className = "insight-card";
    card.innerHTML = `
      <span>${label} · ${focus}</span>
      <strong>${Math.round(share * 100)}%</strong>
      <p>${tr("share")} ${start}-${end}${delta ? ` · ${tr("delta")} ${delta > 0 ? "+" : ""}${Math.round(delta * 100)}pp` : ""}</p>
    `;
    container.appendChild(card);
  });
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
  cursorLabel.textContent = `${localized(example, "label")} · R${example.round}`;
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
    examples.map((example, index) => ({ id: String(index), label: `${localized(example, "label")} · R${example.round}` })),
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
      <strong>${localized(example, "label")} · round ${example.round}</strong>
      <span>${localized(example, "reason")} ${tr("linkedRound")}</span>
    </div>
    <div class="round-meta">
      <div class="meta-item"><span>${tr("scenario")}</span><strong>${example.scenario}</strong></div>
      <div class="meta-item"><span>${tr("task")}</span><strong>${example.taskType}</strong></div>
      <div class="meta-item"><span>${tr("chosen")}</span><strong>${example.chosen}</strong></div>
      <div class="meta-item"><span>${tr("budget")}</span><strong>$${example.budget}</strong></div>
    </div>
    <div class="lambda-block">
      <div class="lambda-head"><span>${tr("budgetPressure")}</span><strong>${example.lambdaNorm}</strong></div>
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
        <div class="reward-head"><span>${tr("utility")}</span><strong>${example.utility}</strong></div>
        <div class="reward-track" style="--accent:#15905f"><span style="width:${utilityWidth}%"></span></div>
      </div>
      <div class="reward-card">
        <div class="reward-head"><span>${tr("costPenalty")}</span><strong>$${example.cost}</strong></div>
        <div class="reward-track" style="--accent:#d88912"><span style="width:${costPenalty}%"></span></div>
      </div>
      <div class="reward-card">
        <div class="reward-head"><span>${tr("quality")}</span><strong>${example.quality}</strong></div>
        <div class="reward-track" style="--accent:#2563eb"><span style="width:${example.quality * 100}%"></span></div>
      </div>
      <div class="reward-card">
        <div class="reward-head"><span>${tr("paReward")}</span><strong>${example.reward}</strong></div>
        <div class="reward-track" style="--accent:${example.reward >= 0 ? "#15905f" : "#d14b4b"}"><span style="width:${rewardWidth}%"></span></div>
      </div>
    </div>
  `;
  container.appendChild(card);
}

function renderResults() {
  renderControls();
  renderResultMatrix();
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
    [tr("paDctCum"), format(padct.cumPA), `± ${padct.cumStd}`],
    [tr("vsMid"), `${deltaMid >= 0 ? "+" : ""}${format(deltaMid)}`, state.resultScenario === "S1" ? tr("explorationCost") : tr("shockWin")],
    [tr("oracleGap"), format(gap), tr("onlineGap")],
    [tr("failRate"), format(padct.failPct, 1, "%"), state.resultScenario === "S2" ? "AlwaysMid 7.5%" : tr("lowFailure")],
  ];

  cards.forEach(([label, value, note]) => {
    const card = document.createElement("div");
    card.className = "metric-card";
    card.innerHTML = `<span>${label}</span><strong>${value}</strong><p>${note}</p>`;
    container.appendChild(card);
  });
}

function renderResultMatrix() {
  const container = $("#resultMatrix");
  clear(container);
  const scenarios = ["S1", "S2", "S3"];
  const metrics = ["cumPA", "roi", "meanQ", "failPct"];
  const header = document.createElement("div");
  header.className = "matrix-row";
  header.innerHTML = `
    <div class="matrix-cell header">${tr("metricMatrix")}</div>
    ${scenarios.map((scenario) => `<div class="matrix-cell header">${scenario}</div>`).join("")}
  `;
  container.appendChild(header);

  metrics.forEach((metric) => {
    const config = metricConfig[metric];
    const values = scenarios.map((scenario) => getRow("PA-DCT", scenario)[metric]);
    const min = Math.min(...values);
    const max = Math.max(...values);
    const row = document.createElement("div");
    row.className = "matrix-row";
    row.innerHTML = `
      <div class="matrix-cell metric-label">${state.lang === "zh" ? config.zhLabel : config.label}</div>
      ${scenarios
        .map((scenario) => {
          const padct = getRow("PA-DCT", scenario);
          const mid = getRow("AlwaysMid", scenario);
          const value = padct[metric];
          const delta = value - mid[metric];
          const normalized = max === min ? 0.5 : (value - min) / (max - min);
          const good = config.higherBetter ? normalized > 0.66 : normalized < 0.34;
          const bad = config.higherBetter ? normalized < 0.34 : normalized > 0.66;
          const tone = good ? "good" : bad ? "bad" : "warn";
          return `
            <div class="matrix-cell ${tone}">
              <strong>${format(value, config.decimals, config.suffix)}</strong>
              <span>vs Mid ${delta >= 0 ? "+" : ""}${format(delta, config.decimals, config.suffix)}</span>
            </div>
          `;
        })
        .join("")}
    `;
    container.appendChild(row);
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
    chip.innerHTML = `<span>${state.activeAblations.has(item.id) ? tr("removed") : tr("active")}</span><strong>${item.component}</strong>`;
    map.appendChild(chip);
  });

  const toggles = $("#ablationToggles");
  clear(toggles);

  DATA.ablations.forEach((item) => {
    const button = document.createElement("button");
    button.type = "button";
    button.className = `ablation-toggle ${state.activeAblations.has(item.id) ? "active" : ""}`;
    button.innerHTML = `
      <h3>${localized(item, "label")}</h3>
      <p>${localized(item, "breaks")}</p>
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
    summary.innerHTML = `<h3>${tr("fullPadct")}</h3><p>${tr("fullPadctText")}</p>`;
    return;
  }

  summary.innerHTML = `
    <h3>${active.length} ${tr("componentsRemoved")}</h3>
    <div class="ablation-list">
      ${active
        .map((item) => `<div><strong>${item.component}</strong><p>${localized(item, "impact")}</p><span>${item.metric}</span></div>`)
        .join("")}
    </div>
  `;
}

function renderAll() {
  applyStaticText();
  renderProviderCards();
  renderControls();
  updatePathMode();
  renderAdaptation();
  renderRoundTabs();
  renderRoundMicroscope();
  renderResults();
  renderAblations();
}

function init() {
  renderAll();

  window.addEventListener("resize", () => {
    drawArmShareChart(state.adaptationScenario);
    drawResultChart();
  });
}

init();
