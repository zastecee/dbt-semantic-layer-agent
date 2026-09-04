"""Plotly chart builders used by the ADK agent and the Streamlit dashboard."""

from __future__ import annotations

from typing import Any, Optional

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go


def _to_dataframe(data: list[dict[str, Any]]) -> pd.DataFrame:
    return pd.DataFrame(data)


def create_bar_chart(
    data: list[dict[str, Any]],
    x: str,
    y: str,
    title: Optional[str] = None,
) -> Any:
    """Create a bar chart comparing ``y`` across categories of ``x``.

    Args:
        data: Rows of query results, typically the ``data`` field returned by
            ``query_metric``.
        x: Column name to use for the category axis.
        y: Column name to use for the value axis.
        title: Optional chart title.

    Returns:
        A Plotly ``Figure``.
    """
    frame = _to_dataframe(data)
    fig = px.bar(
        frame,
        x=x,
        y=y,
        title=title
        or f"{y.replace('_', ' ').title()} by {x.replace('_', ' ').title()}",
    )
    fig.update_layout(
        xaxis_title=x.replace("_", " ").title(), yaxis_title=y.replace("_", " ").title()
    )
    return fig


def create_line_chart(
    data: list[dict[str, Any]],
    x: str,
    y: str,
    color: Optional[str] = None,
    title: Optional[str] = None,
) -> Any:
    """Create a line chart showing the trend of ``y`` over ``x`` (typically a date dimension)."""
    frame = _to_dataframe(data)
    if x in frame.columns:
        frame = frame.sort_values(by=x)
    fig = px.line(
        frame,
        x=x,
        y=y,
        color=color,
        markers=True,
        title=title or f"{y.replace('_', ' ').title()} over Time",
    )
    fig.update_layout(
        xaxis_title=x.replace("_", " ").title(), yaxis_title=y.replace("_", " ").title()
    )
    return fig


def create_pie_chart(
    data: list[dict[str, Any]],
    names: str,
    values: str,
    title: Optional[str] = None,
) -> Any:
    """Create a pie chart showing the share of ``values`` across categories of ``names``."""
    frame = _to_dataframe(data)
    fig = px.pie(
        frame,
        names=names,
        values=values,
        title=title or f"Share of {values.replace('_', ' ').title()}",
    )
    return fig


def create_top_n_chart(
    data: list[dict[str, Any]],
    category: str,
    value: str,
    n: int = 10,
    title: Optional[str] = None,
) -> Any:
    """Create a horizontal bar chart of the top ``n`` categories ranked by ``value``."""
    frame = _to_dataframe(data)
    frame = frame.sort_values(by=value, ascending=False).head(n)
    fig = px.bar(
        frame,
        x=value,
        y=category,
        orientation="h",
        title=title
        or f"Top {n} {category.replace('_', ' ').title()} by {value.replace('_', ' ').title()}",
    )
    fig.update_layout(yaxis={"categoryorder": "total ascending"})
    return fig
