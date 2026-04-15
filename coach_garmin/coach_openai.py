from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from coach_garmin.text_encoding import repair_text_tree

from coach_garmin.config import DEFAULT_OPENAI_BASE_URL, DEFAULT_OPENAI_MODEL


class OpenAIConnectionError(RuntimeError):
    pass


class OpenAIModelError(RuntimeError):
    pass


@dataclass(slots=True)
class OpenAICoachClient:
    api_key: str | None
    base_url: str = DEFAULT_OPENAI_BASE_URL
    model: str = DEFAULT_OPENAI_MODEL
    timeout_seconds: int = 120

    def ensure_ready(self) -> None:
        if not self.api_key:
            raise OpenAIConnectionError(
                "OPENAI_API_KEY is missing. Put it in the environment or in .env.local, then retry."
            )

    def generate_weekly_plan(self, prompt_bundle: dict[str, Any]) -> dict[str, Any]:
        self.ensure_ready()
        prompt = self._build_prompt(prompt_bundle)
        text = self._chat(prompt)
        parsed = self._parse_json_response(text)
        if "weekly_plan" not in parsed or not isinstance(parsed["weekly_plan"], list):
            raise RuntimeError("OpenAI returned a response without a valid weekly plan payload.")
        return parsed

    def _chat(self, prompt: str) -> str:
        payload = self._request_json(
            "/chat/completions",
            {
                "model": self.model,
                "messages": [
                    {
                        "role": "system",
                        "content": (
                            "You are a cautious but direct French running coach. "
                            "Use only the provided local context. "
                            "Start with an analytical assessment before the weekly plan. "
                            "Use pace guidance when the context contains sufficient benchmark evidence. "
                            "Respect the signal coverage report and do not claim unavailable metrics or features. "
                            "If the data is weak, say so explicitly and fall back to effort guidance. "
                            "Do not give medical advice. "
                            "Respond with valid JSON only."
                        ),
                    },
                    {"role": "user", "content": prompt},
                ],
                "temperature": 0.2,
                "response_format": {"type": "json_object"},
            },
        )
        choices = payload.get("choices", [])
        if not isinstance(choices, list) or not choices:
            raise RuntimeError("OpenAI returned an unexpected chat payload.")
        message = choices[0].get("message") if isinstance(choices[0], dict) else None
        content = message.get("content") if isinstance(message, dict) else None
        if not isinstance(content, str):
            raise RuntimeError("OpenAI returned a response without text content.")
        return content

    def _request_json(self, path: str, payload: dict[str, Any] | None = None, method: str = "POST") -> dict[str, Any]:
        url = f"{self.base_url}{path}"
        data = None if method == "GET" else json.dumps(payload or {}).encode("utf-8")
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        request = Request(url, data=data, headers=headers, method=method)
        try:
            with urlopen(request, timeout=self.timeout_seconds) as response:
                return repair_text_tree(json.loads(response.read().decode("utf-8")))
        except HTTPError as exc:
            if exc.code in {401, 403}:
                raise OpenAIConnectionError("OPENAI_API_KEY was rejected. Check the key and retry.") from exc
            if exc.code == 404:
                raise OpenAIModelError(f"OpenAI model '{self.model}' was not found. Check the model name.") from exc
            raise OpenAIConnectionError(f"OpenAI request failed with HTTP {exc.code}.") from exc
        except URLError as exc:
            raise OpenAIConnectionError(
                "OpenAI is unreachable. Check the network and the OpenAI endpoint URL."
            ) from exc

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
                raise RuntimeError("OpenAI returned non-JSON output for the weekly plan.")
            try:
                return repair_text_tree(json.loads(text[start : end + 1]))
            except json.JSONDecodeError as exc:
                raise RuntimeError("OpenAI returned invalid JSON for the weekly plan.") from exc
