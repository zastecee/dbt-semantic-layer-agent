"""Streamlit dashboard: National Roaming AI Analytics.

Run with:
    streamlit run dashboard/streamlit_app.py
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path

import pandas as pd
import streamlit as st
import yaml

# Allow running via `streamlit run dashboard/streamlit_app.py` from the repo root
# without having the project installed as a package.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from adk_agent.chart_spec import (  # noqa: E402
    adapt_spec_to_data,
    render_spec,
    validate_spec,
)
from adk_agent.tools.dashboard import (  # noqa: E402
    build_dashboard_summary,
)
from mcp_server.semantic_layer import get_client  # noqa: E402

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s | %(levelname)s | %(name)s | %(message)s"
)
logger = logging.getLogger(__name__)

st.set_page_config(page_title="National Roaming AI Analytics", layout="wide")


@st.cache_resource
def _semantic_layer_client():
    return get_client()


@st.cache_resource
def _agent_runner():
    from adk_agent.agent import create_runner

    return create_runner()


def render_header() -> None:
    st.title("National Roaming AI Analytics")
    st.caption(
        "Ask business questions in plain language and get metrics, charts and "
        "explanations powered by the dbt Semantic Layer, MCP and Google ADK."
    )


def render_metrics_summary() -> None:
    st.header("Metrics Summary")
    col_start, col_end = st.columns(2)
    default_end = pd.Timestamp.today().date()
    default_start = default_end - pd.Timedelta(days=180)
    start_date = col_start.date_input(
        "Start date", value=default_start, key="summary_start"
    )
    end_date = col_end.date_input("End date", value=default_end, key="summary_end")

    try:
        summary = build_dashboard_summary(
            start_date=str(start_date), end_date=str(end_date)
        )
    except Exception as exc:  # noqa: BLE001
        st.error(f"Failed to load metrics summary: {exc}")
        return

    metric_cols = st.columns(len(summary["metrics"]) or 1)
    for col, (metric_name, payload) in zip(metric_cols, summary["metrics"].items()):
        value = payload["value"] or 0
        if metric_name == "total_revenue":
            display_value = f"${value:,.2f}"
        else:
            display_value = f"{value:,.2f}"
        col.metric(payload["label"], display_value)


def render_charts() -> None:
    st.header("Charts")
    client = _semantic_layer_client()
    config_path = Path(__file__).with_name("charts.yml")
    chart_configs = yaml.safe_load(config_path.read_text(encoding="utf-8")).get(
        "charts", []
    )
    for chart_config in chart_configs:
        spec = validate_spec(chart_config, client)
        end_date = pd.Timestamp.today().date()
        start_days_ago = chart_config.get("start_days_ago")
        start_date = (
            end_date - pd.Timedelta(days=start_days_ago)
            if start_days_ago is not None
            else None
        )
        if spec.get("granularity"):
            result = client.get_time_series(
                ",".join(spec["metrics"]),
                granularity=spec["granularity"],
                dimensions=[d for d in spec["dimensions"] if d != "event_date"],
                start_date=str(start_date) if start_date else None,
                end_date=str(end_date) if start_date else None,
            )
        else:
            result = client.query_metric(
                ",".join(spec["metrics"]),
                dimensions=spec["dimensions"],
                start_date=str(start_date) if start_date else None,
                end_date=str(end_date) if start_date else None,
                limit=spec["limit"],
            )
        st.subheader(spec["title"])
        if result["data"]:
            adapted_spec, adaptation_message = adapt_spec_to_data(spec, result["data"])
            if adaptation_message:
                st.info(
                    f"Chart adjusted to match the returned data: {adaptation_message}."
                )
            st.plotly_chart(
                render_spec(adapted_spec, result["data"]),
                use_container_width=True,
            )
        else:
            st.info("No data available for this chart.")


def render_query_results() -> None:
    st.header("Query Results")
    client = _semantic_layer_client()

    metrics = client.list_metrics()
    dimensions = client.list_dimensions()

    metric_names = [m["name"] for m in metrics]
    dimension_names = [d["name"] for d in dimensions]

    col1, col2, col3 = st.columns(3)
    metric_name = col1.selectbox("Metric", metric_names, key="qr_metric")
    selected_dimensions = col2.multiselect(
        "Group by", dimension_names, key="qr_dimensions"
    )
    limit = col3.number_input(
        "Row limit", min_value=1, max_value=1000, value=100, key="qr_limit"
    )

    col4, col5 = st.columns(2)
    start_date = col4.date_input("Start date", value=None, key="qr_start")
    end_date = col5.date_input("End date", value=None, key="qr_end")

    if st.button("Run query", key="qr_run"):
        try:
            result = client.query_metric(
                metric_name,
                dimensions=selected_dimensions,
                start_date=str(start_date) if start_date else None,
                end_date=str(end_date) if end_date else None,
                limit=int(limit),
            )
            st.dataframe(pd.DataFrame(result["data"]), use_container_width=True)
            with st.expander("SQL generated by MetricFlow"):
                preview = client.metric_sql_preview(metric_name, selected_dimensions)
                st.code(preview["sql"], language="sql")
        except Exception as exc:  # noqa: BLE001
            st.error(f"Query failed: {exc}")


def render_natural_language_question() -> None:
    st.header("Natural Language Question")
    st.caption(
        'Examples: "Show revenue by country for the last 6 months", '
        '"Show top 10 roaming partners by revenue", '
        '"Compare current month revenue with previous month".'
    )
    question = st.text_input("Ask NationalRoamingAnalyst a question", key="nl_question")
    if st.button("Ask", key="nl_ask") and question:
        with st.spinner("Analyzing..."):
            try:
                runner = _agent_runner()
                result = runner.ask_result(question)
                answer = str(result["answer"])
                if answer:
                    st.markdown(answer)
                else:
                    st.warning(
                        "The agent finished without returning text. "
                        "Please try the question again."
                    )
                try:
                    chart_spec = result.get("chart_spec")
                    if chart_spec:
                        _render_chart_spec(chart_spec)
                    else:
                        st.info("No chart was requested for this question.")
                except Exception as exc:  # noqa: BLE001
                    logger.exception("Question chart rendering failed")
                    st.warning(
                        f"The answer was returned, but the chart could not be rendered: {exc}"
                    )
            except Exception as exc:  # noqa: BLE001
                logger.exception("Agent invocation failed")
                st.error(
                    "The AI agent could not be reached. Make sure `google-adk`, "
                    "`litellm` and `boto3` are installed and that `AWS_REGION`, "
                    f"`AWS_PROFILE` and `BEDROCK_MODEL_ID` are set. Details: {exc}"
                )


def _render_chart_spec(raw_spec: object) -> None:
    """Validate, query, display data, and render an ADK chart specification."""
    client = _semantic_layer_client()
    spec = validate_spec(raw_spec, client)
    if spec.get("granularity"):
        query = client.get_time_series(
            ",".join(spec["metrics"]),
            granularity=spec["granularity"],
            dimensions=[
                dimension
                for dimension in spec["dimensions"]
                if dimension != "event_date"
            ],
            start_date=spec["start_date"],
            end_date=spec["end_date"],
        )
    else:
        query = client.query_metric(
            ",".join(spec["metrics"]),
            dimensions=spec["dimensions"],
            start_date=spec["start_date"],
            end_date=spec["end_date"],
            limit=spec["limit"],
        )
    if not query["data"]:
        st.info("No data is available for the chart period.")
        return
    adapted_spec, adaptation_message = adapt_spec_to_data(spec, query["data"])
    if adaptation_message:
        st.info(f"Chart adjusted to match the returned data: {adaptation_message}.")
    st.dataframe(pd.DataFrame(query["data"]), use_container_width=True)
    st.plotly_chart(
        render_spec(adapted_spec, query["data"]),
        use_container_width=True,
    )


def main() -> None:
    render_header()
    render_metrics_summary()
    st.divider()
    render_charts()
    st.divider()
    render_query_results()


if __name__ == "__main__":
    main()
