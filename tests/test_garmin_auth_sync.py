from __future__ import annotations

import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

import duckdb

from coach_garmin.garmin_auth import run_authenticated_sync


class FakeGarminClient:
    def __init__(self, email: str | None, password: str | None, prompt_mfa) -> None:
        self.email = email
        self.password = password
        self.prompt_mfa = prompt_mfa
        self.login_calls: list[str | None] = []

    def login(self, tokenstore: str | None = None) -> tuple[str | None, str | None]:
        self.login_calls.append(tokenstore)
        return None, None

    def get_activities_by_date(
        self,
        startdate: str,
        enddate: str | None = None,
        activitytype: str | None = None,
        sortorder: str | None = None,
    ) -> list[dict[str, object]]:
        return [
            {
                "activityId": 101,
                "activityType": {"typeKey": "running"},
                "startTimeLocal": "2026-04-01T06:30:00+00:00",
                "distance": 10500,
                "duration": 3120,
                "averageHR": 146,
                "maxHR": 171,
                "trainingLoad": 78,
                "calories": 710,
            },
            {
                "activityId": 102,
                "activityType": {"typeKey": "running"},
                "startTimeLocal": "2026-04-03T07:00:00+00:00",
                "distance": 6200,
                "duration": 2100,
                "averageHR": 141,
                "maxHR": 164,
                "trainingLoad": 42,
                "calories": 410,
            },
        ]

    def get_sleep_data(self, cdate: str) -> dict[str, object]:
        return {
            "dailySleepDTO": {
                "calendarDate": cdate,
                "sleepTimeSeconds": 7 * 3600 + 900,
            }
        }

    def get_rhr_day(self, cdate: str) -> dict[str, object]:
        return {"restingHeartRate": 48, "calendarDate": cdate}

    def get_heart_rates(self, cdate: str) -> dict[str, object]:
        return {"averageHeartRate": 61, "calendarDate": cdate}

    def get_hrv_data(self, cdate: str) -> dict[str, object]:
        return {"hrvSummary": {"lastNightAvg": 74}, "calendarDate": cdate}

    def get_stress_data(self, cdate: str) -> dict[str, object]:
        return {"overallStressLevel": 19, "calendarDate": cdate}

    def get_daily_steps(self, start: str, end: str) -> list[dict[str, object]]:
        return [
            {"calendarDate": "2026-04-01", "totalSteps": 13000},
            {"calendarDate": "2026-04-02", "totalSteps": 9500},
            {"calendarDate": "2026-04-03", "totalSteps": 14200},
        ]


class GarminAuthSyncTest(unittest.TestCase):
    def test_authenticated_sync_builds_raw_layers_and_dedupes_on_rerun(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            data_dir = root / "data"
            env_file = root / ".env.local"
            env_file.write_text(
                "\n".join(
                    [
                        "COACH_GARMIN_GARMIN_EMAIL=runner@example.com",
                        "COACH_GARMIN_GARMIN_PASSWORD=secret",
                    ]
                )
                + "\n",
                encoding="utf-8",
            )
            tokenstore_path = root / ".local" / "garmin" / "garmin_tokens.json"

            summary_one = run_authenticated_sync(
                data_dir=data_dir,
                start_date="2026-04-01",
                end_date="2026-04-03",
                tokenstore_path=tokenstore_path,
                env_file=env_file,
                client_factory=FakeGarminClient,
            )
            summary_two = run_authenticated_sync(
                data_dir=data_dir,
                start_date="2026-04-01",
                end_date="2026-04-03",
                tokenstore_path=tokenstore_path,
                env_file=env_file,
                client_factory=FakeGarminClient,
            )

            self.assertEqual(
                summary_one["datasets_seen"],
                ["activities", "heart_rate", "hrv", "sleep", "steps", "stress"],
            )
            self.assertEqual(summary_one["artifacts_imported"], 6)
            self.assertEqual(summary_two["artifacts_imported"], 6)

            manifest_path = Path(summary_one["manifest_path"])
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            self.assertEqual(manifest["source_kind"], "garmin-authenticated-api")
            self.assertEqual(manifest["metadata"]["start_date"], "2026-04-01")
            self.assertEqual(manifest["metadata"]["end_date"], "2026-04-03")
            self.assertTrue(str(tokenstore_path) in manifest["metadata"]["tokenstore_path"])

            report_path = data_dir / "reports" / "latest_metrics.json"
            self.assertTrue(report_path.is_file())
            report = json.loads(report_path.read_text(encoding="utf-8"))
            self.assertEqual(report["latest_day"], "2026-04-03")
            self.assertIn("load_7d", report["latest_metrics"])

            db_path = data_dir / "normalized" / "coach_garmin.duckdb"
            con = duckdb.connect(str(db_path))
            try:
                self.assertEqual(con.execute("SELECT COUNT(*) FROM sync_runs").fetchone()[0], 2)
                self.assertEqual(con.execute("SELECT COUNT(*) FROM activities").fetchone()[0], 2)
                self.assertEqual(con.execute("SELECT COUNT(*) FROM wellness_daily").fetchone()[0], 15)
            finally:
                con.close()
