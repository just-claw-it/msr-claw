"""SamplerAgent: sample up to N rows per dataset and compute coverage stats."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

import pandas as pd

from msrclaw.agents.llm_tailoring import enrich_sample_profile_llm
from msrclaw.config import load_config
from msrclaw.pipeline.state import PipelineState, SampleProfile


def _read_jsonl_sample(path: Path, n: int) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    with path.open(encoding="utf-8", errors="replace") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError:
                continue
            if len(rows) >= n:
                break
    return pd.DataFrame(rows)


def _profile_frame(df: pd.DataFrame) -> dict[str, Any]:
    if df.empty:
        return {"rows": 0, "columns": []}
    null_rates = {c: float(df[c].isna().mean()) for c in df.columns}
    dtypes = {c: str(df[c].dtype) for c in df.columns}
    return {
        "rows": int(len(df)),
        "columns": list(df.columns),
        "null_rates": null_rates,
        "dtypes": dtypes,
    }


def run_sampler_agent(pipeline: PipelineState) -> None:
    sample_n = load_config().sample_size
    if os.environ.get("MSRCLAW_MOCK_LLM", "").lower() in ("1", "true", "yes"):
        sample_n = min(sample_n, 50)

    metrics: dict[str, Any] = {"datasets": {}}
    notes_parts: list[str] = []

    paths = list(pipeline.collected_data_paths)
    if not paths:
        pipeline.sample_profile = SampleProfile(
            notes="No collected data files found to sample.",
            metrics=metrics,
        )
        return

    for p in paths:
        path = Path(p)
        if not path.is_file():
            continue
        key = str(path)
        if path.suffix.lower() == ".jsonl":
            df = _read_jsonl_sample(path, sample_n)
        elif path.suffix.lower() == ".csv":
            df = pd.read_csv(path, nrows=sample_n)
        elif path.suffix.lower() == ".json":
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
                if isinstance(data, list):
                    df = pd.DataFrame(data[:sample_n])
                else:
                    df = pd.DataFrame([data])
            except Exception:
                continue
        else:
            continue
        metrics["datasets"][key] = _profile_frame(df)
        notes_parts.append(f"{path.name}: {len(df)} rows sampled")

    pipeline.sample_profile = SampleProfile(
        notes="; ".join(notes_parts) if notes_parts else "No tabular samples produced.",
        metrics=metrics,
    )
    enrich_sample_profile_llm(pipeline)
