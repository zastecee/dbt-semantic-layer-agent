"""Shared helpers for building the standard MCP tool JSON response schema."""

from __future__ import annotations

import logging
from typing import Any, Callable

logger = logging.getLogger(__name__)


def success(data: Any) -> dict[str, Any]:
    """Wrap a successful tool result in the standard ``{status, data, error}`` schema."""
    return {"status": "success", "data": data, "error": None}


def failure(message: str) -> dict[str, Any]:
    """Wrap a failed tool result in the standard ``{status, data, error}`` schema."""
    return {"status": "error", "data": None, "error": message}


def run_tool(func: Callable[..., Any], *args: Any, **kwargs: Any) -> dict[str, Any]:
    """Execute a tool callable, normalizing its result or exception into the standard schema."""
    try:
        return success(func(*args, **kwargs))
    except Exception as exc:  # noqa: BLE001
        logger.exception("MCP tool %s failed", getattr(func, "__name__", func))
        return failure(str(exc))
