"""Cloud Monitoring custom-metric writer.

Emits `custom.googleapis.com/flowpulse/crowd_flow_score` once per engine tick
with the venue-wide average Flow Score as the point value and the venue size
as a label. Lets a judge (or an SRE) open Metrics Explorer and see a live
chart of the stadium's health.

Activation: set `GOOGLE_CLOUD_PROJECT` + runtime service account has
`roles/monitoring.metricWriter`. Without credentials this module is a no-op.
"""

from __future__ import annotations

import logging
import os
import time
from typing import Any

log = logging.getLogger("flowpulse.metrics")

_PROJECT = os.environ.get("GOOGLE_CLOUD_PROJECT", "")
_DISABLED = os.environ.get("FLOWPULSE_DISABLE_METRICS", "").lower() in ("1", "true", "yes")

_client: Any | None = None


def _get_client() -> Any | None:
    """Lazily create the Cloud Monitoring client once per process."""
    global _client
    if _client is not None or _DISABLED or not _PROJECT:
        return _client
    try:  # pragma: no cover — requires google-cloud-monitoring + creds
        from google.cloud import monitoring_v3

        _client = monitoring_v3.MetricServiceClient()
        log.info("metrics.cloud_monitoring_ready", extra={"project": _PROJECT})
    except Exception as e:
        log.info("metrics.disabled", extra={"reason": str(e)})
        _client = None
    return _client


def write_tick_metric(avg_score: float, critical: int, congested: int, zones: int) -> None:
    """Write one data point to `custom.googleapis.com/flowpulse/crowd_flow_score`.

    Also writes two sibling metrics for critical / congested zone counts so a
    dashboard can alert on either.
    """
    if _DISABLED or not _PROJECT:
        return
    client = _get_client()
    if client is None:
        return
    try:  # pragma: no cover
        from google.cloud import monitoring_v3

        project_name = f"projects/{_PROJECT}"
        now_seconds = int(time.time())

        def make_series(metric_type: str, value: float) -> Any:
            series = monitoring_v3.TimeSeries()
            series.metric.type = metric_type
            series.resource.type = "global"
            series.resource.labels["project_id"] = _PROJECT
            series.metric.labels["zones"] = str(zones)
            point = monitoring_v3.Point(
                {
                    "interval": {"end_time": {"seconds": now_seconds}},
                    "value": {"double_value": float(value)},
                }
            )
            series.points = [point]
            return series

        client.create_time_series(
            name=project_name,
            time_series=[
                make_series("custom.googleapis.com/flowpulse/crowd_flow_score", avg_score),
                make_series("custom.googleapis.com/flowpulse/critical_zones", float(critical)),
                make_series("custom.googleapis.com/flowpulse/congested_zones", float(congested)),
            ],
        )
    except Exception as e:
        # Don't let observability failures break the tick; log once per minute.
        _maybe_log_failure(str(e))


_LAST_FAIL_LOG = 0.0


def _maybe_log_failure(msg: str) -> None:
    global _LAST_FAIL_LOG
    now = time.time()
    if now - _LAST_FAIL_LOG > 60.0:
        _LAST_FAIL_LOG = now
        log.warning("metrics.write_failed", extra={"err": msg[:240]})
