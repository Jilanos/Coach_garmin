from __future__ import annotations

import json
import time
from dataclasses import dataclass
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from coach_garmin.text_encoding import repair_text_tree

from coach_garmin.config import DEFAULT_GEMINI_BASE_URL, DEFAULT_GEMINI_MODEL


class GeminiConnectionError(RuntimeError):
    pass


class GeminiModelError(RuntimeError):
    pass


@dataclass(slots=True)
class GeminiCoachClient:
    api_key: str | None
    base_url: str = DEFAULT_GEMINI_BASE_URL
    model: str = DEFAULT_GEMINI_MODEL
    timeout_seconds: int = 120

    def ensure_ready(self) -> None:
        if not self.api_key:
            raise GeminiConnectionError(
                "GEMINI_API_KEY is missing. Put it in the environment or in .env.local, then retry."
            )
        self._request_json(f"/models/{self.model}", method="GET")

    def generate_weekly_plan(self, prompt_bundle: dict[str, Any]) -> dict[str, Any]:
        self.ensure_ready()
        prompt = self._build_prompt(prompt_bundle)
        text = self._chat(prompt)
        parsed = self._parse_json_response(text)
        if "weekly_plan" not in parsed or not isinstance(parsed["weekly_plan"], list):
            raise RuntimeError("Gemini returned a response without a valid weekly plan payload.")
        return parsed

    def _chat(self, prompt: str) -> str:
        response_schema = {
            "type": "object",
            "properties": {
                "coach_summary": {"type": "string"},
                "signals_used": {"type": "array", "items": {"type": "string"}},
                "weekly_plan": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "day": {"type": "string"},
                            "session_title": {"type": "string"},
                            "objective": {"type": "string"},
                            "duration_minutes": {"type": "number"},
                            "intensity": {"type": "string"},
                            "notes": {"type": "string"},
                        },
                        "required": ["day", "session_title", "objective", "duration_minutes", "intensity", "notes"],
                    },
                },
            },
            "required": ["coach_summary", "signals_used", "weekly_plan"],
        }
        payload = self._request_json(
            f"/models/{self.model}:generateContent",
            {
                "contents": [
                    {
                        "role": "user",
                        "parts": [{"text": prompt}],
                    }
                ],
                "generationConfig": {
                    "temperature": 0.2,
                    "maxOutputTokens": 4096,
                    "responseMimeType": "application/json",
                    "responseSchema": response_schema,
                },
            },
        )
        candidates = payload.get("candidates", [])
        if not isinstance(candidates, list) or not candidates:
            raise RuntimeError("Gemini returned an unexpected generateContent payload.")
        content = candidates[0].get("content") if isinstance(candidates[0], dict) else None
        parts = content.get("parts", []) if isinstance(content, dict) else []
        texts = [str(part.get("text", "")) for part in parts if isinstance(part, dict) and part.get("text")]
        if not texts:
            raise RuntimeError("Gemini returned a response without text parts.")
        return "".join(texts)

    def _request_json(self, path: str, payload: dict[str, Any] | None = None, method: str = "POST") -> dict[str, Any]:
        url = f"{self.base_url}{path}"
        if self.api_key:
            separator = "&" if "?" in url else "?"
            url = f"{url}{separator}key={self.api_key}"
        data = None if method == "GET" else json.dumps(payload or {}).encode("utf-8")
        request = Request(
            url,
            data=data,
            headers={"Content-Type": "application/json"},
            method=method,
        )
        retries = 3
        last_error: Exception | None = None
        for attempt in range(retries):
            try:
                with urlopen(request, timeout=self.timeout_seconds) as response:
                    return repair_text_tree(json.loads(response.read().decode("utf-8")))
            except HTTPError as exc:
                last_error = exc
                if exc.code in {401, 403}:
                    raise GeminiConnectionError(
                        "Gemini API key was rejected. Check GEMINI_API_KEY and retry."
                    ) from exc
                if exc.code == 404:
                    raise GeminiModelError(f"Gemini model '{self.model}' was not found. Check the model tag.") from exc
                if exc.code in {429, 503} and attempt + 1 < retries:
                    time.sleep(2 * (attempt + 1))
                    continue
                raise GeminiConnectionError(f"Gemini request failed with HTTP {exc.code}.") from exc
            except URLError as exc:
                last_error = exc
                if attempt + 1 < retries:
                    time.sleep(2 * (attempt + 1))
                    continue
                raise GeminiConnectionError(
                    "Gemini is unreachable. Check the network and the Gemini endpoint URL."
                ) from exc
        if last_error is not None:
            raise GeminiConnectionError("Gemini request failed after retries.") from last_error
        raise GeminiConnectionError("Gemini request failed unexpectedly.")

    @staticmethod
    def _build_prompt(prompt_bundle: dict[str, Any]) -> str:
        schema = {
            "coach_summary": "direct analytical summary in French grounded in the provided history and goal",
            "signals_used": ["list of local signals mentioned in the recommendation"],
            "weekly_plan": [
                {
                    "day": "Lundi",
                    "session_title": "Seuil 3 x 8 min autour de 4:12-4:20/km",
                    "objective": "why this session exists with direct coaching logic",
                    "duration_minutes": 45,
                    "intensity": "Z3-Z4 or pace range",
                    "notes": "execution details with reps, blocks, pace, or fallback effort guidance",
                }
            ],
        }
        return (
            "Build a one-week running plan in French from the provided local context.\n"
            "The answer must feel individualized, analytical, and specific.\n"
            "Do not produce a generic motivational summary.\n"
            "You must explain the current training phase, benchmark evidence, and tradeoff between goal ambition and recent history.\n"
            "You must respect the coverage report and avoid overclaiming missing signals.\n"
            "If multiple goals exist, follow the principal objective in the context.\n"
            "When pace inference is available, use it directly in sessions.\n"
            "When pace inference is weak, explicitly say that and use RPE guidance.\n"
            "Return valid JSON only.\n"
            f"Required schema: {json.dumps(schema, ensure_ascii=True)}\n"
            f"Context: {json.dumps(prompt_bundle, ensure_ascii=True)}"
        )

    @staticmethod
    def _parse_json_response(content: str) -> dict[str, Any]:
        text = content.strip()
        if text.startswith("```"):
            lines = text.splitlines()
            if lines and lines[0].startswith("```"):
                lines = lines[1:]
            if lines and lines[-1].startswith("```"):
                lines = lines[:-1]
            text = "\n".join(lines).strip()
        try:
            return repair_text_tree(json.loads(text))
        except json.JSONDecodeError:
            start = text.find("{")
            end = text.rfind("}")
            if start == -1 or end == -1 or end <= start:
                raise RuntimeError("Gemini returned non-JSON output for the weekly plan.")
            try:
                return repair_text_tree(json.loads(text[start : end + 1]))
            except json.JSONDecodeError as exc:
                raise RuntimeError("Gemini returned invalid JSON for the weekly plan.") from exc
