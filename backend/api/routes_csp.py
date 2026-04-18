"""CSP violation reporting endpoint.

Browsers POST CSP-violation reports here when the `report-uri` (legacy) or
`report-to` (Reporting-API) directives fire. We log them as structured JSON so
they show up alongside the rest of FlowPulse's events in Cloud Logging without
adding any persistent dependency.

The payload shape varies by browser:
- Chrome/Edge (Reporting-API): `application/reports+json` — a list of reports.
- Firefox/Safari (legacy `report-uri`): `application/csp-report` — single
  `{"csp-report": {...}}` wrapper.

We accept both without blowing up; the log entry is the source of truth.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Request, status
from fastapi.responses import Response

from backend.core.logging import log

router = APIRouter(prefix="/api", tags=["security"])


@router.post(
    "/csp-report",
    status_code=status.HTTP_204_NO_CONTENT,
    include_in_schema=False,
)
async def csp_report(request: Request) -> Response:
    """Accept a CSP violation report and emit it as a structured log line."""
    try:
        body: Any = await request.json()
    except ValueError:
        body = {"parse_error": "non_json_body"}

    # The report is untrusted input; truncate the stringified form to keep the
    # log line inside GCP's per-entry size limit.
    log.warning(
        "security.csp_violation",
        extra={
            "ua": request.headers.get("user-agent", "")[:240],
            "ct": request.headers.get("content-type", ""),
            "report": str(body)[:2000],
        },
    )
    return Response(status_code=status.HTTP_204_NO_CONTENT)
