# Multisensor Environmental Analysis of the 2026 Langtang Lirung Glacier–Rock Slope Collapse

An open-source research prototype combining satellite Earth observation, climate data, statistical analysis, and unsupervised AI to investigate environmental conditions surrounding the August 2026 Langtang Lirung event in Nepal.

The project integrates Sentinel-1 SAR, Sentinel-2 optical imagery, ERA5-Land climate data, glacier boundaries, and terrain information using Google Earth Engine and Python.

    Research objective: Can open satellite, climate, and AI-based analytical methods identify long term environmental changes, short-term anomalies, and observable surface changes surrounding a major glacier–rock slope event?


## Sample Outputs

![Glacier](https://github.com/debabratapruseth/Langtang-Glacier-AI-Multisensor-Analysis-of-the-2026-Langtang-Lirung-Event/blob/main/Artefacts/Glacier%20Analysis.png)

![](https://github.com/debabratapruseth/Langtang-Glacier-AI-Multisensor-Analysis-of-the-2026-Langtang-Lirung-Event/blob/main/Artefacts/pre_event_historical_percentiles.png)

![Anomaly Score Timeseries](https://github.com/debabratapruseth/Langtang-Glacier-AI-Multisensor-Analysis-of-the-2026-Langtang-Lirung-Event/blob/main/Artefacts/anomaly_score_timeseries.png)

![](https://github.com/debabratapruseth/Langtang-Glacier-AI-Multisensor-Analysis-of-the-2026-Langtang-Lirung-Event/blob/main/Artefacts/integrated_event_timeline.png)



## Key Findings

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

⸻

### 2. No exceptional immediate rainfall signal

The same historical comparison did not identify extreme short-term precipitation immediately before the event.

Approximate precipitation percentiles were:

* 1 day: ~19th percentile
* 3 days: ~17th percentile
* 7 days: ~43rd percentile
* 14 days: ~60th percentile
* 30 days: ~69th percentile

The ERA5-Land evidence therefore does not support an exceptional immediate rainfall anomaly as a simple explanation for the event.

⸻

### 3. Increasing melt-favourable conditions

Long-term analysis identifies an increasing tendency in Positive Degree Days (PDD).

The result is supported across multiple statistical approaches, including:

* Sen’s slope
* OLS with HAC standard errors
* autocorrelation-adjusted Mann–Kendall analysis

This provides evidence of increasingly melt-favourable environmental conditions over the study period.

⸻

### 4. Sentinel-1 reveals long-term radar changes

The quality-controlled Sentinel-1 time series identifies statistically significant trends in both VV and VH backscatter.

These radar changes may reflect evolving surface properties such as snow state, wetness, roughness, ice exposure, or other surface characteristics.

They should not currently be interpreted as direct evidence of glacier instability or collapse susceptibility.

⸻

### 5. A valid Sentinel-1 pre/post-event pair was identified

The pipeline identifies a consistent Sentinel-1 acquisition geometry:

ASCENDING — Relative Orbit 85

with approximately 95.6% valid glacier coverage.

Event comparison:

* Pre-event acquisition: 16 August 2026
* Event: 26 August 2026
* Post-event acquisition: 28 August 2026

This provides a basis for spatial SAR change analysis in the next research phase.

⸻

### 6. Sentinel-2 event comparison fails quality control

Cloud obstruction severely limits post-event Sentinel-2 observations.

The post-event optical composite contains only approximately 2.3% valid glacier coverage.

The pipeline therefore automatically rejects quantitative Sentinel-2 pre/post change estimation.

This quality-control mechanism prevents cloud-related missing observations from being misinterpreted as physical glacier change.

⸻

### 7. AI did not detect a unique collapse precursor

The project uses an ensemble unsupervised anomaly framework combining:

* robust multivariate distance
* Isolation Forest
* PCA reconstruction error

The model is trained exclusively on observations before 2026.

After correcting for data completeness and integrating valid Sentinel-1 features, the model does not identify a uniquely extreme monthly environmental state immediately preceding the event.

This is an important negative result. The system should therefore be interpreted as an: environmental anomaly detection system

rather than a: glacier-collapse prediction model.



## Why AI?

The role of AI in this project is not to predict glacier collapse from a single historical event.

Instead, unsupervised learning asks:

How unusual is the current combination of environmental conditions compared with historical environmental states?

The analytical workflow is:

  Climate + Satellite + Terrain
  ↓
  Quality Control
  ↓
  Feature Engineering
  ↓
  Trend & Statistical Analysis
  ↓
  Unsupervised Anomaly Detection
  ↓
  Environmental State Assessment
  ↓
  Evidence Synthesis

This allows unusual combinations of climate and satellite observations to be investigated without requiring labelled collapse-training data.



## Data Sources

### Sentinel-2

Used for optical analysis of:

* NDSI
* snow/clean-ice spectral proxy
* seasonal variability
* pre/post-event optical screening

Cloud Score+ and Sentinel-2 Scene Classification Layer masking are used for quality control.

Important: NDSI-derived snow fraction is a spectral snow/clean-ice proxy. It is not equivalent to total glacier area, glacier volume, or glacier mass balance.

⸻

### Sentinel-1 SAR

Used for:

* VV backscatter
* VH backscatter
* long-term radar time series
* radar change metrics
* event-window screening

Candidate orbit geometries are evaluated using actual ROI coverage rather than scene count alone.

The current workflow selects:

ASCENDING / Relative Orbit 85

for the primary Langtang Lirung analysis.

The analysis uses Sentinel-1 GRD backscatter and is not InSAR displacement analysis.

⸻

### ERA5-Land

Used for:

* temperature
* precipitation
* Positive Degree Days
* snowfall
* runoff
* solar radiation
* freeze-thaw metrics
* antecedent environmental windows

Historical baseline:

1984–2025

The event year is excluded from the historical baseline.

⸻

### Glacier Geometry

The glacier ROI is resolved using GLIMS glacier inventory information.

The workflow avoids silently substituting manually drawn glacier polygons when authoritative geometry is expected.

⸻

### Terrain and Hydrology

DEM and hydrological information provide context including:

* elevation
* slope
* aspect
* terrain characteristics
* basin/catchment context

These layers are intended to support future physical-event and runout analysis.

⸻

## Quality-Aware Scientific AI

A central principle of this project is:

Data quality must be evaluated before statistical or AI analysis.

Each observation can carry information such as:

* valid area fraction
* observation count
* expected observations
* period completeness
* quality status
* quality reason

This prevents incomplete observations from silently influencing downstream models.

Example: incomplete August climate data

Instead of comparing a partial August 2026 month with complete historical August months, the pipeline performs matched-period comparisons:

1–24 August 2026

versus:

1–24 August for each historical baseline year

This prevents incomplete monthly accumulations from producing artificial anomalies.

Example: cloudy Sentinel-2 imagery

If pre/post-event optical coverage fails the configured quality threshold, quantitative change estimation is suppressed.

This prevents cloud-obscured pixels from being interpreted as glacier loss.


## Statistical Methods

The repository includes:

Trend analysis

* OLS regression
* HAC/Newey-West standard errors
* Sen’s slope
* Mann–Kendall trend test
* modified Mann–Kendall analysis

Association analysis

* Pearson correlation
* Spearman correlation
* lagged correlation
* false-discovery-rate correction
* multivariate regression

Unsupervised AI

* Isolation Forest
* robust multivariate distance
* PCA reconstruction error
* environmental regime clustering

Dimensionality analysis

* Principal Component Analysis
* feature loading analysis
* environmental regime visualization

⸻

## Repository Structure

    langtang-glacier-ai/
    │
    ├── notebooks/
    │   ├── 01_setup_and_roi.ipynb
    │   ├── 02_sentinel2_glacier_analysis.ipynb
    │   ├── 03_sentinel2_visual_comparison.ipynb
    │   ├── 04_climate_weather_analysis.ipynb
    │   ├── 05_sentinel1_sar_change.ipynb
    │   ├── 06_feature_engineering.ipynb
    │   ├── 07_trend_analysis.ipynb
    │   ├── 08_anomaly_detection.ipynb
    │   ├── 09_event_pre_post_analysis.ipynb
    │   └── 10_integrated_dashboard_and_conclusions.ipynb
    │
    ├── src/
    │   ├── config.py
    │   ├── gee_utils.py
    │   ├── glacier_features.py
    │   ├── climate_features.py
    │   ├── sar_features.py
    │   ├── feature_engineering.py
    │   ├── trend_analysis.py
    │   ├── anomaly_detection.py
    │   ├── event_analysis.py
    │   ├── visualization.py
    │   ├── reporting.py
    │   └── utils.py
    │
    ├── data/
    │   └── processed/
    │
    ├── outputs/
    │   ├── charts/
    │   ├── maps/
    │   ├── tables/
    │   └── qa/
    │
    ├── docs/
    │   ├── datasets.md
    │   ├── methodology.md
    │   └── limitations.md
    │
    ├── tests/
    ├── requirements.txt
    ├── LICENSE
    └── README.md



## Running the Project

### Google Earth Engine

Satellite-data extraction requires access to Google Earth Engine.

Authenticate Earth Engine using the authentication method appropriate for your environment and configure the required Earth Engine project before executing the online notebooks.

### Run the notebooks

We have used GDrive to store the files and Google Colab to run the code. You can use your local drive and IDE of choice. The /notebooks are designed to be executed sequentially:

01 → ROI
02–03 → Sentinel-2
04 → Climate
05 → Sentinel-1
06 → Feature Engineering
07 → Statistics
08 → AI / Anomaly Detection
09 → Event Analysis
10 → Integrated Results

Some tests and analyses can operate using previously generated local outputs without reconnecting to Earth Engine.



## Research Questions & Findings

The project investigates five research questions using climate records, multisensor satellite observations, statistical analysis, and unsupervised AI.

### RQ1 — Long-term environmental change

Question:
Are statistically detectable changes present in temperature, melt-favourable conditions, optical snow characteristics, or radar backscatter around Langtang Lirung?

Finding: YES — but the strength of evidence differs by variable.

The analysis finds evidence of increasingly melt-favourable conditions, with Positive Degree Days (PDD) showing an increasing tendency supported by Sen’s slope, OLS with HAC standard errors, and autocorrelation-adjusted Mann–Kendall analysis.

Sentinel-1 also shows statistically significant long-term changes in VV and VH radar backscatter. These changes indicate evolving radar-observed surface characteristics, although their physical cause cannot yet be uniquely attributed to ice loss, surface wetness, snow conditions, roughness, or glacier instability.

Temperature shows an upward tendency, but its statistical significance becomes weaker after accounting for temporal autocorrelation.

Sentinel-2 snow/clean-ice spectral indicators also show changes, but the trend depends on how seasonality and observation windows are treated and should not be interpreted as direct glacier-area or mass loss.

Conclusion: 🟢 Evidence of long-term environmental change is present, with the strongest current evidence coming from increasing PDD and changing Sentinel-1 backscatter.

⸻

### RQ2 — Pre-event environmental conditions

Question:
Were conditions during the days, weeks, or months preceding 26 August 2026 unusual relative to the historical record?

Finding: YES — particularly for temperature and melt-favourable conditions.

Matched historical analysis comparing identical calendar periods shows exceptionally warm conditions before the event.

Temperature and PDD reached approximately:

* 100th percentile over the preceding 1-day window
* 100th percentile over 3 days
* 100th percentile over 7 days
* ~98th percentile over 14 days
* ~93rd percentile over 30 days
* ~98th percentile over 60 days

In contrast, short-term precipitation was not exceptionally high. Precipitation over the 1-, 3-, 7-, 14- and 30-day antecedent windows remained broadly within the historical distribution.

Conclusion: 🟢 The event was preceded by an unusually warm and strongly melt-favourable period, but not by an exceptional immediate rainfall anomaly in the ERA5-Land data.

This represents environmental context and does not establish that the thermal conditions caused the collapse.

⸻

### RQ3 — AI anomaly detection

Question:
Can unsupervised multivariate analysis identify an unusual environmental state preceding the event?

Finding: PARTIALLY — but no unique collapse precursor was detected.

The project combines climate and Sentinel-1 features using an ensemble anomaly-detection approach based on:

* robust multivariate distance
* Isolation Forest
* PCA reconstruction error

The model identifies unusual environmental states elsewhere in the historical record and highlights changing combinations of climate and radar conditions.

However, after correcting incomplete-period bias and applying the data-quality controls, the model does not identify a uniquely extreme monthly anomaly immediately preceding the August 2026 event.

This is an important result.

The strongest pre-event signals appear at shorter days-to-weeks timescales, particularly in temperature and PDD, rather than as a unique monthly multivariate anomaly.

Conclusion: 🟡 AI can identify unusual environmental states, but the current model does not provide evidence of a unique AI-detectable precursor to the collapse.

The anomaly score should therefore not be interpreted as a collapse probability or early-warning signal.

⸻

### RQ4 — Satellite event evidence

Question:
Can Sentinel-1 and Sentinel-2 observations identify measurable surface changes across the event window?

Finding: PARTIALLY.

Sentinel-1 SAR

A quality-controlled same-geometry Sentinel-1 pair was identified:

* Pre-event: 16 August 2026
* Event: 26 August 2026
* Post-event: 28 August 2026
* Geometry: ASCENDING / Relative Orbit 85
* Valid glacier coverage: ~95.6%

This provides a credible basis for examining radar-observed surface change around the event.

Whole-glacier mean VV/VH changes are relatively small, however, and a spatially validated collapse footprint has not yet been established.

Further spatial SAR change analysis is therefore required.

Sentinel-2 Optical

Sentinel-2 provides adequate pre-event imagery but only approximately 2.3% valid post-event glacier coverage, primarily because of cloud obstruction.

The pipeline therefore automatically rejects quantitative optical pre/post change estimation rather than interpreting missing/cloud-covered pixels as physical change.

Conclusion: 🟡 Sentinel-1 provides usable event-window observations and exploratory evidence for spatial change analysis. Sentinel-2 post-event data are currently insufficient for quantitative event-change measurement.

A validated physical collapse footprint has not yet been demonstrated.

⸻

### RQ5 — Environmental conditioning

Question:
What can the combined evidence tell us about environmental conditioning while remaining distinct from causal attribution or event prediction?

Finding: The combined evidence supports environmental conditioning as a research hypothesis — not causal attribution.

The observations collectively indicate:

* increasingly melt-favourable PDD conditions over the study period
* statistically significant long-term Sentinel-1 backscatter changes
* exceptionally warm and high-PDD conditions during several days-to-weeks windows immediately before the event
* no corresponding exceptional short-term rainfall anomaly
* no unique monthly AI anomaly capable of distinguishing the event from other unusual environmental periods
* a valid Sentinel-1 pre/post-event observation pair, but no independently validated physical failure footprint yet

Together, these observations are consistent with the possibility that the glacier–rock slope system experienced significant environmental conditioning before the event.

However, the analysis does not contain sufficient information about rock mechanics, slope deformation, fractures, permafrost, ice thickness, glacier velocity, subglacial hydrology, or other mechanical processes to determine the physical failure mechanism.

Conclusion: 🟢 The evidence supports environmental-state monitoring and a hypothesis of thermal/melt conditioning, but it does not establish why the slope failed on 26 August 2026, prove that climate caused the event, or demonstrate that the collapse could have been predicted.

⸻

## Overall Research Outcome

The central result of this research is therefore:

  The 26 August 2026 Langtang Lirung event occurred following an exceptionally warm and melt-favourable period, against a longer-term background of increasing Positive Degree Day conditions and changing radar backscatter characteristics. Immediate antecedent precipitation was not exceptionally high in the ERA5-Land record, and unsupervised AI did not identify a unique monthly collapse precursor. The combined evidence is consistent with environmental conditioning but does not establish the physical trigger, causal mechanism, or predictive capability.

The project therefore demonstrates the potential of:

Satellite Earth Observation + Climate Data + Statistical Analysis + Unsupervised AI

for reconstructing and monitoring glacier environmental states — while also demonstrating why anomaly detection should not automatically be interpreted as event prediction.

⸻

## Scientific Limitations

This repository is an exploratory research prototype.

It does not establish:

* the physical trigger of the collapse
* causal attribution to climate change
* glacier-collapse probability
* validated hazard probability
* glacier displacement
* event volume
* validated debris/runout footprint
* predictive capability

ERA5-Land represents regional gridded atmospheric conditions and should not be interpreted as an in-situ meteorological station at the failure location.

Sentinel-2 snow metrics represent spectral snow/clean-ice characteristics and are not measurements of total glacier mass.

Sentinel-1 backscatter changes may result from multiple physical processes and should not be interpreted as displacement without appropriate interferometric analysis.

The current event analysis does not yet contain an independently validated failure/runout footprint.



## Future Research

The next research phase will focus on:

* spatial Sentinel-1 event-change detection
* source/failure-zone analysis
* avalanche/debris runout geometry
* control-region comparisons
* higher-frequency rolling environmental anomaly detection
* terrain-linked SAR change
* glacier surface velocity
* permafrost and rock-slope susceptibility
* hydrological cascade analysis

The longer-term research direction is an:

AI-enabled Glacier Hazard Digital Twin

integrating:

  Climate → Cryosphere → Slope Condition → Event Detection → Runout → Downstream Risk


## Responsible Use

This repository is intended for:

* research
* education
* Earth-observation experimentation
* climate and cryosphere analytics
* scientific-method development

It should not be used as an operational early-warning, emergency-management, or hazard-prediction system.



## Citation

If you use this repository in research or derivative work, please cite the repository.

A formal research-paper citation and DOI will be added if/when the accompanying study is published.



## Status

Research Prototype — V2

The project is under active development. Findings may be revised as additional satellite observations, event geometry, validation data, and improved physical modelling become available.
