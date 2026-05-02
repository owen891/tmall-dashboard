#!/bin/bash
# scripts/redlines/R3-check.sh
# 零硬编码密钥检查

set -e

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
ERRORS=0

echo "[REDLINE R3] 零硬编码密钥检查..."

# 敏感模式
SENSITIVE_PATTERNS=(
    'password\s*=\s*"[^"]+"'
    'secret\s*=\s*"[^"]+"'
    'token\s*=\s*"[^"]+"'
    'api_key\s*=\s*"[^"]+"'
    'private_key\s*=\s*"[^"]+"'
)

for pattern in "${SENSITIVE_PATTERNS[@]}"; do
    matches=$(grep -rE "$pattern" --include="*.go" "$PROJECT_ROOT" 2>/dev/null || true)
    if [ -n "$matches" ]; then
        echo "[R3] ❌ 发现硬编码密钥:"
        echo "$matches" | head -5
        ERRORS=$((ERRORS+1))
    fi
done

# 检查.env文件
if find "$PROJECT_ROOT" -name ".env*" -type f 2>/dev/null | grep -q .; then
    echo "[R3] ⚠️ 发现.env文件，请确保已加入.gitignore"
fi

if [ $ERRORS -eq 0 ]; then
    echo "[R3] ✅ 通过"
    exit 0
else
    exit 1
fi
