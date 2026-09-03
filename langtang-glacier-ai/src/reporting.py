"""Integrated Phase 10 research summaries, timeline, and static dashboard."""

from __future__ import annotations

from html import escape
import json
from pathlib import Path
from typing import Any

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

PRODUCTS = (
    ("qa", "Feature provenance", "qa/feature_provenance.csv"),
    ("qa", "Matched August climate", "qa/climate_matched_august_1_24.csv"),
    ("qa", "Antecedent climate windows", "qa/climate_event_antecedent_windows.csv"),
    ("qa", "Sentinel-1 candidate tracks", "qa/sentinel1_candidate_track_qa.csv"),
    ("qa", "Sentinel-1 angle sensitivity", "qa/sentinel1_angle_mask_sensitivity.csv"),
    ("qa", "Sentinel-2 proxy sensitivity", "qa/sentinel2_proxy_trend_sensitivity.csv"),
    ("qa", "ROI provenance", "qa/roi_provenance.json"),
    (
        "table",
        "Optical candidate changes",
        "tables/candidate_spectral_change_polygons.geojson",
    ),
    ("table", "Monthly feature store", "tables/langtang_monthly_features.csv"),
    (
        "table",
        "Feature store with anomaly scores",
        "tables/langtang_monthly_features_with_anomaly.csv",
    ),
    ("table", "Trend summary", "tables/trend_summary.csv"),
    ("table", "Anomaly scores", "tables/anomaly_scores.csv"),
    ("table", "PCA loadings", "tables/pca_loadings.csv"),
    ("table", "Event windows", "tables/event_windows.json"),
    ("table", "Sentinel-2 event metrics", "tables/sentinel2_event_metrics.csv"),
    ("table", "Sentinel-1 event metrics", "tables/sentinel1_event_metrics.csv"),
    ("chart", "Seasonally adjusted trends", "charts/seasonally_adjusted_trends.png"),
    ("chart", "Anomaly scores", "charts/anomaly_score_timeseries.png"),
    ("chart", "Environmental regimes", "charts/environmental_regimes_pca.png"),
    (
        "chart",
        "Pre-event historical percentiles",
        "charts/pre_event_historical_percentiles.png",
    ),
    ("chart", "Integrated event timeline", "charts/integrated_event_timeline.png"),
    ("map", "Study area", "maps/study_area.html"),
    ("map", "Sentinel-2 event comparison", "maps/sentinel2_event_pre_post.html"),
    ("map", "Sentinel-1 event comparison", "maps/sentinel1_event_pre_post.html"),
)


def read_json_if_present(path: Path) -> dict[str, Any]:
    """Read a JSON object, returning an empty dictionary when it is absent."""
    if not path.is_file():
        return {}
    with path.open() as file:
        return json.load(file)


def build_output_inventory(output_root: Path) -> pd.DataFrame:
    """Inventory expected research products without treating gaps as successes."""
    rows = []
    for kind, label, relative_path in PRODUCTS:
        path = output_root / relative_path
        rows.append(
            {
                "kind": kind,
                "product": label,
                "relative_path": relative_path,
                "status": "available" if path.is_file() else "pending",
                "size_bytes": path.stat().st_size if path.is_file() else pd.NA,
            }
        )
    return pd.DataFrame(rows)


def _load_csv(path: Path) -> pd.DataFrame:
    """Load an optional CSV without masking malformed present files."""
    return pd.read_csv(path) if path.is_file() else pd.DataFrame()


def _boolean_column(frame: pd.DataFrame, column: str) -> pd.Series:
    """Parse nullable CSV booleans without treating the text 'False' as true."""
    if column not in frame:
        return pd.Series(False, index=frame.index, dtype=bool)
    values = frame[column]
    if pd.api.types.is_bool_dtype(values.dtype):
        return values.fillna(False).astype(bool)
    return values.astype("string").str.lower().eq("true").fillna(False)


def _event_context(
    event_metadata: dict[str, Any],
) -> tuple[pd.Timestamp | None, pd.Timestamp | None]:
    """Return event date and beginning of its preceding 12-month interval."""
    if not event_metadata.get("event_date"):
        return None, None
    event_date = pd.Timestamp(event_metadata["event_date"])
    return event_date, event_date - pd.DateOffset(months=12)


def build_research_question_summary(
    output_root: Path,
    features: pd.DataFrame,
    event_metadata: dict[str, Any],
) -> pd.DataFrame:
    """Build cautious evidence statements for the seven research questions."""
    data = features.copy()
    data["date"] = pd.to_datetime(data["date"])
    trend = _load_csv(output_root / "tables" / "trend_summary.csv")
    s2_event = _load_csv(output_root / "tables" / "sentinel2_event_metrics.csv")
    s1_event = _load_csv(output_root / "tables" / "sentinel1_event_metrics.csv")
    event_date, pre_start = _event_context(event_metadata)

    estimable = trend.dropna(subset=["sen_slope_per_year"]) if (
        "sen_slope_per_year" in trend
    ) else pd.DataFrame()
    significant = (
        trend.loc[_boolean_column(trend, "mk_significant_0_05")]
        if not trend.empty
        else pd.DataFrame()
    )
    rq1_text = (
        f"Trend diagnostics are available for {len(estimable)} features; "
        "their slopes and uncertainty must be interpreted with coverage and sensor "
        "limitations."
        if not trend.empty
        else "Trend output is pending; no long-term finding is reported."
    )
    rq2_text = (
        f"{len(significant)} exploratory Mann–Kendall results are flagged at 0.05 "
        "before any multiple-testing adjustment; consult trend_summary.csv for "
        "effect sizes and OLS-HAC uncertainty."
        if not trend.empty
        else "Climate and snow trend tests are pending."
    )

    pre_event = pd.DataFrame()
    if event_date is not None and pre_start is not None:
        pre_event = data.loc[
            data["date"].ge(pre_start) & data["date"].lt(event_date)
        ]
    if "anomaly_score" in pre_event and pre_event["anomaly_score"].notna().any():
        scores = pre_event["anomaly_score"].dropna()
        flags = _boolean_column(
            pre_event, "anomaly_above_reference_quantile"
        ).loc[scores.index]
        rq3_text = (
            f"{int(flags.sum())} of {len(scores)} scored pre-event months exceeded "
            f"the configured reference threshold; the maximum ensemble score was "
            f"{scores.max():.3f}. This is a relative anomaly screen, not probability."
        )
    else:
        rq3_text = "No complete pre-event anomaly scores are available."

    s2_quantitative = (
        not s2_event.empty
        and _boolean_column(s2_event, "quantitative_change_estimated").all()
    )
    if s2_quantitative:
        rq4_text = (
            "Sentinel-2 pre/post metrics and maps are available as spectral-change "
            "screening."
        )
    elif not s2_event.empty:
        rq4_text = (
            "Sentinel-2 observations exist, but quantitative change was rejected "
            "by the optical coverage QA threshold."
        )
    else:
        rq4_text = "Sentinel-2 event comparison is pending."
    if not s1_event.empty:
        rq4_text += " Same-track Sentinel-1 event metrics are also available."
    elif event_metadata.get("sentinel1_available") is False:
        rq4_text += " Post-event same-track Sentinel-1 imagery is not yet available."

    top_feature = ""
    top_feature_column = (
        "top_contributing_feature"
        if "top_contributing_feature" in data
        else "climate_sar_top_feature"
    )
    if top_feature_column in data:
        flagged = data.loc[
            _boolean_column(data, "anomaly_above_reference_quantile"),
            top_feature_column,
        ].dropna()
        if not flagged.empty:
            counts = flagged.value_counts()
            top_feature = (
                f"The most frequent largest standardized contributor among flagged "
                f"months was {counts.index[0]} ({int(counts.iloc[0])} months). "
            )
    rq5_text = top_feature + (
        "Use PCA loadings and all standardized inputs; a largest contributor is not "
        "a physical cause."
    )

    rows = [
        (
            "RQ1", "Long-term environmental change", "EXPLORATORY",
            "STATISTICAL ASSOCIATION",
            rq1_text, "trend_summary.csv",
        ),
        (
            "RQ2", "Climate, snow, and melt trends", "EXPLORATORY",
            "STATISTICAL ASSOCIATION",
            rq2_text, "trend_summary.csv",
        ),
        (
            "RQ3", "Pre-event seasonal anomalies", "EXPLORATORY",
            "OBSERVATION AND STATISTICAL ASSOCIATION",
            rq3_text, "anomaly_scores.csv",
        ),
        (
            "RQ4",
            "Satellite-observed event-associated change",
            "MODERATE" if s2_quantitative else "DATA INSUFFICIENT",
            "OBSERVATION",
            rq4_text,
            "Sentinel-2/Sentinel-1 event outputs",
        ),
        (
            "RQ5",
            "Variables contributing to anomaly scores",
            "EXPLORATORY",
            "STATISTICAL ASSOCIATION",
            rq5_text,
            "anomaly_scores.csv; pca_loadings.csv",
        ),
        (
            "RQ6",
            "Detectable precursory combination",
            "UNSUPPORTED",
            "HYPOTHESIS",
            "The unsupervised results can identify unusual combinations, but one "
            "event provides no test of precursor specificity, sensitivity, or "
            "predictive skill.",
            "Integrated exploratory outputs",
        ),
        (
            "RQ7",
            "What cannot be concluded",
            "STRONG",
            "UNSUPPORTED CAUSAL INTERPRETATION",
            "The workflow cannot establish collapse causation, calibrated hazard, "
            "predictive capability, displacement, event volume, or a validated "
            "debris footprint from these data alone.",
            "docs/limitations.md",
        ),
    ]
    return pd.DataFrame(
        rows,
        columns=[
            "research_question", "topic", "evidence_grade", "evidence_type",
            "evidence_summary", "source_outputs",
        ],
    )


def plot_integrated_event_timeline(
    features: pd.DataFrame,
    event_metadata: dict[str, Any],
    output: Path,
) -> plt.Figure:
    """Plot aligned environmental indicators as a non-causal analytical timeline."""
    data = features.copy()
    data["date"] = pd.to_datetime(data["date"])
    candidates = (
        ("temp_anomaly", "Temperature anomaly"),
        ("PDD", "Positive degree days"),
        ("snow_fraction", "Snow fraction proxy"),
        ("anomaly_score", "Ensemble anomaly score"),
    )
    available = [(column, label) for column, label in candidates if column in data]
    if not available:
        raise ValueError("No timeline variables are available in the feature table.")
    figure, axes = plt.subplots(
        len(available),
        1,
        figsize=(12, 2.6 * len(available)),
        sharex=True,
        constrained_layout=True,
    )
    axes = np.atleast_1d(axes)
    event_date, pre_start = _event_context(event_metadata)
    for axis, (column, label) in zip(axes, available):
        axis.plot(data["date"], data[column], color="#969696", linewidth=0.8)
        axis.plot(
            data["date"],
            data[column].rolling(12, min_periods=6).median(),
            color="#2171b5",
            linewidth=1.6,
            label="12-month rolling median",
        )
        if event_date is not None:
            axis.axvline(event_date, color="#d7301f", linestyle="--", label="Event")
            if pre_start is not None:
                axis.axvspan(pre_start, event_date, color="#fdae61", alpha=0.12)
        axis.set_ylabel(label)
        axis.grid(alpha=0.2)
    axes[0].legend(frameon=False, ncol=2, fontsize=8)
    axes[0].set_title("Integrated analytical timeline (associations, not causation)")
    axes[-1].set_xlabel("Date")
    output.parent.mkdir(parents=True, exist_ok=True)
    figure.savefig(output, dpi=200, bbox_inches="tight")
    return figure


def write_research_conclusions(
    summary: pd.DataFrame,
    inventory: pd.DataFrame,
    output: Path,
) -> None:
    """Write a concise Markdown handoff from generated, evidence-linked statements."""
    lines = [
        "# Langtang Lirung research conclusions",
        "",
        "These statements are generated from the available outputs and are "
        "exploratory, not causal or predictive.",
        "",
    ]
    for row in summary.itertuples(index=False):
        lines.extend(
            [
                f"## {row.research_question}: {row.topic}",
                "",
                f"Evidence grade: **{row.evidence_grade}**",
                "",
                f"Evidence type: **{row.evidence_type}**",
                "",
                row.evidence_summary,
                "",
                f"Evidence: `{row.source_outputs}`",
                "",
            ]
        )
    pending = inventory.loc[inventory["status"].eq("pending"), "product"].tolist()
    lines.extend(
        [
            "## Pending products",
            "",
            *(f"- {product}" for product in pending),
            "",
            "See `docs/limitations.md` before scientific interpretation.",
        ]
    )
    output.write_text("\n".join(lines))


def build_static_dashboard(
    output_root: Path,
    inventory: pd.DataFrame,
    summary: pd.DataFrame,
    event_metadata: dict[str, Any],
) -> Path:
    """Create a portable HTML index linking all available research artifacts."""
    available = inventory.loc[inventory["status"].eq("available")]
    charts = available.loc[available["kind"].eq("chart")]
    maps = available.loc[available["kind"].eq("map")]
    status_rows = "".join(
        "<tr>"
        f"<td>{escape(row.product)}</td>"
        f"<td class='{row.status}'>{escape(row.status)}</td>"
        f"<td><a href='{escape(row.relative_path)}'>{escape(row.relative_path)}</a></td>"
        "</tr>"
        for row in inventory.itertuples(index=False)
    )
    rq_rows = "".join(
        "<tr>"
        f"<td>{escape(row.research_question)}</td>"
        f"<td>{escape(row.topic)}</td>"
        f"<td>{escape(row.evidence_grade)}</td>"
        f"<td>{escape(row.evidence_type)}</td>"
        f"<td>{escape(row.evidence_summary)}</td>"
        "</tr>"
        for row in summary.itertuples(index=False)
    )
    chart_cards = "".join(
        f"<figure><img src='{escape(row.relative_path)}' alt='{escape(row.product)}'>"
        f"<figcaption>{escape(row.product)}</figcaption></figure>"
        for row in charts.itertuples(index=False)
    )
    map_links = "".join(
        f"<li><a href='{escape(row.relative_path)}'>{escape(row.product)}</a></li>"
        for row in maps.itertuples(index=False)
    )
    event_source = escape(str(event_metadata.get("event_source", "Not configured")))
    failed_qc = []
    if event_metadata.get("sentinel1_available") is False:
        failed_qc.append(
            "Sentinel-1 event comparison failed availability QA: no valid "
            "same-track post-event acquisition was available."
        )
    pending_qa = inventory.loc[
        inventory["kind"].eq("qa") & inventory["status"].eq("pending"), "product"
    ].tolist()
    failed_qc.extend(f"Pending QA output: {product}." for product in pending_qa)
    qc_items = "".join(f"<li>{escape(message)}</li>" for message in failed_qc)
    html = f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Langtang Lirung environmental conditioning and change dashboard</title>
<style>
body{{font:16px/1.5 system-ui,sans-serif;margin:auto;max-width:1200px;padding:24px;color:#222}}
h1,h2{{color:#17365d}} .notice{{background:#fff3cd;padding:12px;border-left:5px solid #d39e00}}
table{{border-collapse:collapse;width:100%;margin:16px 0}}
th,td{{border:1px solid #ddd;padding:8px;text-align:left;vertical-align:top}}
th{{background:#eef4f8}} .available{{color:#176b2c}} .pending{{color:#9c5a00}}
.gallery{{display:grid;grid-template-columns:repeat(auto-fit,minmax(360px,1fr));gap:16px}}
figure{{margin:0;border:1px solid #ddd;padding:8px}} img{{width:100%;height:auto}}
</style></head><body>
<h1>Environmental conditioning and multisensor change analysis around the 2026
Langtang Lirung event</h1>
<p class="notice"><strong>Responsible interpretation:</strong>
This dashboard summarizes exploratory associations and screening products.
It does not predict glacier collapse, establish causation, or provide a
calibrated hazard assessment.</p>
<p><strong>Event source:</strong> {event_source}</p>
<h2>Failed or pending quality-control tests</h2>
<ul>{qc_items or '<li>No failed or pending QA outputs were detected.</li>'}</ul>
<h2>Research-question summary</h2>
<table><tr><th>RQ</th><th>Topic</th><th>Grade</th><th>Evidence type</th>
<th>Evidence summary</th></tr>
{rq_rows}</table>
<h2>Output status</h2>
<table><tr><th>Product</th><th>Status</th><th>Path</th></tr>
{status_rows}</table>
<h2>Charts</h2><div class="gallery">{chart_cards}</div>
<h2>Interactive maps</h2><ul>{map_links or '<li>No maps available.</li>'}</ul>
<p><a href="../docs/limitations.md">Scientific limitations</a> ·
<a href="../docs/methodology.md">Methodology</a></p>
</body></html>"""
    dashboard_path = output_root / "research_dashboard.html"
    dashboard_path.write_text(html)
    return dashboard_path
