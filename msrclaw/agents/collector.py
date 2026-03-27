"""CollectorAgent: write and execute collection scripts per approved source."""

from __future__ import annotations

import os
import subprocess
import sys
import traceback
from datetime import datetime, timezone
from pathlib import Path

from msrclaw.agents.llm_generated_scripts import try_llm_collection_script
from msrclaw.config import load_config
from msrclaw.pipeline.state import PipelineState, Script
from msrclaw.sources.registry import get_source


def _utc_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def run_collector_agent(pipeline: PipelineState) -> None:
    pipeline.collection_scripts.clear()
    pipeline.collected_data_paths.clear()
    pipeline.collection_last_error = None
    pipeline.collection_last_exit_code = None

    if pipeline.collection_skipped:
        pipeline.collection_last_exit_code = 0
        return

    if not pipeline.approved_sources:
        pipeline.collection_last_exit_code = 0
        return

    cfg = load_config()
    ws = Path(pipeline.workspace_dir)
    timeout_sec = max(60, int(cfg.collection_timeout_minutes * 60))
    overall_ok = True
    last_err: str | None = None
    last_code: int | None = 0

    for src in pipeline.approved_sources:
        try:
            cls = get_source(src.name)
        except KeyError as e:
            overall_ok = False
            last_err = str(e)
            last_code = 1
            break
        plugin = cls()
        raw_dir = ws / "data" / "raw" / src.name
        raw_dir.mkdir(parents=True, exist_ok=True)
        raw_out = str(raw_dir.resolve())
        script_obj = try_llm_collection_script(pipeline, src, plugin, raw_out_dir=raw_out)
        if script_obj is None:
            script_obj = plugin.generate_collection_script(
                pipeline.rqs,
                src,
                raw_out_dir=raw_out,
            )
        script_path = ws / "scripts" / "collection" / script_obj.name
        script_path.write_text(script_obj.content or "", encoding="utf-8")
        log_path = ws / "logs" / f"{src.name}.log"
        log_path.parent.mkdir(parents=True, exist_ok=True)
        env = os.environ.copy()
        merged = src.extra or {}
        token = merged.get("api_key")
        if token and str(token).strip():
            if str(token).startswith("${") and str(token).endswith("}"):
                pass
            else:
                env["GITHUB_TOKEN"] = str(token)
        try:
            proc = subprocess.run(
                [os.environ.get("MSRCLAW_PYTHON", sys.executable), str(script_path)],
                cwd=str(ws),
                env=env,
                capture_output=True,
                text=True,
                timeout=timeout_sec,
            )
        except subprocess.TimeoutExpired:
            overall_ok = False
            last_code = -1
            last_err = f"timeout after {timeout_sec}s for {src.name}"
            log_path.write_text(last_err or "", encoding="utf-8")
            break
        except Exception:
            overall_ok = False
            last_code = 1
            last_err = traceback.format_exc()
            log_path.write_text(last_err, encoding="utf-8")
            break

        log_path.write_text((proc.stdout or "") + ("\n--- stderr ---\n" + proc.stderr if proc.stderr else ""), encoding="utf-8")
        pipeline.collection_scripts.append(
            Script(name=script_obj.name, path=str(script_path), language="python", content=None)
        )
        # Collect JSONL / CSV paths
        for p in raw_dir.rglob("*"):
            if p.is_file() and p.suffix.lower() in (".jsonl", ".json", ".csv"):
                pipeline.collected_data_paths.append(str(p.resolve()))
        if proc.returncode != 0:
            overall_ok = False
            last_code = proc.returncode
            last_err = (proc.stderr or proc.stdout or "")[:8000]
            break

    pipeline.collection_last_exit_code = 0 if overall_ok else (last_code if last_code is not None else 1)
    pipeline.collection_last_error = None if overall_ok else (last_err or "collection failed")
