#!/bin/bash
# scripts/update-doc-index.sh
# 更新文档索引

set -e

echo "[SCRIPT] 更新文档索引..."

# 生成规范文档索引
cat > docs/standards/_index.md << 'EOF'
# 规范文档索引

自动生成于 $(date)

## 通用规范

EOF

for f in docs/standards/common/*.md; do
    if [ -f "$f" ]; then
        name=$(basename "$f" .md)
        echo "- [$name](common/$name.md)" >> docs/standards/_index.md
    fi
done

echo "[SCRIPT] 索引更新完成"
