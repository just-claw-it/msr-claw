"""AnalysisAgent: LLM-generated analysis script when enabled, else template fallback."""

from __future__ import annotations

import json
import os
from pathlib import Path

from msrclaw.agents.llm_generated_scripts import try_llm_analysis_script, try_llm_figures_script
from msrclaw.agents.llm_tailoring import figure_result_paths
from msrclaw.codegen.analysis_script import build_analysis_script
from msrclaw.pipeline.state import PipelineState, Result, Script


def run_analysis_agent(pipeline: PipelineState) -> None:
    ws = Path(pipeline.workspace_dir)
    out_dir = ws / "data" / "processed"
    out_dir.mkdir(parents=True, exist_ok=True)
    script_dir = ws / "scripts" / "analysis"
    script_dir.mkdir(parents=True, exist_ok=True)

    body = try_llm_analysis_script(pipeline)
    if body is None:
        body = build_analysis_script(pipeline)
    script_name = "analyze_msr_run.py"
    script_path = script_dir / script_name
    script_path.write_text(body.strip() + "\n", encoding="utf-8")
    pipeline.analysis_scripts.append(Script(name=script_path.name, path=str(script_path), language="python"))

    if os.environ.get("MSRCLAW_MOCK_LLM", "").lower() in ("1", "true", "yes"):
        pass
    else:
        import subprocess
        import sys

        subprocess.run([sys.executable, str(script_path)], cwd=str(ws), check=False)

    fig_body = try_llm_figures_script(pipeline)
    if fig_body:
        fig_path = script_dir / "make_figures.py"
        fig_path.write_text(fig_body.strip() + "\n", encoding="utf-8")
        pipeline.analysis_scripts.append(Script(name=fig_path.name, path=str(fig_path), language="python"))
        if os.environ.get("MSRCLAW_MOCK_LLM", "").lower() not in ("1", "true", "yes"):
            import subprocess
            import sys

            (ws / "figures").mkdir(parents=True, exist_ok=True)
            subprocess.run([sys.executable, str(fig_path)], cwd=str(ws), check=False)

    summary_path = out_dir / "summary.json"
    summary_text = "Analysis complete."
    if summary_path.is_file():
        try:
            blob = json.loads(summary_path.read_text(encoding="utf-8"))
            if isinstance(blob, dict):
                summary_text = json.dumps(blob, ensure_ascii=False)[:2000]
        except (OSError, json.JSONDecodeError):
            pass
    pipeline.results.append(
        Result(
            rq_id=pipeline.rqs[0].id if pipeline.rqs else "rq1",
            result_type="stat",
            path=str(summary_path) if summary_path.is_file() else None,
            summary=summary_text,
        )
    )
    rq0 = pipeline.rqs[0].id if pipeline.rqs else "rq1"
    for fp in figure_result_paths(str(ws)):
        pipeline.results.append(
            Result(
                rq_id=rq0,
                result_type="figure",
                path=fp,
                summary="Generated figure artifact.",
            )
        )
