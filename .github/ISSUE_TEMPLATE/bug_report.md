---
name: Bug report
about: Something doesn't work as documented — a route errors, an agent hallucinates, a metric goes missing.
title: "bug: "
labels: [bug]
assignees: ["shri-ram07"]
---

## What happened

<!-- One sentence. e.g. "POST /api/ops/apply returns 500 instead of 409 when no redirect candidate exists." -->

## What you expected

<!-- The behaviour you were expecting based on the README / docs. -->

## Steps to reproduce

1.
2.
3.

## Environment

- OptimFlow / FlowPulse version or commit SHA:
- Where did it happen: `localhost` / live Cloud Run / other
- Browser (if frontend) / Python version (if backend):

## Relevant logs / screenshots

<!-- Paste the last ~30 lines of stderr, or the response body from the API. -->

```

```

## Does `verify_live.py` reproduce it?

<!-- If yes, paste the failing row. If no, note it. -->

- [ ] Yes, `python scripts/verify_live.py` flags this
- [ ] No, only reproducible manually
