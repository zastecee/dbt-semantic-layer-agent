FROM python:3.11-slim

WORKDIR /app

COPY mcp_server/requirements.txt ./mcp_server/requirements.txt
RUN --mount=type=cache,target=/root/.cache/pip \
    pip install -r mcp_server/requirements.txt

COPY mcp_server ./mcp_server
COPY dbt_project ./dbt_project
COPY .dbt ./.dbt

RUN chmod +x mcp_server/entrypoint.sh

ENV PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app \
    DBT_PROFILES_DIR=/app/.dbt

EXPOSE 8000

CMD ["./mcp_server/entrypoint.sh"]
