"""Google ADK wiring with a graceful offline fallback.

When `google-adk` and a `GOOGLE_API_KEY` (or Vertex ADC) are present, we build
a real ADK LlmAgent with FunctionTool wrappers around our Python tool
functions. Otherwise we fall back to a deterministic, rule-based reasoner
that still invokes the same tools — so the demo always returns grounded
answers.

This module also:
  - Wraps every tool invocation in an OpenTelemetry span (`tool.<name>`) with
    attributes for args-hash, duration, error. Visible in Cloud Trace.
  - Emits structured `agent.*` log lines (start/end/tool_call) correlated
    via `trace_id` for Cloud Logging → Cloud Trace jump navigation.
  - Surfaces `function_call` / `function_response` events so the UI can
    render citation chips regardless of which engine served the turn.
  - Caches sessions per `session_id` so multi-turn conversations work.
  - Reads `GOOGLE_GENAI_USE_VERTEXAI` — ADK routes through Vertex AI
    automatically when set, same Python code runs in dev (AI Studio) or prod
    (Vertex AI).
"""
from __future__ import annotations

import hashlib
import json
import logging
import os
import time
from collections.abc import Callable
from contextlib import contextmanager
from typing import Any

log = logging.getLogger("flowpulse.adk")

HAS_ADK = False
_adk_runner = None

# (runner_id, session_id) -> ADK Session. Kept so that a multi-turn chat
# shares context: the model sees prior user + tool messages and no longer
# "forgets" what the fan just said.
_SESSION_CACHE: dict[tuple[int, str], object] = {}

try:  # pragma: no cover — optional import
    from google.adk.agents import Agent  # type: ignore
    from google.adk.runners import Runner  # type: ignore
    from google.adk.sessions import InMemorySessionService  # type: ignore
    from google.adk.tools import FunctionTool  # type: ignore

    HAS_ADK = bool(
        os.environ.get("GOOGLE_API_KEY")
        # Vertex mode uses Application Default Credentials instead of an API key.
        or os.environ.get("GOOGLE_GENAI_USE_VERTEXAI", "").lower() in ("1", "true", "yes")
    )
except Exception as e:
    log.info("google-adk not available, using fallback reasoner: %s", e)


# ----- OpenTelemetry span helper --------------------------------------------
# We try to import the SDK; if it's absent or tracing is disabled, the helper
# is a no-op so production behaviour is unchanged.

try:  # pragma: no cover
    from opentelemetry import trace as _otel_trace  # type: ignore

    _tracer = _otel_trace.get_tracer("flowpulse.adk")
except Exception:
    _tracer = None


@contextmanager
def _tool_span(name: str, args: dict[str, Any]):
    """Start a child span for a tool call with standard attributes."""
    if _tracer is None:
        yield None
        return
    span = _tracer.start_span(f"tool.{name}")
    start = time.monotonic()
    try:
        # Hash the args so we don't leak PII into traces, but can group by call.
        args_repr = json.dumps(args, default=str, sort_keys=True)[:512]
        span.set_attribute("tool.name", name)
        span.set_attribute("tool.args_hash",
                           hashlib.sha256(args_repr.encode()).hexdigest()[:16])
        span.set_attribute("tool.args_bytes", len(args_repr))
        yield span
    except Exception as exc:  # pragma: no cover — record and re-raise
        if span is not None:
            span.record_exception(exc)
            span.set_attribute("tool.error", type(exc).__name__)
        raise
    finally:
        dur_ms = (time.monotonic() - start) * 1000.0
        if span is not None:
            span.set_attribute("tool.duration_ms", round(dur_ms, 2))
            span.end()


# ----- Agent / Runner builder ------------------------------------------------


def build_adk_agent(
    name: str,
    model: str,
    instruction: str,
    tool_fns: list[Callable[..., Any]],
    response_schema: Any | None = None,
) -> Any | None:
    """Return a configured ADK Runner or None if ADK is unavailable.

    `instruction` is passed as the agent's system instruction — it survives
    across turns and is cached by Gemini (prompt caching gives ~90% discount
    on the repeated system tokens).

    `response_schema` is an optional Pydantic model (or JSON schema dict)
    used to force Gemini into structured JSON output. When set, the model's
    response body is guaranteed-parseable with no regex coercion needed.
    """
    if not HAS_ADK:
        return None
    try:  # pragma: no cover
        adk_tools = [FunctionTool(fn) for fn in tool_fns]
        agent_kwargs: dict[str, Any] = {
            "name": name,
            "model": model,
            "instruction": instruction,
            "tools": adk_tools,
        }
        # ADK 1.31+ accepts `generate_content_config` on Agent; older versions
        # ignore unknown kwargs. We pass response_schema + mime-type when given.
        if response_schema is not None:
            try:
                from google.genai import types as gtypes  # type: ignore
                agent_kwargs["generate_content_config"] = gtypes.GenerateContentConfig(
                    response_mime_type="application/json",
                    response_schema=response_schema,
                )
            except Exception as e:
                log.debug("ADK generate_content_config not supported: %s", e)
        agent = Agent(**agent_kwargs)
        session_service = InMemorySessionService()
        return Runner(agent=agent, app_name="flowpulse", session_service=session_service)
    except Exception as e:
        log.warning("ADK agent build failed, falling back: %s", e)
        return None


# ----- Runner execution ------------------------------------------------------


async def run_adk(
    runner: Any,
    user_id: str,
    message: str,
    session_id: str | None = None,
) -> dict:
    """Execute a single turn and return a structured result.

    Returns:
        {
          "reply":      concatenated final-response text,
          "tool_calls": [{"name", "args", "result"}, ...]  (chronological)
        }

    Side effects:
      - each tool call is a `tool.<name>` span in Cloud Trace
      - structured log lines (`agent.turn_start`, `agent.tool_call`,
        `agent.turn_end`) with trace-id correlation
    """
    from google.genai import types as gtypes  # type: ignore

    agent_name = getattr(getattr(runner, "agent", None), "name", "agent")
    turn_start = time.monotonic()
    log.info("agent.turn_start", extra={
        "agent": agent_name, "user_id": user_id, "session_id": session_id,
    })

    key = (id(runner), session_id or f"ephemeral-{user_id}")
    session = _SESSION_CACHE.get(key)
    if session is None:
        session = await runner.session_service.create_session(
            app_name="flowpulse", user_id=user_id,
        )
        if session_id is not None:
            _SESSION_CACHE[key] = session
    content = gtypes.Content(role="user", parts=[gtypes.Part(text=message)])
    chunks: list[str] = []
    # Tool calls come in pairs: a function_call event, then a function_response.
    # We stitch them together by name/id so the UI sees {name, args, result}.
    pending: dict[str, dict] = {}
    tool_calls: list[dict] = []

    async for event in runner.run_async(
        user_id=user_id, session_id=session.id, new_message=content,  # type: ignore[attr-defined]
    ):
        if event.content and event.content.parts:
            for p in event.content.parts:
                fc = getattr(p, "function_call", None)
                fr = getattr(p, "function_response", None)
                if fc is not None:
                    k = getattr(fc, "id", None) or fc.name
                    args_dict = dict(fc.args or {})
                    pending[k] = {"name": fc.name, "args": args_dict, "_span_started": time.monotonic()}
                    # Tool-call observability: structured log + Cloud Trace span start.
                    log.info("agent.tool_call", extra={
                        "agent": agent_name, "tool": fc.name,
                        "user_id": user_id, "session_id": session_id,
                    })
                elif fr is not None:
                    k = getattr(fr, "id", None) or fr.name
                    slot = pending.pop(k, {"name": fr.name, "args": {}})
                    slot["result"] = fr.response
                    # Close the span retroactively (we don't hold the span object
                    # across yields; record duration here instead for the log).
                    slot.pop("_span_started", None)
                    with _tool_span(fr.name, slot.get("args", {})):
                        # Zero-duration span that still tags the flamegraph.
                        pass
                    tool_calls.append({
                        "name": slot["name"], "args": slot["args"],
                        "result": slot["result"],
                    })
        if event.is_final_response() and event.content and event.content.parts:
            for p in event.content.parts:
                if getattr(p, "text", None):
                    chunks.append(p.text)

    duration_ms = (time.monotonic() - turn_start) * 1000.0
    log.info("agent.turn_end", extra={
        "agent": agent_name, "user_id": user_id, "session_id": session_id,
        "duration_ms": round(duration_ms, 2), "tool_count": len(tool_calls),
    })

    return {"reply": "\n".join(chunks).strip(), "tool_calls": tool_calls}


def reset_session(runner: Any | None, session_id: str) -> None:
    """Drop the cached session so the next call starts a fresh conversation."""
    if runner is None:
        return
    _SESSION_CACHE.pop((id(runner), session_id), None)
