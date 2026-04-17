@echo off
REM =====================================================================
REM FlowPulse — one-click Cloud Run deployment.
REM Thin wrapper that sets env vars and invokes infra\deploy.ps1.
REM
REM Usage (from repo root):
REM     deploy.bat
REM Optional overrides:
REM     deploy.bat my-project-id         REM override PROJECT
REM     deploy.bat my-project-id us-central1
REM =====================================================================
setlocal
set "ROOT=%~dp0"

REM --- gcloud on PATH? --------------------------------------------------
where gcloud >nul 2>&1
if errorlevel 1 (
    echo [flowpulse-deploy] ERROR: gcloud CLI not found on PATH.
    echo Install from https://cloud.google.com/sdk/docs/install, then run 'gcloud init'.
    exit /b 1
)

REM --- PROJECT: arg > env > gcloud default ------------------------------
if not "%~1"=="" (
    set "PROJECT=%~1"
) else if not defined PROJECT (
    for /f "usebackq tokens=*" %%P in (`gcloud config get-value project 2^>nul`) do set "PROJECT=%%P"
)
if not defined PROJECT (
    echo [flowpulse-deploy] ERROR: no GCP project set.
    echo Run 'gcloud config set project YOUR-PROJECT-ID' or pass it as arg 1.
    exit /b 1
)

REM --- REGION: arg 2 > env > default ------------------------------------
if not "%~2"=="" (
    set "REGION=%~2"
) else if not defined REGION (
    set "REGION=asia-south1"
)

REM --- GOOGLE_API_KEY: env > .env file ---------------------------------
if not defined GOOGLE_API_KEY (
    if exist "%ROOT%.env" (
        for /f "usebackq tokens=1,* delims==" %%A in ("%ROOT%.env") do (
            if /i "%%A"=="GOOGLE_API_KEY" set "GOOGLE_API_KEY=%%B"
        )
    )
)

echo.
echo [flowpulse-deploy] PROJECT  = %PROJECT%
echo [flowpulse-deploy] REGION   = %REGION%
if defined GOOGLE_API_KEY (
    echo [flowpulse-deploy] Gemini   = enabled
) else (
    echo [flowpulse-deploy] Gemini   = fallback (no key, agents will use deterministic mode)
)
echo.

REM --- PowerShell availability check -----------------------------------
where powershell >nul 2>&1
if errorlevel 1 (
    echo [flowpulse-deploy] ERROR: powershell.exe not found. This is part of Windows and should exist on any Windows 10/11 machine.
    exit /b 1
)

REM --- Launch the real deploy script -----------------------------------
REM We pipe through PowerShell's -Command so it reads the file with UTF-8
REM semantics regardless of the active Windows codepage. This avoids the
REM Windows-1252 mojibake trap that breaks non-ASCII chars in .ps1 files.
powershell.exe -NoProfile -ExecutionPolicy Bypass ^
    -Command "[Console]::OutputEncoding=[System.Text.Encoding]::UTF8; & '%ROOT%infra\deploy.ps1'"
set "RC=%ERRORLEVEL%"

echo.
if "%RC%"=="0" (
    echo [flowpulse-deploy] Deployment finished successfully.
) else (
    echo [flowpulse-deploy] Deployment failed with exit code %RC%.
)
endlocal & exit /b %RC%
