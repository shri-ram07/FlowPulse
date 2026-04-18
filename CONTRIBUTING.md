# Contributing to FlowPulse

Thanks for considering a contribution. This guide shows you how to get a local
dev loop running, what the code-style gates are, and how to submit changes.

## Local setup (Windows / macOS / Linux)

```bash
git clone https://github.com/shri-ram07/FlowPulse
cd flowpulse
# One-shot launcher: creates .venv, installs deps, opens backend + frontend tabs.
start.bat        # Windows
./start.sh       # macOS / Linux (equivalent — read the file for individual commands)
```

Minimum prerequisites:

- **Python 3.11+**  (3.11 is what Cloud Run uses)
- **Node.js 20+**  (`next@14.2.15` requires ≥ 18.17)
- **gcloud CLI**   (optional — only needed to deploy to Cloud Run)

Environment variables are all optional — see [`.env.example`](.env.example).
The demo runs end-to-end without any keys (agents fall back to a deterministic
reasoner; FCM runs dry-run; Cloud Trace no-ops).

## Verify gates

Every pull request must pass all four:

```bash
# 1. Lint the backend
.venv/Scripts/python.exe -m ruff check backend

# 2. Strict type-check the entire backend
.venv/Scripts/python.exe -m mypy backend --strict

# 3. Backend unit + integration tests (72 tests, 85% coverage gate)
.venv/Scripts/python.exe -m pytest backend/tests -q

# 4. Frontend type-check + unit tests
cd frontend
npx tsc --noEmit
npm test
```

CI runs the same gates plus Trivy container scan, gitleaks, SBOM, and
Lighthouse. See [`.github/workflows/ci.yml`](.github/workflows/ci.yml).

## Code style

- **Python** — ruff (E/F/I/B/UP/S/SIM/RUF/ARG/PIE rule-sets) · mypy `--strict` ·
  4-space indent · one-paragraph module docstring at the top of every file.
- **TypeScript** — `strict: true` · `noUnusedLocals` · `noUnusedParameters` ·
  2-space indent.
- **Components** — PascalCase (`StadiumMap.tsx`); `*.test.tsx` siblings for unit tests.
- **Backend modules** — snake_case; `test_<module>.py` siblings in `backend/tests/`.
- **Constants** — UPPER_SNAKE with `Final[T]` annotation + one-line comment on the *why*.
- **Commits** — conventional-commits format (`feat:`, `fix:`, `refactor:`, `docs:`, etc.).

## Adding a new ADK agent

1. Create `backend/agents/<name>_agent.py` mirroring the structure of
   `safety_agent.py` or `forecast_agent.py`:
   - a module docstring
   - a `SYS_PROMPT` constant
   - `runner = build_adk_agent(name=..., model=GEMINI_MODEL, instruction=SYS_PROMPT, tool_fns=[...])`
   - a deterministic `fallback_<name>(...)` function for when ADK is unavailable.
2. Add a typed response schema to `backend/agents/schemas.py` with
   `description=` on every `Field(...)`.
3. If the agent is *orchestrator-composed*, wire it into
   `backend/agents/orchestrator_agent.py` as a `FunctionTool` callable.
4. Add a pytest module under `backend/tests/test_<name>_agent.py`.

## Pull request checklist

- [ ] All four verify gates are green locally.
- [ ] If you added a new env var: `.env.example` + `docs/DEPLOYING.md` updated.
- [ ] If you added a new Google service: `README.md` services table + `AGENTS.md` stack table updated.
- [ ] If you changed a public API: a matching row added or updated in `VERIFICATION.md`.
- [ ] Commit messages follow conventional-commits.

## Security

Security reports → see [`docs/SECURITY.md`](docs/SECURITY.md) for the STRIDE
threat model and [SECURITY.md](SECURITY.md) for disclosure policy.

## License

By contributing you agree that your contributions are licensed under the
repository's [MIT LICENSE](LICENSE).
