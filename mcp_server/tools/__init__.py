"""MCP tool modules. Importing this package registers every tool with the shared FastMCP instance."""

from mcp_server.tools import (  # noqa: F401  (imported for tool-registration side effects)
    explain_metric,
    get_time_series,
    health_check,
    list_dimensions,
    list_metrics,
    metric_sql_preview,
    query_metric,
    top_n,
)

__all__ = [
    "health_check",
    "list_metrics",
    "list_dimensions",
    "explain_metric",
    "query_metric",
    "get_time_series",
    "top_n",
    "metric_sql_preview",
]
