"""MCP tool: get_time_series."""

from __future__ import annotations

from typing import Any, Optional

from mcp_server.mcp_instance import mcp
from mcp_server.semantic_layer import get_client
from mcp_server.tools._common import run_tool


@mcp.tool()
def get_time_series(
    metric_name: str,
    granularity: str = "month",
    dimensions: Optional[list[str]] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
) -> dict[str, Any]:
    """Return a metric's evolution over time via MetricFlow (``--group-by metric_time__<granularity>``).

    Args:
        metric_name: The metric to compute, e.g. ``total_revenue``.
        granularity: One of ``day``, ``week``, ``month``, ``quarter``, ``year``.
        start_date: Optional inclusive start date filter (``YYYY-MM-DD``).
        end_date: Optional inclusive end date filter (``YYYY-MM-DD``).

    Returns:
        The standard ``{status, data, error}`` envelope with the time series
        rows ordered chronologically.
    """
    return run_tool(
        get_client().get_time_series,
        metric_name,
        granularity,
        dimensions,
        start_date,
        end_date,
    )
