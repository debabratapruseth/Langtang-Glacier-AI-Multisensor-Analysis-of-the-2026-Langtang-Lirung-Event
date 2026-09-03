"""ERA5-Land extraction and seasonally aware climate feature engineering."""

from __future__ import annotations

from datetime import timedelta
from pathlib import Path

import ee
import numpy as np
import pandas as pd

from .config import SETTINGS, Settings
from .gee_utils import DATASET_IDS
from .quality import add_period_quality


ERA5_INPUT_BANDS = (
    "temperature_2m",
    "temperature_2m_min",
    "temperature_2m_max",
    "total_precipitation_sum",
    "snowfall_sum",
    "snow_depth",
    "surface_solar_radiation_downwards_sum",
    "runoff_sum",
)


def get_era5_land_daily(start: str, end: str) -> ee.ImageCollection:
    """Return the selected ERA5-Land daily aggregate bands."""
    return (
        ee.ImageCollection(DATASET_IDS["era5_land_daily"])
        .filterDate(start, end)
        .select(list(ERA5_INPUT_BANDS))
    )


def _daily_climate_feature(
    image: ee.Image,
    region: ee.Geometry,
    settings: Settings,
) -> ee.Feature:
    """Convert one ERA5-Land image to regional daily metrics in useful units."""
    temperature = image.select(
        ["temperature_2m", "temperature_2m_min", "temperature_2m_max"]
    ).subtract(273.15).rename(["temp_mean_c", "temp_min_c", "temp_max_c"])
    water = (
        image.select(
            ["total_precipitation_sum", "snowfall_sum", "runoff_sum"]
        )
        .multiply(1_000)
        .max(0)
        .rename(["precip_mm", "snowfall_mm_we", "runoff_mm"])
    )
    snow_depth = image.select("snow_depth").rename("snow_depth_m")
    radiation = (
        image.select("surface_solar_radiation_downwards_sum")
        .divide(1_000_000)
        .rename("solar_radiation_mj_m2")
    )
    metrics = temperature.addBands(water).addBands(snow_depth).addBands(radiation)
    values = metrics.reduceRegion(
        reducer=ee.Reducer.mean(),
        geometry=region,
        scale=settings.era5_scale_m,
        maxPixels=settings.max_pixels,
        tileScale=settings.tile_scale,
    )
    date = ee.Date(image.get("system:time_start"))
    return ee.Feature(None, values).set(
        {"date": date.format("YYYY-MM-dd"), "system:time_start": date.millis()}
    )


def era5_daily_features(
    region: ee.Geometry,
    start: str,
    end: str,
    settings: Settings = SETTINGS,
) -> ee.FeatureCollection:
    """Create daily regional ERA5-Land features without client-side interpolation."""
    collection = get_era5_land_daily(start, end)
    return ee.FeatureCollection(
        collection.map(lambda image: _daily_climate_feature(image, region, settings))
    )


def _feature_collection_rows(features: ee.FeatureCollection) -> list[dict]:
    """Download a bounded feature batch and return its property dictionaries."""
    payload = features.getInfo()
    return [feature.get("properties", {}) for feature in payload.get("features", [])]


def extract_era5_daily_dataframe(
    region: ee.Geometry,
    start: str = SETTINGS.climate_start,
    end: str = SETTINGS.climate_end,
    settings: Settings = SETTINGS,
) -> pd.DataFrame:
    """Download daily metrics in yearly batches to avoid one oversized response."""
    start_date = pd.Timestamp(start)
    end_date = pd.Timestamp(end)
    if end_date <= start_date:
        raise ValueError("Climate extraction end must be after start.")

    rows: list[dict] = []
    for year in range(start_date.year, end_date.year + 1):
        batch_start = max(start_date, pd.Timestamp(year=year, month=1, day=1))
        batch_end = min(end_date, pd.Timestamp(year=year + 1, month=1, day=1))
        if batch_start >= batch_end:
            continue
        features = era5_daily_features(
            region,
            batch_start.strftime("%Y-%m-%d"),
            batch_end.strftime("%Y-%m-%d"),
            settings,
        )
        year_rows = _feature_collection_rows(features)
        print(f"ERA5-Land {year}: {len(year_rows)} daily records")
        rows.extend(year_rows)

    if not rows:
        raise ValueError("ERA5-Land returned no daily observations for the period.")
    frame = pd.DataFrame(rows)
    frame["date"] = pd.to_datetime(frame["date"])
    return frame.sort_values("date").drop_duplicates("date").reset_index(drop=True)


def add_daily_climate_features(
    frame: pd.DataFrame,
    settings: Settings = SETTINGS,
) -> pd.DataFrame:
    """Add rolling precipitation, PDD, freeze-thaw, and daily seasonal anomalies."""
    required = {"date", "temp_mean_c", "temp_min_c", "temp_max_c", "precip_mm"}
    missing = required.difference(frame.columns)
    if missing:
        raise ValueError(f"Daily climate table lacks columns: {sorted(missing)}")

    daily = frame.copy().sort_values("date")
    daily["date"] = pd.to_datetime(daily["date"])
    complete_index = pd.date_range(daily["date"].min(), daily["date"].max(), freq="D")
    daily = daily.set_index("date").reindex(complete_index).rename_axis("date")
    daily["observation_count"] = daily["temp_mean_c"].notna().astype(int)
    daily["missing_data_flag"] = daily["observation_count"].eq(0)

    for window in (3, 7, 30):
        daily[f"precip_{window}d_mm"] = daily["precip_mm"].rolling(
            window, min_periods=window
        ).sum()
    daily["positive_degree_days"] = daily["temp_mean_c"].clip(lower=0)
    daily["freeze_thaw_cycle"] = (
        daily["temp_min_c"].le(0) & daily["temp_max_c"].gt(0)
    ).astype("Int64")

    baseline = daily.loc[
        pd.Timestamp(settings.climate_baseline_start) :
        pd.Timestamp(settings.climate_baseline_end) - pd.Timedelta(days=1)
    ].copy()
    daily["month_day"] = daily.index.strftime("%m-%d")
    baseline["month_day"] = baseline.index.strftime("%m-%d")
    temp_climatology = baseline.groupby("month_day")["temp_mean_c"].mean()
    daily["temp_anomaly_c"] = daily["temp_mean_c"] - daily["month_day"].map(
        temp_climatology
    )
    return daily.reset_index()


def aggregate_monthly_climate(
    daily: pd.DataFrame,
    settings: Settings = SETTINGS,
) -> pd.DataFrame:
    """Aggregate daily features and calculate month-of-year anomalies."""
    indexed = daily.copy().set_index(pd.to_datetime(daily["date"]))
    monthly = indexed.resample("MS").agg(
        temp_mean_c=("temp_mean_c", "mean"),
        temp_max_c=("temp_max_c", "max"),
        temp_min_c=("temp_min_c", "min"),
        temp_anomaly_c=("temp_anomaly_c", "mean"),
        precip_month_mm=("precip_mm", "sum"),
        precip_1d_max_mm=("precip_mm", "max"),
        precip_3d_max_mm=("precip_3d_mm", "max"),
        precip_7d_max_mm=("precip_7d_mm", "max"),
        precip_30d_max_mm=("precip_30d_mm", "max"),
        pdd=("positive_degree_days", "sum"),
        freeze_thaw_cycles=("freeze_thaw_cycle", "sum"),
        snowfall_mm_we=("snowfall_mm_we", "sum"),
        snow_depth_m=("snow_depth_m", "mean"),
        solar_radiation_mj_m2=("solar_radiation_mj_m2", "sum"),
        runoff_mm=("runoff_mm", "sum"),
        observation_count=("observation_count", "sum"),
    )
    monthly["expected_observation_count"] = monthly.index.days_in_month
    monthly = add_period_quality(
        monthly.reset_index(names="date"),
        "observation_count",
        "expected_observation_count",
    ).set_index("date")
    monthly["expected_days"] = monthly["expected_observation_count"]
    monthly["missing_data_flag"] = ~monthly["is_complete_period"]
    accumulated = [
        "precip_month_mm",
        "precip_3d_max_mm",
        "precip_7d_max_mm",
        "precip_30d_max_mm",
        "pdd",
        "freeze_thaw_cycles",
        "snowfall_mm_we",
        "solar_radiation_mj_m2",
        "runoff_mm",
    ]
    monthly.loc[~monthly["is_complete_period"], accumulated] = np.nan
    monthly["month"] = monthly.index.month

    baseline_mask = (
        (monthly.index >= pd.Timestamp(settings.climate_baseline_start))
        & (monthly.index < pd.Timestamp(settings.climate_baseline_end))
        & ~monthly["missing_data_flag"]
    )
    baseline = monthly.loc[baseline_mask]
    precip_mean = baseline.groupby("month")["precip_month_mm"].mean()
    precip_std = baseline.groupby("month")["precip_month_mm"].std().replace(0, np.nan)
    pdd_mean = baseline.groupby("month")["pdd"].mean()
    pdd_std = baseline.groupby("month")["pdd"].std().replace(0, np.nan)
    monthly["precip_anomaly_z"] = (
        monthly["precip_month_mm"] - monthly["month"].map(precip_mean)
    ) / monthly["month"].map(precip_std)
    monthly["pdd_anomaly_z"] = (
        monthly["pdd"] - monthly["month"].map(pdd_mean)
    ) / monthly["month"].map(pdd_std)
    return monthly.rename_axis("date").reset_index()


def _summarize_interval(interval: pd.DataFrame) -> dict[str, float]:
    """Summarize one complete daily interval using metric-appropriate operators."""
    return {
        "temp_mean_c": float(interval["temp_mean_c"].mean()),
        "precip_mm": float(interval["precip_mm"].sum()),
        "pdd": float(interval["positive_degree_days"].sum()),
        "freeze_thaw_cycles": float(interval["freeze_thaw_cycle"].sum()),
        "snowfall_mm_we": float(interval["snowfall_mm_we"].sum()),
        "runoff_mm": float(interval["runoff_mm"].sum()),
    }


def matched_period_climatology(
    daily: pd.DataFrame,
    start: str | pd.Timestamp,
    end: str | pd.Timestamp,
    baseline_start_year: int,
    baseline_end_year: int,
) -> pd.DataFrame:
    """Compare an observed interval with identical month/day spans in prior years.

    ``end`` is exclusive. Only years containing every expected day are admitted to
    the historical distribution, preventing partial accumulated values from being
    compared with complete periods.
    """
    data = daily.copy()
    data["date"] = pd.to_datetime(data["date"])
    start_date = pd.Timestamp(start).normalize()
    end_date = pd.Timestamp(end).normalize()
    if end_date <= start_date:
        raise ValueError("Matched-period end must be after start.")
    if start_date.year != (end_date - timedelta(days=1)).year:
        raise ValueError("Matched-period intervals may not cross a year boundary.")
    expected = (end_date - start_date).days
    required = (
        "temp_mean_c",
        "precip_mm",
        "positive_degree_days",
        "freeze_thaw_cycle",
        "snowfall_mm_we",
        "runoff_mm",
    )
    missing = [column for column in required if column not in data]
    if missing:
        raise ValueError(f"Daily climate table lacks matched-period fields: {missing}")

    observed = data.loc[data["date"].ge(start_date) & data["date"].lt(end_date)]
    observed_complete = len(observed) == expected and observed[list(required)].notna().all().all()
    observed_values = _summarize_interval(observed) if observed_complete else {}
    historical: dict[str, list[float]] = {key: [] for key in _summarize_interval(data.iloc[:1])}
    for year in range(baseline_start_year, baseline_end_year + 1):
        historical_start = start_date.replace(year=year)
        historical_end = historical_start + timedelta(days=expected)
        interval = data.loc[
            data["date"].ge(historical_start) & data["date"].lt(historical_end)
        ]
        if len(interval) != expected or not interval[list(required)].notna().all().all():
            continue
        for metric, value in _summarize_interval(interval).items():
            historical[metric].append(value)

    rows = []
    for metric, reference_values in historical.items():
        reference = np.asarray(reference_values, dtype=float)
        value = observed_values.get(metric, np.nan)
        if observed_complete and reference.size:
            percentile = float((reference <= value).mean())
            standard_deviation = float(reference.std(ddof=1)) if reference.size > 1 else np.nan
            z_score = (
                float((value - reference.mean()) / standard_deviation)
                if np.isfinite(standard_deviation) and standard_deviation > 0
                else np.nan
            )
        else:
            percentile = np.nan
            z_score = np.nan
        rows.append(
            {
                "period_start": start_date,
                "period_end_exclusive": end_date,
                "metric": metric,
                "value": value,
                "historical_percentile": percentile,
                "z_score": z_score,
                "historical_sample_size": int(reference.size),
                "observation_count": int(len(observed)),
                "expected_observation_count": expected,
                "period_completeness": len(observed) / expected,
                "is_complete_period": bool(observed_complete),
                "quality_status": "GOOD" if observed_complete else "INSUFFICIENT",
                "quality_reason": (
                    "matched period is complete"
                    if observed_complete
                    else f"matched period has {len(observed)}/{expected} daily rows"
                ),
            }
        )
    return pd.DataFrame(rows)


def build_antecedent_climate_summary(
    daily: pd.DataFrame,
    event_date: str | pd.Timestamp,
    baseline_start_year: int,
    baseline_end_year: int,
    windows: tuple[int, ...] = (1, 3, 7, 14, 30, 60, 90),
) -> pd.DataFrame:
    """Build event-exclusive antecedent windows with matched historical periods."""
    event = pd.Timestamp(event_date).normalize()
    frames = []
    for days in windows:
        summary = matched_period_climatology(
            daily,
            event - pd.Timedelta(days=days),
            event,
            baseline_start_year,
            baseline_end_year,
        )
        summary.insert(0, "window_days", days)
        frames.append(summary)
    return pd.concat(frames, ignore_index=True)


def load_or_extract_daily_climate(
    region: ee.Geometry,
    cache_path: Path,
    force: bool = False,
    settings: Settings = SETTINGS,
) -> pd.DataFrame:
    """Reuse a real cached extraction or query Earth Engine and persist it."""
    if cache_path.exists() and not force:
        cached = pd.read_csv(cache_path, parse_dates=["date"])
        if not cached.empty:
            print(f"Loaded {len(cached)} cached daily records from {cache_path}")
            return cached
    raw = extract_era5_daily_dataframe(
        region, settings.climate_start, settings.climate_end, settings
    )
    daily = add_daily_climate_features(raw, settings)
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    daily.to_csv(cache_path, index=False)
    return daily
