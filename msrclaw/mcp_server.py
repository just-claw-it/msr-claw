"""Model Context Protocol (stdio) server — exposes MSR-Claw run/resume/list as MCP tools."""

from __future__ import annotations

import json
import os
import traceback
from pathlib import Path
from typing import Any

from mcp.server.fastmcp import FastMCP

from msrclaw import run_service


def _cfg() -> Path | None:
    raw = os.environ.get("MSRCLAW_CONFIG", "").strip()
    return Path(raw) if raw else None


def _json_error(exc: BaseException) -> str:
    return json.dumps({"error": str(exc), "traceback": traceback.format_exc()}, default=str)


mcp = FastMCP(
    "msr-claw",
    instructions=(
        "MSR-Claw: human-in-the-loop mining-software-research pipelines. "
        "Use msrclaw_start_run with a problem statement, then msrclaw_resume_run until status is completed. "
        "Set environment variable MSRCLAW_CONFIG to the path of msrclaw.yaml if not in the default cwd."
    ),
)


@mcp.tool()
def msrclaw_start_run(problem: str) -> str:
    """Start a new pipeline run. Returns JSON: run_id, status (paused|completed), interrupt payload if paused, pipeline summary."""
    try:
        out = run_service.start_run(problem.strip(), config_path=_cfg())
        return json.dumps(out, default=str)
    except Exception as e:
        return _json_error(e)


@mcp.tool()
def msrclaw_resume_run(run_id: str, resume: dict[str, Any]) -> str:
    """Resume a paused run at a human gate. `resume` must include \"choice\" (e.g. approve, approve_all, abort, retry, skip) and may include \"rationale\" or gate-specific keys."""
    try:
        if not isinstance(resume, dict):
            return _json_error(ValueError("resume must be an object"))
        out = run_service.resume_run(run_id.strip(), resume, config_path=_cfg())
        return json.dumps(out, default=str)
    except Exception as e:
        return _json_error(e)


@mcp.tool()
def msrclaw_get_snapshot(run_id: str) -> str:
    """Return checkpoint snapshot and pending interrupt for a run (from LangGraph + provenance)."""
    try:
        out = run_service.get_snapshot(run_id.strip(), config_path=_cfg())
        return json.dumps(out, default=str)
    except Exception as e:
        return _json_error(e)


@mcp.tool()
def msrclaw_list_runs() -> str:
    """List all runs from the provenance database."""
    try:
        rows = run_service.list_runs(config_path=_cfg())
        return json.dumps({"runs": rows}, default=str)
    except Exception as e:
        return _json_error(e)


def main() -> None:
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
