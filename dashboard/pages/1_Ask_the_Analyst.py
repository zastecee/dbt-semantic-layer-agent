"""Conversational analytics page for the National Roaming Analyst."""

from __future__ import annotations

import logging
import sys
from pathlib import Path

import pandas as pd
import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from adk_agent.chart_spec import (  # noqa: E402
    adapt_spec_to_data,
    render_spec,
    validate_spec,
)
from mcp_server.semantic_layer import get_client  # noqa: E402

logger = logging.getLogger(__name__)

st.set_page_config(page_title="Ask the Analyst", page_icon="", layout="wide")


@st.cache_resource
def _agent_runner():
    from adk_agent.agent import create_runner

    return create_runner()


@st.cache_resource
def _semantic_layer_client():
    return get_client()


def _render_chart(chart_spec: object, progress: object | None = None) -> None:
    client = _semantic_layer_client()
    if progress:
        progress.write("Validating chart specification")
    spec = validate_spec(chart_spec, client)
    metrics = ",".join(spec["metrics"])
    if progress:
        progress.write("Querying the Semantic Layer")
    if spec.get("granularity"):
        result = client.get_time_series(
            metrics,
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
        result = client.query_metric(
            metrics,
            dimensions=spec["dimensions"],
            start_date=spec["start_date"],
            end_date=spec["end_date"],
            limit=spec["limit"],
        )
    if not result["data"]:
        st.info("No data is available for this question.")
        return
    adapted_spec, message = adapt_spec_to_data(spec, result["data"])
    if message:
        st.caption(f"Chart adjusted to match the returned data: {message}.")
    st.dataframe(pd.DataFrame(result["data"]), use_container_width=True)
    if progress:
        progress.write("Rendering visualization")
    st.plotly_chart(render_spec(adapted_spec, result["data"]), use_container_width=True)


def _display_result(result: dict[str, object]) -> None:
    answer = str(result.get("answer") or "The analyst did not return a text response.")
    st.markdown(answer)
    chart_spec = result.get("chart_spec")
    if chart_spec:
        try:
            _render_chart(chart_spec)
        except Exception as exc:  # noqa: BLE001
            logger.exception("Chat chart rendering failed")
            st.warning(
                f"The answer was returned, but the chart could not be rendered: {exc}"
            )


st.title("Ask the Analyst")
st.caption(
    "Ask questions about roaming revenue, data usage, duration, trends, and comparisons."
)

if "chat_messages" not in st.session_state:
    st.session_state.chat_messages = [
        {
            "role": "assistant",
            "content": "Hello. I can analyze roaming revenue, data usage, duration, and trends.",
        }
    ]

with st.sidebar:
    st.header("Conversation")
    if st.button("Clear chat"):
        st.session_state.chat_messages = []
        st.rerun()

for message in st.session_state.chat_messages:
    with st.chat_message(message["role"]):
        if message["role"] == "assistant" and message.get("result"):
            _display_result(message["result"])
        else:
            st.markdown(message["content"])

question = st.chat_input("Ask a question about roaming analytics")
if question:
    st.session_state.chat_messages.append({"role": "user", "content": question})
    with st.chat_message("user"):
        st.markdown(question)
    with st.chat_message("assistant"):
        with st.status("Analyzing your question...", expanded=True) as progress:
            progress.write("Sending request to NationalRoamingAnalyst")
            try:
                result = _agent_runner().ask_result(question)
                progress.write("Received response from the analyst")
                answer = str(
                    result.get("answer")
                    or "The analyst did not return a text response."
                )
                st.markdown(answer)
                chart_spec = result.get("chart_spec")
                if chart_spec:
                    try:
                        _render_chart(chart_spec, progress)
                    except Exception as exc:  # noqa: BLE001
                        logger.exception("Chat chart rendering failed")
                        progress.write(f"Chart could not be rendered: {exc}")
                        st.warning(
                            f"The answer was returned, but the chart could not be rendered: {exc}"
                        )
                else:
                    progress.write("No visualization was requested")
                progress.update(
                    label="Analysis complete", state="complete", expanded=True
                )
                st.session_state.chat_messages.append(
                    {"role": "assistant", "result": result}
                )
            except Exception as exc:  # noqa: BLE001
                logger.exception("Agent invocation failed")
                message = f"The analyst could not answer this question: {exc}"
                progress.update(label="Analysis failed", state="error", expanded=True)
                st.error(message)
                st.session_state.chat_messages.append(
                    {"role": "assistant", "content": message}
                )
