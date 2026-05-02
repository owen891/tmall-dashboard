#!/bin/bash
# scripts/gates/G2-verify.sh
# 验证规划阶段完成

set -e

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
ERRORS=0

echo "[G2] 规划阶段验证..."

# 查找最新的 plan.md
PLAN_FILE=$(find "$PROJECT_ROOT/docs/plans" -name "plan.md" -type f 2>/dev/null | head -1)

if [ -z "$PLAN_FILE" ]; then
    echo "[G2] ❌ 缺少 plan.md"
    echo "[HINT] 运行: make plan NAME=xxx"
    exit 1
fi

echo "[G2] 检查: $PLAN_FILE"

# 检查功能边界
if grep -q "功能边界\|功能范围\|scope\|边界" "$PLAN_FILE"; then
    echo "[G2] ✅ 包含功能边界"
else
    echo "[G2] ❌ 缺少功能边界"
    ERRORS=$((ERRORS+1))
fi

# 检查异常契约
if grep -q "异常\|错误\|error\|exception" "$PLAN_FILE"; then
    echo "[G2] ✅ 包含异常处理"
else
    echo "[G2] ❌ 缺少异常处理"
    ERRORS=$((ERRORS+1))
fi

# 检查回滚方案
if grep -q "回滚\|rollback\|回退" "$PLAN_FILE"; then
    echo "[G2] ✅ 包含回滚方案"
else
    echo "[G2] ❌ 缺少回滚方案"
    ERRORS=$((ERRORS+1))
fi

if [ $ERRORS -eq 0 ]; then
    exit 0
else
    exit 1
fi
