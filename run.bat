@echo off
title MYEXA - Search Engine
cd /d "%~dp0"

if not exist ".env" (
    copy .env.example .env
    echo Created .env — edit it to add your EXA_API_KEY
)

if not exist "database" mkdir database

echo.
echo ========================================
echo   MYEXA - Advanced Search Engine
echo ========================================
echo.

rem Warn early if the API key is missing — the server starts fine without it,
rem but every search returns "no results".
rem The check passes when a line starts with EXA_API_KEY= and does not hold
rem the placeholder. (A third "findstr /V EXA_API_KEY=" used to strip comment
rem lines but matched the valid line too, so the warning always fired.)
findstr /B /C:"EXA_API_KEY=" .env | findstr /V /C:"your_api_key_here" >nul
if errorlevel 1 (
    echo WARNING: EXA_API_KEY is missing or still the placeholder in .env
    echo          Searches will return no results until it is set.
    echo.
)

echo Installing dependencies...
pip install -q -r backend\requirements.txt
if errorlevel 1 (
    echo ERROR: failed to install dependencies
    pause
    exit /b 1
)

echo Starting server...
start /B "" python backend\app.py

echo Loading model (30-45 sec)...
setlocal enabledelayedexpansion
for /L %%i in (1,1,90) do (
    >nul 2>&1 timeout /t 1
    >nul 2>&1 curl.exe -s http://localhost:3005/api/health && goto ready
)
:ready

echo.
echo ========================================
echo   Server ready on http://localhost:3005
echo ========================================

rem Report which provider actually answers. When the Exa API is blocked
rem (Cloudflare answers 403 for whole IP ranges) the search falls back to the
rem local SearXNG instance, and that instance only lives as long as Docker
rem Desktop is running.
set MYEXA_PROVIDER=
for /f "usebackq delims=" %%a in (`powershell -NoProfile -Command "try { $h = Invoke-RestMethod 'http://localhost:3005/api/health?deep=true'; $h.active_provider } catch { '' }"`) do set MYEXA_PROVIDER=%%a
if "%MYEXA_PROVIDER%"=="searxng" (
    echo NOTE: the Exa API is unavailable, so the search runs on the local
    echo       SearXNG fallback. Docker Desktop must be running for it to
    echo       answer - otherwise searches will fail.
    echo.
)

start http://localhost:3005
echo.
echo Close this window to stop the server.
pause >nul

rem Stop only this server. The old "taskkill /f /im python.exe" also killed
rem every unrelated Python process on the machine.
if exist "database\myexa.pid" (
    set /p MYEXA_PID=<database\myexa.pid
    taskkill /f /PID !MYEXA_PID! >nul 2>&1
    del /q "database\myexa.pid" >nul 2>&1
)
