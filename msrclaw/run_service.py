"""Checkpoint-backed pipeline runs for CLI-aligned automation (e.g. MCP)."""

from __future__ import annotations

import json
import sqlite3
import threading
import uuid
from pathlib import Path
from typing import Any

from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.types import Command

from msrclaw.config import load_config
from msrclaw.mock_llm import mock_llm_context
from msrclaw.pipeline.graph import build_graph
from msrclaw.pipeline.state import PipelineState
from msrclaw.pipeline.state_coercion import coerce_pipeline_state
from msrclaw.storage.provenance import ProvenanceStore
from msrclaw.storage.workspace import checkpoints_db_path, ensure_run_workspace, run_workspace_root

_locks: dict[str, threading.Lock] = {}
_global = threading.Lock()


def _run_lock(run_id: str) -> threading.Lock:
    with _global:
        if run_id not in _locks:
            _locks[run_id] = threading.Lock()
        return _locks[run_id]


def _prov(cfg_workspace: Path) -> ProvenanceStore:
    return ProvenanceStore(cfg_workspace.expanduser().resolve() / "provenance.db")


def _checkpointer(run_root: Path) -> SqliteSaver:
    db = checkpoints_db_path(run_root)
    db.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db), check_same_thread=False)
    return SqliteSaver(conn)


def _sync_decisions(prov: ProvenanceStore, run_id: str, pipeline: PipelineState | dict[str, Any], seen: int) -> int:
    p = coerce_pipeline_state(pipeline)
    while seen < len(p.decisions):
        prov.log_decision(run_id, p.decisions[seen])
        seen += 1
    return seen


def _interrupt_from_out(out: dict[str, Any]) -> dict[str, Any] | None:
    xs = out.get("__interrupt__") or []
    if not xs:
        return None
    val = xs[0].value
    return val if isinstance(val, dict) else None


def _thread_cfg(run_id: str) -> dict[str, Any]:
    return {"configurable": {"thread_id": run_id}}


def _read_run_mock_llm(run_root: Path) -> bool:
    p = run_root / "run_meta.json"
    if not p.is_file():
        return False
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, TypeError):
        return False
    if not isinstance(data, dict):
        return False
    return bool(data.get("mock_llm"))


def pipeline_summary(p: PipelineState) -> dict[str, Any]:
    """JSON-serializable overview for tools and logs."""
    return {
        "run_id": p.run_id,
        "workspace_dir": p.workspace_dir,
        "problem_prompt": p.problem_prompt[:2000],
        "rqs": [{"id": r.id, "text": r.text} for r in p.rqs],
        "candidate_sources": [s.name for s in p.candidate_sources],
        "approved_sources": [s.name for s in p.approved_sources],
        "decisions_count": len(p.decisions),
        "last_decisions": [
            {"gate_id": d.gate_id, "choice": d.choice, "rationale": d.rationale[:500]}
            for d in p.decisions[-5:]
        ],
        "collection_exit_code": p.collection_last_exit_code,
        "collection_error": (p.collection_last_error or "")[:2000] if p.collection_last_error else None,
        "collected_paths_count": len(p.collected_data_paths),
        "research_plan": (json.dumps(p.research_plan, ensure_ascii=False)[:3000] if p.research_plan else None),
        "sample_notes": (p.sample_profile.notes[:2000] if p.sample_profile else None),
        "paper_section_keys": list(p.paper_sections.keys()),
        "threats_count": len(p.threats),
    }


def start_run(problem: str, *, config_path: Path | None = None, mock_llm: bool = False) -> dict[str, Any]:
    """Create a new run and perform the first graph invoke (may pause at a gate)."""
    cfg = load_config(config_path)
    cfg.workspace_dir.mkdir(parents=True, exist_ok=True)
    run_id = str(uuid.uuid4())
    run_root = run_workspace_root(cfg.workspace_dir, run_id)
    ensure_run_workspace(run_root)
    (run_root / "run_meta.json").write_text(
        json.dumps({"mock_llm": mock_llm}),
        encoding="utf-8",
    )
    prov = _prov(cfg.workspace_dir)
    prov.insert_run(run_id, problem, str(run_root.resolve()), status="running")

    pipeline = PipelineState(
        problem_prompt=problem,
        run_id=run_id,
        workspace_dir=str(run_root.resolve()),
    )
    graph = build_graph(checkpointer=_checkpointer(run_root))
    tc = _thread_cfg(run_id)

    with _run_lock(run_id):
        with mock_llm_context(mock_llm):
            out: dict[str, Any] = graph.invoke({"pipeline": pipeline}, tc)  # type: ignore[assignment]
        seen = prov.count_decisions(run_id)
        seen = _sync_decisions(prov, run_id, out["pipeline"], seen)
        p = coerce_pipeline_state(out["pipeline"])
        intr = _interrupt_from_out(out)
        if intr is None:
            prov.update_run_status(run_id, "completed")

    return {
        "run_id": run_id,
        "status": "paused" if intr is not None else "completed",
        "interrupt": intr,
        "pipeline": pipeline_summary(p),
        "mock_llm": mock_llm,
    }


def resume_run(
    run_id: str,
    resume: dict[str, Any],
    *,
    config_path: Path | None = None,
    mock_llm: bool = False,
) -> dict[str, Any]:
    """Resume a paused run with gate JSON (same shape as CLI)."""
    cfg = load_config(config_path)
    run_root = run_workspace_root(cfg.workspace_dir, run_id)
    if not run_root.is_dir():
        raise FileNotFoundError(f"Run workspace not found: {run_root}")
    row = _prov(cfg.workspace_dir).get_run(run_id)
    if not row:
        raise KeyError(f"Unknown run id: {run_id}")

    prov = _prov(cfg.workspace_dir)
    graph = build_graph(checkpointer=_checkpointer(run_root))
    tc = _thread_cfg(run_id)
    meta_path = run_root / "run_meta.json"
    effective_mock = _read_run_mock_llm(run_root) if meta_path.is_file() else mock_llm

    with _run_lock(run_id):
        with mock_llm_context(effective_mock):
            out: dict[str, Any] = graph.invoke(Command(resume=resume), tc)  # type: ignore[assignment]
        seen = prov.count_decisions(run_id)
        seen = _sync_decisions(prov, run_id, out["pipeline"], seen)
        p = coerce_pipeline_state(out["pipeline"])
        intr = _interrupt_from_out(out)
        if intr is None:
            prov.update_run_status(run_id, "completed")

    return {
        "run_id": run_id,
        "status": "paused" if intr is not None else "completed",
        "interrupt": intr,
        "pipeline": pipeline_summary(p),
        "mock_llm": effective_mock,
    }


def get_snapshot(run_id: str, *, config_path: Path | None = None) -> dict[str, Any]:
    """Current checkpoint snapshot + pending interrupt (if any)."""
    cfg = load_config(config_path)
    run_root = run_workspace_root(cfg.workspace_dir, run_id)
    if not run_root.is_dir():
        raise FileNotFoundError(f"Run workspace not found: {run_root}")
    prov = _prov(cfg.workspace_dir)
    row = prov.get_run(run_id)
    if not row:
        raise KeyError(f"Unknown run id: {run_id}")

    mock_flag = _read_run_mock_llm(run_root)
    graph = build_graph(checkpointer=_checkpointer(run_root))
    snap = graph.get_state(_thread_cfg(run_id))
    if not snap.values:
        return {
            "run_id": run_id,
            "provenance": row,
            "status": row.get("status"),
            "pipeline": None,
            "interrupt": None,
            "mock_llm": mock_flag,
        }
    p = coerce_pipeline_state(snap.values["pipeline"])
    intr = None
    if snap.interrupts:
        v = snap.interrupts[0].value
        intr = v if isinstance(v, dict) else None
    return {
        "run_id": run_id,
        "provenance": row,
        "status": row.get("status"),
        "pipeline": pipeline_summary(p),
        "interrupt": intr,
        "mock_llm": mock_flag,
    }


def list_runs(*, config_path: Path | None = None) -> list[dict[str, Any]]:
    cfg = load_config(config_path)
    return _prov(cfg.workspace_dir).list_runs()
