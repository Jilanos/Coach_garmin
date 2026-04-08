from __future__ import annotations

import io
import json
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from coach_garmin.cli import main
from coach_garmin.coach_chat import run_coach_chat
from coach_garmin.coach_tools import LocalCoachToolkit
from coach_garmin.manual_import import run_import_export


GARMIN_FULL_EXPORT_DIR = Path(__file__).resolve().parent / "fixtures" / "garmin_full_export"


class FakeCoachClient:
    def __init__(self) -> None:
        self.prompt_bundle: dict[str, object] | None = None

    def generate_weekly_plan(self, prompt_bundle: dict[str, object]) -> dict[str, object]:
        self.prompt_bundle = prompt_bundle
        return {
            "coach_summary": "Le focus de la semaine est une progression controlee avec recuperation protegee.",
            "signals_used": [
                "load_7d",
                "sleep_hours_7d",
                "hrv_7d",
                "training_history",
            ],
            "weekly_plan": [
                {
                    "day": "Lundi",
                    "session_title": "Footing facile",
                    "objective": "Relancer sans fatigue excessive.",
                    "duration_minutes": 45,
                    "intensity": "Z1-Z2",
                    "notes": "Rester facile.",
                },
                {
                    "day": "Mardi",
                    "session_title": "Repos",
                    "objective": "Laisser la charge se stabiliser.",
                    "duration_minutes": 0,
                    "intensity": "Repos",
                    "notes": "Mobilite legere possible.",
                },
                {
                    "day": "Mercredi",
                    "session_title": "Seuil controle",
                    "objective": "Stimuler l'allure cible sans pic de fatigue.",
                    "duration_minutes": 55,
                    "intensity": "Z3-Z4",
                    "notes": "Bloc principal modere.",
                },
                {
                    "day": "Jeudi",
                    "session_title": "Footing recuperation",
                    "objective": "Faciliter la recuperation.",
                    "duration_minutes": 40,
                    "intensity": "Z1",
                    "notes": "Tres facile.",
                },
                {
                    "day": "Vendredi",
                    "session_title": "Repos",
                    "objective": "Consolider la semaine.",
                    "duration_minutes": 0,
                    "intensity": "Repos",
                    "notes": "Sommeil prioritaire.",
                },
                {
                    "day": "Samedi",
                    "session_title": "Sortie longue",
                    "objective": "Construire l'endurance specifique.",
                    "duration_minutes": 80,
                    "intensity": "Z2",
                    "notes": "Finir en controle.",
                },
                {
                    "day": "Dimanche",
                    "session_title": "Activation courte",
                    "objective": "Maintenir la frequence sans surcharger.",
                    "duration_minutes": 30,
                    "intensity": "Z1-Z2",
                    "notes": "Optionnel si fatigue.",
                },
            ],
        }


class FailingCoachClient:
    def generate_weekly_plan(self, prompt_bundle: dict[str, object]) -> dict[str, object]:
        raise RuntimeError("Ollama is unavailable.")


class ShortPlanCoachClient:
    def generate_weekly_plan(self, prompt_bundle: dict[str, object]) -> dict[str, object]:
        return {
            "coach_summary": "Plan court a completer.",
            "signals_used": ["fatigue_flag"],
            "weekly_plan": [
                {
                    "day": "Lundi",
                    "session_title": "Footing facile",
                    "objective": "Relancer.",
                    "duration_minutes": 35,
                    "intensity": "Z1-Z2",
                    "notes": "Souple.",
                }
            ],
        }


class CoachChatTest(unittest.TestCase):
    def test_local_coach_toolkit_reads_metrics_history_and_persists_outputs(self) -> None:
        with TemporaryDirectory() as tmp:
            data_dir = Path(tmp) / "data"
            run_import_export(GARMIN_FULL_EXPORT_DIR, data_dir, run_label="coach-fixture")

            toolkit = LocalCoachToolkit(data_dir=data_dir)
            metrics = toolkit.metrics()
            self.assertEqual(metrics["latest_day"], "2026-04-02")
            self.assertIn("load_7d", metrics["latest_metrics"])
            self.assertIn("acute_load", metrics)

            goals = toolkit.goals({"goal_text": "semi 1h45", "target_event": "semi-marathon"})
            self.assertTrue(Path(goals["path"]).is_file())
            self.assertEqual(toolkit.goals()["goal_profile"]["target_event"], "semi-marathon")

            history = toolkit.history()
            self.assertTrue(history["available"])
            self.assertGreaterEqual(history["recent_activity_count"], 1)
            self.assertGreater(history["total_distance_km"], 0.0)

            plan = toolkit.plan({"weekly_plan": [{"day": "Lundi"}]})
            self.assertTrue(Path(plan["path"]).is_file())

    def test_local_coach_toolkit_metrics_tolerates_missing_optional_tables(self) -> None:
        with TemporaryDirectory() as tmp:
            data_dir = Path(tmp) / "data"
            run_import_export(Path("tests/fixtures/manual_export"), data_dir, run_label="coach-minimal")

            metrics = LocalCoachToolkit(data_dir=data_dir).metrics()

            self.assertTrue(metrics["db_available"])
            self.assertIsNotNone(metrics["latest_day"])
            self.assertNotIn("acute_load", metrics)
            self.assertNotIn("training_status", metrics)
            self.assertNotIn("heart_rate_zones", metrics)

    def test_run_coach_chat_asks_clarifications_and_saves_weekly_plan(self) -> None:
        with TemporaryDirectory() as tmp:
            data_dir = Path(tmp) / "data"
            run_import_export(GARMIN_FULL_EXPORT_DIR, data_dir, run_label="coach-fixture")
            fake_client = FakeCoachClient()
            answers = iter(["12", "4", "aucune"])
            outputs: list[str] = []

            summary = run_coach_chat(
                data_dir=data_dir,
                goal_text="Je vise un semi en 1h45",
                input_func=lambda prompt: next(answers),
                output_func=outputs.append,
                llm_client=fake_client,
            )

            self.assertEqual(summary["goal_profile"]["target_event"], "semi-marathon")
            self.assertEqual(summary["goal_profile"]["target_timeline_weeks"], 12)
            self.assertEqual(summary["goal_profile"]["available_days_per_week"], 4)
            self.assertEqual(len(summary["questions_asked"]), 3)
            self.assertTrue(Path(summary["goal_profile_path"]).is_file())
            self.assertTrue(Path(summary["plan_path"]).is_file())
            self.assertIsNotNone(fake_client.prompt_bundle)
            assert fake_client.prompt_bundle is not None
            self.assertIn("metrics", fake_client.prompt_bundle)
            self.assertIn("history", fake_client.prompt_bundle)
            self.assertIn("analysis", fake_client.prompt_bundle)
            self.assertIn("Signaux utilises", "\n".join(outputs))

            saved_plan = json.loads(Path(summary["plan_path"]).read_text(encoding="utf-8"))
            self.assertEqual(len(saved_plan["weekly_plan"]), 7)
            self.assertIn("load_7d", saved_plan["signals_used"])

    def test_run_coach_chat_surfaces_provider_errors(self) -> None:
        with TemporaryDirectory() as tmp:
            data_dir = Path(tmp) / "data"
            run_import_export(GARMIN_FULL_EXPORT_DIR, data_dir, run_label="coach-fixture")
            answers = iter(["12", "4", "aucune"])

            with self.assertRaisesRegex(RuntimeError, "Ollama is unavailable"):
                run_coach_chat(
                    data_dir=data_dir,
                    goal_text="Je vise un semi en 1h45",
                    input_func=lambda prompt: next(answers),
                    output_func=lambda message: None,
                    llm_client=FailingCoachClient(),
                )

    def test_run_coach_chat_normalizes_partial_model_output_to_seven_days(self) -> None:
        with TemporaryDirectory() as tmp:
            data_dir = Path(tmp) / "data"
            run_import_export(GARMIN_FULL_EXPORT_DIR, data_dir, run_label="coach-fixture")
            answers = iter(["12", "4", "aucune"])

            summary = run_coach_chat(
                data_dir=data_dir,
                goal_text="Je vise un semi en 1h45",
                input_func=lambda prompt: next(answers),
                output_func=lambda message: None,
                llm_client=ShortPlanCoachClient(),
            )

            self.assertEqual(len(summary["weekly_plan"]), 7)
            self.assertEqual(summary["weekly_plan"][0]["day"], "Lundi")
            self.assertEqual(summary["weekly_plan"][-1]["day"], "Dimanche")
            self.assertIn(summary["weekly_plan"][1]["session_title"], {"Repos ou adaptation", "Seance allure specifique"})

    def test_tolerant_activity_normalization_repairs_real_shape_units_for_history(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            source_dir = root / "source"
            source_dir.mkdir(parents=True, exist_ok=True)
            (source_dir / "activities.json").write_text(
                json.dumps(
                    [
                        {
                            "activityId": 1,
                            "activityType": "running",
                            "startTimeLocal": 1775546807000.0,
                            "duration": 1528222.0458984375,
                            "elapsedDuration": 1528222.0458984375,
                            "distance": 493497.021484375,
                            "avgSpeed": 0.32290000915527345,
                            "activityTrainingLoad": 71.31999206542969,
                            "calories": 1722.09,
                            "steps": 3876,
                        }
                    ],
                    ensure_ascii=True,
                ),
                encoding="utf-8",
            )
            data_dir = root / "data"

            run_import_export(source_dir, data_dir, run_label="aberrant-activity")

            toolkit = LocalCoachToolkit(data_dir=data_dir)
            history = toolkit.history(days=7)
            self.assertTrue(history["available"])
            self.assertAlmostEqual(history["total_distance_km"], 4.93, places=2)
            self.assertAlmostEqual(history["total_duration_minutes"], 25.5, places=1)
            self.assertAlmostEqual(history["long_run_km"], 4.93, places=2)
            self.assertEqual(history["recent_activities"][0]["training_load"], 71.31999206542969)

    def test_local_coach_toolkit_analysis_derives_benchmark_and_paces(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            source_dir = root / "source"
            source_dir.mkdir(parents=True, exist_ok=True)
            (source_dir / "activities.json").write_text(
                json.dumps(
                    [
                        {
                            "activityId": 1,
                            "activityType": "running",
                            "startTimeLocal": 1775546807000.0,
                            "duration": 2520.0,
                            "distance": 10000.0,
                            "activityTrainingLoad": 95.0,
                        },
                        {
                            "activityId": 2,
                            "activityType": "running",
                            "startTimeLocal": 1774946807000.0,
                            "duration": 5400.0,
                            "distance": 18000.0,
                            "activityTrainingLoad": 130.0,
                        },
                    ],
                    ensure_ascii=True,
                ),
                encoding="utf-8",
            )
            data_dir = root / "data"
            run_import_export(source_dir, data_dir, run_label="analysis-benchmark")

            analysis = LocalCoachToolkit(data_dir=data_dir).analysis(
                {
                    "target_event": "10 km",
                    "principal_objective": "10 km",
                    "constraints": "fin de periostite sensible",
                }
            )

            self.assertTrue(analysis["available"])
            self.assertEqual(analysis["recommended_benchmark"]["event"], "10 km")
            self.assertEqual(analysis["training_phase"], "return-from-injury")
            self.assertIsNotNone(analysis["inferred_paces"]["threshold_pace_min_per_km"])
            self.assertIn("10 km", analysis["analysis_summary"])

    def test_history_prioritizes_running_rows_for_running_coach_metrics(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            source_dir = root / "source"
            source_dir.mkdir(parents=True, exist_ok=True)
            (source_dir / "activities.json").write_text(
                json.dumps(
                    [
                        {
                            "activityId": 1,
                            "activityType": "cycling",
                            "startTimeLocal": 1775546807000.0,
                            "duration": 900000.0,
                            "distance": 500000.0,
                            "activityTrainingLoad": 20.0,
                        },
                        {
                            "activityId": 2,
                            "activityType": "running",
                            "startTimeLocal": 1775547807000.0,
                            "duration": 360000.0,
                            "distance": 120000.0,
                            "activityTrainingLoad": 50.0,
                        },
                    ],
                    ensure_ascii=True,
                ),
                encoding="utf-8",
            )
            data_dir = root / "data"

            run_import_export(source_dir, data_dir, run_label="running-priority")

            history = LocalCoachToolkit(data_dir=data_dir).history(days=7)
            self.assertEqual(history["recent_activity_count"], 1)
            self.assertEqual(history["recent_activity_count_all"], 2)
            self.assertAlmostEqual(history["long_run_km"], 12.0, places=2)
            self.assertEqual(history["recent_activities"][0]["activity_type"], "running")

    def test_running_goal_caps_long_run_even_with_huge_observed_history(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            source_dir = root / "source"
            source_dir.mkdir(parents=True, exist_ok=True)
            (source_dir / "activities.json").write_text(
                json.dumps(
                    [
                        {
                            "activityId": 1,
                            "activityType": "running",
                            "startTimeLocal": 1775546807000.0,
                            "duration": 720000.0,
                            "distance": 300000.0,
                            "activityTrainingLoad": 120.0,
                        }
                    ],
                    ensure_ascii=True,
                ),
                encoding="utf-8",
            )
            data_dir = root / "data"
            run_import_export(source_dir, data_dir, run_label="long-run-cap")
            answers = iter(["12", "4", "aucune"])

            summary = run_coach_chat(
                data_dir=data_dir,
                goal_text="Je vise un semi en 1h45",
                input_func=lambda prompt: next(answers),
                output_func=lambda message: None,
                llm_client=ShortPlanCoachClient(),
            )

            saturday = next(item for item in summary["weekly_plan"] if item["day"] == "Samedi")
            self.assertLessEqual(saturday["duration_minutes"], 132)

    def test_run_coach_chat_asks_for_principal_objective_when_multiple_goals_exist(self) -> None:
        with TemporaryDirectory() as tmp:
            data_dir = Path(tmp) / "data"
            run_import_export(GARMIN_FULL_EXPORT_DIR, data_dir, run_label="coach-fixture")
            answers = iter(["10 km", "12", "4", "aucune"])
            outputs: list[str] = []

            summary = run_coach_chat(
                data_dir=data_dir,
                goal_text="Je vise un 10 km en sub 40 et un marathon en sub 3h30",
                input_func=lambda prompt: next(answers),
                output_func=outputs.append,
                llm_client=ShortPlanCoachClient(),
            )

            self.assertEqual(summary["goal_profile"]["principal_objective"], "10 km")
            self.assertEqual(summary["goal_profile"]["target_event"], "10 km")
            self.assertEqual(summary["questions_asked"][0], "Tu mentionnes plusieurs objectifs. Lequel est prioritaire pour les 6 a 12 prochaines semaines ?")

    def test_new_goal_does_not_inherit_previous_target_event(self) -> None:
        with TemporaryDirectory() as tmp:
            data_dir = Path(tmp) / "data"
            run_import_export(GARMIN_FULL_EXPORT_DIR, data_dir, run_label="coach-fixture")
            toolkit = LocalCoachToolkit(data_dir=data_dir)
            toolkit.goals(
                {
                    "goal_text": "ancien 10 km",
                    "target_event": "10 km",
                    "principal_objective": "10 km",
                    "available_days_per_week": 4,
                }
            )
            answers = iter(["12", "4", "aucune"])

            summary = run_coach_chat(
                data_dir=data_dir,
                goal_text="Je veux simplement reprendre la course durablement sans objectif chrono",
                input_func=lambda prompt: next(answers),
                output_func=lambda message: None,
                llm_client=ShortPlanCoachClient(),
            )

            self.assertNotEqual(summary["goal_profile"].get("target_event"), "10 km")

    def test_cli_coach_chat_json_mode_prints_json_payload(self) -> None:
        buffer = io.StringIO()
        with patch(
            "coach_garmin.cli.run_coach_chat",
            return_value={"plan_path": "data/reports/weekly_plan_20260407.json", "signals_used": ["load_7d"]},
        ):
            with redirect_stdout(buffer):
                exit_code = main(["coach", "chat", "--format", "json", "--goal", "semi 1h45"])

        self.assertEqual(exit_code, 0)
        payload = json.loads(buffer.getvalue())
        self.assertEqual(payload["plan_path"], "data/reports/weekly_plan_20260407.json")


if __name__ == "__main__":
    unittest.main()
