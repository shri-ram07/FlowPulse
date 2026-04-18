"""Central agent configuration.

One place to pin the Gemini model + any future agent-wide knobs. All 5
specialists import `GEMINI_MODEL` from here so switching models is a single
env var away.

Default: `gemini-3-flash-preview` — Google's newest-generation Flash SKU,
verified working on our Orchestrator's multi-tool pipeline. Slightly tighter
free-tier quotas than the GA 2.5 Flash, but normal demo-scale traffic sits
comfortably inside the window. See ADR 0005 for the decision trail and the
one-command fallback to `gemini-2.5-flash` when quota tightens.

Override via `FLOWPULSE_GEMINI_MODEL` (e.g. `gemini-2.5-flash`,
`gemini-3.1-flash-lite-preview`, `gemini-2.5-pro`). No rebuild required —
a single `gcloud run services update ... --update-env-vars=...` flips it
live on Cloud Run.
"""

from __future__ import annotations

import os
from typing import Final

GEMINI_MODEL: str = os.environ.get(
    "FLOWPULSE_GEMINI_MODEL",
    "gemini-3-flash-preview",
)

# ---- Forecast recommendation thresholds -----------------------------------
# Maps a `predicted_score` to an action band:
#   score <  SCORE_INTERVENE_THRESHOLD              -> "intervene"
#   SCORE_INTERVENE <= score < SCORE_MONITOR         -> "monitor"
#   score >= SCORE_MONITOR_THRESHOLD                 -> "hold"
# Shared by ForecastAgent (prompt + fallback) and the Orchestrator so the
# numbers live in one place.
SCORE_INTERVENE_THRESHOLD: Final[int] = 50
SCORE_MONITOR_THRESHOLD: Final[int] = 75
