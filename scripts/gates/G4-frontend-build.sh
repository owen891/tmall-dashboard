#!/bin/bash
# 前端构建验证脚本

echo "🔍 检查前端构建..."

cd frontend

if [ ! -f "package.json" ]; then
    echo "❌ 错误: package.json 不存在"
    exit 1
fi

echo "✓ 运行 npm run build..."
npm run build > /tmp/build.log 2>&1

if [ $? -eq 0 ]; then
    echo "✅ 前端构建成功!"
    rm -f /tmp/build.log
    exit 0
else
    echo "❌ 前端构建失败!"
    echo ""
    echo "错误日志:"
    cat /tmp/build.log
    exit 1
fi
