# Scientific limitations

- A single reported event cannot support a collapse classifier, probability, or
  predictive claim. The current phase performs no event inference.
- Satellite/climate associations alone cannot identify a causal failure mechanism.
- The exact 2026 collapse time/mechanism remains unset pending an authoritative,
  citable source; pre/post windows are therefore not executed.
- GLIMS is an inventory with heterogeneous outline dates and methods. Its polygon is
  a spatial analysis mask, not a current glacier boundary.
- NDSI maps snow and clean ice imperfectly. It cannot reliably distinguish
  debris-covered ice from surrounding moraine/rock, so `snow_area_km2` is not total
  glacier area.
- Snow/cloud confusion, residual thin cloud, cloud shadow, topographic shadow, steep
  viewing geometry, and mixed pixels remain possible after masking.
- Sentinel-2 band resolutions differ; NDSI is effectively evaluated at B11's 20 m
  resolution. Short records and missing/cloudy observations limit trend inference.
- Changing acquisition density and masks can create apparent change. Coverage and
  observation-count fields must accompany every estimate.
- Thresholds are configurable assumptions, not locally calibrated truth. Field data
  and uncertainty/sensitivity analysis are needed for defensible area estimates.
- Copernicus GLO-30 is a DSM with an EGM2008 vertical datum and is not a 2026 terrain
  model. It cannot provide an event volume without valid co-registered DEM differencing.
- ERA5-Land is approximately 11.1 km and represents a model grid-cell/regional
  context, not exact conditions at a glacier face. Complex-terrain temperature,
  snowfall, rainfall, radiation, and runoff can be biased; there is also a recent-data
  lag. Future CHIRPS/GPM and SAR phases add their own mountain-precipitation,
  layover/shadow, incidence-angle, and ambiguous-backscatter limitations.
- Sparse ground observations and unobserved permafrost/englacial processes constrain
  physical interpretation. Anomaly detection will not establish predictive capability.
- Sentinel-1 GRD backscatter is sensitive to surface moisture, snow state, roughness,
  viewing geometry, and coverage. Himalayan layover, foreshortening, and radar shadow
  remain despite orthorectification. Earth Engine does not apply radiometric terrain
  flattening to this collection. Backscatter change is not surface displacement, and
  this project makes no InSAR claim because it does not process complex phase data.
- The integrated monthly table does not make all sensors temporally equivalent.
  ERA5-Land is a daily model product, Sentinel-1 sampling depends on a selected orbit,
  and Sentinel-2 may be absent for monsoon months. Joining by month does not remove
  these sampling differences. Missing optical/SAR values are intentionally retained.
- Trend tests are exploratory and repeated across multiple variables without claiming
  confirmatory significance. Original Mann–Kendall results can be influenced by
  serial correlation; OLS-HAC addresses covariance uncertainty but not model
  misspecification. PELT dates depend on penalty, minimum segment length, available
  record, and sensor sampling, and must not be interpreted as collapse precursors.
- Anomaly scores depend on the selected variables, seasonal adjustment, pre-2026
  training window, robust scaling, algorithms, and missing-data pattern. Their
  empirical percentiles are not probabilities, return periods, or calibrated hazard
  levels. A high score does not identify a cause or demonstrate predictive skill.
- The primary climate-SAR and sparse multisensor models use different complete-case
  month sets, so their scores are not directly interchangeable. Optical gaps can
  suppress or bias the multisensor comparison. K-means regime IDs and PCA axes are
  mathematical summaries whose labels, orientation, and selected cluster count can
  change with the input record; they are not physical states or hazard classes.
- When SAR changes or levels lack enough complete overlap, Phase 8 falls back to a
  climate-only primary model and records the selected strategy in its diagnostics.
  Such a result contains no radar evidence and must not be described as multisensor.
- Phase 9 depends on a user-supplied event citation and comparison windows. Window
  length, season, cloud/snow conditions, acquisition timing, and sensor coverage can
  dominate apparent pre/post differences. Historical percentile bands are empirical
  descriptions from a short record, not confidence intervals or event probabilities.
- Sentinel-1 uses the nearest available same-track acquisitions on either side of
  the event, which may not coincide with the optical windows or have equal temporal
  offsets. Surface and weather changes between those dates can affect the difference.
- Optical index differences and SAR backscatter differences are screening layers.
  They do not by themselves delineate a collapse scar, avalanche or debris footprint,
  channel change, or causal mechanism. No area or volume estimate is reported without
  a validated classification or co-registered DEM-difference methodology.
- The Phase 10 dashboard is a reporting layer over earlier outputs, not an independent
  validation. Automatically generated research-question statements inherit every
  sampling, model, and measurement limitation of their source tables. An available
  file indicates workflow completion, not scientific correctness or data quality.
- MERIT Hydro is about 90 m and documents unreliable flow direction over glaciers.
  HydroSHEDS/MERIT products provide regional hydrological context, not a validated
  avalanche pathway or event catchment at glacier-scale resolution.
- DEM-based radar shadow/layover masks are geometry diagnostics. A defensible
  radiometric terrain-normalization workflow requires local validation and is not
  represented as completed merely because a correction formula can be applied.
