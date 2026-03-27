"""Human gate identifiers, payloads, and helpers for CLI + LangGraph interrupts."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any


class GateId(str, Enum):
    """The five milestone human gates (CLI may show \"GATE n OF 5\")."""

    REVIEW_RQS_AND_SOURCES = "review_rqs_and_sources"
    SELECT_SOURCES = "select_sources"
    REVIEW_SAMPLE = "review_sample"
    REFINE_RQS = "refine_rqs"
    REVIEW_VALIDITY = "review_validity"


# Optional: collection did not succeed — interrupt for retry / skip / abort (not one of the five above).
COLLECTION_RECOVERY_GATE_ID = "collection_recovery"


@dataclass(frozen=True, slots=True)
class GatePrompt:
    """JSON-serializable payload passed to `interrupt()` for rendering in the CLI."""

    gate_id: str
    ordinal: int  # 1..5 for milestone gates
    title: str
    body: dict[str, Any]


def milestone_gate_ids() -> tuple[str, ...]:
    return tuple(g.value for g in GateId)


def gate_ordinal(gate_id: str) -> int | None:
    order = {g.value: i + 1 for i, g in enumerate(GateId)}
    return order.get(gate_id)
