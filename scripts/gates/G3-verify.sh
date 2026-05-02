#!/bin/bash
# scripts/gates/G3-verify.sh
# 验证TDD合规

set -e

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
source "$PROJECT_ROOT/scripts/lib/project-config.sh"
ERRORS=0
CHECKED=0

echo "[G3] TDD合规验证..."

STACK="$(detect_stack)"

if [ "$STACK" = "none" ]; then
    echo "[G3] ℹ️ 未检测到已配置技术栈，TDD 门控不适用"
    exit 0
fi

if ! stack_exists "$STACK"; then
    echo "[G3] ❌ 未知技术栈: $STACK"
    exit 1
fi

if [ "$STACK" != "go" ]; then
    echo "[G3] ℹ️ $STACK 技术栈未配置文件级 TDD 检查，TDD 门控不适用"
    exit 0
fi

while IFS= read -r impl_file; do
    CHECKED=$((CHECKED+1))
    test_file="${impl_file%.go}_test.go"

    if [ ! -f "$test_file" ]; then
        echo "[G3] ❌ 实现文件缺少对应测试: $impl_file"
        ERRORS=$((ERRORS+1))
        continue
    fi

    # 比较修改时间（需要git支持）
    if [ -d "$PROJECT_ROOT/.git" ]; then
        test_time=$(git log -1 --format=%ct -- "$test_file" 2>/dev/null || echo "0")
        impl_time=$(git log -1 --format=%ct -- "$impl_file" 2>/dev/null || echo "0")

        if [ "$test_time" -lt "$impl_time" ]; then
            echo "[G3] ❌ 实现比测试新: $impl_file"
            ERRORS=$((ERRORS+1))
        fi
    else
        # 无git时使用文件修改时间
        if [ "$test_file" -ot "$impl_file" ]; then
            echo "[G3] ❌ 实现比测试新: $impl_file"
            ERRORS=$((ERRORS+1))
        fi
    fi
done < <(find "$PROJECT_ROOT" -name "*.go" -not -name "*_test.go" -not -path "*/vendor/*" -type f)

if [ "$CHECKED" -eq 0 ]; then
    echo "[G3] ℹ️ 未检测到 Go 实现文件"
    exit 0
fi

if [ $ERRORS -eq 0 ]; then
    echo "[G3] ✅ TDD合规"
    exit 0
else
    echo "[G3] ❌ 存在先实现后测试的文件"
    exit 1
fi
