"""LangGraph pipeline: state, gates, and graph."""

from __future__ import annotations

from typing import Any

from msrclaw.pipeline.gates import GateId
from msrclaw.pipeline.state import PipelineState
from msrclaw.pipeline.state_coercion import coerce_pipeline_state

__all__ = ["GateId", "PipelineState", "build_graph", "coerce_pipeline_state"]


def __getattr__(name: str) -> Any:
    if name == "build_graph":
        from msrclaw.pipeline.graph import build_graph

        return build_graph
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
