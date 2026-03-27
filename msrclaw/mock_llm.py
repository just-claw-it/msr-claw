"""Request-scoped toggling of MSRCLAW_MOCK_LLM for API/MCP testing."""

from __future__ import annotations

import os
from contextlib import contextmanager


@contextmanager
def mock_llm_context(active: bool):
    """When active, set MSRCLAW_MOCK_LLM=1 for the duration of the block (restores previous env)."""
    if not active:
        yield
        return
    key = "MSRCLAW_MOCK_LLM"
    prev = os.environ.get(key)
    os.environ[key] = "1"
    try:
        yield
    finally:
        if prev is None:
            os.environ.pop(key, None)
        else:
            os.environ[key] = prev
