"""Earth Engine initialization, ROI, and defensive server-side helpers."""

from __future__ import annotations

from typing import Any, Optional

import ee

from .config import SETTINGS, Settings


DATASET_IDS = {
    "glims": "GLIMS/current",
    "sentinel2_sr": "COPERNICUS/S2_SR_HARMONIZED",
    "cloud_score_plus": "GOOGLE/CLOUD_SCORE_PLUS/V1/S2_HARMONIZED",
    "dem": "COPERNICUS/DEM/GLO30_2024_1",
    "era5_land_daily": "ECMWF/ERA5_LAND/DAILY_AGGR",
    "sentinel1_grd": "COPERNICUS/S1_GRD",
    "merit_hydro": "MERIT/Hydro/v1_0_1",
    "hydrosheds_basin_12": "WWF/HydroSHEDS/v1/Basins/hybas_12",
}


def initialize_earth_engine(
    project: Optional[str] = None,
    authenticate: bool = False,
) -> None:
    """Initialize Earth Engine, optionally starting interactive authentication.

    In Colab call this with ``authenticate=True`` on the first run. Authentication
    is never attempted silently because it requires user interaction.
    """
    if authenticate:
        ee.Authenticate()
    kwargs = {"project": project} if project else {}
    try:
        ee.Initialize(**kwargs)
    except Exception as exc:
        raise RuntimeError(
            "Earth Engine initialization failed. Authenticate, confirm that the "
            "Cloud project is registered for Earth Engine, and set SETTINGS.ee_project."
        ) from exc


def _newest_feature(collection: ee.FeatureCollection) -> ee.Feature:
    """Return the newest GLIMS record, treating malformed dates as old."""
    def add_sort_date(feature: ee.Feature) -> ee.Feature:
        date_text = ee.String(
            ee.Algorithms.If(
                feature.get("src_date"), feature.get("src_date"), "1900-01-01"
            )
        )
        return feature.set("_sort_date", ee.Date(date_text).millis())

    return ee.Feature(collection.map(add_sort_date).sort("_sort_date", False).first())


def get_lirung_glacier(settings: Settings = SETTINGS) -> ee.Feature:
    """Resolve Lirung Glacier using documented IDs, then a guarded name fallback.

    GLIMS IDs encode a representative coordinate and can change between inventory
    vintages. The resolver therefore checks the later published ID, then documented
    legacy IDs. Only glacier-boundary records near the Lirung anchor are eligible.
    No synthetic polygon or unverified neighboring glacier is substituted.
    """
    anchor = ee.Geometry.Point(
        [settings.glacier_anchor_lon, settings.glacier_anchor_lat]
    )
    nearby_boundaries = (
        ee.FeatureCollection(DATASET_IDS["glims"])
        .filterBounds(anchor.buffer(6_000))
        .filter(ee.Filter.eq("line_type", "glac_bound"))
    )
    for glacier_id in (settings.glims_id, *settings.glims_legacy_ids):
        matches = nearby_boundaries.filter(ee.Filter.eq("glac_id", glacier_id))
        count = int(matches.size().getInfo())
        if count:
            return _newest_feature(matches).set(
                {
                    "roi_role": "glacier_inventory_outline",
                    "record_count": count,
                    "roi_selected_by": "documented_glims_id",
                    "configured_glims_id": glacier_id,
                }
            )

    # Some GLIMS vintages retain the name while changing the coordinate-based ID.
    named = nearby_boundaries.filter(ee.Filter.eq("glac_name", "Lirung"))
    named_count = int(named.size().getInfo())
    named_ids = named.aggregate_array("glac_id").distinct().getInfo()
    if named_count and len(named_ids) == 1:
        return _newest_feature(named).set(
            {
                "roi_role": "glacier_inventory_outline",
                "record_count": named_count,
                "roi_selected_by": "unique_nearby_name",
                "configured_glims_id": settings.glims_id,
            }
        )

    diagnostic = nearby_boundaries.limit(20).aggregate_array("glac_id").getInfo()
    raise LookupError(
        "No unambiguous Lirung outline was found in GLIMS/current using documented "
        f"IDs {(settings.glims_id, *settings.glims_legacy_ids)} or the unique nearby "
        f"name 'Lirung'. Nearby glacier-boundary IDs include: {diagnostic}"
    )


def build_rois(settings: Settings = SETTINGS) -> dict[str, Any]:
    """Build distinct authoritative glacier and contextual geometries."""
    glacier = get_lirung_glacier(settings)
    glacier_geometry = glacier.geometry()
    anchor = ee.Geometry.Point(
        [settings.glacier_anchor_lon, settings.glacier_anchor_lat]
    )
    hydrological_basin = ee.Feature(
        ee.FeatureCollection(DATASET_IDS["hydrosheds_basin_12"])
        .filterBounds(anchor)
        .sort("UP_AREA")
        .first()
    )
    stable_control = glacier_geometry.buffer(5_000).difference(
        glacier_geometry.buffer(1_000), 30
    )
    return {
        "glacier_feature": glacier,
        "glacier_roi": glacier_geometry,
        "context_roi": glacier_geometry.buffer(settings.context_buffer_m).bounds(),
        "downstream_context_roi": glacier_geometry.buffer(
            settings.downstream_buffer_m
        ).bounds(),
        "hydrological_catchment_roi": hydrological_basin.geometry(),
        "stable_control_candidate_roi": stable_control,
        "suspected_source_zone_roi": None,
        "avalanche_debris_pathway_roi": None,
        "roi_provenance": {
            "glacier_roi": "GLIMS/current documented Lirung inventory outline",
            "context_roi": "15 km visual buffer; not hydrological",
            "downstream_context_roi": "25 km visual buffer; not event footprint",
            "hydrological_catchment_roi": (
                "HydroSHEDS level-12 basin containing documented Lirung anchor"
            ),
            "stable_control_candidate_roi": (
                "derived 1-5 km annulus; candidate only, not field-validated stable"
            ),
            "suspected_source_zone_roi": "UNSET; requires external validated geometry",
            "avalanche_debris_pathway_roi": "UNSET; requires external validation",
        },
    }


def get_dem() -> ee.Image:
    """Return Copernicus GLO-30 DSM with its native projection retained."""
    collection = ee.ImageCollection(DATASET_IDS["dem"])
    projection = ee.Image(collection.first()).select("DEM").projection()
    return collection.mosaic().select("DEM").setDefaultProjection(projection)


def collection_size(collection: ee.ImageCollection, label: str) -> int:
    """Evaluate collection size and fail early with a meaningful message."""
    count = int(collection.size().getInfo())
    if count == 0:
        raise ValueError(f"No images found for {label}; check dates, ROI, and filters.")
    return count
