"""Unit tests for the observability sinks.

Each sink (BigQuery, Cloud Monitoring, Cloud Trace) has the same shape:

  - module-level `_DISABLED` / `_PROJECT` flags read at import time
  - lazy `_get_client()` that returns None when creds are missing or
    `*_DISABLE_*` env vars are set
  - a public `write_*` / `stream_*` / `configure_*` function that early-returns
    when the client is None

We test each early-return path and the rate-limited failure logger so the
observability layer's decision logic is covered without touching live GCP.
"""

from __future__ import annotations

import importlib
from types import ModuleType
from typing import Any
from unittest.mock import patch


def _fresh(module_path: str, env: dict[str, str]) -> ModuleType:
    """Import (or reload) a module with a scrubbed env.

    Observability modules capture their flags at module load, so to test
    the "disabled" path we must wipe the relevant env vars before reimport.
    """
    import sys

    with patch.dict("os.environ", env, clear=False):
        # Force reimport so module-level env reads pick up `env`.
        sys.modules.pop(module_path, None)
        return importlib.import_module(module_path)


# ---- BigQuery ----------------------------------------------------------------


def test_bigquery_disabled_flag_short_circuits_client() -> None:
    """Setting FLOWPULSE_DISABLE_BIGQUERY=1 makes _get_client() return None."""
    env = {"FLOWPULSE_DISABLE_BIGQUERY": "1", "GOOGLE_CLOUD_PROJECT": "test-proj"}
    mod = _fresh("backend.observability.bigquery", env)
    assert mod._get_client() is None, "expected None when explicit disable flag is set"


def test_bigquery_no_project_short_circuits_client() -> None:
    """Without GOOGLE_CLOUD_PROJECT, _get_client() returns None and never imports BQ SDK."""
    env = {"GOOGLE_CLOUD_PROJECT": "", "FLOWPULSE_DISABLE_BIGQUERY": ""}
    mod = _fresh("backend.observability.bigquery", env)
    assert mod._get_client() is None, "expected None when GOOGLE_CLOUD_PROJECT is empty"


def test_bigquery_stream_is_noop_when_disabled() -> None:
    """stream_tick_rows returns cleanly (no raise) when the sink is disabled."""
    env = {"FLOWPULSE_DISABLE_BIGQUERY": "1", "GOOGLE_CLOUD_PROJECT": "test-proj"}
    mod = _fresh("backend.observability.bigquery", env)
    # Should not raise, should not try to call BQ.
    mod.stream_tick_rows([{"id": "z1", "score": 100}])


def test_bigquery_rate_limited_log_fires_once_per_window() -> None:
    """_maybe_log_failure logs at most once per 60s even on repeat errors."""
    import backend.observability.bigquery as bq

    bq._LAST_FAIL_LOG = 0.0  # reset window
    # First call within window must log; subsequent suppressed.
    with patch.object(bq.log, "warning") as warn:
        bq._maybe_log_failure("oops")  # first
        bq._maybe_log_failure("again")  # suppressed (window not elapsed)
        assert warn.call_count == 1, f"expected 1 log inside window, got {warn.call_count}"


# ---- Cloud Monitoring --------------------------------------------------------


def test_metrics_disabled_flag_short_circuits_client() -> None:
    """FLOWPULSE_DISABLE_METRICS=1 makes _get_client() return None."""
    env = {"FLOWPULSE_DISABLE_METRICS": "1", "GOOGLE_CLOUD_PROJECT": "test-proj"}
    mod = _fresh("backend.observability.metrics", env)
    assert mod._get_client() is None, "expected None when explicit disable flag is set"


def test_metrics_no_project_short_circuits_client() -> None:
    """Without GOOGLE_CLOUD_PROJECT, _get_client() returns None."""
    env = {"GOOGLE_CLOUD_PROJECT": "", "FLOWPULSE_DISABLE_METRICS": ""}
    mod = _fresh("backend.observability.metrics", env)
    assert mod._get_client() is None, "expected None when GOOGLE_CLOUD_PROJECT is empty"


def test_metrics_write_tick_is_noop_when_disabled() -> None:
    """write_tick_metric is a safe no-op when the sink is disabled."""
    env = {"FLOWPULSE_DISABLE_METRICS": "1", "GOOGLE_CLOUD_PROJECT": "test-proj"}
    mod = _fresh("backend.observability.metrics", env)
    # Should not raise.
    mod.write_tick_metric(avg_score=95.0, critical=0, congested=0, zones=29)


# ---- Cloud Trace -------------------------------------------------------------


def test_tracing_noop_tracer_when_otel_absent() -> None:
    """_NoopTracer.start_as_current_span() yields a null-context without raising."""
    from backend.observability.tracing import _NoopTracer

    noop = _NoopTracer()
    with noop.start_as_current_span("test.span"):
        pass  # just ensures no raise


def test_tracing_sa_project_returns_none_without_credentials(tmp_path: Any) -> None:
    """_sa_project() returns None when GOOGLE_APPLICATION_CREDENTIALS points nowhere."""
    from backend.observability.tracing import _sa_project

    with patch.dict("os.environ", {"GOOGLE_APPLICATION_CREDENTIALS": ""}, clear=False):
        assert _sa_project() is None, "empty creds path must yield None"

    # Explicitly-set missing file also returns None.
    missing = tmp_path / "does-not-exist.json"
    with patch.dict("os.environ", {"GOOGLE_APPLICATION_CREDENTIALS": str(missing)}, clear=False):
        assert _sa_project() is None, "missing-file path must yield None"


def test_tracing_rate_limit_filter_strips_exception_text() -> None:
    """_RateLimitAndStripStack filter drops exc_info and suppresses repeats within 60s."""
    import logging

    from backend.observability.tracing import _RateLimitAndStripStack

    f = _RateLimitAndStripStack()
    rec1 = logging.LogRecord("x", logging.WARNING, "", 0, "boom", None, None)
    rec1.exc_info = (ValueError, ValueError("boom"), None)  # mypy: the filter mutates this back to None
    rec1.exc_text = "traceback..."

    assert f.filter(rec1) is True, "first occurrence must pass"
    # The filter strips exc_info + exc_text in-place; read via rec1.__dict__
    # to dodge mypy's narrowed-type inference from the previous assignment.
    assert rec1.__dict__["exc_info"] is None, "exc_info must be stripped by the filter"
    assert rec1.__dict__["exc_text"] is None, "exc_text must be stripped by the filter"

    # Same message within window must be suppressed.
    rec2 = logging.LogRecord("x", logging.WARNING, "", 0, "boom", None, None)
    assert f.filter(rec2) is False, "duplicate within 60s window must be suppressed"
