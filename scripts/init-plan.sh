#!/bin/bash
# scripts/init-plan.sh
# 创建新计划

set -e

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

if [ -z "$NAME" ]; then
    echo "[ERROR] 请设置 NAME 环境变量"
    echo "  示例: NAME=my-feature make plan"
    exit 1
fi

DATE=$(date +%Y-%m-%d)
PLAN_DIR="$PROJECT_ROOT/docs/plans/$DATE-$NAME"

if [ -d "$PLAN_DIR" ]; then
    echo "[ERROR] 计划已存在: $PLAN_DIR"
    exit 1
fi

mkdir -p "$PLAN_DIR"

# 复制模板
cp "$PROJECT_ROOT/templates/plan/spec.md" "$PLAN_DIR/spec.md"
cp "$PROJECT_ROOT/templates/plan/plan.md" "$PLAN_DIR/plan.md"
cp "$PROJECT_ROOT/templates/plan/tasks.md" "$PLAN_DIR/tasks.md"

# 替换模板变量
for file in "$PLAN_DIR"/*.md; do
    sed -i "s/YYYY-MM-DD/$DATE/g" "$file" 2>/dev/null || \
        sed -i.bak "s/YYYY-MM-DD/$DATE/g" "$file" && rm -f "$file.bak"
    sed -i "s/xxx/$NAME/g" "$file" 2>/dev/null || \
        sed -i.bak "s/xxx/$NAME/g" "$file" && rm -f "$file.bak"
done

echo "[INIT] 已创建计划: $PLAN_DIR"
echo ""
echo "请编辑以下文件:"
echo "  - $PLAN_DIR/spec.md (需求)"
echo "  - $PLAN_DIR/plan.md (方案)"
echo "  - $PLAN_DIR/tasks.md (任务)"
