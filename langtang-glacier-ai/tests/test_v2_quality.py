"""V2 scientific-hardening tests; dependency-aware for minimal offline runners."""

from __future__ import annotations

import importlib.util
import unittest


HAS_NUMERIC = all(
    importlib.util.find_spec(package) is not None
    for package in ("numpy", "pandas")
)
HAS_EE_STACK = HAS_NUMERIC and importlib.util.find_spec("ee") is not None
HAS_ML_STACK = HAS_EE_STACK and importlib.util.find_spec("sklearn") is not None


@unittest.skipUnless(HAS_NUMERIC, "numeric dependencies are not installed")
class CentralQualityTests(unittest.TestCase):
    def test_sentinel2_coverage_rejection(self) -> None:
        import pandas as pd

        from src.quality import require_pre_post_coverage

        frame = pd.DataFrame({"valid_area_fraction": [0.91, 0.72]})
        approved, reason = require_pre_post_coverage(frame, 0.80)
        self.assertFalse(approved)
        self.assertEqual(
            reason,
            "Quantitative change not estimated because optical coverage is "
            "insufficient.",
        )

    def test_no_future_date_observations(self) -> None:
        from src.quality import validate_no_future_dates

        with self.assertRaisesRegex(ValueError, "Future-date observations"):
            validate_no_future_dates(["2026-09-04"], as_of="2026-09-03")

    def test_feature_provenance(self) -> None:
        from src.feature_engineering import get_feature_provenance

        provenance = get_feature_provenance()
        self.assertIn("antecedent_precipitation_index", set(provenance["feature"]))
        self.assertTrue(provenance["source"].notna().all())


@unittest.skipUnless(HAS_EE_STACK, "Earth Engine/numeric dependencies unavailable")
class ClimateAndEventTests(unittest.TestCase):
    @staticmethod
    def _daily_climate():
        import numpy as np
        import pandas as pd

        dates = pd.date_range("2018-08-01", "2026-08-31", freq="D")
        frame = pd.DataFrame({"date": dates})
        frame["temp_mean_c"] = 2.0
        frame["temp_min_c"] = -1.0
        frame["temp_max_c"] = 3.0
        frame["precip_mm"] = 1.0
        frame["positive_degree_days"] = 2.0
        frame["freeze_thaw_cycle"] = 1
        frame["snowfall_mm_we"] = 0.5
        frame["runoff_mm"] = 0.25
        frame.loc[frame["date"].eq(pd.Timestamp("2026-08-25")), "precip_mm"] = np.nan
        return frame

    def test_partial_month_historical_matching(self) -> None:
        from src.climate_features import matched_period_climatology

        result = matched_period_climatology(
            self._daily_climate(), "2026-08-01", "2026-08-25", 2018, 2025
        )
        precipitation = result.loc[result["metric"].eq("precip_mm")].iloc[0]
        self.assertEqual(precipitation["value"], 24.0)
        self.assertEqual(precipitation["historical_sample_size"], 8)
        self.assertTrue(precipitation["is_complete_period"])

    def test_incomplete_period_exclusion(self) -> None:
        from src.climate_features import matched_period_climatology

        result = matched_period_climatology(
            self._daily_climate(), "2026-08-01", "2026-08-26", 2018, 2025
        )
        self.assertTrue(result["value"].isna().all())
        self.assertTrue(result["quality_status"].eq("INSUFFICIENT").all())

    def test_historical_percentile_calculation(self) -> None:
        import pandas as pd

        from src.event_analysis import build_pre_event_percentiles

        frame = pd.DataFrame(
            {
                "date": pd.date_range("2018-01-01", "2025-12-01", freq="MS"),
                "temp_anomaly": list(range(96)),
            }
        )
        result = build_pre_event_percentiles(
            frame, "2026-08-26", features=("temp_anomaly",), months=1
        )
        self.assertEqual(result.iloc[0]["historical_count"], 8)
        self.assertEqual(result.iloc[0]["historical_median"], 48.0)

    def test_event_window_construction(self) -> None:
        from src.event_analysis import EventWindows

        windows = EventWindows(
            "2026-08-26", "ESA", "2026-08-20", "2026-08-26",
            "2026-08-27", "2026-09-02",
        ).validated()
        self.assertEqual(windows.event_date, "2026-08-26")

    def test_sentinel1_zero_coverage_detection(self) -> None:
        import pandas as pd

        from src.sar_features import select_sentinel1_candidate

        qa = pd.DataFrame(
            {
                "orbit_pass": ["DESCENDING"],
                "relative_orbit": [19],
                "usable_months": [0],
                "median_valid_area_fraction": [0.0],
                "temporal_coverage_days": [2000],
            }
        )
        with self.assertRaisesRegex(ValueError, "mostly-null"):
            select_sentinel1_candidate(qa)


@unittest.skipUnless(HAS_ML_STACK, "ML dependencies are not installed")
class AnomalyNamingTests(unittest.TestCase):
    def test_dynamic_anomaly_model_naming(self) -> None:
        import numpy as np
        import pandas as pd

        from src.anomaly_detection import run_anomaly_detection

        dates = pd.date_range("2018-01-01", "2025-12-01", freq="MS")
        phase = np.arange(len(dates), dtype=float)
        frame = pd.DataFrame(
            {
                "date": dates,
                "temp_anomaly": np.sin(phase),
                "PDD": 10 + np.cos(phase),
                "precip_3d_max": 1 + phase % 4,
                "precip_7d_max": 2 + phase % 5,
                "precip_30d_max": 3 + phase % 7,
                "antecedent_precipitation_index": 5 + phase % 9,
                "VV": np.nan,
                "VH": np.nan,
                "VV_change": np.nan,
                "VH_change": np.nan,
                "snow_fraction": np.nan,
                "snow_fraction_change": np.nan,
                "NDSI": np.nan,
            }
        )
        output, _, _, diagnostics = run_anomaly_detection(frame)
        self.assertTrue(output["anomaly_model_name"].eq("climate_only").all())
        self.assertEqual(diagnostics[0]["actual_features"], [
            "temp_anomaly", "PDD_adjusted", "precip_7d_adjusted",
            "antecedent_precipitation_index_adjusted",
        ])


if __name__ == "__main__":
    unittest.main()
