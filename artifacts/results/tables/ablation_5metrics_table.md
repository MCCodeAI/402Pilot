# Ablation Matrix: 4 metrics × 5 ablations + Full × 3 scenarios

Reproduces paper Table 6 (component ablations).

**Metrics:**
- **PA-gap/T** = (Oracle cum_PA − policy cum_PA)/T, paired by seed; reported as mean ± std over 30 seeds. Lower is better.
- **ROI** = Σ q / Σ $ (raw quality per dollar, mean across seeds)
- **q̄_T** = Σ q_t / T (full-horizon mean quality). †  marks ablations with any mid-run bankruptcy.
- **AdaptT** = trailing-200 ROI shock-response time (rounds). S2 ≥95% of pre-outage ROI; S3 ≥110% of pre-promotion ROI. ∞ if never reached.
- **n.r.** means the (ablation, scenario) combination was not run (e.g. -C_post is S3-only by design).

## S1 (stationary)

| Variant | PA-gap/T | ROI | q̄_T | AdaptT |
|---|---|---|---|---|
| Full PA-DCT | 0.133±0.004 | 378 | 0.797 | n/a |
| $-P$ | 0.855±0.058 | 111 | 0.555† | n/a |
| $-D$ | 0.109±0.008 | 412 | 0.810 | n/a |
| $-C$ | 0.116±0.003 | 390 | 0.812 | n/a |
| $-TS$ | 0.130±0.046 | 535 | 0.740 | n/a |
| $-C_{\mathrm{post}}$ | n.r. | n.r. | n.r. | n.r. |

## S2 (outage 3000-5500)

| Variant | PA-gap/T | ROI | q̄_T | AdaptT |
|---|---|---|---|---|
| Full PA-DCT | 0.166±0.006 | 357 | 0.761 | 1467 |
| $-P$ | 0.878±0.050 | 103 | 0.517† | 1611 |
| $-D$ | 0.170±0.012 | 399 | 0.745 | 2249 |
| $-C$ | 0.158±0.006 | 368 | 0.761 | 1176 |
| $-TS$ | 0.175±0.048 | 537 | 0.687 | 1125 |
| $-C_{\mathrm{post}}$ | n.r. | n.r. | n.r. | n.r. |

## S3 (promo at round 1000)

| Variant | PA-gap/T | ROI | q̄_T | AdaptT |
|---|---|---|---|---|
| Full PA-DCT | 0.121±0.004 | 429 | 0.831 | 200 |
| $-P$ | 0.259±0.036 | 351 | 0.840 | 200 |
| $-D$ | 0.114±0.009 | 426 | 0.838 | 279 |
| $-C$ | 0.109±0.003 | 425 | 0.848 | 398 |
| $-TS$ | 0.145±0.025 | 552 | 0.742 | 2232 |
| $-C_{\mathrm{post}}$ | 0.144±0.005 | 423 | 0.797 | 200 |

## AdaptT cross-scenario summary (Full + D/C/C_post focus)

| Scenario | Full | $-D$ | $-C$ | $-TS$ | $-C_{\mathrm{post}}$ |
|---|---|---|---|---|---|
| S2 | 1467 | 2249 | 1176 | 1125 | n.r. |
| S3 | 200 | 279 | 398 | 2232 | 200 |
