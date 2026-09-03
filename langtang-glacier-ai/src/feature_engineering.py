"""Integration of real monthly optical, SAR, and climate feature tables."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from .config import SETTINGS, Settings
from .quality import feature_provenance_table, validate_no_future_dates


FEATURE_PROVENANCE = {
    "temp_change": {
        "source": "ERA5-Land", "operation": "monthly difference", "units": "degC",
    },
    "PDD_change": {
        "source": "ERA5-Land", "operation": "monthly difference", "units": "degC day",
    },
    "snow_fraction_change": {
        "source": "Sentinel-2", "operation": "monthly difference", "units": "fraction",
    },
    "NDSI_change": {
        "source": "Sentinel-2", "operation": "monthly difference", "units": "index",
    },
    "antecedent_precipitation_index": {
        "source": "ERA5-Land", "operation": "API decay=0.85", "units": "mm",
    },
    "freeze_thaw_cycles": {
        "source": "ERA5-Land",
        "operation": "monthly sum of Tmin <= 0 < Tmax days",
        "units": "days",
    },
    "environmental_transition_magnitude": {
        "source": "multisensor",
        "operation": "RMS robust standardized monthly changes",
        "units": "relative",
    },
}


CLIMATE_RENAME = {
    "temp_mean_c": "temp_mean",
    "temp_max_c": "temp_max",
    "temp_min_c": "temp_min",
    "temp_anomaly_c": "temp_anomaly",
    "precip_month_mm": "precip_month",
    "precip_1d_max_mm": "precip_1d_max",
    "precip_3d_max_mm": "precip_3d_max",
    "precip_7d_max_mm": "precip_7d_max",
    "precip_30d_max_mm": "precip_30d_max",
    "precip_anomaly_z": "precip_anomaly",
    "pdd": "PDD",
    "expected_observation_count": "climate_expected_observation_count",
    "period_completeness": "climate_period_completeness",
    "is_complete_period": "climate_is_complete_period",
    "quality_status": "climate_quality_status",
    "quality_reason": "climate_quality_reason",
}

OPTICAL_RENAME = {
    "ndsi_mean": "NDSI",
    "snow_fraction_valid": "snow_fraction",
    "snow_area_km2": "snow_area_proxy_km2",
    "scene_count": "sentinel2_scene_count",
    "valid_area_fraction": "sentinel2_valid_area_fraction",
    "mean_valid_observation_count": "sentinel2_observation_count",
    "missing_data_flag": "sentinel2_missing_data_flag",
    "expected_observation_count": "sentinel2_expected_observation_count",
    "period_completeness": "sentinel2_period_completeness",
    "is_complete_period": "sentinel2_is_complete_period",
    "quality_status": "sentinel2_quality_status",
    "quality_reason": "sentinel2_quality_reason",
}

SAR_RENAME = {
    "vv_db": "VV",
    "vh_db": "VH",
    "vv_change_db": "VV_change",
    "vh_change_db": "VH_change",
    "scene_count": "sentinel1_scene_count",
    "valid_area_fraction": "sentinel1_valid_area_fraction",
    "mean_valid_observation_count": "sentinel1_observation_count",
    "missing_data_flag": "sentinel1_missing_data_flag",
    "expected_observation_count": "sentinel1_expected_observation_count",
    "period_completeness": "sentinel1_period_completeness",
    "is_complete_period": "sentinel1_is_complete_period",
    "quality_status": "sentinel1_quality_status",
    "quality_reason": "sentinel1_quality_reason",
}


def _read_monthly_table(path: Path, label: str) -> pd.DataFrame:
    """Read and validate one cached monthly table."""
    if not path.is_file():
        raise FileNotFoundError(
            f"Missing {label} table: {path}. Run its source notebook first."
        )
    frame = pd.read_csv(path, parse_dates=["date"])
    if frame.empty:
        raise ValueError(f"The {label} table is empty: {path}")
    frame["date"] = pd.to_datetime(frame["date"]).dt.to_period("M").dt.to_timestamp()
    count_columns = [
        column
        for column in ("observation_count", "scene_count")
        if column in frame
    ]
    if count_columns:
        observed = frame[count_columns].apply(
            pd.to_numeric, errors="coerce"
        ).fillna(0).gt(0).any(axis=1)
    else:
        observed = frame.drop(columns="date").notna().any(axis=1)
    validate_no_future_dates(frame.loc[observed, "date"])
    if frame["date"].duplicated().any():
        duplicates = frame.loc[frame["date"].duplicated(), "date"].tolist()
        raise ValueError(f"Duplicate months in {label} table: {duplicates[:5]}")
    return frame.sort_values("date")


def _seasonal_anomaly(
    frame: pd.DataFrame,
    column: str,
    baseline_end: str,
    minimum_count: int = 3,
) -> pd.Series:
    """Subtract calendar-month climatology without filling missing observations."""
    valid_baseline = frame.loc[
        (frame["date"] < pd.Timestamp(baseline_end)) & frame[column].notna(),
        ["date", column],
    ].copy()
    valid_baseline["month"] = valid_baseline["date"].dt.month
    grouped = valid_baseline.groupby("month")[column]
    climatology = grouped.mean()
    counts = grouped.count()
    climatology = climatology.where(counts >= minimum_count)
    return frame[column] - frame["date"].dt.month.map(climatology)


def build_integrated_monthly_features(
    climate_path: Path,
    optical_path: Path,
    sar_path: Path,
    settings: Settings = SETTINGS,
) -> pd.DataFrame:
    """Merge monthly sources and derive seasonal anomalies with no interpolation."""
    climate = _read_monthly_table(climate_path, "ERA5-Land climate").rename(
        columns=CLIMATE_RENAME
    )
    optical = _read_monthly_table(optical_path, "Sentinel-2 optical").rename(
        columns=OPTICAL_RENAME
    )
    sar = _read_monthly_table(sar_path, "Sentinel-1 SAR").rename(
        columns=SAR_RENAME
    )

    start = min(optical["date"].min(), sar["date"].min())
    observed_dates = [
        climate.loc[climate["temp_mean"].notna(), "date"].max(),
        optical.loc[optical["NDSI"].notna(), "date"].max(),
        sar.loc[sar["VV"].notna(), "date"].max(),
    ]
    observed_dates = [date for date in observed_dates if pd.notna(date)]
    if not observed_dates:
        raise ValueError("No valid climate, optical, or SAR observations were found.")
    observed_max = max(observed_dates)
    calendar = pd.DataFrame(
        {"date": pd.date_range(start, observed_max, freq="MS")}
    )
    integrated = calendar.merge(climate, on="date", how="left", suffixes=("", "_climate"))
    integrated = integrated.merge(
        optical, on="date", how="left", suffixes=("", "_optical")
    )
    integrated = integrated.merge(
        sar, on="date", how="left", suffixes=("", "_sar")
    )

    # Retain QA metadata but prevent failed sensor periods from entering derived
    # statistics or unsupervised models as if they were valid observations.
    if "climate_is_complete_period" in integrated:
        climate_ok = integrated["climate_is_complete_period"].fillna(False).astype(bool)
        climate_values = [
            column for column in CLIMATE_RENAME.values()
            if column in integrated and not column.startswith("climate_")
        ]
        integrated.loc[~climate_ok, climate_values] = np.nan
    if "sentinel2_quality_status" in integrated:
        optical_ok = integrated["sentinel2_quality_status"].eq("GOOD")
        optical_values = [
            "NDSI", "snow_fraction", "snow_area_proxy_km2",
        ]
        integrated.loc[~optical_ok, optical_values] = np.nan
    if "sentinel1_quality_status" in integrated:
        sar_ok = integrated["sentinel1_quality_status"].eq("GOOD")
        sar_values = ["VV", "VH", "VV_change", "VH_change", "angle_deg"]
        integrated.loc[~sar_ok, [c for c in sar_values if c in integrated]] = np.nan

    integrated["snow_fraction_anomaly"] = _seasonal_anomaly(
        integrated, "snow_fraction", settings.climate_baseline_end
    )
    integrated["NDSI_anomaly"] = _seasonal_anomaly(
        integrated, "NDSI", settings.climate_baseline_end
    )
    integrated["VV_anomaly"] = _seasonal_anomaly(
        integrated, "VV", settings.climate_baseline_end
    )
    integrated["VH_anomaly"] = _seasonal_anomaly(
        integrated, "VH", settings.climate_baseline_end
    )
    integrated["snow_fraction_change"] = integrated["snow_fraction"].diff()
    integrated["temp_change"] = integrated["temp_mean"].diff()
    integrated["PDD_change"] = integrated["PDD"].diff()
    integrated["NDSI_change"] = integrated["NDSI"].diff()
    api_values = []
    previous = np.nan
    for precipitation in integrated["precip_month"]:
        if pd.isna(precipitation):
            previous = np.nan
            api_values.append(np.nan)
        else:
            previous = float(precipitation) + (
                0.85 * previous if np.isfinite(previous) else 0.0
            )
            api_values.append(previous)
    integrated["antecedent_precipitation_index"] = api_values
    transition_columns = [
        "temp_change", "PDD_change", "snow_fraction_change", "NDSI_change",
        "VV_change", "VH_change",
    ]
    transition = integrated[transition_columns].copy()
    median = transition.median()
    scale = (transition - median).abs().median().replace(0, np.nan) * 1.4826
    standardized_transition = (transition - median) / scale
    integrated["environmental_transition_magnitude"] = np.sqrt(
        standardized_transition.pow(2).mean(axis=1, skipna=False)
    )

    climate_source_missing = integrated.get(
        "missing_data_flag", pd.Series(True, index=integrated.index)
    )
    integrated["climate_missing_data_flag"] = (
        climate_source_missing.fillna(True).astype(bool)
        | integrated["temp_mean"].isna()
    )
    integrated["sentinel2_missing_data_flag"] = integrated[
        "sentinel2_missing_data_flag"
    ].fillna(True).astype(bool)
    integrated["sentinel1_missing_data_flag"] = integrated[
        "sentinel1_missing_data_flag"
    ].fillna(True).astype(bool)
    core_features = [
        "temp_anomaly", "precip_anomaly", "PDD", "snow_fraction",
        "NDSI", "VV", "VH",
    ]
    integrated["available_feature_count"] = integrated[core_features].notna().sum(
        axis=1
    )
    integrated["missing_data_flag"] = integrated[
        [
            "climate_missing_data_flag",
            "sentinel2_missing_data_flag",
            "sentinel1_missing_data_flag",
        ]
    ].any(axis=1)

    preferred = [
        "date", "temp_mean", "temp_max", "temp_min", "temp_anomaly",
        "precip_1d_max", "precip_3d_max", "precip_7d_max",
        "precip_30d_max", "precip_month", "precip_anomaly", "PDD",
        "freeze_thaw_cycles", "snowfall_mm_we", "snow_depth_m",
        "solar_radiation_mj_m2", "runoff_mm", "snow_fraction",
        "snow_fraction_anomaly", "snow_fraction_change", "NDSI",
        "NDSI_anomaly", "NDSI_change", "snow_area_proxy_km2", "VV", "VH", "VV_change",
        "VH_change", "VV_anomaly", "VH_anomaly", "angle_deg",
        "temp_change", "PDD_change", "antecedent_precipitation_index",
        "environmental_transition_magnitude",
        "sentinel2_scene_count", "sentinel2_valid_area_fraction",
        "sentinel2_observation_count", "sentinel1_scene_count",
        "sentinel1_valid_area_fraction", "sentinel1_observation_count",
        "climate_missing_data_flag", "sentinel2_missing_data_flag",
        "sentinel1_missing_data_flag", "available_feature_count",
        "missing_data_flag",
        "climate_expected_observation_count", "climate_period_completeness",
        "climate_is_complete_period", "climate_quality_status",
        "climate_quality_reason", "sentinel2_expected_observation_count",
        "sentinel2_period_completeness", "sentinel2_is_complete_period",
        "sentinel2_quality_status", "sentinel2_quality_reason",
        "sentinel1_expected_observation_count", "sentinel1_period_completeness",
        "sentinel1_is_complete_period", "sentinel1_quality_status",
        "sentinel1_quality_reason",
    ]
    available_columns = [column for column in preferred if column in integrated]
    result = integrated[available_columns].copy()
    numeric_columns = result.select_dtypes(include=[np.number]).columns
    result[numeric_columns] = result[numeric_columns].replace([np.inf, -np.inf], np.nan)
    return result


def get_feature_provenance() -> pd.DataFrame:
    """Return machine-readable provenance for V2 engineered features."""
    return feature_provenance_table(FEATURE_PROVENANCE)
