from __future__ import annotations

from pathlib import Path

DEFAULT_DATA_DIR = Path("data")
DEFAULT_DB_PATH = DEFAULT_DATA_DIR / "normalized" / "coach_garmin.duckdb"
DEFAULT_REPORT_PATH = DEFAULT_DATA_DIR / "reports" / "latest_metrics.json"
DEFAULT_COVERAGE_REPORT_PATH = DEFAULT_DATA_DIR / "reports" / "feature_coverage.json"
DEFAULT_LOCAL_DIR = Path(".local")
DEFAULT_GARMIN_TOKENSTORE = DEFAULT_LOCAL_DIR / "garmin" / "garmin_tokens.json"
DEFAULT_GARMIN_LOOKBACK_DAYS = 30
DEFAULT_ENV_FILE = Path(".env.local")
DEFAULT_GARMIN_EMAIL_ENV = "COACH_GARMIN_GARMIN_EMAIL"
DEFAULT_GARMIN_PASSWORD_ENV = "COACH_GARMIN_GARMIN_PASSWORD"
DEFAULT_OLLAMA_BASE_URL = "http://127.0.0.1:11434"
DEFAULT_OLLAMA_MODEL = "qwen2.5:7b"
DEFAULT_GOAL_PROFILE_PATH = DEFAULT_DATA_DIR / "reports" / "goal_profile.json"

SUPPORTED_DATASETS = (
    "activities",
    "sleep",
    "heart_rate",
    "hrv",
    "stress",
    "acute_load",
    "training_history",
    "profile",
    "heart_rate_zones",
    "device_raw",
    "settings_raw",
    "body_battery",
    "steps",
    "intensity_minutes",
    "training_readiness",
    "recovery_time",
)

AUTHENTICATED_DATASETS = (
    "activities",
    "sleep",
    "heart_rate",
    "hrv",
    "stress",
    "steps",
)

DATASET_ALIASES = {
    "activities": "activities",
    "activity": "activities",
    "runs": "activities",
    "run": "activities",
    "sleep": "sleep",
    "sleeps": "sleep",
    "heart_rate": "heart_rate",
    "heartrate": "heart_rate",
    "restingheartrate": "heart_rate",
    "rhr": "heart_rate",
    "hrv": "hrv",
    "stress": "stress",
    "acuteload": "acute_load",
    "acute_load": "acute_load",
    "traininghistory": "training_history",
    "training_history": "training_history",
    "profile": "profile",
    "userprofile": "profile",
    "heartratezones": "heart_rate_zones",
    "heart_rate_zones": "heart_rate_zones",
    "device": "device_raw",
    "device_raw": "device_raw",
    "settings": "settings_raw",
    "settings_raw": "settings_raw",
    "bodybattery": "body_battery",
    "body_battery": "body_battery",
    "steps": "steps",
    "dailysteps": "steps",
    "intensityminutes": "intensity_minutes",
    "intensity_minutes": "intensity_minutes",
    "trainingreadiness": "training_readiness",
    "training_readiness": "training_readiness",
    "recoverytime": "recovery_time",
    "recovery_time": "recovery_time",
}
