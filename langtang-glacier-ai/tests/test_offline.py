"""Offline checks that do not require Earth Engine credentials."""

import json
from pathlib import Path
import unittest

from src.config import SETTINGS, Settings


ROOT = Path(__file__).resolve().parents[1]


class OfflineChecks(unittest.TestCase):
    def test_default_configuration_is_valid(self) -> None:
        SETTINGS.validate()
        self.assertEqual(SETTINGS.glims_id, "G085544E28246N")
        self.assertIn("G085547E28252N", SETTINGS.glims_legacy_ids)
        self.assertIsNone(SETTINGS.event_date)
        self.assertEqual(SETTINGS.analysis_years, tuple(range(2017, 2027)))

    def test_invalid_cloud_score_is_rejected(self) -> None:
        with self.assertRaisesRegex(ValueError, "cloud_score_threshold"):
            Settings(cloud_score_threshold=1.1).validate()

    def test_notebooks_are_valid_and_documented(self) -> None:
        names = (
            "01_setup_and_roi.ipynb",
            "02_sentinel2_glacier_analysis.ipynb",
            "03_sentinel2_visual_comparison.ipynb",
            "04_climate_weather_analysis.ipynb",
            "05_sentinel1_sar_change.ipynb",
            "06_feature_engineering.ipynb",
            "07_trend_analysis.ipynb",
            "08_anomaly_detection.ipynb",
            "09_event_pre_post_analysis.ipynb",
            "10_integrated_dashboard_and_conclusions.ipynb",
            "11_v2_quality_assurance.ipynb",
        )
        for name in names:
            with self.subTest(name=name):
                notebook = json.loads((ROOT / "notebooks" / name).read_text())
                self.assertEqual(notebook["nbformat"], 4)
                first = "".join(notebook["cells"][0]["source"])
                for heading in (
                    "Purpose", "Inputs", "Outputs", "Runtime", "Dependencies"
                ):
                    self.assertIn(heading, first)


if __name__ == "__main__":
    unittest.main()
