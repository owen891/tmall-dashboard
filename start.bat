@echo off
echo ========================================
echo   Haibeihai Dashboard - Start Service
echo ========================================
echo.
cd /d "%~dp0"

echo Starting application...
echo.
echo Service URL: http://localhost:5000
echo.
echo Press Ctrl+C to stop
echo ========================================
echo.

python app.py

if errorlevel 1 (
    echo.
    echo Trying with py command...
    py app.py
)

pause
