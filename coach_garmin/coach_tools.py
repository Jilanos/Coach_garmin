from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Any

import duckdb

from coach_garmin.config import DEFAULT_GOAL_PROFILE_PATH
from coach_garmin.storage import (
    default_coverage_report_path,
    default_db_path,
    default_report_path,
    ensure_data_dirs,
    write_json,
)
from coach_garmin.text_encoding import repair_text_tree


STANDARD_BENCHMARKS: tuple[tuple[str, float, float], ...] = (
    ("5 km", 4.5, 5.5),
    ("10 km", 9.0, 11.0),
    ("semi-marathon", 20.0, 22.5),
    ("marathon", 40.0, 43.5),
)


@dataclass(slots=True)
class LocalCoachToolkit:
    data_dir: Path

    def metrics(self) -> dict[str, Any]:
        ensure_data_dirs(self.data_dir)
        report_path = default_report_path(self.data_dir)
        coverage_path = default_coverage_report_path(self.data_dir)
        report: dict[str, Any] = {}
        if report_path.exists():
            report = repair_text_tree(json.loads(report_path.read_text(encoding="utf-8")))
        coverage: dict[str, Any] = {}
        if coverage_path.exists():
            coverage = repair_text_tree(json.loads(coverage_path.read_text(encoding="utf-8")))

        payload: dict[str, Any] = {
            "report_path": str(report_path),
            "coverage_report_path": str(coverage_path),
            "latest_day": report.get("latest_day"),
            "latest_metrics": report.get("latest_metrics", {}),
            "supported_metrics": report.get("supported_metrics", {}),
            "trend_insights": report.get("trend_insights", {}),
            "coverage": coverage,
        }

        db_path = default_db_path(self.data_dir)
        if not db_path.exists():
            payload["db_available"] = False
            return repair_text_tree(payload)

        payload["db_available"] = True
        con = duckdb.connect(str(db_path), read_only=True)
        try:
            existing_tables = {
                str(row[0]).lower()
                for row in con.execute("SHOW TABLES").fetchall()
            }

            if "acute_load_daily" in existing_tables:
                acute_load = con.execute(
                    """
                    SELECT metric_date, acute_load, chronic_load, load_ratio, acwr_status
                    FROM acute_load_daily
                    WHERE metric_date IS NOT NULL
                    ORDER BY metric_date DESC
                    LIMIT 1
                    """
                ).fetchone()
                if acute_load:
                    payload["acute_load"] = {
                        "metric_date": str(acute_load[0]),
                        "acute_load": acute_load[1],
                        "chronic_load": acute_load[2],
                        "load_ratio": acute_load[3],
                        "acwr_status": acute_load[4],
                    }

            if "training_history_daily" in existing_tables:
                training_status = con.execute(
                    """
                    SELECT metric_date, sport, training_status, fitness_trend, feedback_phrase
                    FROM training_history_daily
                    WHERE metric_date IS NOT NULL
                    ORDER BY metric_date DESC
                    LIMIT 1
                    """
                ).fetchone()
                if training_status:
                    payload["training_status"] = {
                        "metric_date": str(training_status[0]),
                        "sport": training_status[1],
                        "training_status": training_status[2],
                        "fitness_trend": training_status[3],
                        "feedback_phrase": training_status[4],
                    }

            if "heart_rate_zones" in existing_tables:
                hr_zones = con.execute(
                    """
                    SELECT sport, resting_hr, max_hr, zone2_floor, zone3_floor, zone4_floor
                    FROM heart_rate_zones
                    LIMIT 1
                    """
                ).fetchone()
                if hr_zones:
                    payload["heart_rate_zones"] = {
                        "sport": hr_zones[0],
                        "resting_hr": hr_zones[1],
                        "max_hr": hr_zones[2],
                        "zone2_floor": hr_zones[3],
                        "zone3_floor": hr_zones[4],
                        "zone4_floor": hr_zones[5],
                    }
        finally:
            con.close()
        return repair_text_tree(payload)

    def goals(self, goal_profile: dict[str, Any] | None = None) -> dict[str, Any]:
        ensure_data_dirs(self.data_dir)
        goal_path = self._goal_profile_path()
        if goal_profile is None:
            if not goal_path.exists():
                return repair_text_tree({"path": str(goal_path), "goal_profile": {}})
            return repair_text_tree({
                "path": str(goal_path),
                "goal_profile": repair_text_tree(json.loads(goal_path.read_text(encoding="utf-8"))),
            })

        write_json(goal_path, goal_profile)
        return repair_text_tree({"path": str(goal_path), "goal_profile": goal_profile})

    def history(self, days: int = 21) -> dict[str, Any]:
        db_path = default_db_path(self.data_dir)
        if not db_path.exists():
            return repair_text_tree({
                "window_days": days,
                "available": False,
                "recent_activity_count": 0,
                "recent_bike_activity_count": 0,
                "recent_activities": [],
                "coverage": self._load_coverage_report(),
            })

        con = duckdb.connect(str(db_path), read_only=True)
        try:
            latest_day_row = con.execute(
                "SELECT max(activity_date) FROM activities WHERE activity_date IS NOT NULL"
            ).fetchone()
            latest_day = latest_day_row[0]
            if latest_day is None:
                return repair_text_tree({
                    "window_days": days,
                    "available": False,
                    "recent_activity_count": 0,
                    "recent_bike_activity_count": 0,
                    "recent_activities": [],
                    "coverage": self._load_coverage_report(),
                })

            latest_date = self._coerce_date(latest_day)
            window_start = latest_date - timedelta(days=days - 1)
            rows = con.execute(
                """
                SELECT activity_date, activity_type, duration_seconds, distance_meters, average_hr, training_load
                FROM activities
                WHERE activity_date >= ?
                ORDER BY activity_date DESC, started_at DESC
                """,
                [window_start.isoformat()],
            ).fetchall()

            running_types = {"running", "trail_running", "treadmill_running", "indoor_running"}
            bike_types = {"cycling", "bike", "biking", "road_biking", "mountain_biking", "indoor_cycling", "virtual_ride", "ebike", "gravel_cycling"}
            running_rows = [row for row in rows if str(row[1] or "").lower() in running_types]
            bike_rows = [row for row in rows if str(row[1] or "").lower() in bike_types]
            summary_rows = running_rows if running_rows else rows

            recent_activities = [
                {
                    "activity_date": str(row[0]),
                    "activity_type": row[1],
                    "duration_minutes": round((row[2] or 0.0) / 60.0, 1) if row[2] is not None else None,
                    "distance_km": round((row[3] or 0.0) / 1000.0, 2) if row[3] is not None else None,
                    "average_hr": row[4],
                    "training_load": row[5],
                }
                for row in summary_rows[:5]
            ]
            total_distance = sum((row[3] or 0.0) for row in summary_rows) / 1000.0 if summary_rows else 0.0
            bike_distance = sum((row[3] or 0.0) for row in bike_rows) / 1000.0 if bike_rows else 0.0
            total_duration = sum((row[2] or 0.0) for row in summary_rows) / 60.0 if summary_rows else 0.0
            long_run_km = max(((row[3] or 0.0) / 1000.0 for row in summary_rows), default=0.0)
            running_days = len({str(row[0]) for row in summary_rows})
            bike_days = len({str(row[0]) for row in bike_rows})
        finally:
            con.close()

        return repair_text_tree({
            "window_days": days,
            "available": True,
            "latest_activity_day": latest_date.isoformat(),
            "recent_activity_count": len(summary_rows),
            "recent_bike_activity_count": len(bike_rows),
            "recent_activity_count_all": len(rows),
            "recent_running_days": running_days,
            "recent_bike_days": bike_days,
            "total_distance_km": round(total_distance, 2),
            "running_distance_km": round(total_distance, 2),
            "bike_distance_km": round(bike_distance, 2),
            "total_duration_minutes": round(total_duration, 1),
            "long_run_km": round(long_run_km, 2),
            "recent_activities": recent_activities,
            "coverage": self._load_coverage_report(),
        })

    def analysis(self, goal_profile: dict[str, Any]) -> dict[str, Any]:
        db_path = default_db_path(self.data_dir)
        if not db_path.exists():
            return repair_text_tree({
                "available": False,
                "principal_objective": goal_profile.get("principal_objective")
                or goal_profile.get("target_event"),
                "windows": {},
                "benchmarks": [],
                "recommended_benchmark": None,
                "inferred_paces": {},
                "training_phase": "insufficient-data",
                "coverage": self._load_coverage_report(),
                "analysis_summary": "Pas assez de donnees locales pour produire une analyse historique fiable.",
            })

        con = duckdb.connect(str(db_path), read_only=True)
        try:
            latest_day_row = con.execute(
                "SELECT max(activity_date) FROM activities WHERE activity_date IS NOT NULL"
            ).fetchone()
            latest_day = latest_day_row[0]
            if latest_day is None:
                return repair_text_tree({
                    "available": False,
                    "principal_objective": goal_profile.get("principal_objective")
                    or goal_profile.get("target_event"),
                    "windows": {},
                    "benchmarks": [],
                    "recommended_benchmark": None,
                    "inferred_paces": {},
                    "training_phase": "insufficient-data",
                    "coverage": self._load_coverage_report(),
                    "analysis_summary": "Aucune activite n'est disponible pour analyser l'historique.",
                })

            latest_date = self._coerce_date(latest_day)
            windows = {
                "21d": self._summarize_running_window(con, latest_date, 21),
                "90d": self._summarize_running_window(con, latest_date, 90),
                "365d": self._summarize_running_window(con, latest_date, 365),
            }
            benchmarks = self._extract_benchmarks(con, latest_date)
            stated_benchmarks = goal_profile.get("stated_benchmarks", [])
            if isinstance(stated_benchmarks, list):
                benchmarks = [item for item in stated_benchmarks if isinstance(item, dict)] + benchmarks
            principal_objective = self._principal_objective(goal_profile)
            benchmark = self._select_benchmark(principal_objective, benchmarks)
            inferred_paces = self._infer_paces(principal_objective, benchmark, windows)
            training_phase = self._infer_training_phase(goal_profile, windows, benchmark)
            analysis_summary = self._build_analysis_summary(
                goal_profile,
                windows,
                benchmark,
                inferred_paces,
                training_phase,
            )
            signal_highlights = self._build_signal_highlights(windows, benchmark, inferred_paces, training_phase)
        finally:
            con.close()

        return repair_text_tree({
            "available": True,
            "latest_activity_day": latest_date.isoformat(),
            "principal_objective": principal_objective,
            "windows": windows,
            "benchmarks": benchmarks,
            "recommended_benchmark": benchmark,
            "inferred_paces": inferred_paces,
            "training_phase": training_phase,
            "signal_highlights": signal_highlights,
            "coverage": self._load_coverage_report(),
            "analysis_summary": analysis_summary,
        })

    def plan(self, plan_payload: dict[str, Any]) -> dict[str, Any]:
        ensure_data_dirs(self.data_dir)
        timestamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
        plan_path = self.data_dir / "reports" / f"weekly_plan_{timestamp}.json"
        write_json(plan_path, plan_payload)
        return {"path": str(plan_path), "plan": plan_payload}

    def _goal_profile_path(self) -> Path:
        if self.data_dir == DEFAULT_GOAL_PROFILE_PATH.parent.parent:
            return DEFAULT_GOAL_PROFILE_PATH
        return self.data_dir / "reports" / "goal_profile.json"

    def _load_coverage_report(self) -> dict[str, Any]:
        coverage_path = default_coverage_report_path(self.data_dir)
        if not coverage_path.exists():
            return {}
        return repair_text_tree(json.loads(coverage_path.read_text(encoding="utf-8")))

    def _summarize_running_window(self, con: duckdb.DuckDBPyConnection, latest_date: date, days: int) -> dict[str, Any]:
        window_start = latest_date - timedelta(days=days - 1)
        rows = con.execute(
            """
            SELECT activity_date, activity_type, duration_seconds, distance_meters, average_hr, training_load
            FROM activities
            WHERE activity_date >= ?
            ORDER BY activity_date DESC, started_at DESC
            """,
            [window_start.isoformat()],
        ).fetchall()

        running_rows = [row for row in rows if self._is_running_type(row[1])]
        summary_rows = running_rows if running_rows else rows
        total_distance_km = sum((row[3] or 0.0) for row in summary_rows) / 1000.0 if summary_rows else 0.0
        total_duration_minutes = sum((row[2] or 0.0) for row in summary_rows) / 60.0 if summary_rows else 0.0
        active_days = len({str(row[0]) for row in summary_rows})
        activity_count = len(summary_rows)
        average_pace = self._pace_min_per_km(total_duration_minutes, total_distance_km)
        long_run_km = max(((row[3] or 0.0) / 1000.0 for row in summary_rows), default=0.0)
        quality_like_sessions = [
            row
            for row in summary_rows
            if self._pace_min_per_km((row[2] or 0.0) / 60.0, (row[3] or 0.0) / 1000.0) is not None
            and ((row[3] or 0.0) / 1000.0) >= 5.0
            and self._pace_min_per_km((row[2] or 0.0) / 60.0, (row[3] or 0.0) / 1000.0) <= 4.45
        ]

        return {
            "days": days,
            "activity_count": activity_count,
            "active_days": active_days,
            "distance_km": round(total_distance_km, 2),
            "duration_minutes": round(total_duration_minutes, 1),
            "average_pace_min_per_km": average_pace,
            "long_run_km": round(long_run_km, 2),
            "quality_like_session_count": len(quality_like_sessions),
        }

    def _extract_benchmarks(self, con: duckdb.DuckDBPyConnection, latest_date: date) -> list[dict[str, Any]]:
        window_start = latest_date - timedelta(days=364)
        rows = con.execute(
            """
            SELECT activity_date, activity_type, duration_seconds, distance_meters, average_hr, training_load
            FROM activities
            WHERE activity_date >= ?
            ORDER BY activity_date DESC, started_at DESC
            """,
            [window_start.isoformat()],
        ).fetchall()
        benchmarks: list[dict[str, Any]] = []
        for row in rows:
            if not self._is_running_type(row[1]):
                continue
            distance_km = (row[3] or 0.0) / 1000.0
            duration_minutes = (row[2] or 0.0) / 60.0
            pace = self._pace_min_per_km(duration_minutes, distance_km)
            if pace is None:
                continue
            for label, min_km, max_km in STANDARD_BENCHMARKS:
                if min_km <= distance_km <= max_km:
                    benchmarks.append(
                        {
                            "event": label,
                            "activity_date": str(row[0]),
                            "distance_km": round(distance_km, 2),
                            "duration_minutes": round(duration_minutes, 1),
                            "pace_min_per_km": pace,
                            "average_hr": row[4],
                            "training_load": row[5],
                        }
                    )
                    break
        return benchmarks

    @staticmethod
    def _principal_objective(goal_profile: dict[str, Any]) -> str:
        return str(
            goal_profile.get("principal_objective")
            or goal_profile.get("target_event")
            or goal_profile.get("goal_text")
            or "running goal"
        )

    def _select_benchmark(self, principal_objective: str, benchmarks: list[dict[str, Any]]) -> dict[str, Any] | None:
        if not benchmarks:
            return None
        objective = principal_objective.lower()
        preferred_events: list[str]
        if "10" in objective:
            preferred_events = ["10 km", "5 km", "semi-marathon"]
        elif "semi" in objective:
            preferred_events = ["semi-marathon", "10 km", "5 km"]
        elif "marathon" in objective:
            preferred_events = ["marathon", "semi-marathon", "10 km"]
        elif "5" in objective:
            preferred_events = ["5 km", "10 km"]
        else:
            preferred_events = ["10 km", "5 km", "semi-marathon", "marathon"]

        for preferred in preferred_events:
            candidates = [item for item in benchmarks if item["event"] == preferred]
            if candidates:
                return candidates[0]
        return benchmarks[0]

    def _infer_paces(
        self,
        principal_objective: str,
        benchmark: dict[str, Any] | None,
        windows: dict[str, Any],
    ) -> dict[str, Any]:
        if benchmark is None:
            return {
                "confidence": "low",
                "easy_pace_min_per_km": None,
                "threshold_pace_min_per_km": None,
                "interval_pace_min_per_km": None,
                "marathon_pace_min_per_km": None,
            }

        base_pace = float(benchmark["pace_min_per_km"])
        reduced_load = windows["21d"]["distance_km"] < 35 or windows["21d"]["quality_like_session_count"] <= 1
        easy_adjustment = 0.7 if reduced_load else 0.55
        threshold_adjustment = 0.18 if "10 km" in benchmark["event"] else 0.12
        interval_adjustment = -0.06 if "10 km" in benchmark["event"] else -0.12
        marathon_adjustment = 0.3 if "10 km" in benchmark["event"] else 0.18
        return {
            "confidence": "high" if windows["90d"]["distance_km"] >= 120 else "medium",
            "source_event": benchmark["event"],
            "source_date": benchmark["activity_date"],
            "source_pace_min_per_km": round(base_pace, 2),
            "easy_pace_min_per_km": round(base_pace + easy_adjustment, 2),
            "threshold_pace_min_per_km": round(base_pace + threshold_adjustment, 2),
            "interval_pace_min_per_km": round(max(2.8, base_pace + interval_adjustment), 2),
            "marathon_pace_min_per_km": round(base_pace + marathon_adjustment, 2),
        }

    def _infer_training_phase(
        self,
        goal_profile: dict[str, Any],
        windows: dict[str, Any],
        benchmark: dict[str, Any] | None,
    ) -> str:
        constraints = str(goal_profile.get("constraints", "")).lower()
        if any(term in constraints for term in ("periost", "bless", "douleur", "sensible")):
            return "return-from-injury"
        if windows["21d"]["distance_km"] < 25 or windows["21d"]["active_days"] <= 2:
            return "rebuild"
        objective = self._principal_objective(goal_profile).lower()
        if "marathon" in objective:
            return "marathon-base"
        if "10" in objective and benchmark is not None:
            return "10k-progression"
        return "general-build"

    def _build_analysis_summary(
        self,
        goal_profile: dict[str, Any],
        windows: dict[str, Any],
        benchmark: dict[str, Any] | None,
        inferred_paces: dict[str, Any],
        training_phase: str,
    ) -> str:
        principal = self._principal_objective(goal_profile)
        window_21 = windows["21d"]
        if benchmark is None:
            return (
                f"Objectif principal analyse: {principal}. "
                f"La priorite actuelle est une phase de {training_phase} avec des reperes d'allure encore trop faibles. "
                f"Sur 21 jours, tu as {window_21['distance_km']} km sur {window_21['active_days']} jours actifs, "
                "donc le plan doit rester structure mais prudent."
            )

        source_event = benchmark["event"]
        source_date = benchmark["activity_date"]
        source_pace = self._format_pace(benchmark["pace_min_per_km"])
        threshold_pace = self._format_pace(inferred_paces.get("threshold_pace_min_per_km"))
        return (
            f"Objectif principal analyse: {principal}. "
            f"Le meilleur repere recent exploitable est un {source_event} du {source_date} couru a {source_pace}/km. "
            f"Sur 21 jours, tu as {window_21['distance_km']} km sur {window_21['active_days']} jours actifs. "
            f"La phase actuelle est {training_phase}. "
            f"La logique de la semaine est donc de repartir d'une base durable, avec une seule vraie seance de qualite et des allures de seuil autour de {threshold_pace}/km."
        )

    def _build_signal_highlights(
        self,
        windows: dict[str, Any],
        benchmark: dict[str, Any] | None,
        inferred_paces: dict[str, Any],
        training_phase: str,
    ) -> list[str]:
        highlights = [
            f"window_21d_distance_km={windows['21d']['distance_km']}",
            f"window_21d_active_days={windows['21d']['active_days']}",
            f"window_90d_distance_km={windows['90d']['distance_km']}",
            f"training_phase={training_phase}",
        ]
        if benchmark is not None:
            highlights.append(
                f"benchmark_{benchmark['event'].replace('-', '_').replace(' ', '_').lower()}={self._format_pace(benchmark['pace_min_per_km'])}/km"
            )
        if inferred_paces.get("threshold_pace_min_per_km") is not None:
            highlights.append(f"threshold_pace={self._format_pace(inferred_paces['threshold_pace_min_per_km'])}/km")
        return highlights

    @staticmethod
    def _is_running_type(value: Any) -> bool:
        return str(value or "").lower() in {"running", "trail_running", "walking", "hiking"}

    @staticmethod
    def _pace_min_per_km(duration_minutes: float, distance_km: float) -> float | None:
        if duration_minutes <= 0 or distance_km <= 0:
            return None
        return round(duration_minutes / distance_km, 2)

    @staticmethod
    def _format_pace(value: Any) -> str:
        if value in (None, ""):
            return "inconnue"
        total_minutes = float(value)
        minutes = int(total_minutes)
        seconds = int(round((total_minutes - minutes) * 60))
        if seconds == 60:
            minutes += 1
            seconds = 0
        return f"{minutes}:{seconds:02d}"

    @staticmethod
    def _coerce_date(value: Any) -> date:
        if isinstance(value, date):
            return value
        return date.fromisoformat(str(value))
