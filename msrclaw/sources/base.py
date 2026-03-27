"""Base interface for data source plugins."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any

from msrclaw.pipeline.state import ResearchQuestion, Script, SourceConfig


@dataclass(slots=True)
class AvailabilityReport:
    """Human-readable availability / complexity estimate for a source."""

    summary: str
    estimated_rows: str | None = None
    complexity: str | None = None  # low | medium | high
    notes: dict[str, Any] = field(default_factory=dict)


class BaseSource(ABC):
    """Every source implements validation, availability estimation, and script generation."""

    name: str
    description: str
    required_credentials: tuple[str, ...]

    @abstractmethod
    def validate_credentials(self, config: SourceConfig) -> bool:
        raise NotImplementedError

    @abstractmethod
    def estimate_availability(self, rqs: list[ResearchQuestion], config: SourceConfig) -> AvailabilityReport:
        raise NotImplementedError

    @abstractmethod
    def generate_collection_script(
        self,
        rqs: list[ResearchQuestion],
        config: SourceConfig,
        *,
        raw_out_dir: str,
    ) -> Script:
        """Return a standalone Python script that writes under `raw_out_dir`."""
        raise NotImplementedError

    def llm_prompt_hints(self, config: SourceConfig) -> str:
        """Extra instructions for :mod:`msrclaw.agents.llm_generated_scripts` (LLM-authored scripts)."""
        return (
            f"Source plugin: {self.name}\n"
            f"{self.description}\n"
            "Align queries and fields with the research problem and RQs."
        )
