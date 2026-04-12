from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from coach_garmin.coach_gemini import GeminiCoachClient
from coach_garmin.coach_ollama import OllamaCoachClient
from coach_garmin.coach_openai import OpenAICoachClient
from coach_garmin.config import (
    DEFAULT_GEMINI_BASE_URL,
    DEFAULT_GEMINI_MODEL,
    DEFAULT_OLLAMA_BASE_URL,
    DEFAULT_OLLAMA_MODEL,
    DEFAULT_OPENAI_BASE_URL,
    DEFAULT_OPENAI_MODEL,
)
from coach_garmin.env import resolve_secret


@dataclass(slots=True)
class CoachLLMConfig:
    provider: str = "ollama"
    model: str | None = None
    base_url: str | None = None
    api_key: str | None = None


def build_coach_client(config: CoachLLMConfig) -> Any:
    provider = config.provider.strip().lower()
    if provider == "ollama":
        return OllamaCoachClient(
            base_url=config.base_url or DEFAULT_OLLAMA_BASE_URL,
            model=config.model or DEFAULT_OLLAMA_MODEL,
        )
    if provider == "gemini":
        api_key = config.api_key or resolve_secret("GEMINI_API_KEY")
        if not api_key:
            raise RuntimeError("GEMINI_API_KEY is missing. Put it in the environment or in .env.local, then retry.")
        return GeminiCoachClient(
            api_key=api_key,
            base_url=config.base_url or DEFAULT_GEMINI_BASE_URL,
            model=config.model or DEFAULT_GEMINI_MODEL,
        )
    if provider == "openai":
        api_key = config.api_key or resolve_secret("OPENAI_API_KEY")
        if not api_key:
            raise RuntimeError("OPENAI_API_KEY is missing. Put it in the environment or in .env.local, then retry.")
        return OpenAICoachClient(
            api_key=api_key,
            base_url=config.base_url or DEFAULT_OPENAI_BASE_URL,
            model=config.model or DEFAULT_OPENAI_MODEL,
        )
    raise RuntimeError(f"Unsupported coach provider '{config.provider}'.")
