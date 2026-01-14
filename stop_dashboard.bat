@echo off
REM Stop dashboard script for Windows

echo === Stopping Dashboard ===
echo.

REM Kill existing dashboard on port 8081
for /f "tokens=5" %%a in ('netstat -ano ^| findstr ":8081.*LISTENING"') do (
    echo Stopping process PID %%a...
    taskkill /F /PID %%a >NUL 2>&1
)

echo.
echo === Dashboard Stopped ===
