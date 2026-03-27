"""Apply human `resume` payloads to `PipelineState` after `interrupt()`."""

from __future__ import annotations

from typing import Any

from msrclaw.pipeline.state import PipelineState, ResearchQuestion, SourceConfig


def apply_review_rqs_and_sources(pipeline: PipelineState, resume: Any) -> None:
    if not isinstance(resume, dict):
        return
    rqs_raw = resume.get("rqs")
    if isinstance(rqs_raw, list):
        new_rqs: list[ResearchQuestion] = []
        for i, item in enumerate(rqs_raw, start=1):
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
    cand_raw = resume.get("candidate_sources")
    if isinstance(cand_raw, list):
        cands: list[SourceConfig] = []
        for item in cand_raw:
            if isinstance(item, str):
                cands.append(SourceConfig(name=item.strip(), extra={}))
            elif isinstance(item, dict):
                name = str(item.get("name") or "").strip()
                if name:
                    cands.append(SourceConfig(name=name, extra=dict(item.get("extra") or {})))
        if cands:
            pipeline.candidate_sources = cands


def apply_select_sources(pipeline: PipelineState, resume: Any) -> None:
    if not isinstance(resume, dict):
        return
    names = resume.get("approved_source_names") or resume.get("sources")
    if not isinstance(names, list):
        return
    allowed = {str(n).strip() for n in names if str(n).strip()}
    if not allowed:
        return
    pipeline.approved_sources = [s for s in pipeline.approved_sources if s.name in allowed]
