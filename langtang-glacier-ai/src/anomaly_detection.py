"""Seasonally adjusted unsupervised environmental anomaly detection."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np
import pandas as pd
from sklearn.cluster import KMeans
from sklearn.decomposition import PCA
from sklearn.ensemble import IsolationForest
from sklearn.metrics import silhouette_score

from .config import SETTINGS, Settings


CLIMATE_FEATURES = (
    "temp_anomaly",
    "PDD_adjusted",
    "precip_7d_adjusted",
    "antecedent_precipitation_index_adjusted",
)

SAR_CHANGE_FEATURES = (
    "VV_change_adjusted",
    "VH_change_adjusted",
)

SAR_LEVEL_FEATURES = (
    "VV_anomaly",
    "VH_anomaly",
)

OPTICAL_FEATURES = (
    "snow_fraction_anomaly",
    "snow_fraction_change_adjusted",
    "NDSI_anomaly",
)


@dataclass
class FeatureGroupResult:
    """Outputs from one complete-case unsupervised feature group."""

    scores: pd.DataFrame
    loadings: pd.DataFrame
    diagnostics: dict[str, Any]
    standardized: pd.DataFrame
    training_mask: pd.Series


def _calendar_month_anomaly(
    frame: pd.DataFrame,
    column: str,
    training_end: str,
    minimum_count: int = 3,
) -> pd.Series:
    """Subtract training-period calendar-month means without gap filling."""
    baseline = frame.loc[
        (frame["date"] < pd.Timestamp(training_end)) & frame[column].notna(),
        ["date", column],
    ].copy()
    baseline["month"] = baseline["date"].dt.month
    grouped = baseline.groupby("month")[column]
    climatology = grouped.mean().where(grouped.count() >= minimum_count)
    return frame[column] - frame["date"].dt.month.map(climatology)


def prepare_anomaly_features(
    frame: pd.DataFrame,
    settings: Settings = SETTINGS,
) -> pd.DataFrame:
    """Derive seasonally adjusted inputs while retaining original missingness."""
    prepared = frame.copy()
    prepared["date"] = pd.to_datetime(prepared["date"])
    derived = {
        "PDD": "PDD_adjusted",
        "precip_3d_max": "precip_3d_adjusted",
        "precip_7d_max": "precip_7d_adjusted",
        "precip_30d_max": "precip_30d_adjusted",
        "antecedent_precipitation_index": "antecedent_precipitation_index_adjusted",
        "VV_change": "VV_change_adjusted",
        "VH_change": "VH_change_adjusted",
        "VV": "VV_anomaly",
        "VH": "VH_anomaly",
        "snow_fraction": "snow_fraction_anomaly",
        "snow_fraction_change": "snow_fraction_change_adjusted",
        "NDSI": "NDSI_anomaly",
    }
    for raw, adjusted in derived.items():
        if adjusted not in prepared or prepared[adjusted].notna().sum() == 0:
            prepared[adjusted] = _calendar_month_anomaly(
                prepared, raw, settings.anomaly_training_end
            )
    return prepared


def _complete_training_count(
    frame: pd.DataFrame,
    features: tuple[str, ...],
    training_end: str,
) -> int:
    """Count complete reference-period rows for a candidate feature set."""
    if any(column not in frame for column in features):
        return 0
    training_period = frame["date"] < pd.Timestamp(training_end)
    return int((training_period & frame[list(features)].notna().all(axis=1)).sum())


def select_primary_features(
    frame: pd.DataFrame,
    settings: Settings = SETTINGS,
) -> tuple[tuple[str, ...], str, dict[str, int]]:
    """Prefer SAR changes, then SAR levels, while retaining a valid climate model."""
    candidates = (
        ("climate_sar_change", CLIMATE_FEATURES + SAR_CHANGE_FEATURES),
        ("climate_sar_level", CLIMATE_FEATURES + SAR_LEVEL_FEATURES),
        ("climate_only", CLIMATE_FEATURES),
    )
    counts = {
        name: _complete_training_count(
            frame, features, settings.anomaly_training_end
        )
        for name, features in candidates
    }
    for name, features in candidates:
        minimum = max(settings.anomaly_min_training_months, len(features) * 4)
        if counts[name] >= minimum:
            return features, name, counts
    raise ValueError(
        "No primary anomaly feature set has enough complete training months. "
        f"Complete-row counts are {counts}; at least "
        f"{settings.anomaly_min_training_months} climate-only months are required."
    )


def _robust_standardize(
    values: pd.DataFrame,
    training_mask: pd.Series,
) -> tuple[pd.DataFrame, pd.Series, pd.Series]:
    """Scale by training median and MAD, using IQR only for zero-MAD features."""
    training = values.loc[training_mask]
    median = training.median()
    mad = (training - median).abs().median()
    iqr_scale = (training.quantile(0.75) - training.quantile(0.25)) / 1.349
    standard_scale = training.std(ddof=0)
    scale = mad.mul(1.4826).where(mad.gt(0), iqr_scale)
    scale = scale.where(scale.gt(0), standard_scale).replace(0, np.nan)
    if scale.isna().any():
        constant = scale.index[scale.isna()].tolist()
        raise ValueError(f"Constant or invalid training features: {constant}")
    return (values - median) / scale, median, scale


def _empirical_percentile(
    values: pd.Series,
    reference_mask: pd.Series,
) -> pd.Series:
    """Map scores to [0, 1] using the empirical training distribution."""
    reference = np.sort(values.loc[reference_mask].dropna().to_numpy(dtype=float))
    result = pd.Series(np.nan, index=values.index, dtype=float)
    if len(reference) == 0:
        return result
    valid = values.notna()
    result.loc[valid] = np.searchsorted(
        reference, values.loc[valid].to_numpy(dtype=float), side="right"
    ) / len(reference)
    return result


def score_feature_group(
    frame: pd.DataFrame,
    features: tuple[str, ...],
    group_name: str,
    settings: Settings = SETTINGS,
) -> FeatureGroupResult:
    """Fit robust, Isolation Forest, and PCA scores on pre-2026 complete cases."""
    missing_columns = [column for column in features if column not in frame]
    if missing_columns:
        raise ValueError(f"Missing anomaly features: {missing_columns}")
    complete = frame.loc[:, features].notna().all(axis=1)
    training = complete & (
        frame["date"] < pd.Timestamp(settings.anomaly_training_end)
    )
    minimum = max(settings.anomaly_min_training_months, len(features) * 4)
    if int(training.sum()) < minimum:
        raise ValueError(
            f"{group_name} has {int(training.sum())} complete training months; "
            f"at least {minimum} are required."
        )

    standardized, median, scale = _robust_standardize(frame[list(features)], training)
    valid_x = standardized.loc[complete, list(features)]
    training_x = standardized.loc[training, list(features)]
    output = pd.DataFrame({"date": frame["date"]}, index=frame.index)

    robust_raw = np.sqrt(valid_x.pow(2).mean(axis=1))
    output.loc[complete, f"{group_name}_robust_raw"] = robust_raw

    isolation = IsolationForest(
        n_estimators=500,
        contamination="auto",
        random_state=settings.random_seed,
        n_jobs=1,
    ).fit(training_x)
    isolation_raw = pd.Series(
        -isolation.decision_function(valid_x), index=valid_x.index
    )
    output.loc[complete, f"{group_name}_isolation_raw"] = isolation_raw

    pca = PCA(n_components=0.90, svd_solver="full").fit(training_x)
    transformed = pca.transform(valid_x)
    reconstructed = pca.inverse_transform(transformed)
    pca_raw = pd.Series(
        np.mean(np.square(valid_x.to_numpy() - reconstructed), axis=1),
        index=valid_x.index,
    )
    output.loc[complete, f"{group_name}_pca_raw"] = pca_raw

    algorithm_columns = []
    for algorithm in ("robust", "isolation", "pca"):
        raw_column = f"{group_name}_{algorithm}_raw"
        percentile_column = f"{group_name}_{algorithm}_percentile"
        output[percentile_column] = _empirical_percentile(
            output[raw_column], training
        )
        algorithm_columns.append(percentile_column)
    output[f"{group_name}_anomaly_score"] = output[algorithm_columns].mean(
        axis=1, skipna=False
    )
    output[f"{group_name}_top_feature"] = pd.Series(
        valid_x.abs().idxmax(axis=1), index=valid_x.index
    )

    loadings = pd.DataFrame(
        pca.components_.T,
        index=features,
        columns=[f"PC{index + 1}" for index in range(pca.n_components_)],
    ).reset_index(names="feature")
    diagnostics = {
        "group": group_name,
        "features": list(features),
        "complete_months": int(complete.sum()),
        "training_months": int(training.sum()),
        "training_end_exclusive": settings.anomaly_training_end,
        "pca_components": int(pca.n_components_),
        "pca_explained_variance": float(pca.explained_variance_ratio_.sum()),
        "training_median": median.to_dict(),
        "training_scale": scale.to_dict(),
    }
    standardized_output = standardized.add_prefix(f"{group_name}_z_")
    return FeatureGroupResult(
        output, loadings, diagnostics, standardized_output, training
    )


def discover_environmental_regimes(
    standardized: pd.DataFrame,
    training_mask: pd.Series,
    random_seed: int = SETTINGS.random_seed,
) -> tuple[pd.Series, pd.DataFrame, pd.DataFrame]:
    """Select K by silhouette score, then return unlabeled cluster IDs and PCA axes."""
    complete = standardized.notna().all(axis=1)
    training = complete & training_mask
    training_x = standardized.loc[training]
    if len(training_x) < 24:
        raise ValueError("At least 24 complete training months are required for regimes.")
    diagnostics: list[dict] = []
    upper = min(6, len(training_x) - 1)
    for clusters in range(2, upper + 1):
        candidate = KMeans(
            n_clusters=clusters, random_state=random_seed, n_init=20
        ).fit(training_x)
        diagnostics.append(
            {
                "n_clusters": clusters,
                "silhouette_score": silhouette_score(
                    training_x, candidate.labels_
                ),
            }
        )
    diagnostic_frame = pd.DataFrame(diagnostics)
    best_k = int(
        diagnostic_frame.loc[
            diagnostic_frame["silhouette_score"].idxmax(), "n_clusters"
        ]
    )
    model = KMeans(n_clusters=best_k, random_state=random_seed, n_init=20).fit(
        training_x
    )
    labels = pd.Series(pd.NA, index=standardized.index, dtype="Int64")
    labels.loc[complete] = model.predict(standardized.loc[complete])

    pca = PCA(n_components=2).fit(training_x)
    coordinates = pd.DataFrame(
        np.nan, index=standardized.index, columns=["PC1", "PC2"]
    )
    coordinates.loc[complete, ["PC1", "PC2"]] = pca.transform(
        standardized.loc[complete]
    )
    return labels, coordinates, diagnostic_frame


def run_anomaly_detection(
    frame: pd.DataFrame,
    settings: Settings = SETTINGS,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, list[dict[str, Any]]]:
    """Run consistent climate-SAR and sparse multisensor anomaly experiments."""
    prepared = prepare_anomaly_features(frame, settings)
    primary_features, feature_strategy, candidate_counts = select_primary_features(
        prepared, settings
    )
    primary = score_feature_group(
        prepared, primary_features, feature_strategy, settings
    )
    primary.diagnostics["feature_strategy"] = feature_strategy
    primary.diagnostics["candidate_complete_training_months"] = candidate_counts
    requested = list(CLIMATE_FEATURES + SAR_CHANGE_FEATURES)
    primary.diagnostics["requested_features"] = requested
    primary.diagnostics["actual_features"] = list(primary_features)
    primary.diagnostics["dropped_features"] = [
        feature for feature in requested if feature not in primary_features
    ]
    primary.diagnostics["drop_reason"] = {
        feature: "insufficient complete pre-2026 coverage"
        for feature in primary.diagnostics["dropped_features"]
    }
    primary.diagnostics["training_rows"] = int(primary.training_mask.sum())
    primary.diagnostics["training_period"] = (
        f"before {settings.anomaly_training_end} (exclusive)"
    )
    outputs = prepared.copy()
    outputs = outputs.join(primary.scores.drop(columns="date"))
    outputs["anomaly_score"] = outputs[f"{feature_strategy}_anomaly_score"]
    outputs["anomaly_model_name"] = feature_strategy
    outputs["top_contributing_feature"] = outputs[
        f"{feature_strategy}_top_feature"
    ]
    directions = pd.Series(pd.NA, index=outputs.index, dtype="string")
    for index, feature in outputs["top_contributing_feature"].dropna().items():
        value = primary.standardized.loc[
            index, f"{feature_strategy}_z_{feature}"
        ]
        directions.loc[index] = "above_reference" if value >= 0 else "below_reference"
    outputs["anomaly_direction"] = directions
    outputs["anomaly_interpretation"] = "unusual environmental state"
    loadings = [primary.loadings.assign(group=feature_strategy)]
    diagnostics = [primary.diagnostics]

    try:
        multisensor_features = primary_features + OPTICAL_FEATURES
        multisensor_name = f"multisensor_{feature_strategy}"
        multisensor = score_feature_group(
            prepared, multisensor_features, multisensor_name, settings
        )
        outputs = outputs.join(multisensor.scores.drop(columns="date"))
        loadings.append(multisensor.loadings.assign(group=multisensor_name))
        diagnostics.append(multisensor.diagnostics)
    except ValueError as exc:
        diagnostics.append({"group": "multisensor", "error": str(exc)})

    labels, coordinates, cluster_diagnostics = discover_environmental_regimes(
        primary.standardized,
        primary.training_mask,
        settings.random_seed,
    )
    outputs["environmental_regime"] = labels
    outputs[["regime_PC1", "regime_PC2"]] = coordinates.to_numpy()
    threshold = outputs.loc[
        outputs["date"] < pd.Timestamp(settings.anomaly_training_end),
        "anomaly_score",
    ].quantile(settings.anomaly_reference_quantile)
    anomaly_flag = outputs["anomaly_score"].ge(threshold).astype("boolean")
    anomaly_flag.loc[outputs["anomaly_score"].isna()] = pd.NA
    outputs["anomaly_above_reference_quantile"] = anomaly_flag
    return (
        outputs,
        pd.concat(loadings, ignore_index=True),
        cluster_diagnostics,
        diagnostics,
    )
