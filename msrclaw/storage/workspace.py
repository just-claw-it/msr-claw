"""Workspace directory layout for a pipeline run."""

from __future__ import annotations

from pathlib import Path


def run_workspace_root(cfg_workspace: Path, run_id: str) -> Path:
    """Per-run directory under the configured workspace root."""
    return cfg_workspace.expanduser().resolve() / "runs" / run_id


def ensure_run_workspace(root: Path) -> None:
    """Create standard subdirectories and placeholder files."""
    root.mkdir(parents=True, exist_ok=True)
    (root / "scripts" / "collection").mkdir(parents=True, exist_ok=True)
    (root / "scripts" / "analysis").mkdir(parents=True, exist_ok=True)
    (root / "data" / "raw").mkdir(parents=True, exist_ok=True)
    (root / "data" / "processed").mkdir(parents=True, exist_ok=True)
    (root / "figures").mkdir(parents=True, exist_ok=True)
    (root / "paper").mkdir(parents=True, exist_ok=True)
    (root / "logs").mkdir(parents=True, exist_ok=True)


def checkpoints_db_path(root: Path) -> Path:
    return root / "checkpoints.sqlite"
