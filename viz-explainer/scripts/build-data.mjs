import { createReadStream, mkdirSync, writeFileSync } from "node:fs";
import { readdir } from "node:fs/promises";
import path from "node:path";
import readline from "node:readline";

const root = path.resolve(new URL("../../", import.meta.url).pathname);
const outDir = path.join(root, "viz-explainer");
const providers = ["P-cheap", "P-mid", "P-premium", "P-adv", "P-flaky"];
const binSize = 200;
const maxCost = 0.01;

const providerSpecs = {
  "P-cheap": {
    label: "Cheap",
    model: "Qwen3-8B",
    cost: 0.0005,
    signal: "Low-cost fallback",
    note: "Useful when wallet pressure dominates quality.",
    zhSignal: "省钱但能力有限",
    zhNote: "适合作为低成本保底臂。",
    quality: 0.61,
    reliability: 1,
  },
  "P-mid": {
    label: "Mid",
    model: "GPT-5.4-mini + BM25",
    cost: 0.002,
    signal: "Balanced baseline",
    note: "The strongest fixed arm in the stationary market.",
    zhSignal: "平衡点",
    zhNote: "静态市场里的强固定基线。",
    quality: 0.82,
    reliability: 1,
  },
  "P-premium": {
    label: "Premium",
    model: "GPT-5.4 + tools",
    cost: 0.01,
    signal: "High quality, high cost",
    note: "Becomes attractive after the S3 promotion.",
    zhSignal: "高质量高价格",
    zhNote: "S3 降价后变成机会臂。",
    quality: 0.87,
    reliability: 1,
  },
  "P-adv": {
    label: "Adversarial",
    model: "GPT-5.4-mini + BM25",
    cost: 0.002,
    signal: "Fluent but wrong",
    note: "Same cost tier as P-mid, separable only through feedback.",
    zhSignal: "看似可信但会错",
    zhNote: "价格和栈都像 P-mid，只能靠反馈识别。",
    quality: 0.52,
    reliability: 0.96,
  },
  "P-flaky": {
    label: "Flaky",
    model: "GPT-5.4-mini + BM25",
    cost: 0.002,
    signal: "Good when it responds",
    note: "40% timeout rate, and payments are irreversible.",
    zhSignal: "成功时不错但会 timeout",
    zhNote: "40% timeout，付款不可逆。",
    quality: 0.49,
    reliability: 0.6,
  },
};

const scenarios = {
  S1: {
    label: "S1 Stationary",
    zhLabel: "S1 静态市场",
    short: "baseline",
    source: "results/scenario_sweep/S1",
    eventRound: null,
    eventWindow: null,
    summary: "No market shock. This is the control case for learning cost and stable arm shares.",
    zhSummary: "无市场冲击，用来对照正常学习成本和稳定选择分布。",
  },
  S2: {
    label: "S2 Mid outage",
    zhLabel: "S2 Mid outage",
    short: "outage",
    source: "results/scenario_sweep/S2",
    eventRound: 3000,
    eventWindow: [3000, 5500],
    summary: "P-mid receives a 30% timeout injection during rounds 3000-5500.",
    zhSummary: "P-mid 在 3000-5500 轮注入 30% timeout。",
  },
  S3: {
    label: "S3 Premium promo",
    zhLabel: "S3 Premium promo",
    short: "promo",
    source: "results/scenario_sweep_s3promo_v2",
    eventRound: 1000,
    eventWindow: [1000, 10000],
    summary: "P-premium drops from $0.01 to $0.002 starting at round 1000.",
    zhSummary: "P-premium 从 $0.01 降到 $0.002。",
  },
};

const headline = {
  S1: [
    ["PA-DCT", 5512, 54, 0.797, 377, 1325, 21.11, 0.4],
    ["AlwaysMid", 5831, 29, 0.819, 410, 1006, 20.0, 0],
    ["AlwaysCheap", 5164, 23, 0.61, 1220, 1673, 5.0, 0],
    ["AlwaysPremium", -3887, 3, 0.866, 87, 10725, 50.0, 0],
    ["BudgetRule", -82, 14, 0.831, 208, 6919, 40.0, 0],
    ["Oracle", 6837, 27, 0.901, 561, 0, 16.05, 0],
  ],
  S2: [
    ["PA-DCT", 5147, 80, 0.761, 356, 1662, 21.37, 1.9],
    ["AlwaysMid", 5069, 37, 0.757, 379, 1740, 20.0, 7.5],
    ["AlwaysCheap", 5164, 23, 0.61, 1220, 1645, 5.0, 0],
    ["AlwaysPremium", -3887, 3, 0.866, 87, 10696, 50.0, 0],
    ["BudgetRule", -408, 18, 0.769, 192, 7217, 40.0, 7.5],
    ["Oracle", 6809, 25, 0.901, 551, 0, 16.34, 0],
  ],
  S3: [
    ["PA-DCT", 5911, 51, 0.831, 429, 1206, 19.38, 0.4],
    ["AlwaysMid", 5831, 29, 0.819, 410, 1286, 20.0, 0],
    ["AlwaysCheap", 5164, 23, 0.61, 1220, 1952, 5.0, 0],
    ["AlwaysPremium", 3112, 19, 0.865, 309, 4004, 28.0, 0],
    ["BudgetRule", 3064, 17, 0.859, 307, 4053, 28.0, 0],
    ["Oracle", 7117, 24, 0.906, 722, 0, 12.54, 0],
  ],
};

const ablations = [
  {
    id: "noPayment",
    component: "Payment-aware λ",
    label: "Budget pressure",
    impact: "The policy stops changing the quality/cost tradeoff as the wallet depletes.",
    breaks: "Selection no longer reacts to wallet pressure.",
    zhLabel: "预算压力",
    zhImpact: "预算权重消失，cum_PA 大幅坍塌。",
    zhBreaks: "不会根据钱包压力改变质量/成本权重。",
    metric: "S1 regret +7222",
    severity: 0.94,
  },
  {
    id: "noDiscount",
    component: "Discount γ",
    label: "Evidence decay",
    impact: "Old observations keep dominating after a market shock.",
    breaks: "Posteriors adapt too slowly when provider behavior changes.",
    zhLabel: "证据衰减",
    zhImpact: "旧证据不衰减，冲击恢复更慢。",
    zhBreaks: "市场变了以后，旧 posterior 仍然压着新信号。",
    metric: "S2 恢复约慢 35%",
    severity: 0.54,
  },
  {
    id: "noContext",
    component: "Context",
    label: "Task context",
    impact: "Task-specific provider differences are averaged away.",
    breaks: "T1/T2/T3 preferences collapse into one shared bucket.",
    zhLabel: "任务上下文",
    zhImpact: "任务类型差异被抹平，机会利用变弱。",
    zhBreaks: "T1/T2/T3 的 provider 偏好被混成一个桶。",
    metric: "S3 task split 变钝",
    severity: 0.42,
  },
  {
    id: "noTS",
    component: "Thompson sampling",
    label: "Exploration",
    impact: "Mean performance can look similar, but seed variance expands.",
    breaks: "Early lucky or unlucky samples can lock in the wrong arm.",
    zhLabel: "探索机制",
    zhImpact: "均值接近，但种子方差显著放大。",
    zhBreaks: "早期偶然样本更容易把策略锁死。",
    metric: "variance 5-9x",
    severity: 0.38,
  },
  {
    id: "noCostPosterior",
    component: "Cost posterior",
    label: "Cost learning",
    impact: "The S3 premium promotion is almost invisible.",
    breaks: "Price changes do not become a learnable signal.",
    zhLabel: "成本后验",
    zhImpact: "S3 中几乎发现不了 premium 降价。",
    zhBreaks: "价格变化不会进入可学习信号。",
    metric: "premium share 60% -> 4%",
    severity: 0.78,
  },
];

const roundSelections = {
  S1: [
    [800, "Early exploration", "Posteriors are still settling in the no-shock control.", "早期探索", "没有冲击，观察 posterior 还在收敛时的选择。"],
    [2200, "Stable entry", "P-mid is usually established as the main arm.", "稳定前段", "P-mid 通常已经成为主力臂。"],
    [5000, "Midpoint control", "A direct reference point for S2/S3 event windows.", "中点对照", "和 S2/S3 的事件窗口做横向比较。"],
    [8500, "Late stability", "Checks whether wallet pressure changes the stable mix.", "后期稳定", "看长期预算压力下是否仍维持选择结构。"],
  ],
  S2: [
    [1200, "Pre-outage", "P-mid has not degraded yet.", "故障前", "P-mid 尚未 outage，是正常市场对照点。"],
    [3200, "Shock entry", "Failures begin and the policy is still confirming the signal.", "刚进入 outage", "P-mid 开始出现失败，策略还在确认信号。"],
    [4200, "Outage middle", "The migration away from P-mid should be visible.", "outage 中段", "迁移应该已经明显发生。"],
    [6200, "Recovery", "P-mid is healthy again and the policy starts returning.", "恢复后", "P-mid 恢复后，策略开始回流但保留一些谨慎。"],
  ],
  S3: [
    [800, "Pre-promo", "P-premium is still expensive and mostly exploratory.", "促销前", "P-premium 仍然昂贵，只少量探索。"],
    [1200, "Price signal", "The cost posterior starts seeing the promotion.", "刚降价", "成本 posterior 开始看到价格变化。"],
    [2200, "Migration", "Premium's quality-cost advantage begins to dominate.", "迁移期", "P-premium 的性价比优势开始主导。"],
    [7000, "Exploitation", "The promotion has been fully exploited for thousands of rounds.", "利用期", "降价已被充分利用，premium share 保持高位。"],
  ],
};

function scenarioDir(scenario) {
  return path.join(root, scenarios[scenario].source, "padct");
}

async function seedFiles(dir) {
  const files = await readdir(dir);
  return files
    .filter((file) => /^seed_\d+\.jsonl$/.test(file))
    .sort()
    .map((file) => path.join(dir, file));
}

async function readJsonl(file, onRecord) {
  const rl = readline.createInterface({
    input: createReadStream(file),
    crlfDelay: Infinity,
  });
  for await (const line of rl) {
    if (!line || line.charCodeAt(0) !== 123) continue;
    onRecord(JSON.parse(line));
  }
}

async function buildArmShares(scenario) {
  const files = await seedFiles(scenarioDir(scenario));
  const bins = new Map();

  for (const file of files) {
    await readJsonl(file, (record) => {
      const bin = Math.floor(record.round / binSize);
      if (!bins.has(bin)) {
        bins.set(bin, Object.fromEntries(providers.map((provider) => [provider, 0])));
      }
      bins.get(bin)[record.chosen_arm] += 1;
    });
  }

  return [...bins.entries()]
    .sort((a, b) => a[0] - b[0])
    .map(([bin, counts]) => {
      const total = providers.reduce((sum, provider) => sum + counts[provider], 0);
      return {
        round: bin * binSize + binSize / 2,
        shares: Object.fromEntries(
          providers.map((provider) => [provider, total ? +(counts[provider] / total).toFixed(4) : 0]),
        ),
      };
    });
}

function defaultCost(provider, scenario, round) {
  if (scenario === "S3" && provider === "P-premium" && round >= 1000) return 0.002;
  return providerSpecs[provider].cost;
}

async function buildRoundExamples(scenario, selectedRounds) {
  const file = path.join(scenarioDir(scenario), "seed_00.jsonl");
  const stats = Object.fromEntries(
    providers.map((provider) => [
      provider,
      { pulls: 0, utility: 0, cost: 0, fail: 0 },
    ]),
  );
  const selectionMap = new Map(
    selectedRounds.map(([round, label, reason, zhLabel, zhReason]) => [
      round,
      { label, reason, zhLabel, zhReason },
    ]),
  );
  const wanted = new Set(selectionMap.keys());
  const examples = [];

  await readJsonl(file, (record) => {
    if (wanted.has(record.round)) {
      const lambdaNorm = record.lambda_t / (1 + record.lambda_t);
      const candidates = providers.map((provider) => {
        const arm = stats[provider];
        const meanUtility = arm.pulls ? arm.utility / arm.pulls : 0.5;
        const meanCost = arm.pulls ? arm.cost / arm.pulls : defaultCost(provider, scenario, record.round);
        const score = (1 - lambdaNorm) * meanUtility - lambdaNorm * (meanCost / maxCost);
        return {
          provider,
          pulls: arm.pulls,
          utility: +meanUtility.toFixed(3),
          cost: +meanCost.toFixed(4),
          score: +score.toFixed(3),
          failRate: arm.pulls ? +(arm.fail / arm.pulls).toFixed(3) : 0,
        };
      });
      candidates.sort((a, b) => b.score - a.score);

      examples.push({
        scenario,
        round: record.round,
        label: selectionMap.get(record.round).label,
        reason: selectionMap.get(record.round).reason,
        zhLabel: selectionMap.get(record.round).zhLabel,
        zhReason: selectionMap.get(record.round).zhReason,
        taskType: record.task_type,
        chosen: record.chosen_arm,
        quality: +record.quality.toFixed(3),
        cost: +record.charged_cost_usdc.toFixed(4),
        failure: Boolean(record.failure_flag),
        utility: +record.utility.toFixed(3),
        reward: +record.payment_aware_reward.toFixed(3),
        budget: +record.budget_remaining_usdc.toFixed(2),
        lambdaNorm: +lambdaNorm.toFixed(3),
        candidates,
      });
    }

    const arm = stats[record.chosen_arm];
    arm.pulls += 1;
    arm.utility += record.utility;
    arm.cost += record.charged_cost_usdc;
    arm.fail += record.failure_flag ? 1 : 0;
  });

  return examples;
}

function formatHeadline() {
  return Object.fromEntries(
    Object.entries(headline).map(([scenario, rows]) => [
      scenario,
      rows.map(([policy, cumPA, cumStd, meanQ, roi, regret, spend, failPct]) => ({
        policy,
        cumPA,
        cumStd,
        meanQ,
        roi,
        regret,
        spend,
        failPct,
      })),
    ]),
  );
}

async function main() {
  const [s1Shares, s2Shares, s3Shares, s1Examples, s2Examples, s3Examples] = await Promise.all([
    buildArmShares("S1"),
    buildArmShares("S2"),
    buildArmShares("S3"),
    buildRoundExamples("S1", roundSelections.S1),
    buildRoundExamples("S2", roundSelections.S2),
    buildRoundExamples("S3", roundSelections.S3),
  ]);

  const data = {
    generatedAt: new Date().toISOString(),
    provenance: {
      S1: "logs/m3f_results.md + results/scenario_sweep/S1",
      S2: "logs/m3f_results.md + results/scenario_sweep/S2",
      S3: "logs/m3f_results.md + results/scenario_sweep_s3promo_v2",
    },
    providers: providerSpecs,
    scenarios,
    headline: formatHeadline(),
    armShares: { S1: s1Shares, S2: s2Shares, S3: s3Shares },
    roundExamples: [...s1Examples, ...s2Examples, ...s3Examples],
    ablations,
  };

  mkdirSync(outDir, { recursive: true });
  writeFileSync(
    path.join(outDir, "data.js"),
    `window.PILOT402_EXPLAINER_DATA = ${JSON.stringify(data, null, 2)};\n`,
  );
}

main().catch((error) => {
  console.error(error);
  process.exit(1);
});
