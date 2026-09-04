"""Dashboard/summary assembly helpers shared by the ADK agent and the Streamlit app."""

from __future__ import annotations

import logging
from datetime import date, timedelta
from typing import Any, Optional

from mcp_server.semantic_layer import get_client

logger = logging.getLogger(__name__)


def _lookback_range(months: int = 6) -> tuple[str, str]:
    end = date.today()
    start = end - timedelta(days=30 * months)
    return start.isoformat(), end.isoformat()


def build_dashboard_summary(
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
) -> dict[str, Any]:
    """Build a headline metrics summary (revenue, usage, duration) for a period.

    Args:
        start_date: Optional inclusive start date (``YYYY-MM-DD``). Defaults to 6 months ago.
        end_date: Optional inclusive end date (``YYYY-MM-DD``). Defaults to today.

    Returns:
        A dict with ``start_date``, ``end_date`` and a ``metrics`` mapping of
        metric name to ``{"label": ..., "value": ...}``.
    """
    client = get_client()
    if not start_date or not end_date:
        default_start, default_end = _lookback_range()
        start_date = start_date or default_start
        end_date = end_date or default_end

    summary: dict[str, Any] = {
        "start_date": start_date,
        "end_date": end_date,
        "metrics": {},
    }
    for metric in client.list_summary_metrics():
        result = client.query_metric(
            metric["name"],
            dimensions=[],
            start_date=start_date,
            end_date=end_date,
            limit=1,
        )
        value = result["data"][0][metric["name"]] if result["data"] else 0
        summary["metrics"][metric["name"]] = {"label": metric["label"], "value": value}
    logger.info("Built dashboard summary for %s to %s", start_date, end_date)
    return summary
