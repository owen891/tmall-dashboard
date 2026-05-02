#!/bin/bash
# scripts/redlines/R2-check.sh
# 零静默失败检查

set -e

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
ERRORS=0

echo "[REDLINE R2] 零静默失败检查..."

# 查找Go文件中的空error处理
find "$PROJECT_ROOT" -name "*.go" -type f | while read file; do
    # 查找 if err != nil { } 或 if err != nil { //... }
    if grep -nE 'if\s+err\s*!=\s*nil\s*\{\s*(//[^\n]*)?\s*\}' "$file" > /dev/null 2>&1; then
        echo "[R2] ❌ 空error处理块: $file"
        grep -nE 'if\s+err\s*!=\s*nil\s*\{\s*(//[^\n]*)?\s*\}' "$file" | head -3
        ERRORS=$((ERRORS+1))
    fi
done

if [ $ERRORS -eq 0 ]; then
    echo "[R2] ✅ 通过"
    exit 0
else
    exit 1
fi
