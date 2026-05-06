# 402Pilot — Notation Cheatsheet

**Purpose**: Single source of truth for symbols across paper §2 / §5 / §6,
algorithm box, `pilot402/runtime/reward.py` and `pilot402/policies/padct.py`
docstrings, and cross-document references. **Use these symbols verbatim**
in every paper section. Inconsistencies are bugs.

LaTeX symbol conventions are given alongside each entry; copy from here
when writing.

---

## 1. Time, arms, contexts

| Symbol | LaTeX | Meaning | Domain / value |
| --- | --- | --- | --- |
| `t` | `t` | Round index | `t ∈ {0, 1, …, T−1}` |
| `T` | `T` | Total rounds per run | `T = 10 000` |
| `a` | `a` | Arm / provider | `a ∈ {P-cheap, P-mid, P-premium, P-adv, P-flaky}` |
| `K` | `K` | Number of arms | `K = 5` |
| `a_t` | `a_t` | Arm chosen at round `t` | one of `a` |
| `x_t` | `\mathbf{x}_t` | Context vector at round `t` | ℝ^d, `d = 7` (NaiveEncoder) |
| `k(x_t)` | `k(\mathbf{x}_t)` | Task-type bucket from context | `k ∈ {T1, T2, T3a, T3b}`; degenerate to a single bucket under `−C` ablation |
| `K_b` | `K_b` | Number of context buckets | `K_b = 4` (main) or `K_b = 1` (`−C` ablation) |

---

## 2. Per-round observations

| Symbol | LaTeX | Meaning | Domain |
| --- | --- | --- | --- |
| `q_t` | `q_t` | Quality score for the chosen arm | `[0, 1]` (continuous, evaluator-grounded) |
| `c_t` | `c_t` | Raw cost charged this round (USDC) | `≥ 0` (e.g. 0.0005 / 0.002 / 0.01) |
| `c̃_t` | `\tilde c_t` | Normalized cost | `\tilde c_t = \mathrm{clip}(c_t / c_\max, 0, 1)`, `c_\max = \$0.01` |
| `f_t` | `f_t` | Failure flag | `{0, 1}` (timeout / parse-failure) |
| `B` | `B` | Total wallet budget | `B = \$50` |
| `B_t` | `B_t` | Remaining wallet budget at start of round `t` | `B_0 = B`; `B_{t+1} = B_t − c_t` |

Bandit feedback: only `(q_t, c_t, f_t)` for `a = a_t` is observed; other
arms' outcomes are unseen.

---

## 3. Reward / utility

| Symbol | LaTeX | Definition | Domain | Notes |
| --- | --- | --- | --- | --- |
| `ν` | `\nu` | Failure penalty constant | `ν = 0.5` (locked) | Bundled with `q` to form *utility* |
| `u_t` | `u_t` | Utility (intrinsic provider quality) | `u_t = q_t − \nu f_t` ∈ `[−ν, +1]` | What the **Q-posterior** tracks |
| `α` | `\alpha` | Sigmoid sharpness for budget pressure | `α = 2.0` (locked) | |
| `λ_t` | `\lambda_t` | Raw budget-pressure multiplier (Wallet output) | `\lambda_t = \exp(α · \mathrm{burn\_excess}_t)` | Monotone non-decreasing in spend rate vs. plan |
| `λ_norm` | `\lambda_{\mathrm{norm}}` | Bounded sigmoid weight | `λ_norm = λ_t / (1 + λ_t) ∈ (0, 1)` | Used in reward & decision rule |
| `r_t` | `r_t` | Payment-aware reward | `r_t = (1 − λ_norm) · u_t − λ_norm · \tilde c_t` ∈ `[−1, +1]` | Decision criterion (NOT the posterior update signal) |

**Critical separation**: `u_t` updates the policy's belief about a provider; `r_t` ranks arms at decision time. This decoupling keeps beliefs stable when `λ_t` jumps.

---

## 4. Discount

| Symbol | LaTeX | Meaning | Value | Notes |
| --- | --- | --- | --- | --- |
| `γ` | `\gamma` | Quality-posterior discount per round | `γ = 0.999` | `γ = 1` recovers vanilla TS (`−D` ablation) |
| `γ_c` | `\gamma_c` | Cost-posterior discount per round | `γ_c = 0.999` | Same value as `γ` in main; ablate together as `−D` |

When the paper text refers to "the discount factor" without subscript,
it's `γ` with `γ_c = γ`. Distinguish only when ablating one independently.

---

## 5. Posteriors (per arm × bucket pair)

For each arm `a` and bucket `k`, two independent Gaussian posteriors are
maintained:

### Q-posterior (quality)

| Symbol | LaTeX | Meaning |
| --- | --- | --- |
| `μ₀_q` | `\mu_{0,q}` | Q-posterior prior mean (default 0.5) |
| `σ₀²_q` | `\sigma_{0,q}^2` | Q-posterior prior variance (default 1.0) |
| `σ²_q` | `\sigma_q^2` | Q-likelihood (observation) variance (default 0.09) |
| `n^{a,k}_t` | `n^{a,k}_t` | Discounted effective sample count |
| `S^{a,k}_t` | `S^{a,k}_t` | Discounted weighted sum of utilities |
| `θ_q^{a,k}` | `\theta_q^{a,k}` | Posterior mean over `μ` (closed form below) |
| `Σ_q^{a,k}` | `\Sigma_q^{a,k}` | Posterior variance over `μ` |
| `\hat u^{a,k}` | `\hat u^{a,k}` | Sample drawn from `\mathcal{N}(θ_q^{a,k}, Σ_q^{a,k})` at decision time |

Closed forms (Normal–Normal conjugacy):
```
precision^{a,k}_t = 1/σ₀²_q + n^{a,k}_t / σ²_q
Σ_q^{a,k}        = 1 / precision^{a,k}_t
θ_q^{a,k}        = Σ_q^{a,k} · (μ₀_q / σ₀²_q + S^{a,k}_t / σ²_q)
```

### C-posterior (cost)

Same shape as Q-posterior, separate hyperparameters:

| Symbol | LaTeX | Value |
| --- | --- | --- |
| `μ₀_c` | `\mu_{0,c}` | spec base price (e.g. `0.01` for premium) |
| `σ₀²_c` | `\sigma_{0,c}^2` | `1e-4` (locked) |
| `σ²_c` | `\sigma_c^2` | `1e-6` (locked, very tight likelihood — costs are nearly deterministic) |
| `θ_c^{a,k}, Σ_c^{a,k}` | `\theta_c^{a,k}, \Sigma_c^{a,k}` | Same Normal–Normal closed form |
| `\hat c^{a,k}` | `\hat c^{a,k}` | Sample → normalize: `\tilde{\hat c}^{a,k} = \mathrm{clip}(\hat c^{a,k}/c_\max, 0, 1)` |

### Discounted sufficient statistics update

Per-round, before observing new data, **all** `(a, k)` cells discount:
```
n^{a,k}_t = γ · n^{a,k}_{t−1}
S^{a,k}_t = γ · S^{a,k}_{t−1}
```
Then the chosen arm's bucket updates with the observation:
```
n^{a_t, k_t}_t += 1
S^{a_t, k_t}_t += u_t        (Q-posterior)
S_c^{a_t, k_t}_t += c_t       (C-posterior, separate sufficient stats)
```

Discount applies regardless of pulls — non-stationarity is wall-clock,
not pull-conditional.

---

## 6. Decision rule (per round)

```
For each affordable arm a (i.e. B_t ≥ effective_price(a, t)):
    \hat u^{a,k} ~ N(θ_q^{a,k}, Σ_q^{a,k})        (Q-posterior sample)
    \hat c^{a,k} ~ N(θ_c^{a,k}, Σ_c^{a,k})        (C-posterior sample)
    \tilde{\hat c}^{a,k} = clip(\hat c^{a,k} / c_max, 0, 1)
    π^{a,k} = (1 − λ_norm) · \hat u^{a,k}  −  λ_norm · \tilde{\hat c}^{a,k}

a_t = argmax_a π^{a, k(x_t)}
```

Under `−TS` ablation, replace `~` with `=`: use posterior **means**
`θ_q^{a,k}, θ_c^{a,k}` directly, no sampling.

Under `−P` ablation, force `λ_norm = 0`: rank by `\hat u^{a,k}` only.

---

## 7. Scenarios (locked)

| Symbol | Meaning | Implementation |
| --- | --- | --- |
| `S1` | Stationary | `StationaryScenario` (identity transform) |
| `S2` | Mid outage | `MidOutageScenario(outage_start=3000, outage_end=5500, outage_failure_rate=0.30)` — P-mid fails 30% of the time inside `[3000, 5500)`, fully recovers after |
| `S3` | Premium promo | `PremiumDropScenario(shock_round=1000, price_multiplier=0.2)` — at round 1000, P-premium price drops from $0.01 to $0.002 (= mid price) |

---

## 8. Metrics (four locked)

| Symbol | LaTeX | Definition |
| --- | --- | --- |
| `\text{task\_q}` | `\overline{q}` | Mean quality across rounds (proxy for task_success_rate) |
| `\text{ROI}` | `\mathrm{ROI}` | `Σ_t q_t / Σ_t c_t` |
| `\text{cum\_PA}` | `R_T` | `Σ_t r_t` (cumulative payment-aware reward) |
| `\text{Regret}_T` | `\mathrm{Regret}_T` | `R_T^{\mathrm{Oracle}} - R_T^{\pi}` (cumulative regret vs. True Oracle) |
| `\text{AdaptT}` | `\tau_{\mathrm{adapt}}` | Rounds for trailing-200 ROI to recover within 5% of pre-event level (S2 / S3 only) |

---

## 9. Ablation labels

| Label | Means | Effect |
| --- | --- | --- |
| `−P` | No payment-aware | Force `λ_norm = 0` in decision rule |
| `−D` | No discount | `γ = 1` (and `γ_c = 1`) |
| `−C` | No contextual | Single global bucket (`K_b = 1`) |
| `−TS` | No Thompson sampling | Use posterior means instead of samples |

The "full" PA-DCT enables all four; each ablation flips exactly one
flag. **Never use the old A1 / A2 / A3 / A4 naming** — that was an
earlier outline draft.

---

## 10. LaTeX preamble snippet

For paper writing, paste this into the preamble to keep symbols consistent:

```latex
\newcommand{\nrm}{\mathrm{norm}}
\newcommand{\lamn}{\lambda_{\nrm}}
\newcommand{\bex}{\mathrm{burn\_excess}}
\newcommand{\padct}{PA\nobreakdash-DCT}
\newcommand{\rt}{r_t}
\newcommand{\ut}{u_t}
\newcommand{\ctilde}{\tilde c_t}
\newcommand{\thetaq}[2]{\theta_q^{#1,#2}}
\newcommand{\thetac}[2]{\theta_c^{#1,#2}}
\newcommand{\Sigmaq}[2]{\Sigma_q^{#1,#2}}
\newcommand{\Sigmac}[2]{\Sigma_c^{#1,#2}}
\newcommand{\hatu}[2]{\hat u^{#1,#2}}
\newcommand{\hatc}[2]{\hat c^{#1,#2}}
\newcommand{\Regret}{\mathrm{Regret}}
\newcommand{\AdaptT}{\tau_{\mathrm{adapt}}}
```

Then in body text: `$\rt = (1 - \lamn)\ut - \lamn\ctilde$` etc.

---

## 11. Authoritative references

If anything below is ambiguous, the source of truth is:

1. This file (latest)
2. `pilot402/runtime/reward.py` docstring (reward formula)
3. `pilot402/policies/padct.py` docstring (algorithm structure)
4. `pilot402/policies/posterior.py` (Gaussian posterior closed form)
5. `logs/paper_design_decisions.md` §11 (locked title, naming, contributions)

PLAN.md / IDEATION.md are historical; **do not** lift notation from them.
