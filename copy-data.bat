@echo off
echo ========================================
echo   Copy Raw Data Files
echo ========================================
echo.
cd /d "%~dp0"

python copy_data.py

if errorlevel 1 (
    echo.
    echo Trying with py command...
    py copy_data.py
)

echo.
echo ========================================
echo Done!
echo ========================================
pause
