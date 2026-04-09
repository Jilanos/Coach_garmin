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
            goal_profile = self._merge_existing_goal_profile(existing_goal, goal_profile)

        questions_asked: list[str] = []
        for key, question, parser in self._clarification_questions(goal_profile, history_context):
            answer = self.input_func(f"{question} ").strip()
            questions_asked.append(question)
            goal_profile[key] = parser(answer)

        goal_profile["goal_text"] = goal_text
        goal_profile["target_event"] = self._primary_event(goal_profile)
        goal_profile["updated_at"] = datetime.now(UTC).isoformat()
        goal_state = self.toolkit.goals(goal_profile)

        metrics_context = self.toolkit.metrics()
        analysis_context = self.toolkit.analysis(goal_profile)
        plan_skeleton = self._build_plan_skeleton(goal_profile, metrics_context, history_context, analysis_context)
        prompt_bundle = {
            "goal_profile": goal_profile,
            "metrics": metrics_context,
            "history": history_context,
            "analysis": analysis_context,
            "coverage": metrics_context.get("coverage", {}),
            "suggested_plan_skeleton": plan_skeleton,
            "generation_rules": {
                "language": "fr",
                "plan_days": 7,
                "must_reference_local_signals": True,
                "must_be_cautious": True,
                "must_be_direct_and_analytical": True,
                "must_analyze_before_planning": True,
                "must_use_pace_when_confident": True,
                "must_respect_signal_coverage": True,
            },
        }
        plan_response = self.llm_client.generate_weekly_plan(prompt_bundle)
        normalized_plan = self._normalize_weekly_plan(plan_response.get("weekly_plan", []), plan_skeleton)
        normalized_plan = self._enrich_weekly_plan(normalized_plan, plan_skeleton)
        saved_plan_payload = {
            "generated_at": datetime.now(UTC).isoformat(),
            "goal_profile": goal_profile,
            "metrics_snapshot": metrics_context,
            "history_snapshot": history_context,
            "analysis_snapshot": analysis_context,
            "coverage_snapshot": metrics_context.get("coverage", {}),
            "coach_summary": self._choose_coach_summary(
                plan_response.get("coach_summary", ""),
                analysis_context,
            ),
            "signals_used": self._normalize_signals_used(
                plan_response.get("signals_used", []),
                metrics_context,
                history_context,
                analysis_context,
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
            self.output_func("Analyse coach")
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
        analysis_context: dict[str, Any],
    ) -> list[dict[str, Any]]:
        days = ["Lundi", "Mardi", "Mercredi", "Jeudi", "Vendredi", "Samedi", "Dimanche"]
        available_days = int(goal_profile.get("available_days_per_week", 4) or 4)
        latest_metrics = metrics_context.get("latest_metrics", {})
        fatigue = bool(latest_metrics.get("fatigue_flag"))
        overreaching = bool(latest_metrics.get("overreaching_flag"))
        observed_long_run_km = float(history_context.get("long_run_km", 12.0) or 12.0)
        event = str(goal_profile.get("principal_objective") or goal_profile.get("target_event", "running goal"))
        training_phase = str(analysis_context.get("training_phase", "general-build"))
        inferred_paces = analysis_context.get("inferred_paces", {})
        easy_pace = CoachChatSession._format_pace_range(inferred_paces.get("easy_pace_min_per_km"), 0.12)
        threshold_pace = CoachChatSession._format_pace_range(inferred_paces.get("threshold_pace_min_per_km"), 0.08)
        interval_pace = CoachChatSession._format_pace_range(inferred_paces.get("interval_pace_min_per_km"), 0.06)
        long_run_km = CoachChatSession._target_long_run_km(event, observed_long_run_km, fatigue or overreaching)

        if available_days <= 2:
            running_days = {"Mercredi", "Dimanche"}
        elif available_days == 3:
            running_days = {"Mardi", "Jeudi", "Dimanche"}
        elif available_days == 4:
            running_days = {"Lundi", "Mercredi", "Samedi", "Dimanche"}
        else:
            running_days = {"Lundi", "Mardi", "Jeudi", "Samedi", "Dimanche"}

        intensity_label = "Z3-Z4" if not fatigue and not overreaching else "Z2-Z3"
        quality_title, quality_objective, quality_notes = CoachChatSession._quality_session_blueprint(
            event=event,
            training_phase=training_phase,
            threshold_pace=threshold_pace,
            interval_pace=interval_pace,
            fatigue=fatigue,
            overreaching=overreaching,
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
                        "session_title": "Sortie longue progressive",
                        "objective": "Construire l'endurance specifique sans perdre le controle mecanique.",
                        "duration_minutes": long_run_minutes,
                        "intensity": "Z2",
                        "notes": (
                            "Rester facile tout du long, avec 10 a 15 min un peu plus toniques en fin de sortie seulement si les sensations sont bonnes."
                            if training_phase != "return-from-injury"
                            else "Rester strictement facile et couper court au moindre signal tibial."
                        ),
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
                        "notes": quality_notes,
                    }
                )
                continue

            skeleton.append(
                {
                    "day": day,
                    "session_title": "Footing facile avec plafond d'allure",
                    "objective": "Ajouter du volume utile sans surcharge excessive et sans transformer la sortie en faux tempo.",
                    "duration_minutes": 40 if fatigue or overreaching else 50,
                    "intensity": f"Z1-Z2 | {easy_pace}/km" if easy_pace != "RPE 4-5" else "Z1-Z2",
                    "notes": (
                        f"Ne pas aller plus vite que {easy_pace}/km et rester capable de parler facilement."
                        if easy_pace != "RPE 4-5"
                        else "Rester a RPE 4-5 et respirer confortablement."
                    ),
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
        analysis_context: dict[str, Any],
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
            "recent_benchmark_performance",
            "training_phase",
            "pace_inference",
            "window_21d",
            "window_90d",
        }
        normalized = [
            str(item).strip()
            for item in raw_signals
            if isinstance(item, str) and str(item).strip() in allowed
        ]

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
        if analysis_context.get("recommended_benchmark"):
            fallback.append("recent_benchmark_performance")
        if analysis_context.get("training_phase"):
            fallback.append("training_phase")
        if analysis_context.get("inferred_paces", {}).get("threshold_pace_min_per_km") is not None:
            fallback.append("pace_inference")
        if analysis_context.get("windows"):
            fallback.append("window_21d")
            fallback.append("window_90d")
        merged = normalized[:]
        for item in fallback or ["load_7d"]:
            if item not in merged:
                merged.append(item)
        return merged

    @staticmethod
    def _build_goal_profile(goal_text: str) -> dict[str, Any]:
        goal_lower = goal_text.lower()
        detected_goals = CoachChatSession._extract_goal_events(goal_lower)
        profile: dict[str, Any] = {
            "goal_text": goal_text,
            "target_event": detected_goals[0] if detected_goals else None,
            "detected_goals": detected_goals,
            "stated_benchmarks": CoachChatSession._extract_stated_benchmarks(goal_lower),
            "target_time": CoachChatSession._extract_target_time(goal_lower),
            "target_timeline_weeks": CoachChatSession._extract_timeline_weeks(goal_lower),
            "available_days_per_week": CoachChatSession._extract_days_per_week(goal_lower),
        }
        return {key: value for key, value in profile.items() if value not in (None, "")}

    @staticmethod
    def _merge_existing_goal_profile(existing_goal: dict[str, Any], new_goal_profile: dict[str, Any]) -> dict[str, Any]:
        carryable_keys = {
            "available_days_per_week",
            "constraints",
            "current_weekly_distance_km",
        }
        merged = dict(new_goal_profile)
        for key in carryable_keys:
            if key not in merged and existing_goal.get(key) not in (None, ""):
                merged[key] = existing_goal[key]
        return merged

    @staticmethod
    def _clarification_questions(goal_profile: dict[str, Any], history_context: dict[str, Any]) -> list[tuple[str, str, Callable[[str], Any]]]:
        questions: list[tuple[str, str, Callable[[str], Any]]] = []
        detected_goals = goal_profile.get("detected_goals", [])
        if isinstance(detected_goals, list) and len(detected_goals) > 1 and "principal_objective" not in goal_profile:
            questions.append(
                (
                    "principal_objective",
                    "Tu mentionnes plusieurs objectifs. Lequel est prioritaire pour les 6 a 12 prochaines semaines ?",
                    lambda answer: answer.strip() or str(detected_goals[0]),
                )
            )
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
                    CoachChatSession._parse_timeline_answer,
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
        events = CoachChatSession._extract_goal_events(goal_lower)
        return events[0] if events else None

    @staticmethod
    def _extract_goal_events(goal_lower: str) -> list[str]:
        mapping = (
            ("semi-marathon", "semi-marathon"),
            ("semi marathon", "semi-marathon"),
            ("semi", "semi-marathon"),
            ("marathon", "marathon"),
            ("10 km", "10 km"),
            ("10km", "10 km"),
            ("10k", "10 km"),
            ("5 km", "5 km"),
            ("5km", "5 km"),
            ("5k", "5 km"),
            ("trail", "trail"),
        )
        detected: list[str] = []
        for key, value in mapping:
            if key in goal_lower and value not in detected:
                detected.append(value)
        return detected

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
    def _extract_stated_benchmarks(goal_lower: str) -> list[dict[str, Any]]:
        benchmarks: list[dict[str, Any]] = []
        patterns = (
            ("10 km", r"10\s*km.*?(?:sub\s*|sous\s*)(\d{1,2})"),
            ("5 km", r"5\s*km.*?(?:sub\s*|sous\s*)(\d{1,2})"),
            ("semi-marathon", r"semi.*?(?:sub\s*|sous\s*)(\d{1,2})\s*h?\s*(\d{0,2})"),
            ("marathon", r"marathon.*?(?:sub\s*|sous\s*)(\d{1,2})\s*h?\s*(\d{0,2})"),
        )
        for event, pattern in patterns:
            match = re.search(pattern, goal_lower)
            if not match:
                continue
            if event in {"10 km", "5 km"}:
                total_minutes = float(match.group(1))
                distance_km = 10.0 if event == "10 km" else 5.0
            else:
                hours = int(match.group(1))
                minutes = int(match.group(2) or 0)
                total_minutes = float(hours * 60 + minutes)
                distance_km = 21.1 if event == "semi-marathon" else 42.2
            benchmarks.append(
                {
                    "event": event,
                    "activity_date": "stated-in-goal",
                    "distance_km": distance_km,
                    "duration_minutes": round(total_minutes, 1),
                    "pace_min_per_km": round(total_minutes / distance_km, 2),
                    "average_hr": None,
                    "training_load": None,
                }
            )
        return benchmarks

    @staticmethod
    def _extract_timeline_weeks(goal_lower: str) -> int | None:
        match = re.search(r"(\d{1,2})\s*sem", goal_lower)
        if match:
            return int(match.group(1))
        month_match = re.search(r"(\d{1,2})\s*mois", goal_lower)
        if month_match:
            return int(month_match.group(1)) * 4
        return None

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
    def _parse_timeline_answer(answer: str) -> int:
        normalized = answer.replace(",", ".").lower()
        numbers = [int(value) for value in re.findall(r"\d{1,2}", normalized)]
        if not numbers:
            raise RuntimeError("A numeric answer was expected for this clarification.")
        horizon = max(numbers)
        if "mois" in normalized or "month" in normalized:
            return horizon * 4
        return horizon

    @staticmethod
    def _parse_float_answer(answer: str) -> float:
        normalized = answer.replace(",", ".")
        match = re.search(r"-?\d+(?:\.\d+)?", normalized)
        if not match:
            raise RuntimeError("A numeric answer was expected for this clarification.")
        return float(match.group(0))

    @staticmethod
    def _primary_event(goal_profile: dict[str, Any]) -> str:
        principal = goal_profile.get("principal_objective")
        if principal:
            detected = CoachChatSession._detect_target_event(str(principal).lower())
            if detected:
                return detected
            return str(principal)
        return str(goal_profile.get("target_event") or "running goal")

    @staticmethod
    def _quality_session_blueprint(
        *,
        event: str,
        training_phase: str,
        threshold_pace: str,
        interval_pace: str,
        fatigue: bool,
        overreaching: bool,
    ) -> tuple[str, str, str]:
        normalized_event = event.lower()
        if training_phase == "return-from-injury":
            return (
                "Qualite legere 6 x 2 min",
                "Reintroduire la qualite sans empiler de charge mecanique trop vite.",
                "20 min faciles puis 6 x 2 min un peu plus vite avec 2 min faciles. Rester propre techniquement et couper au moindre signal de douleur.",
            )
        if "10" in normalized_event:
            return (
                f"Seuil 3 x 8 min autour de {threshold_pace}/km" if threshold_pace != "RPE 7" else "Seuil 3 x 8 min",
                "Remettre une vraie seance orientee 10 km sans multiplier les rappels rapides la meme semaine.",
                (
                    f"20 min faciles puis 3 x 8 min autour de {threshold_pace}/km avec 2 min trottées. Retour au calme 10 a 15 min."
                    if threshold_pace != "RPE 7"
                    else "20 min faciles puis 3 x 8 min a RPE 7 avec 2 min trottées. Retour au calme 10 a 15 min."
                ),
            )
        if "marathon" in normalized_event:
            return (
                f"Tempo 2 x 15 min autour de {threshold_pace}/km" if threshold_pace != "RPE 7" else "Tempo 2 x 15 min",
                "Construire la base d'allure utile sans transformer la semaine en bloc marathon trop agressif.",
                (
                    f"20 min faciles puis 2 x 15 min autour de {threshold_pace}/km avec 4 min faciles. Finir frais."
                    if threshold_pace != "RPE 7"
                    else "20 min faciles puis 2 x 15 min a RPE 7 avec 4 min faciles. Finir frais."
                ),
            )
        if fatigue or overreaching:
            return (
                "Seance de rappel 8 x 1 min",
                "Entretenir un peu d'intensite tout en gardant un cout de fatigue limite.",
                "20 min faciles puis 8 x 1 min tonique / 1 min facile. Tout doit rester sous controle.",
            )
        return (
            f"10 x 400 m autour de {interval_pace}/km" if interval_pace != "RPE 8" else "10 x 400 m controle",
            "Garder une vraie seance de rythme pour ancrer l'economie de course.",
            (
                f"20 min faciles puis 10 x 400 m autour de {interval_pace}/km avec 200 m de trot. Retour au calme 10 min."
                if interval_pace != "RPE 8"
                else "20 min faciles puis 10 x 400 m a RPE 8 avec 200 m de trot. Retour au calme 10 min."
            ),
        )

    @staticmethod
    def _format_pace_range(base_pace: Any, delta: float) -> str:
        if base_pace in (None, ""):
            return "RPE 4-5" if delta >= 0.1 else "RPE 7"
        low = float(base_pace) - delta
        high = float(base_pace) + delta
        return f"{CoachChatSession._format_pace(low)}-{CoachChatSession._format_pace(high)}"

    @staticmethod
    def _format_pace(value: float) -> str:
        minutes = int(value)
        seconds = int(round((value - minutes) * 60))
        if seconds == 60:
            minutes += 1
            seconds = 0
        return f"{minutes}:{seconds:02d}"

    @staticmethod
    def _enrich_weekly_plan(
        weekly_plan: list[dict[str, Any]],
        plan_skeleton: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        skeleton_by_day = {item["day"]: item for item in plan_skeleton}
        generic_titles = {
            "recovery run",
            "footing facile",
            "session de qualite controlee",
            "seance allure specifique",
            "pause",
            "long run",
        }
        quality_markers = ("seuil", "tempo", "interval", "qualit", "allure", "400 m", "1000 m")
        enriched: list[dict[str, Any]] = []
        for session in weekly_plan:
            skeleton = skeleton_by_day.get(str(session.get("day", "")), {})
            session_title = str(session.get("session_title", ""))
            objective = str(session.get("objective", ""))
            notes = str(session.get("notes", ""))
            session_title_lower = session_title.strip().lower()
            skeleton_title_lower = str(skeleton.get("session_title", "")).strip().lower()
            session_is_quality = any(marker in session_title_lower for marker in quality_markers)
            skeleton_is_easy_or_rest = any(
                marker in skeleton_title_lower
                for marker in ("footing", "repos", "sortie longue", "adaptation")
            )
            if session_is_quality and skeleton_is_easy_or_rest:
                enriched.append(dict(skeleton))
                continue
            if session_title.strip().lower() in generic_titles and skeleton.get("session_title"):
                session["session_title"] = skeleton["session_title"]
            if len(objective.strip()) < 35 and skeleton.get("objective"):
                session["objective"] = skeleton["objective"]
            if len(notes.strip()) < 25 and skeleton.get("notes"):
                session["notes"] = skeleton["notes"]
            if (
                str(session.get("intensity", "")).strip() in {"Z2-Z3", "Z1-Z2", "Repos"}
                or "pace" in str(session.get("intensity", "")).lower()
            ) and skeleton.get("intensity"):
                session["intensity"] = skeleton["intensity"]
            enriched.append(session)
        return enriched

    @staticmethod
    def _choose_coach_summary(raw_summary: Any, analysis_context: dict[str, Any]) -> str:
        summary = str(raw_summary or "").strip()
        benchmark = analysis_context.get("recommended_benchmark")
        analysis_summary = str(analysis_context.get("analysis_summary", "")).strip()
        if not summary:
            return analysis_summary
        generic_markers = (
            "plan d'entrainement",
            "plan d'entraînement",
            "le plan integre",
            "le plan intègre",
            "des jours de recuperation",
            "des jours de récupération",
        )
        if any(marker in summary.lower() for marker in generic_markers):
            return analysis_summary or summary
        if benchmark and benchmark["event"] not in summary and analysis_summary:
            return analysis_summary
        return summary


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
