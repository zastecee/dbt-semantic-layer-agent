"""MCP tool: list_dimensions."""

from __future__ import annotations

from typing import Any, Optional

from mcp_server.mcp_instance import mcp
from mcp_server.semantic_layer import get_client
from mcp_server.tools._common import run_tool


@mcp.tool()
def list_dimensions(metric_name: Optional[str] = None) -> dict[str, Any]:
    """List dimensions available for a metric (``mf list dimensions --metrics <metric_name>``).

    Args:
        metric_name: Optional metric to scope the dimensions to. If omitted,
            all dimensions known to the semantic layer are returned.

    Returns:
        The standard ``{status, data, error}`` envelope. ``data`` is a list
        of dimensions, each with ``name`` and MetricFlow's ``qualified_name``.
    """
    return run_tool(get_client().list_dimensions, metric_name)
