from __future__ import annotations

import json
from typing import Any

import httpx

from app.core.config import settings
from app.schemas.meeting import EvidenceExtraction, MinutesDocument
from app.services.transcription import format_timestamp


class OllamaUnavailable(RuntimeError):
    pass


class OllamaValidationError(RuntimeError):
    pass


class OllamaClient:
    def __init__(self, base_url: str | None = None, timeout: float = 120.0):
        self.base_url = (base_url or settings.ollama_url).rstrip("/")
        self.timeout = timeout

    def list_models(self) -> list[str]:
        try:
            response = httpx.get(f"{self.base_url}/api/tags", timeout=5)
            response.raise_for_status()
            return [item.get("name", "") for item in response.json().get("models", [])]
        except (httpx.HTTPError, OSError, ValueError) as exc:
            raise OllamaUnavailable(f"Ollama is unavailable at {self.base_url}: {exc}") from exc

    def ensure_model(self, model: str) -> None:
        models = self.list_models()
        if model not in models and not any(name.split(":", 1)[0] == model for name in models):
            raise OllamaUnavailable(f"Ollama model '{model}' is not installed. Run: ollama pull {model}")

    def structured_chat(self, model: str, prompt: str, schema: dict[str, Any]) -> Any:
        self.ensure_model(model)
        payload = {
            "model": model,
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "You are a careful meeting-minutes assistant. Use only the supplied transcript. "
                        "Never infer speakers, owners, attendees, decisions, or deadlines. Return JSON only."
                    ),
                },
                {"role": "user", "content": prompt},
            ],
            "format": schema,
            "stream": False,
            "options": {"temperature": 0},
        }
        try:
            response = httpx.post(f"{self.base_url}/api/chat", json=payload, timeout=self.timeout)
            response.raise_for_status()
            content = response.json().get("message", {}).get("content", "")
            return json.loads(_strip_json_fence(content))
        except (httpx.HTTPError, ValueError, json.JSONDecodeError) as exc:
            raise OllamaValidationError(f"Ollama returned invalid structured output: {exc}") from exc


def _strip_json_fence(content: str) -> str:
    text = content.strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[1] if "\n" in text else text[3:]
        if text.endswith("```"):
            text = text[:-3]
    return text.strip()


def evidence_prompt(segments: list[dict]) -> str:
    transcript = "\n".join(
        f"[{format_timestamp(s['start_time'])} - {format_timestamp(s['end_time'])}] {s['text']}" for s in segments
    )
    return (
        "Extract evidence from this transcript chunk. Every item needs exact evidence timestamps and a short "
        "verbatim source_excerpt. Set action owner/deadline to null unless explicitly stated.\n\n"
        f"TRANSCRIPT CHUNK:\n{transcript}"
    )


def minutes_prompt(title: str, meeting_date: str | None, purpose: str | None, evidence: list[dict]) -> str:
    return (
        "Create final meeting minutes from the evidence JSON below. Preserve timestamps on every discussion point, "
        "decision, action, risk, question, and next step. Do not invent information.\n\n"
        f"Title: {title}\nDate: {meeting_date or 'Not supplied'}\nPurpose: {purpose or 'Not supplied'}\n\n"
        f"EVIDENCE JSON:\n{json.dumps(evidence, ensure_ascii=False)}"
    )


def validate_with_retry(client: OllamaClient, model: str, prompt: str, model_type: type, schema: dict) -> tuple[Any, list[str]]:
    warnings: list[str] = []
    try:
        raw = client.structured_chat(model, prompt, schema)
        return model_type.model_validate(raw), warnings
    except Exception as first_error:
        warnings.append(f"Structured output validation failed; retrying once: {first_error}")
        try:
            retry_prompt = f"{prompt}\n\nPrevious validation error: {first_error}\nReturn corrected JSON only."
            raw = client.structured_chat(model, retry_prompt, schema)
            return model_type.model_validate(raw), warnings
        except Exception as second_error:
            warnings.append(f"Structured output remained invalid; raw result was not accepted: {second_error}")
            raise OllamaValidationError(str(second_error)) from second_error


def evidence_schema() -> dict:
    return EvidenceExtraction.model_json_schema()


def minutes_schema() -> dict:
    return MinutesDocument.model_json_schema()
