@echo off
TITLE CSRGO AI Video Studio Launcher

set "ROOT_DIR=%~dp0"
if "%ROOT_DIR:~-1%"=="\" set "ROOT_DIR=%ROOT_DIR:~0,-1%"
cd /d "%ROOT_DIR%"

echo ===================================================
echo     CSRGO AI VIDEO STUDIO - LOCAL STUDIO
echo ===================================================
echo Project Directory: %ROOT_DIR%
echo.

:: 0. Verify .env
if not exist "%ROOT_DIR%\.env" (
    if exist "%ROOT_DIR%\.env.example" (
        echo [INFO] Creating .env from .env.example...
        copy "%ROOT_DIR%\.env.example" "%ROOT_DIR%\.env" >nul
    )
)

:: 1. Check Ollama
echo [1/4] Verifying Ollama local model service...
curl.exe -s http://127.0.0.1:11434/api/tags >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo [INFO] Starting local Ollama service in background...
    start "" ollama serve >nul 2>&1
    ping 127.0.0.1 -n 4 >nul
) else (
    echo [OK] Ollama service is online.
)

:: 2. Check Frontend node_modules
echo [2/4] Verifying Frontend dependencies...
if not exist "%ROOT_DIR%\frontend\node_modules" (
    echo [INFO] Installing frontend packages...
    cd /d "%ROOT_DIR%\frontend"
    call npm.cmd install
    cd /d "%ROOT_DIR%"
) else (
    echo [OK] Frontend packages verified.
)

:: 3. Start FastAPI Backend
echo [3/4] Starting FastAPI Backend on http://127.0.0.1:8000 ...
start "CSRGO Backend Server" cmd /k "cd /d "%ROOT_DIR%" && "%ROOT_DIR%\.venv\Scripts\python.exe" -m uvicorn backend.main:app --host 127.0.0.1 --port 8000"

:: 4. Start Vite React Frontend
echo [4/4] Starting Vite React Frontend on http://127.0.0.1:5173 ...
start "CSRGO Studio Frontend" cmd /k "cd /d "%ROOT_DIR%\frontend" && npm.cmd run dev"

:: Wait for servers to spin up
ping 127.0.0.1 -n 4 >nul

:: Open browser automatically
start "" "http://127.0.0.1:5173"

echo.
echo ===================================================
echo   CSRGO AI Video Studio is running!
echo   Dashboard:  http://127.0.0.1:5173
echo   API Docs:   http://127.0.0.1:8000/docs
echo ===================================================
echo Close the respective terminal windows to stop the servers.
pause
