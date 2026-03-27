"""WriterAgent: incremental paper drafts grounded in pipeline state."""

from __future__ import annotations

import os
from pathlib import Path

from msrclaw.agents.llm_tailoring import figure_result_paths, research_plan_excerpt
from msrclaw.config import load_config
from msrclaw.llm import LLMClient
from msrclaw.pipeline.state import PipelineState


_SECTION_ORDER = [
    ("methodology", "Methodology"),
    ("results", "Results"),
    ("discussion", "Discussion"),
    ("introduction", "Introduction"),
    ("abstract", "Abstract"),
    ("conclusion", "Conclusion"),
]


def run_writer_agent(pipeline: PipelineState) -> None:
    if os.environ.get("MSRCLAW_MOCK_LLM", "").lower() in ("1", "true", "yes"):
        pipeline.paper_sections = {
            "methodology": "Stub methodology (MSRCLAW_MOCK_LLM).",
            "results": "Stub results.",
            "discussion": "Stub discussion.",
            "introduction": "Stub introduction.",
            "abstract": "Stub abstract.",
            "conclusion": "Stub conclusion.",
        }
        ws = Path(pipeline.workspace_dir)
        paper_dir = ws / "paper"
        paper_dir.mkdir(parents=True, exist_ok=True)
        for key, text in pipeline.paper_sections.items():
            (paper_dir / f"{key}.md").write_text(text + "\n", encoding="utf-8")
        return

    cfg = load_config()
    client = LLMClient(
        base_url=cfg.llm_base_url,
        api_key=cfg.llm_api_key,
        model=cfg.llm_model,
    )
    fig_paths = figure_result_paths(pipeline.workspace_dir)
    base_context = (
        f"Problem: {pipeline.problem_prompt}\n"
        f"RQs: {[r.text for r in pipeline.rqs]}\n"
        f"Research plan:\n{research_plan_excerpt(pipeline, max_chars=8000)}\n"
        f"Threats: {[t.description for t in pipeline.threats]}\n"
        f"Results: {[r.summary for r in pipeline.results]}\n"
        f"Figure file paths (reference in Results/Discussion): {fig_paths}\n"
    )
    ws = Path(pipeline.workspace_dir)
    paper_dir = ws / "paper"
    paper_dir.mkdir(parents=True, exist_ok=True)
    for key, title in _SECTION_ORDER:
        system = (
            f"Write the '{title}' section for an MSR paper tailored to this study's problem and plan. "
            "Use only the provided context; do not invent datasets or statistical results not present. "
            "If figure paths are listed, cite them where appropriate. Markdown."
        )
        text = client.complete_text(system=system, user=base_context)
        pipeline.paper_sections[key] = text
        (paper_dir / f"{key}.md").write_text(text, encoding="utf-8")
