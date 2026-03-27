"""OpenAI-compatible chat client (uses `openai` with configurable `base_url`).

Smaller / weaker models often emit brittle collection scripts and invalid JSON. Prefer GPT-4o-class
(or comparable) for reliable MSR pipeline outputs.
"""

from __future__ import annotations

import json
import os
from typing import Any

from openai import OpenAI


class LLMClient:
    """Thin wrapper around the OpenAI SDK for JSON-oriented agent steps."""

    def __init__(
        self,
        *,
        base_url: str | None = None,
        api_key: str | None = None,
        model: str | None = None,
        timeout: float = 120.0,
    ) -> None:
        base = base_url or os.environ.get("LLM_BASE_URL", "https://api.openai.com/v1")
        key = api_key if api_key is not None else os.environ.get("LLM_API_KEY", "")
        self._model = model or os.environ.get("LLM_MODEL", "gpt-4o")
        self._client = OpenAI(base_url=base, api_key=key or "missing", timeout=timeout)

    @property
    def model(self) -> str:
        return self._model

    def complete_json(self, *, system: str, user: str) -> dict[str, Any]:
        """Return a JSON object from the model (best-effort parse)."""
        resp = self._client.chat.completions.create(
            model=self._model,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            response_format={"type": "json_object"},
        )
        text = (resp.choices[0].message.content or "").strip()
        return json.loads(text)

    def complete_text(self, *, system: str, user: str) -> str:
        resp = self._client.chat.completions.create(
            model=self._model,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
        )
        return (resp.choices[0].message.content or "").strip()
