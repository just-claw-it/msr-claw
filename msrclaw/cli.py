"""Typer CLI: init, resume, status, list, export."""

from __future__ import annotations

import json
import sqlite3
import uuid
import zipfile
from pathlib import Path
from typing import Any

import typer
from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.types import Command

from msrclaw.config import load_config
from msrclaw.pipeline.graph import build_graph
from msrclaw.pipeline.state import PipelineState
from msrclaw.pipeline.state_coercion import coerce_pipeline_state
from msrclaw.storage.provenance import ProvenanceStore
from msrclaw.storage.workspace import checkpoints_db_path, ensure_run_workspace, run_workspace_root

app = typer.Typer(
    name="msr-claw",
    no_args_is_help=True,
    help="MSR-Claw — human-in-the-loop MSR research pipeline.",
)


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


def _interrupt_payload(out: dict[str, Any]) -> dict[str, Any] | None:
    xs = out.get("__interrupt__") or []
    if not xs:
        return None
    val = xs[0].value
    return val if isinstance(val, dict) else None


def _render_interrupt(payload: dict[str, Any]) -> None:
    gid = payload.get("gate_id", "")
    ordinal = int(payload.get("ordinal") or 0)
    title = payload.get("title", "")
    body = payload.get("body") or {}
    typer.echo("")
    typer.echo("═══════════════════════════════════════")
    if ordinal:
        typer.echo(f"GATE {ordinal} OF 5 — {title}")
    else:
        typer.echo(f"COLLECTION — {title}")
    typer.echo("═══════════════════════════════════════")
    typer.echo(f"gate_id: {gid}")
    typer.echo(json.dumps(body, indent=2, default=str))
    typer.echo("")
    typer.echo("Respond with JSON on one line, e.g.")
    typer.echo('  {"choice":"approve","rationale":"ok"}')
    typer.echo("Common choices: approve | approve_all | a | abort | x | retry | r | skip | s")
    typer.echo("Optional keys: rqs, candidate_sources, approved_source_names, sources")


def _parse_resume_line(line: str) -> dict[str, Any]:
    line = line.strip()
    if not line:
        return {"choice": "approve", "rationale": ""}
    try:
        val = json.loads(line)
        return val if isinstance(val, dict) else {"choice": str(val), "rationale": ""}
    except json.JSONDecodeError:
        return {"choice": line, "rationale": ""}


@app.command("init")
def init_cmd(
    problem: str = typer.Argument(..., help="MSR research problem description"),
    config: Path | None = typer.Option(None, "--config", "-c", help="Path to msrclaw.yaml"),
) -> None:
    """Start a new pipeline run."""
    cfg = load_config(config)
    cfg.workspace_dir.mkdir(parents=True, exist_ok=True)
    run_id = str(uuid.uuid4())
    run_root = run_workspace_root(cfg.workspace_dir, run_id)
    ensure_run_workspace(run_root)
    prov = _prov(cfg.workspace_dir)
    prov.insert_run(run_id, problem, str(run_root.resolve()), status="running")

    pipeline = PipelineState(
        problem_prompt=problem,
        run_id=run_id,
        workspace_dir=str(run_root.resolve()),
    )
    graph = build_graph(checkpointer=_checkpointer(run_root))
    thread_cfg: dict[str, Any] = {"configurable": {"thread_id": run_id}}
    seen = 0

    out: dict[str, Any] = graph.invoke({"pipeline": pipeline}, thread_cfg)  # type: ignore[assignment]
    pipeline = coerce_pipeline_state(out["pipeline"])
    seen = _sync_decisions(prov, run_id, out["pipeline"], seen)

    while True:
        payload = _interrupt_payload(out)
        if payload is None:
            break
        _render_interrupt(payload)
        line = typer.prompt("Your JSON response", default='{"choice":"approve","rationale":"ok"}')
        resume = _parse_resume_line(line)
        out = graph.invoke(Command(resume=resume), thread_cfg)  # type: ignore[assignment]
        pipeline = coerce_pipeline_state(out["pipeline"])
        seen = _sync_decisions(prov, run_id, out["pipeline"], seen)

    prov.update_run_status(run_id, "completed")
    typer.echo(f"Run {run_id} completed.")


@app.command("resume")
def resume_cmd(
    run_id: str = typer.Argument(..., help="Run id to resume"),
    config: Path | None = typer.Option(None, "--config", "-c", help="Path to msrclaw.yaml"),
) -> None:
    """Resume a paused pipeline."""
    cfg = load_config(config)
    run_root = run_workspace_root(cfg.workspace_dir, run_id)
    if not run_root.is_dir():
        typer.echo(f"Unknown run workspace: {run_root}", err=True)
        raise typer.Exit(code=1)
    prov = _prov(cfg.workspace_dir)
    row = prov.get_run(run_id)
    if not row:
        typer.echo(f"Unknown run id in provenance: {run_id}", err=True)
        raise typer.Exit(code=1)

    graph = build_graph(checkpointer=_checkpointer(run_root))
    thread_cfg: dict[str, Any] = {"configurable": {"thread_id": run_id}}
    snap = graph.get_state(thread_cfg)
    if not snap.values:
        typer.echo("No checkpoint state for this run.", err=True)
        raise typer.Exit(code=1)
    pipeline = coerce_pipeline_state(snap.values["pipeline"])
    seen = len(pipeline.decisions)

    if not snap.interrupts:
        typer.echo("No pending interrupt for this run.")
        raise typer.Exit(code=0)

    payload0 = snap.interrupts[0].value
    if isinstance(payload0, dict):
        _render_interrupt(payload0)
    line = typer.prompt("Your JSON response", default='{"choice":"approve","rationale":"ok"}')
    resume = _parse_resume_line(line)
    out = graph.invoke(Command(resume=resume), thread_cfg)  # type: ignore[assignment]
    pipeline = coerce_pipeline_state(out["pipeline"])
    seen = _sync_decisions(prov, run_id, out["pipeline"], seen)

    while True:
        payload = _interrupt_payload(out)
        if payload is None:
            break
        _render_interrupt(payload)
        line = typer.prompt("Your JSON response", default='{"choice":"approve","rationale":"ok"}')
        resume = _parse_resume_line(line)
        out = graph.invoke(Command(resume=resume), thread_cfg)  # type: ignore[assignment]
        pipeline = coerce_pipeline_state(out["pipeline"])
        seen = _sync_decisions(prov, run_id, out["pipeline"], seen)

    prov.update_run_status(run_id, "completed")
    typer.echo(f"Run {run_id} completed.")


@app.command("status")
def status_cmd(
    run_id: str = typer.Argument(..., help="Run id"),
    config: Path | None = typer.Option(None, "--config", "-c", help="Path to msrclaw.yaml"),
) -> None:
    """Show current pipeline state and next interrupt (if any)."""
    cfg = load_config(config)
    run_root = run_workspace_root(cfg.workspace_dir, run_id)
    graph = build_graph(checkpointer=_checkpointer(run_root))
    thread_cfg: dict[str, Any] = {"configurable": {"thread_id": run_id}}
    snap = graph.get_state(thread_cfg)
    if not snap.values:
        typer.echo("No checkpoint for this run.")
        raise typer.Exit(code=1)
    p = coerce_pipeline_state(snap.values["pipeline"])
    typer.echo(json.dumps({"run_id": p.run_id, "workspace": p.workspace_dir}, indent=2))
    typer.echo(json.dumps({"rqs": [{"id": r.id, "text": r.text} for r in p.rqs]}, indent=2))
    typer.echo(json.dumps({"decisions": [d.choice for d in p.decisions]}, indent=2))
    intr = snap.interrupts
    if intr:
        typer.echo("Pending interrupt:")
        typer.echo(json.dumps(intr[0].value, indent=2, default=str))
    else:
        typer.echo("No pending interrupt (graph may be finished).")


@app.command("list")
def list_cmd(config: Path | None = typer.Option(None, "--config", "-c", help="Path to msrclaw.yaml")) -> None:
    """List all runs from provenance."""
    cfg = load_config(config)
    prov = _prov(cfg.workspace_dir)
    rows = prov.list_runs()
    for r in rows:
        typer.echo(f"{r['run_id']}\t{r['status']}\t{r['started_at']}\t{r['workspace_dir']}")


@app.command("export")
def export_cmd(
    run_id: str = typer.Argument(..., help="Run id"),
    out: Path = typer.Option(Path("export.zip"), "--out", "-o", help="Output zip path"),
    config: Path | None = typer.Option(None, "--config", "-c", help="Path to msrclaw.yaml"),
) -> None:
    """Zip the run workspace (replication package)."""
    cfg = load_config(config)
    run_root = run_workspace_root(cfg.workspace_dir, run_id)
    if not run_root.is_dir():
        typer.echo(f"Unknown run workspace: {run_root}", err=True)
        raise typer.Exit(code=1)
    guide = run_root / "replication-guide.md"
    if not guide.is_file():
        guide.write_text(
            "# Replication guide\n\n"
            "1. Copy `msrclaw.yaml` and set API tokens.\n"
            "2. Install `msr-claw` from the project root.\n"
            "3. Re-run collection scripts under `scripts/collection/` into `data/raw/`.\n"
            "4. Re-run analysis scripts under `scripts/analysis/`.\n",
            encoding="utf-8",
        )
    with zipfile.ZipFile(out, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for path in run_root.rglob("*"):
            if path.is_file():
                zf.write(path, arcname=f"{run_id}/{path.relative_to(run_root).as_posix()}")
    typer.echo(f"Wrote {out.resolve()}")


@app.command("mcp")
def mcp_cmd() -> None:
    """Run the Model Context Protocol server (stdio) for IDE / Claude Desktop integration."""
    try:
        from msrclaw.mcp_server import main as mcp_main
    except ImportError as e:
        typer.echo("Missing MCP dependency. Install: pip install 'msr-claw[mcp]'", err=True)
        raise typer.Exit(code=1) from e
    mcp_main()


def main() -> None:
    app()


if __name__ == "__main__":
    main()
