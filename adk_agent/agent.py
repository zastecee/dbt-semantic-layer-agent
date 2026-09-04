"""Google ADK agent definition for the National Roaming Analyst.

Defines the ``NationalRoamingAnalyst`` ADK agent, which discovers dbt
Semantic Layer metrics/dimensions via the project's MCP tools, chooses the
right metric and dimensions for a natural-language business question,
executes it, builds chart data, and returns a business-friendly explanation.
"""

from __future__ import annotations

import asyncio
import logging
import os
import threading
from datetime import date
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv
from google.adk.agents import LlmAgent
from google.adk.models.lite_llm import LiteLlm
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.genai import types

from adk_agent.chart_spec import parse_response
from adk_agent.tools.dashboard import (
    build_dashboard_summary,
)
from mcp_server.tools.explain_metric import explain_metric
from mcp_server.tools.get_time_series import get_time_series
from mcp_server.tools.health_check import health_check
from mcp_server.tools.list_dimensions import list_dimensions
from mcp_server.tools.list_metrics import list_metrics
from mcp_server.tools.metric_sql_preview import metric_sql_preview
from mcp_server.tools.query_metric import query_metric
from mcp_server.tools.top_n import top_n

load_dotenv()

logger = logging.getLogger(__name__)

AGENT_NAME = "NationalRoamingAnalyst"
# Uses AWS Bedrock (via LiteLLM) as the model backend. Requires AWS_REGION,
# BEDROCK_MODEL_ID, and either AWS_PROFILE or
# AWS_ACCESS_KEY_ID/AWS_SECRET_ACCESS_KEY/AWS_SESSION_TOKEN to be set (e.g. in a .env file).
MODEL_NAME = f"bedrock/converse/{os.getenv('BEDROCK_MODEL_ID')}"
APP_NAME = "dbt-agent"
PROMPT_PATH = Path(__file__).resolve().parent / "prompts" / "analyst_prompt.txt"

if not os.getenv("BEDROCK_MODEL_ID"):
    logger.warning("BEDROCK_MODEL_ID is not set; the agent will fail to call Bedrock.")


def _load_system_prompt() -> str:
    """Load the agent's system prompt from prompts/analyst_prompt.txt."""
    prompt = PROMPT_PATH.read_text(encoding="utf-8")
    return f"{prompt}\n\nThe current date is {date.today().isoformat()}."


root_agent = LlmAgent(
    name=AGENT_NAME,
    model=LiteLlm(model=MODEL_NAME),
    description=(
        "Business analyst agent that answers natural-language questions about "
        "national roaming revenue and usage using the dbt Semantic Layer."
    ),
    instruction=_load_system_prompt(),
    tools=[
        health_check,
        list_metrics,
        list_dimensions,
        explain_metric,
        query_metric,
        get_time_series,
        top_n,
        metric_sql_preview,
        build_dashboard_summary,
    ],
)

# Alias expected by some ADK CLI tooling (`adk run adk_agent`).
agent = root_agent


class NationalRoamingAnalystRunner:
    """Synchronous-friendly wrapper around the ADK ``Runner`` for use from Streamlit."""

    def __init__(self, user_id: str = "dashboard-user") -> None:
        self._user_id = user_id
        self._session_service = InMemorySessionService()
        self._runner = Runner(
            agent=root_agent, app_name=APP_NAME, session_service=self._session_service
        )
        self._session_id: Optional[str] = None
        self._loop = asyncio.new_event_loop()
        self._loop_thread = threading.Thread(
            target=self._loop.run_forever,
            name="adk-event-loop",
            daemon=True,
        )
        self._loop_thread.start()

    async def _ensure_session(self) -> str:
        if self._session_id is None:
            session = await self._session_service.create_session(
                app_name=APP_NAME, user_id=self._user_id
            )
            self._session_id = session.id
        return self._session_id

    async def ask_async(self, question: str) -> str:
        """Send a natural-language question to the agent and return its final text answer."""
        normalized_question = question.strip().lower().rstrip("!?.,")
        if normalized_question in {
            "ola",
            "olá",
            "hi",
            "hello",
            "bom dia",
            "boa tarde",
            "boa noite",
        }:
            return (
                "Olá! Posso ajudar a analisar receita, utilização de dados e duração "
                "de chamadas. Por exemplo: mostre a receita por país nos últimos 6 meses."
            )
        session_id = await self._ensure_session()
        message = types.Content(role="user", parts=[types.Part(text=question)])
        final_text = ""
        last_text = ""
        async for event in self._runner.run_async(
            user_id=self._user_id, session_id=session_id, new_message=message
        ):
            if event.content and event.content.parts:
                event_text = "".join(
                    part.text or "" for part in event.content.parts
                ).strip()
                if event_text:
                    last_text = event_text
                if event.is_final_response() and event_text:
                    final_text = event_text
        return final_text or last_text

    def ask(self, question: str) -> str:
        """Synchronous helper around :meth:`ask_async`, safe to call from Streamlit callbacks."""
        future = asyncio.run_coroutine_threadsafe(self.ask_async(question), self._loop)
        return future.result()

    def ask_result(self, question: str) -> dict[str, object]:
        """Return the answer text and optional declarative chart specification."""
        raw_response = self.ask(question)
        answer, chart_spec = parse_response(raw_response)
        return {"answer": answer, "chart_spec": chart_spec}


def create_runner() -> NationalRoamingAnalystRunner:
    """Factory used by the Streamlit dashboard to obtain a fresh agent runner."""
    return NationalRoamingAnalystRunner()
