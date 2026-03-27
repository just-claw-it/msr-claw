"""ValidityAgent: list threats to internal/external/construct validity."""

from __future__ import annotations

import os
from pathlib import Path

from msrclaw.agents.llm_tailoring import research_plan_excerpt
from msrclaw.config import load_config
from msrclaw.llm import LLMClient
from msrclaw.pipeline.state import PipelineState, Threat


def run_validity_agent(pipeline: PipelineState) -> None:
    if os.environ.get("MSRCLAW_MOCK_LLM", "").lower() in ("1", "true", "yes"):
        pipeline.threats = [
            Threat(
                category="internal",
                description="Sampling and measurement limited to GitHub API search results.",
                mitigation="Disclose query window and rate-limit effects.",
            )
        ]
        _write_threats_md(pipeline)
        return

    cfg = load_config()
    client = LLMClient(
        base_url=cfg.llm_base_url,
        api_key=cfg.llm_api_key,
        model=cfg.llm_model,
    )
    system = (
        "List threats to internal, external, and construct validity for an MSR study. "
        "Ground threats in the stated problem, research plan, and actual results — not generic MSR boilerplate. "
        "Return JSON: {\"threats\":[{\"category\":\"internal|external|construct\","
        "\"description\":\"...\",\"mitigation\":\"...\"}]}"
    )
    user = "\n".join(
        [
            f"Problem:\n{pipeline.problem_prompt[:8000]}",
            "",
            f"RQs: {[r.text for r in pipeline.rqs]}",
            "",
            "Research plan:",
            research_plan_excerpt(pipeline, max_chars=4000),
            "",
            f"Results summaries: {[r.summary for r in pipeline.results]}",
        ]
    )
    data = client.complete_json(system=system, user=user)
    threats: list[Threat] = []
    for t in data.get("threats") or []:
        if not isinstance(t, dict):
            continue
        threats.append(
            Threat(
                category=str(t.get("category") or "internal"),
                description=str(t.get("description") or ""),
                mitigation=str(t.get("mitigation") or "") or None,
            )
        )
    pipeline.threats = threats
    _write_threats_md(pipeline)


def _write_threats_md(pipeline: PipelineState) -> None:
    lines: list[str] = ["# Threats to validity", ""]
    for t in pipeline.threats:
        lines.append(f"## {t.category}")
        lines.append("")
        lines.append(t.description)
        if t.mitigation:
            lines.append("")
            lines.append(f"Mitigation: {t.mitigation}")
        lines.append("")
    path = Path(pipeline.workspace_dir) / "threats.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines).strip() + "\n", encoding="utf-8")
