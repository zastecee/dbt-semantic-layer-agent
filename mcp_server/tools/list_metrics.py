"""MCP tool: list_metrics."""

from __future__ import annotations

from typing import Any

from mcp_server.mcp_instance import mcp
from mcp_server.semantic_layer import get_client
from mcp_server.tools._common import run_tool


@mcp.tool()
def list_metrics() -> dict[str, Any]:
    """List all business metrics exposed by MetricFlow (``mf list metrics``).

    Returns:
        The standard ``{status, data, error}`` envelope. ``data`` is a list
        of metrics, each with ``name``, ``label``, ``description`` and ``dimensions``.
    """
    return run_tool(get_client().list_metrics)
