@echo off
chcp 65001 > nul
echo ========================================
echo   海贝海数据仪表盘 - 启动服务
echo ========================================
echo.
cd /d "%~dp0"

echo 正在启动应用...
echo.
echo 服务地址: http://localhost:5000
echo.
echo 按 Ctrl+C 停止服务
echo ========================================
echo.

python app.py

if errorlevel 1 (
    echo.
    echo 尝试使用 py 命令...
    py app.py
)

pause
