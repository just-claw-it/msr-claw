"""Generate `scripts/analysis/analyze_msr_run.py` from pipeline state (template + injection)."""

from __future__ import annotations

import json

from msrclaw.pipeline.state import PipelineState


def build_analysis_script(pipeline: PipelineState) -> str:
    """
    Emit a reproducible analysis scaffold: fixed structure, injected run id, problem,
    RQs, and paths to collected files. Extend this file for real statistics / plots.
    """
    ctx = {
        "run_id": pipeline.run_id,
        "problem_prompt": pipeline.problem_prompt[:8000],
        "research_questions": [{"id": r.id, "text": r.text} for r in pipeline.rqs],
        "collected_files": [str(p) for p in pipeline.collected_data_paths],
        "research_plan": dict(pipeline.research_plan) if pipeline.research_plan else {},
    }
    ctx_expr = python_json_loads_expr(ctx)

    return f'''# -*- coding: utf-8 -*-
"""MSR-Claw generated analysis (template + injection).

This file is produced by the Analysis agent. Structure is stable; values come from
your run (problem, RQs, collected paths). Replace `summarize_path` / `main` with
your study-specific statistics and visualizations.
"""
from __future__ import annotations

import csv
import json
from pathlib import Path

WORKSPACE = Path(__file__).resolve().parents[2]
CONTEXT = {ctx_expr}


def summarize_path(path: Path) -> dict:
    """Lightweight, dependency-free summaries for JSONL / CSV / small JSON."""
    out: dict = {{"path": str(path), "kind": "unknown", "note": ""}}
    if not path.is_file():
        out["note"] = "missing"
        return out
    suf = path.suffix.lower()
    try:
        if suf == ".jsonl":
            n = 0
            keys: set[str] = set()
            with path.open(encoding="utf-8", errors="replace") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    n += 1
                    if n <= 3:
                        try:
                            obj = json.loads(line)
                            if isinstance(obj, dict):
                                keys.update(obj.keys())
                        except json.JSONDecodeError:
                            pass
            out.update({{"kind": "jsonl", "rows": n, "sample_keys": sorted(keys)[:20]}})
        elif suf == ".csv":
            with path.open(encoding="utf-8", errors="replace", newline="") as f:
                r = csv.reader(f)
                header = next(r, [])
                n = sum(1 for _ in r) + (1 if header else 0)
            out.update({{"kind": "csv", "rows": max(0, n - 1), "columns": header[:40]}})
        elif suf == ".json":
            raw = path.read_text(encoding="utf-8", errors="replace")
            data = json.loads(raw)
            if isinstance(data, list):
                out.update({{"kind": "json", "rows": len(data)}})
            elif isinstance(data, dict):
                out.update({{"kind": "json", "keys": list(data.keys())[:40]}})
            else:
                out.update({{"kind": "json", "note": "scalar"}})
        else:
            out["note"] = "suffix not summarized; add a handler if needed"
    except OSError as e:
        out["note"] = str(e)[:500]
    return out


def main() -> None:
    processed = WORKSPACE / "data" / "processed"
    processed.mkdir(parents=True, exist_ok=True)
    out_path = processed / "summary.json"

    per_file = []
    for rel in CONTEXT.get("collected_files") or []:
        p = Path(rel)
        if not p.is_absolute():
            p = WORKSPACE / p
        per_file.append(summarize_path(p))

    payload = {{
        "generator": "msrclaw.codegen.analysis_script",
        "run_id": CONTEXT.get("run_id"),
        "problem_excerpt": (CONTEXT.get("problem_prompt") or "")[:500],
        "research_questions": CONTEXT.get("research_questions"),
        "file_summaries": per_file,
    }}
    out_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\\n", encoding="utf-8")
    print("wrote", out_path)


if __name__ == "__main__":
    main()
'''


def python_json_loads_expr(obj: object) -> str:
    """Python source fragment: parsed JSON object as literal."""
    return "json.loads(" + json.dumps(json.dumps(obj, ensure_ascii=False)) + ")"
