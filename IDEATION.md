402Pilot: Learning What to Pay For in Agent Micropayment Markets

**Status:** superseded by the ACM paper and current implementation. Kept as
an ideation record; do not treat scenario counts, method names, or benchmark
numbers here as current specification.






当 AI agent 已经可以通过 x402 付款之后，它如何决定“该不该付、付给谁、付多少钱、什么时候用便宜服务、什么时候用贵服务”？

这比单纯实现 x402 payment loop 更有研究价值。你们原 PPT 已经把问题说出来了：x402 解决 payment channel，但缺少 budget、ROI decision、risk/fraud control、trust/reputation 等 finance layer；POC 里也已经提出 controlled micro-economy、cheap/medium/premium API tier、budget policy engine、cost-vs-quality measurement 等核心设想。 ￼

⸻

一、项目核心定位

1.1 不要把它定位成“x402 payment demo”

如果只是：

Agent → API → 402 Payment Required → x402 payment → API response

那只是工程集成，不够顶会。

因为 x402 / A402 / 各种 agent payment projects 已经在快速发展。x402 的核心就是把 payment 变成 HTTP request-response loop 的一部分；A402 进一步指出 x402 的问题是支付、服务执行和结果交付没有原子性，并提出 Atomic Service Channels，把服务执行嵌入 payment channel。 ￼

所以我们的 paper 不应该主打：

我们实现了 agent micropayment。

而应该主打：

我们研究 autonomous agents 在 micropayment market 中的经济决策问题。

⸻

1.2 推荐的研究定位

我建议把项目定位为：

Payment-aware adaptive service selection for autonomous agents in x402-based micropayment markets.

中文：

面向 x402 微支付市场的 agent 自主付费服务选择与经济决策。

它研究的不是“怎么付款”，而是：

1. agent 应该什么时候付费？
2. 在多个 paid services 之间应该选谁？
3. 如何在质量、成本、延迟、失败风险之间做 trade-off？
4. 当服务质量和价格随时间变化时，agent 如何在线适应？
5. 如何证明 agent 不只是能付款，而是会花钱？

这才是 paper 的主线。

⸻

二、文章题目备选

我建议准备三类题目：系统型、算法型、经济层型。

方向 A：系统 + agent finance layer

Title 1

Paying Wisely: A Payment-Aware Finance Layer for Autonomous Agents in x402 Micropayment Markets

这个题目最清楚。“Paying Wisely” 很有记忆点，强调 agent 会花钱。

Title 2

From Agent Payments to Agent Finance: Adaptive Service Selection for x402-Based Micropayments

这个题目很适合顶会风格。它清楚区分了 payment 和 finance。

Title 3

Beyond Payment Execution: Learning-Based Economic Decision-Making for Agent Micropayments

这个更泛化，不绑定 x402 太死，但仍然可以在系统里用 x402。

⸻

方向 B：bandit / learning 型

Title 4

Budget-Aware Contextual Bandits for Agent Micropayment Service Selection

这个很学术，直接点出方法。

Title 5

Non-Stationary Contextual Bandits for Autonomous Agent Service Markets

这个更像 ML / AI conference，但 x402 味道弱一点。

Title 6

Learning What to Pay For: Non-Stationary Contextual Bandits for Agentic Commerce

这个我比较喜欢。核心非常准：不是 how to pay，而是 what to pay for。

⸻

方向 C：market / ecosystem 型

Title 7

Can Agents Spend Rationally? A Controlled Micro-Economy for x402-Based Agentic Commerce

这个适合系统实验 paper，强调 controlled micro-economy。

Title 8

A Controlled Micro-Economy for Evaluating Autonomous Agent Micropayment Decisions

这个更偏 evaluation benchmark / testbed。

⸻

我最推荐的题目

如果目标是顶会 paper，我最推荐：

Learning What to Pay For: Budget-Aware Contextual Bandits for Agent Micropayment Markets

副标题可以是：

A Finance Layer for x402-Based Autonomous Agents

完整题目：

Learning What to Pay For: Budget-Aware Contextual Bandits for Agent Micropayment Markets

或者：

From Agent Payments to Agent Finance: Learning What to Pay For in x402 Micropayment Markets

第二个更有故事性。

⸻

三、最需要解决的问题

3.1 当前 x402 的核心缺口

x402 解决的是：

How can an agent pay for a service?

但没有解决：

How should an agent decide which service is worth paying for?

你们 PPT 里已经说得很对：

Payment ≠ Service Guarantee
No native budgeting
No ROI decision engine
No autonomous risk control
No reputation / dispute layer

这些是 finance layer 的缺口。 ￼

但我们要进一步收窄，否则题目太大。一个 paper 不可能同时解决 budget、ROI、risk、reputation、escrow、dispute、atomic payment。

⸻

3.2 第一篇 paper 应该解决的问题

我建议第一篇 paper 只聚焦一个问题：

Paid service selection under budget, quality uncertainty, and non-stationary provider behavior.

中文：

在预算约束、质量不确定、服务表现随时间变化的条件下，agent 如何选择付费服务。

这足够重要，也足够可做。

具体场景：

一个 agent 需要完成一系列任务。
每个任务到来时，它可以选择 Cheap / Medium / Premium / 或不同 provider。
每个 provider 有价格、延迟、失败率、质量分布。
agent 只能购买一个服务，不能把所有服务都买一遍。
服务质量可能随时间变化。
agent 的目标是在有限预算下最大化任务完成质量。

这个问题自然导向 contextual bandit，而不是完整 RL。

⸻

3.3 为什么不是 full RL？

这是我们讨论中非常关键的一点。

Agent workflow 可能是多步的，例如：

search → retrieve → summarize → verify → write

但每一个 paid service invocation 是一个局部经济决策：

在当前上下文下，我应该买哪个服务？

现实中 agent 不能同一个请求把 Cheap / Medium / Premium 都买一遍再比较。那不符合经济理性，也会破坏微支付的意义。

所以我们应该这样定义：

Although an agent workflow may contain multiple paid service calls, each micropayment event is modeled as a one-shot service selection decision with immediate feedback. The agent learns across repeated interactions rather than purchasing all alternatives within the same request.

中文：

Agent 的整体任务流可以是多步的，但每一次微支付事件本身是单次购买决策。Agent 根据历史经验学习，而不是在同一个请求中把所有候选服务都买一遍。

这句话非常重要。它能挡住 reviewer 对“为什么不用 RL”的质疑。

⸻

四、研究空白与相关工作位置

4.1 已有工作一：x402 / A402 / agent payment

x402 已经让 API 和 agents 可以通过 HTTP-native payment 进行 per-request micropayment。公开介绍中也明确把 x402 描述成 autonomous agents and APIs 的 per-request payment protocol。 ￼

A402 进一步指出 x402 缺少 service execution、payment、result delivery 之间的端到端原子性，并提出 Atomic Service Channels 来解决 trust-minimized payment 与服务交付绑定问题。 ￼

所以 related work 可以写成：

Existing work focuses on payment execution, settlement efficiency, and service-delivery atomicity.

我们的区别：

We focus on pre-payment decision-making: which service should the agent pay for under uncertainty and budget constraints?

⸻

4.2 已有工作二：budget / spending guardrails

已经有一些项目做 agent spending management、budget tracking、spend approval、ROI analysis。比如 Harvey Budget 的描述就是 x402-paid MCP server for agent spending management with budget tracking, ROI analysis, and spend approval。 ￼

所以我们不能说：

第一次提出 agent budget / ROI layer。

这会被反驳。

我们的区别要写成：

Existing budget systems constrain or approve spending.
Our system learns adaptive service-selection policies from quality, cost, latency, and failure feedback.

中文：

现有系统更多是预算限制和审批；我们研究的是 agent 如何根据上下文和历史反馈学习选择最值得买的服务。

⸻

4.3 已有工作三：LLM routing / contextual bandits

这块也已经有人做了。Online Multi-LLM Selection 用 contextual bandits 做实时 adaptive LLM selection，并比较 accuracy 和 cost-efficiency。 ￼

Adaptive LLM Routing under Budget Constraints 也明确把 LLM routing 研究成 contextual bandit 问题，用 bandit feedback 来做 adaptive decision-making，而不是对所有模型做 exhaustive inference。 ￼

LLM Bandit 也已经把 LLM selection 建模成 multi-armed bandit，目标是动态选择合适模型以平衡性能和成本。 ￼

所以我们不能说：

第一次用 contextual bandit 做 LLM/tool/service selection。

我们的区别应该是：

LLM routing optimizes computational inference cost.
Agent micropayment service selection optimizes economic spending over external paid services, where payment is explicit, irreversible, provider behavior is non-stationary, and budget constraints are wallet-level.

这就是场景创新。

⸻

4.4 已有工作四：non-stationary / discounted Thompson Sampling

Discounted Thompson Sampling 是成熟方法。DS-TS 用 discount factor 处理 non-stationary bandit，包括 abrupt change 和 smooth change。 ￼

所以不能说：

我们提出新的 Discounted TS。

应该说：

We instantiate the finance layer with Discounted Contextual Thompson Sampling as a practical online policy.

⸻

五、核心研究问题

我建议把 paper 的 research questions 写成 4 个。

RQ1：agent 能不能学会“花钱”？

Can an autonomous agent improve task utility per dollar by learning from paid service feedback?

指标：

utility per dollar
cost per successful task
task completion under fixed budget
quality under fixed spend

⸻

RQ2：context 是否重要？

Does task context improve paid service selection compared with non-contextual spending policies?

比较：

ordinary TS vs contextual TS
rule-based vs contextual bandit
always premium vs contextual bandit

如果 contextual bandit 在不同任务类型上明显更好，说明不是简单平均选服务，而是能理解“什么任务值得买贵服务”。

⸻

RQ3：non-stationarity 是否重要？

Can a discounted policy adapt when provider quality, price, latency, or failure rate changes over time?

这是非常关键的实验。因为如果服务质量稳定，普通 TS 就够了；我们的 Discounted Contextual TS 的价值主要在非平稳市场。

要设计 provider drift：

premium provider gradually degrades
cheap provider improves
medium provider temporarily fails
provider price changes
latency spikes

然后看 discounted 方法恢复速度、regret、预算效率。

⸻

RQ4：真实 x402 integration 是否带来系统可行性？

Can the learned service-selection policy be integrated into a real x402 payment loop without excessive overhead?

指标：

policy decision latency
x402 payment overhead
end-to-end service latency
budget enforcement correctness
number of paid calls
failure handling

这会让 paper 从纯算法变成系统 paper。

⸻

六、问题建模

6.1 基本设定

每一轮 t，一个 task 到来：

x_t = task context

候选服务集合：

A = {cheap, medium, premium}

或者更一般：

A = {provider_1, provider_2, ..., provider_K}

每个服务有价格：

c_a

agent 选择一个服务：

a_t ∈ A

通过 x402 支付，获得输出：

y_t = service_a(x_t)

然后 evaluator 给出质量分：

q_t ∈ [0,1]

同时记录成本、延迟、失败：

cost c_t
latency l_t
failure f_t

reward 可以定义为：

r_t = q_t - λ · normalized_cost_t - μ · normalized_latency_t - ν · failure_t

也可以用 constrained optimization：

maximize Σ q_t
subject to Σ cost_t ≤ B

我建议两种都写。主实验用 reward，补充实验用 fixed-budget constraint。

⸻

6.2 为什么是 contextual bandit？

因为每轮只有 selected service 的反馈：

agent 只知道自己买的服务质量
不知道没有买的服务在同一个任务上的表现

这正是 bandit feedback。

它不是 supervised learning，因为 supervised routing 默认知道所有候选服务的 label 或质量。

它也不是 full RL，因为每次服务选择都有即时 reward，不需要等整个多步 workflow 结束再 credit assignment。

⸻

6.3 为什么是 non-stationary？

因为 agent market 中服务质量不是固定的：

provider 负载变化
模型版本变化
服务涨价 / 降价
API failure rate 变化
恶意 provider 短期刷高表现后降质
网络 latency 变化

所以需要 discount / sliding window / change detection。

⸻

七、方法设计

7.1 系统架构

建议 paper 的系统名字可以叫：

PayPilot
PayWise
AgentFin
MicroPayPilot
SpendWise

我个人推荐：

PayPilot

简单，有 agent 自动驾驶花钱的感觉。

系统结构：

Task arrives
    ↓
Context Encoder
    ↓
Budget State Manager
    ↓
Payment-Aware Service Selector
    ↓
x402 Payment Executor
    ↓
Service Response
    ↓
Quality / Latency / Cost Evaluator
    ↓
Reward Calculator
    ↓
Policy Update

⸻

7.2 Context Encoder

context 不要太复杂，第一版可以包括：

task_type
task_difficulty
prompt length
expected output type
remaining budget ratio
historical provider statistics
latency requirement
quality requirement

任务类型可以是：

QA
summarization
code generation
data extraction
translation
reasoning
search/retrieval

difficulty 可以用：

LLM judge 打分
prompt length
estimated required reasoning depth
historical success probability

⸻

7.3 Payment-Aware Service Selector

主方法：

Discounted Contextual Thompson Sampling

可以写成：

For each provider a, maintain a posterior over expected reward conditioned on context.
At each decision, sample reward parameters from the posterior and choose the provider with highest sampled utility.
Old observations are exponentially discounted to adapt to non-stationary provider behavior.

中文：

对每个服务商维护一个带上下文的收益估计；每次从后验分布采样，选择采样收益最高的服务；历史观测按衰减因子折扣，使系统更重视近期表现。

⸻

7.4 Budget-aware extension

单纯 reward 还不够。要加入预算状态，否则 reviewer 会说只是普通 routing。

建议设计：

remaining_budget_ratio = B_remaining / B_total

作为 context 的一部分。

另外可以设计动态 λ：

λ_t = λ_0 · g(B_remaining, T_remaining)

当预算越少，cost penalty 越大。

例如：

λ_t = λ_0 · (1 + α · max(0, expected_remaining_spend - B_remaining))

不用把公式搞太复杂，但概念要清楚：

The agent becomes more cost-sensitive when the remaining budget is low.

这会让方法更贴近 finance layer，而不是普通 service routing。

⸻

7.5 Risk-aware extension

可以加入 failure penalty：

r_t = q_t - λ_t c_t - μ l_t - ν f_t

其中：

f_t = 1 if service fails, times out, returns invalid output, or violates task constraints.

也可以维护 provider risk score：

risk_a = moving average of failures / low-quality responses

但第一篇不要扩展太多。risk 可以作为 reward component，不要单独做 reputation system。

⸻

八、实验设计

这是最重要的部分。顶会 reviewer 最关心的是：实验能不能证明这个问题真实、有价值、方法有效。

我建议设计三层实验。

⸻

8.1 Experiment 1：Controlled Micro-Economy Simulation

这是主实验。

目标

证明在受控市场中，PayPilot 能在 budget constraint 下获得更高 utility。

环境

建立一个模拟 agent service market：

3 service tiers:
Cheap: low cost, lower average quality, higher variance
Medium: moderate cost, stable quality
Premium: high cost, high average quality, lower failure rate

但关键是不同任务类型下表现不同：

simple QA: cheap already足够
hard reasoning: premium明显更好
summarization: medium性价比最高
coding: premium质量高但cost高
data extraction: cheap/medium差异小

这样才能体现 contextual 的价值。

任务集

可以用公开 benchmark：

MMLU / GSM8K / HotpotQA / Natural Questions
HumanEval / MBPP
CNN/DailyMail or XSum
FEVER or fact verification

也可以构建 mixed workload。

注意，如果用真实 LLM API，会有成本；可以先用记录好的数据或开源模型模拟 provider。

⸻

8.2 Experiment 2：Non-Stationary Provider Dynamics

这是证明 Discounted 的关键实验。

设计几种变化：

Abrupt change

t = 500 后 premium provider 质量下降
t = 800 后 medium provider 延迟上升
t = 1000 后 cheap provider failure rate 增加

Smooth drift

cheap provider 逐渐变好
premium provider 逐渐变差

Price shock

premium price 从 0.01 涨到 0.02 (S3 price shock — 2x)
medium 降价

Adversarial-looking but not adversarial

某 provider 前期表现好，后期变差

指标：

adaptation speed
cumulative regret
utility per dollar
budget exhaustion time
post-change recovery quality

预期结果：

普通 TS 适应慢
Discounted TS / Discounted Contextual TS 适应快
Rule-based 无法适应质量变化
Always Premium 质量高但预算很快耗尽
Always Cheap 成本低但完成率低

⸻

8.3 Experiment 3：Real x402-in-the-loop Prototype

虽然你现在说不要做 POC，但真正 paper 最后还是需要 implementation。不是课程 demo，而是 research artifact。

这个实验不是为了炫技，而是证明可行性。

实现：

Orchestrator agent
3 paid API services
x402 payment middleware
wallet / mock wallet / testnet
policy engine
evaluator
logging dashboard

服务可以是：

Cheap service: small/local model
Medium service: mid-size model
Premium service: stronger commercial model

也可以是同一个任务的不同 API：

basic search API
enhanced search API
premium reasoning API

指标：

decision overhead
payment overhead
end-to-end latency
budget enforcement
successful payment rate
service failure handling

这部分要控制篇幅。主贡献不是 x402 implementation，而是 adaptive finance layer。

⸻

九、Baseline 设计

Baseline 要非常关键。不能只和 Random 比。

9.1 Simple baselines

Always Cheap
Always Medium
Always Premium
Random

作用：

证明固定策略不够

⸻

9.2 Rule-based baselines

至少设计两个：

Rule-based Budget

if remaining_budget > 70%: use Premium
elif remaining_budget > 30%: use Medium
else: use Cheap

Rule-based Difficulty

if task_difficulty high: use Premium
elif medium: use Medium
else: use Cheap

这个很重要，因为 reviewer 会问：为什么不用简单规则？

⸻

9.3 Learning baselines

ε-greedy
UCB
LinUCB
Vanilla Thompson Sampling
Contextual Thompson Sampling
Discounted Thompson Sampling
Sliding-Window Thompson Sampling
Discounted Contextual Thompson Sampling

不一定全部放主表，但至少要有：

Vanilla TS
Contextual TS
Discounted TS
Discounted Contextual TS
LinUCB

这样才能说明：

context 有用
discount 有用
TS 有用
budget-aware reward 有用

⸻

9.4 Oracle baseline

需要一个 upper bound：

Oracle knows the true quality of all providers for each task and picks the best utility provider.

注意：online agent 不能真的买所有服务，但 offline evaluation 可以有 oracle。要写清楚：

Oracle is used only as an offline upper bound and is not available to the online agent.

⸻

十、Metrics

10.1 质量指标

task success rate
average quality score
LLM-as-judge score
exact match / F1 / pass@1 for code
human preference score if possible

⸻

10.2 经济指标

这是 paper 的灵魂。

total spend
cost per successful task
quality per dollar
budget exhaustion rate
remaining budget at target quality
ROI = utility / cost

可以定义：

Cost-per-success = total_spend / number_of_successful_tasks
Utility-per-dollar = total_utility / total_spend

⸻

10.3 learning 指标

cumulative regret
moving average reward
adaptation time after provider drift
exploration cost
policy stability

⸻

10.4 system 指标

policy decision latency
x402 payment latency
end-to-end latency
failed payment rate
invalid response rate

⸻

十一、贡献点设计

我建议 paper 的 contribution 写成 4 点。

Contribution 1：Problem formulation

We formulate autonomous agent micropayment service selection as a budget-aware, non-stationary contextual bandit problem.

中文：

我们首次将 agent 微支付中的付费服务选择问题系统建模为预算约束、非平稳的 contextual bandit 问题。

注意“首次”要谨慎。可以写：

To our knowledge, this is the first systematic formulation…

但如果担心被挑战，可以不用 first：

We provide a systematic formulation…

⸻

Contribution 2：Finance-layer system

We design a payment-aware finance layer that sits above x402 and decides which paid service to invoke before payment execution.

中文：

我们设计了一个位于 x402 payment execution 之上的 finance layer，使 agent 在付款前做经济决策。

⸻

Contribution 3：Budget-aware discounted contextual TS

We instantiate the finance layer with a budget-aware Discounted Contextual Thompson Sampling policy that adapts to task context, remaining budget, and non-stationary provider behavior.

注意不要说 invented algorithm。说 instantiate / adapt / operationalize。

⸻

Contribution 4：Controlled micro-economy evaluation

We build a controlled micro-economy benchmark for evaluating agent micropayment decisions under varying service quality, price, latency, and failure dynamics.

这个很重要。即使方法不是全新，如果 benchmark / evaluation framework 新，也能撑起 paper。

⸻

十二、文章结构建议

Abstract

核心结构：

Autonomous agents can now pay for APIs through x402-like micropayment protocols.
However, payment execution alone does not make agents economically rational.
Agents still lack a finance layer for deciding which service is worth paying for under budget, quality uncertainty, and non-stationary provider behavior.
We formulate each paid service invocation as a budget-aware non-stationary contextual bandit problem.
We propose PayPilot, a payment-aware finance layer that selects paid service tiers before x402 execution and updates its policy from quality, cost, latency, and failure feedback.
PayPilot uses Discounted Contextual Thompson Sampling with budget-sensitive reward shaping.
Experiments in a controlled micro-economy and x402-in-the-loop prototype show that PayPilot improves utility-per-dollar, reduces cost-per-success, and adapts faster to provider drift than rule-based and non-contextual baselines.

⸻

Introduction

结构：

1. AI agents are becoming economic actors.
2. x402/A402 solve payment execution and settlement.
3. But agents still do not know what to pay for.
4. Existing budget guardrails limit spending but do not learn adaptive service choice.
5. Existing LLM routing optimizes model inference, not explicit micropayment markets.
6. We propose payment-aware adaptive service selection.
7. Contributions.

⸻

Motivation Example

一定要有一个简单例子：

An agent has $1 budget and must solve 200 tasks.
Premium API costs $0.01 and is high quality.
Cheap API costs $0.0005 but is noisy.
If the agent always uses premium, it runs out of budget after 100 calls.
If it always uses cheap, many hard tasks fail.
The rational strategy is context-dependent:
cheap for easy tasks, medium for routine tasks, premium for hard/high-value tasks.
But service quality changes over time, so static rules fail.

这个例子非常有说服力。

⸻

Problem Formulation

写成正式 notation。

⸻

System Design

包括：

Context Encoder
Policy Engine
Budget Manager
x402 Payment Executor
Evaluator
Policy Update

⸻

Method

重点写：

Discounted Contextual Thompson Sampling
Budget-aware reward
Non-stationary update

⸻

Evaluation

分四部分：

Experimental setup
Baselines
Main results
Ablation

Ablation 很重要：

without context
without discount
without budget-aware λ
without latency/failure penalty

⸻

Discussion

讨论边界：

We do not solve escrow/dispute.
We do not guarantee service correctness cryptographically.
We are complementary to A402.
We focus on pre-payment decision-making, not payment atomicity.

这个非常重要。否则 reviewer 会拿 A402 来打你。

⸻

十三、核心创新边界：一定要讲清楚

我们的创新不是：

不是 x402 协议创新
不是区块链支付创新
不是新的 Thompson Sampling 算法
不是完整 reputation / escrow system
不是 full RL agent planner

我们的创新是：

agent micropayment market 中，付款前的经济决策层
payment-aware service selection formulation
budget-aware + non-stationary contextual bandit
controlled micro-economy benchmark
x402-in-the-loop validation

这条边界非常重要。

⸻

十四、可能的 reviewer 质疑与应对

质疑 1：这不就是 LLM routing 吗？

回答：

LLM routing chooses among inference models, usually within a single platform or compute stack. Our setting involves explicit economic payment events, wallet-level budgets, irreversible per-call costs, provider failure, and x402 payment execution. The decision is not only computational routing but autonomous economic spending.

中文：

LLM routing 是模型调用优化；我们是显式支付市场中的经济决策。

⸻

质疑 2：为什么不用 RL？

回答：

Each micropayment event provides immediate feedback and only one selected service is observed. The agent learns across repeated purchases. Therefore contextual bandits are a more appropriate and lightweight formulation than full long-horizon RL.

中文：

每次购买后马上有反馈，而且只能观察买过的服务；这正是 contextual bandit，不需要 full RL。

⸻

质疑 3：Discounted TS 不是新算法

回答：

We do not claim algorithmic novelty in Thompson Sampling. Our contribution is the payment-aware formulation, system integration, budget-sensitive reward design, and controlled micro-economy evaluation for x402-based agent markets.

中文：

算法不是创新，问题定义、系统、奖励设计和实验环境是创新。

⸻

质疑 4：A402 已经解决 x402 问题了

回答：

A402 addresses payment-service atomicity after a service is selected. Our work addresses which service should be selected before payment. The two are complementary.

中文：

A402 解决付了钱以后服务交付和支付绑定；我们解决付款前选谁。

⸻

质疑 5：LLM-as-judge 评估质量可靠吗？

回答：

可以做多种 evaluator：

automatic benchmark metrics
LLM-as-judge
human evaluation subset
task-specific correctness metrics

代码任务用 pass@1，QA 用 exact match/F1，summarization 用 LLM judge + human subset。

⸻

十五、实施路线

虽然你说现在不要做 POC，但如果要实施成 paper，我建议按下面路线走。

Phase 1：问题和仿真环境

目标：

先不接 x402，完成 controlled micro-economy simulator

内容：

task generator
provider simulator
quality/cost/latency/failure model
non-stationary dynamics
baseline policies
evaluation scripts

产出：

main algorithm results
regret curves
budget curves
utility-per-dollar curves

这是最快拿到 paper signal 的部分。

⸻

Phase 2：真实任务和服务替代

目标：

把 provider simulator 替换成真实模型 / API / benchmark

例如：

Cheap = small open-source model
Medium = mid-size model
Premium = strong commercial model

任务：

QA
coding
summarization
reasoning

产出：

真实质量分布
真实成本
真实 latency

⸻

Phase 3：x402-in-the-loop

目标：

把 payment executor 接进去

只需要证明：

policy can operate before payment
payment proof can be attached
budget can be updated after paid call
logs are auditable

不需要做复杂 escrow。

⸻

Phase 4：paper writing

目标：

把仿真结果 + 真实任务结果 + x402系统结果合成 paper

⸻

十六、最强 paper framing

我建议最后把项目的一句话 thesis 写成：

x402 makes agents able to pay; our work makes agents decide what is worth paying for.

中文：

x402 让 agent 能付款；我们的工作让 agent 知道什么值得付。

这是整个 paper 的灵魂。

⸻

十七、最终建议的计划书框架

下面是可以直接作为 project proposal 的结构。

⸻

Project Proposal Draft

Title

Learning What to Pay For: Budget-Aware Contextual Bandits for Agent Micropayment Markets

1. Motivation

Autonomous agents are increasingly able to invoke APIs, access tools, and interact with external services. Protocols such as x402 make it possible for agents to pay for services on a per-request basis. However, payment execution alone does not make agents economically rational. An agent with a wallet still lacks a decision mechanism for determining which service is worth paying for, when to use a cheap provider, when to upgrade to a premium provider, and how to adapt when provider quality changes.

2. Problem

We study the problem of paid service selection in agent micropayment markets. At each paid invocation, an agent observes the task context, remaining budget, and historical provider performance, then selects one service from multiple paid providers or service tiers. After payment and service execution, the agent receives feedback in terms of quality, cost, latency, and failure. The goal is to maximize long-term task utility under budget constraints.

3. Key Insight

Although an agent workflow may contain multiple paid calls, each micropayment event is a one-shot economic decision. The agent cannot purchase all candidate services for the same request and then choose the best one. Instead, it must learn from historical experience and make a rational selection before payment. This naturally leads to a contextual bandit formulation rather than full reinforcement learning.

4. Method

We propose a payment-aware finance layer above x402. The layer contains a context encoder, budget manager, service-selection policy, x402 payment executor, evaluator, and online policy updater. We instantiate the policy with Budget-Aware Discounted Contextual Thompson Sampling. The discount factor allows the policy to adapt to non-stationary provider behavior, while budget-aware reward shaping makes the agent more cost-sensitive as its remaining budget decreases.

5. Reward

The reward combines service quality, payment cost, latency, and failure:

reward = quality - λ_t · cost - μ · latency - ν · failure

where λ_t depends on the remaining budget.

6. Experiments

We evaluate the system in three stages:

1. Controlled micro-economy simulation
2. Real-task service selection with different model/API tiers
3. x402-in-the-loop prototype validation

7. Baselines

Always Cheap
Always Medium
Always Premium
Random
Rule-based budget policy
Rule-based difficulty policy
ε-greedy
UCB / LinUCB
Vanilla Thompson Sampling
Contextual Thompson Sampling
Discounted Thompson Sampling
Sliding-Window Thompson Sampling
Oracle offline upper bound

8. Metrics

task success rate
average quality
total spend
cost per successful task
utility per dollar
budget exhaustion rate
cumulative regret
adaptation speed after provider drift
end-to-end latency
payment overhead

9. Contributions

1. We formulate x402-based paid service selection as a budget-aware, non-stationary contextual bandit problem.
2. We design a finance layer that enables agents to make pre-payment economic decisions.
3. We instantiate the layer with a budget-aware discounted contextual Thompson Sampling policy.
4. We construct a controlled micro-economy benchmark for evaluating autonomous agent micropayment decisions.
5. We validate the system with an x402-in-the-loop implementation.

⸻

十八、最重要的判断

这个项目要想达到顶会 paper 水平，不能只做：

x402 + agent + API payment

这太像 demo。

也不能只做：

contextual bandit service selection

这又太像已有 LLM routing。

最好的切入点是二者之间的空白：

x402 / agent payment 领域缺少 learning-based pre-payment decision layer；
LLM routing 领域没有显式处理 agent micropayment、wallet budget、payment irreversibility 和 service-market non-stationarity。

所以 paper 的真正价值是：

把 agent micropayment 从“支付协议问题”提升为“自主经济决策问题”。

这就是我们应该围绕的核心。
















----------

## 实验设计完整复述

---

### 一、整体结构

实验名为 **402Pilot-Bench**，是一个单一的综合评测框架。通过五个独立运行的场景（S1–S5）、一套固定的 comparator 算法池、以及一套消融实验，同时回答四个研究问题：学习是否优于固定策略（RQ1）、上下文是否有助于选择（RQ2）、discount 机制是否能处理非平稳性（RQ3）、以及整个系统能否在真实 x402 支付循环中运行（RQ4）。

---

### 二、数据集：预生成响应池

实验不在运行时调用任何 API。在实验开始前，针对所有 `(任务, Provider)` 组合预先生成响应，形成一个固定数据集，实验时完全本地回放。

具体做法：每个 `(任务, Provider)` 组合生成 **5 个响应版本**（不同随机种子下的温度采样）。实验运行时，按 run seed 控制地从 5 个版本中抽取一个，既保留了真实 LLM 的输出随机性，又保证 30 个 seed 之间的可复现性。

对于确定性评估器（pass@1、EM/F1），质量分数在预生成阶段就计算并存储。对于 LLM-as-judge，judge 模型 ID 和 seed 一并记录。Provider E 的 40% timeout 事件也在预生成阶段用固定 version 标注（versions 0 和 1 强制 timeout）。

预生成总量约 **20,600 次 API 调用**（824 任务 × 5 providers × 5 versions），一次性成本。实验本身零 API 成本。

---

### 三、五个 Provider

**K = 5**，分三种角色：标准分层（A/B/C）+ 行为型（D/E）。

**Provider A — Cheap**
- LLM：Qwen3-8B，non-thinking 模式（reasoning 关闭）
- 工具：无，纯参数记忆作答
- 特点：最便宜、最快，质量较低

**Provider B — Medium**
- LLM：GPT-5.4-mini，reasoning 关闭
- 工具：BM25 检索，从题目附带文档中取 top-2 段落
- 特点：中等成本和质量，稳定可靠

**Provider C — Premium**
- LLM：GPT-5.4，启用 CoT pipeline
- 工具：全文档注入 context window（利用大 context window 直接看所有文档）+ Coding 任务时使用代码执行沙箱
- 特点：最贵、最慢，质量最高

**Provider D — Adversarial**
- LLM：GPT-5.4-mini，reasoning 关闭（与 B 完全相同）
- 工具：BM25 top-2（与 B 完全相同）
- 特殊行为：加载 adversarial system prompt，指示模型高置信度、不表达不确定性，产生流畅但事实错误的答案
- 成本与 B 相同，外观与 B 无法通过价格/延迟区分

**Provider E — Flaky**
- LLM：GPT-5.4-mini，reasoning 关闭（与 B 完全相同）
- 工具：BM25 top-2（与 B 完全相同）
- 特殊行为：40% 的调用被标记为 timeout（version-level 机制，5 个 version 中固定 v=0 和 v=1 强制 timeout）。Timeout 时质量=0、成本=base_price（x402 协议下失败也要付费）、延迟=超时阈值；正常工作时质量与 B 持平
- 期望质量 = 0.6 × B质量，显著低于 B，但靠价格/底层模型无法区分（必须从失败观察学习）

**B/D/E 三方对比的意义**：三者成本相同、底层模型相同，rule-based 策略无法区分。PA-DCTS 必须通过奖励反馈学习区分三者，这正是 contextual bandit 的核心价值所在。

---

### 四、三类任务

**M = 3**，覆盖不同的评估客观性梯度，同时产生 Provider D 可被检测的难度梯度。

**T1 — Coding（HumanEval，150 题）**
- 任务：函数补全 / bug 修复，生成满足 docstring 的 Python 代码
- 评分：pass@1，执行单元测试，完全确定性
- D 的检测难度：极高，代码语法合法但逻辑错误，测试直接失败，约 20 轮内发现 D

**T2 — Multi-hop QA（HotpotQA validation set，300 题）**
- 任务：基于题目附带的约 10 个段落，进行跨文档多步推理
- 评分：归一化 EM + token-level F1，取两者较高值（标准化处理：小写、去冠词和标点）
- D 的检测难度：中等，事实错误大多被 F1 捕捉，偶有流畅错误答案部分匹配

**T3 — Web Search（双子池，共 375 题）**
- 闭合型（40%，约 150 题）：TriviaQA-web subset，短事实型问题，有标准答案。Provider 从题目附带网页文档中检索作答，不需实时联网。评分：归一化 EM + F1，与 T2 相同协议
- 开放型（60%，约 225 题）：自定义综合性问题，无单一正确答案（例："从至少两个视角总结 X 的利与弊"）。评分：LLM-as-judge，结构化评分标准（事实准确性、完整性、无幻觉），记录 judge 模型 ID 和 seed
- D 的检测难度：闭合型中等高，开放型低——流畅错误答案可能部分满足评分标准

**核心发现预期**：Coding 约 20 轮内规避 D；Multi-hop QA 约 50 轮；T3 开放题持续受损。这揭示了 bandit 防欺诈能力受评估器质量约束的基本规律。

任务混合比例默认均匀（各约 33%），按 run seed 有放回采样，难度由数据集本身隐含，无需额外设定难度分布。

---

### 五、五个场景（独立运行）

每个场景独立运行：10,000 轮 × 30 seeds。相同 provider、相同任务池、相同 seed——只有参数变化时间表不同。

**S1 — Stationary**
无任何变化。A/B/C 保持基础配置，D 全程对抗，E 全程 40% timeout。建立静态市场基线，验证 bandit 在稳定环境下能否识别 D/E 并学到最优任务-provider 匹配。

**S2 — Abrupt Degradation**
- Round 3,000：Provider C 质量下跌（切换低质量响应池）
- Round 5,000：Provider E 的 timeout 率从 40% 飙升至 80%

两个事件测试不同类型的突变适应：C 的质量退化信号较缓，测试 discount 机制能否加速感知；E 的超时飙升信号明显，验证失败惩罚项 ν·f_t 的有效性。

**S3 — Smooth Drift**
- 0–10,000 轮：Provider A 质量平滑提升（模拟廉价模型版本升级）
- 0–10,000 轮：Provider D 在 T3 开放题上的对抗响应逐渐更难被 LLM judge 发现（错误答案流畅度提升）

这是最复杂的场景：A 涨分是真实改善（bandit 应增加分配），D 涨分是评估器失效的虚假信号（bandit 不应增加分配）。bandit 需要通过 T1/T2 的客观评估信号辨别 D 的真实质量，避免被 T3 开放题的虚假信号误导。

**S4 — Price Shock**
- Round 5,000：Provider C 价格翻倍，Provider B 价格减半（质量不变）

纯价格事件。C 翻倍后，B 的性价比全面提升；B 减价后，同层的 D/E 相对变贵（它们的价格不随 B 变化），bandit 应进一步偏向 B 而非 D/E。测试 budget-aware λ_t 能否正确响应成本结构重组。

**S5 — Mixed Realistic Regime**
S2/S3/S4 事件的交错组合，时间点错开。最贴近真实 x402 市场。S5 的存在依赖于 S2/S3/S4 的单独结果作为对照基准。

---

### 六、Comparator 算法池

| 类别 | 算法 |
|---|---|
| 固定基线 | Always-A（cheap）、Always-B（medium）、Always-C（premium）、Random |
| 规则基线 | Difficulty rule、Budget rule |
| 非上下文学习 | ε-greedy、Vanilla Thompson Sampling、Discounted TS |
| 上下文学习 | LinUCB、Contextual Thompson Sampling |
| 我们的方法 | **PA-DCTS** |
| 参考上界 | Oracle（离线最优，不参与比较） |

D 和 E 是所有学习策略的可选 arm，但不设专属固定基线。

---

### 七、核心指标

质量：平均任务质量、任务成功率。  
经济：总花费、每成功任务成本、**utility-per-dollar**（主指标）、ROI。  
预算：钱包耗尽轮次、达到固定质量目标的剩余预算。  
学习：累积 regret（对比 Oracle）、漂移/冲击后的适应时间。  
系统（仅 x402-in-the-loop）：决策延迟、支付开销、端到端延迟、支付成功率。

---

### 八、消融实验（PA-DCTS 的四个组件逐一移除）

- A1：去掉上下文（Vanilla TS，忽略 x_t）
- A2：去掉 discount（γ=1，无非平稳适应）
- A3：去掉 budget-aware λ（固定 λ）
- A4：去掉延迟/失败惩罚（μ=ν=0）

---

### 九、运行规模

每个（policy × scenario）组合运行 **30 seeds**，报告均值 ± 标准差，图表用 95% CI。  
统计检验：Welch's t-test + Bonferroni 校正。  
总运行次数：5 scenarios × 10 policies × 30 seeds = **1,500 次完整运行**，全部本地数据集回放，无 API 成本，单机几小时内可完成。

---

### 十、x402-in-the-loop 验证

独立的可行性探测，不是第六个场景。使用真实 x402 客户端，五个本地付费端点（A/B/C/D/E 各一个），mock testnet 钱包，仅在 S1（稳定场景）下运行。目标是测量系统开销：决策延迟、支付开销、端到端延迟、支付成功率，以及 D/E 在真实 x402 支付流程下的行为是否正确处理。预期结论：PA-DCTS 的决策开销亚毫秒级，支付和服务调用主导端到端延迟。

---

以上是当前实验设计的完整状态，请告知是否需要调整。
