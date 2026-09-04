"""MCP tool: query_metric."""

from __future__ import annotations

from typing import Any, Optional

from mcp_server.mcp_instance import mcp
from mcp_server.semantic_layer import get_client
from mcp_server.tools._common import run_tool


@mcp.tool()
def query_metric(
    metric_name: str,
    dimensions: Optional[list[str]] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    limit: int = 100,
) -> dict[str, Any]:
    """Execute a business query using MetricFlow (``mf query --metrics ... --group-by ...``).

    Never generates SQL manually: MetricFlow compiles and executes the query.

    Args:
        metric_name: The metric to compute, e.g. ``total_revenue``.
        dimensions: Optional list of dimensions to group by, e.g. ``["country"]``.
        start_date: Optional inclusive start date filter (``YYYY-MM-DD``).
        end_date: Optional inclusive end date filter (``YYYY-MM-DD``).
        limit: Maximum number of rows to return.

    Returns:
        The standard ``{status, data, error}`` envelope. ``data`` contains
        ``metric``, ``dimensions``, ``row_count`` and the resulting ``data`` rows.
    """
    return run_tool(
        get_client().query_metric, metric_name, dimensions, start_date, end_date, limit
    )
