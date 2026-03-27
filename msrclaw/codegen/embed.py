"""Safe embedding of research context into generated Python source."""

from __future__ import annotations

import json
from typing import Any

from msrclaw.pipeline.state import ResearchQuestion


def research_context_dict(
    *,
    run_id: str,
    problem_prompt: str,
    rqs: list[ResearchQuestion],
    raw_out_dir: str | None = None,
) -> dict[str, Any]:
    """Structured metadata injected into generated scripts (JSON-serializable)."""
    out: dict[str, Any] = {
        "run_id": run_id,
        "problem_prompt": problem_prompt[:8000],
        "research_questions": [{"id": r.id, "text": r.text} for r in rqs],
    }
    if raw_out_dir is not None:
        out["raw_out_dir"] = raw_out_dir
    return out


def python_json_literal(obj: Any) -> str:
    """Expression usable inside generated code: json.loads(<one safe string>)."""
    return "json.loads(" + json.dumps(json.dumps(obj, ensure_ascii=False)) + ")"


def search_keywords_from_rqs(rqs: list[ResearchQuestion], *, max_chars: int = 120) -> str:
    """Single search phrase for APIs (whitespace-normalized, length-capped)."""
    import re

    parts: list[str] = []
    for r in rqs:
        t = " ".join((r.text or "").split())
        if t:
            parts.append(t)
    if not parts:
        return "mining software repositories"
    merged = " ".join(parts)
    merged = re.sub(r"\s+", " ", merged).strip()
    return merged[:max_chars]
