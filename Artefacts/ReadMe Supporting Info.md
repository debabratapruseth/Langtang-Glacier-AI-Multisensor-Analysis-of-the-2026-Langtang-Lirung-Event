# Key Findings

The analysis provides evidence of unusually warm and melt-favourable conditions in the days and weeks preceding the event, while finding no similarly exceptional immediate rainfall anomaly.

### 1. Exceptionally warm pre-event conditions

Matched historical analysis shows that temperature and Positive Degree Day (PDD) conditions immediately before the event were unusually high relative to the 1984–2025 reference period.

Across several antecedent windows:

* 1-day temperature/PDD: ~100th historical percentile
* 3-day: ~100th percentile
* 7-day: ~100th percentile
* 14-day: ~98th percentile
* 30-day: ~93rd percentile
* 60-day: ~98th percentile

These results indicate a strongly melt-favourable thermal environment before the event.


### 2. No exceptional immediate rainfall signal

The same historical comparison did not identify extreme short-term precipitation immediately before the event.

Approximate precipitation percentiles were:

* 1 day: ~19th percentile
* 3 days: ~17th percentile
* 7 days: ~43rd percentile
* 14 days: ~60th percentile
* 30 days: ~69th percentile

The ERA5-Land evidence therefore does not support an exceptional immediate rainfall anomaly as a simple explanation for the event.


### 3. Increasing melt-favourable conditions

Long-term analysis identifies an increasing tendency in Positive Degree Days (PDD).

The result is supported across multiple statistical approaches, including:

* Sen’s slope
* OLS with HAC standard errors
* autocorrelation-adjusted Mann–Kendall analysis

This provides evidence of increasingly melt-favourable environmental conditions over the study period.


### 4. Sentinel-1 reveals long-term radar changes

The quality-controlled Sentinel-1 time series identifies statistically significant trends in both VV and VH backscatter.

These radar changes may reflect evolving surface properties such as snow state, wetness, roughness, ice exposure, or other surface characteristics.

They should not currently be interpreted as direct evidence of glacier instability or collapse susceptibility.


### 5. A valid Sentinel-1 pre/post-event pair was identified

The pipeline identifies a consistent Sentinel-1 acquisition geometry:

ASCENDING — Relative Orbit 85

with approximately 95.6% valid glacier coverage.

Event comparison:

* Pre-event acquisition: 16 August 2026
* Event: 26 August 2026
* Post-event acquisition: 28 August 2026

This provides a basis for spatial SAR change analysis in the next research phase.


### 6. Sentinel-2 event comparison fails quality control

Cloud obstruction severely limits post-event Sentinel-2 observations.

The post-event optical composite contains only approximately 2.3% valid glacier coverage.

The pipeline therefore automatically rejects quantitative Sentinel-2 pre/post change estimation.

This quality-control mechanism prevents cloud-related missing observations from being misinterpreted as physical glacier change.


### 7. AI did not detect a unique collapse precursor

The project uses an ensemble unsupervised anomaly framework combining:

* robust multivariate distance
* Isolation Forest
* PCA reconstruction error

The model is trained exclusively on observations before 2026.

After correcting for data completeness and integrating valid Sentinel-1 features, the model does not identify a uniquely extreme monthly environmental state immediately preceding the event.

This is an important negative result. The system should therefore be interpreted as an: environmental anomaly detection system

rather than a: glacier-collapse prediction model.
