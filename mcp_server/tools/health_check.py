"""MCP tool: health_check."""

from __future__ import annotations

from typing import Any

from mcp_server.mcp_instance import mcp
from mcp_server.semantic_layer import get_client
from mcp_server.tools._common import run_tool


@mcp.tool()
def health_check() -> dict[str, Any]:
    """Check whether MetricFlow and the Semantic Layer can reach the data warehouse.

    Internally runs ``mf health-checks``.

    Returns:
        The standard ``{status, data, error}`` envelope. ``data`` contains
        ``healthy`` (bool) and ``details`` (raw health-check output).
    """
    return run_tool(get_client().health_check)
