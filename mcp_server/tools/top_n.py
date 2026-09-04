"""MCP tool: top_n."""

from __future__ import annotations

from typing import Any

from mcp_server.mcp_instance import mcp
from mcp_server.semantic_layer import get_client
from mcp_server.tools._common import run_tool


@mcp.tool()
def top_n(metric_name: str, dimension: str, limit: int = 10) -> dict[str, Any]:
    """Return ranking data (e.g. top 10 partners by revenue) using MetricFlow.

    Args:
        metric_name: The metric to rank by, e.g. ``total_revenue``.
        dimension: The dimension to rank, e.g. ``partner_network``.
        limit: Number of top rows to return.

    Returns:
        The standard ``{status, data, error}`` envelope with rows sorted
        descending by ``metric_name``.
    """
    return run_tool(get_client().top_n, metric_name, dimension, limit)
