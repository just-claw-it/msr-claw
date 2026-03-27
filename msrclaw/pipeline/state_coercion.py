"""Rehydrate `PipelineState` when LangGraph/SQLite checkpoints deserialize values as plain dicts."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from msrclaw.pipeline.state import (
    HumanDecision,
    PipelineState,
    ResearchQuestion,
    Result,
    SampleProfile,
    Script,
    SourceConfig,
    Threat,
)


def _maybe_int(value: Any) -> int | None:
    if value is None:
        return None
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value)
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _parse_dt(value: Any) -> datetime:
    if isinstance(value, datetime):
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value
    if isinstance(value, str):
        s = value.replace("Z", "+00:00")
        dt = datetime.fromisoformat(s)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    return datetime.now(timezone.utc)


def _rq(obj: Any) -> ResearchQuestion:
    if isinstance(obj, ResearchQuestion):
        return obj
    if isinstance(obj, dict):
        return ResearchQuestion(id=str(obj.get("id") or ""), text=str(obj.get("text") or ""))
    raise TypeError(f"Cannot coerce ResearchQuestion from {type(obj).__name__}")


def _source(obj: Any) -> SourceConfig:
    if isinstance(obj, SourceConfig):
        return obj
    if isinstance(obj, dict):
        return SourceConfig(name=str(obj.get("name") or ""), extra=dict(obj.get("extra") or {}))
    raise TypeError(f"Cannot coerce SourceConfig from {type(obj).__name__}")


def _script(obj: Any) -> Script:
    if isinstance(obj, Script):
        return obj
    if isinstance(obj, dict):
        return Script(
            name=str(obj.get("name") or ""),
            path=str(obj.get("path") or ""),
            language=str(obj.get("language") or "python"),
            content=obj.get("content"),
        )
    raise TypeError(f"Cannot coerce Script from {type(obj).__name__}")


def _result(obj: Any) -> Result:
    if isinstance(obj, Result):
        return obj
    if isinstance(obj, dict):
        return Result(
            rq_id=str(obj.get("rq_id") or ""),
            result_type=str(obj.get("result_type") or ""),
            path=obj.get("path"),
            summary=str(obj.get("summary") or ""),
        )
    raise TypeError(f"Cannot coerce Result from {type(obj).__name__}")


def _threat(obj: Any) -> Threat:
    if isinstance(obj, Threat):
        return obj
    if isinstance(obj, dict):
        mit = obj.get("mitigation")
        mit_s = str(mit).strip() if mit is not None else ""
        return Threat(
            category=str(obj.get("category") or ""),
            description=str(obj.get("description") or ""),
            mitigation=mit_s if mit_s else None,
        )
    raise TypeError(f"Cannot coerce Threat from {type(obj).__name__}")


def _decision(obj: Any) -> HumanDecision:
    if isinstance(obj, HumanDecision):
        return obj
    if isinstance(obj, dict):
        return HumanDecision(
            gate_id=str(obj.get("gate_id") or ""),
            timestamp=_parse_dt(obj.get("timestamp")),
            choice=str(obj.get("choice") or ""),
            rationale=str(obj.get("rationale") or ""),
        )
    raise TypeError(f"Cannot coerce HumanDecision from {type(obj).__name__}")


def _research_plan(obj: Any) -> dict[str, Any] | None:
    if obj is None:
        return None
    if isinstance(obj, dict):
        return dict(obj)
    return None


def _sample_profile(obj: Any) -> SampleProfile | None:
    if obj is None:
        return None
    if isinstance(obj, SampleProfile):
        return obj
    if isinstance(obj, dict):
        return SampleProfile(
            notes=str(obj.get("notes") or ""),
            metrics=dict(obj.get("metrics") or {}),
        )
    return None


def coerce_pipeline_state(raw: Any) -> PipelineState:
    """Return a real `PipelineState`, rebuilding from dict-shaped checkpoint data when needed."""
    if isinstance(raw, PipelineState):
        return raw
    if not isinstance(raw, dict):
        raise TypeError(f"Expected PipelineState or dict, got {type(raw).__name__}")

    d = raw
    rq_hist: list[list[ResearchQuestion]] = []
    for group in d.get("rq_history") or []:
        if isinstance(group, list):
            rq_hist.append([_rq(x) for x in group])

    return PipelineState(
        problem_prompt=str(d.get("problem_prompt") or ""),
        rqs=[_rq(x) for x in (d.get("rqs") or [])],
        rq_history=rq_hist,
        candidate_sources=[_source(x) for x in (d.get("candidate_sources") or [])],
        approved_sources=[_source(x) for x in (d.get("approved_sources") or [])],
        collection_scripts=[_script(x) for x in (d.get("collection_scripts") or [])],
        collected_data_paths=[str(x) for x in (d.get("collected_data_paths") or [])],
        collection_last_exit_code=_maybe_int(d.get("collection_last_exit_code")),
        collection_last_error=(
            str(d["collection_last_error"]) if d.get("collection_last_error") is not None else None
        ),
        collection_skipped=bool(d.get("collection_skipped", False)),
        source_availability=dict(d.get("source_availability") or {}),
        sample_profile=_sample_profile(d.get("sample_profile")),
        research_plan=_research_plan(d.get("research_plan")),
        analysis_scripts=[_script(x) for x in (d.get("analysis_scripts") or [])],
        results=[_result(x) for x in (d.get("results") or [])],
        paper_sections={str(k): str(v) for k, v in dict(d.get("paper_sections") or {}).items()},
        threats=[_threat(x) for x in (d.get("threats") or [])],
        run_id=str(d.get("run_id") or ""),
        workspace_dir=str(d.get("workspace_dir") or ""),
        decisions=[_decision(x) for x in (d.get("decisions") or [])],
    )
