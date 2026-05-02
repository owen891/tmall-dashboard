#!/bin/bash
# scripts/hooks/check-dangerous-file.sh
# 检查危险文件修改

FILEPATH="${CLAUDE_FILE_PATH:-$FILEPATH}"

if [ -z "$FILEPATH" ]; then
    exit 0
fi

# 危险模式
DANGEROUS_PATTERNS=(
    '\.env$'
    '\.env\.'
    'secret'
    'credential'
    'token'
    'password'
    'private.*key'
    '\.key$'
    '\.pem$'
    '\.p12$'
    'migration.*sql'
    'schema.*sql'
    'config\.ya?ml$'
)

for pattern in "${DANGEROUS_PATTERNS[@]}"; do
    if echo "$FILEPATH" | grep -qiE "$pattern"; then
        echo "[HOOK 🛡️] BLOCKED: 危险文件修改"
        echo "  文件: $FILEPATH"
        echo "  匹配: $pattern"
        echo "  操作: 需要人工确认"
        exit 2
    fi
done

exit 0
