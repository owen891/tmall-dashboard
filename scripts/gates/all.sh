#!/bin/bash
# scripts/gates/all.sh
# 运行所有门控

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

DRY_RUN=false
if [ "$1" == "--dry-run" ]; then
    DRY_RUN=true
fi

echo "========================================"
echo "[GATES] 运行所有质量门控"
echo "========================================"
echo ""

PASSED=0
FAILED=0
SKIPPED=0
STATE_FILE="$PROJECT_ROOT/.agent/state/current.json"

# 门控列表（按顺序）
GATES=("G1" "G2" "G3" "G4" "G5" "G6" "G7")

for GATE in "${GATES[@]}"; do
    echo "[$GATE] 检查..."

    if [ "$DRY_RUN" == "true" ]; then
        echo "[$GATE] ℹ️ 干运行模式，跳过"
        SKIPPED=$((SKIPPED+1))
        continue
    fi

    VERIFY_SCRIPT="$SCRIPT_DIR/${GATE}-verify.sh"

    if [ -f "$VERIFY_SCRIPT" ]; then
        if bash "$VERIFY_SCRIPT"; then
            echo "[$GATE] ✅ 通过"
            PASSED=$((PASSED+1))

            mkdir -p "$PROJECT_ROOT/.agent/state"
            if command -v jq >/dev/null 2>&1; then
                if [ ! -s "$STATE_FILE" ]; then
                    echo '{"gates":{}}' > "$STATE_FILE"
                fi
                tmp_file="${STATE_FILE}.tmp"
                jq --arg gate "$GATE" --arg ts "$(date -Iseconds)" \
                    '.gates[$gate] = {"status":"passed","verified_at":$ts}' \
                    "$STATE_FILE" > "$tmp_file" && mv "$tmp_file" "$STATE_FILE"
            else
                echo "{\"gates\": {\"$GATE\": {\"status\": \"passed\"}}}" > "$STATE_FILE"
            fi
        else
            echo "[$GATE] ❌ 失败"
            FAILED=$((FAILED+1))
        fi
    else
        echo "[$GATE] ⚠️ 缺少验证脚本"
        SKIPPED=$((SKIPPED+1))
    fi
    echo ""
done

echo "========================================"
echo "[GATES] 结果: $PASSED 通过, $FAILED 失败, $SKIPPED 跳过"
echo "========================================"

if [ "$DRY_RUN" == "true" ]; then
    echo "[GATES] ℹ️ 干运行完成，未执行实际门控"
    exit 0
elif [ $FAILED -eq 0 ] && [ $SKIPPED -eq 0 ]; then
    echo "[GATES] ✅ 所有门控通过"
    exit 0
elif [ $FAILED -eq 0 ]; then
    echo "[GATES] ⚠️ 无失败门控，但存在跳过项，不能声称全部通过"
    exit 0
else
    echo "[GATES] ❌ 有门控未通过"
    exit 1
fi
