#!/bin/bash
# MYEXA - Advanced Search Engine Launcher (Linux/Mac)

echo ""
echo "========================================"
echo "  MYEXA - Advanced Search Engine"
echo "========================================"
echo ""

# Check if Python is installed
if ! command -v python3 &> /dev/null; then
    echo "Error: Python 3 is not installed"
    exit 1
fi

# Create .env file if it doesn't exist
if [ ! -f ".env" ]; then
    echo "Creating .env file..."
    cp .env.example .env
    echo "Please edit .env and add your EXA_API_KEY"
    read -p "Press Enter to continue..."
fi

# Create database directory
mkdir -p database

# Install dependencies
echo ""
echo "Installing dependencies..."
pip3 install -r backend/requirements.txt -q

if [ $? -ne 0 ]; then
    echo "Error: Failed to install dependencies"
    exit 1
fi

# Start the application
echo ""
echo "Starting MYEXA on http://localhost:3005"
echo "Press Ctrl+C to stop the server"
echo ""

python3 backend/app.py
