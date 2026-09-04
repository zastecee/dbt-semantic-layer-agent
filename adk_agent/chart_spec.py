"""Validation and rendering helpers for ADK-generated chart specifications."""

from __future__ import annotations

import json
from typing import Any

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

ALLOWED_TYPES = {
    "bar",
    "line",
    "area",
    "scatter",
    "pie",
    "histogram",
    "box",
    "heatmap",
}
MAX_ROWS = 5000
TIME_ALIASES = {
    "day": "event_date",
    "date": "event_date",
    "week": "event_date",
    "month": "event_date",
    "quarter": "event_date",
    "year": "event_date",
}


def _normalize_field(field: str | None) -> str | None:
    if field and field.startswith("metric_time__"):
        return "event_date"
    return TIME_ALIASES.get(field, field)


CHART_CAPABILITIES = {
    "bar": {"requires_x": True, "requires_y": True},
    "line": {"requires_x": True, "requires_y": True},
    "area": {"requires_x": True, "requires_y": True},
    "scatter": {"requires_x": True, "requires_y": True},
    "pie": {"requires_x": True, "requires_y": True},
    "histogram": {"requires_x": True, "requires_y": False},
    "box": {"requires_x": True, "requires_y": True},
    "heatmap": {"requires_x": True, "requires_y": True},
}


def parse_response(response: str) -> tuple[str, dict[str, Any] | None]:
    """Extract the optional chart specification from the model response."""
    start_marker = "<CHART_SPEC>"
    end_marker = "</CHART_SPEC>"
    start = response.find(start_marker)
    if start < 0:
        return response.strip(), None
    end = response.find(end_marker, start + len(start_marker))
    if end < 0:
        raise ValueError("The chart specification is missing </CHART_SPEC>.")
    raw_spec = response[start + len(start_marker) : end].strip()
    try:
        spec = json.loads(raw_spec)
    except json.JSONDecodeError as exc:
        raise ValueError(f"Invalid chart specification JSON: {exc}") from exc
    text = (response[:start] + response[end + len(end_marker) :]).strip()
    return text, spec


def validate_spec(spec: dict[str, Any], client: Any) -> dict[str, Any]:
    """Validate a model-produced spec against the semantic-layer metadata."""
    if not isinstance(spec, dict):
        raise ValueError("Chart specification must be a JSON object.")
    if "chart" in spec:
        query = spec.get("query", {})
        chart = spec.get("chart", {})
        metrics = query.get("metrics", [])
        spec = {
            **query,
            **chart,
            "metric": chart.get("metric", metrics[0] if metrics else None),
            "metrics": chart.get("metrics", metrics),
            "dimensions": chart.get("dimensions", query.get("group_by", [])),
            "start_date": query.get("start_date", query.get("start_time")),
            "end_date": query.get("end_date", query.get("end_time")),
        }
    chart_type = spec.get("type")
    if chart_type not in ALLOWED_TYPES:
        raise ValueError(f"Unsupported chart type: {chart_type!r}.")
    x_field = spec.get("x")
    color_field = spec.get("color")
    comparison = spec.get("comparison")
    if comparison is None and "comparison_period" in {x_field, color_field}:
        comparison = "mom"
    if comparison not in {None, "mom", "yoy"}:
        raise ValueError(f"Unsupported comparison: {comparison!r}.")
    requested_metrics = spec.get("metrics")
    if requested_metrics is None:
        y_value = spec.get("y")
        requested_metrics = (
            y_value if isinstance(y_value, list) else [spec.get("metric")]
        )
    if not isinstance(requested_metrics, list) or not all(
        isinstance(item, str) for item in requested_metrics
    ):
        raise ValueError("Chart metrics must be a list of strings.")
    metric = requested_metrics[0] if requested_metrics else None
    metrics = {item["name"]: item for item in client.list_metrics()}
    unknown_metrics = set(requested_metrics) - set(metrics)
    if unknown_metrics:
        raise ValueError(
            f"Unknown chart metrics: {', '.join(sorted(unknown_metrics))}."
        )
    dimensions = spec.get("dimensions", [])
    if not isinstance(dimensions, list) or not all(
        isinstance(item, str) for item in dimensions
    ):
        raise ValueError("Chart dimensions must be a list of strings.")
    granularity = spec.get("granularity")
    if granularity is None and x_field in {"day", "week", "month", "quarter", "year"}:
        granularity = x_field
    if (
        granularity is None
        and x_field == "event_date"
        and "event_date" not in dimensions
    ):
        granularity = "month"
    if (
        granularity is None
        and len(dimensions) == 1
        and dimensions[0] in {"day", "week", "month", "quarter", "year"}
    ):
        granularity = dimensions[0]
    if granularity is not None and granularity not in {
        "day",
        "week",
        "month",
        "quarter",
        "year",
    }:
        raise ValueError(f"Unsupported chart granularity: {granularity!r}.")
    dimensions = [_normalize_field(item) for item in dimensions]
    available = set(metrics[metric]["dimensions"])
    unknown = set(dimensions) - available
    if unknown:
        raise ValueError(f"Unknown chart dimensions: {', '.join(sorted(unknown))}.")
    if len(dimensions) > 3:
        raise ValueError("A chart may use at most three dimensions.")
    limit = spec.get("limit", 100)
    if not isinstance(limit, int) or not 1 <= limit <= MAX_ROWS:
        raise ValueError(f"Chart limit must be an integer from 1 to {MAX_ROWS}.")
    normalized_x = _normalize_field(x_field)
    if granularity and normalized_x is None:
        normalized_x = "event_date"
    y_field = spec.get("y", metric)
    if isinstance(y_field, list):
        y_field = [str(item) for item in y_field]
    result = {
        "type": chart_type,
        "metric": metric,
        "metrics": requested_metrics,
        "dimensions": dimensions,
        "granularity": granularity,
        "comparison": comparison,
        "start_date": spec.get("start_date"),
        "end_date": spec.get("end_date"),
        "limit": limit,
        "title": str(spec.get("title", ""))[:200],
        "x": normalized_x,
        "y": y_field,
        "color": "series"
        if color_field == "metric" and len(requested_metrics) > 1
        else _normalize_field(color_field),
    }
    fields = set(dimensions) | set(requested_metrics)
    if len(requested_metrics) > 1:
        fields.add("series")
    if granularity:
        fields.add("event_date")
    if comparison:
        fields.add("comparison_period")
    temporal_x_is_valid = bool(granularity and result["x"] == "event_date")
    for key in ("x", "y", "color"):
        values = result[key] if isinstance(result[key], list) else [result[key]]
        invalid = [
            value for value in values if value is not None and value not in fields
        ]
        if invalid and not (key == "x" and temporal_x_is_valid):
            raise ValueError(
                f"Chart field {key!r} is not present in the query: {invalid}."
            )
    return result


def adapt_spec_to_data(
    spec: dict[str, Any], data: list[dict[str, Any]]
) -> tuple[dict[str, Any], str | None]:
    """Adapt visual-only fields to the columns actually returned by MetricFlow."""
    frame = pd.DataFrame(data)
    columns = list(frame.columns)
    numeric_columns = list(frame.select_dtypes(include="number").columns)
    dimensions = [dimension for dimension in spec["dimensions"] if dimension in columns]
    adapted = dict(spec)
    changes: list[str] = []

    x = adapted.get("x")
    if x not in columns:
        adapted["x"] = (
            dimensions[0] if dimensions else (columns[0] if columns else None)
        )
        changes.append("x was replaced with an available field")
    y = adapted.get("y")
    y_values = y if isinstance(y, list) else [y]
    valid_y_values = [value for value in y_values if value in columns]
    if not valid_y_values:
        adapted["y"] = (
            spec["metric"]
            if spec["metric"] in columns
            else (numeric_columns[0] if numeric_columns else None)
        )
        changes.append("y was replaced with an available numeric field")
    elif isinstance(y, list):
        adapted["y"] = valid_y_values
    color = adapted.get("color")
    synthetic_series = color == "series" and isinstance(y, list) and len(y) > 1
    if color not in columns and not synthetic_series:
        adapted["color"] = None
        if color:
            changes.append("color was removed because it is not in the result")

    if adapted["type"] == "line" and adapted.get("x") not in columns:
        adapted["type"] = "bar"
        changes.append("line was replaced with bar because no x field is available")
    if not adapted.get("x") or not adapted.get("y"):
        raise ValueError("The query returned no usable fields for a chart.")
    return adapted, "; ".join(changes) if changes else None


def render_spec(spec: dict[str, Any], data: list[dict[str, Any]]) -> go.Figure:
    """Render a validated chart specification with Plotly Express."""
    frame = pd.DataFrame(data)
    y_fields = spec["y"] if isinstance(spec["y"], list) else [spec["y"]]
    if len(y_fields) > 1:
        id_fields = [field for field in frame.columns if field not in y_fields]
        frame = frame.melt(
            id_vars=id_fields,
            value_vars=[field for field in y_fields if field in frame.columns],
            var_name="series",
            value_name="value",
        )
        spec = {**spec, "y": "value", "color": spec.get("color") or "series"}
    chart_type = spec["type"]
    x = spec["x"] or (spec["dimensions"][0] if spec["dimensions"] else spec["y"])
    y = spec["y"] or spec["metric"]
    color = spec["color"]
    title = (
        spec["title"]
        or f"{y.replace('_', ' ').title()} by {x.replace('_', ' ').title()}"
    )
    renderers = {
        "bar": lambda: px.bar(frame, x=x, y=y, color=color, title=title),
        "line": lambda: px.line(
            frame, x=x, y=y, color=color, markers=True, title=title
        ),
        "area": lambda: px.area(frame, x=x, y=y, color=color, title=title),
        "scatter": lambda: px.scatter(frame, x=x, y=y, color=color, title=title),
        "pie": lambda: px.pie(frame, names=x, values=y, title=title),
        "histogram": lambda: px.histogram(frame, x=x, y=y, color=color, title=title),
        "box": lambda: px.box(frame, x=x, y=y, color=color, title=title),
    }
    if chart_type in renderers:
        return renderers[chart_type]()
    pivot = frame.pivot_table(index=x, columns=color or y, values=y, aggfunc="sum")
    return go.Figure(
        data=go.Heatmap(z=pivot.values, x=list(pivot.columns), y=list(pivot.index))
    )
