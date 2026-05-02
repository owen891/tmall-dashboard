#!/bin/bash
# scripts/checkpoint/save.sh
# 保存状态检查点

set -e

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
STATE_DIR="$PROJECT_ROOT/.agent/state"
CHECKPOINT_DIR="$PROJECT_ROOT/.agent/checkpoints"

mkdir -p "$STATE_DIR" "$CHECKPOINT_DIR"

TIMESTAMP=$(date +%Y%m%d-%H%M%S)
PHASE=${1:-"unknown"}

# 构建状态JSON
cat > "$STATE_DIR/current.json" << EOF
{
  "timestamp": "$(date -Iseconds)",
  "phase": "$PHASE",
  "git_branch": "$(git branch --show-current 2>/dev/null || echo 'unknown')",
  "git_commit": "$(git rev-parse --short HEAD 2>/dev/null || echo 'unknown')",
  "files_modified": $(git diff --name-only 2>/dev/null | jq -R . | jq -s . || echo '[]'),
  "environment": {
    "go_version": "$(go version 2>/dev/null || echo 'not installed')",
    "working_dir": "$(pwd)"
  }
}
EOF

# 创建时间戳备份
cp "$STATE_DIR/current.json" "$CHECKPOINT_DIR/$TIMESTAMP.json"

# 只保留最近10个检查点
ls -t "$CHECKPOINT_DIR"/*.json 2>/dev/null | tail -n +11 | xargs rm -f 2>/dev/null || true

echo "[CHECKPOINT] 已保存: $PHASE at $TIMESTAMP"
