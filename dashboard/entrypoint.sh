#!/usr/bin/env bash
set -euo pipefail

export DBT_PROFILES_DIR=/app/.dbt

exec streamlit run dashboard/streamlit_app.py --server.address=0.0.0.0 --server.port=8501
