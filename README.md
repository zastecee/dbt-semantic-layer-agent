# dbt-agent — National Roaming AI Analytics

An AI Analytics Agent that lets business users ask questions like:

- *"Show revenue by country for the last 6 months"*
- *"Show top 10 roaming partners by revenue"*
- *"Compare current month revenue with previous month"*

...without writing a single line of SQL. The agent discovers metrics and
dimensions from a **dbt Semantic Layer powered by MetricFlow**, exposes them
through an **MCP** (Model Context Protocol) server, is orchestrated by a
**Google ADK** agent, renders charts with **Plotly**, and is presented
through a **Streamlit** dashboard — all backed by **PostgreSQL**.

---

## Architecture

```mermaid
flowchart LR
    subgraph Warehouse
        PG[(PostgreSQL 16<br/>analytics DB)]
    end

    subgraph dbt["dbt Project (roaming_analytics)"]
        STG[stg_national_roaming.sql]
        FCT[fct_roaming.sql]
        SEM[roaming_semantic.yml]
        MET[metrics.yml]
        STG --> FCT --> SEM --> MET
    end

    subgraph MF["MetricFlow (mf CLI)"]
        ENGINE[MetricFlow query engine]
    end

    subgraph MCP["MCP Server (FastMCP)"]
        SLC[SemanticLayerClient]
        T1[health_check]
        T2[list_metrics]
        T3[list_dimensions]
        T4[explain_metric]
        T5[query_metric]
        T6[get_time_series]
        T7[top_n]
        T8[metric_sql_preview]
        SLC --> T1 & T2 & T3 & T4 & T5 & T6 & T7 & T8
    end

    subgraph ADK["Google ADK Agent"]
        AGENT[NationalRoamingAnalyst]
        CHARTS[Plotly chart tools]
    end

    subgraph UI["Streamlit Dashboard"]
        DASH[National Roaming AI Analytics]
    end

    USER([Business User]) -->|Natural language question| DASH
    DASH --> AGENT
    AGENT -->|calls tools| T2
    AGENT --> T3
    AGENT --> T4
    AGENT --> T5
    AGENT --> T6
    AGENT --> T7
    AGENT --> T8
    AGENT --> CHARTS
    SLC -->|subprocess: mf query / mf list / mf health-checks| ENGINE
    ENGINE -->|generated SQL| PG
    MET -.compiled into semantic_manifest.json for.-> ENGINE
    SEM -.compiled into semantic_manifest.json for.-> ENGINE
    FCT -->|materialized table| PG
    CHARTS -->|Plotly figures| DASH
```

---

## Project structure

```
dbt-agent/
├── .dbt/profiles.yml               # dbt connection profile (Postgres, env-var driven)
├── docker-compose.yml              # postgres + mcp_server + dashboard
├── dbt_project/roaming_analytics/  # dbt project
│   ├── dbt_project.yml
│   ├── models/
│   │   ├── staging/                # stg_national_roaming.sql + sources.yml
│   │   ├── marts/                  # fct_roaming.sql
│   │   ├── semantic_models/        # roaming_semantic.yml
│   │   ├── metrics/                # metrics.yml
│   │   └── metricflow_time_spine.sql/.yml  # required by MetricFlow
│   └── seeds/
├── mcp_server/                     # FastMCP server, backed by MetricFlow
│   ├── app.py
│   ├── semantic_layer.py           # SemanticLayerClient (wraps the `mf` CLI)
│   ├── entrypoint.sh               # runs `dbt run` then starts the server (Docker)
│   ├── requirements.txt
│   └── tools/                      # health_check, list_metrics, list_dimensions,
│                                    # explain_metric, query_metric, get_time_series,
│                                    # top_n, metric_sql_preview
├── adk_agent/                      # Google ADK agent
│   ├── agent.py                    # NationalRoamingAnalyst
│   ├── requirements.txt
│   ├── prompts/analyst_prompt.txt
│   └── tools/                      # charts.py, dashboard.py
├── dashboard/                      # Streamlit UI
│   ├── streamlit_app.py
│   └── entrypoint.sh               # starts Streamlit after the MCP service builds dbt
├── sample_data/roaming_data.csv     # sample dataset (420 rows)
└── README.md
```

---

## Prerequisites

- Docker & Docker Compose
- Python 3.11
- AWS credentials with access to Amazon Bedrock (for the ADK agent), configured
  via `AWS_REGION` + `BEDROCK_MODEL_ID`, plus either `AWS_PROFILE` (a named
  CLI profile) or `AWS_ACCESS_KEY_ID`/`AWS_SECRET_ACCESS_KEY`/`AWS_SESSION_TOKEN`
  (explicit, e.g. temporary STS credentials). Copy `.env.example` to `.env` and
  fill in whichever option applies. The dashboard and Semantic Layer views
  still work without it — only the "Natural Language Question" box requires it.

---

## Setup instructions

### 1. Clone and create a virtual environment

```bash
python3 -m venv .venv
source .venv/bin/activate
```

### 2. Install dependencies

```bash
pip install -r mcp_server/requirements.txt   # includes dbt-core, dbt-postgres, dbt-metricflow
pip install -r adk_agent/requirements.txt
pip install -r dashboard/requirements.txt
```

This installs the `mf` CLI (from `dbt-metricflow`), which the
`SemanticLayerClient` shells out to for every metric operation.

### 3. Point dbt to the bundled profile

```bash
export DBT_PROFILES_DIR=$(pwd)/.dbt
```

### 4. Make the repo root importable

Both `mcp_server` and `adk_agent` use absolute imports (`from mcp_server...`,
`from adk_agent...`), so run all Python commands from the repository root, or:

```bash
export PYTHONPATH=$(pwd)
```

---

## Docker commands

Start Postgres (auto-seeded with `sample_data/roaming_data.csv`), the MCP
server and the dashboard:

```bash
docker compose up -d postgres
docker compose up -d --build mcp_server dashboard
```

The `mcp_server` runs `dbt run` on container startup to build `fct_roaming` and
the MetricFlow semantic manifest. The dashboard waits for the MCP service to
be healthy before starting, so the two services never run dbt concurrently.

Useful commands:

```bash
docker compose ps                     # check container health
docker compose logs -f postgres       # tail Postgres logs
docker compose logs -f mcp_server     # tail MCP server logs (includes the dbt run output)
docker compose down                   # stop everything
docker compose down -v                # stop and wipe the Postgres volume (re-seeds on next start)
```

> The Postgres container only runs `sample_data/init.sql` (which creates
> `public.national_roaming` and loads the CSV) on a **fresh volume**. Run
> `docker compose down -v` before `up` if you change the sample data.

---

## dbt commands

Run from `dbt_project/roaming_analytics`:

```bash
cd dbt_project/roaming_analytics

dbt debug     # verify the Postgres connection
dbt deps      # (no-op, no external packages required)
dbt parse     # validate models + semantic models/metrics, build semantic_manifest.json
dbt compile   # compile SQL without executing
dbt run       # build stg_national_roaming (view), fct_roaming (table) and the time spine
dbt test      # run schema tests (not_null, unique)
```

`dbt run`/`dbt parse` must succeed at least once before the MCP server or
dashboard can start, since MetricFlow reads `target/semantic_manifest.json`.

---

## MetricFlow (mf) commands

The `SemanticLayerClient` shells out to these same commands; running them
directly is useful for debugging:

```bash
cd dbt_project/roaming_analytics

mf health-checks
mf list metrics --show-all-dimensions
mf list dimensions --metrics total_revenue
mf query --metrics total_revenue --group-by roaming_event__country --csv /tmp/out.csv
mf query --metrics total_revenue --group-by roaming_event__country --explain --show-dataflow-plan --quiet
```

---

## MCP server commands

```bash
# Local (venv):
python -m mcp_server.app        # starts on http://localhost:8000 (streamable-http)

# Docker:
docker compose up -d --build mcp_server
```

Environment variables (all optional, defaults shown):

| Variable            | Default     |
|---------------------|-------------|
| `POSTGRES_HOST`     | `localhost` |
| `POSTGRES_PORT`     | `5432`      |
| `POSTGRES_DB`       | `analytics` |
| `POSTGRES_USER`     | `admin`     |
| `POSTGRES_PASSWORD` | `admin`     |
| `MCP_SERVER_HOST`   | `0.0.0.0`   |
| `MCP_SERVER_PORT`   | `8000`      |

The server exposes 8 tools, all backed by MetricFlow and returning the
standard `{status, data, error}` JSON envelope:
`health_check`, `list_metrics`, `list_dimensions`, `explain_metric`,
`query_metric`, `get_time_series`, `top_n`, `metric_sql_preview`.

### Connect an external MCP client

The repository includes `.mcp.json` for Claude Code. Start the MCP service:

```bash
docker compose up -d postgres
docker compose up -d --build mcp_server
```

In Claude Code, use `/mcp` to verify the `roaming-analytics` server and its
tools. The configured endpoint is `http://localhost:8000/mcp`.

For Claude Desktop, configure `claude_desktop_config.json` with a local HTTP
bridge:

```json
{
    "mcpServers": {
        "roaming-analytics": {
            "command": "npx",
            "args": ["-y", "mcp-remote", "http://localhost:8000/mcp"]
        }
    }
}
```

For local inspection, start the MCP Inspector and use the same endpoint:

```bash
npx @modelcontextprotocol/inspector
```

This endpoint is local-only. Remote access requires HTTPS, authentication, and
a read-only warehouse credential before exposing the MCP server publicly.

The semantic layer also defines reusable `total_events`, average metrics,
`revenue_per_event`, `usage_per_event`, `revenue_mtd`, and `revenue_ytd`
metrics. MetricFlow validates these definitions when `dbt parse` or `dbt run`
builds the semantic manifest.

---

## Google ADK agent commands

The agent uses AWS Bedrock (via LiteLLM) as its model backend. Copy
`.env.example` to `.env` and set `AWS_REGION` + `BEDROCK_MODEL_ID`, plus
either `AWS_PROFILE` (named CLI profile) or `AWS_ACCESS_KEY_ID` /
`AWS_SECRET_ACCESS_KEY` / `AWS_SESSION_TOKEN` (explicit credentials). The
agent loads `.env` automatically via `python-dotenv`; ensure the credentials
used have `bedrock:InvokeModel` permissions.

```bash
cp .env.example .env   # then edit AWS_REGION / BEDROCK_MODEL_ID and your AWS credentials

# Interactive CLI chat with the agent:
adk run adk_agent

# Or programmatically:
python -c "from adk_agent.agent import create_runner; print(create_runner().ask('Show revenue by country for the last 6 months'))"
```

---

## Streamlit dashboard commands

```bash
streamlit run dashboard/streamlit_app.py
# open http://localhost:8501
```

Dashboard sections:

1. **Metrics Summary** — headline totals for revenue, usage and duration,
   plus a month-over-month revenue comparison.
2. **Charts** — revenue by country, top 10 roaming partners, revenue trend
   over time.
3. **Query Results** — pick any metric/dimensions/date range, inspect the
   raw rows and preview the SQL MetricFlow generated for that query.

The Streamlit navigation also includes **Ask the Analyst**, a dedicated
ChatGPT-style conversation page with chat history, tables, and generated charts.

---

## Testing examples

Ask the dashboard (or `adk run adk_agent`) any of:

```
Show revenue by country for the last 6 months
Show top 10 roaming partners by revenue
Compare current month revenue with previous month
What is the total data usage in Kenya this year?
Which country had the highest average call duration?
```

Calling MCP tools directly (Python REPL, from the repo root):

```python
from mcp_server.tools.list_metrics import list_metrics
from mcp_server.tools.query_metric import query_metric
from mcp_server.tools.top_n import top_n

print(list_metrics())
print(query_metric("total_revenue", dimensions=["country"], limit=10))
print(top_n("total_revenue", dimension="partner_network", limit=10))
```

---

## Troubleshooting

| Symptom | Fix |
|---|---|
| `dbt debug` fails to connect | Ensure `docker compose up -d postgres` is running and `DBT_PROFILES_DIR` points to `./.dbt`. |
| `relation "public.national_roaming" does not exist` | The Postgres volume was created before the seed script existed. Run `docker compose down -v && docker compose up -d postgres`. |
| `MetricFlow semantic manifest not found` | Run `dbt run` (or `dbt parse`) inside `dbt_project/roaming_analytics` at least once — this generates `target/semantic_manifest.json`. |
| `The mf CLI was not found` | Install `dbt-metricflow` (`pip install -r mcp_server/requirements.txt`). |
| `The semantic layer requires a time spine model` | Ensure `models/metricflow_time_spine.sql` and its `.yml` config exist, then re-run `dbt run`. |
| `ModuleNotFoundError: mcp_server` / `adk_agent` | Run commands from the repo root, or `export PYTHONPATH=$(pwd)`. |
| Natural Language Question box errors out | Ensure `litellm`/`boto3` are installed, `.env` (or the environment) sets `AWS_REGION`, `BEDROCK_MODEL_ID`, and either `AWS_PROFILE` or `AWS_ACCESS_KEY_ID`/`AWS_SECRET_ACCESS_KEY`/`AWS_SESSION_TOKEN`, and the credentials can call `bedrock:InvokeModel`. |
| `NoCredentialsError` / `Unable to locate credentials` | Run `aws configure --profile <name>` locally, or check that `AWS_PROFILE` matches an existing profile in `~/.aws/credentials`, or set `AWS_ACCESS_KEY_ID`/`AWS_SECRET_ACCESS_KEY`/`AWS_SESSION_TOKEN` directly in `.env`. In Docker, ensure `~/.aws` is mounted into the `dashboard` container when using `AWS_PROFILE`. |
| Port `5432`/`8000`/`8501` already in use | Stop the conflicting local service or change the host port mapping in `docker-compose.yml`. |
| Streamlit shows stale metric/dimension lists after editing `metrics.yml` | Re-run `dbt run` (to refresh the semantic manifest), then restart Streamlit/MCP server. |
