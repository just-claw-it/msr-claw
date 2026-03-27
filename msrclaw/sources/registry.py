"""Source plugin registry."""

from __future__ import annotations

from typing import TypeVar

from msrclaw.sources.base import BaseSource
from msrclaw.sources.github import GitHubSource

T = TypeVar("T", bound=type[BaseSource])

_SOURCES: dict[str, type[BaseSource]] = {
    GitHubSource.name: GitHubSource,
}


def register(cls: T) -> T:
    _SOURCES[cls.name] = cls
    return cls


def get_source(name: str) -> type[BaseSource]:
    if name not in _SOURCES:
        raise KeyError(f"Unknown source plugin: {name!r}. Registered: {sorted(_SOURCES)}")
    return _SOURCES[name]


def registered_names() -> tuple[str, ...]:
    return tuple(sorted(_SOURCES))
