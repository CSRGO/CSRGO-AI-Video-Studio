#!/usr/bin/env bash
# CSRGO AI Video Studio - Git Bash Setup Script
set -e

echo "==================================================="
echo "    CSRGO AI VIDEO STUDIO - GIT BASH SETUP"
echo "==================================================="

# 1. Environment Config
if [ ! -f ".env" ]; then
    if [ -f ".env.example" ]; then
        echo "[1/6] Initializing .env configuration from .env.example..."
        cp .env.example .env
    fi
else
    echo "[1/6] Configuration file (.env) exists [OK]"
fi

# 2. Python Virtual Environment
if [ ! -d ".venv" ]; then
    echo "[2/6] Creating Python virtual environment..."
    python -m venv .venv
else
    echo "[2/6] Virtual environment exists (.venv) [OK]"
fi

# Determine python executable in venv
if [ -f "./.venv/Scripts/python.exe" ]; then
    PY_BIN="./.venv/Scripts/python.exe"
elif [ -f "./.venv/bin/python" ]; then
    PY_BIN="./.venv/bin/python"
else
    PY_BIN="python"
fi

# 3. Python Dependencies
echo "[3/6] Installing Python production packages..."
"$PY_BIN" -m pip install --upgrade pip
"$PY_BIN" -m pip install -r requirements.txt

# 4. Playwright Headless Browser
echo "[4/6] Installing Playwright Chromium browser..."
"$PY_BIN" -m playwright install chromium

# 5. Kokoro TTS Offline Models
echo "[5/6] Verifying / downloading Kokoro TTS model weights..."
"$PY_BIN" -m backend.services.tts_service

# 6. Frontend Dependencies
echo "[6/6] Installing frontend dependencies..."
if [ -d "frontend" ]; then
    cd frontend
    npm install
    cd ..
fi

echo ""
echo "==================================================="
echo "    VERIFYING INSTALLATION & SUBSYSTEMS"
echo "==================================================="
"$PY_BIN" verify_installation.py

echo ""
echo "==================================================="
echo "Setup complete! Run start_windows.bat or launch backend and frontend."
echo "==================================================="
