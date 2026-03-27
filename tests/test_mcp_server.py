"""MCP server smoke tests."""

from __future__ import annotations

import asyncio

import pytest

pytest.importorskip("mcp")

from msrclaw.mcp_server import mcp


def test_mcp_tools_registered() -> None:
    tools = asyncio.run(mcp.list_tools())
    names = {t.name for t in tools}
    assert "msrclaw_start_run" in names
    assert "msrclaw_resume_run" in names
    assert "msrclaw_get_snapshot" in names
    assert "msrclaw_list_runs" in names
