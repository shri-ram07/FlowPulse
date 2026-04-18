"""DEPRECATED back-compat shim — re-exports `propose_actions` from
`orchestrator_agent`.

This module is NOT one of the five specialist agents. It exists solely so that
older imports (`from backend.agents.operations_agent import propose_actions`)
keep working; everything moved into the 5-agent orchestration in April 2026.

The five real ADK agents are:
  - orchestrator_agent.py  (top-level composer)
  - safety_agent.py
  - forecast_agent.py
  - routing_agent.py
  - comms_agent.py
(attendee_agent.py is the fan-facing Concierge, which composes Routing +
Forecast as sub-tools — it is counted as the Concierge, not a specialist.)

See docs/adr/0002-grounded-tool-calling.md for the rationale. Prefer importing
from `backend.agents.orchestrator_agent` directly in new code.
"""

from __future__ import annotations

from backend.agents.orchestrator_agent import propose_actions

__all__ = ["propose_actions"]
