# ADR 0002 — Grounded tool-calling over free-form generation

Status: **Accepted**
Date: 2026-04-16
Deciders: Shri Ram Dwivedi

## Context

FlowPulse's agents help fans and staff make decisions with real consequences ("go to food court 5, 3-min walk"). A hallucinated Flow Score or an invented walking time isn't just wrong — it erodes trust and can send someone into a worse queue.

Two design axes:

1. **Free-form generation**: system prompt includes recent zone data; model improvises.
2. **Grounded tool-calling**: model is forced to invoke deterministic functions that read the live `CrowdFlowEngine`.

## Decision

Adopt **grounded tool-calling at three layers**, enforced end-to-end:

### 1. Prompt level
Explicit rules in `backend/agents/prompts.py` forbid inventing scores, wait times, or locations. When the fan hasn't shared their position, the model is instructed *not* to call `get_best_route` and *not* to claim to know where they are.

### 2. Tool level
Every tool in `backend/agents/tools.py` validates input against the live engine and returns `{"error": ...}` on unknown zone / invalid kind. The model is told never to fabricate around errors.

### 3. UI level
Every agent reply renders the underlying `tool_calls` as citation chips (`get_all_zones()` `get_best_route()`). An answer without chips is visibly ungrounded — judges and users both can audit the chain.

We use **Gemini's `response_schema`** for structured outputs (Ops plan, forecasts) so JSON is always parseable without regex, and ADK's `FunctionTool` wrapping so every tool call is a span in Cloud Trace.

## Consequences

**Positive**
- No hallucinated numbers in production chat. Verified in smoke tests.
- The trace view shows exactly which engine calls produced each claim.
- Tool-call chips double as user-facing explainability — a rare combination.

**Negative**
- Latency is higher than single-shot generation (model needs a round-trip per tool call; typical chat turn is 1.5–3 s for 1–2 tools).
- The model occasionally refuses to answer rather than invent — a feature for trust but sometimes blunt.

## Alternatives considered

- **Free-form with system-prompt-embedded data**: cheaper, faster, but couldn't survive even a 30-second data delay — data would diverge from the grounded state.
- **RAG over zone history**: useful later for multi-match analytics; overkill for the real-time loop FlowPulse targets.
