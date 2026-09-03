# Datasets

Datasets used in Phases 1--9 are listed. IDs link to their Earth Engine catalog
entries and were verified on 2026-09-02.

| Dataset | Provider / EE ID | Resolution and coverage | Variables used | Purpose | Known limitations |
|---|---|---|---|---|---|
| [GLIMS Current](https://developers.google.com/earth-engine/datasets/catalog/GLIMS_current) | GLIMS/NSIDC; `GLIMS/current` | Vector polygons; repeated observations; catalog snapshot through 2023-06-07 | `glac_id`, `src_date`, geometry | Inventory-based Lirung ROI | Outline dates and methods vary; repeated records; not a 2026 boundary |
| [Sentinel-2 MSI Level-2A Harmonized](https://developers.google.com/earth-engine/datasets/catalog/COPERNICUS_S2_SR_HARMONIZED) | EU/ESA/Copernicus; `COPERNICUS/S2_SR_HARMONIZED` | 10--60 m bands, nominal 5-day revisit, from 2017-03-28 | B2, B3, B4, B8, B11, SCL | Reflectance, RGB, NDSI, snow proxy | Clouds, shadows, steep-terrain illumination, mixed pixels, processing changes; B11 is 20 m |
| [Cloud Score+ S2 Harmonized V1](https://developers.google.com/earth-engine/datasets/catalog/GOOGLE_CLOUD_SCORE_PLUS_V1_S2_HARMONIZED) | Google Earth Engine; `GOOGLE/CLOUD_SCORE_PLUS/V1/S2_HARMONIZED` | 10 m QA, Sentinel-2 archive; operational/backfilled | `cs_cdf` | Per-pixel clear-surface score | Threshold is empirical; backfill/processing availability can vary |
| [Copernicus DEM GLO-30 2024_1](https://developers.google.com/earth-engine/datasets/catalog/COPERNICUS_DEM_GLO30_2024_1) | Copernicus; `COPERNICUS/DEM/GLO30_2024_1` | 30 m global DSM; source acquisitions 2010--2015/product metadata through 2020 | DEM | Elevation background | DSM, not bare-earth DTM; EGM2008 vertical datum; not contemporaneous with event |
| [ERA5-Land Daily Aggregated](https://developers.google.com/earth-engine/datasets/catalog/ECMWF_ERA5_LAND_DAILY_AGGR) | ECMWF/Copernicus CDS/Google; `ECMWF/ERA5_LAND/DAILY_AGGR` | Approx. 11,132 m pixels; daily from 1950 to roughly three months from real time | 2 m mean/min/max temperature, precipitation, snowfall, snow depth, downward solar radiation, runoff | Regional climate context, rolling precipitation, PDD, freeze–thaw, seasonal anomalies | Reanalysis grid-cell averages do not resolve glacier-face microclimate; mountain precipitation/topography biases; recent-data lag; accumulated-field artifacts |
| [Sentinel-1 SAR GRD](https://developers.google.com/earth-engine/datasets/catalog/COPERNICUS_S1_GRD) | EU/ESA/Copernicus; `COPERNICUS/S1_GRD` | 10/25/40 m products from 2014-10-03; revisit depends on track and mission availability | VV, VH, approximate ellipsoid incidence angle, orbit metadata | Monthly backscatter, representative maps, optional pre/post screening | Speckle; radar shadow, layover and foreshortening; incidence/track sensitivity; no radiometric terrain flattening; GRD has no usable interferometric phase |
| [MERIT Hydro v1.0.1](https://developers.google.com/earth-engine/datasets/catalog/MERIT_Hydro_v1_0_1) | University of Tokyo; `MERIT/Hydro/v1_0_1` | Approx. 92.77 m global hydrography | `elv`, `dir`, `upg`, `upa`, `hnd` | Flow direction/accumulation, upstream area, HAND, drainage-network context | Flow direction over glaciers is explicitly documented as unreliable; not event-contemporaneous; licensing conditions apply |
| [HydroSHEDS level-12 basins](https://developers.google.com/earth-engine/datasets/catalog/WWF_HydroSHEDS_v1_Basins_hybas_12) | WWF/partners; `WWF/HydroSHEDS/v1/Basins/hybas_12` | Global nested basin polygons | basin geometry, upstream area | Primary hydrological basin context replacing a buffer | Global delineation requiring local validation; basin containing an anchor can be ambiguous near divides |

Sentinel-2 SR values are divided by 10,000. Band B11 determines the effective 20 m
reduction scale for NDSI metrics.

ERA5-Land temperatures are converted from kelvin to degrees Celsius; precipitation,
snowfall water equivalent, and runoff from metres to millimetres; downward solar
radiation from J m-2 to MJ m-2. Small negative accumulated water values are clipped
to zero and must not be interpreted as measured zero precipitation.
