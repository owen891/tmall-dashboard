@echo off
chcp 65001 > nul
echo ========================================
echo   复制原始数据文件
echo ========================================
echo.
cd /d "%~dp0"

python copy_data.py

if errorlevel 1 (
    echo.
    echo 尝试使用 py 命令...
    py copy_data.py
)

echo.
echo ========================================
echo 操作完成！
echo ========================================
pause
