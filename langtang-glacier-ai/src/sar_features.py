"""Comparable-track Sentinel-1 GRD composites and backscatter metrics."""

from __future__ import annotations

from typing import Any

import ee
import numpy as np
import pandas as pd

from .config import SETTINGS, Settings
from .gee_utils import DATASET_IDS
from .gee_utils import get_dem


def get_sentinel1_base_collection(
    roi: ee.Geometry,
    start: str,
    end: str,
) -> ee.ImageCollection:
    """Return dual-polarization, 10 m, IW Sentinel-1 GRD scenes."""
    return (
        ee.ImageCollection(DATASET_IDS["sentinel1_grd"])
        .filterBounds(roi)
        .filterDate(start, end)
        .filter(ee.Filter.eq("instrumentMode", "IW"))
        .filter(ee.Filter.eq("resolution_meters", 10))
        .filter(ee.Filter.listContains("transmitterReceiverPolarisation", "VV"))
        .filter(ee.Filter.listContains("transmitterReceiverPolarisation", "VH"))
    )


def _largest_histogram_key(histogram: dict[str, Any], label: str) -> str:
    """Return the most frequent deterministic key in an EE histogram."""
    if not histogram:
        raise ValueError(f"No Sentinel-1 {label} candidates were found.")
    return max(sorted(histogram), key=lambda key: histogram[key])


def choose_sentinel1_track(
    roi: ee.Geometry,
    settings: Settings = SETTINGS,
) -> dict[str, Any]:
    """Choose a QA-ranked track or explicit override; never use scene count alone."""
    qa_path = settings.output_qa / "sentinel1_candidate_track_qa.csv"
    if (
        settings.sentinel1_orbit_pass is None
        and settings.sentinel1_relative_orbit is None
    ):
        if not qa_path.is_file():
            raise ValueError(
                "Sentinel-1 track QA is required before selection. Run "
                "diagnose_sentinel1_candidates and save its QA table."
            )
        return select_sentinel1_candidate(pd.read_csv(qa_path), settings)
    base = get_sentinel1_base_collection(
        roi, settings.sentinel1_start, settings.sentinel1_end
    )
    pass_histogram = base.aggregate_histogram("orbitProperties_pass").getInfo()
    if settings.sentinel1_orbit_pass is None:
        raise ValueError("Both Sentinel-1 pass and relative orbit must be overridden.")
    orbit_pass = settings.sentinel1_orbit_pass
    pass_collection = base.filter(ee.Filter.eq("orbitProperties_pass", orbit_pass))
    orbit_histogram = pass_collection.aggregate_histogram(
        "relativeOrbitNumber_start"
    ).getInfo()
    if settings.sentinel1_relative_orbit is None:
        raise ValueError("Both Sentinel-1 pass and relative orbit must be overridden.")
    relative_orbit = settings.sentinel1_relative_orbit

    selected_count = int(
        pass_collection.filter(
            ee.Filter.eq("relativeOrbitNumber_start", relative_orbit)
        ).size().getInfo()
    )
    if selected_count == 0:
        raise ValueError(
            f"No scenes found for {orbit_pass} relative orbit {relative_orbit}. "
            f"Available track histogram: {orbit_histogram}"
        )
    return {
        "orbit_pass": orbit_pass,
        "relative_orbit": relative_orbit,
        "scene_count": selected_count,
        "pass_histogram": pass_histogram,
        "orbit_histogram": orbit_histogram,
    }


def get_comparable_sentinel1_collection(
    roi: ee.Geometry,
    start: str,
    end: str,
    track: dict[str, Any],
    settings: Settings = SETTINGS,
    angle_mode: str = "fixed",
    robust_angle_range: tuple[float, float] | None = None,
) -> ee.ImageCollection:
    """Filter to one acquisition geometry and mask extreme ellipsoid angles."""
    if angle_mode not in ("none", "fixed", "robust"):
        raise ValueError("angle_mode must be none, fixed, or robust.")
    if angle_mode == "robust" and robust_angle_range is None:
        raise ValueError("robust angle mode requires robust_angle_range.")
    collection = (
        get_sentinel1_base_collection(roi, start, end)
        .filter(ee.Filter.eq("orbitProperties_pass", track["orbit_pass"]))
        .filter(
            ee.Filter.eq("relativeOrbitNumber_start", track["relative_orbit"])
        )
    )

    def mask_geometry(image: ee.Image) -> ee.Image:
        angle = image.select("angle")
        if angle_mode == "none":
            angle_mask = ee.Image(1)
        elif angle_mode == "robust":
            angle_mask = angle.gte(robust_angle_range[0]).And(
                angle.lte(robust_angle_range[1])
            )
        else:
            angle_mask = angle.gte(settings.sentinel1_angle_min_deg).And(
                angle.lte(settings.sentinel1_angle_max_deg)
            )
        valid = image.select(["VV", "VH"]).mask().reduce(ee.Reducer.min())
        terrain_valid = radar_shadow_layover_mask(
            image, track["orbit_pass"]
        )
        return (
            image.select(["VV", "VH", "angle"])
            .updateMask(angle_mask.And(valid).And(terrain_valid))
            .copyProperties(image, image.propertyNames())
        )

    return collection.map(mask_geometry)


def make_sentinel1_composite(
    roi: ee.Geometry,
    start: str,
    end: str,
    track: dict[str, Any],
    settings: Settings = SETTINGS,
    angle_mode: str = "fixed",
    robust_angle_range: tuple[float, float] | None = None,
) -> ee.Image:
    """Build a median dB composite with a valid-observation count band."""
    collection = get_comparable_sentinel1_collection(
        roi, start, end, track, settings, angle_mode, robust_angle_range
    )
    count = collection.size()
    empty = (
        ee.Image.constant([0, 0, 0])
        .rename(["VV", "VH", "angle"])
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
            collection.select("VV").count().rename("valid_observation_count"),
            empty_count,
        )
    )
    return composite.addBands(valid_count).set(
        {
            "scene_count": count,
            "period_start": start,
            "period_end": end,
            "orbit_pass": track["orbit_pass"],
            "relative_orbit": track["relative_orbit"],
        }
    )


def extract_sentinel1_metrics(
    composite: ee.Image,
    roi: ee.Geometry,
    date: str,
    settings: Settings = SETTINGS,
) -> ee.Feature:
    """Reduce one SAR composite to backscatter and transparent QA metrics."""
    valid_area = (
        ee.Image.pixelArea()
        .updateMask(composite.select("VV").mask())
        .rename("valid_m2")
    )
    metrics = composite.select(
        ["VV", "VH", "angle", "valid_observation_count"]
    ).addBands(valid_area)
    reducer = ee.Reducer.mean().combine(
        reducer2=ee.Reducer.stdDev(), sharedInputs=True
    ).combine(reducer2=ee.Reducer.sum(), sharedInputs=True)
    stats = metrics.reduceRegion(
        reducer=reducer,
        geometry=roi,
        scale=settings.sentinel1_reduction_scale_m,
        maxPixels=settings.max_pixels,
        tileScale=settings.tile_scale,
    )
    valid_m2 = ee.Number(
        ee.Algorithms.If(stats.get("valid_m2_sum"), stats.get("valid_m2_sum"), 0)
    )
    return ee.Feature(
        None,
        {
            "date": date,
            "vv_db": stats.get("VV_mean"),
            "vv_std_db": stats.get("VV_stdDev"),
            "vh_db": stats.get("VH_mean"),
            "vh_std_db": stats.get("VH_stdDev"),
            "angle_deg": stats.get("angle_mean"),
            "mean_valid_observation_count": stats.get(
                "valid_observation_count_mean"
            ),
            "valid_area_fraction": valid_m2.divide(roi.area(1)),
            "scene_count": composite.get("scene_count"),
            "missing_data_flag": valid_m2.eq(0),
            "orbit_pass": composite.get("orbit_pass"),
            "relative_orbit": composite.get("relative_orbit"),
        },
    )


def build_monthly_sentinel1_series(
    roi: ee.Geometry,
    track: dict[str, Any],
    settings: Settings = SETTINGS,
) -> tuple[ee.ImageCollection, ee.FeatureCollection]:
    """Build monthly median composites and metrics over the configured period."""
    first_month = pd.Timestamp(settings.sentinel1_start).to_period("M").start_time
    end = min(
        pd.Timestamp(settings.sentinel1_end),
        pd.Timestamp.now().normalize().to_period("M").start_time,
    )
    months = pd.date_range(first_month, end, freq="MS", inclusive="left")
    composites: list[ee.Image] = []
    features: list[ee.Feature] = []
    for month in months:
        next_month = month + pd.offsets.MonthBegin(1)
        start_text = month.strftime("%Y-%m-%d")
        end_text = min(next_month, end).strftime("%Y-%m-%d")
        composite = make_sentinel1_composite(
            roi, start_text, end_text, track, settings
        ).set("system:time_start", ee.Date(start_text).millis())
        composites.append(composite)
        features.append(
            extract_sentinel1_metrics(composite, roi, start_text, settings)
        )
    return ee.ImageCollection.fromImages(composites), ee.FeatureCollection(features)


def sentinel1_features_to_dataframe(
    features: ee.FeatureCollection,
    minimum_usable_months: int = SETTINGS.sentinel1_min_usable_months,
    required_valid_area: float = SETTINGS.sentinel1_min_valid_area,
    enforce_coverage: bool = True,
) -> pd.DataFrame:
    """Download monthly SAR metrics and add month-to-month dB differences."""
    payload = features.getInfo()
    rows = [feature.get("properties", {}) for feature in payload.get("features", [])]
    if not rows:
        raise ValueError("Earth Engine returned no monthly Sentinel-1 metrics.")
    frame = pd.DataFrame(rows).sort_values("date").reset_index(drop=True)
    frame["date"] = pd.to_datetime(frame["date"])
    for column in ("vv_db", "vh_db", "valid_area_fraction"):
        if column not in frame:
            frame[column] = pd.NA
        frame[column] = pd.to_numeric(frame[column], errors="coerce")
    usable = (
        frame[["vv_db", "vh_db"]].notna().all(axis=1)
        & frame["valid_area_fraction"].ge(required_valid_area)
    )
    frame["is_complete_period"] = usable
    frame["period_completeness"] = frame["valid_area_fraction"]
    frame["expected_observation_count"] = pd.NA
    frame["observation_count"] = frame["mean_valid_observation_count"]
    frame["quality_status"] = usable.map({True: "GOOD", False: "INSUFFICIENT"})
    frame["quality_reason"] = usable.map(
        {
            True: "VV/VH and ROI coverage pass requirements",
            False: "missing VV/VH or valid ROI coverage below threshold",
        }
    )
    if enforce_coverage and int(usable.sum()) < minimum_usable_months:
        source_scenes = pd.to_numeric(frame["scene_count"], errors="coerce").sum()
        raise ValueError(
            f"Sentinel-1 source contains {int(source_scenes)} scene-month records "
            f"but only {int(usable.sum())} usable months; at least "
            f"{minimum_usable_months} are required. Run track/angle QA."
        )
    frame["vv_change_db"] = frame["vv_db"].diff()
    frame["vh_change_db"] = frame["vh_db"].diff()
    return frame


def enumerate_sentinel1_candidates(
    roi: ee.Geometry,
    settings: Settings = SETTINGS,
    event_date: str | None = None,
) -> list[dict[str, Any]]:
    """Enumerate pass/orbit candidates with scene dates and event availability."""
    collection = get_sentinel1_base_collection(
        roi, settings.sentinel1_start, settings.sentinel1_end
    )
    passes = collection.aggregate_array("orbitProperties_pass").distinct().getInfo()
    candidates = []
    event_text = event_date or settings.event_date or settings.documented_event_date
    event = pd.Timestamp(event_text) if event_text else None
    for orbit_pass in sorted(passes):
        pass_collection = collection.filter(
            ee.Filter.eq("orbitProperties_pass", orbit_pass)
        )
        orbits = pass_collection.aggregate_array(
            "relativeOrbitNumber_start"
        ).distinct().getInfo()
        for orbit in sorted(int(value) for value in orbits):
            selected = pass_collection.filter(
                ee.Filter.eq("relativeOrbitNumber_start", orbit)
            )
            times = selected.aggregate_array("system:time_start").getInfo()
            dates = pd.to_datetime(times, unit="ms", utc=True).tz_localize(None)
            candidates.append(
                {
                    "orbit_pass": orbit_pass,
                    "relative_orbit": orbit,
                    "total_scenes": len(dates),
                    "first_acquisition": dates.min().strftime("%Y-%m-%d"),
                    "last_acquisition": dates.max().strftime("%Y-%m-%d"),
                    "temporal_coverage_days": int((dates.max() - dates.min()).days),
                    "event_date": event_text,
                    "event_source": settings.documented_event_source,
                    "pre_event_scenes_60d": (
                        int(((dates < event) & (dates >= event - pd.Timedelta(days=60))).sum())
                        if event is not None else None
                    ),
                    "post_event_scenes_60d": (
                        int(((dates > event) & (dates <= event + pd.Timedelta(days=60))).sum())
                        if event is not None else None
                    ),
                }
            )
    return candidates


def angle_mask_sensitivity(
    roi: ee.Geometry,
    track: dict[str, Any],
    start: str,
    end: str,
    settings: Settings = SETTINGS,
) -> pd.DataFrame:
    """Compare no, fixed, and data-derived angle masks for one track/period."""
    raw = get_comparable_sentinel1_collection(
        roi, start, end, track, settings, angle_mode="none"
    )
    angle_stats = raw.select("angle").median().reduceRegion(
        reducer=ee.Reducer.percentile([2, 98]),
        geometry=roi,
        scale=settings.sentinel1_reduction_scale_m,
        maxPixels=settings.max_pixels,
        tileScale=settings.tile_scale,
    ).getInfo()
    robust_range = (
        float(angle_stats["angle_p2"]),
        float(angle_stats["angle_p98"]),
    )
    rows = []
    for mode in ("none", "fixed", "robust"):
        composite = make_sentinel1_composite(
            roi,
            start,
            end,
            track,
            settings,
            angle_mode=mode,
            robust_angle_range=robust_range if mode == "robust" else None,
        )
        properties = ee.Feature(
            extract_sentinel1_metrics(composite, roi, start, settings)
        ).toDictionary().getInfo()
        rows.append(
            {
                "angle_mode": mode,
                "angle_min": robust_range[0] if mode == "robust" else (
                    settings.sentinel1_angle_min_deg if mode == "fixed" else None
                ),
                "angle_max": robust_range[1] if mode == "robust" else (
                    settings.sentinel1_angle_max_deg if mode == "fixed" else None
                ),
                "scene_count": properties.get("scene_count"),
                "valid_area_fraction": properties.get("valid_area_fraction"),
                "mean_angle": properties.get("angle_deg"),
            }
        )
    return pd.DataFrame(rows)


def select_sentinel1_candidate(
    qa: pd.DataFrame,
    settings: Settings = SETTINGS,
) -> dict[str, Any]:
    """Select a track from measured usability, coverage, span, and consistency."""
    required = {
        "orbit_pass",
        "relative_orbit",
        "usable_months",
        "median_valid_area_fraction",
        "temporal_coverage_days",
    }
    missing = required.difference(qa.columns)
    if missing:
        raise ValueError(f"Sentinel-1 candidate QA lacks columns: {sorted(missing)}")
    candidates = qa.copy()
    candidates = candidates.loc[
        candidates["usable_months"].ge(settings.sentinel1_min_usable_months)
        & candidates["median_valid_area_fraction"].ge(
            settings.sentinel1_min_valid_area
        )
    ]
    if candidates.empty:
        raise ValueError(
            "Sentinel-1 scenes exist but no candidate passes usable-month and ROI "
            "coverage requirements. Do not emit a mostly-null time series."
        )
    for column in (
        "usable_months",
        "median_valid_area_fraction",
        "temporal_coverage_days",
    ):
        maximum = candidates[column].max()
        candidates[f"_{column}_score"] = (
            candidates[column] / maximum if maximum > 0 else 0
        )
    if {"incidence_angle_p05", "incidence_angle_p95"}.issubset(candidates):
        spread = (
            candidates["incidence_angle_p95"]
            - candidates["incidence_angle_p05"]
        ).clip(lower=0)
        candidates["_geometry_consistency_score"] = 1 / (1 + spread)
        candidates["selection_score"] = (
            0.40 * candidates["_usable_months_score"]
            + 0.30 * candidates["_median_valid_area_fraction_score"]
            + 0.20 * candidates["_temporal_coverage_days_score"]
            + 0.10 * candidates["_geometry_consistency_score"]
        )
    else:
        candidates["selection_score"] = (
            0.45 * candidates["_usable_months_score"]
            + 0.35 * candidates["_median_valid_area_fraction_score"]
            + 0.20 * candidates["_temporal_coverage_days_score"]
        )
    best = candidates.sort_values(
        ["selection_score", "median_valid_area_fraction", "usable_months"],
        ascending=False,
    ).iloc[0]
    return {
        "orbit_pass": best["orbit_pass"],
        "relative_orbit": int(best["relative_orbit"]),
        "selection_score": float(best["selection_score"]),
        "selection_method": "usable_coverage_temporal_geometry_score",
    }


def diagnose_sentinel1_candidates(
    roi: ee.Geometry,
    settings: Settings = SETTINGS,
    event_date: str | None = None,
) -> pd.DataFrame:
    """Evaluate monthly ROI usability for every pass/orbit candidate sequentially."""
    rows = []
    candidates = enumerate_sentinel1_candidates(roi, settings, event_date)
    complete_month_end = min(
        pd.Timestamp(settings.sentinel1_end),
        pd.Timestamp.now().normalize().to_period("M").start_time,
    )
    months = pd.date_range(
        pd.Timestamp(settings.sentinel1_start).to_period("M").start_time,
        complete_month_end,
        freq="MS",
        inclusive="left",
    )
    for candidate in candidates:
        track = {
            "orbit_pass": candidate["orbit_pass"],
            "relative_orbit": candidate["relative_orbit"],
        }
        monthly_rows = []
        for month in months:
            end = min(month + pd.offsets.MonthBegin(1), complete_month_end)
            composite = make_sentinel1_composite(
                roi,
                month.strftime("%Y-%m-%d"),
                end.strftime("%Y-%m-%d"),
                track,
                settings,
            )
            properties = ee.Feature(
                extract_sentinel1_metrics(
                    composite, roi, month.strftime("%Y-%m-%d"), settings
                )
            ).toDictionary().getInfo()
            monthly_rows.append(properties)
        monthly = pd.DataFrame(monthly_rows)
        for column in ("valid_area_fraction", "angle_deg", "vv_db", "vh_db"):
            if column not in monthly:
                monthly[column] = np.nan
            monthly[column] = pd.to_numeric(monthly[column], errors="coerce")
        usable = (
            monthly[["vv_db", "vh_db"]].notna().all(axis=1)
            & monthly["valid_area_fraction"].ge(settings.sentinel1_min_valid_area)
        )
        rows.append(
            {
                **candidate,
                "usable_months": int(usable.sum()),
                "median_valid_area_fraction": float(
                    monthly["valid_area_fraction"].median()
                ),
                "median_incidence_angle": float(monthly["angle_deg"].median()),
                "incidence_angle_p05": float(monthly["angle_deg"].quantile(0.05)),
                "incidence_angle_p95": float(monthly["angle_deg"].quantile(0.95)),
            }
        )
        print(
            "Sentinel-1 QA complete:",
            candidate["orbit_pass"],
            candidate["relative_orbit"],
        )
    return pd.DataFrame(rows)


def radar_shadow_layover_mask(
    image: ee.Image,
    orbit_pass: str,
) -> ee.Image:
    """Return an approximate valid-geometry mask from DEM slope and radar look.

    This masks unavoidable geometric shadow/layover for screening. It is not
    radiometric terrain normalization and does not create InSAR information.
    """
    terrain = ee.Terrain.products(get_dem())
    slope = terrain.select("slope").multiply(np.pi / 180)
    aspect = terrain.select("aspect").multiply(np.pi / 180)
    incidence = image.select("angle").multiply(np.pi / 180)
    look_azimuth = 77.0 if orbit_pass == "ASCENDING" else 283.0
    relative_aspect = aspect.subtract(look_azimuth * np.pi / 180).cos()
    range_slope = slope.tan().multiply(relative_aspect).atan()
    layover = range_slope.gt(incidence)
    shadow = range_slope.lt(incidence.subtract(np.pi / 2))
    return layover.Or(shadow).Not().rename("valid_radar_geometry")


def sentinel1_difference(
    roi: ee.Geometry,
    pre_start: str,
    pre_end: str,
    post_start: str,
    post_end: str,
    track: dict[str, Any],
    settings: Settings = SETTINGS,
) -> tuple[ee.Image, ee.Image, ee.Image]:
    """Return comparable pre, post, and post-minus-pre dB composites."""
    pre = make_sentinel1_composite(roi, pre_start, pre_end, track, settings)
    post = make_sentinel1_composite(roi, post_start, post_end, track, settings)
    pre_count = int(ee.Number(pre.get("scene_count")).getInfo())
    post_count = int(ee.Number(post.get("scene_count")).getInfo())
    if pre_count == 0 or post_count == 0:
        raise ValueError(
            "Sentinel-1 pre/post comparison requires observations in both windows; "
            f"found pre={pre_count}, post={post_count}."
        )
    delta = (
        post.select(["VV", "VH"])
        .subtract(pre.select(["VV", "VH"]))
        .rename(["delta_VV", "delta_VH"])
    )
    return pre, post, delta
