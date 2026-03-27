"""Ask the LLM for problem-specific collection and analysis Python (JSON envelope + validation).

When ``MSRCLAW_MOCK_LLM`` is set, callers should not use this module (use plugin / template fallbacks).

Disable LLM script synthesis (always use templates) with ``MSRCLAW_LLM_SCRIPTS=0``.
"""

from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Any

from msrclaw.agents.llm_tailoring import llm_scripts_enabled, research_plan_excerpt
from msrclaw.config import load_config
from msrclaw.llm import LLMClient
from msrclaw.pipeline.state import PipelineState, Script, SourceConfig
from msrclaw.sources.base import BaseSource


def _client() -> LLMClient:
    cfg = load_config()
    return LLMClient(
        base_url=cfg.llm_base_url,
        api_key=cfg.llm_api_key,
        model=cfg.llm_model,
    )


def _safe_py_filename(name: str, default: str) -> str:
    base = (name or default).strip()
    if not base.endswith(".py"):
        base += ".py"
    base = re.sub(r"[^a-zA-Z0-9_.-]+", "_", base.split("/")[-1])
    if not base.endswith(".py"):
        base += ".py"
    return base[:120] if base else default


def _validate_collection_script(script: str, raw_out_dir: str) -> bool:
    if len(script) > 200_000:
        return False
    if "def main" not in script and "main()" not in script:
        return False
    alts = {
        raw_out_dir,
        os.path.normpath(raw_out_dir),
        raw_out_dir.replace("\\", "/"),
        os.path.normpath(raw_out_dir).replace("\\", "/"),
    }
    if not any(a and a in script for a in alts):
        return False
    return True


def _validate_analysis_script(script: str, workspace_dir: str) -> bool:
    if len(script) > 200_000:
        return False
    if "def main" not in script and "main()" not in script:
        return False
    if "summary.json" not in script and "processed" not in script:
        return False
    return True


COLLECTION_SYSTEM = """You write Python 3.11+ data collection scripts for empirical software engineering (MSR) studies.

Respond with a single JSON object (no markdown fences) with exactly these keys:
- "filename": short name ending in .py, e.g. "collect_github_research.py"
- "script": full Python source code as a string

Rules for the script:
- Standard library only: json, os, re, pathlib, urllib.request, urllib.parse, csv, datetime, etc.
- Do not hardcode API keys or tokens. Read secrets with os.environ.get("GITHUB_TOKEN") or similar.
- Define RAW_OUT as a string constant set EXACTLY to the path given in the user message (copy it verbatim).
- Create RAW_OUT with pathlib.Path(RAW_OUT).mkdir(parents=True, exist_ok=True) or os.makedirs.
- Write at least one output file under RAW_OUT (prefer .jsonl for records).
- Include if __name__ == "__main__": main() and a main() function.
- Tailor HTTP requests, search queries, and field extraction to the research problem and RQs.
- Follow the research_plan.collection_strategy when choosing endpoints and filters.
"""


ANALYSIS_SYSTEM = """You write Python 3.11+ analysis scripts for MSR studies.

Respond with a single JSON object (no markdown fences) with exactly these keys:
- "filename": e.g. "analyze_msr_run.py"
- "script": full Python source as a string

Rules:
- Standard library only unless you only use pathlib/json/csv — prefer stdlib.
- Read inputs from the absolute file paths listed in the user message (collected data).
- Write a JSON summary to: WORKSPACE / "data" / "processed" / "summary.json"
  where WORKSPACE = Path(__file__).resolve().parents[2]
- The summary should relate results to the research questions and problem (even descriptively).
- Align tables and narrative keys with research_plan.analysis_strategy when present in the user message.
- Include if __name__ == "__main__": main()
"""


FIGURES_SYSTEM = """You write Python 3.11+ scripts that build publication-style figures for MSR studies.

Respond with JSON: {"filename": "make_figures.py", "script": "<full source>"}.

Rules:
- WORKSPACE = Path(__file__).resolve().parents[2]
- Write images under WORKSPACE / "figures" (create the directory). Use .png or .pdf names tied to the RQs/plan.
- You may use: pathlib, json, csv, and if available matplotlib and pandas (import inside try/except; if missing, write a small figures/README.md explaining intended plots instead).
- Read data only from absolute paths in the user message or from WORKSPACE / "data" / "raw" and "processed/summary.json".
- Tailor plot types and labels to the research_plan.figure_plan and the stated problem.
- Include if __name__ == "__main__": main()
"""


def try_llm_collection_script(
    pipeline: PipelineState,
    config: SourceConfig,
    plugin: BaseSource,
    *,
    raw_out_dir: str,
) -> Script | None:
    """Return an LLM-authored collection script, or None to use the source plugin template."""
    if not llm_scripts_enabled():
        return None
    rqs_blob = [{"id": r.id, "text": r.text} for r in pipeline.rqs]
    user = "\n".join(
        [
            "## Research problem",
            pipeline.problem_prompt.strip()[:12000],
            "",
            "## Research questions (answer with data you collect)",
            json.dumps(rqs_blob, indent=2, ensure_ascii=False),
            "",
            "## Approved data source",
            f"name: {config.name}",
            f"description: {plugin.description}",
            "",
            "## Source-specific hints",
            plugin.llm_prompt_hints(config),
            "",
            "## Research plan (from problem decomposition)",
            research_plan_excerpt(pipeline),
            "",
            "## Output directory (set RAW_OUT to this exact string in your script)",
            raw_out_dir,
        ]
    )
    try:
        data = _client().complete_json(system=COLLECTION_SYSTEM, user=user)
    except Exception:
        return None
    return _script_from_llm_response(data, raw_out_dir, default_name=f"collect_{config.name}.py", validator=_validate_collection_script)


def try_llm_analysis_script(pipeline: PipelineState) -> str | None:
    """Return LLM-authored analysis script body, or None to use template fallback."""
    if not llm_scripts_enabled():
        return None
    sp = pipeline.sample_profile
    sample_blob: dict[str, Any] = {}
    if sp:
        sample_blob = {"notes": sp.notes[:4000], "metrics": sp.metrics}
    rqs_blob = [{"id": r.id, "text": r.text} for r in pipeline.rqs]
    files = list(pipeline.collected_data_paths)
    user = "\n".join(
        [
            "## Research problem",
            pipeline.problem_prompt.strip()[:12000],
            "",
            "## Research questions",
            json.dumps(rqs_blob, indent=2, ensure_ascii=False),
            "",
            "## Collected data files (read these paths)",
            json.dumps(files, indent=2, ensure_ascii=False),
            "",
            "## Sample / profiling notes (from earlier pipeline step)",
            json.dumps(sample_blob, indent=2, ensure_ascii=False),
            "",
            "## Workspace root",
            pipeline.workspace_dir,
            "",
            "## Research plan",
            research_plan_excerpt(pipeline),
        ]
    )
    try:
        data = _client().complete_json(system=ANALYSIS_SYSTEM, user=user)
    except Exception:
        return None
    script = data.get("script") if isinstance(data, dict) else None
    if not isinstance(script, str) or not script.strip():
        return None
    if not _validate_analysis_script(script, pipeline.workspace_dir):
        return None
    return script


def _script_from_llm_response(
    data: dict[str, Any],
    path_hint: str,
    *,
    default_name: str,
    validator: Any,
) -> Script | None:
    if not isinstance(data, dict):
        return None
    script = data.get("script")
    if not isinstance(script, str) or not script.strip():
        return None
    if not validator(script, path_hint):
        return None
    name = _safe_py_filename(str(data.get("filename") or ""), default_name)
    return Script(name=name, path="", language="python", content=script)


def _validate_figures_script(script: str, workspace_dir: str) -> bool:
    if len(script) > 200_000:
        return False
    if "def main" not in script and "main()" not in script:
        return False
    s = script.replace("\\\\", "/")
    if "figures" not in s.lower():
        return False
    wd = workspace_dir.replace("\\\\", "/")
    if wd not in script and "Path(__file__)" not in script:
        return False
    return True


def try_llm_figures_script(pipeline: PipelineState) -> str | None:
    """Return LLM-authored figure-generation script, or None to skip figures pass."""
    if not llm_scripts_enabled():
        return None
    ws = pipeline.workspace_dir
    summary = str(Path(ws) / "data" / "processed" / "summary.json") if ws else ""
    user = "\n".join(
        [
            "## Research problem",
            pipeline.problem_prompt.strip()[:8000],
            "",
            "## Research questions",
            json.dumps([{"id": r.id, "text": r.text} for r in pipeline.rqs], indent=2, ensure_ascii=False),
            "",
            "## Research plan",
            research_plan_excerpt(pipeline),
            "",
            "## Processed summary (read if present)",
            summary,
            "",
            "## Collected data paths",
            json.dumps(list(pipeline.collected_data_paths), indent=2, ensure_ascii=False),
            "",
            "## Workspace",
            ws,
        ]
    )
    try:
        data = _client().complete_json(system=FIGURES_SYSTEM, user=user)
    except Exception:
        return None
    script = data.get("script") if isinstance(data, dict) else None
    if not isinstance(script, str) or not script.strip():
        return None
    if not _validate_figures_script(script, ws):
        return None
    return script
