"""Interactive and static visualizations for the analysis workflows."""

from __future__ import annotations

from pathlib import Path
from typing import Mapping

import ee
import geemap
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from .config import SETTINGS, Settings
from .gee_utils import get_dem


RGB_VIS = {"bands": ["B4", "B3", "B2"], "min": 0.02, "max": 0.35, "gamma": 1.1}
NDSI_VIS = {"min": -0.5, "max": 0.9, "palette": ["7f3b08", "f7f7f7", "2b8cbe"]}
NDVI_VIS = {"min": -0.3, "max": 0.8, "palette": ["8c510a", "f6e8c3", "01665e"]}
INDEX_DELTA_VIS = {
    "min": -0.5,
    "max": 0.5,
    "palette": ["2166ac", "f7f7f7", "b2182b"],
}
DEM_VIS = {"min": 3500, "max": 7500, "palette": ["2c7bb6", "abd9e9", "ffffbf", "fdae61", "ffffff"]}
S1_VV_VIS = {"min": -22, "max": -5, "palette": ["000000", "777777", "FFFFFF"]}
S1_VH_VIS = {"min": -30, "max": -10, "palette": ["000000", "777777", "FFFFFF"]}
S1_DELTA_VIS = {
    "min": -5,
    "max": 5,
    "palette": ["2166ac", "f7f7f7", "b2182b"],
}


def make_study_area_map(
    rois: Mapping[str, object],
    settings: Settings = SETTINGS,
) -> geemap.Map:
    """Create an interactive terrain map with separately labelled ROI roles."""
    map_ = geemap.Map()
    map_.add_basemap("Esri.WorldImagery")
    map_.addLayer(get_dem().clip(rois["context_roi"]), DEM_VIS, "Copernicus DEM", False, 0.65)
    map_.addLayer(
        ee.FeatureCollection([rois["glacier_feature"]]),
        {"color": "00FFFF", "fillColor": "00000000", "width": 3},
        "GLIMS Lirung outline",
    )
    map_.addLayer(
        ee.FeatureCollection([ee.Feature(rois["context_roi"])]),
        {"color": "FFD700", "fillColor": "00000000"},
        "15 km analysis context",
        False,
    )
    map_.addLayer(
        ee.FeatureCollection([ee.Feature(rois["downstream_context_roi"])]),
        {"color": "FF7F00", "fillColor": "00000000"},
        "25 km wider context (not event footprint)",
        False,
    )
    map_.centerObject(rois["glacier_feature"], 11)
    map_.addLayerControl()
    return map_


def add_representative_composites(
    map_: geemap.Map,
    composites: ee.ImageCollection,
    years: tuple[int, ...] = SETTINGS.representative_years,
) -> geemap.Map:
    """Add toggleable RGB and NDSI layers for representative years."""
    for year in years:
        image = ee.Image(composites.filter(ee.Filter.eq("year", year)).first())
        map_.addLayer(image, RGB_VIS, f"RGB post-monsoon {year}", year == years[-1])
        map_.addLayer(image.select("NDSI"), NDSI_VIS, f"NDSI post-monsoon {year}", False)
    return map_


def plot_snow_time_series(frame: pd.DataFrame, output: Path | None = None) -> plt.Figure:
    """Plot annual snow proxy with valid-area coverage shown explicitly."""
    fig, axes = plt.subplots(2, 1, figsize=(9, 7), sharex=True, constrained_layout=True)
    axes[0].plot(frame["date"], frame["snow_area_km2"], marker="o", color="#2171b5")
    axes[0].set_ylabel("Mapped snow proxy (km²)")
    axes[0].set_title("Lirung GLIMS ROI: post-monsoon Sentinel-2 snow proxy")
    axes[0].grid(alpha=0.25)
    axes[1].bar(frame["date"], frame["valid_area_fraction"], width=120, color="#969696")
    axes[1].axhline(0.8, color="#d7301f", linestyle="--", linewidth=1, label="80% reference")
    axes[1].set_ylabel("Valid ROI fraction")
    axes[1].set_xlabel("Year")
    axes[1].set_ylim(0, 1.05)
    axes[1].legend(frameon=False)
    if output:
        output.parent.mkdir(parents=True, exist_ok=True)
        fig.savefig(output, dpi=200, bbox_inches="tight")
    return fig


def plot_monthly_climate(
    frame: pd.DataFrame,
    output_directory: Path,
) -> tuple[plt.Figure, plt.Figure, plt.Figure]:
    """Save temperature, precipitation, and PDD climate-context figures."""
    output_directory.mkdir(parents=True, exist_ok=True)
    dates = pd.to_datetime(frame["date"])

    temperature, temp_axis = plt.subplots(figsize=(11, 4), constrained_layout=True)
    temp_axis.plot(dates, frame["temp_mean_c"], color="#636363", alpha=0.45)
    temp_axis.plot(dates, frame["temp_mean_c"].rolling(12).mean(), color="#d7301f")
    temp_axis.set(title="ERA5-Land regional temperature context", ylabel="2 m temperature (°C)")
    temp_axis.grid(alpha=0.25)
    temperature.savefig(
        output_directory / "era5_land_temperature.png", dpi=200, bbox_inches="tight"
    )

    precipitation, precip_axis = plt.subplots(figsize=(11, 4), constrained_layout=True)
    precip_axis.bar(dates, frame["precip_month_mm"], width=25, color="#3182bd")
    precip_axis.set(
        title="ERA5-Land regional precipitation context",
        ylabel="Monthly precipitation (mm)",
    )
    precip_axis.grid(axis="y", alpha=0.25)
    precipitation.savefig(
        output_directory / "era5_land_precipitation.png", dpi=200, bbox_inches="tight"
    )

    pdd, pdd_axis = plt.subplots(figsize=(11, 4), constrained_layout=True)
    pdd_axis.plot(dates, frame["pdd"], color="#f16913", linewidth=1)
    pdd_axis.set(title="ERA5-Land positive degree days", ylabel="Monthly PDD (°C day)")
    pdd_axis.grid(alpha=0.25)
    pdd.savefig(
        output_directory / "era5_land_pdd.png", dpi=200, bbox_inches="tight"
    )
    return temperature, precipitation, pdd


def plot_sentinel1_time_series(
    frame: pd.DataFrame,
    output: Path | None = None,
) -> plt.Figure:
    """Plot monthly VV/VH backscatter with scene-count quality context."""
    dates = pd.to_datetime(frame["date"])
    figure, axes = plt.subplots(
        2, 1, figsize=(11, 7), sharex=True, constrained_layout=True
    )
    axes[0].plot(dates, frame["vv_db"], color="#2166ac", label="VV")
    axes[0].plot(dates, frame["vh_db"], color="#b2182b", label="VH")
    axes[0].set_ylabel("Median-composite mean σ° (dB)")
    axes[0].set_title("Lirung ROI: comparable-track Sentinel-1 GRD")
    axes[0].legend(frameon=False)
    axes[0].grid(alpha=0.25)
    axes[1].bar(dates, frame["scene_count"], width=25, color="#969696")
    axes[1].set_ylabel("Scenes per month")
    axes[1].set_xlabel("Month")
    axes[1].grid(axis="y", alpha=0.25)
    if output:
        output.parent.mkdir(parents=True, exist_ok=True)
        figure.savefig(output, dpi=200, bbox_inches="tight")
    return figure


def plot_feature_availability(
    frame: pd.DataFrame,
    output: Path | None = None,
) -> plt.Figure:
    """Plot availability of core integrated features across the monthly calendar."""
    columns = [
        "temp_anomaly", "precip_anomaly", "PDD", "snow_fraction",
        "NDSI", "VV", "VH",
    ]
    available = [column for column in columns if column in frame]
    matrix = frame[available].notna().astype(int).to_numpy().T
    figure, axis = plt.subplots(figsize=(12, 4), constrained_layout=True)
    axis.imshow(
        matrix,
        aspect="auto",
        interpolation="nearest",
        cmap="Greens",
        vmin=0,
        vmax=1,
    )
    axis.set_yticks(range(len(available)), labels=available)
    dates = pd.to_datetime(frame["date"])
    year_positions = [index for index, date in enumerate(dates) if date.month == 1]
    year_labels = [dates.iloc[index].year for index in year_positions]
    axis.set_xticks(year_positions, labels=year_labels, rotation=45)
    axis.set_title("Integrated monthly feature availability (green = observed)")
    axis.set_xlabel("Month")
    if output:
        output.parent.mkdir(parents=True, exist_ok=True)
        figure.savefig(output, dpi=200, bbox_inches="tight")
    return figure


def plot_trend_panels(
    frame: pd.DataFrame,
    output: Path | None = None,
) -> plt.Figure:
    """Plot seasonally adjusted series and centered 12-month rolling means."""
    columns = [
        "temp_anomaly", "PDD_adjusted", "snow_fraction_anomaly", "VV_anomaly"
    ]
    available = [column for column in columns if frame[column].notna().any()]
    figure, axes = plt.subplots(
        len(available), 1, figsize=(11, 2.7 * len(available)),
        sharex=True, constrained_layout=True,
    )
    axes = np.atleast_1d(axes)
    dates = pd.to_datetime(frame["date"])
    for axis, column in zip(axes, available):
        axis.plot(dates, frame[column], color="#969696", alpha=0.5, linewidth=0.8)
        axis.plot(
            dates,
            frame[column].rolling(12, min_periods=8, center=True).mean(),
            color="#2b8cbe",
            linewidth=1.8,
            label="Centered 12-month mean",
        )
        axis.axhline(0, color="black", linewidth=0.6)
        axis.set_ylabel(column)
        axis.grid(alpha=0.2)
    axes[0].set_title("Seasonally adjusted environmental indicators")
    axes[0].legend(frameon=False)
    if output:
        output.parent.mkdir(parents=True, exist_ok=True)
        figure.savefig(output, dpi=200, bbox_inches="tight")
    return figure


def plot_correlation_heatmap(
    correlations: pd.DataFrame,
    output: Path | None = None,
) -> plt.Figure:
    """Plot a compact correlation matrix without an additional dependency."""
    figure, axis = plt.subplots(figsize=(8, 7), constrained_layout=True)
    image_ = axis.imshow(correlations.astype(float), vmin=-1, vmax=1, cmap="RdBu_r")
    labels = list(correlations.columns)
    axis.set_xticks(range(len(labels)), labels=labels, rotation=45, ha="right")
    axis.set_yticks(range(len(labels)), labels=labels)
    for row in range(len(labels)):
        for column in range(len(labels)):
            value = correlations.iloc[row, column]
            text_ = "NA" if pd.isna(value) else f"{value:.2f}"
            axis.text(column, row, text_, ha="center", va="center", fontsize=8)
    figure.colorbar(image_, ax=axis, label="Pearson r")
    axis.set_title("Pairwise seasonally adjusted correlations")
    if output:
        output.parent.mkdir(parents=True, exist_ok=True)
        figure.savefig(output, dpi=200, bbox_inches="tight")
    return figure


def plot_change_points(
    frame: pd.DataFrame,
    column: str,
    changes: pd.DataFrame,
    output: Path | None = None,
) -> plt.Figure:
    """Plot one monthly series with PELT candidate dates."""
    figure, axis = plt.subplots(figsize=(11, 4), constrained_layout=True)
    axis.plot(pd.to_datetime(frame["date"]), frame[column], color="#252525")
    if not changes.empty:
        for date in pd.to_datetime(changes["change_date"]):
            axis.axvline(date, color="#d7301f", linestyle="--", alpha=0.8)
    axis.set(title=f"PELT level-shift candidates: {column}", ylabel=column)
    axis.grid(alpha=0.2)
    if output:
        output.parent.mkdir(parents=True, exist_ok=True)
        figure.savefig(output, dpi=200, bbox_inches="tight")
    return figure


def plot_anomaly_scores(
    frame: pd.DataFrame,
    training_end: str,
    reference_quantile: float = SETTINGS.anomaly_reference_quantile,
    output: Path | None = None,
) -> plt.Figure:
    """Plot primary scores and their configured training reference quantile."""
    dates = pd.to_datetime(frame["date"])
    figure, axis = plt.subplots(figsize=(12, 5), constrained_layout=True)
    model_name = (
        str(frame["anomaly_model_name"].dropna().iloc[0])
        if "anomaly_model_name" in frame and frame["anomaly_model_name"].notna().any()
        else "climate_sar"
    )
    algorithm_columns = [
        f"{model_name}_robust_percentile",
        f"{model_name}_isolation_percentile",
        f"{model_name}_pca_percentile",
    ]
    for column in algorithm_columns:
        if column in frame:
            axis.plot(dates, frame[column], alpha=0.35, linewidth=0.8, label=column)
    axis.plot(
        dates, frame["anomaly_score"], color="#d7301f", linewidth=1.8,
        label="Ensemble anomaly score",
    )
    baseline = frame.loc[
        dates < pd.Timestamp(training_end), "anomaly_score"
    ].dropna()
    if not baseline.empty:
        axis.axhline(
            baseline.quantile(reference_quantile), color="black", linestyle="--",
            label=f"Training-period {reference_quantile:.0%} quantile",
        )
    axis.axvline(pd.Timestamp(training_end), color="#636363", linestyle=":")
    axis.set(
        title="Seasonally adjusted unsupervised environmental anomaly scores",
        ylabel="Empirical score (higher = less typical)",
        xlabel="Month",
        ylim=(0, 1.05),
    )
    axis.grid(alpha=0.2)
    axis.legend(frameon=False, ncol=2, fontsize=8)
    if output:
        output.parent.mkdir(parents=True, exist_ok=True)
        figure.savefig(output, dpi=200, bbox_inches="tight")
    return figure


def plot_environmental_regimes(
    frame: pd.DataFrame,
    output: Path | None = None,
) -> plt.Figure:
    """Plot data-derived K-means regimes in a two-component PCA projection."""
    valid = frame.dropna(
        subset=["regime_PC1", "regime_PC2", "environmental_regime"]
    )
    figure, axis = plt.subplots(figsize=(8, 6), constrained_layout=True)
    scatter = axis.scatter(
        valid["regime_PC1"],
        valid["regime_PC2"],
        c=valid["environmental_regime"].astype(int),
        cmap="tab10",
        s=28,
        alpha=0.75,
    )
    axis.set(
        title="Data-derived environmental regimes (labels are arbitrary)",
        xlabel="PCA axis 1",
        ylabel="PCA axis 2",
    )
    figure.colorbar(scatter, ax=axis, label="Cluster ID")
    axis.grid(alpha=0.2)
    if output:
        output.parent.mkdir(parents=True, exist_ok=True)
        figure.savefig(output, dpi=200, bbox_inches="tight")
    return figure


def plot_pre_event_percentiles(
    percentiles: pd.DataFrame,
    event_date: str,
    output: Path | None = None,
) -> plt.Figure:
    """Plot observed pre-event values against earlier same-month envelopes."""
    features = list(percentiles["feature"].drop_duplicates())
    columns = 2
    rows = int(np.ceil(len(features) / columns))
    figure, axes = plt.subplots(
        rows,
        columns,
        figsize=(13, 2.8 * rows),
        sharex=True,
        constrained_layout=True,
    )
    axes = np.atleast_1d(axes).ravel()
    for axis, feature in zip(axes, features):
        subset = percentiles.loc[percentiles["feature"].eq(feature)].copy()
        dates = pd.to_datetime(subset["date"])
        axis.fill_between(
            dates,
            subset["historical_q05"].astype(float),
            subset["historical_q95"].astype(float),
            color="#bdd7e7",
            alpha=0.45,
            label="Historical 5–95%",
        )
        axis.fill_between(
            dates,
            subset["historical_q25"].astype(float),
            subset["historical_q75"].astype(float),
            color="#6baed6",
            alpha=0.55,
            label="Historical 25–75%",
        )
        axis.plot(
            dates,
            subset["historical_median"],
            color="#2171b5",
            linewidth=1,
            label="Historical median",
        )
        axis.plot(
            dates,
            subset["observed"],
            color="#d7301f",
            marker="o",
            linewidth=1.5,
            label="Pre-event observation",
        )
        axis.axvline(pd.Timestamp(event_date), color="black", linestyle="--")
        axis.set_title(feature)
        axis.grid(alpha=0.2)
    for axis in axes[len(features):]:
        axis.set_visible(False)
    if features:
        axes[0].legend(frameon=False, fontsize=8, ncol=2)
    figure.suptitle("Pre-event observations versus earlier same-month conditions")
    if output:
        output.parent.mkdir(parents=True, exist_ok=True)
        figure.savefig(output, dpi=200, bbox_inches="tight")
    return figure
