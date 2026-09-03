"""Statistical trend, correlation, decomposition, and change-point analysis."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Iterable

import numpy as np
import pandas as pd
import pymannkendall as mk
import ruptures as rpt
import statsmodels.api as sm
from scipy.stats import pearsonr, spearmanr, theilslopes
from statsmodels.tsa.seasonal import STL
from statsmodels.stats.diagnostic import acorr_ljungbox
from statsmodels.stats.multitest import multipletests
from statsmodels.stats.outliers_influence import variance_inflation_factor

from .config import SETTINGS, Settings


ANALYSIS_FEATURES = {
    "temperature": "temp_anomaly",
    "precipitation": "precip_anomaly",
    "positive_degree_days": "PDD_adjusted",
    "snow_fraction": "snow_fraction_anomaly",
    "ndsi": "NDSI_anomaly",
    "sentinel1_vv": "VV_anomaly",
    "sentinel1_vh": "VH_anomaly",
}


def load_integrated_features(path: Path) -> pd.DataFrame:
    """Load and validate the integrated monthly feature table."""
    if not path.is_file():
        raise FileNotFoundError(f"Run notebook 06 first; missing table: {path}")
    frame = pd.read_csv(path, parse_dates=["date"])
    if frame.empty or frame["date"].duplicated().any():
        raise ValueError("Integrated features must be non-empty with unique dates.")
    return frame.sort_values("date").reset_index(drop=True)


def calendar_month_anomaly(
    frame: pd.DataFrame,
    column: str,
    baseline_end: str = SETTINGS.climate_baseline_end,
    minimum_count: int = 3,
) -> pd.Series:
    """Subtract a same-calendar-month baseline without filling gaps."""
    baseline = frame.loc[
        (frame["date"] < pd.Timestamp(baseline_end)) & frame[column].notna(),
        ["date", column],
    ].copy()
    baseline["month"] = baseline["date"].dt.month
    groups = baseline.groupby("month")[column]
    climatology = groups.mean().where(groups.count() >= minimum_count)
    return frame[column] - frame["date"].dt.month.map(climatology)


def build_trend_analysis_matrix(
    frame: pd.DataFrame,
    settings: Settings = SETTINGS,
) -> pd.DataFrame:
    """Assemble seasonally adjusted variables suitable for trend comparisons."""
    result = frame.copy()
    result["PDD_adjusted"] = calendar_month_anomaly(
        result, "PDD", settings.climate_baseline_end
    )
    for raw, adjusted in (
        ("snow_fraction", "snow_fraction_anomaly"),
        ("NDSI", "NDSI_anomaly"),
        ("VV", "VV_anomaly"),
        ("VH", "VH_anomaly"),
    ):
        if adjusted not in result or result[adjusted].notna().sum() == 0:
            result[adjusted] = calendar_month_anomaly(
                result, raw, settings.climate_baseline_end
            )
    return result[["date", *ANALYSIS_FEATURES.values()]]


def _valid_dated_values(
    frame: pd.DataFrame,
    column: str,
    minimum_observations: int = 24,
) -> pd.DataFrame:
    """Return finite dated observations or raise a transparent sample-size error."""
    valid = frame[["date", column]].dropna().copy()
    valid = valid[np.isfinite(valid[column])]
    if len(valid) < minimum_observations:
        raise ValueError(
            f"{column} has {len(valid)} valid observations; "
            f"at least {minimum_observations} are required."
        )
    return valid


def estimate_trend(
    frame: pd.DataFrame,
    column: str,
    hac_lags: int = 12,
) -> dict[str, float | int | str | bool]:
    """Estimate OLS-HAC, original Mann-Kendall, and Sen slope per year."""
    valid = _valid_dated_values(frame, column)
    elapsed_years = (
        valid["date"] - valid["date"].min()
    ).dt.days.to_numpy() / 365.2425
    values = valid[column].to_numpy(dtype=float)
    design = sm.add_constant(elapsed_years)
    fitted = sm.OLS(values, design).fit(
        cov_type="HAC",
        cov_kwds={"maxlags": min(hac_lags, max(1, len(valid) // 4))},
    )
    sen = theilslopes(values, elapsed_years, alpha=0.95)
    mann_kendall = mk.original_test(values)
    modified_mk = mk.hamed_rao_modification_test(values)
    lag_one_autocorrelation = (
        float(pd.Series(values).autocorr(lag=1)) if len(values) > 2 else np.nan
    )
    ljung_box = acorr_ljungbox(
        values, lags=[min(12, max(1, len(values) // 5))], return_df=True
    )
    return {
        "feature": column,
        "n": len(valid),
        "start": valid["date"].min().strftime("%Y-%m-%d"),
        "end": valid["date"].max().strftime("%Y-%m-%d"),
        "ols_slope_per_year": float(fitted.params[1]),
        "ols_hac_se": float(fitted.bse[1]),
        "ols_p_value": float(fitted.pvalues[1]),
        "ols_r_squared": float(fitted.rsquared),
        "sen_slope_per_year": float(sen.slope),
        "sen_ci_low": float(sen.low_slope),
        "sen_ci_high": float(sen.high_slope),
        "mk_trend": str(mann_kendall.trend),
        "mk_tau": float(mann_kendall.Tau),
        "mk_p_value": float(mann_kendall.p),
        "mk_significant_0_05": bool(mann_kendall.h),
        "modified_mk_trend": str(modified_mk.trend),
        "modified_mk_p_value": float(modified_mk.p),
        "modified_mk_significant_0_05": bool(modified_mk.h),
        "lag1_autocorrelation": lag_one_autocorrelation,
        "ljung_box_p_value": float(ljung_box["lb_pvalue"].iloc[0]),
    }


def build_trend_summary(
    frame: pd.DataFrame,
    columns: Iterable[str] = ANALYSIS_FEATURES.values(),
) -> pd.DataFrame:
    """Run trend estimators and retain explicit errors for sparse variables."""
    rows: list[dict] = []
    for column in columns:
        try:
            rows.append(estimate_trend(frame, column))
        except ValueError as exc:
            rows.append({"feature": column, "error": str(exc)})
    return pd.DataFrame(rows)


def correlation_tables(
    frame: pd.DataFrame,
    columns: Iterable[str] = ANALYSIS_FEATURES.values(),
    minimum_pairs: int = 24,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Calculate pairwise Pearson/Spearman correlations and valid pair counts."""
    selected = [column for column in columns if column in frame]
    pearson = pd.DataFrame(np.nan, index=selected, columns=selected)
    spearman = pearson.copy()
    counts = pd.DataFrame(0, index=selected, columns=selected, dtype=int)
    for left in selected:
        for right in selected:
            pairs = pd.DataFrame(
                {"left": frame[left], "right": frame[right]}
            ).dropna()
            counts.loc[left, right] = len(pairs)
            if len(pairs) >= minimum_pairs:
                pearson.loc[left, right] = pearsonr(
                    pairs["left"], pairs["right"]
                ).statistic
                spearman.loc[left, right] = spearmanr(
                    pairs["left"], pairs["right"]
                ).statistic
    return pearson, spearman, counts


def lagged_correlations(
    frame: pd.DataFrame,
    driver: str,
    response: str,
    maximum_lag: int = 12,
    minimum_pairs: int = 24,
) -> pd.DataFrame:
    """Correlate response(t) with driver(t-lag); positive lag means driver leads."""
    rows: list[dict] = []
    for lag in range(0, maximum_lag + 1):
        pairs = pd.DataFrame(
            {"driver": frame[driver].shift(lag), "response": frame[response]}
        ).dropna()
        if len(pairs) >= minimum_pairs:
            correlation, p_value = pearsonr(pairs["driver"], pairs["response"])
        else:
            correlation, p_value = np.nan, np.nan
        rows.append(
            {
                "driver": driver,
                "response": response,
                "lag_months": lag,
                "n_pairs": len(pairs),
                "pearson_r": correlation,
                "p_value": p_value,
            }
        )
    result = pd.DataFrame(rows)
    valid = result["p_value"].notna()
    result["p_value_fdr_bh"] = np.nan
    result["significant_fdr_0_05"] = False
    if valid.any():
        rejected, adjusted, _, _ = multipletests(
            result.loc[valid, "p_value"], alpha=0.05, method="fdr_bh"
        )
        result.loc[valid, "p_value_fdr_bh"] = adjusted
        result.loc[valid, "significant_fdr_0_05"] = rejected
    result["lag_definition"] = "response(t) versus driver(t-lag); positive=driver leads"
    return result


def trend_quality_sensitivity(
    frame: pd.DataFrame,
    column: str,
    quality_column: str,
    accepted_statuses: tuple[str, ...] = ("GOOD", "CAUTION"),
) -> pd.DataFrame:
    """Compare trend estimates before and after explicit quality filtering."""
    rows = []
    for label, subset in (
        ("all_available", frame),
        (
            "quality_filtered",
            frame.loc[frame[quality_column].isin(accepted_statuses)],
        ),
    ):
        try:
            rows.append({"quality_filter": label, **estimate_trend(subset, column)})
        except ValueError as exc:
            rows.append({"quality_filter": label, "feature": column, "error": str(exc)})
    return pd.DataFrame(rows)


def multivariate_snow_regression(
    frame: pd.DataFrame,
    response: str = "snow_fraction_anomaly",
    predictors: tuple[str, ...] = (
        "temp_anomaly",
        "PDD_adjusted",
        "precip_anomaly",
    ),
) -> tuple[pd.DataFrame, dict[str, float | int]]:
    """Fit optional OLS-HAC snow model and report predictor multicollinearity."""
    columns = [response, *predictors]
    data = frame[columns].replace([np.inf, -np.inf], np.nan).dropna()
    if len(data) < max(36, len(predictors) * 10):
        raise ValueError("Insufficient complete rows for multivariate snow regression.")
    design = sm.add_constant(data[list(predictors)])
    model = sm.OLS(data[response], design).fit(
        cov_type="HAC", cov_kwds={"maxlags": 12}
    )
    vif = {
        predictor: float(variance_inflation_factor(data[list(predictors)].values, index))
        for index, predictor in enumerate(predictors)
    }
    coefficients = pd.DataFrame(
        {
            "term": model.params.index,
            "coefficient": model.params.values,
            "hac_se": model.bse.values,
            "p_value": model.pvalues.values,
        }
    )
    diagnostics = {
        "n": int(len(data)),
        "r_squared": float(model.rsquared),
        "maximum_vif": max(vif.values()),
        **{f"vif_{key}": value for key, value in vif.items()},
    }
    return coefficients, diagnostics


def _trimmed_monthly_series(frame: pd.DataFrame, column: str) -> pd.Series:
    """Trim unavailable endpoints while retaining internal gaps for validation."""
    series = frame.set_index("date")[column].asfreq("MS")
    first = series.first_valid_index()
    last = series.last_valid_index()
    if first is None or last is None:
        raise ValueError(f"{column} contains no valid monthly observations.")
    return series.loc[first:last]


def stl_decomposition(
    frame: pd.DataFrame,
    column: str,
    period: int = 12,
) -> Any:
    """Run robust STL only on a complete, consecutive monthly series."""
    series = _trimmed_monthly_series(frame, column)
    if series.isna().any():
        raise ValueError(f"STL skipped for {column}: monthly gaps are present.")
    if len(series) < period * 3:
        raise ValueError(f"STL skipped for {column}: fewer than three cycles.")
    return STL(series, period=period, robust=True).fit()


def detect_change_points(
    frame: pd.DataFrame,
    column: str,
    penalty_multiplier: float = 3.0,
    minimum_segment_months: int = 12,
) -> pd.DataFrame:
    """Detect level shifts with PELT and return diagnostics, not confidence."""
    series = _trimmed_monthly_series(frame, column)
    if series.isna().any():
        raise ValueError(f"Change-point analysis skipped for {column}: gaps present.")
    if len(series) < minimum_segment_months * 3:
        raise ValueError(f"Change-point analysis skipped for {column}: series too short.")
    scale = float(series.std(ddof=0))
    if not np.isfinite(scale) or scale == 0:
        raise ValueError(f"Change-point analysis skipped for {column}: zero variance.")
    standardized = ((series - series.mean()) / scale).to_numpy()
    penalty = penalty_multiplier * np.log(len(series))
    endpoints = rpt.Pelt(
        model="l2", min_size=minimum_segment_months, jump=1
    ).fit(standardized).predict(pen=penalty)
    rows: list[dict] = []
    for endpoint in endpoints[:-1]:
        before = series.iloc[max(0, endpoint - minimum_segment_months) : endpoint]
        after = series.iloc[
            endpoint : min(len(series), endpoint + minimum_segment_months)
        ]
        rows.append(
            {
                "feature": column,
                "change_date": series.index[endpoint].strftime("%Y-%m-%d"),
                "magnitude_after_minus_before": float(after.mean() - before.mean()),
                "penalty": float(penalty),
                "minimum_segment_months": minimum_segment_months,
                "diagnostic": "PELT l2 level-shift candidate; not a confidence score",
            }
        )
    return pd.DataFrame(rows)
