"""Google ADK wiring with a graceful offline fallback.

If google-adk + a GOOGLE_API_KEY are present, we build a real ADK Agent with
FunctionTool wrappers around our Python tool functions. Otherwise we fall back
to a deterministic, rule-based reasoner that still invokes the same tools —
so the demo always returns grounded answers.

The runner helper also extracts `function_call` / `function_response` events
so the UI can render citation chips regardless of which engine served the turn.
"""
from __future__ import annotations

import logging
import os
from collections.abc import Callable
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
    HAS_ADK = bool(os.environ.get("GOOGLE_API_KEY"))
except Exception as e:
    log.info("google-adk not available, using fallback reasoner: %s", e)


def build_adk_agent(
    name: str,
    model: str,
    instruction: str,
    tool_fns: list[Callable[..., Any]],
) -> Any | None:
    """Return a configured ADK Runner or None if ADK is unavailable."""
    if not HAS_ADK:
        return None
    try:  # pragma: no cover
        tools = [FunctionTool(fn) for fn in tool_fns]
        agent = Agent(name=name, model=model, instruction=instruction, tools=tools)
        session_service = InMemorySessionService()
        return Runner(agent=agent, app_name="flowpulse", session_service=session_service)
    except Exception as e:
        log.warning("ADK agent build failed, falling back: %s", e)
        return None


async def run_adk(
    runner: Any,
    user_id: str,
    message: str,
    session_id: str | None = None,
) -> dict:
    """Execute a single turn.

    A stable `session_id` lets the caller carry conversation memory across
    turns. The session is created on first use and then reused — so the
    model sees earlier messages + tool results instead of starting blank
    every turn.

    Returns:
        {
          "reply":      concatenated final-response text,
          "tool_calls": [{"name", "args", "result"}, ...]  — chronological
        }
    """
    from google.genai import types as gtypes  # type: ignore

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
                    key = getattr(fc, "id", None) or fc.name
                    pending[key] = {"name": fc.name, "args": dict(fc.args or {})}
                elif fr is not None:
                    key = getattr(fr, "id", None) or fr.name
                    slot = pending.pop(key, {"name": fr.name, "args": {}})
                    slot["result"] = fr.response
                    tool_calls.append(slot)
        if event.is_final_response() and event.content and event.content.parts:
            for p in event.content.parts:
                if getattr(p, "text", None):
                    chunks.append(p.text)

    return {"reply": "\n".join(chunks).strip(), "tool_calls": tool_calls}


def reset_session(runner: Any | None, session_id: str) -> None:
    """Drop the cached session so the next call starts a fresh conversation."""
    if runner is None:
        return
    _SESSION_CACHE.pop((id(runner), session_id), None)
