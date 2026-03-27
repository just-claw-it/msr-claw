"""Load `msrclaw.yaml` with `${ENV_VAR}` substitution."""

from __future__ import annotations

import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

_ENV_PATTERN = re.compile(r"\$\{([A-Za-z_][A-Za-z0-9_]*)\}")


def _substitute_env(value: Any) -> Any:
    if isinstance(value, str):

        def repl(m: re.Match[str]) -> str:
            name = m.group(1)
            return os.environ.get(name, "")

        return _ENV_PATTERN.sub(repl, value)
    if isinstance(value, dict):
        return {k: _substitute_env(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_substitute_env(v) for v in value]
    return value


@dataclass(frozen=True, slots=True)
class MSRClawConfig:
    """Resolved configuration for a run."""

    workspace_dir: Path
    llm_base_url: str
    llm_api_key: str
    llm_model: str
    collection_timeout_minutes: int
    collection_max_retries: int
    sample_size: int
    sources: dict[str, dict[str, Any]]
    raw: dict[str, Any]


def load_config(path: Path | None = None) -> MSRClawConfig:
    cfg_path = path or Path.cwd() / "msrclaw.yaml"
    if not cfg_path.is_file():
        raise FileNotFoundError(
            f"Config not found: {cfg_path}. Copy msrclaw.yaml.example to msrclaw.yaml and set LLM_* env vars."
        )
    raw = yaml.safe_load(cfg_path.read_text(encoding="utf-8")) or {}
    data = _substitute_env(raw)

    workspace = Path(data.get("workspace_dir", "./msr-workspace")).expanduser()
    llm = data.get("llm") or {}
    collection = data.get("collection") or {}
    sample = data.get("sample") or {}
    sources = data.get("sources") or {}

    return MSRClawConfig(
        workspace_dir=workspace,
        llm_base_url=str(llm.get("base_url") or os.environ.get("LLM_BASE_URL", "https://api.openai.com/v1")),
        llm_api_key=str(llm.get("api_key") or os.environ.get("LLM_API_KEY", "")),
        llm_model=str(llm.get("model") or os.environ.get("LLM_MODEL", "gpt-4o")),
        collection_timeout_minutes=int(collection.get("timeout_minutes", 30)),
        collection_max_retries=int(collection.get("max_retries", 2)),
        sample_size=int(sample.get("size", 1000)),
        sources=dict(sources) if isinstance(sources, dict) else {},
        raw=data,
    )
