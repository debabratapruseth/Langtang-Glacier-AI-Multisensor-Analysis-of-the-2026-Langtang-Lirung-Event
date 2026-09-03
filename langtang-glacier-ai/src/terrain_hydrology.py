"""Terrain and hydrology layers with explicit dataset provenance and caveats."""

from __future__ import annotations

from typing import Any

import ee

from .gee_utils import DATASET_IDS, get_dem


def terrain_layers() -> dict[str, ee.Image]:
    """Return elevation, slope, aspect, and finite-difference curvature layers."""
    elevation = get_dem().rename("elevation_m")
    terrain = ee.Terrain.products(elevation)
    slope = terrain.select("slope").rename("slope_deg")
    aspect = terrain.select("aspect").rename("aspect_deg")
    curvature = elevation.convolve(
        ee.Kernel.laplacian8(normalize=False)
    ).rename("curvature_index")
    return {
        "elevation": elevation,
        "slope": slope,
        "aspect": aspect,
        "curvature": curvature,
    }


def hydrology_layers(
    drainage_area_threshold_km2: float = 10.0,
) -> dict[str, ee.Image]:
    """Return MERIT Hydro direction, accumulation, HAND, and channel screening."""
    merit = ee.Image(DATASET_IDS["merit_hydro"])
    upstream_area = merit.select("upa").rename("upstream_area_km2")
    return {
        "hydrological_elevation": merit.select("elv"),
        "flow_direction": merit.select("dir"),
        "flow_accumulation": merit.select("upg"),
        "upstream_area_km2": upstream_area,
        "height_above_drainage_m": merit.select("hnd"),
        "drainage_network": upstream_area.gte(
            drainage_area_threshold_km2
        ).selfMask().rename("drainage_network"),
    }


def terrain_hydrology_provenance() -> dict[str, Any]:
    """Describe scale and limitations of terrain/hydrology products."""
    return {
        "terrain": {
            "dataset": DATASET_IDS["dem"],
            "role": "elevation/slope/aspect/curvature context",
            "limitation": "DSM; not contemporaneous event topography",
        },
        "hydrology": {
            "dataset": DATASET_IDS["merit_hydro"],
            "resolution_m": 92.77,
            "role": "flow direction, upstream area, HAND, drainage network",
            "limitation": (
                "flow direction over glaciers is documented as unreliable; "
                "network is regional context, not a validated debris pathway"
            ),
        },
        "catchment": {
            "dataset": DATASET_IDS["hydrosheds_basin_12"],
            "role": "primary hydrological basin representation",
            "limitation": "global product requiring local validation",
        },
    }
