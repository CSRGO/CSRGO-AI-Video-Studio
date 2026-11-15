@echo off
TITLE CSRGO AI Video Studio Shutdown
echo ===================================================
echo     CSRGO AI VIDEO STUDIO - SAFE SHUTDOWN
echo ===================================================
echo.
echo Stopping CSRGO Backend (port 8000)...
for /f "tokens=5" %%a in ('netstat -aon ^| findstr ":8000" ^| findstr "LISTENING"') do (
    echo Terminating backend process PID %%a
    taskkill /F /PID %%a >nul 2>&1
)

echo Stopping CSRGO Frontend (port 5173)...
for /f "tokens=5" %%a in ('netstat -aon ^| findstr ":5173" ^| findstr "LISTENING"') do (
    echo Terminating frontend process PID %%a
    taskkill /F /PID %%a >nul 2>&1
)

echo.
echo [OK] All CSRGO AI Video Studio processes stopped safely.
pause

