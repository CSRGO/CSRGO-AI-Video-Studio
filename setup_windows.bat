@echo off
TITLE CSRGO AI Video Studio - Windows Setup
echo ===================================================
echo     CSRGO AI VIDEO STUDIO - ENVIRONMENT SETUP
echo ===================================================
echo.

:: 1. Environment Config
if not exist ".env" (
    if exist ".env.example" (
        echo [1/6] Initializing .env configuration from .env.example...
        copy .env.example .env >nul
    )
) else (
    echo [1/6] Configuration file (.env) exists [OK]
)

:: 2. Python Virtual Environment
if not exist ".venv" (
    echo [2/6] Creating Python virtual environment (.venv)...
    python -m venv .venv
    if %ERRORLEVEL% NEQ 0 (
        echo [ERROR] Failed to create virtual environment. Ensure Python 3.11+ is installed and on PATH.
        pause
        exit /b 1
    )
) else (
    echo [2/6] Python virtual environment exists (.venv) [OK]
)

:: 3. Python Dependencies
echo [3/6] Installing Python production packages...
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
if %ERRORLEVEL% NEQ 0 (
    echo [ERROR] Package installation encountered an error.
    pause
    exit /b 1
)

:: 4. Playwright Headless Browser
echo [4/6] Installing Playwright Chromium browser...
.\.venv\Scripts\python.exe -m playwright install chromium

:: 5. Kokoro TTS Offline Models
echo [5/6] Verifying / downloading Kokoro TTS model weights...
.\.venv\Scripts\python.exe -m backend.services.tts_service

:: 6. Frontend Dependencies
echo [6/6] Installing frontend dependencies...
if exist "frontend" (
    cd frontend
    call npm.cmd ci
    cd ..
)

echo.
echo ===================================================
echo Installing native video renderers (Node 22+)...
call npm.cmd ci --prefix renderer
if errorlevel 1 exit /b 1

echo     VERIFYING INSTALLATION & SUBSYSTEMS
echo ===================================================
.\.venv\Scripts\python.exe verify_installation.py

echo.
echo ===================================================
echo Setup complete! Run start_windows.bat to launch the studio.
echo ===================================================
pause
