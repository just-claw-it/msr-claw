"""Central pipeline state and supporting value types."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


@dataclass(frozen=True, slots=True)
class ResearchQuestion:
    """A research question with stable id for provenance."""

    id: str
    text: str


@dataclass(frozen=True, slots=True)
class SourceConfig:
    """Configuration for a data source (credentials resolved from env / msrclaw.yaml)."""

    name: str
    extra: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class Script:
    """A generated script artifact."""

    name: str
    path: str
    language: str = "python"
    content: str | None = None  # set before write; path filled after save


@dataclass(slots=True)
class SampleProfile:
    """Summary stats over a sample of collected data (stub for SamplerAgent)."""

    notes: str = ""
    metrics: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class Result:
    """Structured output from an analysis script."""

    rq_id: str
    result_type: str  # e.g. "table", "figure", "stat"
    path: str | None
    summary: str


@dataclass(slots=True)
class Threat:
    """A validity threat and optional mitigation."""

    category: str  # internal | external | construct
    description: str
    mitigation: str | None = None


@dataclass(slots=True)
class HumanDecision:
    """One human gate decision for provenance."""

    gate_id: str
    timestamp: datetime
    choice: str
    rationale: str

    @staticmethod
    def record(gate_id: str, choice: str, rationale: str) -> HumanDecision:
        return HumanDecision(
            gate_id=gate_id,
            timestamp=_utcnow(),
            choice=choice,
            rationale=rationale,
        )


@dataclass
class PipelineState:
    """Central state passed between agents and persisted across interrupts."""

    # Input
    problem_prompt: str

    # RQs
    rqs: list[ResearchQuestion] = field(default_factory=list)
    rq_history: list[list[ResearchQuestion]] = field(default_factory=list)

    # Data sources
    candidate_sources: list[SourceConfig] = field(default_factory=list)
    approved_sources: list[SourceConfig] = field(default_factory=list)

    # Collection
    collection_scripts: list[Script] = field(default_factory=list)
    collected_data_paths: list[str] = field(default_factory=list)
    collection_last_exit_code: int | None = None
    collection_last_error: str | None = None
    collection_skipped: bool = False

    # SourceAgent (availability estimates per plugin name)
    source_availability: dict[str, dict[str, Any]] = field(default_factory=dict)

    # Sample
    sample_profile: SampleProfile | None = None

    # LLM-produced plan (problem agent); drives tailoring downstream
    research_plan: dict[str, Any] | None = None

    # Analysis
    analysis_scripts: list[Script] = field(default_factory=list)
    results: list[Result] = field(default_factory=list)

    # Writing
    paper_sections: dict[str, str] = field(default_factory=dict)
    threats: list[Threat] = field(default_factory=list)

    # Provenance
    run_id: str = ""
    workspace_dir: str = ""
    decisions: list[HumanDecision] = field(default_factory=list)
