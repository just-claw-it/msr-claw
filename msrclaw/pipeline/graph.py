"""LangGraph pipeline: eight agent nodes, five milestone gates, optional collection recovery."""

from __future__ import annotations

from dataclasses import asdict
from typing import Any, Literal, TypedDict

from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph
from langgraph.types import interrupt

from msrclaw.agents import analysis, collector, problem, refinement, sampler, source, validity, writer
from msrclaw.pipeline.gates import COLLECTION_RECOVERY_GATE_ID, GateId, GatePrompt, gate_ordinal
from msrclaw.pipeline.resume_apply import apply_review_rqs_and_sources, apply_select_sources
from msrclaw.pipeline.state import HumanDecision, PipelineState


class MSRClawState(TypedDict):
    """Graph state: single `pipeline` object updated by each node."""

    pipeline: PipelineState


def _gate_payload(gate: GateId, title: str, body: dict[str, Any]) -> dict[str, Any]:
    gp = GatePrompt(
        gate_id=gate.value,
        ordinal=gate_ordinal(gate.value) or 0,
        title=title,
        body=body,
    )
    return asdict(gp)


def _record_decision(pipeline: PipelineState, gate_id: str, resume: Any) -> None:
    if isinstance(resume, dict):
        choice = str(resume.get("choice", "approve"))
        rationale = str(resume.get("rationale", ""))
    else:
        choice = str(resume)
        rationale = ""
    pipeline.decisions.append(HumanDecision.record(gate_id, choice, rationale))


def problem_agent(state: MSRClawState) -> MSRClawState:
    problem.run_problem_agent(state["pipeline"])
    return state


def source_agent(state: MSRClawState) -> MSRClawState:
    source.run_source_agent(state["pipeline"])
    return state


def collector_agent(state: MSRClawState) -> MSRClawState:
    collector.run_collector_agent(state["pipeline"])
    return state


def sampler_agent(state: MSRClawState) -> MSRClawState:
    sampler.run_sampler_agent(state["pipeline"])
    return state


def refinement_agent(state: MSRClawState) -> MSRClawState:
    refinement.run_refinement_agent(state["pipeline"])
    return state


def analysis_agent(state: MSRClawState) -> MSRClawState:
    analysis.run_analysis_agent(state["pipeline"])
    return state


def validity_agent(state: MSRClawState) -> MSRClawState:
    validity.run_validity_agent(state["pipeline"])
    return state


def writer_agent(state: MSRClawState) -> MSRClawState:
    writer.run_writer_agent(state["pipeline"])
    return state


def gate_review_rqs_and_sources(state: MSRClawState) -> MSRClawState:
    payload = _gate_payload(
        GateId.REVIEW_RQS_AND_SOURCES,
        "Review research questions and candidate sources",
        {
            "rqs": [asdict(rq) for rq in state["pipeline"].rqs],
            "candidate_sources": [asdict(s) for s in state["pipeline"].candidate_sources],
            "stage": "problem",
        },
    )
    resume = interrupt(payload)
    apply_review_rqs_and_sources(state["pipeline"], resume)
    _record_decision(state["pipeline"], GateId.REVIEW_RQS_AND_SOURCES.value, resume)
    return state


def gate_select_sources(state: MSRClawState) -> MSRClawState:
    payload = _gate_payload(
        GateId.SELECT_SOURCES,
        "Select sources and confirm credentials",
        {
            "approved": [s.name for s in state["pipeline"].approved_sources],
            "candidates": [s.name for s in state["pipeline"].candidate_sources],
            "availability": dict(state["pipeline"].source_availability),
        },
    )
    resume = interrupt(payload)
    apply_select_sources(state["pipeline"], resume)
    _record_decision(state["pipeline"], GateId.SELECT_SOURCES.value, resume)
    return state


def gate_review_sample(state: MSRClawState) -> MSRClawState:
    sp = state["pipeline"].sample_profile
    body: dict[str, Any] = {"sample_profile": None}
    if sp is not None:
        body["sample_profile"] = {"notes": sp.notes, "metrics": sp.metrics}
    payload = _gate_payload(GateId.REVIEW_SAMPLE, "Review sample profile", body)
    resume = interrupt(payload)
    _record_decision(state["pipeline"], GateId.REVIEW_SAMPLE.value, resume)
    return state


def gate_refine_rqs(state: MSRClawState) -> MSRClawState:
    payload = _gate_payload(
        GateId.REFINE_RQS,
        "Approve or refine research questions",
        {"rqs": [asdict(rq) for rq in state["pipeline"].rqs]},
    )
    resume = interrupt(payload)
    _record_decision(state["pipeline"], GateId.REFINE_RQS.value, resume)
    return state


def gate_review_validity(state: MSRClawState) -> MSRClawState:
    payload = _gate_payload(
        GateId.REVIEW_VALIDITY,
        "Review threats to validity",
        {"threats": [t.description for t in state["pipeline"].threats]},
    )
    resume = interrupt(payload)
    _record_decision(state["pipeline"], GateId.REVIEW_VALIDITY.value, resume)
    return state


def gate_collection_recovery(state: MSRClawState) -> MSRClawState:
    p = state["pipeline"]
    payload = {
        "gate_id": COLLECTION_RECOVERY_GATE_ID,
        "ordinal": 0,
        "title": "Collection failed — choose next step",
        "body": {
            "exit_code": p.collection_last_exit_code,
            "error": p.collection_last_error,
        },
    }
    resume = interrupt(payload)
    ch = ""
    if isinstance(resume, dict):
        ch = str(resume.get("choice", "")).lower().strip()
        if ch in ("skip", "s"):
            p.collection_skipped = True
            p.collection_last_exit_code = 0
            p.collection_last_error = None
        elif ch in ("retry", "r"):
            p.collection_skipped = False
    _record_decision(p, COLLECTION_RECOVERY_GATE_ID, resume)
    return state


def route_after_refinement_gate(
    state: MSRClawState,
) -> Literal["analysis_agent", "refinement_agent", END]:
    last = state["pipeline"].decisions[-1]
    c = last.choice.lower().strip()
    if c in ("abort", "x"):
        return END
    if c in ("approve", "approve_all", "a"):
        return "analysis_agent"
    return "refinement_agent"


def route_after_collector(
    state: MSRClawState,
) -> Literal["sampler_agent", "gate_collection_recovery"]:
    if state["pipeline"].collection_last_exit_code == 0:
        return "sampler_agent"
    return "gate_collection_recovery"


def route_after_collection_recovery(
    state: MSRClawState,
) -> Literal["collector_agent", "sampler_agent", END]:
    last = state["pipeline"].decisions[-1]
    c = last.choice.lower().strip()
    if c in ("abort", "x"):
        return END
    if c in ("retry", "r"):
        return "collector_agent"
    return "sampler_agent"


def build_graph(*, checkpointer: BaseCheckpointSaver | None = None):
    """Compile the pipeline graph. Pass a persistent checkpointer for resume across processes."""
    cg = checkpointer if checkpointer is not None else MemorySaver()
    g = StateGraph(MSRClawState)

    g.add_node("problem_agent", problem_agent)
    g.add_node("gate_review_rqs_and_sources", gate_review_rqs_and_sources)
    g.add_node("source_agent", source_agent)
    g.add_node("gate_select_sources", gate_select_sources)
    g.add_node("collector_agent", collector_agent)
    g.add_node("gate_collection_recovery", gate_collection_recovery)
    g.add_node("sampler_agent", sampler_agent)
    g.add_node("gate_review_sample", gate_review_sample)
    g.add_node("refinement_agent", refinement_agent)
    g.add_node("gate_refine_rqs", gate_refine_rqs)
    g.add_node("analysis_agent", analysis_agent)
    g.add_node("validity_agent", validity_agent)
    g.add_node("gate_review_validity", gate_review_validity)
    g.add_node("writer_agent", writer_agent)

    g.add_edge(START, "problem_agent")
    g.add_edge("problem_agent", "gate_review_rqs_and_sources")
    g.add_edge("gate_review_rqs_and_sources", "source_agent")
    g.add_edge("source_agent", "gate_select_sources")
    g.add_edge("gate_select_sources", "collector_agent")
    g.add_conditional_edges(
        "collector_agent",
        route_after_collector,
        {
            "sampler_agent": "sampler_agent",
            "gate_collection_recovery": "gate_collection_recovery",
        },
    )
    g.add_conditional_edges(
        "gate_collection_recovery",
        route_after_collection_recovery,
        {
            "collector_agent": "collector_agent",
            "sampler_agent": "sampler_agent",
            END: END,
        },
    )
    g.add_edge("sampler_agent", "gate_review_sample")
    g.add_edge("gate_review_sample", "refinement_agent")
    g.add_edge("refinement_agent", "gate_refine_rqs")

    g.add_conditional_edges(
        "gate_refine_rqs",
        route_after_refinement_gate,
        {
            "analysis_agent": "analysis_agent",
            "refinement_agent": "refinement_agent",
            END: END,
        },
    )

    g.add_edge("analysis_agent", "validity_agent")
    g.add_edge("validity_agent", "gate_review_validity")
    g.add_edge("gate_review_validity", "writer_agent")
    g.add_edge("writer_agent", END)

    return g.compile(checkpointer=cg)
