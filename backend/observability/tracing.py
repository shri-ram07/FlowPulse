"""OpenTelemetry wiring — exports spans to Google Cloud Trace when running
on GCP, otherwise uses a no-op tracer so local dev has zero friction.

Guardrails applied so misconfigured credentials never spam the console:

1. If the service-account's project doesn't match GOOGLE_CLOUD_PROJECT,
   we skip the exporter entirely (permission-denied is guaranteed).
2. The OT Cloud-Trace exporter's own logger is quieted to WARNING and
   given a single-line formatter so if permissions ARE wrong at runtime
   we see one clean line per batch, not a 90-line stack trace each tick.
"""
from __future__ import annotations

import json
import logging
import os
import pathlib
from typing import Any

from backend.core.logging import log


def _sa_project() -> str | None:
    """Best-effort read of the SA JSON's project_id, or None."""
    path = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS", "")
    if not path or not pathlib.Path(path).exists():
        return None
    try:
        return json.loads(pathlib.Path(path).read_text()).get("project_id")
    except Exception:
        return None


def configure_tracing(service_name: str = "flowpulse") -> Any:
    """Idempotent tracer setup. Returns the tracer (or a no-op stand-in)."""
    try:
        from opentelemetry import trace
        from opentelemetry.sdk.resources import SERVICE_NAME, Resource
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export import BatchSpanProcessor
    except Exception as e:  # pragma: no cover — OT not installed
        log.info("tracing.disabled", extra={"reason": str(e)})
        return _NoopTracer()

    provider = TracerProvider(resource=Resource.create({SERVICE_NAME: service_name}))
    project = os.environ.get("GOOGLE_CLOUD_PROJECT")
    sa_proj = _sa_project()

    should_export = bool(project)
    skip_reason: str | None = None

    if should_export and sa_proj and sa_proj != project:
        should_export = False
        skip_reason = (
            f"service-account project '{sa_proj}' does not match "
            f"GOOGLE_CLOUD_PROJECT='{project}' — would 403 on every export"
        )

    if should_export:
        try:  # pragma: no cover — requires google-cloud-trace
            from opentelemetry.exporter.cloud_trace import CloudTraceSpanExporter  # type: ignore
            exporter = CloudTraceSpanExporter(project_id=project)
            provider.add_span_processor(BatchSpanProcessor(exporter))
            log.info("tracing.cloud_trace", extra={"project": project})
        except Exception as e:
            log.warning("tracing.cloud_trace_unavailable", extra={"err": str(e)})

        # Tame the exporter's noisy logger: one-line WARNING per unique
        # message, at most once per minute. A stray 403 or network blip must
        # never spam the console with multi-page tracebacks every 5 s.
        ct_logger = logging.getLogger("opentelemetry.exporter.cloud_trace")
        ct_logger.setLevel(logging.WARNING)
        ct_logger.addFilter(_RateLimitAndStripStack())
    else:
        log.info(
            "tracing.cloud_trace_skipped",
            extra={"reason": skip_reason or "GOOGLE_CLOUD_PROJECT not set"},
        )

    trace.set_tracer_provider(provider)
    return trace.get_tracer(service_name)


class _NoopTracer:
    def start_as_current_span(self, _name: str, **_: Any):  # type: ignore[no-untyped-def]
        from contextlib import nullcontext
        return nullcontext()


class _RateLimitAndStripStack(logging.Filter):
    """Strips exception tracebacks and rate-limits identical messages to
    at most once per minute. Prevents the Cloud Trace exporter from
    flooding stdout when IAM is misconfigured.
    """
    _WINDOW = 60.0

    def __init__(self) -> None:
        super().__init__()
        self._seen: dict[str, float] = {}

    def filter(self, record: logging.LogRecord) -> bool:  # type: ignore[override]
        import time
        now = time.monotonic()
        key = record.getMessage()
        last = self._seen.get(key, 0)
        if now - last < self._WINDOW:
            return False
        self._seen[key] = now
        # Drop the traceback so the line stays short.
        record.exc_info = None
        record.exc_text = None
        return True
