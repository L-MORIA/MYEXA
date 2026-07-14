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
echo Installing dependencies...
pip install -q -r backend\requirements.txt 2>nul

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
start http://localhost:3005
echo.
echo Close this window to stop the server.
pause >nul
taskkill /f /im python.exe >nul 2>&1
