@echo off
REM =====================================================================
REM FlowPulse launcher -- one tab for backend, one for frontend.
REM First run: create .venv, install deps, npm install.
REM Every run: open a Windows Terminal window with two tabs.
REM =====================================================================
setlocal
set "ROOT=%~dp0"
cd /d "%ROOT%"

REM --- load optional .env (KEY=VALUE, # comments ok) --------------------
if exist "%ROOT%.env" (
    for /f "usebackq eol=# tokens=1,* delims==" %%A in ("%ROOT%.env") do (
        if not "%%A"=="" set "%%A=%%B"
    )
)

REM --- Python available? ------------------------------------------------
where py >nul 2>&1
if errorlevel 1 goto no_py

REM --- venv + pip install on first run ----------------------------------
if not exist "%ROOT%.venv\Scripts\python.exe" call :setup_venv
if errorlevel 1 exit /b 1

REM Sentinel marker -- if pip install didn't complete last time, redo it.
if not exist "%ROOT%.venv\.deps_installed" call :install_pip_deps
if errorlevel 1 exit /b 1

REM --- npm available? ---------------------------------------------------
where npm >nul 2>&1
if errorlevel 1 goto no_npm

REM --- npm install on first run -----------------------------------------
if not exist "%ROOT%frontend\node_modules" call :setup_node
if errorlevel 1 exit /b 1

REM --- commands for each tab (MUST be quoted set so && is stored as text)
set "BACKEND_CMD=cd /d %ROOT% && call .venv\Scripts\activate.bat && uvicorn backend.main:app --reload --port 8000"
set "FRONTEND_CMD=cd /d %ROOT%frontend && npm run dev"

REM --- launch ------------------------------------------------------------
where wt >nul 2>&1
if errorlevel 1 goto two_windows

echo [FlowPulse] Launching Windows Terminal with two tabs...
start "" wt -w 0 new-tab --title "FlowPulse Backend" cmd /k "%BACKEND_CMD%" \; new-tab --title "FlowPulse Frontend" cmd /k "%FRONTEND_CMD%"
goto done

:two_windows
echo [FlowPulse] Windows Terminal not found -- opening two separate windows.
start "FlowPulse Backend"  cmd /k "%BACKEND_CMD%"
start "FlowPulse Frontend" cmd /k "%FRONTEND_CMD%"

:done
echo.
echo [FlowPulse] Running.
echo   Attendee map    : http://localhost:3000
echo   Concierge chat  : http://localhost:3000/chat
echo   Ops console     : http://localhost:3000/ops      ops / ops-demo
echo   API docs        : http://localhost:8000/docs
echo.
endlocal
exit /b 0

REM =====================================================================
REM helpers
REM =====================================================================

:setup_venv
echo [FlowPulse] Creating .venv ...
py -3 -m venv "%ROOT%.venv"
if errorlevel 1 (
    echo [FlowPulse] Failed to create venv.
    exit /b 1
)
exit /b 0

:install_pip_deps
echo [FlowPulse] Installing Python dependencies, one-time step...
"%ROOT%.venv\Scripts\python.exe" -m pip install --upgrade pip
"%ROOT%.venv\Scripts\python.exe" -m pip install -r "%ROOT%backend\requirements.txt"
if errorlevel 1 (
    echo [FlowPulse] pip install failed.
    exit /b 1
)
REM write sentinel marker so we don't reinstall every run.
> "%ROOT%.venv\.deps_installed" echo ok
exit /b 0

:setup_node
echo [FlowPulse] Running npm install ...
pushd "%ROOT%frontend"
call npm install
set "NPM_RC=%ERRORLEVEL%"
popd
if not "%NPM_RC%"=="0" (
    echo [FlowPulse] npm install failed.
    exit /b 1
)
exit /b 0

:no_py
echo [FlowPulse] ERROR: 'py' launcher not found. Install Python 3.11+ from python.org.
exit /b 1

:no_npm
echo [FlowPulse] ERROR: npm not found. Install Node.js 20+ from nodejs.org.
exit /b 1
