from __future__ import annotations

import http.client
import json
import unittest
from threading import Thread
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from coach_garmin.manual_import import run_import_export
from coach_garmin.pwa_service import (
    CoachPwaConfig,
    _build_handler,
    answer_coach_question,
    build_workspace_status,
    generate_coach_plan,
    prepare_coach_questions,
    save_coach_profile,
)
from http.server import ThreadingHTTPServer


GARMIN_FULL_EXPORT_DIR = Path(__file__).resolve().parent / "fixtures" / "garmin_full_export"


class FakeCoachClient:
    def __init__(self) -> None:
        self.prompt_bundle: dict[str, object] | None = None
        self.question_prompt_bundle: dict[str, object] | None = None

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

    def answer_targeted_question(self, prompt_bundle: dict[str, object]) -> dict[str, object]:
        self.question_prompt_bundle = prompt_bundle
        latest_plan = prompt_bundle.get("latest_plan") if isinstance(prompt_bundle, dict) else {}
        plan_used = bool(latest_plan.get("available")) if isinstance(latest_plan, dict) else False
        return {
            "coach_answer": "Garde la séance seulement si les sensations reviennent et baisse d'un cran sinon.",
            "signals_used": ["load_7d", "history", "latest_plan" if plan_used else "no_plan_context"],
            "plan_context_used": plan_used,
            "follow_up": "Surveille le ressenti au tibia et coupe si la gêne monte.",
        }


class FailingCoachClient:
    def ensure_ready(self) -> None:
        return

    def generate_weekly_plan(self, prompt_bundle: dict[str, object]) -> dict[str, object]:
        raise RuntimeError("Gemini request failed with HTTP 503.")


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
        self.assertIn("pace_hr_curve", status["analysis"]["trend"])
        self.assertIn("cadence_daily", status["analysis"]["trend"])
        self.assertIn("daily_load", status["analysis"]["trend"])
        self.assertIn("daily_sleep_smoothed", status["analysis"]["trend"])
        self.assertIn("running_session_types", status["analysis"]["trend"])
        self.assertIn("latest_run", status["import_status"])
        self.assertIn("sync_state", status["import_status"])
        self.assertIn("weekly_volume_km", status["analysis"]["metrics"])
        self.assertIn("cadence_7d", status["analysis"]["metrics"])
        self.assertIn("load_reference_low", status["analysis"]["metrics"])
        self.assertEqual(status["analysis"]["metrics"]["load_ratio_target"], 1.0)
        self.assertIn("goal_profile", status)
        self.assertIn("latest_plan", status)
        self.assertFalse(status["latest_plan"]["available"])

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
                        profile={
                            "blessure": "périostite sensible mais stable",
                            "fatigue": "fatigue légère",
                            "maladie": "",
                            "emploi_du_temps": "mardi et jeudi très chargés",
                            "disponibilite": "4 à 5 séances max",
                            "temperature": "chaleur l'après-midi",
                            "deplacements": "déplacement vendredi",
                            "autres_sports": "vélo facile samedi",
                        },
                    )
            self.assertFalse(payload["needs_clarification"])
            self.assertIn("coach_summary", payload)
            self.assertIn("weekly_plan", payload)
            self.assertTrue(Path(payload["plan_path"]).is_file())
            self.assertIsNotNone(fake_client.prompt_bundle)
            self.assertGreaterEqual(len(payload["weekly_plan"]), 1)
            self.assertEqual(payload["goal_profile"]["blessure"], "périostite sensible mais stable")
            self.assertIn("structured_constraints", fake_client.prompt_bundle)
            saved_plan = json.loads(Path(payload["plan_path"]).read_text(encoding="utf-8"))
            self.assertIn("coverage_snapshot", saved_plan)
            self.assertEqual(saved_plan["goal_profile"]["fatigue"], "fatigue légère")
            self.assertIn("trend", payload["dashboard"]["analysis"])
            self.assertTrue(payload["dashboard"]["latest_plan"]["available"])
            self.assertEqual(payload["dashboard"]["latest_plan"]["plan"]["coach_summary"], payload["coach_summary"])

    def test_save_coach_profile_persists_expanded_fields(self) -> None:
        with TemporaryDirectory() as tmp:
            data_dir = Path(tmp) / "data"
            run_import_export(GARMIN_FULL_EXPORT_DIR, data_dir, run_label="pwa-fixture")

            with patch("coach_garmin.pwa_service._probe_provider", return_value={"available": True, "provider": "ollama"}):
                payload = save_coach_profile(
                    data_dir=data_dir,
                    goal_text="Je vise un semi propre dans 12 semaines",
                    profile={
                        "blessure": "aucune",
                        "fatigue": "fatigue pro modérée",
                        "maladie": "",
                        "emploi_du_temps": "semaine dense",
                        "disponibilite": "4 créneaux",
                        "temperature": "chaud le soir",
                        "deplacements": "RAS",
                        "autres_sports": "renfo lundi",
                        "targeted_question": "Est-ce que je garde la séance de qualité ?",
                    },
                )

            self.assertEqual(payload["goal_profile"]["fatigue"], "fatigue pro modérée")
            self.assertEqual(payload["goal_profile"]["targeted_question"], "Est-ce que je garde la séance de qualité ?")
            self.assertTrue(Path(payload["goal_profile_path"]).is_file())
            self.assertIn("goal_profile", payload["dashboard"])

    def test_answer_coach_question_uses_latest_saved_plan_when_available(self) -> None:
        with TemporaryDirectory() as tmp:
            data_dir = Path(tmp) / "data"
            run_import_export(GARMIN_FULL_EXPORT_DIR, data_dir, run_label="pwa-fixture")

            fake_client = FakeCoachClient()
            with patch("coach_garmin.pwa_service.build_coach_client", return_value=fake_client):
                with patch("coach_garmin.pwa_service._probe_provider", return_value={"available": True, "provider": "ollama"}):
                    generate_coach_plan(
                        data_dir=data_dir,
                        goal_text="Je vise un 10 km en sub 40 dans 10 semaines",
                        profile={"disponibilite": "4 séances", "fatigue": "bonne fraîcheur"},
                    )
                    payload = answer_coach_question(
                        data_dir=data_dir,
                        goal_text="Je vise un 10 km en sub 40 dans 10 semaines",
                        question_text="Est-ce que je garde la séance de seuil si je suis un peu fatigué ?",
                        profile={"fatigue": "fatigue légère depuis 3 jours"},
                    )

            self.assertTrue(payload["plan_context_available"])
            self.assertIn("coach_answer", payload)
            self.assertIn("utilisé comme contexte", payload["plan_context_note"])
            self.assertIsNotNone(fake_client.question_prompt_bundle)
            assert fake_client.question_prompt_bundle is not None
            self.assertTrue(fake_client.question_prompt_bundle["latest_plan"]["available"])

    def test_answer_coach_question_falls_back_without_saved_plan(self) -> None:
        with TemporaryDirectory() as tmp:
            data_dir = Path(tmp) / "data"
            run_import_export(GARMIN_FULL_EXPORT_DIR, data_dir, run_label="pwa-fixture")

            fake_client = FakeCoachClient()
            with patch("coach_garmin.pwa_service.build_coach_client", return_value=fake_client):
                with patch("coach_garmin.pwa_service._probe_provider", return_value={"available": True, "provider": "ollama"}):
                    payload = answer_coach_question(
                        data_dir=data_dir,
                        goal_text="Je vise un 10 km en sub 40 dans 10 semaines",
                        question_text="Est-ce que je remplace la séance si je sens la chaleur ?",
                        profile={"temperature": "32 degrés prévus"},
                    )

            self.assertFalse(payload["plan_context_available"])
            self.assertIn("Aucun plan enregistré", payload["plan_context_note"])
            self.assertIsNotNone(fake_client.question_prompt_bundle)
            assert fake_client.question_prompt_bundle is not None
            self.assertFalse(fake_client.question_prompt_bundle["latest_plan"]["available"])

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

                    body = json.dumps(
                        {
                            "goal_text": "Je vise un 10 km en sub 40 dans 10 semaines",
                            "question_text": "Est-ce que je garde la séance qualité si je dors mal ?",
                            "data_dir": data_dir.as_posix(),
                            "provider": "ollama",
                            "profile": {"fatigue": "sommeil léger"},
                        }
                    )
                    with patch("coach_garmin.pwa_service.build_coach_client", return_value=FakeCoachClient()):
                        conn.request(
                            "POST",
                            "/api/coach/question",
                            body=body,
                            headers={"Content-Type": "application/json"},
                        )
                        response = conn.getresponse()
                        self.assertEqual(response.status, 200)
                        question_payload = json.loads(response.read().decode("utf-8"))
                        self.assertIn("coach_answer", question_payload)
                finally:
                    server.shutdown()
                    server.server_close()

    def test_plan_endpoint_returns_retryable_provider_error(self) -> None:
        with TemporaryDirectory() as tmp:
            data_dir = Path(tmp) / "data"
            run_import_export(GARMIN_FULL_EXPORT_DIR, data_dir, run_label="pwa-fixture")

            with patch("coach_garmin.pwa_service.build_coach_client", return_value=FailingCoachClient()):
                with patch("coach_garmin.pwa_service._probe_provider", return_value={"available": True, "provider": "gemini"}):
                    handler = _build_handler(CoachPwaConfig(web_root=Path("web"), default_data_dir=data_dir, host="127.0.0.1", port=0))
                    server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
                    port = server.server_address[1]
                    thread = Thread(target=server.serve_forever, daemon=True)
                    thread.start()
                    try:
                        conn = http.client.HTTPConnection("127.0.0.1", port, timeout=10)
                        body = json.dumps(
                            {
                                "goal_text": "Je vise un 10 km en sub 40 dans 10 semaines",
                                "data_dir": data_dir.as_posix(),
                                "provider": "gemini",
                                "answers": {
                                    "target_timeline_weeks": "10",
                                    "available_days_per_week": "4",
                                    "constraints": "aucune",
                                },
                            }
                        )
                        conn.request("POST", "/api/coach/plan", body=body, headers={"Content-Type": "application/json"})
                        response = conn.getresponse()
                        self.assertEqual(response.status, 503)
                        payload = json.loads(response.read().decode("utf-8"))
                        self.assertTrue(payload["retryable"])
                        self.assertIn("Gemini request failed with HTTP 503", payload["error"])
                    finally:
                        server.shutdown()
                        server.server_close()

    def test_sync_endpoint_returns_payload_and_keeps_server_responsive(self) -> None:
        with TemporaryDirectory() as tmp:
            data_dir = Path(tmp) / "data"
            run_import_export(GARMIN_FULL_EXPORT_DIR, data_dir, run_label="pwa-fixture")

            with patch(
                "coach_garmin.pwa_service.sync_garmin_connect",
                return_value={
                    "run_id": "sync-run-1",
                    "run_label": "pwa-garmin-sync",
                    "source_kind": "garmin-authenticated-api",
                    "dashboard": build_workspace_status(data_dir, provider="ollama"),
                },
            ):
                handler = _build_handler(CoachPwaConfig(web_root=Path("web"), default_data_dir=data_dir, host="127.0.0.1", port=0))
                server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
                port = server.server_address[1]
                thread = Thread(target=server.serve_forever, daemon=True)
                thread.start()
                try:
                    conn = http.client.HTTPConnection("127.0.0.1", port, timeout=10)
                    body = json.dumps({"data_dir": data_dir.as_posix(), "run_label": "pwa-garmin-sync"})
                    conn.request("POST", "/api/sync/garmin-connect", body=body, headers={"Content-Type": "application/json"})
                    response = conn.getresponse()
                    self.assertEqual(response.status, 200)
                    payload = json.loads(response.read().decode("utf-8"))
                    self.assertEqual(payload["run_id"], "sync-run-1")
                    self.assertEqual(payload["source_kind"], "garmin-authenticated-api")
                finally:
                    server.shutdown()
                    server.server_close()


if __name__ == "__main__":
    unittest.main()
