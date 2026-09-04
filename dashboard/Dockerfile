FROM python:3.11-slim

WORKDIR /app

COPY dashboard/requirements.txt ./dashboard/requirements.txt
RUN --mount=type=cache,target=/root/.cache/pip \
    pip install -r dashboard/requirements.txt

COPY dashboard ./dashboard
COPY adk_agent ./adk_agent
COPY mcp_server ./mcp_server
COPY dbt_project ./dbt_project
COPY .dbt ./.dbt

RUN chmod +x dashboard/entrypoint.sh

ENV PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app \
    DBT_PROFILES_DIR=/app/.dbt

EXPOSE 8501

CMD ["./dashboard/entrypoint.sh"]
