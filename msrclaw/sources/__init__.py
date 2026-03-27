"""Data source plugins."""

from msrclaw.sources import registry
from msrclaw.sources.base import AvailabilityReport, BaseSource
from msrclaw.sources.github import GitHubSource

__all__ = ["AvailabilityReport", "BaseSource", "GitHubSource", "registry"]
