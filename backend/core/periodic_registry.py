"""Compatibility wrapper around the shared PlatformKit task registry."""

from platformkit.periodic_registry import (
    TASK_REGISTRY,
    TaskRegistry,
    apply_registry,
)

__all__ = ["TASK_REGISTRY", "TaskRegistry", "apply_registry"]
