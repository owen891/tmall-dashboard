#!/bin/bash
# scripts/validate-config.sh
# 验证配置有效性

set -e

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ERRORS=0

echo "========================================"
echo "[VALIDATE] 配置验证"
echo "========================================"
echo ""

# 检查必需文件
echo "[CHECK] 必需文件..."
REQUIRED_FILES=(
    "CLAUDE.md"
    "README.md"
    "Makefile"
    ".agent/project.json"
    ".claude/settings.json"
    ".claude/workflow.json"
)

for file in "${REQUIRED_FILES[@]}"; do
    if [ -f "$PROJECT_ROOT/$file" ]; then
        echo "[OK] $file"
    else
        echo "[ERROR] 缺少: $file"
        ERRORS=$((ERRORS+1))
    fi
done
echo ""

# 检查脚本可执行
echo "[CHECK] 脚本可执行..."
REQUIRED_SCRIPTS=(
    "scripts/preflight/all.sh"
    "scripts/gates/all.sh"
    "scripts/checkpoint/save.sh"
)

for script in "${REQUIRED_SCRIPTS[@]}"; do
    if [ -x "$PROJECT_ROOT/$script" ]; then
        echo "[OK] $script"
    else
        if [ -f "$PROJECT_ROOT/$script" ]; then
            echo "[WARN] 不可执行: $script (尝试修复...)"
            chmod +x "$PROJECT_ROOT/$script"
        else
            echo "[ERROR] 缺少: $script"
            ERRORS=$((ERRORS+1))
        fi
    fi
done
echo ""

# 检查JSON有效性
echo "[CHECK] JSON文件..."
if command -v jq &>/dev/null; then
    for json in "$PROJECT_ROOT/.claude"/*.json "$PROJECT_ROOT/.agent"/*.json; do
        if [ -f "$json" ]; then
            if jq empty "$json" 2>/dev/null; then
                echo "[OK] ${json#$PROJECT_ROOT/}"
            else
                echo "[ERROR] 无效JSON: ${json#$PROJECT_ROOT/}"
                ERRORS=$((ERRORS+1))
            fi
        fi
    done
else
    echo "[SKIP] jq未安装，跳过JSON验证"
fi
echo ""

# 检查换行格式
echo "[CHECK] Shell脚本换行..."
CRLF_FILES=$(find "$PROJECT_ROOT" -path "$PROJECT_ROOT/.git" -prune -o -name "*.sh" -type f -print0 | xargs -0 grep -Il $'\r' 2>/dev/null || true)
if [ -n "$CRLF_FILES" ]; then
    echo "[ERROR] Shell脚本包含CRLF换行:"
    echo "$CRLF_FILES"
    ERRORS=$((ERRORS+1))
else
    echo "[OK] Shell脚本均为LF换行"
fi
echo ""

# 总结
echo "========================================"
if [ $ERRORS -eq 0 ]; then
    echo "[VALIDATE] ✅ 配置有效"
    exit 0
else
    echo "[VALIDATE] ❌ 发现 $ERRORS 个问题"
    exit 1
fi
