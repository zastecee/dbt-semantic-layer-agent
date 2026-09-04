"""Semantic layer client that centralizes execution of metric queries.

Wraps the MetricFlow CLI (``mf``, provided by the ``dbt-metricflow`` package)
so that every metric discovery/query operation is executed by MetricFlow
against the semantic manifest produced by `dbt run`/`dbt parse` for the
``roaming_analytics`` dbt project. No SQL is built by hand: MetricFlow
compiles and executes (or explains) the SQL, and this client only shapes the
CLI's output into structured, JSON-serializable Python objects.
"""

from __future__ import annotations

import logging
import os
import subprocess
import tempfile
from datetime import date, datetime
from pathlib import Path
from typing import Any, Optional

import pandas as pd
import yaml

logger = logging.getLogger(__name__)
REPO_ROOT = Path(__file__).resolve().parents[1]
DBT_PROJECT_DIR = REPO_ROOT / "dbt_project" / "roaming_analytics"
DBT_PROFILES_DIR = REPO_ROOT / ".dbt"
METRICS_PATH = DBT_PROJECT_DIR / "models" / "metrics" / "metrics.yml"
ENTITY_PREFIX = "roaming_event__"
TIME_DIMENSION = "event_date"
DEFAULT_COMMAND_TIMEOUT = 60
VALID_GRANULARITIES = {"day", "week", "month", "quarter", "year"}


class SemanticLayerConfigError(RuntimeError):
    """Raised when the dbt/MetricFlow project is not correctly set up."""


class MetricFlowCommandError(RuntimeError):
    """Raised when MetricFlow cannot execute a command."""


class SemanticLayerClient:
    """Execute discovery and queries through the MetricFlow CLI."""

    def __init__(
        self,
        project_dir: Path = DBT_PROJECT_DIR,
        profiles_dir: Path = DBT_PROFILES_DIR,
        metrics_path: Path = METRICS_PATH,
        command_timeout: int = DEFAULT_COMMAND_TIMEOUT,
    ) -> None:
        self._project_dir = Path(project_dir)
        self._profiles_dir = Path(profiles_dir)
        self._timeout = command_timeout
        self._metric_metadata = self._load_metric_metadata(Path(metrics_path))
        self._dimension_cache: dict[str, list[str]] = {}

    @staticmethod
    def _load_metric_metadata(path: Path) -> dict[str, dict[str, Any]]:
        if not path.exists():
            raise SemanticLayerConfigError(f"Metrics file not found: {path}")
        document = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        metadata = {}
        for metric in document.get("metrics", []):
            inputs = metric.get("type_params", {}).get("metrics", [])
            metric_type = metric.get("type", "simple")
            cumulative_params = metric.get("type_params", {}).get(
                "cumulative_type_params", {}
            )
            metadata[metric["name"]] = {
                "label": metric.get("label", metric["name"]),
                "description": metric.get("description", ""),
                "type": metric_type,
                "requires_time_dimension": any(
                    "offset_window" in item for item in inputs
                )
                or (
                    metric_type == "cumulative"
                    and bool(cumulative_params.get("grain_to_date"))
                ),
            }
        if not metadata:
            raise SemanticLayerConfigError("No metrics were defined in metrics.yml")
        return metadata

    def _run_mf(self, args: list[str]) -> str:
        cmd = ["mf", *args]
        env = {**os.environ, "DBT_PROFILES_DIR": str(self._profiles_dir)}
        logger.info("Running MetricFlow command: %s", " ".join(cmd))
        try:
            result = subprocess.run(
                cmd,
                cwd=self._project_dir,
                env=env,
                capture_output=True,
                text=True,
                timeout=self._timeout,
                check=False,
            )
        except FileNotFoundError as exc:
            raise MetricFlowCommandError(
                "The `mf` CLI was not found. Install it with `pip install dbt-metricflow`."
            ) from exc
        except subprocess.TimeoutExpired as exc:
            raise MetricFlowCommandError(
                f"MetricFlow command timed out after {self._timeout}s: {' '.join(cmd)}"
            ) from exc
        if result.returncode != 0:
            raise MetricFlowCommandError(
                f"MetricFlow command failed ({' '.join(cmd)}):\n{result.stdout}\n{result.stderr}"
            )
        return result.stdout

    # ------------------------------------------------------------------
    # Dimension name normalization
    # ------------------------------------------------------------------

    @staticmethod
    def _short_dimension_name(qualified: str) -> str:
        if qualified.startswith("metric_time"):
            return TIME_DIMENSION
        if qualified.startswith(ENTITY_PREFIX):
            return qualified[len(ENTITY_PREFIX) :]
        return qualified

    def _get_available_dimensions(self, metric_name: str) -> list[str]:
        """Return MetricFlow's fully-qualified dimension names for a metric (cached)."""
        if metric_name not in self._dimension_cache:
            stdout = self._run_mf(["list", "dimensions", "--metrics", metric_name])
            self._dimension_cache[metric_name] = self._parse_bullet_list(stdout)
        return self._dimension_cache[metric_name]

    def _qualify_dimension(self, metric_name: str, dimension: str) -> str:
        """Resolve a short dimension name (e.g. ``country``) to MetricFlow's qualified name."""
        if dimension.startswith("metric_time__"):
            granularity = dimension.removeprefix("metric_time__")
            if granularity in VALID_GRANULARITIES:
                return dimension
        available = self._get_available_dimensions(metric_name)
        if dimension in available:
            return dimension
        if dimension == TIME_DIMENSION:
            candidate = f"{ENTITY_PREFIX}{TIME_DIMENSION}"
            if candidate in available:
                return candidate
        candidate = f"{ENTITY_PREFIX}{dimension}"
        if candidate in available:
            return candidate
        available_short = sorted({self._short_dimension_name(d) for d in available})
        raise ValueError(
            f"Unknown dimension '{dimension}' for metric '{metric_name}'. "
            f"Available dimensions: {', '.join(available_short)}"
        )

    # ------------------------------------------------------------------
    # Output parsing
    # ------------------------------------------------------------------

    @staticmethod
    def _parse_bullet_list(stdout: str) -> list[str]:
        items = []
        for line in stdout.splitlines():
            line = line.strip()
            if line.startswith("•"):
                items.append(line.lstrip("•").strip())
        return items

    @staticmethod
    def _parse_metrics_listing(stdout: str) -> dict[str, list[str]]:
        metrics: dict[str, list[str]] = {}
        for line in stdout.splitlines():
            line = line.strip()
            if not line.startswith("•") or ":" not in line:
                continue
            name, dims = line.lstrip("•").strip().split(":", 1)
            metrics[name.strip()] = [d.strip() for d in dims.split(",") if d.strip()]
        return metrics

    @staticmethod
    def _split_explain_output(stdout: str) -> tuple[str, str]:
        """Split `mf query --explain --show-dataflow-plan` output into (sql, query_plan)."""
        plan_lines: list[str] = []
        sql_lines: list[str] = []
        in_plan = True
        for line in stdout.splitlines():
            if in_plan and (line.startswith("--") or not line.strip()):
                plan_lines.append(line)
                continue
            in_plan = False
            sql_lines.append(line)
        return "\n".join(sql_lines).strip(), "\n".join(plan_lines).strip()

    def _rename_result_columns(self, frame: pd.DataFrame) -> pd.DataFrame:
        rename_map = {}
        entity_time_prefix = f"{ENTITY_PREFIX}{TIME_DIMENSION}"
        for col in frame.columns:
            if col.startswith(("metric_time", entity_time_prefix)):
                # MetricFlow suffixes time dimensions with their granularity
                # (e.g. `roaming_event__event_date__day`); collapse all of
                # these back to the single business-friendly `event_date`.
                rename_map[col] = TIME_DIMENSION
            elif col.startswith(ENTITY_PREFIX):
                rename_map[col] = col[len(ENTITY_PREFIX) :]
        return frame.rename(columns=rename_map)

    @staticmethod
    def _frame_to_records(frame: pd.DataFrame) -> list[dict[str, Any]]:
        records = frame.to_dict(orient="records")
        for record in records:
            for key, value in record.items():
                if isinstance(value, (pd.Timestamp, datetime, date)):
                    record[key] = value.isoformat()
                elif isinstance(value, float) and pd.isna(value):
                    record[key] = None
        return records

    def _run_query_to_dataframe(self, args: list[str]) -> pd.DataFrame:
        """Run `mf query ... --csv <tmp>` and load the result into a DataFrame."""
        with tempfile.NamedTemporaryFile(suffix=".csv", delete=False) as tmp:
            csv_path = Path(tmp.name)
        try:
            self._run_mf([*args, "--csv", str(csv_path), "--quiet"])
            try:
                frame = pd.read_csv(csv_path)
            except pd.errors.EmptyDataError:
                # MetricFlow emits an empty file when a valid query has no rows.
                frame = pd.DataFrame()
        finally:
            csv_path.unlink(missing_ok=True)
        return self._rename_result_columns(frame)

    # ------------------------------------------------------------------
    # Discovery
    # ------------------------------------------------------------------

    def health_check(self) -> dict[str, Any]:
        """Run `mf health-checks` to verify MetricFlow can reach the warehouse."""
        try:
            stdout = self._run_mf(["health-checks"])
        except MetricFlowCommandError as exc:
            return {"healthy": False, "details": str(exc)}
        healthy = "❌" not in stdout and "FAIL" not in stdout.upper()
        return {"healthy": healthy, "details": stdout.strip()}

    def list_metrics(self) -> list[dict[str, Any]]:
        """Return all metrics known to MetricFlow, enriched with label/description."""
        stdout = self._run_mf(["list", "metrics", "--show-all-dimensions"])
        parsed = self._parse_metrics_listing(stdout)
        metrics = []
        for name, qualified_dims in parsed.items():
            self._dimension_cache[name] = qualified_dims
            meta = self._metric_metadata.get(name, {"label": name, "description": ""})
            metrics.append(
                {
                    "name": name,
                    "label": meta["label"],
                    "description": meta["description"],
                    "type": meta.get("type", "simple"),
                    "requires_time_dimension": meta.get(
                        "requires_time_dimension", False
                    ),
                    "dimensions": sorted(
                        {self._short_dimension_name(d) for d in qualified_dims}
                    ),
                }
            )
        return metrics

    def list_summary_metrics(self) -> list[dict[str, Any]]:
        """Return metrics selected by the dashboard's declarative configuration."""
        summary_path = self._project_dir.parents[1] / "dashboard" / "summary.yml"
        if not summary_path.exists():
            raise SemanticLayerConfigError(
                f"Summary configuration not found: {summary_path}"
            )
        summary = yaml.safe_load(summary_path.read_text(encoding="utf-8")) or {}
        selected_names = summary.get("metrics", [])
        metrics_by_name = {metric["name"]: metric for metric in self.list_metrics()}
        return [
            metrics_by_name[name] for name in selected_names if name in metrics_by_name
        ]

    def list_dimensions(
        self, metric_name: Optional[str] = None
    ) -> list[dict[str, Any]]:
        """List dimensions, optionally scoped to a single metric.

        MetricFlow's ``mf list dimensions`` requires at least one metric, so
        when ``metric_name`` is omitted this queries across every known
        metric and returns the union of their dimensions.
        """
        metrics_arg = metric_name or ",".join(sorted(self._metric_metadata))
        args = ["list", "dimensions", "--metrics", metrics_arg]
        qualified = self._parse_bullet_list(self._run_mf(args))
        if metric_name:
            self._dimension_cache[metric_name] = qualified
        unique: dict[str, str] = {}
        # Prefer entity-qualified names (e.g. `roaming_event__event_date`)
        # over the generic `metric_time` alias when both map to the same
        # short name, since the former is more descriptive.
        for dim in sorted(qualified, key=lambda d: d.startswith("metric_time")):
            unique.setdefault(self._short_dimension_name(dim), dim)
        return [
            {"name": short, "qualified_name": qualified_name}
            for short, qualified_name in sorted(unique.items())
        ]

    def explain_metric(self, metric_name: str) -> dict[str, Any]:
        """Return metadata for a metric: name, description, measure and available dimensions."""
        meta = self._metric_metadata.get(metric_name)
        if meta is None:
            available = ", ".join(sorted(self._metric_metadata))
            raise ValueError(
                f"Unknown metric '{metric_name}'. Available metrics: {available}"
            )
        available_dims = self._get_available_dimensions(metric_name)
        return {
            "name": metric_name,
            "label": meta["label"],
            "description": meta["description"],
            "measure": metric_name,
            "dimensions": sorted(
                {self._short_dimension_name(d) for d in available_dims}
            ),
        }

    # ------------------------------------------------------------------
    # Query execution (all via MetricFlow, never hand-built SQL)
    # ------------------------------------------------------------------

    def query_metric(
        self,
        metric_name: str,
        dimensions: Optional[list[str]] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        limit: int = 100,
    ) -> dict[str, Any]:
        """Execute `mf query` for a metric and return rows as structured JSON."""
        dimensions = dimensions or []
        metric_metadata = self._metric_metadata.get(metric_name, {})
        if (
            metric_metadata.get("requires_time_dimension")
            and TIME_DIMENSION not in dimensions
        ):
            dimensions = [TIME_DIMENSION, *dimensions]
        qualified_dims = [self._qualify_dimension(metric_name, d) for d in dimensions]

        args = ["query", "--metrics", metric_name]
        if qualified_dims:
            args += ["--group-by", ",".join(qualified_dims)]
        if start_date:
            args += ["--start-time", start_date]
        if end_date:
            args += ["--end-time", end_date]
        if limit is not None:
            args += ["--limit", str(limit)]

        frame = self._run_query_to_dataframe(args)
        records = self._frame_to_records(frame)
        return {
            "metric": metric_name,
            "dimensions": dimensions,
            "start_date": start_date,
            "end_date": end_date,
            "row_count": len(records),
            "data": records,
        }

    def get_time_series(
        self,
        metric_name: str,
        granularity: str = "month",
        dimensions: Optional[list[str]] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
    ) -> dict[str, Any]:
        """Return a metric's evolution over time at the requested granularity."""
        if granularity not in VALID_GRANULARITIES:
            raise ValueError(
                f"Invalid granularity '{granularity}'. Must be one of {sorted(VALID_GRANULARITIES)}"
            )
        time_dim = f"metric_time__{granularity}"
        dimensions = dimensions or []
        qualified_dims = [
            self._qualify_dimension(metric_name, dimension) for dimension in dimensions
        ]
        args = [
            "query",
            "--metrics",
            metric_name,
            "--group-by",
            ",".join([time_dim, *qualified_dims]),
            "--order",
            time_dim,
        ]
        if start_date:
            args += ["--start-time", start_date]
        if end_date:
            args += ["--end-time", end_date]

        frame = self._run_query_to_dataframe(args)
        records = self._frame_to_records(frame)
        return {
            "metric": metric_name,
            "granularity": granularity,
            "dimensions": dimensions,
            "start_date": start_date,
            "end_date": end_date,
            "row_count": len(records),
            "data": records,
        }

    def top_n(
        self, metric_name: str, dimension: str, limit: int = 10
    ) -> dict[str, Any]:
        """Return the top-N values of `dimension` ranked by `metric_name` (descending)."""
        qualified_dim = self._qualify_dimension(metric_name, dimension)
        args = [
            "query",
            "--metrics",
            metric_name,
            "--group-by",
            qualified_dim,
            "--order",
            f"-{metric_name}",
            "--limit",
            str(limit),
        ]
        frame = self._run_query_to_dataframe(args)
        records = self._frame_to_records(frame)
        return {
            "metric": metric_name,
            "dimension": dimension,
            "limit": limit,
            "row_count": len(records),
            "data": records,
        }

    def metric_sql_preview(
        self, metric_name: str, dimensions: Optional[list[str]] = None
    ) -> dict[str, Any]:
        """Return the SQL and query plan MetricFlow would execute for a metric query."""
        dimensions = dimensions or []
        qualified_dims = [self._qualify_dimension(metric_name, d) for d in dimensions]

        args = ["query", "--metrics", metric_name]
        if qualified_dims:
            args += ["--group-by", ",".join(qualified_dims)]
        args += ["--explain", "--show-dataflow-plan", "--quiet"]

        stdout = self._run_mf(args)
        sql, query_plan = self._split_explain_output(stdout)
        return {
            "metric": metric_name,
            "dimensions": dimensions,
            "sql": sql,
            "query_plan": query_plan,
            "metric_info": self.explain_metric(metric_name),
        }


_client: Optional[SemanticLayerClient] = None


def get_client() -> SemanticLayerClient:
    """Return a process-wide singleton :class:`SemanticLayerClient` instance."""
    global _client
    if _client is None:
        _client = SemanticLayerClient()
    return _client
