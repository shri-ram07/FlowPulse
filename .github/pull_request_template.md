<!-- Thanks for contributing to FlowPulse. Please fill out the sections below. -->

## Summary
<!-- 1-3 bullets: what changes, why. If fixing a bug, link the issue. -->

-

## Test plan

<!-- Check each box once you've run the gate. CI runs the same set on push. -->

- [ ] `ruff check backend` → All checks passed
- [ ] `ruff format --check backend` → no diffs
- [ ] `mypy backend --strict --exclude 'backend/tests'` → 0 errors
- [ ] `pytest backend/tests -q` → all pass, coverage ≥ 85%
- [ ] `cd frontend && npm run lint` → No ESLint warnings or errors
- [ ] `cd frontend && npm run format:check` → clean
- [ ] `cd frontend && npx tsc --noEmit` → exit 0
- [ ] `cd frontend && npm run test:coverage` → all pass, thresholds met

## Checklist

- [ ] Conventional-commit message (`feat:` / `fix:` / `refactor:` / `docs:` / `chore:`)
- [ ] New env var → documented in `.env.example` + `docs/DEPLOYING.md`
- [ ] New Google service wired → row added to README services table + AGENTS.md stack table
- [ ] New public API → row added to `VERIFICATION.md`
- [ ] No secrets, API keys, or credentials in the diff
- [ ] No change to a currently-passing test assertion (or a strong reason why)

## Screenshots / logs
<!-- Optional — helpful for UI changes, new dashboards, new Cloud Trace spans. -->
