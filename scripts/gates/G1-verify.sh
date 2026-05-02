#!/bin/bash
# scripts/gates/G1-verify.sh
# 验证探索阶段完成

set -e

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
STATE_FILE="$PROJECT_ROOT/.agent/state/explore.json"

ERRORS=0

echo "[G1] 探索阶段验证..."

# 检查状态文件
if [ ! -f "$STATE_FILE" ]; then
    echo "[G1] ❌ 缺少探索记录: $STATE_FILE"
    echo "[HINT] 运行探索命令后自动保存"
    exit 1
fi

# 验证文件数量
FILE_COUNT=$(jq -r '.files | length' "$STATE_FILE" 2>/dev/null || echo "0")
if [ "$FILE_COUNT" -lt 3 ]; then
    echo "[G1] ❌ 只读了 $FILE_COUNT 个文件，需要 ≥3"
    ERRORS=$((ERRORS+1))
else
    echo "[G1] ✅ 已读 $FILE_COUNT 个文件"
fi

# 验证主要矛盾
if ! jq -e '.main_contradiction' "$STATE_FILE" &>/dev/null; then
    echo "[G1] ❌ 未识别主要矛盾"
    ERRORS=$((ERRORS+1))
else
    echo "[G1] ✅ 已识别主要矛盾"
fi

# 验证技能检查
if ! jq -e '.skills_checked' "$STATE_FILE" &>/dev/null; then
    echo "[G1] ⚠️ 未检查可用技能"
fi

if [ $ERRORS -eq 0 ]; then
    exit 0
else
    exit 1
fi
