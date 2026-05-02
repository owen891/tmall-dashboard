#!/bin/bash
# scripts/hooks/check-context.sh
# 检查外部调用是否有context

FILEPATH="${CLAUDE_FILE_PATH:-$FILEPATH}"

if [ -z "$FILEPATH" ] || [ ! -f "$FILEPATH" ]; then
    exit 0
fi

# 只检查Go文件
if ! echo "$FILEPATH" | grep -qE '\.go$'; then
    exit 0
fi

# 检查外部调用模式
EXTERNAL_CALLS=(
    'http\.(Get|Post|Do)'
    'sql\.'
    'grpc\.'
    'redis\.'
)

NEEDS_CONTEXT=false
for pattern in "${EXTERNAL_CALLS[@]}"; do
    if grep -qE "$pattern" "$FILEPATH" 2>/dev/null; then
        NEEDS_CONTEXT=true
        break
    fi
done

if [ "$NEEDS_CONTEXT" = true ]; then
    # 检查是否有context使用
    if ! grep -qE 'context\.(Background|WithTimeout|WithCancel)' "$FILEPATH" 2>/dev/null && \
       ! grep -qE 'ctx\s+context\.Context' "$FILEPATH" 2>/dev/null; then
        echo "[HOOK] ⚠️ 外部调用建议使用 context"
        echo "  文件: $FILEPATH"
        echo "  建议: 添加 ctx context.Context 参数或使用 context.Background()"
    fi
fi

exit 0
