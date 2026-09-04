"""Entrypoint for the MCP server exposing the National Roaming dbt Semantic Layer.

Run with:
    python -m mcp_server.app
"""

from __future__ import annotations

import logging
import os

from mcp_server import (
    tools,  # noqa: F401  (imported for tool-registration side effects)
)
from mcp_server.mcp_instance import mcp

logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO"),
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)

logger = logging.getLogger(__name__)


def main() -> None:
    """Start the MCP server using the streamable-http transport."""
    host = os.getenv("MCP_SERVER_HOST", "0.0.0.0")
    port = int(os.getenv("MCP_SERVER_PORT", "8000"))
    logger.info("Starting MCP server on %s:%s", host, port)
    mcp.run(transport="streamable-http", host=host, port=port)


if __name__ == "__main__":
    main()
