"""RefinementAgent: propose RQ refinements grounded in sample profile (LLM)."""

from __future__ import annotations

import os

from msrclaw.agents.llm_tailoring import research_plan_excerpt
from msrclaw.config import load_config
from msrclaw.llm import LLMClient
from msrclaw.pipeline.state import PipelineState, ResearchQuestion


def run_refinement_agent(pipeline: PipelineState) -> None:
    if os.environ.get("MSRCLAW_MOCK_LLM", "").lower() in ("1", "true", "yes"):
        return

    cfg = load_config()
    client = LLMClient(
        base_url=cfg.llm_base_url,
        api_key=cfg.llm_api_key,
        model=cfg.llm_model,
    )
    sp = pipeline.sample_profile
    sp_blob = sp.metrics if sp else {}
    system = (
        "You refine MSR research questions using empirical sample evidence and the study's research plan. "
        "Return JSON: {\"rqs\":[{\"id\":\"rq1\",\"text\":\"...\"}],\"change_summary\":\"...\"}. "
        "Keep 2–4 RQs; ids should stay stable when meaning is preserved."
    )
    user = (
        f"Research plan:\n{research_plan_excerpt(pipeline, max_chars=4000)}\n\n"
        f"Current RQs:\n{[{'id': r.id, 'text': r.text} for r in pipeline.rqs]}\n\n"
        f"Sample profile metrics:\n{sp_blob}\n"
    )
    data = client.complete_json(system=system, user=user)
    new_rqs: list[ResearchQuestion] = []
    for i, item in enumerate(data.get("rqs") or [], start=1):
        if isinstance(item, dict):
            rid = str(item.get("id") or f"rq{i}")
            text = str(item.get("text") or "").strip()
        else:
            rid = f"rq{i}"
            text = str(item).strip()
        if text:
            new_rqs.append(ResearchQuestion(id=rid, text=text))
    if new_rqs:
        pipeline.rq_history.append(list(pipeline.rqs))
        pipeline.rqs = new_rqs
