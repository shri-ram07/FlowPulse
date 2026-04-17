"""Back-compat shim — the Ops pipeline now lives in `orchestrator_agent`.

This module still exposes `propose_actions` so the existing API route and
tests keep working. The heavy lifting — SafetyAgent → ForecastAgent →
RoutingAgent → CommsAgent → direct engine tools — is in orchestrator_agent.py.

Historically this file contained a single big LlmAgent. We upgraded to a
5-agent orchestration in April 2026; see docs/adr/0002-grounded-tool-calling.md
and the README's architecture section for the rationale.
"""
from __future__ import annotations

from backend.agents.orchestrator_agent import propose_actions

__all__ = ["propose_actions"]
