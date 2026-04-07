from __future__ import annotations

import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

import duckdb

from coach_garmin.manual_import import run_import_export


FIXTURE_DIR = Path(__file__).resolve().parent / "fixtures" / "manual_export"
GARMIN_FULL_EXPORT_DIR = Path(__file__).resolve().parent / "fixtures" / "garmin_full_export"


class ManualImportTest(unittest.TestCase):
    def test_run_import_export_builds_raw_normalized_and_report_layers(self) -> None:
        with TemporaryDirectory() as tmp:
            data_dir = Path(tmp) / "data"
            summary = run_import_export(FIXTURE_DIR, data_dir, run_label="fixture-sync")

            self.assertEqual(summary["artifacts_imported"], 10)
            self.assertEqual(
                summary["datasets_seen"],
                [
                    "activities",
                    "body_battery",
                    "heart_rate",
                    "hrv",
                    "intensity_minutes",
                    "recovery_time",
                    "sleep",
                    "steps",
                    "stress",
                    "training_readiness",
                ],
            )

            manifest_path = Path(summary["manifest_path"])
            self.assertTrue(manifest_path.is_file())

            report_path = data_dir / "reports" / "latest_metrics.json"
            self.assertTrue(report_path.is_file())
            report = json.loads(report_path.read_text(encoding="utf-8"))
            self.assertEqual(report["latest_day"], "2026-04-02")
            self.assertIn("load_7d", report["latest_metrics"])
            self.assertIn("fatigue_flag", report["latest_metrics"])

            db_path = data_dir / "normalized" / "coach_garmin.duckdb"
            self.assertTrue(db_path.is_file())
            con = duckdb.connect(str(db_path))
            try:
                self.assertEqual(con.execute("SELECT COUNT(*) FROM sync_runs").fetchone()[0], 1)
                self.assertEqual(con.execute("SELECT COUNT(*) FROM activities").fetchone()[0], 2)
                self.assertEqual(con.execute("SELECT COUNT(*) FROM wellness_daily").fetchone()[0], 18)
                self.assertGreaterEqual(con.execute("SELECT COUNT(*) FROM derived_daily_metrics").fetchone()[0], 2)
            finally:
                con.close()

    def test_run_import_export_supports_garmin_native_export_shapes(self) -> None:
        with TemporaryDirectory() as tmp:
            data_dir = Path(tmp) / "data"
            summary = run_import_export(GARMIN_FULL_EXPORT_DIR, data_dir, run_label="garmin-native-export")

            self.assertEqual(summary["artifacts_imported"], 6)
            self.assertEqual(
                summary["datasets_seen"],
                ["activities", "heart_rate", "hrv", "sleep", "steps", "stress"],
            )
            self.assertEqual(summary["total_records"], 12)

            report_path = data_dir / "reports" / "latest_metrics.json"
            report = json.loads(report_path.read_text(encoding="utf-8"))
            self.assertEqual(report["latest_day"], "2026-04-02")
            self.assertIn("load_7d", report["latest_metrics"])

            db_path = data_dir / "normalized" / "coach_garmin.duckdb"
            con = duckdb.connect(str(db_path))
            try:
                self.assertEqual(con.execute("SELECT COUNT(*) FROM sync_runs").fetchone()[0], 1)
                self.assertEqual(con.execute("SELECT COUNT(*) FROM activities").fetchone()[0], 2)
                self.assertEqual(con.execute("SELECT COUNT(*) FROM wellness_daily").fetchone()[0], 10)
                self.assertGreaterEqual(con.execute("SELECT COUNT(*) FROM derived_daily_metrics").fetchone()[0], 2)
            finally:
                con.close()
