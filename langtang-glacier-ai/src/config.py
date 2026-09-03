"""Central configuration for the Langtang Lirung analysis."""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional


ROOT = Path(__file__).resolve().parents[1]


@dataclass(frozen=True)
class Settings:
    """Immutable, centralized settings used by the analysis workflows."""

    random_seed: int = 42
    ee_project: Optional[str] = None

    # Lirung Glacier IDs vary across inventory vintages as centroid positions move.
    glims_id: str = "G085544E28246N"
    glims_legacy_ids: tuple[str, ...] = ("G085547E28252N",)
    glacier_name: str = "Lirung Glacier"
    glacier_anchor_lon: float = 85.547
    glacier_anchor_lat: float = 28.252
    context_buffer_m: int = 15_000
    downstream_buffer_m: int = 25_000

    sentinel2_start: str = "2017-03-28"
    sentinel2_monthly_start: str = "2017-04-01"  # First complete SR month.
    sentinel2_end: str = "2027-01-01"  # Earth Engine filterDate end-exclusive.
    season_start_month: int = 10
    season_end_month: int = 11
    analysis_years: tuple[int, ...] = tuple(range(2017, 2027))
    representative_years: tuple[int, ...] = (2017, 2021, 2025)

    max_scene_cloud_percent: float = 80.0
    cloud_score_band: str = "cs_cdf"
    cloud_score_threshold: float = 0.60
    ndsi_snow_threshold: float = 0.40
    min_green_reflectance: float = 0.10
    reflectance_scale: float = 10_000.0
    reduction_scale_m: int = 20
    max_pixels: int = 100_000_000
    tile_scale: int = 4

    climate_start: str = "1984-01-01"
    climate_end: str = "2027-01-01"  # End-exclusive; availability lags real time.
    climate_baseline_start: str = "1984-01-01"
    climate_baseline_end: str = "2026-01-01"  # Excludes event year 2026.
    era5_scale_m: int = 11_132

    sentinel1_start: str = "2015-07-01"
    sentinel1_end: str = "2027-01-01"  # End-exclusive; archive may lag.
    sentinel1_orbit_pass: Optional[str] = None  # Select from candidate QA.
    sentinel1_relative_orbit: Optional[int] = None  # Select from candidate QA.
    sentinel1_angle_min_deg: float = 30.0
    sentinel1_angle_max_deg: float = 45.0
    sentinel1_reduction_scale_m: int = 30
    sentinel1_representative_years: tuple[int, ...] = (2017, 2021, 2025)

    anomaly_training_end: str = "2026-01-01"  # Excludes event year.
    anomaly_reference_quantile: float = 0.95
    anomaly_min_training_months: int = 36

    sentinel2_event_min_valid_area: float = 0.80
    sentinel1_min_valid_area: float = 0.50
    sentinel1_min_usable_months: int = 12
    quality_caution_completeness: float = 0.90

    # Documented provenance, separate from the execution gate below.
    documented_event_date: str = "2026-08-26"
    documented_event_source: str = (
        "https://www.esa.int/Applications/Observing_the_Earth/Copernicus/"
        "Sentinel-2/Nepal_flash_flood_imaged_by_satellites"
    )

    # Intentionally unset until supported by an authoritative event source.
    event_date: Optional[str] = None
    pre_event_start: str = "2025-09-01"
    pre_event_end: Optional[str] = None
    post_event_start: Optional[str] = None
    post_event_end: str = "2026-09-30"

    data_raw: Path = field(default=ROOT / "data" / "raw")
    data_processed: Path = field(default=ROOT / "data" / "processed")
    output_maps: Path = field(default=ROOT / "outputs" / "maps")
    output_charts: Path = field(default=ROOT / "outputs" / "charts")
    output_tables: Path = field(default=ROOT / "outputs" / "tables")
    output_qa: Path = field(default=ROOT / "outputs" / "qa")

    def validate(self) -> None:
        """Raise a useful error for inconsistent settings."""
        if not 1 <= self.season_start_month <= self.season_end_month <= 12:
            raise ValueError("Season months must be ordered integers in [1, 12].")
        if not 0 <= self.cloud_score_threshold <= 1:
            raise ValueError("cloud_score_threshold must be in [0, 1].")
        if not -1 <= self.ndsi_snow_threshold <= 1:
            raise ValueError("ndsi_snow_threshold must be in [-1, 1].")
        if self.sentinel1_orbit_pass not in (None, "ASCENDING", "DESCENDING"):
            raise ValueError("sentinel1_orbit_pass must be ASCENDING or DESCENDING.")
        if self.sentinel1_angle_min_deg >= self.sentinel1_angle_max_deg:
            raise ValueError("Sentinel-1 incidence-angle limits must be ordered.")
        if not 0 < self.anomaly_reference_quantile < 1:
            raise ValueError("anomaly_reference_quantile must be in (0, 1).")
        if self.anomaly_min_training_months < 24:
            raise ValueError("anomaly_min_training_months must be at least 24.")
        for name, value in (
            ("sentinel2_event_min_valid_area", self.sentinel2_event_min_valid_area),
            ("sentinel1_min_valid_area", self.sentinel1_min_valid_area),
            ("quality_caution_completeness", self.quality_caution_completeness),
        ):
            if not 0 <= value <= 1:
                raise ValueError(f"{name} must be in [0, 1].")
        if self.event_date is None and any(
            value is not None
            for value in (self.pre_event_end, self.post_event_start)
        ):
            raise ValueError("Event-relative dates require event_date to be set.")
        if not self.documented_event_date or not self.documented_event_source:
            raise ValueError("Documented event provenance may not be empty.")


SETTINGS = Settings()
