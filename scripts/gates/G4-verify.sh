#!/bin/bash
# scripts/gates/G4-verify.sh
# 验证Lint通过

set -e

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
source "$PROJECT_ROOT/scripts/lib/project-config.sh"
LINT_OUTPUT="$PROJECT_ROOT/.agent/logs/lint.json"

echo "[G4] Lint验证..."

STACK="$(detect_stack)"

if [ "$STACK" = "none" ]; then
    echo "[G4] ℹ️ 未检测到已配置技术栈，lint 门控不适用"
    exit 0
fi

if ! stack_exists "$STACK"; then
    echo "[G4] ❌ 未知技术栈: $STACK"
    exit 1
fi

COMMAND="$(gate_command "$STACK" lint)"
if ! run_gate_command "$STACK" lint "$COMMAND" G4; then
    echo "[G4] ❌ lint 命令失败"
    exit 1
fi

if [ "$STACK" != "go" ]; then
    echo "[G4] ✅ lint 命令通过"
    exit 0
fi

# 解析lint结果
if command -v jq &>/dev/null; then
    ISSUES=$(jq '.Issues | length' "$LINT_OUTPUT" 2>/dev/null || echo "0")
    if [ "$ISSUES" -eq 0 ]; then
        echo "[G4] ✅ Lint通过 (无问题)"
        exit 0
    else
        echo "[G4] ❌ 发现 $ISSUES 个问题"
        jq -r '.Issues[] | "\(.Pos.Filename):\(.Pos.Line): \(.Text)"' "$LINT_OUTPUT" | head -10
        exit 1
    fi
else
    # 无jq时的简单检查
    if grep -q '"Issues":\[\]' "$LINT_OUTPUT" || grep -q '"Issues": null' "$LINT_OUTPUT"; then
        echo "[G4] ✅ Lint通过"
        exit 0
    else
        echo "[G4] ❌ Lint发现问题"
        exit 1
    fi
fi
