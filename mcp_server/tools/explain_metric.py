"""MCP tool: explain_metric."""

from __future__ import annotations

from typing import Any

from mcp_server.mcp_instance import mcp
from mcp_server.semantic_layer import get_client
from mcp_server.tools._common import run_tool


@mcp.tool()
def explain_metric(metric_name: str) -> dict[str, Any]:
    """Return metadata for a metric: name, description, measure and available dimensions.

    Args:
        metric_name: The metric to explain, e.g. ``total_revenue``.

    Returns:
        The standard ``{status, data, error}`` envelope.
    """
    return run_tool(get_client().explain_metric, metric_name)
