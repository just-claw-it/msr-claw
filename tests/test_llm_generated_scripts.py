"""LLM script generation and fallbacks."""

from __future__ import annotations

from pathlib import Path

import pytest

from msrclaw.agents.llm_generated_scripts import (
    llm_scripts_enabled,
    try_llm_analysis_script,
    try_llm_collection_script,
)
from msrclaw.llm import LLMClient
from msrclaw.pipeline.state import PipelineState, ResearchQuestion, SourceConfig
from msrclaw.sources.github import GitHubSource


def test_llm_scripts_disabled_under_mock_llm(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MSRCLAW_MOCK_LLM", "1")
    assert llm_scripts_enabled() is False


def test_llm_scripts_respects_env_off(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("MSRCLAW_MOCK_LLM", raising=False)
    monkeypatch.setenv("MSRCLAW_LLM_SCRIPTS", "0")
    assert llm_scripts_enabled() is False


def _write_config(path: Path) -> None:
    (path / "msrclaw.yaml").write_text(
        "\n".join(
            [
                "workspace_dir: ./ws",
                "llm:",
                "  base_url: http://localhost",
                "  api_key: x",
                "  model: gpt-4o",
                "collection:",
                "  timeout_minutes: 1",
                "  max_retries: 0",
                "sample:",
                "  size: 50",
                "sources: {}",
                "",
            ]
        ),
        encoding="utf-8",
    )


def test_try_collection_returns_script_when_llm_ok(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.chdir(tmp_path)
    _write_config(tmp_path)
    monkeypatch.delenv("MSRCLAW_MOCK_LLM", raising=False)
    monkeypatch.setenv("MSRCLAW_LLM_SCRIPTS", "1")
    raw = str((tmp_path / "raw" / "github").resolve())

    def fake_json(self: LLMClient, *, system: str, user: str) -> dict:
        return {
            "filename": "collect_custom.py",
            "script": f"""
import os
from pathlib import Path

RAW_OUT = r"{raw}"

def main() -> None:
    Path(RAW_OUT).mkdir(parents=True, exist_ok=True)
    p = Path(RAW_OUT) / "out.jsonl"
    p.write_text("{{}}\\n", encoding="utf-8")

if __name__ == "__main__":
    main()
""",
        }

    monkeypatch.setattr(LLMClient, "complete_json", fake_json)

    p = PipelineState(
        problem_prompt="Study flaky tests",
        run_id="r1",
        workspace_dir=str(tmp_path),
        rqs=[ResearchQuestion(id="rq1", text="How common are flaky tests?")],
    )
    cfg = SourceConfig(name="github", extra={})
    plugin = GitHubSource()
    out = try_llm_collection_script(p, cfg, plugin, raw_out_dir=raw)
    assert out is not None
    assert out.name == "collect_custom.py"
    assert "def main" in (out.content or "")


def test_try_analysis_returns_string(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.chdir(tmp_path)
    _write_config(tmp_path)
    monkeypatch.delenv("MSRCLAW_MOCK_LLM", raising=False)
    monkeypatch.setenv("MSRCLAW_LLM_SCRIPTS", "1")
    ws = str(tmp_path.resolve())

    def fake_json(self: LLMClient, *, system: str, user: str) -> dict:
        return {
            "filename": "analyze_msr_run.py",
            "script": f"""
import json
from pathlib import Path

def main() -> None:
    ws = Path(r"{ws}")
    out = ws / "data" / "processed" / "summary.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps({{"ok": True}}), encoding="utf-8")

if __name__ == "__main__":
    main()
""",
        }

    monkeypatch.setattr(LLMClient, "complete_json", fake_json)

    pl = PipelineState(
        problem_prompt="Flaky tests",
        run_id="r2",
        workspace_dir=ws,
        rqs=[ResearchQuestion(id="rq1", text="Prevalence?")],
        collected_data_paths=[str(tmp_path / "x.jsonl")],
    )
    body = try_llm_analysis_script(pl)
    assert body is not None
    assert "summary.json" in body
    assert "def main" in body
