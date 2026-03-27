"""Shared helpers: enrich prompts with ``research_plan`` and optional tailoring flags."""

from __future__ import annotations

import json
import os

from msrclaw.config import load_config
from msrclaw.llm import LLMClient
from msrclaw.pipeline.state import PipelineState


def llm_scripts_enabled() -> bool:
    """Whether LLM should author collection / analysis / figure scripts (not mock; not opted out)."""
    if os.environ.get("MSRCLAW_MOCK_LLM", "").lower() in ("1", "true", "yes"):
        return False
    return os.environ.get("MSRCLAW_LLM_SCRIPTS", "1").strip().lower() not in (
        "0",
        "false",
        "no",
        "off",
    )


def research_plan_excerpt(pipeline: PipelineState, *, max_chars: int = 6000) -> str:
    """Serialize ``pipeline.research_plan`` for LLM user messages."""
    rp = pipeline.research_plan
    if not rp:
        return "(no structured research plan yet — rely on problem and RQs)"
    try:
        s = json.dumps(rp, indent=2, ensure_ascii=False)
    except (TypeError, ValueError):
        s = str(rp)
    return s[:max_chars]


def figure_result_paths(workspace: str) -> list[str]:
    """PNG/SVG paths under ``figures/`` for writer context."""
    from pathlib import Path

    root = Path(workspace) / "figures"
    if not root.is_dir():
        return []
    out: list[str] = []
    for p in sorted(root.iterdir()):
        if p.is_file() and p.suffix.lower() in (".png", ".svg", ".pdf"):
            out.append(str(p.resolve()))
    return out


def enrich_sample_profile_llm(pipeline: PipelineState) -> None:
    """Append an interpretation paragraph to sample notes (LLM), when script tailoring is enabled."""
    if not llm_scripts_enabled():
        return
    if os.environ.get("MSRCLAW_MOCK_LLM", "").lower() in ("1", "true", "yes"):
        return
    sp = pipeline.sample_profile
    if sp is None or not sp.notes.strip():
        return
    cfg = load_config()
    client = LLMClient(
        base_url=cfg.llm_base_url,
        api_key=cfg.llm_api_key,
        model=cfg.llm_model,
    )
    system = (
        "You interpret tabular sampling metrics for an MSR study. "
        'Return JSON: {"interpretation": "2-4 sentences, markdown allowed"} '
        "Tie insights to the research questions and research_plan; do not invent unseen columns."
    )
    user = "\n".join(
        [
            "## Problem",
            pipeline.problem_prompt[:6000],
            "",
            "## RQs",
            json.dumps([{"id": r.id, "text": r.text} for r in pipeline.rqs], ensure_ascii=False),
            "",
            "## Research plan",
            research_plan_excerpt(pipeline, max_chars=4000),
            "",
            "## Sample metrics (JSON)",
            json.dumps(sp.metrics, indent=2, ensure_ascii=False)[:12000],
            "",
            "## Existing notes",
            sp.notes[:4000],
        ]
    )
    try:
        data = client.complete_json(system=system, user=user)
    except Exception:
        return
    interp = str(data.get("interpretation") or "").strip()
    if not interp:
        return
    sp.notes = (sp.notes + "\n\n### Tailored interpretation (LLM)\n\n" + interp).strip()[:16000]
