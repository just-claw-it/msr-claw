"""Smoke tests for the LangGraph pipeline."""

from __future__ import annotations

from langgraph.types import Command

from msrclaw.pipeline.graph import build_graph
from msrclaw.pipeline.state import PipelineState


def test_full_run_with_all_gates_approved(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("MSRCLAW_MOCK_LLM", "1")
    monkeypatch.chdir(tmp_path)
    (tmp_path / "msrclaw.yaml").write_text(
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
    ws = tmp_path / "runws"
    ws.mkdir()

    g = build_graph()
    p = PipelineState(problem_prompt="p", run_id="run", workspace_dir=str(ws))
    cfg: dict = {"configurable": {"thread_id": "thread-smoke"}}

    out = g.invoke({"pipeline": p}, cfg)
    assert "__interrupt__" in out

    while "__interrupt__" in out:
        out = g.invoke(Command(resume={"choice": "approve", "rationale": "ok"}), cfg)

    assert "__interrupt__" not in out
    assert len(out["pipeline"].decisions) >= 5
