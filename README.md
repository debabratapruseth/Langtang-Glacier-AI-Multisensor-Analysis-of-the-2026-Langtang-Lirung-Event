# Multisensor Environmental Analysis of the 2026 Langtang Lirung Glacier Collapse

An open-source research prototype combining satellite Earth observation, climate data, statistical analysis, and unsupervised AI to investigate environmental conditions surrounding the August 2026 Langtang Lirung event in Nepal/Tibet.

The project integrates Sentinel-1 SAR, Sentinel-2 optical imagery, ERA5-Land climate data, glacier boundaries, and terrain information using Google Earth Engine and Python.

    This is an experimental AI pipeline that combines multi-satellite and climate data, 
    transforms it into time-series features, 
    and uses statistical analysis and AI-based anomaly detection to look for unusual environmental patterns.

    The longer-term idea is to build an AI framework where you can point it at any glacier, 
    ingest its historical satellite + climate data, 
    and automatically investigate changes and anomalies over time.

Research objective: 

``` Can open satellite, climate, and AI-based analytical methods identify long term environmental changes, short-term anomalies, and observable surface changes surrounding a major glacier–rock slope event? ```


## Sample Outputs

![Glacier](https://github.com/debabratapruseth/Langtang-Glacier-AI-Multisensor-Analysis-of-the-2026-Langtang-Lirung-Event/blob/main/Artefacts/Glacier%20Analysis.png)

![](https://github.com/debabratapruseth/Langtang-Glacier-AI-Multisensor-Analysis-of-the-2026-Langtang-Lirung-Event/blob/main/Artefacts/pre_event_historical_percentiles.png)

![Anomaly Score Timeseries](https://github.com/debabratapruseth/Langtang-Glacier-AI-Multisensor-Analysis-of-the-2026-Langtang-Lirung-Event/blob/main/Artefacts/anomaly_score_timeseries.png)

![](https://github.com/debabratapruseth/Langtang-Glacier-AI-Multisensor-Analysis-of-the-2026-Langtang-Lirung-Event/blob/main/Artefacts/integrated_event_timeline.png)


## Key Findings

Our multisensor analysis of the 2026 Langtang Lirung event produced several notable findings:

* Exceptionally warm before the event: Temperature and Positive Degree Days (PDD) reached approximately the 93rd–100th historical percentiles across several 1–60 day pre-event windows.
* No extreme rainfall signal: Immediate pre-event precipitation was not exceptionally high, suggesting there was no simple extreme-rainfall signal in the ERA5-Land data.
* Increasing melt-favourable conditions: Long-term analysis shows an increasing PDD tendency, supported by multiple statistical methods.
* Long-term radar changes detected: Sentinel-1 shows statistically significant changes in VV and VH backscatter, indicating evolving surface characteristics whose physical causes require further investigation.
* Good SAR observations around the event: A consistent Sentinel-1 pre/post pair was identified for 16 Aug → 28 Aug 2026, with ~95.6% valid glacier coverage.
* Optical data were limited: Post-event Sentinel-2 coverage was only ~2.3% due to cloud, so the pipeline correctly rejected quantitative optical change estimates.
* AI found no unique collapse precursor: Unsupervised anomaly detection did not identify a uniquely extreme monthly state immediately before the event.

[Read the detailed finding and analysis ](https://github.com/debabratapruseth/Langtang-Glacier-AI-Multisensor-Analysis-of-the-2026-Langtang-Lirung-Event/blob/main/Artefacts/ReadMe%20Supporting%20Info.md)



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

[Read the detailed finding and analysis ](https://github.com/debabratapruseth/Langtang-Glacier-AI-Multisensor-Analysis-of-the-2026-Langtang-Lirung-Event/blob/main/Artefacts/ReadMe%20Supporting%20Info.md)

The project investigates five research questions using climate records, multisensor satellite observations, statistical analysis, and unsupervised AI.

### RQ1 — Long-term environmental change

Question:
Are statistically detectable changes present in temperature, melt-favourable conditions, optical snow characteristics, or radar backscatter around Langtang Lirung?

Finding: YES — but the strength of evidence differs by variable.

Conclusion: 🟢 Evidence of long-term environmental change is present, with the strongest current evidence coming from increasing PDD and changing Sentinel-1 backscatter.



### RQ2 — Pre-event environmental conditions

Question:
Were conditions during the days, weeks, or months preceding 26 August 2026 unusual relative to the historical record?

Finding: YES — particularly for temperature and melt-favourable conditions.

Conclusion: 🟢 The event was preceded by an unusually warm and strongly melt-favourable period, but not by an exceptional immediate rainfall anomaly in the ERA5-Land data.

This represents environmental context and does not establish that the thermal conditions caused the collapse.



### RQ3 — AI anomaly detection

Question:
Can unsupervised multivariate analysis identify an unusual environmental state preceding the event?

Finding: PARTIALLY — but no unique collapse precursor was detected.

Conclusion: 🟡 AI can identify unusual environmental states, but the current model does not provide evidence of a unique AI-detectable precursor to the collapse.

The anomaly score should therefore not be interpreted as a collapse probability or early-warning signal.



### RQ4 — Satellite event evidence

Question:
Can Sentinel-1 and Sentinel-2 observations identify measurable surface changes across the event window?

Finding: PARTIALLY.

Conclusion: 🟡 Sentinel-1 provides usable event-window observations and exploratory evidence for spatial change analysis. Sentinel-2 post-event data are currently insufficient for quantitative event-change measurement.

A validated physical collapse footprint has not yet been demonstrated.



### RQ5 — Environmental conditioning

Question:
What can the combined evidence tell us about environmental conditioning while remaining distinct from causal attribution or event prediction?

Finding: The combined evidence supports environmental conditioning as a research hypothesis — not causal attribution.

Conclusion: 🟢 The evidence supports environmental-state monitoring and a hypothesis of thermal/melt conditioning, but it does not establish why the slope failed on 26 August 2026, prove that climate caused the event, or demonstrate that the collapse could have been predicted.



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

Research Prototype — V1

The project is under active development. Findings may be revised as additional satellite observations, event geometry, validation data, and improved physical modelling become available.
