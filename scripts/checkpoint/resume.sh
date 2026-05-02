#!/bin/bash
# scripts/checkpoint/resume.sh
# 恢复之前的状态

set -e

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
STATE_FILE="$PROJECT_ROOT/.agent/state/current.json"

if [ ! -f "$STATE_FILE" ]; then
    echo "[RESUME] ⚠️ 没有找到之前的状态"
    echo "[RESUME] 从 idle 阶段开始"
    exit 0
fi

PHASE=$(jq -r '.phase' "$STATE_FILE" 2>/dev/null || echo "unknown")
TIMESTAMP=$(jq -r '.timestamp' "$STATE_FILE" 2>/dev/null || echo "unknown")

echo "[RESUME] 检测到之前的状态:"
echo "  阶段: $PHASE"
echo "  时间: $TIMESTAMP"
echo ""

# 显示恢复选项
echo "恢复选项:"
echo "  1. 继续 $PHASE 阶段"
echo "  2. 重置到 idle 阶段"
echo "  3. 查看详细状态"
echo ""

# 实际项目中，Agent会根据上下文自动决定
# 这里仅输出状态信息供参考

exit 0
