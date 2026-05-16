# Ablation Matrix: 4 metrics × 4 ablations × 3 scenarios

**Metrics:**
- **q_bar_T** = full-horizon mean quality Σq_t / T (unserved rounds after wallet exhaustion count as q_t = 0, so policies that bankrupt mid-run are correctly penalised)
- **ROI** = Σ q / Σ $ (raw quality per dollar)
- **PA-gap** = Oracle cum_PA − policy cum_PA (empirical PA-regret to the True Oracle)
- **AdaptT** = trailing-200 ROI shock-response time (S2: >=95% of pre-outage ROI; S3: >=110% of pre-promotion ROI)

## S1 (stationary)

| Ablation | cum_PA | q_bar_T | ROI (q/$) | PA-gap | AdaptT |
|---|---|---|---|---|---|
| Full PA-DCT | 5512±54 | 0.797 | 378 | 1325 | n/a |
| −P (no payment-aware) | -1710±588 | 0.555 | 111 | 8547 | n/a |
| −D (no discount, γ=1) | 5745±95 | 0.810 | 412 | 1092 | n/a |
| −C (no contextual) | 5679±41 | 0.812 | 390 | 1159 | n/a |
| −TS (greedy) | 5540±458 | 0.740 | 535 | 1297 | n/a |

## S2 (outage 3000-5500)

| Ablation | cum_PA | q_bar_T | ROI (q/$) | PA-gap | AdaptT |
|---|---|---|---|---|---|
| Full PA-DCT | 5147±80 | 0.761 | 357 | 1662 | 1467 (30/30) |
| −P (no payment-aware) | -1966±507 | 0.517 | 103 | 8775 | 1611 (14/30) |
| −D (no discount, γ=1) | 5113±125 | 0.745 | 399 | 1696 | 2249 (30/30) |
| −C (no contextual) | 5225±66 | 0.761 | 368 | 1584 | 1176 (30/30) |
| −TS (greedy) | 5063±481 | 0.687 | 537 | 1746 | 1125 (30/30) |

## S3 (promo at round 1000)

| Ablation | cum_PA | q_bar_T | ROI (q/$) | PA-gap | AdaptT |
|---|---|---|---|---|---|
| Full PA-DCT | 5911±51 | 0.831 | 429 | 1206 | 200 (30/30) |
| −P (no payment-aware) | 4528±369 | 0.840 | 351 | 2589 | 200 (30/30) |
| −D (no discount, γ=1) | 5974±93 | 0.838 | 426 | 1143 | 279 (30/30) |
| −C (no contextual) | 6024±35 | 0.848 | 425 | 1092 | 398 (29/30) |
| −TS (greedy) | 5663±244 | 0.742 | 552 | 1453 | 2232 (24/30) |

## Cross-scenario adaptation_time comparison (D and C)

| Scenario | full | −D | −C | full vs −D Δ | full vs −C Δ |
|---|---|---|---|---|---|
| S2 | 1467 | 2249 | 1176 | -781 | +292 |
| S3 | 200 | 279 | 398 | -79 | -198 |
