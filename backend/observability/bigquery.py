"""BigQuery streaming sink for engine ticks.

Every tick streams one row per zone into `flowpulse_events.ticks`. Creates
the dataset + table on first use. Enables:
  - SQL analytics ("which zone spent the most minutes at `critical`?")
  - A Looker Studio dashboard in two clicks.
  - Post-match replay + comparison across match phases.

Schema:
  ts         TIMESTAMP
  zone_id    STRING
  name       STRING
  kind       STRING
  score      INT64
  occupancy  INT64
  capacity   INT64
  density    FLOAT64
  level      STRING
  trend      STRING

Activation: `GOOGLE_CLOUD_PROJECT` set + runtime SA has `roles/bigquery.dataEditor`
on the `flowpulse_events` dataset. Without creds, this module is a no-op.
"""
from __future__ import annotations

import logging
import os
import time
from collections.abc import Iterable
from datetime import datetime, timezone
from typing import Any

log = logging.getLogger("flowpulse.bigquery")

_PROJECT = os.environ.get("GOOGLE_CLOUD_PROJECT", "")
_DATASET = os.environ.get("FLOWPULSE_BQ_DATASET", "flowpulse_events")
_TABLE = os.environ.get("FLOWPULSE_BQ_TABLE", "ticks")
_DISABLED = os.environ.get("FLOWPULSE_DISABLE_BIGQUERY", "").lower() in ("1", "true", "yes")

_client: Any | None = None
_table_ready = False
_LAST_FAIL_LOG = 0.0


_SCHEMA = [
    {"name": "ts", "type": "TIMESTAMP", "mode": "REQUIRED"},
    {"name": "zone_id", "type": "STRING", "mode": "REQUIRED"},
    {"name": "name", "type": "STRING"},
    {"name": "kind", "type": "STRING"},
    {"name": "score", "type": "INT64"},
    {"name": "occupancy", "type": "INT64"},
    {"name": "capacity", "type": "INT64"},
    {"name": "density", "type": "FLOAT64"},
    {"name": "level", "type": "STRING"},
    {"name": "trend", "type": "STRING"},
]


def _get_client() -> Any | None:
    global _client
    if _client is not None or _DISABLED or not _PROJECT:
        return _client
    try:  # pragma: no cover — requires google-cloud-bigquery + creds
        from google.cloud import bigquery
        _client = bigquery.Client(project=_PROJECT)
        log.info("bigquery.ready", extra={"project": _PROJECT,
                                          "dataset": _DATASET, "table": _TABLE})
    except Exception as e:
        log.info("bigquery.disabled", extra={"reason": str(e)})
        _client = None
    return _client


def _ensure_table() -> bool:
    """Create dataset + table on first successful call. Idempotent.

    Returns True when the table is ready; False if anything failed.
    """
    global _table_ready
    if _table_ready:
        return True
    client = _get_client()
    if client is None:
        return False
    try:  # pragma: no cover
        from google.cloud import bigquery
        from google.cloud.exceptions import NotFound
        dataset_ref = bigquery.DatasetReference(_PROJECT, _DATASET)
        try:
            client.get_dataset(dataset_ref)
        except NotFound:
            client.create_dataset(bigquery.Dataset(dataset_ref), exists_ok=True)
            log.info("bigquery.dataset_created", extra={"dataset": _DATASET})
        table_ref = dataset_ref.table(_TABLE)
        try:
            client.get_table(table_ref)
        except NotFound:
            table = bigquery.Table(
                table_ref,
                schema=[
                    bigquery.SchemaField(
                        name=f["name"],
                        field_type=f["type"],
                        mode=f.get("mode", "NULLABLE"),
                    )
                    for f in _SCHEMA
                ],
            )
            # Partition by day for cheap queries.
            table.time_partitioning = bigquery.TimePartitioning(
                type_=bigquery.TimePartitioningType.DAY, field="ts")
            client.create_table(table, exists_ok=True)
            log.info("bigquery.table_created", extra={"table": _TABLE})
        _table_ready = True
        return True
    except Exception as e:
        _maybe_log_failure(f"ensure_table: {e}")
        return False


def stream_tick_rows(zones: Iterable[dict[str, Any]]) -> None:
    """Push one row per zone state into `flowpulse_events.ticks`.

    Zones are dicts as produced by `CrowdFlowEngine._zone_state(...)` — includes
    `id, name, kind, capacity, occupancy, density, score, level, trend, …`.
    """
    if _DISABLED or not _PROJECT:
        return
    client = _get_client()
    if client is None or not _ensure_table():
        return
    try:  # pragma: no cover
        ts = datetime.now(timezone.utc).isoformat()
        rows = [
            {
                "ts": ts,
                "zone_id": z["id"],
                "name": z.get("name"),
                "kind": z.get("kind"),
                "score": int(z.get("score", 0)),
                "occupancy": int(z.get("occupancy", 0)),
                "capacity": int(z.get("capacity", 0)),
                "density": float(z.get("density", 0.0)),
                "level": z.get("level"),
                "trend": z.get("trend"),
            }
            for z in zones
        ]
        table_id = f"{_PROJECT}.{_DATASET}.{_TABLE}"
        errors = client.insert_rows_json(table_id, rows)
        if errors:
            _maybe_log_failure(f"insert_rows errors: {str(errors)[:200]}")
    except Exception as e:
        _maybe_log_failure(f"stream: {e}")


def _maybe_log_failure(msg: str) -> None:
    global _LAST_FAIL_LOG
    now = time.time()
    if now - _LAST_FAIL_LOG > 60.0:
        _LAST_FAIL_LOG = now
        log.warning("bigquery.stream_failed", extra={"err": msg[:240]})
