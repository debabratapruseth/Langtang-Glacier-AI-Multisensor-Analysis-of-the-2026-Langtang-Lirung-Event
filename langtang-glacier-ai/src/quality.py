"""Central, reusable data-quality and provenance utilities."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Iterable

import numpy as np
import pandas as pd


GOOD = "GOOD"
CAUTION = "CAUTION"
INSUFFICIENT = "INSUFFICIENT"


@dataclass(frozen=True)
class QualityAssessment:
    """Machine-readable quality decision for one observation or period."""

    valid_area_fraction: float | None
    observation_count: int | None
    expected_observation_count: int | None
    period_completeness: float | None
    is_complete_period: bool
    quality_status: str
    quality_reason: str

    def as_dict(self) -> dict[str, Any]:
        """Return a serialization-safe record."""
        return asdict(self)


def assess_quality(
    *,
    valid_area_fraction: float | None = None,
    observation_count: int | None = None,
    expected_observation_count: int | None = None,
    required_area_fraction: float | None = None,
    caution_area_fraction: float | None = None,
) -> QualityAssessment:
    """Classify coverage and period completeness without filling missing data."""
    if expected_observation_count is not None and expected_observation_count <= 0:
        raise ValueError("expected_observation_count must be positive.")
    completeness = None
    if observation_count is not None and expected_observation_count is not None:
        completeness = min(1.0, observation_count / expected_observation_count)
    complete = completeness == 1.0 if completeness is not None else False
    reasons: list[str] = []
    status = GOOD
    if completeness is not None and completeness < 1:
        status = INSUFFICIENT
        reasons.append(
            f"period has {observation_count}/{expected_observation_count} observations"
        )
    if required_area_fraction is not None:
        caution = (
            caution_area_fraction
            if caution_area_fraction is not None
            else max(0.0, required_area_fraction - 0.20)
        )
        if valid_area_fraction is None or not np.isfinite(valid_area_fraction):
            status = INSUFFICIENT
            reasons.append("valid-area fraction is missing")
        elif valid_area_fraction < required_area_fraction:
            if valid_area_fraction < caution:
                status = INSUFFICIENT
            elif status != INSUFFICIENT:
                status = CAUTION
            reasons.append(
                f"valid-area fraction {valid_area_fraction:.3f} is below "
                f"{required_area_fraction:.3f}"
            )
    if not reasons:
        reasons.append("coverage and completeness requirements passed")
    return QualityAssessment(
        valid_area_fraction=valid_area_fraction,
        observation_count=observation_count,
        expected_observation_count=expected_observation_count,
        period_completeness=completeness,
        is_complete_period=complete,
        quality_status=status,
        quality_reason="; ".join(reasons),
    )


def add_period_quality(
    frame: pd.DataFrame,
    observation_column: str,
    expected_column: str,
    valid_area_column: str | None = None,
    required_area_fraction: float | None = None,
) -> pd.DataFrame:
    """Append standard QA fields to a table using row-wise explicit decisions."""
    output = frame.copy()
    assessments = []
    for row in output.itertuples(index=False):
        valid_area = (
            getattr(row, valid_area_column)
            if valid_area_column and hasattr(row, valid_area_column)
            else None
        )
        assessments.append(
            assess_quality(
                valid_area_fraction=valid_area,
                observation_count=int(getattr(row, observation_column)),
                expected_observation_count=int(getattr(row, expected_column)),
                required_area_fraction=required_area_fraction,
            ).as_dict()
        )
    qa = pd.DataFrame(assessments, index=output.index)
    for column in qa:
        if column not in output or column in (
            "period_completeness",
            "is_complete_period",
            "quality_status",
            "quality_reason",
        ):
            output[column] = qa[column]
    return output


def require_pre_post_coverage(
    frame: pd.DataFrame,
    threshold: float,
    coverage_column: str = "valid_area_fraction",
) -> tuple[bool, str]:
    """Approve quantitative change only when both observations pass coverage."""
    if len(frame) != 2 or coverage_column not in frame:
        return False, "Pre/post coverage records are incomplete."
    coverage = pd.to_numeric(frame[coverage_column], errors="coerce")
    if coverage.isna().any() or coverage.lt(threshold).any():
        return (
            False,
            "Quantitative change not estimated because optical coverage is "
            "insufficient.",
        )
    return True, "Both pre/post observations pass the coverage threshold."


def validate_no_future_dates(
    dates: Iterable[Any],
    as_of: str | pd.Timestamp | None = None,
) -> None:
    """Reject observations dated after an explicit reproducibility cutoff."""
    cutoff = (
        pd.Timestamp(as_of).normalize()
        if as_of is not None
        else pd.Timestamp.now().normalize()
    )
    parsed = pd.to_datetime(pd.Series(list(dates))).dropna()
    future = parsed.loc[parsed.dt.normalize() > cutoff]
    if not future.empty:
        raise ValueError(
            f"Future-date observations are not allowed; first future date is "
            f"{future.min().date()} (cutoff {cutoff.date()})."
        )


def feature_provenance_table(records: dict[str, dict[str, Any]]) -> pd.DataFrame:
    """Convert feature provenance definitions into a stable machine-readable table."""
    rows = []
    for feature, metadata in records.items():
        rows.append({"feature": feature, **metadata})
    return pd.DataFrame(rows).sort_values("feature").reset_index(drop=True)


def write_quality_table(frame: pd.DataFrame, path: Path) -> None:
    """Write a QA table under an explicit output location."""
    path.parent.mkdir(parents=True, exist_ok=True)
    frame.to_csv(path, index=False)
