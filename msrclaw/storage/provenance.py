"""SQLite provenance store (runs, decisions, scripts, RQ versions, results)."""

from __future__ import annotations

import json
import sqlite3
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from msrclaw.pipeline.state import HumanDecision, ResearchQuestion


def _utc_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class ProvenanceStore:
    """Append-only style tables for audit trail."""

    def __init__(self, db_path: Path) -> None:
        self._path = db_path
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._init_schema()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self._path), check_same_thread=False)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_schema(self) -> None:
        with self._connect() as c:
            c.executescript(
                """
                CREATE TABLE IF NOT EXISTS runs (
                    run_id TEXT PRIMARY KEY,
                    problem_prompt TEXT NOT NULL,
                    started_at TEXT NOT NULL,
                    status TEXT NOT NULL,
                    workspace_dir TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS decisions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    run_id TEXT NOT NULL,
                    gate_id TEXT NOT NULL,
                    timestamp TEXT NOT NULL,
                    choice TEXT NOT NULL,
                    rationale TEXT NOT NULL,
                    FOREIGN KEY (run_id) REFERENCES runs(run_id)
                );
                CREATE TABLE IF NOT EXISTS scripts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    run_id TEXT NOT NULL,
                    type TEXT NOT NULL,
                    name TEXT NOT NULL,
                    path TEXT NOT NULL,
                    executed_at TEXT,
                    exit_code INTEGER,
                    FOREIGN KEY (run_id) REFERENCES runs(run_id)
                );
                CREATE TABLE IF NOT EXISTS rq_versions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    run_id TEXT NOT NULL,
                    version INTEGER NOT NULL,
                    rqs_json TEXT NOT NULL,
                    reason_for_change TEXT,
                    FOREIGN KEY (run_id) REFERENCES runs(run_id)
                );
                CREATE TABLE IF NOT EXISTS results (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    run_id TEXT NOT NULL,
                    rq_id TEXT NOT NULL,
                    result_type TEXT NOT NULL,
                    path TEXT,
                    summary TEXT,
                    FOREIGN KEY (run_id) REFERENCES runs(run_id)
                );
                """
            )

    def insert_run(self, run_id: str, problem_prompt: str, workspace_dir: str, status: str = "running") -> None:
        with self._connect() as c:
            c.execute(
                """
                INSERT OR REPLACE INTO runs (run_id, problem_prompt, started_at, status, workspace_dir)
                VALUES (?, ?, ?, ?, ?)
                """,
                (run_id, problem_prompt, _utc_iso(), status, workspace_dir),
            )

    def update_run_status(self, run_id: str, status: str) -> None:
        with self._connect() as c:
            c.execute("UPDATE runs SET status = ? WHERE run_id = ?", (status, run_id))

    def log_decision(self, run_id: str, d: HumanDecision) -> None:
        with self._connect() as c:
            c.execute(
                """
                INSERT INTO decisions (run_id, gate_id, timestamp, choice, rationale)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    run_id,
                    d.gate_id,
                    d.timestamp.isoformat(),
                    d.choice,
                    d.rationale,
                ),
            )

    def count_decisions(self, run_id: str) -> int:
        with self._connect() as c:
            row = c.execute("SELECT COUNT(*) FROM decisions WHERE run_id = ?", (run_id,)).fetchone()
        return int(row[0]) if row else 0

    def log_script(
        self,
        run_id: str,
        *,
        script_type: str,
        name: str,
        path: str,
        executed_at: str | None,
        exit_code: int | None,
    ) -> None:
        with self._connect() as c:
            c.execute(
                """
                INSERT INTO scripts (run_id, type, name, path, executed_at, exit_code)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (run_id, script_type, name, path, executed_at, exit_code),
            )

    def log_rq_version(self, run_id: str, version: int, rqs: list[ResearchQuestion], reason: str) -> None:
        payload = json.dumps([asdict(rq) for rq in rqs])
        with self._connect() as c:
            c.execute(
                """
                INSERT INTO rq_versions (run_id, version, rqs_json, reason_for_change)
                VALUES (?, ?, ?, ?)
                """,
                (run_id, version, payload, reason),
            )

    def log_result(
        self, run_id: str, rq_id: str, result_type: str, path: str | None, summary: str
    ) -> None:
        with self._connect() as c:
            c.execute(
                """
                INSERT INTO results (run_id, rq_id, result_type, path, summary)
                VALUES (?, ?, ?, ?, ?)
                """,
                (run_id, rq_id, result_type, path, summary),
            )

    def list_runs(self) -> list[dict[str, Any]]:
        with self._connect() as c:
            rows = c.execute(
                "SELECT run_id, problem_prompt, started_at, status, workspace_dir FROM runs ORDER BY started_at DESC"
            ).fetchall()
        return [dict(r) for r in rows]

    def get_run(self, run_id: str) -> dict[str, Any] | None:
        with self._connect() as c:
            row = c.execute(
                "SELECT run_id, problem_prompt, started_at, status, workspace_dir FROM runs WHERE run_id = ?",
                (run_id,),
            ).fetchone()
        return dict(row) if row else None
