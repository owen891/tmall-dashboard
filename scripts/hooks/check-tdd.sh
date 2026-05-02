#!/bin/bash
# scripts/hooks/check-tdd.sh
# 检查TDD合规

FILEPATH="${CLAUDE_FILE_PATH:-$FILEPATH}"

if [ -z "$FILEPATH" ]; then
    exit 0
fi

# 只检查Go实现文件
if echo "$FILEPATH" | grep -qE '\.go$' && ! echo "$FILEPATH" | grep -qE '_test\.go$'; then
    TEST_FILE="${FILEPATH%.go}_test.go"

    if [ ! -f "$TEST_FILE" ]; then
        echo "[HOOK TDD] ⚠️ 实现文件缺少对应测试"
        echo "  实现: $FILEPATH"
        echo "  测试: $TEST_FILE (不存在)"
        echo ""
        echo "建议:"
        echo "  1. 先创建 $TEST_FILE"
        echo "  2. 编写失败的测试 (RED)"
        echo "  3. 再实现功能 (GREEN)"
        # 返回0作为警告，不阻断
    fi
fi

exit 0
