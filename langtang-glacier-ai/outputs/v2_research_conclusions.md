# Langtang Lirung research conclusions

These statements are generated from the available outputs and are exploratory, not causal or predictive.

## RQ1: Long-term environmental change

Evidence grade: **EXPLORATORY**

Evidence type: **STATISTICAL ASSOCIATION**

Trend diagnostics are available for 7 features; their slopes and uncertainty must be interpreted with coverage and sensor limitations.

Evidence: `trend_summary.csv`

## RQ2: Climate, snow, and melt trends

Evidence grade: **EXPLORATORY**

Evidence type: **STATISTICAL ASSOCIATION**

6 exploratory Mann–Kendall results are flagged at 0.05 before any multiple-testing adjustment; consult trend_summary.csv for effect sizes and OLS-HAC uncertainty.

Evidence: `trend_summary.csv`

## RQ3: Pre-event seasonal anomalies

Evidence grade: **EXPLORATORY**

Evidence type: **OBSERVATION AND STATISTICAL ASSOCIATION**

0 of 11 scored pre-event months exceeded the configured reference threshold; the maximum ensemble score was 0.730. This is a relative anomaly screen, not probability.

Evidence: `anomaly_scores.csv`

## RQ4: Satellite-observed event-associated change

Evidence grade: **DATA INSUFFICIENT**

Evidence type: **OBSERVATION**

Sentinel-2 observations exist, but quantitative change was rejected by the optical coverage QA threshold. Same-track Sentinel-1 event metrics are also available.

Evidence: `Sentinel-2/Sentinel-1 event outputs`

## RQ5: Variables contributing to anomaly scores

Evidence grade: **EXPLORATORY**

Evidence type: **STATISTICAL ASSOCIATION**

The most frequent largest standardized contributor among flagged months was PDD_adjusted (4 months). Use PCA loadings and all standardized inputs; a largest contributor is not a physical cause.

Evidence: `anomaly_scores.csv; pca_loadings.csv`

## RQ6: Detectable precursory combination

Evidence grade: **UNSUPPORTED**

Evidence type: **HYPOTHESIS**

The unsupervised results can identify unusual combinations, but one event provides no test of precursor specificity, sensitivity, or predictive skill.

Evidence: `Integrated exploratory outputs`

## RQ7: What cannot be concluded

Evidence grade: **STRONG**

Evidence type: **UNSUPPORTED CAUSAL INTERPRETATION**

The workflow cannot establish collapse causation, calibrated hazard, predictive capability, displacement, event volume, or a validated debris footprint from these data alone.

Evidence: `docs/limitations.md`

## Pending products

- Feature provenance
- Matched August climate
- Antecedent climate windows
- Sentinel-1 angle sensitivity
- Sentinel-2 proxy sensitivity
- Optical candidate changes

See `docs/limitations.md` before scientific interpretation.