#!/bin/bash
# 红线检查 - R3: 零硬编码密钥

echo "🔒 红线检查 R3: 零硬编码密钥"
echo "=========================================="

FOUND=0

# 检查前端文件中的密钥模式
echo "检查前端代码..."
for pattern in "password\s*=" "secret\s*=" "apiKey\s*=" "api_key\s*=" "token\s*=" "privateKey"; do
    RESULTS=$(grep -rn "$pattern" frontend/src --include="*.vue" --include="*.js" 2>/dev/null | grep -v "node_modules" | grep -v "//.*$pattern")
    if [ -n "$RESULTS" ]; then
        echo "❌ 发现硬编码密钥:"
        echo "$RESULTS"
        FOUND=1
    fi
done

# 检查后端文件中的密钥模式
echo "检查后端代码..."
for pattern in "password\s*=" "secret\s*=" "apiKey\s*=" "api_key\s*=" "token\s*="; do
    RESULTS=$(grep -rn "$pattern" backend/app --include="*.py" 2>/dev/null | grep -v "#.*$pattern" | grep -v '".*"')
    if [ -n "$RESULTS" ]; then
        echo "❌ 发现硬编码密钥:"
        echo "$RESULTS"
        FOUND=1
    fi
done

echo ""
if [ $FOUND -eq 0 ]; then
    echo "✅ R3 检查通过: 未发现硬编码密钥"
    exit 0
else
    echo "❌ R3 检查失败: 发现硬编码密钥"
    exit 1
fi
