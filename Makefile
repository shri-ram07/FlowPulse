# FlowPulse — one-command reproducibility.
#
#   make verify        full local verification: lint + type + test
#   make verify-live   curl-test every live-deployment claim
#   make test          backend + frontend tests
#   make lint          ruff + tsc
#   make type          mypy strict on pure modules
#   make coverage      pytest with coverage threshold
#   make demo          start backend + frontend for a local demo

PYTHON ?= .venv/Scripts/python.exe
RUFF   ?= .venv/Scripts/ruff.exe
MYPY   ?= .venv/Scripts/mypy.exe
NPM    ?= npm

.PHONY: verify verify-live test lint type coverage demo clean

verify: lint type test
	@echo ""
	@echo "[verify] all local checks passed."

lint:
	@echo "--- ruff ---"
	$(RUFF) check backend
	@echo "--- tsc ---"
	cd frontend && npx tsc --noEmit

type:
	@echo "--- mypy strict (core / security / observability) ---"
	$(MYPY) backend/core backend/security backend/observability --strict --ignore-missing-imports

test:
	@echo "--- pytest (backend) ---"
	$(PYTHON) -m pytest backend/tests -q
	@echo "--- vitest (frontend) ---"
	cd frontend && $(NPM) test --silent

coverage:
	$(PYTHON) -m pytest backend/tests --cov=backend --cov-report=term-missing --cov-fail-under=85

verify-live:
	$(PYTHON) scripts/verify_live.py

demo:
	@echo "Starting backend on http://localhost:8000 and frontend on http://localhost:3000 ..."
	@echo "(Use two terminals locally: 'uvicorn backend.main:app --reload' and 'cd frontend && npm run dev')"
	@echo "Or run: start.bat"

clean:
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name .coverage -delete 2>/dev/null || true
	find . -type d -name .pytest_cache -exec rm -rf {} + 2>/dev/null || true
