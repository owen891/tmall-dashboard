@echo off
chcp 65001 > nul
echo ========================================
echo   批量导入数据
echo ========================================
echo.
cd /d "%~dp0"

echo 正在导入数据...
echo.
python scripts/import_data.py --batch data/raw

if errorlevel 1 (
    echo.
    echo 尝试使用 py 命令...
    py scripts/import_data.py --batch data/raw
)

echo.
echo ========================================
echo 导入完成！
echo ========================================
pause
