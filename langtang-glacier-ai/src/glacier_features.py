"""Sentinel-2 masking, compositing, and snow-proxy feature extraction."""

from __future__ import annotations

from pathlib import Path
from dataclasses import replace

import ee
import numpy as np
import pandas as pd

from .config import SETTINGS, Settings
from .gee_utils import DATASET_IDS, collection_size


S2_BANDS = ["B2", "B3", "B4", "B8", "B11", "SCL"]


def get_sentinel2_collection(
    roi: ee.Geometry,
    start: str,
    end: str,
    settings: Settings = SETTINGS,
) -> ee.ImageCollection:
    """Retrieve S2 SR and link Cloud Score+ using shared system:index values."""
    sr = (
        ee.ImageCollection(DATASET_IDS["sentinel2_sr"])
        .filterBounds(roi)
        .filterDate(start, end)
        .filter(
            ee.Filter.lte(
                "CLOUDY_PIXEL_PERCENTAGE", settings.max_scene_cloud_percent
            )
        )
    )
    cloud_score = ee.ImageCollection(DATASET_IDS["cloud_score_plus"])
    return sr.linkCollection(cloud_score, [settings.cloud_score_band])


def mask_and_add_indices(
    image: ee.Image,
    settings: Settings = SETTINGS,
) -> ee.Image:
    """Mask cloud/shadow/bad SCL pixels and append reflectance and snow bands."""
    qa = image.select(settings.cloud_score_band).gte(
        settings.cloud_score_threshold
    )
    scl = image.select("SCL")
    scl_ok = (
        scl.neq(0)
        .And(scl.neq(1))
        .And(scl.neq(3))
        .And(scl.neq(8))
        .And(scl.neq(9))
        .And(scl.neq(10))
    )
    reflectance = image.select(["B2", "B3", "B4", "B8", "B11"]).divide(
        settings.reflectance_scale
    )
    ndsi = reflectance.normalizedDifference(["B3", "B11"]).rename("NDSI")
    snow = (
        ndsi.gte(settings.ndsi_snow_threshold)
        .And(reflectance.select("B3").gte(settings.min_green_reflectance))
        .rename("snow")
    )
    return (
        reflectance.addBands([ndsi, snow, image.select(settings.cloud_score_band)])
        .updateMask(qa.And(scl_ok))
        .copyProperties(image, image.propertyNames())
    )


def seasonal_collection(
    roi: ee.Geometry,
    year: int,
    settings: Settings = SETTINGS,
) -> ee.ImageCollection:
    """Return masked images in one comparable, configurable seasonal window."""
    start = ee.Date.fromYMD(year, settings.season_start_month, 1)
    end = ee.Date.fromYMD(year, settings.season_end_month, 1).advance(1, "month")
    raw = get_sentinel2_collection(
        roi, start.format("YYYY-MM-dd"), end.format("YYYY-MM-dd"), settings
    )
    return raw.map(lambda image: mask_and_add_indices(image, settings))


def make_seasonal_composite(
    roi: ee.Geometry,
    year: int,
    settings: Settings = SETTINGS,
) -> ee.Image:
    """Create a median seasonal composite and attach observation-count metadata."""
    start = f"{year}-{settings.season_start_month:02d}-01"
    end = pd.Timestamp(
        year=year, month=settings.season_end_month, day=1
    ) + pd.offsets.MonthBegin(1)
    return make_sentinel2_composite(
        roi, start, end.strftime("%Y-%m-%d"), settings
    ).set(
        {
            "year": year,
            "system:time_start": ee.Date(start).millis(),
        }
    )


def make_sentinel2_composite(
    roi: ee.Geometry,
    start: str,
    end: str,
    settings: Settings = SETTINGS,
) -> ee.Image:
    """Create a masked median Sentinel-2 composite for an arbitrary period."""
    collection = get_sentinel2_collection(roi, start, end, settings).map(
        lambda image: mask_and_add_indices(image, settings)
    )
    count = collection.size()
    output_bands = [
        "B2", "B3", "B4", "B8", "B11", "NDSI", "snow",
        settings.cloud_score_band,
    ]
    empty = (
        ee.Image.constant([0] * len(output_bands))
        .rename(output_bands)
        .updateMask(ee.Image(0))
    )
    composite = ee.Image(
        ee.Algorithms.If(count.gt(0), collection.median(), empty)
    ).clip(roi)
    empty_count = (
        ee.Image.constant(0)
        .rename("valid_observation_count")
        .updateMask(ee.Image(0))
    )
    valid_count = ee.Image(
        ee.Algorithms.If(
            count.gt(0),
            collection.select("NDSI").count().rename("valid_observation_count"),
            empty_count,
        )
    )
    return composite.addBands(valid_count).set(
        {
            "scene_count": count,
            "period_start": start,
            "period_end": end,
            "system:time_start": ee.Date(start).millis(),
        }
    )


def extract_snow_metrics(
    composite: ee.Image,
    glacier_roi: ee.Geometry,
    year: int,
    settings: Settings = SETTINGS,
) -> ee.Feature:
    """Reduce one composite to transparent snow-cover proxy and QA metrics."""
    date = f"{year}-{settings.season_start_month:02d}-01"
    return extract_period_snow_metrics(
        composite, glacier_roi, date, settings
    ).set("year", year)


def extract_period_snow_metrics(
    composite: ee.Image,
    glacier_roi: ee.Geometry,
    date: str,
    settings: Settings = SETTINGS,
) -> ee.Feature:
    """Reduce a dated composite to snow-proxy and observation-quality metrics."""
    pixel_area = ee.Image.pixelArea()
    valid = composite.select("NDSI").mask()
    snow_area = pixel_area.updateMask(composite.select("snow")).rename("snow_m2")
    valid_area = pixel_area.updateMask(valid).rename("valid_m2")
    bands = composite.select(["NDSI", "valid_observation_count"]).addBands(
        [snow_area, valid_area]
    )
    stats = bands.reduceRegion(
        reducer=ee.Reducer.mean().combine(ee.Reducer.sum(), sharedInputs=True),
        geometry=glacier_roi,
        scale=settings.reduction_scale_m,
        maxPixels=settings.max_pixels,
        tileScale=settings.tile_scale,
        bestEffort=False,
    )
    snow_m2 = ee.Number(
        ee.Algorithms.If(stats.get("snow_m2_sum"), stats.get("snow_m2_sum"), 0)
    )
    valid_m2 = ee.Number(
        ee.Algorithms.If(stats.get("valid_m2_sum"), stats.get("valid_m2_sum"), 0)
    )
    glacier_m2 = glacier_roi.area(1)
    snow_fraction_valid = ee.Algorithms.If(
        valid_m2.gt(0), snow_m2.divide(valid_m2), None
    )
    return ee.Feature(
        None,
        {
            "date": date,
            "scene_count": composite.get("scene_count"),
            "ndsi_mean": stats.get("NDSI_mean"),
            "snow_area_km2": snow_m2.divide(1e6),
            "snow_fraction_valid": snow_fraction_valid,
            "valid_area_fraction": valid_m2.divide(glacier_m2),
            "mean_valid_observation_count": stats.get(
                "valid_observation_count_mean"
            ),
            "missing_data_flag": valid_m2.eq(0),
        },
    )


def build_annual_snow_series(
    glacier_roi: ee.Geometry,
    settings: Settings = SETTINGS,
) -> tuple[ee.ImageCollection, ee.FeatureCollection]:
    """Build post-monsoon composites and their annual metrics for configured years."""
    today = pd.Timestamp.now().normalize()
    available_years = []
    for year in settings.analysis_years:
        season_end = pd.Timestamp(
            year=year, month=settings.season_end_month, day=1
        ) + pd.offsets.MonthBegin(1)
        if season_end <= today:
            available_years.append(year)
    composites = [
        make_seasonal_composite(glacier_roi, year, settings)
        for year in available_years
    ]
    images = ee.ImageCollection.fromImages(composites)
    features = [
        extract_snow_metrics(image, glacier_roi, year, settings)
        for image, year in zip(composites, available_years)
    ]
    return images, ee.FeatureCollection(features)


def build_monthly_snow_series(
    glacier_roi: ee.Geometry,
    settings: Settings = SETTINGS,
) -> tuple[ee.ImageCollection, ee.FeatureCollection]:
    """Build monthly Sentinel-2 composites without filling cloudy or empty months."""
    start = pd.Timestamp(settings.sentinel2_monthly_start)
    end = min(
        pd.Timestamp(settings.sentinel2_end),
        pd.Timestamp.now().normalize().to_period("M").start_time,
    )
    months = pd.date_range(start, end, freq="MS", inclusive="left")
    composites: list[ee.Image] = []
    features: list[ee.Feature] = []
    for month in months:
        next_month = min(month + pd.offsets.MonthBegin(1), end)
        start_text = month.strftime("%Y-%m-%d")
        end_text = next_month.strftime("%Y-%m-%d")
        composite = make_sentinel2_composite(
            glacier_roi, start_text, end_text, settings
        )
        composites.append(composite)
        features.append(
            extract_period_snow_metrics(
                composite, glacier_roi, start_text, settings
            )
        )
    return ee.ImageCollection.fromImages(composites), ee.FeatureCollection(features)


def monthly_snow_features_to_dataframe(
    features: ee.FeatureCollection,
) -> pd.DataFrame:
    """Download monthly Sentinel-2 metrics while preserving null observations."""
    payload = features.getInfo()
    rows = [feature.get("properties", {}) for feature in payload.get("features", [])]
    if not rows:
        raise ValueError("Earth Engine returned no monthly Sentinel-2 metrics.")
    frame = pd.DataFrame(rows).sort_values("date").reset_index(drop=True)
    frame["date"] = pd.to_datetime(frame["date"])
    return _add_optical_quality(frame)


def _add_optical_quality(frame: pd.DataFrame) -> pd.DataFrame:
    """Attach consistent optical coverage QA without inventing expected scenes."""
    output = frame.copy()
    coverage = pd.to_numeric(output["valid_area_fraction"], errors="coerce")
    output["observation_count"] = output["mean_valid_observation_count"]
    output["expected_observation_count"] = pd.NA
    output["period_completeness"] = coverage
    output["is_complete_period"] = coverage.ge(0.80)
    output["quality_status"] = np.select(
        [coverage.ge(0.80), coverage.ge(0.60)],
        ["GOOD", "CAUTION"],
        default="INSUFFICIENT",
    )
    output["quality_reason"] = np.where(
        coverage.ge(0.80),
        "valid-area fraction is at least 0.80",
        "valid-area fraction is below 0.80",
    )
    return output


def extract_monthly_snow_dataframe_sequential(
    glacier_roi: ee.Geometry,
    checkpoint_path: str | Path | None = None,
    resume: bool = True,
    settings: Settings = SETTINGS,
) -> pd.DataFrame:
    """Evaluate one monthly reduction at a time and checkpoint completed rows.

    Earth Engine limits concurrent aggregations. Evaluating a FeatureCollection of
    all monthly ``reduceRegion`` operations can exceed that limit, whereas this
    deliberately sequential path keeps only one aggregation active.
    """
    completed = pd.DataFrame()
    completed_dates: set[str] = set()
    if checkpoint_path and resume:
        try:
            completed = pd.read_csv(checkpoint_path, parse_dates=["date"])
        except FileNotFoundError:
            pass
        if not completed.empty:
            completed_dates = set(completed["date"].dt.strftime("%Y-%m-%d"))
            print(f"Resuming after {len(completed_dates)} checkpointed months")

    start = pd.Timestamp(settings.sentinel2_monthly_start)
    end = min(
        pd.Timestamp(settings.sentinel2_end),
        pd.Timestamp.now().normalize().to_period("M").start_time,
    )
    months = pd.date_range(start, end, freq="MS", inclusive="left")
    rows = completed.to_dict("records") if not completed.empty else []
    for month in months:
        start_text = month.strftime("%Y-%m-%d")
        if start_text in completed_dates:
            continue
        next_month = min(month + pd.offsets.MonthBegin(1), end)
        composite = make_sentinel2_composite(
            glacier_roi,
            start_text,
            next_month.strftime("%Y-%m-%d"),
            settings,
        )
        feature = extract_period_snow_metrics(
            composite, glacier_roi, start_text, settings
        )
        properties = ee.Feature(feature).toDictionary().getInfo()
        rows.append(properties)
        frame = pd.DataFrame(rows)
        frame["date"] = pd.to_datetime(frame["date"])
        frame = frame.sort_values("date").drop_duplicates("date").reset_index(
            drop=True
        )
        if checkpoint_path:
            frame.to_csv(checkpoint_path, index=False)
        print(f"Sentinel-2 monthly reduction complete: {start_text}")

    if not rows:
        raise ValueError("Earth Engine returned no monthly Sentinel-2 metrics.")
    result = pd.DataFrame(rows)
    result["date"] = pd.to_datetime(result["date"])
    result = result.sort_values("date").drop_duplicates("date").reset_index(drop=True)
    return _add_optical_quality(result)


def feature_collection_to_dataframe(features: ee.FeatureCollection) -> pd.DataFrame:
    """Download a small feature collection, preserving nulls as missing values."""
    payload = features.getInfo()
    rows = [feature.get("properties", {}) for feature in payload.get("features", [])]
    if not rows:
        raise ValueError("Earth Engine returned no annual snow metrics.")
    frame = pd.DataFrame(rows).sort_values("year").reset_index(drop=True)
    frame["date"] = pd.to_datetime(frame["date"])
    return _add_optical_quality(frame)


def verify_sentinel2_availability(
    roi: ee.Geometry,
    settings: Settings = SETTINGS,
) -> int:
    """Check that the configured archive window has observations."""
    collection = get_sentinel2_collection(
        roi, settings.sentinel2_start, settings.sentinel2_end, settings
    )
    return collection_size(collection, "Sentinel-2 SR over Lirung Glacier")


def extract_ndsi_threshold_sensitivity(
    glacier_roi: ee.Geometry,
    thresholds: tuple[float, ...] = (0.30, 0.40, 0.50),
    settings: Settings = SETTINGS,
) -> pd.DataFrame:
    """Extract annual proxy metrics for explicit NDSI threshold sensitivity."""
    rows = []
    for threshold in thresholds:
        threshold_settings = replace(settings, ndsi_snow_threshold=threshold)
        today = pd.Timestamp.now().normalize()
        available_years = [
            year for year in settings.analysis_years
            if (
                pd.Timestamp(year=year, month=settings.season_end_month, day=1)
                + pd.offsets.MonthBegin(1)
            ) <= today
        ]
        for year in available_years:
            composite = make_seasonal_composite(
                glacier_roi, year, threshold_settings
            )
            properties = ee.Feature(
                extract_snow_metrics(
                    composite, glacier_roi, year, threshold_settings
                )
            ).toDictionary().getInfo()
            properties["ndsi_threshold"] = threshold
            rows.append(properties)
    frame = pd.DataFrame(rows)
    frame["date"] = pd.to_datetime(frame["date"])
    return frame.sort_values(["ndsi_threshold", "date"]).reset_index(drop=True)


def sentinel2_proxy_trend_sensitivity(
    frame: pd.DataFrame,
    coverage_thresholds: tuple[float, ...] = (0.0, 0.60, 0.80, 0.90),
) -> pd.DataFrame:
    """Report snow-proxy slope stability across NDSI and coverage thresholds."""
    required = {
        "date", "ndsi_threshold", "valid_area_fraction", "snow_fraction_valid"
    }
    missing = required.difference(frame.columns)
    if missing:
        raise ValueError(f"Sentinel-2 sensitivity table lacks: {sorted(missing)}")
    data = frame.copy()
    data["date"] = pd.to_datetime(data["date"])
    rows = []
    for ndsi_threshold, threshold_group in data.groupby("ndsi_threshold"):
        for coverage_threshold in coverage_thresholds:
            subset = threshold_group.loc[
                threshold_group["valid_area_fraction"].ge(coverage_threshold)
            ].dropna(subset=["snow_fraction_valid"])
            if len(subset) >= 4:
                years = (
                    subset["date"] - subset["date"].min()
                ).dt.days.to_numpy() / 365.2425
                slope = float(np.polyfit(years, subset["snow_fraction_valid"], 1)[0])
                direction = "increasing" if slope > 0 else "decreasing" if slope < 0 else "flat"
            else:
                slope = np.nan
                direction = "insufficient"
            rows.append(
                {
                    "ndsi_threshold": ndsi_threshold,
                    "coverage_threshold": coverage_threshold,
                    "n": len(subset),
                    "slope_per_year": slope,
                    "trend_direction": direction,
                    "metric_label": "snow/clean-ice spectral proxy; not glacier area",
                }
            )
    result = pd.DataFrame(rows)
    stable = result.dropna(subset=["slope_per_year"]).groupby(
        "ndsi_threshold"
    )["trend_direction"].transform("nunique").eq(1)
    result.loc[stable.index, "direction_stable_across_coverage"] = stable
    return result
