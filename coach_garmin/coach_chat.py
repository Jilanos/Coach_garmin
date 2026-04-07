from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Callable

from coach_garmin.coach_ollama import OllamaCoachClient
from coach_garmin.coach_tools import LocalCoachToolkit


InputFunc = Callable[[str], str]
OutputFunc = Callable[[str], None]


@dataclass(slots=True)
class CoachChatSession:
    toolkit: LocalCoachToolkit
    llm_client: Any
    input_func: InputFunc = input
    output_func: OutputFunc = print

    def run(self, goal_text: str | None = None) -> dict[str, Any]:
        self.output_func("Coach Garmin chat local-first")
        if not goal_text:
            goal_text = self.input_func("Quel est ton objectif running principal ? ").strip()
        if not goal_text:
            raise RuntimeError("A running goal is required to start the coach chat.")

        goal_profile = self._build_goal_profile(goal_text)
        history_context = self.toolkit.history()
        existing_goal = self.toolkit.goals()["goal_profile"]
        if isinstance(existing_goal, dict):
            goal_profile = {**existing_goal, **goal_profile}

        questions_asked: list[str] = []
        for key, question, parser in self._clarification_questions(goal_profile, history_context):
            answer = self.input_func(f"{question} ").strip()
            questions_asked.append(question)
            goal_profile[key] = parser(answer)

        goal_profile["goal_text"] = goal_text
        goal_profile["updated_at"] = datetime.now(UTC).isoformat()
        goal_state = self.toolkit.goals(goal_profile)

        metrics_context = self.toolkit.metrics()
        plan_skeleton = self._build_plan_skeleton(goal_profile, metrics_context, history_context)
        prompt_bundle = {
            "goal_profile": goal_profile,
            "metrics": metrics_context,
            "history": history_context,
            "suggested_plan_skeleton": plan_skeleton,
            "generation_rules": {
                "language": "fr",
                "plan_days": 7,
                "must_reference_local_signals": True,
                "must_be_cautious": True,
            },
        }
        plan_response = self.llm_client.generate_weekly_plan(prompt_bundle)
        normalized_plan = self._normalize_weekly_plan(plan_response.get("weekly_plan", []), plan_skeleton)
        saved_plan_payload = {
            "generated_at": datetime.now(UTC).isoformat(),
            "goal_profile": goal_profile,
            "metrics_snapshot": metrics_context,
            "history_snapshot": history_context,
            "coach_summary": plan_response.get("coach_summary", ""),
            "signals_used": self._normalize_signals_used(
                plan_response.get("signals_used", []),
                metrics_context,
                history_context,
            ),
            "questions_asked": questions_asked,
            "weekly_plan": normalized_plan,
        }
        saved_plan = self.toolkit.plan(saved_plan_payload)

        self._render_summary(saved_plan_payload)
        return {
            "goal_profile_path": goal_state["path"],
            "plan_path": saved_plan["path"],
            "questions_asked": questions_asked,
            "goal_profile": goal_profile,
            "signals_used": saved_plan_payload["signals_used"],
            "weekly_plan": saved_plan_payload["weekly_plan"],
        }

    def _render_summary(self, payload: dict[str, Any]) -> None:
        if payload.get("coach_summary"):
            self.output_func("")
            self.output_func("Synthese coach")
            self.output_func(str(payload["coach_summary"]))
        signals = payload.get("signals_used") or []
        if signals:
            self.output_func("")
            self.output_func("Signaux utilises")
            for signal in signals:
                self.output_func(f"- {signal}")
        self.output_func("")
        self.output_func("Plan hebdomadaire")
        for session in payload["weekly_plan"]:
            day = session.get("day", "?")
            title = session.get("session_title", "Seance")
            duration = session.get("duration_minutes", "?")
            intensity = session.get("intensity", "?")
            objective = session.get("objective", "")
            self.output_func(f"- {day}: {title} | {duration} min | {intensity}")
            if objective:
                self.output_func(f"  {objective}")

    @staticmethod
    def _normalize_weekly_plan(raw_plan: Any, plan_skeleton: list[dict[str, Any]]) -> list[dict[str, Any]]:
        canonical_days = [
            "Lundi",
            "Mardi",
            "Mercredi",
            "Jeudi",
            "Vendredi",
            "Samedi",
            "Dimanche",
        ]
        sessions: list[dict[str, Any]] = []
        if isinstance(raw_plan, list):
            sessions = [item for item in raw_plan if isinstance(item, dict)]

        by_day: dict[str, dict[str, Any]] = {}
        unnamed_sessions: list[dict[str, Any]] = []
        for session in sessions:
            day = str(session.get("day", "")).strip()
            if day in canonical_days:
                by_day[day] = {
                    "day": day,
                    "session_title": session.get("session_title", "Seance"),
                    "objective": session.get("objective", ""),
                    "duration_minutes": int(session.get("duration_minutes", 0) or 0),
                    "intensity": session.get("intensity", "Ajuster"),
                    "notes": session.get("notes", ""),
                }
            else:
                unnamed_sessions.append(session)

        normalized: list[dict[str, Any]] = []
        skeleton_by_day = {item["day"]: item for item in plan_skeleton}
        for index, day in enumerate(canonical_days):
            if day in by_day:
                normalized.append(by_day[day])
                continue
            fallback = unnamed_sessions[index] if index < len(unnamed_sessions) else {}
            skeleton = skeleton_by_day.get(day, {})
            normalized.append(
                {
                    "day": day,
                    "session_title": fallback.get("session_title", skeleton.get("session_title", "Repos ou adaptation")),
                    "objective": fallback.get(
                        "objective",
                        skeleton.get(
                            "objective",
                            "Ajuster la charge en fonction de la fatigue et des contraintes de la semaine.",
                        ),
                    ),
                    "duration_minutes": int(
                        fallback.get("duration_minutes", skeleton.get("duration_minutes", 0)) or 0
                    ),
                    "intensity": fallback.get("intensity", skeleton.get("intensity", "Repos")),
                    "notes": fallback.get(
                        "notes",
                        skeleton.get("notes", "Conserver une logique prudente et locale-first."),
                    ),
                }
            )
        return normalized

    @staticmethod
    def _build_plan_skeleton(
        goal_profile: dict[str, Any],
        metrics_context: dict[str, Any],
        history_context: dict[str, Any],
    ) -> list[dict[str, Any]]:
        days = ["Lundi", "Mardi", "Mercredi", "Jeudi", "Vendredi", "Samedi", "Dimanche"]
        available_days = int(goal_profile.get("available_days_per_week", 4) or 4)
        latest_metrics = metrics_context.get("latest_metrics", {})
        fatigue = bool(latest_metrics.get("fatigue_flag"))
        overreaching = bool(latest_metrics.get("overreaching_flag"))
        observed_long_run_km = float(history_context.get("long_run_km", 12.0) or 12.0)
        event = str(goal_profile.get("target_event", "running goal"))
        long_run_km = CoachChatSession._target_long_run_km(event, observed_long_run_km, fatigue or overreaching)

        if available_days <= 2:
            running_days = {"Mercredi", "Dimanche"}
        elif available_days == 3:
            running_days = {"Mardi", "Jeudi", "Dimanche"}
        elif available_days == 4:
            running_days = {"Lundi", "Mercredi", "Samedi", "Dimanche"}
        else:
            running_days = {"Lundi", "Mardi", "Jeudi", "Samedi", "Dimanche"}

        intensity_label = "Z2-Z3" if not fatigue and not overreaching else "Z2"
        quality_title = "Seance allure specifique" if "semi" in event or "marathon" in event else "Seance qualite controlee"
        quality_objective = (
            "Travailler l'allure cible tout en gardant une reserve de recuperation."
            if not fatigue and not overreaching
            else "Entretenir l'intensite sans aggraver la fatigue actuelle."
        )
        long_run_minutes = max(70, int(round(long_run_km * 5.5)))

        skeleton: list[dict[str, Any]] = []
        for day in days:
            if day not in running_days:
                skeleton.append(
                    {
                        "day": day,
                        "session_title": "Repos ou adaptation",
                        "objective": "Laisser la charge redescendre et proteger la recuperation.",
                        "duration_minutes": 0,
                        "intensity": "Repos",
                        "notes": "Mobilite ou marche facile seulement si utile.",
                    }
                )
                continue

            if day == "Samedi" or day == "Dimanche" and "Samedi" not in running_days:
                skeleton.append(
                    {
                        "day": day,
                        "session_title": "Sortie longue",
                        "objective": "Construire l'endurance specifique pour l'objectif annonce.",
                        "duration_minutes": long_run_minutes,
                        "intensity": "Z2",
                        "notes": "Rester en controle et couper court si la fatigue monte.",
                    }
                )
                continue

            if day in {"Mardi", "Mercredi"}:
                skeleton.append(
                    {
                        "day": day,
                        "session_title": quality_title,
                        "objective": quality_objective,
                        "duration_minutes": 55 if not fatigue and not overreaching else 45,
                        "intensity": intensity_label,
                        "notes": "Echauffement progressif puis retour au calme long.",
                    }
                )
                continue

            skeleton.append(
                {
                    "day": day,
                    "session_title": "Footing facile",
                    "objective": "Ajouter du volume utile sans surcharge excessive.",
                    "duration_minutes": 40 if fatigue or overreaching else 50,
                    "intensity": "Z1-Z2",
                    "notes": "Rester facile et respirer confortablement.",
                }
            )

        return skeleton

    @staticmethod
    def _target_long_run_km(event: str, observed_long_run_km: float, reduced_load: bool) -> float:
        normalized_event = event.lower()
        default_target = min(max(observed_long_run_km, 10.0), 18.0)
        if "5 km" in normalized_event or "5k" in normalized_event:
            target = min(max(observed_long_run_km, 8.0), 12.0)
        elif "10 km" in normalized_event or "10k" in normalized_event:
            target = min(max(observed_long_run_km, 10.0), 16.0)
        elif "semi" in normalized_event:
            target = min(max(observed_long_run_km, 12.0), 24.0)
        elif "marathon" in normalized_event:
            target = min(max(observed_long_run_km, 16.0), 32.0)
        else:
            target = default_target

        if reduced_load:
            target = max(8.0, round(target * 0.85, 1))
        return target

    @staticmethod
    def _normalize_signals_used(
        raw_signals: Any,
        metrics_context: dict[str, Any],
        history_context: dict[str, Any],
    ) -> list[str]:
        allowed = {
            "load_7d",
            "load_28d",
            "load_ratio_7_28",
            "sleep_hours_7d",
            "resting_hr_7d",
            "hrv_7d",
            "progression_delta",
            "fatigue_flag",
            "overreaching_flag",
            "acute_load",
            "training_status",
            "heart_rate_zones",
            "recent_training_history",
            "recent_activity_volume",
        }
        normalized = [
            str(item).strip()
            for item in raw_signals
            if isinstance(item, str) and str(item).strip() in allowed
        ]
        if normalized:
            return normalized

        fallback: list[str] = []
        latest_metrics = metrics_context.get("latest_metrics", {})
        for key in (
            "load_7d",
            "sleep_hours_7d",
            "hrv_7d",
            "fatigue_flag",
            "overreaching_flag",
        ):
            if key in latest_metrics and latest_metrics.get(key) not in (None, ""):
                fallback.append(key)
        if metrics_context.get("acute_load"):
            fallback.append("acute_load")
        if metrics_context.get("training_status"):
            fallback.append("training_status")
        if metrics_context.get("heart_rate_zones"):
            fallback.append("heart_rate_zones")
        if history_context.get("available"):
            fallback.append("recent_training_history")
            fallback.append("recent_activity_volume")
        return fallback or ["load_7d"]

    @staticmethod
    def _build_goal_profile(goal_text: str) -> dict[str, Any]:
        goal_lower = goal_text.lower()
        profile: dict[str, Any] = {
            "goal_text": goal_text,
            "target_event": CoachChatSession._detect_target_event(goal_lower),
            "target_time": CoachChatSession._extract_target_time(goal_lower),
            "target_timeline_weeks": CoachChatSession._extract_timeline_weeks(goal_lower),
            "available_days_per_week": CoachChatSession._extract_days_per_week(goal_lower),
        }
        return {key: value for key, value in profile.items() if value not in (None, "")}

    @staticmethod
    def _clarification_questions(goal_profile: dict[str, Any], history_context: dict[str, Any]) -> list[tuple[str, str, Callable[[str], Any]]]:
        questions: list[tuple[str, str, Callable[[str], Any]]] = []
        if "target_event" not in goal_profile:
            questions.append(
                (
                    "target_event",
                    "Quel est l'objectif exact (5 km, 10 km, semi-marathon, marathon, trail, reprise) ?",
                    lambda answer: answer or "objectif-running",
                )
            )
        if "target_timeline_weeks" not in goal_profile:
            questions.append(
                (
                    "target_timeline_weeks",
                    "Dans combien de semaines veux-tu atteindre cet objectif ?",
                    CoachChatSession._parse_int_answer,
                )
            )
        if "available_days_per_week" not in goal_profile:
            questions.append(
                (
                    "available_days_per_week",
                    "Combien de jours par semaine peux-tu courir de facon realiste ?",
                    CoachChatSession._parse_int_answer,
                )
            )
        if not history_context.get("available"):
            questions.append(
                (
                    "current_weekly_distance_km",
                    "Quel est ton volume actuel approximatif en kilometres par semaine ?",
                    CoachChatSession._parse_float_answer,
                )
            )
        questions.append(
            (
                "constraints",
                "As-tu une contrainte importante a prendre en compte (blessure, fatigue, emploi du temps) ? Si non, ecris aucune.",
                lambda answer: answer or "aucune",
            )
        )
        return questions

    @staticmethod
    def _detect_target_event(goal_lower: str) -> str | None:
        mapping = {
            "semi": "semi-marathon",
            "semi-marathon": "semi-marathon",
            "marathon": "marathon",
            "10 km": "10 km",
            "10k": "10 km",
            "5 km": "5 km",
            "5k": "5 km",
            "trail": "trail",
        }
        for key, value in mapping.items():
            if key in goal_lower:
                return value
        return None

    @staticmethod
    def _extract_target_time(goal_lower: str) -> str | None:
        match = re.search(r"(\d{1,2})\s*h\s*(\d{1,2})", goal_lower)
        if match:
            return f"{int(match.group(1))}h{int(match.group(2)):02d}"
        match = re.search(r"(\d{1,2})\s*min", goal_lower)
        if match:
            return f"{int(match.group(1))} min"
        return None

    @staticmethod
    def _extract_timeline_weeks(goal_lower: str) -> int | None:
        match = re.search(r"(\d{1,2})\s*sem", goal_lower)
        return int(match.group(1)) if match else None

    @staticmethod
    def _extract_days_per_week(goal_lower: str) -> int | None:
        match = re.search(r"(\d{1,2})\s*(jour|jours|seance|seances)", goal_lower)
        return int(match.group(1)) if match else None

    @staticmethod
    def _parse_int_answer(answer: str) -> int:
        match = re.search(r"-?\d+", answer)
        if not match:
            raise RuntimeError("A numeric answer was expected for this clarification.")
        return int(match.group(0))

    @staticmethod
    def _parse_float_answer(answer: str) -> float:
        normalized = answer.replace(",", ".")
        match = re.search(r"-?\d+(?:\.\d+)?", normalized)
        if not match:
            raise RuntimeError("A numeric answer was expected for this clarification.")
        return float(match.group(0))


def run_coach_chat(
    *,
    data_dir: Path,
    goal_text: str | None = None,
    input_func: InputFunc = input,
    output_func: OutputFunc = print,
    llm_client: Any | None = None,
) -> dict[str, Any]:
    session = CoachChatSession(
        toolkit=LocalCoachToolkit(data_dir=data_dir),
        llm_client=llm_client or OllamaCoachClient(),
        input_func=input_func,
        output_func=output_func,
    )
    return session.run(goal_text=goal_text)
