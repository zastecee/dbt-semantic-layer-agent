"""Shared FastMCP application instance used by all MCP tool modules."""

from __future__ import annotations

from fastmcp import FastMCP

mcp = FastMCP(
    name="dbt-agent-semantic-layer",
    instructions=(
        "Exposes the National Roaming Semantic Layer, backed by MetricFlow, as MCP "
        "tools: health_check, list_metrics, list_dimensions, explain_metric, "
        "query_metric, get_time_series, top_n and metric_sql_preview. All metric "
        "computation and SQL generation is delegated to the MetricFlow CLI (`mf`); "
        "no SQL is built manually."
    ),
)
