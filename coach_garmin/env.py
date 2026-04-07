from __future__ import annotations

import os
from pathlib import Path

from coach_garmin.config import DEFAULT_ENV_FILE


def load_local_env(path: Path = DEFAULT_ENV_FILE) -> dict[str, str]:
    if not path.exists():
        return {}

    values: dict[str, str] = {}
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip().strip('"').strip("'")
    return values


def resolve_secret(name: str, env_file: Path = DEFAULT_ENV_FILE) -> str | None:
    current = os.getenv(name)
    if current:
        return current
    return load_local_env(env_file).get(name)
