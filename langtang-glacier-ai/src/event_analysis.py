"""Guarded event-relative tables and Earth Engine comparison products."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

import ee
import numpy as np
import pandas as pd

from .config import SETTINGS, Settings
from .glacier_features import (
    extract_period_snow_metrics,
    make_sentinel2_composite,
)
from .sar_features import get_comparable_sentinel1_collection
from .sar_features import extract_sentinel1_metrics
from .sar_features import make_sentinel1_composite
from .quality import require_pre_post_coverage
from .terrain_hydrology import hydrology_layers, terrain_layers


PRE_EVENT_FEATURES = (
    "temp_anomaly",
    "precip_month",
    "precip_3d_max",
    "precip_7d_max",
    "PDD",
    "snow_fraction",
    "NDSI",
    "VV",
    "VH",
    "anomaly_score",
)


@dataclass(frozen=True)
class EventWindows:
    """Explicit, cited event and end-exclusive satellite comparison windows."""

    event_date: str
    event_source: str
    pre_start: str
    pre_end: str
    post_start: str
    post_end: str

    def validated(self) -> "EventWindows":
        """Validate chronology and require a nonempty event-source citation."""
        if not self.event_source.strip():
            raise ValueError("EVENT_SOURCE is required for event-relative analysis.")
        dates = {
            name: pd.Timestamp(value)
            for name, value in asdict(self).items()
            if name != "event_source"
        }
        if not dates["pre_start"] < dates["pre_end"]:
            raise ValueError("PRE_START must be earlier than PRE_END.")
        if not dates["post_start"] < dates["post_end"]:
            raise ValueError("POST_START must be earlier than POST_END.")
        if dates["pre_end"] > dates["event_date"]:
            raise ValueError("PRE_END must be on or before EVENT_DATE.")
        if dates["post_start"] < dates["event_date"]:
            raise ValueError("POST_START must be on or after EVENT_DATE.")
        return self

    def metadata(self) -> dict[str, str]:
        """Return validated serializable metadata."""
        self.validated()
        return asdict(self)


def build_pre_event_percentiles(
    frame: pd.DataFrame,
    event_date: str,
    features: tuple[str, ...] = PRE_EVENT_FEATURES,
    months: int = 12,
) -> pd.DataFrame:
    """Compare the months before an event with earlier same-month observations."""
    if months < 1:
        raise ValueError("months must be positive.")
    data = frame.copy()
    data["date"] = pd.to_datetime(data["date"]).dt.to_period("M").dt.to_timestamp()
    event_month = pd.Timestamp(event_date).to_period("M")
    target_periods = pd.period_range(
        event_month - months,
        event_month - 1,
        freq="M",
    )
    target_start = target_periods[0].to_timestamp()
    available = [feature for feature in features if feature in data]
    if not available:
        raise ValueError("None of the configured pre-event features were found.")

    rows: list[dict[str, Any]] = []
    for period in target_periods:
        date = period.to_timestamp()
        observed_row = data.loc[data["date"].eq(date)]
        for feature in available:
            history = data.loc[
                (data["date"] < target_start)
                & data["date"].dt.month.eq(period.month),
                feature,
            ].dropna()
            observed = (
                observed_row[feature].iloc[0]
                if not observed_row.empty and pd.notna(observed_row[feature].iloc[0])
                else np.nan
            )
            quantiles = history.quantile([0.05, 0.25, 0.50, 0.75, 0.95])
            rows.append(
                {
                    "date": date,
                    "feature": feature,
                    "observed": observed,
                    "historical_count": int(history.size),
                    "historical_q05": quantiles.get(0.05, np.nan),
                    "historical_q25": quantiles.get(0.25, np.nan),
                    "historical_median": quantiles.get(0.50, np.nan),
                    "historical_q75": quantiles.get(0.75, np.nan),
                    "historical_q95": quantiles.get(0.95, np.nan),
                }
            )
    return pd.DataFrame(rows)


def make_event_sentinel2_products(
    roi: ee.Geometry,
    windows: EventWindows,
    settings: Settings = SETTINGS,
) -> tuple[ee.Image, ee.Image, ee.Image]:
    """Return pre, post, and post-minus-pre optical screening products."""
    windows.validated()
    pre = make_sentinel2_composite(
        roi, windows.pre_start, windows.pre_end, settings
    )
    post = make_sentinel2_composite(
        roi, windows.post_start, windows.post_end, settings
    )
    pre_count = int(ee.Number(pre.get("scene_count")).getInfo())
    post_count = int(ee.Number(post.get("scene_count")).getInfo())
    if pre_count == 0 or post_count == 0:
        raise ValueError(
            "Sentinel-2 comparison requires scenes in both windows; "
            f"found pre={pre_count}, post={post_count}."
        )

    def add_ndvi(image: ee.Image) -> ee.Image:
        return image.addBands(
            image.normalizedDifference(["B8", "B4"]).rename("NDVI")
        )

    pre = add_ndvi(pre)
    post = add_ndvi(post)
    delta = post.select(["NDSI", "NDVI"]).subtract(
        pre.select(["NDSI", "NDVI"])
    ).rename(["delta_NDSI", "delta_NDVI"])
    return pre, post, delta


def sentinel2_event_metrics(
    pre: ee.Image,
    post: ee.Image,
    glacier_roi: ee.Geometry,
    windows: EventWindows,
    settings: Settings = SETTINGS,
) -> pd.DataFrame:
    """Evaluate pre/post snow-proxy metrics sequentially and retain QA fields."""
    expected = (
        "date",
        "scene_count",
        "ndsi_mean",
        "snow_area_km2",
        "snow_fraction_valid",
        "valid_area_fraction",
        "mean_valid_observation_count",
        "missing_data_flag",
    )
    records = []
    for period, image, date in (
        ("pre", pre, windows.pre_start),
        ("post", post, windows.post_start),
    ):
        feature = extract_period_snow_metrics(image, glacier_roi, date, settings)
        properties = ee.Feature(feature).toDictionary().getInfo()
        record = {column: properties.get(column) for column in expected}
        record["period"] = period
        records.append(record)
    frame = pd.DataFrame(records)
    frame["date"] = pd.to_datetime(frame["date"])
    approved, reason = require_pre_post_coverage(
        frame, settings.sentinel2_event_min_valid_area
    )
    frame["expected_observation_count"] = frame["scene_count"]
    frame["observation_count"] = frame["mean_valid_observation_count"]
    frame["period_completeness"] = frame["valid_area_fraction"]
    frame["is_complete_period"] = approved
    frame["quality_status"] = "GOOD" if approved else "INSUFFICIENT"
    frame["quality_reason"] = reason
    frame["quantitative_change_estimated"] = approved
    for column in ("ndsi_mean", "snow_area_km2", "snow_fraction_valid"):
        frame[column] = pd.to_numeric(frame[column], errors="coerce")
        frame[f"{column}_change_from_pre"] = (
            frame[column] - frame[column].iloc[0] if approved else np.nan
        )
    return frame


def nearest_sentinel1_event_windows(
    roi: ee.Geometry,
    event_date: str,
    track: dict[str, Any],
    search_days: int = 60,
    required: bool = True,
    settings: Settings = SETTINGS,
) -> dict[str, Any]:
    """Find nearest same-track acquisitions strictly before and after an event."""
    if search_days < 1:
        raise ValueError("search_days must be positive.")
    event = pd.Timestamp(event_date).normalize()
    pre_search_start = event - pd.Timedelta(days=search_days)
    post_search_start = event + pd.Timedelta(days=1)
    post_search_end = post_search_start + pd.Timedelta(days=search_days)

    pre_collection = get_comparable_sentinel1_collection(
        roi,
        pre_search_start.strftime("%Y-%m-%d"),
        event.strftime("%Y-%m-%d"),
        track,
        settings,
    )
    post_collection = get_comparable_sentinel1_collection(
        roi,
        post_search_start.strftime("%Y-%m-%d"),
        post_search_end.strftime("%Y-%m-%d"),
        track,
        settings,
    )
    pre_count = int(pre_collection.size().getInfo())
    post_count = int(post_collection.size().getInfo())
    if pre_count == 0 or post_count == 0:
        message = (
            "No same-track Sentinel-1 acquisition was found within "
            f"{search_days} days on both sides of the event; "
            f"found pre={pre_count}, post={post_count}."
        )
        if required:
            raise ValueError(message)
        return {
            "available": False,
            "diagnostic": message,
            "pre_scene_count": pre_count,
            "post_scene_count": post_count,
            "orbit_pass": track["orbit_pass"],
            "relative_orbit": track["relative_orbit"],
            "search_days": search_days,
        }

    pre_image = ee.Image(
        pre_collection.sort("system:time_start", False).first()
    )
    post_image = ee.Image(post_collection.sort("system:time_start").first())
    pre_millis = ee.Number(pre_image.get("system:time_start")).getInfo()
    post_millis = ee.Number(post_image.get("system:time_start")).getInfo()
    pre_date = pd.to_datetime(pre_millis, unit="ms", utc=True).tz_localize(None)
    post_date = pd.to_datetime(post_millis, unit="ms", utc=True).tz_localize(None)
    pre_date = pre_date.normalize()
    post_date = post_date.normalize()
    pre_start = pre_date.strftime("%Y-%m-%d")
    pre_end = (pre_date + pd.Timedelta(days=1)).strftime("%Y-%m-%d")
    post_start = post_date.strftime("%Y-%m-%d")
    post_end = (post_date + pd.Timedelta(days=1)).strftime("%Y-%m-%d")
    coverage = []
    for start, end in ((pre_start, pre_end), (post_start, post_end)):
        composite = make_sentinel1_composite(
            roi, start, end, track, settings
        )
        properties = ee.Feature(
            extract_sentinel1_metrics(composite, roi, start, settings)
        ).toDictionary().getInfo()
        coverage.append(float(properties.get("valid_area_fraction") or 0.0))
    if min(coverage) < settings.sentinel1_min_valid_area:
        message = (
            "Same-track Sentinel-1 acquisitions exist, but valid glacier-ROI "
            f"coverage fails {settings.sentinel1_min_valid_area:.2f}; "
            f"pre={coverage[0]:.3f}, post={coverage[1]:.3f}."
        )
        if required:
            raise ValueError(message)
        return {
            "available": False,
            "diagnostic": message,
            "pre_scene_count": pre_count,
            "post_scene_count": post_count,
            "pre_valid_area_fraction": coverage[0],
            "post_valid_area_fraction": coverage[1],
            "orbit_pass": track["orbit_pass"],
            "relative_orbit": track["relative_orbit"],
            "search_days": search_days,
        }
    return {
        "available": True,
        "pre_start": pre_start,
        "pre_end": pre_end,
        "post_start": post_start,
        "post_end": post_end,
        "pre_days_before_event": int((event - pre_date).days),
        "post_days_after_event": int((post_date - event).days),
        "pre_valid_area_fraction": coverage[0],
        "post_valid_area_fraction": coverage[1],
        "orbit_pass": track["orbit_pass"],
        "relative_orbit": track["relative_orbit"],
        "search_days": search_days,
    }


def sentinel1_event_metrics(
    pre: ee.Image,
    post: ee.Image,
    glacier_roi: ee.Geometry,
    pre_date: str,
    post_date: str,
    settings: Settings = SETTINGS,
) -> pd.DataFrame:
    """Evaluate SAR metrics while preserving omitted Earth Engine null fields."""
    expected = (
        "date",
        "vv_db",
        "vv_std_db",
        "vh_db",
        "vh_std_db",
        "angle_deg",
        "mean_valid_observation_count",
        "valid_area_fraction",
        "scene_count",
        "missing_data_flag",
        "orbit_pass",
        "relative_orbit",
    )
    records = []
    for period, image, date in (
        ("pre", pre, pre_date),
        ("post", post, post_date),
    ):
        properties = ee.Feature(
            extract_sentinel1_metrics(image, glacier_roi, date, settings)
        ).toDictionary().getInfo()
        record = {column: properties.get(column) for column in expected}
        record["period"] = period
        records.append(record)
    frame = pd.DataFrame(records)
    frame["date"] = pd.to_datetime(frame["date"])
    approved, reason = require_pre_post_coverage(
        frame,
        settings.sentinel1_min_valid_area,
    )
    frame["observation_count"] = frame["mean_valid_observation_count"]
    frame["expected_observation_count"] = pd.NA
    frame["period_completeness"] = frame["valid_area_fraction"]
    frame["is_complete_period"] = approved
    frame["quality_status"] = "GOOD" if approved else "INSUFFICIENT"
    frame["quality_reason"] = reason.replace("optical", "radar")
    frame["quantitative_change_estimated"] = approved
    for column in ("vv_db", "vh_db"):
        frame[column] = pd.to_numeric(frame[column], errors="coerce")
        frame[f"{column}_change_from_pre"] = (
            frame[column] - frame[column].iloc[0] if approved else np.nan
        )
    return frame


def optical_candidate_change_polygons(
    delta: ee.Image,
    metrics: pd.DataFrame,
    glacier_roi: ee.Geometry,
    analysis_roi: ee.Geometry,
    ndsi_change_threshold: float = 0.20,
    settings: Settings = SETTINGS,
) -> ee.FeatureCollection:
    """Create QA-gated candidate spectral-change polygons with terrain context."""
    approved, reason = require_pre_post_coverage(
        metrics, settings.sentinel2_event_min_valid_area
    )
    if not approved:
        raise ValueError(reason)
    candidate = delta.select("delta_NDSI").abs().gte(
        ndsi_change_threshold
    ).selfMask().rename("candidate_change")
    vectors = candidate.reduceToVectors(
        geometry=analysis_roi,
        scale=settings.reduction_scale_m,
        geometryType="polygon",
        eightConnected=True,
        labelProperty="candidate_class",
        maxPixels=settings.max_pixels,
        tileScale=settings.tile_scale,
    )
    terrain = terrain_layers()
    drainage = hydrology_layers()["drainage_network"]

    def summarize(feature: ee.Feature) -> ee.Feature:
        geometry = feature.geometry()
        reducer = ee.Reducer.mean().combine(
            ee.Reducer.stdDev(), sharedInputs=True
        ).combine(
            ee.Reducer.percentile([5, 50, 95]), sharedInputs=True
        )
        terrain_stats = terrain["elevation"].addBands(
            terrain["slope"]
        ).reduceRegion(
            reducer=reducer,
            geometry=geometry,
            scale=settings.reduction_scale_m,
            maxPixels=settings.max_pixels,
            tileScale=settings.tile_scale,
        )
        connected = drainage.reduceRegion(
            reducer=ee.Reducer.max(),
            geometry=geometry.buffer(100),
            scale=100,
            maxPixels=settings.max_pixels,
        ).get("drainage_network")
        return feature.set(terrain_stats).set(
            {
                "area_km2": geometry.area(1).divide(1e6),
                "glacier_overlap_km2": geometry.intersection(
                    glacier_roi, 10
                ).area(1).divide(1e6),
                "distance_to_glacier_m": geometry.distance(glacier_roi, 10),
                "downstream_network_connected": ee.Algorithms.If(
                    connected, True, False
                ),
                "status": "candidate spectral-change polygon; not validated footprint",
                "ndsi_change_threshold": ndsi_change_threshold,
            }
        )

    return vectors.map(summarize)
