@echo off
echo ========================================
echo   Batch Import Data
echo ========================================
echo.
cd /d "%~dp0"

echo Importing data...
echo.
python scripts/import_data.py --batch data/raw

if errorlevel 1 (
    echo.
    echo Trying with py command...
    py scripts/import_data.py --batch data/raw
)

echo.
echo ========================================
echo Import complete!
echo ========================================
pause
