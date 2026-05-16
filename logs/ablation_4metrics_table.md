# Ablation Matrix: 4 metrics × 4 ablations × 3 scenarios

**Metrics:**
- **q_bar_T** = full-horizon mean quality Σq_t / T (unserved rounds after wallet exhaustion count as q_t = 0, so policies that bankrupt mid-run are correctly penalised)
- **ROI** = Σ q / Σ $ (raw quality per dollar)
- **PA-gap** = Oracle cum_PA − policy cum_PA (empirical PA-regret to the True Oracle)
- **AdaptT** = trailing-200 ROI shock-response time (S2: >=95% of pre-outage ROI; S3: >=110% of pre-promotion ROI)

## S1 (stationary)

| Ablation | PA-gap | q_bar_T | ROI (q/$) | AdaptT |
|---|---|---|---|---|
| Full PA-DCT | 1325 | 0.797 | 378 | n/a |
| −P (no payment-aware) | 8547 | 0.555 | 111 | n/a |
| −D (no discount, γ=1) | 1092 | 0.810 | 412 | n/a |
| −C (no contextual) | 1159 | 0.812 | 390 | n/a |
| −TS (greedy) | 1297 | 0.740 | 535 | n/a |

## S2 (outage 3000-5500)

| Ablation | PA-gap | q_bar_T | ROI (q/$) | AdaptT |
|---|---|---|---|---|
| Full PA-DCT | 1662 | 0.761 | 357 | 1467 (30/30) |
| −P (no payment-aware) | 8775 | 0.517 | 103 | 1611 (14/30) |
| −D (no discount, γ=1) | 1696 | 0.745 | 399 | 2249 (30/30) |
| −C (no contextual) | 1584 | 0.761 | 368 | 1176 (30/30) |
| −TS (greedy) | 1746 | 0.687 | 537 | 1125 (30/30) |

## S3 (promo at round 1000)

| Ablation | PA-gap | q_bar_T | ROI (q/$) | AdaptT |
|---|---|---|---|---|
| Full PA-DCT | 1206 | 0.831 | 429 | 200 (30/30) |
| −P (no payment-aware) | 2589 | 0.840 | 351 | 200 (30/30) |
| −D (no discount, γ=1) | 1143 | 0.838 | 426 | 279 (30/30) |
| −C (no contextual) | 1092 | 0.848 | 425 | 398 (29/30) |
| −TS (greedy) | 1453 | 0.742 | 552 | 2232 (24/30) |

## Cross-scenario adaptation_time comparison (D and C)

| Scenario | full | −D | −C | full vs −D Δ | full vs −C Δ |
|---|---|---|---|---|---|
| S2 | 1467 | 2249 | 1176 | -781 | +292 |
| S3 | 200 | 279 | 398 | -79 | -198 |
