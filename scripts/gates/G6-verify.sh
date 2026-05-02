#!/bin/bash
# scripts/gates/G6-verify.sh
# 验证覆盖率

set -e

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
source "$PROJECT_ROOT/scripts/lib/project-config.sh"
COVERAGE_FILE="$PROJECT_ROOT/.agent/logs/coverage.out"

echo "[G6] 覆盖率验证..."

STACK="$(detect_stack)"

if [ "$STACK" = "none" ]; then
    echo "[G6] ℹ️ 未检测到已配置技术栈，coverage 门控不适用"
    exit 0
fi

if ! stack_exists "$STACK"; then
    echo "[G6] ❌ 未知技术栈: $STACK"
    exit 1
fi

COMMAND="$(gate_command "$STACK" coverage)"
if ! run_gate_command "$STACK" coverage "$COMMAND" G6; then
    echo "[G6] ❌ coverage 命令失败"
    exit 1
fi

if [ "$STACK" != "go" ]; then
    echo "[G6] ✅ coverage 命令通过"
    exit 0
fi

# 解析覆盖率
if [ -f "$COVERAGE_FILE" ]; then
    # Go覆盖率格式: coverage: 80.5% of statements
    COVERAGE=$(go tool cover -func="$COVERAGE_FILE" | tail -1 | awk '{print $3}' | sed 's/%//')

    if [ -n "$COVERAGE" ]; then
        echo "[G6] 覆盖率: ${COVERAGE}%"

        # 比较（bash浮点比较）
        THRESHOLD="$(coverage_threshold)"
        if awk "BEGIN {exit !($COVERAGE >= $THRESHOLD)}"; then
            echo "[G6] ✅ 覆盖率达标 (≥${THRESHOLD}%)"
            exit 0
        else
            echo "[G6] ❌ 覆盖率不足 (<${THRESHOLD}%)"
            exit 1
        fi
    else
        echo "[G6] ⚠️ 无法解析覆盖率"
        exit 1
    fi
else
    echo "[G6] ❌ 无法生成覆盖率报告"
    exit 1
fi
