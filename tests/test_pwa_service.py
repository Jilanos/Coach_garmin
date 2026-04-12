from __future__ import annotations

import http.client
import json
import unittest
from threading import Thread
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from coach_garmin.manual_import import run_import_export
from coach_garmin.pwa_service import CoachPwaConfig, _build_handler, build_workspace_status, generate_coach_plan, prepare_coach_questions
from http.server import ThreadingHTTPServer


GARMIN_FULL_EXPORT_DIR = Path(__file__).resolve().parent / "fixtures" / "garmin_full_export"


class FakeCoachClient:
    def __init__(self) -> None:
        self.prompt_bundle: dict[str, object] | None = None

    def ensure_ready(self) -> None:
        return

    def generate_weekly_plan(self, prompt_bundle: dict[str, object]) -> dict[str, object]:
        self.prompt_bundle = prompt_bundle
        return {
            "coach_summary": "Plan direct et specifique.",
            "signals_used": ["load_7d", "history"],
            "weekly_plan": [
                {
                    "day": "Lundi",
                    "session_title": "Footing facile",
                    "objective": "Relancer sans surcharge.",
                    "duration_minutes": 45,
                    "intensity": "Z1-Z2",
                    "notes": "Rester facile.",
                }
            ],
        }


class PwaServiceTest(unittest.TestCase):
    def test_build_workspace_status_reports_dashboard_signals(self) -> None:
        with TemporaryDirectory() as tmp:
            data_dir = Path(tmp) / "data"
            run_import_export(GARMIN_FULL_EXPORT_DIR, data_dir, run_label="pwa-fixture")

            with patch("coach_garmin.pwa_service._probe_provider", return_value={"available": True, "provider": "ollama"}):
                status = build_workspace_status(data_dir)

        self.assertTrue(status["db_available"])
        self.assertIn("workspace", status)
        self.assertIn("import_status", status)
        self.assertIn("analysis", status)
        self.assertIn("health", status)
        self.assertIn("trend", status["analysis"])
        self.assertIn("latest_run", status["import_status"])
        self.assertIn("sync_state", status["import_status"])
        self.assertIn("weekly_volume_km", status["analysis"]["metrics"])

    def test_prepare_coach_questions_returns_clarifications_and_dashboard(self) -> None:
        with TemporaryDirectory() as tmp:
            data_dir = Path(tmp) / "data"
            run_import_export(GARMIN_FULL_EXPORT_DIR, data_dir, run_label="pwa-fixture")

            with patch("coach_garmin.pwa_service._probe_provider", return_value={"available": True, "provider": "ollama"}):
                payload = prepare_coach_questions(
                    data_dir=data_dir,
                    goal_text="Je vise un 10 km en sub 40 dans 10 semaines",
                )

        self.assertIn("goal_profile", payload)
        self.assertIn("questions", payload)
        self.assertIn("dashboard", payload)
        self.assertGreaterEqual(len(payload["questions"]), 1)

    def test_generate_coach_plan_saves_weekly_plan_and_surfaces_summary(self) -> None:
        with TemporaryDirectory() as tmp:
            data_dir = Path(tmp) / "data"
            run_import_export(GARMIN_FULL_EXPORT_DIR, data_dir, run_label="pwa-fixture")

            fake_client = FakeCoachClient()
            with patch("coach_garmin.pwa_service.build_coach_client", return_value=fake_client):
                with patch("coach_garmin.pwa_service._probe_provider", return_value={"available": True, "provider": "ollama"}):
                    payload = generate_coach_plan(
                        data_dir=data_dir,
                        goal_text="Je vise un 10 km en sub 40 dans 10 semaines",
                        answers={"target_timeline_weeks": "10", "available_days_per_week": "4", "constraints": "aucune"},
                    )
            self.assertFalse(payload["needs_clarification"])
            self.assertIn("coach_summary", payload)
            self.assertIn("weekly_plan", payload)
            self.assertTrue(Path(payload["plan_path"]).is_file())
            self.assertIsNotNone(fake_client.prompt_bundle)
            self.assertGreaterEqual(len(payload["weekly_plan"]), 1)
            saved_plan = json.loads(Path(payload["plan_path"]).read_text(encoding="utf-8"))
            self.assertIn("coverage_snapshot", saved_plan)
            self.assertIn("trend", payload["dashboard"]["analysis"])

    def test_http_server_serves_static_shell_and_status_endpoints(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            data_dir = root / "data"
            run_import_export(GARMIN_FULL_EXPORT_DIR, data_dir, run_label="pwa-fixture")

            with patch("coach_garmin.pwa_service._probe_provider", return_value={"available": True, "provider": "ollama"}):
                handler = _build_handler(CoachPwaConfig(web_root=Path("web"), default_data_dir=data_dir, host="127.0.0.1", port=0))
                server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
                port = server.server_address[1]
                thread = Thread(target=server.serve_forever, daemon=True)
                thread.start()
                try:
                    conn = http.client.HTTPConnection("127.0.0.1", port, timeout=10)
                    conn.request("GET", "/")
                    response = conn.getresponse()
                    self.assertEqual(response.status, 200)
                    self.assertIn("text/html", response.getheader("Content-Type", ""))
                    response.read()

                    conn.request("GET", f"/api/status?data_dir={data_dir.as_posix()}")
                    response = conn.getresponse()
                    self.assertEqual(response.status, 200)
                    status_payload = json.loads(response.read().decode("utf-8"))
                    self.assertTrue(status_payload["db_available"])

                    body = json.dumps(
                        {
                            "goal_text": "Je vise un 10 km en sub 40 dans 10 semaines",
                            "data_dir": data_dir.as_posix(),
                            "provider": "ollama",
                        }
                    )
                    conn.request(
                        "POST",
                        "/api/coach/prepare",
                        body=body,
                        headers={"Content-Type": "application/json"},
                    )
                    response = conn.getresponse()
                    self.assertEqual(response.status, 200)
                    prepare_payload = json.loads(response.read().decode("utf-8"))
                    self.assertIn("questions", prepare_payload)
                finally:
                    server.shutdown()
                    server.server_close()


if __name__ == "__main__":
    unittest.main()
