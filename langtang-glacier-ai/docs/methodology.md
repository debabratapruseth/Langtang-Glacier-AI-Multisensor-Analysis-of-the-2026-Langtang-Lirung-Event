# Phase 1--8 methodology

## Reproducible setup

Configuration is immutable and centralized in `src/config.py`. Earth Engine
authentication is interactive and explicit. Missing collections, missing GLIMS
outlines, and absent metrics raise readable errors; null pixel reductions become
missing values or an explicit `missing_data_flag`, not interpolated observations.

## Study area

The analysis first resolves later published GLIMS identifier `G085544E28246N`, then
the older inventory-vintage ID `G085547E28252N`, near the documented Lirung anchor.
If neither ID exists, it accepts only a uniquely named nearby `Lirung` boundary.
It then selects the newest available `src_date` and records the resolution method.
This guarded lookup reduces the risk of selecting a neighboring glacier in the dense
Langtang complex. Context buffers remain separate and are not catchments.

## Sentinel-2 processing

Scenes are filtered spatially, temporally, and with a permissive scene-level cloud
ceiling of 80%; pixel-level Cloud Score+ and SCL masks do the substantive filtering.
The retained reflectance bands are scaled by 10,000. NDSI is:

```text
NDSI = (B3 - B11) / (B3 + B11)
```

A configurable proxy marks pixels with NDSI >= 0.40 and green reflectance >= 0.10.
The green constraint reduces dark false positives but is not a universal classifier.
Annual medians use the same October--November post-monsoon window. The range starts
in 2017 because the selected Sentinel-2 surface-reflectance collection starts on
2017-03-28.

For every composite, the pipeline records scene count, mean valid-observation count,
valid ROI area fraction, NDSI mean, proxy snow area, and snow fraction over valid
pixels. A low valid-area fraction is a warning against comparison. Large gaps are
never interpolated.

## Validation before interpretation

Inspect representative RGB and NDSI layers, confirm the GLIMS outline follows the
intended glacier, review valid coverage, and test reasonable threshold sensitivity.
Area differences smaller than classification and geolocation uncertainty should not
be described as glacier change.

## ERA5-Land climate context

Daily ERA5-Land fields are spatially averaged over the 15 km context ROI at the
dataset's approximate 11.1 km grid scale. Extraction is batched by year and cached
as a real derived table in `data/processed/`. The pipeline reindexes to a complete
daily calendar but leaves absent values missing. Rolling 3-, 7-, and 30-day
precipitation totals require complete windows. Positive degree days sum
`max(Tmean, 0)` and a freeze–thaw day requires `Tmin <= 0 < Tmax`.

Daily temperature anomalies use month-day climatology. Monthly precipitation and
PDD standardized anomalies compare each calendar month with the same month during
the 1984–2025 baseline. The baseline excludes 2026 to avoid incorporating the event
year into its own reference distribution.

## Sentinel-1 comparable-track backscatter

Sentinel-1 GRD is filtered to IW mode, 10 m products, and dual VV/VH polarization.
Every orbit direction/relative-orbit candidate is assessed for usable glacier-ROI
coverage, temporal span, and incidence-angle consistency; both may instead be fixed
in configuration. All time-series and pre/post products use the same selection.
Approximate ellipsoid incidence angles outside 30–45 degrees and DEM-screened
shadow/layover geometry are masked. Monthly median composites reduce speckle, then VV
and VH means/standard deviations, coverage, incidence angle, scene count, and valid
observation count are measured inside the glacier ROI.

Differences are calculated in dB as post minus pre only for user-supplied verified
windows. They are screening layers, not displacement estimates. No phase or SLC
processing is performed, so the method is not InSAR.

## Integrated monthly feature store

Sentinel-2 is additionally composited by calendar month from April 2017 onward with
the same Cloud Score+, SCL, NDSI, and brightness rules used in Phase 3. Monthly
optical metrics retain scene counts, valid-area fractions, and valid-observation
counts. Months without usable pixels remain null. Reductions are evaluated one month
at a time and checkpointed after every successful request to respect Earth Engine's
concurrent-aggregation limit and permit resumable extraction.

ERA5-Land, Sentinel-2, and Sentinel-1 tables are joined to a complete monthly
calendar. No interpolation or forward filling is applied. Optical and SAR seasonal
anomalies subtract the historical mean for the same calendar month and require at
least three valid historical observations. The resulting table records separate
missing-data flags and the number of available core features for every month.

## Statistical trends and change points

Seasonally adjusted monthly variables are analyzed before machine learning. Linear
slopes use OLS with heteroskedasticity/autocorrelation-consistent standard errors up
to 12 lags. The original Mann–Kendall test and Sen's slope with a 95% interval provide
nonparametric comparisons. Results retain feature-specific sample counts and periods.

Pearson and Spearman correlations use pairwise-complete months and are accompanied by
pair counts. Positive lag in the lagged-correlation table means the proposed driver
precedes the response. Robust STL is restricted to complete consecutive monthly
series. PELT uses an L2 level-shift model, a minimum 12-month segment, and penalty
`3 * log(n)` on standardized values. Its dates are sensitivity-dependent candidates,
not confidence-scored physical events.

## Unsupervised anomaly detection and environmental regimes

Phase 8 derives same-calendar-month anomalies for climate, precipitation-window,
SAR-change, and optical features using only the pre-2026 reference period. The
primary model prefers climate with Sentinel-1 VV/VH changes. When those changes have
insufficient complete overlap, it uses VV/VH seasonal anomalies; if SAR is absent,
it records that condition and uses the complete climate feature set. A second,
separately reported multisensor model also requires optical snow-fraction,
snow-fraction change, and NDSI observations; it is skipped if fewer than the
configured minimum number of complete training months are available. Missing values
are never imputed.

Each feature is robustly standardized using its training median and median absolute
deviation, with IQR or standard deviation fallback only when necessary. Three
complementary unsupervised scores are fitted on pre-2026 complete cases: root-mean-
square robust distance, Isolation Forest decision score, and PCA reconstruction
error with enough components to explain at least 90% of training variance. Each raw
score is mapped to its empirical percentile in the training distribution. Their mean
is the ensemble `anomaly_score`; it is a relative screening statistic, not a
probability. The configured reference flag marks scores at or above the training
95th percentile.

Recurring environmental regimes are discovered from the primary standardized
features with K-means. Candidate cluster counts from 2 through 6 are compared by
training-period silhouette score. Cluster IDs are arbitrary and are not hazard
levels. PCA coordinates and loadings are retained for diagnostic visualization,
not causal attribution.

## Guarded event-relative analysis

Phase 9 remains disabled until the user supplies an event date, an authoritative
source citation, and explicit pre/post satellite windows. Earth Engine end dates are
exclusive. Validation requires the pre window to end no later than the event and the
post window to begin no earlier than the event. The verified metadata are saved with
the outputs.

For temporal context, the 12 complete calendar months preceding the event month are
compared with earlier observations from the same calendar month. The table and chart
show historical median, 25th–75th, and 5th–95th percentile ranges alongside the
event-relative observation. These are empirical reference ranges, not confidence
intervals. Missing values remain missing.

Sentinel-2 median composites use the existing Cloud Score+, SCL, NDSI, brightness,
and coverage workflow. Pre/post layers include RGB, NDSI, NDVI, snow proxy, and
post-minus-pre NDSI/NDVI. Sentinel-1 uses one orbit direction and relative orbit for
both periods. Because its acquisition dates need not overlap the optical windows,
the nearest same-track acquisitions strictly before and after the event are selected
within a 60-day search and their dates are recorded. The workflow maps post-minus-
pre VV/VH in dB. Reductions report sensor-specific quality fields inside the GLIMS
ROI. The wider context is visual only; no automatic event footprint or volume is
inferred. If no post-event same-track acquisition is yet available, the diagnostic
is recorded and the SAR comparison is skipped until the archive updates.

## Integrated reporting and conclusions

Phase 10 reads saved outputs without making Earth Engine requests. It inventories
expected products as available or pending, plots an aligned analytical timeline,
and generates evidence-linked responses to the seven research questions. Numerical
statements are derived from saved trend and anomaly tables. Missing tables produce a
pending statement rather than a substituted result.

The static HTML dashboard links charts, interactive maps, tables, event-source
metadata, and responsible-interpretation text using paths relative to `outputs/`.
The generated conclusions distinguish observed associations and screening results
from causal attribution, hazard probability, and prediction. Pending post-event SAR
remains visible as pending.

## V2 central quality control

V2 standardizes `valid_area_fraction`, observation and expected counts, period
completeness, complete-period status, quality category, and a human-readable reason.
The categories are `GOOD`, `CAUTION`, and `INSUFFICIENT`. Accumulated climate
variables are invalidated for incomplete months. Optical pre/post quantitative
differences require both periods to reach 0.80 valid-area coverage; otherwise the
workflow emits the prescribed insufficient-coverage statement and no change value.

The partial August 2026 record is compared with the identical available calendar-day
interval in each baseline year. Event-exclusive 1-, 3-, 7-, 14-, 30-, 60-, and
90-day antecedent windows likewise use matched historical calendar days and report
percentile, z-score, sample size, and completeness.

Sentinel-1 V2 QA enumerates every pass/orbit candidate and evaluates usable monthly
coverage, temporal span, incidence angles, and event availability. Selection uses
measured usable coverage and temporal consistency rather than raw scene count. Angle
sensitivity compares no extra mask, the fixed 30–45 degree mask, and a robust
data-derived range. Near-null time series fail explicitly. DEM-derived shadow and
layover screening is diagnostic; no InSAR or validated radiometric terrain
normalization claim is made.

Sentinel-2 sensitivity evaluates NDSI thresholds 0.30, 0.40, and 0.50 under coverage
filters 0.00, 0.60, 0.80, and 0.90. Every output remains labelled as a snow/clean-ice
spectral proxy rather than glacier area or mass.

Terrain context uses Copernicus GLO-30 for elevation, slope, aspect, and a discrete
curvature index. Hydrology uses MERIT Hydro direction, upstream area, HAND, and a
thresholded drainage network plus a HydroSHEDS level-12 basin. The original buffers
remain visual context only. Suspected source and debris-pathway ROIs remain unset
until externally validated geometry is supplied.
