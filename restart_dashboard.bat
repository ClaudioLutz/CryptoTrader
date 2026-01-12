@echo off
REM Restart dashboard script for Windows

echo === Restarting Dashboard ===
echo.

REM Kill existing dashboard on port 8081
echo [1/2] Stopping existing dashboard...
for /f "tokens=5" %%a in ('netstat -ano ^| findstr ":8081.*LISTENING"') do (
    taskkill /F /PID %%a >NUL 2>&1
)
timeout /t 2 /nobreak >NUL
echo   Done.

REM Start dashboard
echo [2/2] Starting dashboard...
start cmd /c "cd /d %~dp0 && start_dashboard.bat"

echo.
echo === Dashboard Restarted ===
echo   URL: http://127.0.0.1:8081
echo.
