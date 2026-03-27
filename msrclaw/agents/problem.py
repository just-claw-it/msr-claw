"""ProblemAgent: decompose problem into RQs and candidate sources."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from msrclaw.config import load_config
from msrclaw.llm import LLMClient
from msrclaw.pipeline.state import PipelineState, ResearchQuestion, SourceConfig
from msrclaw.sources.registry import registered_names


def _mock_pipeline(p: PipelineState) -> None:
    """Deterministic placeholders when MSRCLAW_MOCK_LLM is set — not model inference."""
    raw = p.problem_prompt.strip()
    one_line = " ".join(raw.split())[:220] if raw else ""
    if not one_line:
        one_line = "(empty problem)"
    tag = "[Mock LLM — no API call] "
    p.rqs = [
        ResearchQuestion(
            id="rq1",
            text=f"{tag}What evidence exists for: {one_line}",
        ),
        ResearchQuestion(
            id="rq2",
            text=f"{tag}What metrics, comparisons, and validity threats matter for this study?",
        ),
    ]
    p.candidate_sources = [SourceConfig(name="github", extra={})]
    if not p.rq_history:
        p.rq_history.append(list(p.rqs))
    p.research_plan = {
        "summary": "[Mock] Plan aligned to the stated problem (MSRCLAW_MOCK_LLM).",
        "collection_strategy": "Use approved sources; collection scripts are stubs or templates.",
        "analysis_strategy": "Descriptive summaries from collected artifacts.",
        "figure_plan": [{"title": "(mock)", "rationale": "Placeholder"}],
        "validity_focus": "Sampling and construct limits of the data source.",
        "paper_emphasis": "Report methodology and threats clearly.",
    }


def _parse_llm(data: dict[str, Any]) -> tuple[list[ResearchQuestion], list[SourceConfig], dict[str, Any] | None]:
    rqs_out: list[ResearchQuestion] = []
    for i, item in enumerate(data.get("rqs") or [], start=1):
        if isinstance(item, dict):
            rid = str(item.get("id") or f"rq{i}")
            text = str(item.get("text") or "").strip()
        else:
            rid = f"rq{i}"
            text = str(item).strip()
        if text:
            rqs_out.append(ResearchQuestion(id=rid, text=text))
    candidates: list[SourceConfig] = []
    for item in data.get("candidate_sources") or []:
        if isinstance(item, str):
            name = item.strip()
            extra: dict[str, Any] = {}
        else:
            name = str((item or {}).get("name") or "").strip()
            extra = dict((item or {}).get("extra") or {})
        if name:
            candidates.append(SourceConfig(name=name, extra=extra))
    plan_raw = data.get("research_plan")
    plan: dict[str, Any] | None = None
    if isinstance(plan_raw, dict) and plan_raw:
        plan = dict(plan_raw)
    return rqs_out, candidates, plan


def run_problem_agent(pipeline: PipelineState) -> None:
    if os.environ.get("MSRCLAW_MOCK_LLM", "").lower() in ("1", "true", "yes"):
        _mock_pipeline(pipeline)
        return

    cfg = load_config()
    allowed = set(registered_names())
    client = LLMClient(
        base_url=cfg.llm_base_url,
        api_key=cfg.llm_api_key,
        model=cfg.llm_model,
    )
    system = (
        "You are an MSR research assistant. Decompose the problem into 2–4 research questions (RQs). "
        "Pick candidate data sources ONLY from this allow-list: "
        f"{sorted(allowed)}. "
        "Respond with a single JSON object with keys: "
        'rqs, candidate_sources, notes (string), research_plan (object). '
        "research_plan must include: summary (string), collection_strategy (string), "
        "analysis_strategy (string), figure_plan (array of {title, rationale}), "
        "validity_focus (string), paper_emphasis (string). "
        "Tailor every field to the specific problem — not generic MSR boilerplate."
    )
    user = f"Research problem:\n{pipeline.problem_prompt.strip()}"
    data = client.complete_json(system=system, user=user)
    rqs, candidates, plan = _parse_llm(data)
    if not rqs:
        raise ValueError("LLM returned no RQs; try a stronger model or MSRCLAW_MOCK_LLM=1 for tests.")
    pipeline.rqs = rqs
    pipeline.candidate_sources = [c for c in candidates if c.name in allowed]
    if not pipeline.candidate_sources:
        pipeline.candidate_sources = [SourceConfig(name="github", extra={})]
    pipeline.research_plan = plan
    if not pipeline.rq_history:
        pipeline.rq_history.append(list(pipeline.rqs))
    if pipeline.workspace_dir and pipeline.research_plan:
        p = Path(pipeline.workspace_dir)
        p.mkdir(parents=True, exist_ok=True)
        (p / "research_plan.json").write_text(
            json.dumps(pipeline.research_plan, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
