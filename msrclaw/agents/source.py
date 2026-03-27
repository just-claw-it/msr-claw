"""SourceAgent: validate credentials and estimate availability per candidate source."""

from __future__ import annotations

from msrclaw.config import load_config
from msrclaw.pipeline.state import PipelineState, SourceConfig
from msrclaw.sources.registry import get_source


def _merge_yaml_credentials(name: str, cfg_extra: dict) -> dict:
    cfg = load_config()
    block = (cfg.sources or {}).get(name) or {}
    merged = {**dict(block), **dict(cfg_extra)}
    return merged


def run_source_agent(pipeline: PipelineState) -> None:
    pipeline.source_availability.clear()
    validated: list[SourceConfig] = []
    for cand in pipeline.candidate_sources:
        try:
            cls = get_source(cand.name)
        except KeyError:
            pipeline.source_availability[cand.name] = {"valid": False, "error": "unknown source plugin"}
            continue
        plugin = cls()
        merged_extra = _merge_yaml_credentials(cand.name, cand.extra or {})
        cfg = SourceConfig(name=cand.name, extra=merged_extra)
        ok = plugin.validate_credentials(cfg)
        if not ok:
            pipeline.source_availability[cand.name] = {"valid": False, "error": "credentials missing or invalid"}
            continue
        report = plugin.estimate_availability(pipeline.rqs, cfg)
        pipeline.source_availability[cand.name] = {
            "valid": True,
            "summary": report.summary,
            "estimated_rows": report.estimated_rows,
            "complexity": report.complexity,
            "notes": report.notes,
        }
        validated.append(cfg)
    pipeline.approved_sources = validated
