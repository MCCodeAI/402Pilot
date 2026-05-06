# PA-DCT — Algorithm Box (paper §5 Algorithm 1)

**Purpose**: Single source of truth for the boxed pseudocode in paper §5
Method. Notation follows `logs/notation.md` exactly. Implementation:
`pilot402/policies/padct.py` (`select` + `update`); `pilot402/runtime/loop.py`
provides the surrounding wallet / scenario plumbing.

This document carries:

1. The **plaintext** pseudocode (what we agree on)
2. The **LaTeX** version (paste into the paper)
3. A **code-correspondence** table (every line maps to a function in the codebase)
4. Notes on intentional simplifications for the box vs. the implementation

If notation in the paper text drifts from this file, this file wins.

---

## 1. Plaintext pseudocode

```
ALGORITHM 1 — PA-DCT (Payment-Aware Discounted Contextual Thompson sampling)

Inputs:
  • Provider set        a ∈ {1, …, K}  with spec costs c̄_a
  • Wallet              with budget B, sigmoid sharpness α, target burn rate
  • Discount            γ ∈ (0, 1]            (γ_q for Q, γ_c for C; default γ_q = γ_c = γ)
  • Failure penalty     ν                     (= 0.5)
  • Cost normalizer     c_max                 (= max_a c̄_a)
  • Context encoder     k(·) : context → {1, …, K_b}
  • Q-posterior priors  μ_{0,q}, σ²_{0,q}, σ²_q
  • C-posterior priors  μ_{0,c}^a = c̄_a, σ²_{0,c}, σ²_c

Initialize, for each (a, k) ∈ arms × buckets:
  Q-posterior_{a,k} ← N(μ_{0,q}, σ²_{0,q})    with likelihood var σ²_q
  C-posterior_{a,k} ← N(c̄_a,    σ²_{0,c})    with likelihood var σ²_c

For round t = 0, 1, …, T−1:

  // 1.  Discount every cell — non-stationarity is wall-clock, not pull-conditional.
  For each (a, k):
      Q-posterior_{a,k}.discount(γ_q)
      C-posterior_{a,k}.discount(γ_c)

  // 2.  Observe context and budget pressure.
  Receive context x_t and remaining budget B_t.
  k_t  ← k(x_t)
  λ_t  ← wallet.get_lambda()                   = exp(α · burn_excess_t)
  λ_norm ← λ_t / (1 + λ_t)                     ∈ (0, 1)

  // 3.  Score each affordable arm by sampling both posteriors.
  Affordable_t ← { a : B_t ≥ effective_price(a, t) }
  If Affordable_t is empty: STOP (bankruptcy)
  For each a ∈ Affordable_t:
      û_a ~ Q-posterior_{a, k_t}.sample()                  // Thompson sample of utility
      ĉ_a ~ C-posterior_{a, k_t}.sample()                  // Thompson sample of cost
      c̃_a ← clip(ĉ_a / c_max, 0, 1)
      π_a ← (1 − λ_norm) · û_a  −  λ_norm · c̃_a            // PA-score

  // 4.  Pick the arm.
  a_t ← argmax_{a ∈ Affordable_t} π_a

  // 5.  Pay & observe (delegated to the x402 layer; bandit sees only outcomes).
  Pay c_{a_t} via x402 ; receive (q_t, c_t, f_t)
  u_t ← q_t − ν · f_t                                       // utility (intrinsic)
  r_t ← (1 − λ_norm) · u_t  −  λ_norm · clip(c_t / c_max, 0, 1)   // PA-reward (logged, not used to update)

  // 6.  Update only the chosen (arm, bucket) cell.
  Q-posterior_{a_t, k_t}.update(u_t)
  C-posterior_{a_t, k_t}.update(c_t)
  wallet.record_spend(c_t)
```

**Reading guide.** Step 1 is the discount sweep (the "D" of PA-DCT). Step
2 reads the budget pressure (the "P"). Step 3 samples both posteriors (the
"TS") and computes the payment-aware decision criterion. Step 4 is the
contextual Thompson choice (the "C" — the bucket `k_t = k(x_t)` enters
here). Step 5 is the x402 payment, deliberately a black box for the
algorithm. Step 6 propagates the observation back into the posterior the
policy is meant to learn (Q-posterior on `u_t`, C-posterior on raw `c_t`),
plus the wallet-level spend tracking.

**Termination.** The loop exits early on bankruptcy (no affordable arm).
Otherwise it runs for the full `T` rounds.

---

## 2. LaTeX version (algorithm2e — paste into paper)

```latex
\begin{algorithm}[t]
\DontPrintSemicolon
\caption{PA-DCT (Payment-Aware Discounted Contextual Thompson sampling)}
\label{alg:padct}
\KwIn{providers $\{1,\dots,K\}$ with spec costs $\bar c_a$;
      discount $\gamma \in (0,1]$; failure penalty $\nu$;
      cost normalizer $c_{\max}$; encoder $k(\cdot): \mathbf{x} \to \{1,\dots,K_b\}$;
      priors $\mu_{0,q}, \sigma^2_{0,q}, \sigma^2_q$ (Q),
      $\bar c_a, \sigma^2_{0,c}, \sigma^2_c$ (C);
      wallet sharpness $\alpha$, target burn rate.}
\BlankLine
\For{$(a, k) \in \{1,\dots,K\} \times \{1,\dots,K_b\}$}{
  init Q-posterior$_{a,k}$ $\leftarrow \mathcal{N}(\mu_{0,q}, \sigma^2_{0,q})$\;
  init C-posterior$_{a,k}$ $\leftarrow \mathcal{N}(\bar c_a, \sigma^2_{0,c})$\;
}
\BlankLine
\For{$t = 0, 1, \dots, T-1$}{
  \tcp*[h]{1. Discount every cell (D)}\;
  \For{each $(a, k)$}{
    Q-posterior$_{a,k}.\mathrm{discount}(\gamma)$;\quad C-posterior$_{a,k}.\mathrm{discount}(\gamma)$\;
  }
  \tcp*[h]{2. Context and budget pressure (P)}\;
  observe $\mathbf{x}_t$, budget $B_t$\;
  $k_t \leftarrow k(\mathbf{x}_t)$\;
  $\lambda_t \leftarrow \exp(\alpha \cdot \mathrm{burn\_excess}_t)$\;
  $\lambda_{\mathrm{norm}} \leftarrow \lambda_t / (1 + \lambda_t)$\;
  \tcp*[h]{3. Score affordable arms by Thompson sampling (TS, C)}\;
  $\mathcal{A}_t \leftarrow \{a : B_t \ge \mathrm{eff\_price}(a, t)\}$\;
  \lIf{$\mathcal{A}_t = \emptyset$}{\Return (bankruptcy)}
  \For{$a \in \mathcal{A}_t$}{
    $\hat u_a \sim$ Q-posterior$_{a, k_t}$;\quad $\hat c_a \sim$ C-posterior$_{a, k_t}$\;
    $\tilde c_a \leftarrow \mathrm{clip}(\hat c_a / c_{\max}, 0, 1)$\;
    $\pi_a \leftarrow (1 - \lambda_{\mathrm{norm}})\,\hat u_a - \lambda_{\mathrm{norm}}\,\tilde c_a$\;
  }
  \tcp*[h]{4. Pick}\;
  $a_t \leftarrow \arg\max_{a \in \mathcal{A}_t} \pi_a$\;
  \tcp*[h]{5. Pay via x402; observe outcome}\;
  charge $c_{a_t}$;\quad observe $(q_t, c_t, f_t)$\;
  $u_t \leftarrow q_t - \nu f_t$\;
  \tcp*[h]{6. Update only the chosen cell (Q on $u$, C on raw $c$)}\;
  Q-posterior$_{a_t, k_t}.\mathrm{update}(u_t)$;\quad C-posterior$_{a_t, k_t}.\mathrm{update}(c_t)$\;
  wallet.record\_spend$(c_t)$\;
}
\end{algorithm}
```

---

## 3. Code correspondence

| Pseudocode line | Source | Notes |
| --- | --- | --- |
| `Q-posterior_{a,k} ← N(μ_{0,q}, σ²_{0,q})` | `padct.py` __post_init__ build of `_q_posteriors` | Default `prior_mean=0.5, prior_var=1.0, noise_var=0.09` |
| `C-posterior_{a,k} ← N(c̄_a, σ²_{0,c})` | `padct.py` __post_init__ build of `_c_posteriors` | Per-arm prior mean = spec cost; default `c_prior_var=1e-4, c_noise_var=1e-6` |
| Step 1 (discount) | `_discount_all()` called at top of `select` | Skipped on cost side when `enable_cost_posterior=False` |
| `λ_t = exp(α · burn_excess)` | `Wallet.get_lambda()` (in `runtime/wallet.py`) | Implementation does this directly; alg box treats `wallet.get_lambda()` as opaque |
| `λ_norm = λ_t / (1 + λ_t)` | `_lambda_norm()` | Returns 0 under `−P` ablation |
| Affordable set | `runtime/loop.py` lines 142-148 | Loop builds the affordable set BEFORE calling `select`; algorithm box folds the two for clarity |
| `û_a ~ Q-posterior` | `_q_value_for_arm` | Uses `posterior.sample()` if `enable_ts`, else `posterior_mean` |
| `ĉ_a ~ C-posterior` | `_c_value_for_arm` | Same, plus `provider_costs[a]` if cost posterior disabled |
| `π_a = (1 − λ_n)·û − λ_n·c̃` | `select` inner loop | identical |
| `a_t = argmax_a π_a` | `select` (best_arm) | identical |
| Step 5 — pay & observe | `runtime/loop.py` step 5 (PregenStore lookup + scenario transform) | The replay environment substitutes the x402 payment with a frozen `PregenRecord` |
| `u_t = q_t − ν·f_t` | `RewardCalculator.compute()` returns `utility` (`runtime/reward.py`) | identical |
| Q-posterior update | `update()` line `self._q_posteriors[arm][bucket].update(utility)` | identical |
| C-posterior update | `update()` line `self._c_posteriors[arm][bucket].update(observed_cost)` | Skipped under `enable_cost_posterior=False` |
| `wallet.record_spend(c_t)` | `runtime/loop.py` line 195 | Outside the policy; algorithm box folds it back in for completeness |

---

## 4. Intentional simplifications (alg box vs. implementation)

These are points where the box is intentionally less precise than the
code, to keep the box readable. None affects correctness.

1. **Wallet abstraction.** The box treats `wallet.get_lambda()` and
   `wallet.record_spend` as opaque calls. The actual `Wallet`
   implementation tracks burn rate vs target plan and computes
   `exp(α · burn_excess)` internally; the box gives the formula but does
   not unroll the wallet's state machine.

2. **Effective price.** The box says `eff_price(a, t)` for the
   affordability check. The runtime loop uses
   `scenario.effective_price(round_idx, pid, base_price)` — the box
   abstracts `Scenario` away, since for §5 the scenario is just "the
   environment generating round-`t` prices", not part of PA-DCT itself.

3. **Per-round discount of *all* cells.** This is `O(K · K_b)` per round
   in the box (and in the code). The box does not prematurely optimize.
   The runtime cost is negligible (`5 × 4 = 20` cells × 10 000 rounds ≈
   200k discount ops per seed, sub-second).

4. **Ablation flags.** The box describes the full PA-DCT. Each ablation
   modifies exactly one step:
   - `−P`: line `λ_norm ← λ_t / (1+λ_t)` becomes `λ_norm ← 0`.
   - `−D`: line `Q-posterior.discount(γ)` becomes a no-op (and same for C).
   - `−C`: collapse `K_b = 1` so `k_t` is constant.
   - `−TS`: replace `~` with `=` and read `posterior_mean` instead of sampling.
   - We do **not** show the ablation variants as separate algorithm
     boxes; the paper text describes the modifications inline.

5. **Latency observation.** `latency_s` is logged per round but never enters
   the reward (see `reward.py`: latency term retired 2026-05-02). The
   algorithm box omits it entirely.

---

## 5. Length / format guidance for the paper

- **One column** if the paper is double-column (NeurIPS / ICML / AAAI) —
  the boxed pseudocode above fits.
- **Caption** can be short: "PA-DCT: per-round Thompson-sampling decision
  rule with budget-aware cost penalty and discounted dual posteriors over
  quality and cost."
- **Don't repeat every detail in the body text.** The body should
  highlight the *four ablatable components* (P, D, C, TS) and the
  dual-posterior split (Q on `u`, C on raw `c`). Hyperparameter values
  go in §6.1 setup table or the appendix.
- **Cite `logs/notation.md`** in §5 first paragraph: "Throughout this
  section we use the notation summarized in [Appendix A: Notation]."
  (Or move the notation table into a paper appendix.)
