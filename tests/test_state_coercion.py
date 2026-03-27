"""Tests for checkpoint dict → PipelineState coercion."""

from __future__ import annotations

from dataclasses import asdict
from datetime import datetime, timezone

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
from msrclaw.pipeline.state_coercion import coerce_pipeline_state


def test_coerce_round_trip_via_asdict() -> None:
    p = PipelineState(
        problem_prompt="x",
        rqs=[ResearchQuestion(id="rq1", text="Q1")],
        rq_history=[[ResearchQuestion(id="rq0", text="old")]],
        candidate_sources=[SourceConfig(name="github", extra={"api_key": "${GITHUB_TOKEN}"})],
        approved_sources=[SourceConfig(name="github", extra={})],
        collection_scripts=[Script(name="c.py", path="/tmp/c.py", language="python")],
        collected_data_paths=["/d/a.jsonl"],
        collection_last_exit_code=0,
        collection_last_error=None,
        collection_skipped=False,
        source_availability={"github": {"valid": True}},
        sample_profile=SampleProfile(notes="n", metrics={"rows": 1}),
        analysis_scripts=[Script(name="a.py", path="/a.py")],
        results=[Result(rq_id="rq1", result_type="stat", path=None, summary="s")],
        paper_sections={"abstract": "A"},
        threats=[Threat(category="internal", description="d", mitigation=None)],
        run_id="r1",
        workspace_dir="/w",
        decisions=[
            HumanDecision(
                gate_id="g1",
                timestamp=datetime(2025, 1, 1, tzinfo=timezone.utc),
                choice="approve",
                rationale="ok",
            )
        ],
    )
    raw = asdict(p)
    out = coerce_pipeline_state(raw)
    assert isinstance(out, PipelineState)
    assert out.problem_prompt == "x"
    assert out.rqs[0].id == "rq1"
    assert out.rq_history[0][0].text == "old"
    assert out.candidate_sources[0].name == "github"
    assert out.collection_last_exit_code == 0
    assert out.decisions[0].gate_id == "g1"
    assert out.decisions[0].timestamp.tzinfo is not None
    assert out.sample_profile is not None and out.sample_profile.metrics["rows"] == 1


def test_coerce_iso_timestamp_string() -> None:
    raw = {
        "problem_prompt": "p",
        "rqs": [],
        "rq_history": [],
        "candidate_sources": [],
        "approved_sources": [],
        "collection_scripts": [],
        "collected_data_paths": [],
        "collection_last_exit_code": None,
        "collection_last_error": None,
        "collection_skipped": False,
        "source_availability": {},
        "sample_profile": None,
        "analysis_scripts": [],
        "results": [],
        "paper_sections": {},
        "threats": [],
        "run_id": "r",
        "workspace_dir": "/w",
        "decisions": [
            {
                "gate_id": "g",
                "timestamp": "2025-03-24T12:00:00+00:00",
                "choice": "a",
                "rationale": "",
            }
        ],
    }
    out = coerce_pipeline_state(raw)
    assert out.decisions[0].timestamp.year == 2025


def test_coerce_identity() -> None:
    p = PipelineState(problem_prompt="p")
    assert coerce_pipeline_state(p) is p
