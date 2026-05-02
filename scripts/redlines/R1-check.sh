#!/bin/bash
# scripts/redlines/R1-check.sh
# 零数据丢失检查

set -e

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
ERRORS=0

echo "[REDLINE R1] 零数据丢失检查..."

# 检查SQL文件
for sql_file in $(find "$PROJECT_ROOT" -name "*.sql" -type f 2>/dev/null); do
    # 检查是否有DROP/DELETE/UPDATE
    if grep -qiE '^\s*DROP\s+(TABLE|DATABASE)' "$sql_file"; then
        echo "[R1] ⚠️ 发现DROP语句: $sql_file"
        # 检查是否有备份注释
        if ! grep -qiE '--\s*backup:|backup:|--\s*down' "$sql_file"; then
            echo "[R1] ❌ 缺少备份/回滚说明"
            ERRORS=$((ERRORS+1))
        fi
    fi
done

# 检查migration文件是否有down
for mig_file in $(find "$PROJECT_ROOT" -name "*.sql" -type f 2>/dev/null | grep -i migrat); do
    if ! grep -qiE '^\s*--\s*down\s*$|@down' "$mig_file"; then
        echo "[R1] ❌ migration缺少DOWN: $mig_file"
        ERRORS=$((ERRORS+1))
    fi
done

if [ $ERRORS -eq 0 ]; then
    echo "[R1] ✅ 通过"
    exit 0
else
    exit 1
fi
