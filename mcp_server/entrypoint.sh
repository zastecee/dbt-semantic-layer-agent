#!/usr/bin/env bash
set -euo pipefail

export DBT_PROFILES_DIR=/app/.dbt

echo "Building dbt models and the MetricFlow semantic manifest..."
(cd /app/dbt_project/roaming_analytics && dbt run)

exec python -m mcp_server.app
