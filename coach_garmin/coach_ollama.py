from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from coach_garmin.config import DEFAULT_OLLAMA_BASE_URL, DEFAULT_OLLAMA_MODEL


class OllamaConnectionError(RuntimeError):
    pass


class OllamaModelError(RuntimeError):
    pass


@dataclass(slots=True)
class OllamaCoachClient:
    base_url: str = DEFAULT_OLLAMA_BASE_URL
    model: str = DEFAULT_OLLAMA_MODEL
    timeout_seconds: int = 60

    def ensure_ready(self) -> None:
        payload = self._request_json("/api/tags", {})
        models = payload.get("models", [])
        if not isinstance(models, list):
            raise OllamaConnectionError("Ollama responded without a models list.")
        if not any(isinstance(item, dict) and item.get("name") == self.model for item in models):
            raise OllamaModelError(
                f"Ollama is reachable but the model '{self.model}' is missing. Run `ollama pull {self.model}`."
            )

    def generate_weekly_plan(self, prompt_bundle: dict[str, Any]) -> dict[str, Any]:
        self.ensure_ready()
        prompt = self._build_prompt(prompt_bundle)
        text = self._chat(prompt)
        parsed = self._parse_json_response(text)
        if "weekly_plan" not in parsed or not isinstance(parsed["weekly_plan"], list):
            raise RuntimeError("Ollama returned a response without a valid weekly plan payload.")
        return parsed

    def _chat(self, prompt: str) -> str:
        payload = self._request_json(
            "/api/chat",
            {
                "model": self.model,
                "stream": False,
                "messages": [
                    {
                        "role": "system",
                        "content": (
                            "You are a cautious French running coach. "
                            "Use only the provided local context. Do not give medical advice. "
                            "Respond with valid JSON only."
                        ),
                    },
                    {"role": "user", "content": prompt},
                ],
            },
        )
        message = payload.get("message")
        if not isinstance(message, dict) or not isinstance(message.get("content"), str):
            raise RuntimeError("Ollama returned an unexpected chat payload.")
        return message["content"]

    def _request_json(self, path: str, payload: dict[str, Any]) -> dict[str, Any]:
        request = Request(
            f"{self.base_url}{path}",
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        if path == "/api/tags":
            request = Request(f"{self.base_url}{path}", method="GET")
        try:
            with urlopen(request, timeout=self.timeout_seconds) as response:
                return json.loads(response.read().decode("utf-8"))
        except HTTPError as exc:
            raise OllamaConnectionError(f"Ollama request failed with HTTP {exc.code}.") from exc
        except URLError as exc:
            raise OllamaConnectionError(
                "Ollama is unavailable. Start the local Ollama app or `ollama serve`, then retry."
            ) from exc

    @staticmethod
    def _build_prompt(prompt_bundle: dict[str, Any]) -> str:
        schema = {
            "coach_summary": "short summary in French",
            "signals_used": ["list of local signals mentioned in the recommendation"],
            "weekly_plan": [
                {
                    "day": "Monday",
                    "session_title": "Recovery run",
                    "objective": "why this session exists",
                    "duration_minutes": 45,
                    "intensity": "Z1-Z2 or RPE label",
                    "notes": "recovery or execution notes",
                }
            ],
        }
        return (
            "Build a one-week running plan in French from the provided local context.\n"
            "Return valid JSON only.\n"
            f"Required schema: {json.dumps(schema, ensure_ascii=True)}\n"
            f"Context: {json.dumps(prompt_bundle, ensure_ascii=True)}"
        )

    @staticmethod
    def _parse_json_response(content: str) -> dict[str, Any]:
        text = content.strip()
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            start = text.find("{")
            end = text.rfind("}")
            if start == -1 or end == -1 or end <= start:
                raise RuntimeError("Ollama returned non-JSON output for the weekly plan.")
            try:
                return json.loads(text[start : end + 1])
            except json.JSONDecodeError as exc:
                raise RuntimeError("Ollama returned invalid JSON for the weekly plan.") from exc
