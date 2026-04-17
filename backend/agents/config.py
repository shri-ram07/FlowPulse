"""Central agent configuration.

One place to pin the Gemini model + any future agent-wide knobs. All 5
specialists import `GEMINI_MODEL` from here so switching models is a single
env var away.

Default: `gemini-2.5-flash` — the model Vertex AI currently publishes most
widely across regions. Override via `FLOWPULSE_GEMINI_MODEL` if your project
has access to a different variant (e.g. `gemini-2.0-flash-001`,
`gemini-2.5-pro`).
"""
from __future__ import annotations

import os

GEMINI_MODEL: str = os.environ.get("FLOWPULSE_GEMINI_MODEL", "gemini-2.5-flash")
