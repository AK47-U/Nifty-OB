@echo off
setlocal enabledelayedexpansion

REM ========================================================================
REM NIFTY/SENSEX Live Trading Dashboard - One-Click Startup
REM ========================================================================

cd /d "%~dp0"

echo.
echo ======================================================================
echo   NIFTY/SENSEX Live Trading Dashboard - Starting...
echo ======================================================================
echo.

REM [1/4] Check for old processes using port 8000
echo [1/4] Checking for old processes on port 8000...
for /f "tokens=5" %%a in ('netstat -ano ^| findstr ":8000"') do (
    taskkill /PID %%a /F >nul 2>&1
)
if errorlevel 0 (
    echo       Port cleaned! ✓
) else (
    echo       No old processes found (OK)
)
timeout /t 1 /nobreak >nul

REM [2/4] Start the server
echo [2/4] Starting FastAPI server on port 8000...
set PYTHON_PATH=.\.venv\Scripts\python.exe

if not exist "%PYTHON_PATH%" (
    echo       ERROR: Virtual environment not found at %PYTHON_PATH%
    echo       Please run: python -m venv .venv
    echo       Then: .\.venv\Scripts\pip install -r requirements.txt
    pause
    exit /b 1
)

REM Start server in background
start "" cmd /c "%PYTHON_PATH% -m uvicorn webapp.app:app --host 0.0.0.0 --port 8000"
set SERVER_PID=%ERRORLEVEL%

echo       Server starting (PID: %SERVER_PID%)...
timeout /t 2 /nobreak >nul

REM [3/4] Wait for server to be ready
echo [3/4] Waiting for server to initialize...
set /a RETRY_COUNT=0
:HEALTH_CHECK
set /a RETRY_COUNT+=1

if %RETRY_COUNT% gtr 15 (
    echo       Warning: Server may still be initializing...
    goto OPEN_BROWSER
)

REM Try to connect to server
powershell -Command "try { $response = Invoke-WebRequest -Uri 'http://localhost:8000/api/health' -TimeoutSec 1 -ErrorAction SilentlyContinue; if ($response.StatusCode -eq 200) { exit 0 } else { exit 1 } } catch { exit 1 }" >nul 2>&1

if %ERRORLEVEL% equ 0 (
    echo       Server is ready! ✓
    goto OPEN_BROWSER
) else (
    echo       Waiting... (%RETRY_COUNT%/15)
    timeout /t 1 /nobreak >nul
    goto HEALTH_CHECK
)

REM [4/4] Open browser
:OPEN_BROWSER
echo [4/4] Opening browser to http://localhost:8000...
timeout /t 1 /nobreak >nul
start http://localhost:8000
echo       Browser opened!

echo.
echo ======================================================================
echo   DASHBOARD IS LIVE!
echo ======================================================================
echo.
echo   URL: http://localhost:8000
echo.
echo   Features:
echo   - Live NIFTY/SENSEX candlestick charts (5-min)
echo   - ML-based BUY/SELL signals with confidence
echo   - Real-time WebSocket price updates
echo   - Auto-refresh every 5 minutes
echo   - Entry/Target/Stop Loss levels
echo.
echo   TO STOP THE SERVER:
echo   Press Ctrl+C in this window or close it
echo.
echo ======================================================================
echo.

REM Keep this window open and show server status
:KEEP_ALIVE
echo Server is running... Press Ctrl+C to stop.
timeout /t 60 /nobreak >nul
goto KEEP_ALIVE
