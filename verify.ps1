# verify.ps1 — PowerShell sibling of the Makefile.
#
# Usage:
#   .\verify.ps1          # full local verification (lint + type + test)
#   .\verify.ps1 live     # live-deployment acceptance tests
#   .\verify.ps1 demo     # print the two commands to launch backend + frontend
#
# All commands use the venv at .\.venv (created by start.bat on first run).

param(
    [Parameter(Position=0)]
    [ValidateSet("verify", "live", "test", "lint", "type", "coverage", "demo")]
    [string]$Target = "verify"
)

$ErrorActionPreference = "Stop"
$PY = ".\.venv\Scripts\python.exe"
$RUFF = ".\.venv\Scripts\ruff.exe"

function Say($msg) { Write-Host "`n[verify] $msg" -ForegroundColor Cyan }

function Do-Lint {
    Say "ruff backend"
    & $RUFF check backend
    if ($LASTEXITCODE -ne 0) { throw "ruff failed" }

    Say "tsc --noEmit (frontend)"
    Push-Location frontend
    try {
        npx tsc --noEmit
        if ($LASTEXITCODE -ne 0) { throw "tsc failed" }
    } finally { Pop-Location }
}

function Do-Type {
    Say "mypy --strict on backend/core + security + observability"
    & $PY -m mypy backend/core backend/security backend/observability --strict --ignore-missing-imports
    if ($LASTEXITCODE -ne 0) { throw "mypy strict failed" }
}

function Do-Test {
    Say "pytest (backend)"
    & $PY -m pytest backend/tests -q
    if ($LASTEXITCODE -ne 0) { throw "backend tests failed" }

    Say "vitest (frontend)"
    Push-Location frontend
    try {
        npm test --silent
        if ($LASTEXITCODE -ne 0) { throw "vitest failed" }
    } finally { Pop-Location }
}

function Do-Coverage {
    Say "pytest with --cov-fail-under=85"
    & $PY -m pytest backend/tests --cov=backend --cov-report=term-missing --cov-fail-under=85
    if ($LASTEXITCODE -ne 0) { throw "coverage gate failed" }
}

function Do-Live {
    Say "live deployment acceptance tests"
    & $PY scripts/verify_live.py
    if ($LASTEXITCODE -ne 0) { throw "live verification reported FAIL rows" }
}

switch ($Target) {
    "verify"   { Do-Lint; Do-Type; Do-Test;     Say "all local checks passed." }
    "lint"     { Do-Lint;                       Say "lint clean." }
    "type"     { Do-Type;                       Say "mypy strict passed." }
    "test"     { Do-Test;                       Say "tests passed." }
    "coverage" { Do-Coverage;                   Say "coverage gate met." }
    "live"     { Do-Live;                       Say "live claims verified." }
    "demo"     {
        Write-Host "Run these two commands in separate terminals:" -ForegroundColor Yellow
        Write-Host "  .\.venv\Scripts\uvicorn backend.main:app --reload --port 8000"
        Write-Host "  cd frontend; npm run dev"
        Write-Host "Or: .\start.bat (opens both in Windows Terminal tabs)"
    }
}
