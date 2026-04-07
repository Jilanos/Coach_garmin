from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Any

import duckdb

from coach_garmin.config import DEFAULT_GOAL_PROFILE_PATH
from coach_garmin.storage import default_db_path, default_report_path, ensure_data_dirs, write_json


@dataclass(slots=True)
class LocalCoachToolkit:
    data_dir: Path

    def metrics(self) -> dict[str, Any]:
        ensure_data_dirs(self.data_dir)
        report_path = default_report_path(self.data_dir)
        report: dict[str, Any] = {}
        if report_path.exists():
            report = json.loads(report_path.read_text(encoding="utf-8"))

        payload: dict[str, Any] = {
            "report_path": str(report_path),
            "latest_day": report.get("latest_day"),
            "latest_metrics": report.get("latest_metrics", {}),
            "supported_metrics": report.get("supported_metrics", {}),
        }

        db_path = default_db_path(self.data_dir)
        if not db_path.exists():
            payload["db_available"] = False
            return payload

        payload["db_available"] = True
        con = duckdb.connect(str(db_path), read_only=True)
        try:
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
        return payload

    def goals(self, goal_profile: dict[str, Any] | None = None) -> dict[str, Any]:
        ensure_data_dirs(self.data_dir)
        goal_path = self._goal_profile_path()
        if goal_profile is None:
            if not goal_path.exists():
                return {"path": str(goal_path), "goal_profile": {}}
            return {
                "path": str(goal_path),
                "goal_profile": json.loads(goal_path.read_text(encoding="utf-8")),
            }

        write_json(goal_path, goal_profile)
        return {"path": str(goal_path), "goal_profile": goal_profile}

    def history(self, days: int = 21) -> dict[str, Any]:
        db_path = default_db_path(self.data_dir)
        if not db_path.exists():
            return {
                "window_days": days,
                "available": False,
                "recent_activity_count": 0,
                "recent_activities": [],
            }

        con = duckdb.connect(str(db_path), read_only=True)
        try:
            latest_day_row = con.execute(
                "SELECT max(activity_date) FROM activities WHERE activity_date IS NOT NULL"
            ).fetchone()
            latest_day = latest_day_row[0]
            if latest_day is None:
                return {
                    "window_days": days,
                    "available": False,
                    "recent_activity_count": 0,
                    "recent_activities": [],
                }

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

            running_types = {"running", "trail_running", "walking", "hiking"}
            running_rows = [row for row in rows if str(row[1] or "").lower() in running_types]
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
            total_duration = sum((row[2] or 0.0) for row in summary_rows) / 60.0 if summary_rows else 0.0
            long_run_km = max(((row[3] or 0.0) / 1000.0 for row in summary_rows), default=0.0)
            running_days = len({str(row[0]) for row in summary_rows})
        finally:
            con.close()

        return {
            "window_days": days,
            "available": True,
            "latest_activity_day": latest_date.isoformat(),
            "recent_activity_count": len(summary_rows),
            "recent_activity_count_all": len(rows),
            "recent_running_days": running_days,
            "total_distance_km": round(total_distance, 2),
            "total_duration_minutes": round(total_duration, 1),
            "long_run_km": round(long_run_km, 2),
            "recent_activities": recent_activities,
        }

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

    @staticmethod
    def _coerce_date(value: Any) -> date:
        if isinstance(value, date):
            return value
        return date.fromisoformat(str(value))
