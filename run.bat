@echo off
setlocal
title MYEXA - Launcher
color 0B
cd /d "%~dp0"

echo.
echo ========================================================
echo        MYEXA - Advanced Search Engine
echo ========================================================
echo.

python --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python is not installed or not in PATH
    pause
    exit /b 1
)
echo [OK] Python detected
echo.

if not exist ".env" (
    echo [INFO] Creating .env from .env.example...
    copy /Y .env.example .env >nul
)

if not exist "database" mkdir database

echo [INFO] Checking dependencies...
python -c "import fastapi, uvicorn, slowapi" 2>nul
if errorlevel 1 (
    echo [INFO] Installing dependencies (first run may take a few minutes)...
    pip install -r backend\requirements.txt
    if errorlevel 1 (
        echo [ERROR] Failed to install dependencies
        pause
        exit /b 1
    )
)
echo [OK] Dependencies installed
echo.

echo [INFO] Stopping previous server on port 3005 (if any)...
for /f "tokens=5" %%a in ('netstat -aon ^| findstr ":3005" ^| findstr "LISTENING"') do (
    echo [INFO] Stopping PID %%a
    taskkill /PID %%a /F >nul 2>&1
)

echo.
echo ========================================================
echo [INFO] Starting MYEXA Server (separate window)...
echo [INFO] Loading AI models (30-60 seconds on first run)...
echo [INFO] Browser will open when server is ready
echo ========================================================
echo.

REM cmd /k keeps the server window open after exit or crash
start "MYEXA Server" cmd /k cd /d "%~dp0" ^&^& python backend/app.py

echo [INFO] Waiting for server (up to 90 seconds)...
python -c "import time, urllib.request, sys
url='http://127.0.0.1:3005/api/health'
for _ in range(30):
    try:
        with urllib.request.urlopen(url, timeout=2) as r:
            if r.status == 200:
                print('[OK] Server ready!')
                sys.exit(0)
    except Exception:
        pass
    time.sleep(3)
print('[ERROR] Server did not respond in time')
print('[TIP] Check the \"MYEXA Server\" window for error messages')
sys.exit(1)"

if errorlevel 1 (
    echo.
    pause
    exit /b 1
)

echo [INFO] Opening browser: http://127.0.0.1:3005/
start "" "http://127.0.0.1:3005/"

echo.
echo ========================================================
echo [OK] MYEXA is running!
echo [INFO] Web UI opened in your browser
echo [INFO] Server runs in the \"MYEXA Server\" window
echo.
echo [TIP] To stop: close \"MYEXA Server\" or press Ctrl+C there
echo ========================================================
echo.
pause
endlocal
