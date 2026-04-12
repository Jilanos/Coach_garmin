from __future__ import annotations

import json
import unittest
import zipfile
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

import duckdb

from coach_garmin.manual_import import run_import_export
from coach_garmin.sync_state import load_sync_summary


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

            coverage_path = data_dir / "reports" / "feature_coverage.json"
            self.assertTrue(coverage_path.is_file())
            coverage = json.loads(coverage_path.read_text(encoding="utf-8"))
            self.assertTrue(coverage["raw"]["artifacts"] >= 10)
            self.assertTrue(coverage["normalized"]["activities"]["available"])
            self.assertIn("latest_metrics", coverage["coach"]["available_signals"])

            db_path = data_dir / "normalized" / "coach_garmin.duckdb"
            self.assertTrue(db_path.is_file())
            con = duckdb.connect(str(db_path))
            try:
                self.assertEqual(con.execute("SELECT COUNT(*) FROM sync_runs").fetchone()[0], 1)
                self.assertEqual(con.execute("SELECT COUNT(*) FROM activities").fetchone()[0], 2)
                self.assertEqual(con.execute("SELECT COUNT(*) FROM wellness_daily").fetchone()[0], 18)
                self.assertGreaterEqual(con.execute("SELECT COUNT(*) FROM derived_daily_metrics").fetchone()[0], 2)
                self.assertGreaterEqual(con.execute("SELECT COUNT(*) FROM artifact_inventory").fetchone()[0], 10)
                self.assertGreaterEqual(con.execute("SELECT COUNT(*) FROM normalized_lineage").fetchone()[0], 18)
            finally:
                con.close()

    def test_run_import_export_supports_garmin_native_export_shapes(self) -> None:
        with TemporaryDirectory() as tmp:
            data_dir = Path(tmp) / "data"
            summary = run_import_export(GARMIN_FULL_EXPORT_DIR, data_dir, run_label="garmin-native-export")

            self.assertEqual(summary["artifacts_imported"], 12)
            self.assertEqual(
                summary["datasets_seen"],
                [
                    "activities",
                    "acute_load",
                    "device_raw",
                    "heart_rate",
                    "heart_rate_zones",
                    "hrv",
                    "profile",
                    "settings_raw",
                    "sleep",
                    "steps",
                    "stress",
                    "training_history",
                ],
            )
            self.assertEqual(summary["total_records"], 20)

            report_path = data_dir / "reports" / "latest_metrics.json"
            report = json.loads(report_path.read_text(encoding="utf-8"))
            self.assertEqual(report["latest_day"], "2026-04-02")
            self.assertIn("load_7d", report["latest_metrics"])

            coverage_path = data_dir / "reports" / "feature_coverage.json"
            coverage = json.loads(coverage_path.read_text(encoding="utf-8"))
            self.assertGreaterEqual(coverage["raw"]["artifacts"], 12)
            self.assertTrue(coverage["features"]["derived_daily_metrics"]["available"])

            db_path = data_dir / "normalized" / "coach_garmin.duckdb"
            con = duckdb.connect(str(db_path))
            try:
                self.assertEqual(con.execute("SELECT COUNT(*) FROM sync_runs").fetchone()[0], 1)
                self.assertEqual(con.execute("SELECT COUNT(*) FROM activities").fetchone()[0], 2)
                self.assertEqual(con.execute("SELECT COUNT(*) FROM wellness_daily").fetchone()[0], 10)
                self.assertEqual(con.execute("SELECT COUNT(*) FROM acute_load_daily").fetchone()[0], 2)
                self.assertEqual(con.execute("SELECT COUNT(*) FROM training_history_daily").fetchone()[0], 2)
                self.assertEqual(con.execute("SELECT COUNT(*) FROM profile_snapshots").fetchone()[0], 1)
                self.assertEqual(con.execute("SELECT COUNT(*) FROM heart_rate_zones").fetchone()[0], 1)
                self.assertGreaterEqual(con.execute("SELECT COUNT(*) FROM derived_daily_metrics").fetchone()[0], 2)
                self.assertGreaterEqual(con.execute("SELECT COUNT(*) FROM artifact_inventory").fetchone()[0], 12)
                self.assertGreaterEqual(con.execute("SELECT COUNT(*) FROM normalized_lineage").fetchone()[0], 18)
            finally:
                con.close()

    def test_run_import_export_prefers_fit_activity_files_over_json_sidecars(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            source_dir = root / "source"
            source_dir.mkdir(parents=True, exist_ok=True)
            (source_dir / "run.fit").write_bytes(b"FIT")
            (source_dir / "run.json").write_text(
                json.dumps(
                    [
                        {
                            "activityId": 999,
                            "activityType": "running",
                            "startTimeLocal": "2026-04-01T06:30:00+00:00",
                            "duration": 3600,
                            "distance": 10000,
                        }
                    ],
                    ensure_ascii=True,
                ),
                encoding="utf-8",
            )

            with patch("coach_garmin.storage.read_fit_activity_records", return_value=[{"activityType": "running", "durationSeconds": 3600, "distanceMeters": 10000, "startTimeLocal": "2026-04-01T06:30:00+00:00"}]) as fit_reader:
                summary = run_import_export(source_dir, root / "data", run_label="fit-first")

            self.assertEqual(summary["artifacts_imported"], 1)
            self.assertEqual(summary["datasets_seen"], ["activities"])
            self.assertEqual(fit_reader.call_count, 2)

    def test_run_import_export_falls_back_to_json_when_fit_is_absent(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            source_dir = root / "source"
            source_dir.mkdir(parents=True, exist_ok=True)
            (source_dir / "run.json").write_text(
                json.dumps(
                    [
                        {
                            "activityId": 999,
                            "activityType": "running",
                            "startTimeLocal": "2026-04-01T06:30:00+00:00",
                            "duration": 3600,
                            "distance": 10000,
                        }
                    ],
                    ensure_ascii=True,
                ),
                encoding="utf-8",
            )

            with patch("coach_garmin.storage.read_fit_activity_records") as fit_reader:
                summary = run_import_export(source_dir, root / "data", run_label="json-fallback")

            self.assertEqual(summary["artifacts_imported"], 1)
            self.assertEqual(summary["datasets_seen"], ["activities"])
            fit_reader.assert_not_called()

    def test_run_import_export_supports_zip_baseline_and_records_sync_state(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            zip_path = root / "garmin-export.zip"
            with zipfile.ZipFile(zip_path, "w") as archive:
                for file_path in FIXTURE_DIR.rglob("*"):
                    if file_path.is_file():
                        archive.write(file_path, file_path.relative_to(FIXTURE_DIR).as_posix())

            data_dir = root / "data"
            first = run_import_export(zip_path, data_dir, run_label="zip-baseline")
            second = run_import_export(zip_path, data_dir, run_label="zip-refresh")

            self.assertGreaterEqual(first["artifacts_imported"], 1)
            self.assertGreaterEqual(second["reused_artifacts"], 1)

            state = load_sync_summary(data_dir)
            self.assertTrue(state["available"])
            self.assertEqual(state["run_count"], 2)
            self.assertGreaterEqual(state["artifact_index_rows"], 1)
