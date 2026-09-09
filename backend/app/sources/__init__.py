"""Source adapters for external systems."""

from app.sources.registry import get_repository_monitor

__all__ = ["get_repository_monitor"]
