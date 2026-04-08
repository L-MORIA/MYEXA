@echo off
REM MYEXA - Advanced Search Engine Launcher
REM This script installs dependencies and starts the application

echo.
echo ========================================
echo   MYEXA - Advanced Search Engine
echo ========================================
echo.

REM Check if Python is installed
python --version >nul 2>&1
if errorlevel 1 (
    echo Error: Python is not installed or not in PATH
    pause
    exit /b 1
)

REM Create .env file if it doesn't exist
if not exist ".env" (
    echo Creating .env file...
    copy .env.example .env
    echo Please edit .env and add your EXA_API_KEY
    pause
)

REM Create database directory
if not exist "database" mkdir database

REM Install dependencies
echo.
echo Installing dependencies...
pip install -r backend/requirements.txt -q

if errorlevel 1 (
    echo Error: Failed to install dependencies
    pause
    exit /b 1
)

REM Start the application
echo.
echo Starting MYEXA on http://localhost:3005
echo Press Ctrl+C to stop the server
echo.

python backend/app.py

pause
