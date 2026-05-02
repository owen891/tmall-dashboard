#!/bin/bash
# 环境预检脚本

echo "🔍 嗨贝海数据仪表盘 - 环境预检"
echo "=========================================="

# 检查 Node.js
echo -n "✓ Node.js 版本: "
if command -v node &> /dev/null; then
    node --version
else
    echo "❌ 未安装"
fi

# 检查 npm
echo -n "✓ npm 版本: "
if command -v npm &> /dev/null; then
    npm --version
else
    echo "❌ 未安装"
fi

# 检查 Python
echo -n "✓ Python 版本: "
if command -v python3 &> /dev/null; then
    python3 --version
else
    echo "❌ 未安装"
fi

# 检查前端目录
echo ""
echo "📁 前端项目检查:"
if [ -d "frontend" ]; then
    echo "  ✓ frontend/ 目录存在"
    if [ -f "frontend/package.json" ]; then
        echo "  ✓ package.json 存在"
    else
        echo "  ❌ package.json 不存在"
    fi
    if [ -d "frontend/node_modules" ]; then
        echo "  ✓ node_modules 已安装"
    else
        echo "  ⚠ node_modules 未安装（需要运行 npm install）"
    fi
else
    echo "  ❌ frontend/ 目录不存在"
fi

# 检查后端目录
echo ""
echo "📁 后端项目检查:"
if [ -d "backend" ]; then
    echo "  ✓ backend/ 目录存在"
    if [ -f "backend/requirements.txt" ]; then
        echo "  ✓ requirements.txt 存在"
    fi
else
    echo "  ❌ backend/ 目录不存在"
fi

# 检查文档
echo ""
echo "📚 文档检查:"
if [ -f "CLAUDE.md" ]; then
    echo "  ✓ CLAUDE.md 存在"
else
    echo "  ⚠ CLAUDE.md 不存在"
fi

if [ -d "docs" ]; then
    echo "  ✓ docs/ 目录存在"
else
    echo "  ⚠ docs/ 目录不存在"
fi

echo ""
echo "=========================================="
echo "✅ 预检完成"
