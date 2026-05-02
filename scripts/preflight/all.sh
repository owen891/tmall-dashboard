#!/bin/bash
# scripts/preflight/all.sh
# 环境预检脚本

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

ERRORS=0
WARNINGS=0

echo "========================================"
echo "[PREFLIGHT] 环境预检"
echo "========================================"
echo ""

# 检查1: Go版本
echo "[CHECK] Go版本..."
if command -v go &>/dev/null; then
    GO_VERSION=$(go version | grep -o 'go[0-9.]*' | head -1)
    echo "[OK] Go版本: $GO_VERSION"
else
    echo "[ERROR] Go未安装"
    ERRORS=$((ERRORS+1))
fi
echo ""

# 检查2: 必需工具
echo "[CHECK] 必需工具..."
REQUIRED_TOOLS=("git" "make" "jq")
for tool in "${REQUIRED_TOOLS[@]}"; do
    if command -v "$tool" &>/dev/null; then
        echo "[OK] $tool"
    else
        echo "[ERROR] 缺少工具: $tool"
        ERRORS=$((ERRORS+1))
    fi
done
echo ""

# 检查3: 推荐工具
echo "[CHECK] 推荐工具..."
OPTIONAL_TOOLS=("golangci-lint" "gosec" "gh" "rg" "fd")
for tool in "${OPTIONAL_TOOLS[@]}"; do
    if command -v "$tool" &>/dev/null; then
        echo "[OK] $tool"
    else
        echo "[WARN] 可选工具未安装: $tool"
        WARNINGS=$((WARNINGS+1))
    fi
done
echo ""

# 检查4: Graphify
echo "[CHECK] Graphify..."
if command -v graphify &>/dev/null; then
    echo "[OK] graphify 已安装"
else
    echo "[WARN] graphify 未安装"
    echo "[HINT] 运行: pip install graphifyy && graphify install"
    WARNINGS=$((WARNINGS+1))
fi
echo ""

# 检查5: 技能安装
echo "[CHECK] 技能安装状态..."
if [ -f "$HOME/.claude/skills/superpowers/installed.flag" ]; then
    echo "[OK] superpowers 已安装"
else
    echo "[WARN] superpowers 未安装"
    echo "[HINT] 运行: plugin install superpowers"
    WARNINGS=$((WARNINGS+1))
fi
echo ""

# 检查6: MCP配置
echo "[CHECK] MCP配置..."
if [ -f "$PROJECT_ROOT/.claude/settings.json" ]; then
    echo "[OK] settings.json 存在"
    if grep -q "mcpServers" "$PROJECT_ROOT/.claude/settings.json"; then
        echo "[OK] MCP服务器已配置"
    else
        echo "[WARN] MCP服务器未配置"
        WARNINGS=$((WARNINGS+1))
    fi
else
    echo "[ERROR] settings.json 不存在"
    ERRORS=$((ERRORS+1))
fi
echo ""

# 检查7: 目录结构
echo "[CHECK] 目录结构..."
REQUIRED_DIRS=(".agent/state" ".agent/checkpoints" ".agent/logs" "docs" "scripts")
for dir in "${REQUIRED_DIRS[@]}"; do
    if [ -d "$PROJECT_ROOT/$dir" ]; then
        echo "[OK] $dir"
    else
        echo "[WARN] 目录不存在: $dir"
        mkdir -p "$PROJECT_ROOT/$dir"
        echo "[FIX] 已创建: $dir"
    fi
done
echo ""

# 检查8: 状态管理
echo "[CHECK] 状态管理系统..."
if [ -w "$PROJECT_ROOT/.agent/state" ]; then
    echo "[OK] 状态目录可写"
    # 测试写入
    echo '{"test": true}' > "$PROJECT_ROOT/.agent/state/test.json" 2>/dev/null && rm "$PROJECT_ROOT/.agent/state/test.json"
    echo "[OK] 状态写入测试通过"
else
    echo "[ERROR] 状态目录不可写: .agent/state"
    ERRORS=$((ERRORS+1))
fi
echo ""

# 检查9: Git配置
echo "[CHECK] Git配置..."
if [ -d "$PROJECT_ROOT/.git" ]; then
    echo "[OK] Git仓库已初始化"
    if git config user.name &>/dev/null && git config user.email &>/dev/null; then
        echo "[OK] Git用户已配置"
    else
        echo "[WARN] Git用户未配置"
        WARNINGS=$((WARNINGS+1))
    fi
else
    echo "[WARN] 非Git仓库"
    WARNINGS=$((WARNINGS+1))
fi
echo ""

# 总结
echo "========================================"
if [ $ERRORS -eq 0 ]; then
    echo "[PREFLIGHT] ✅ 通过 ($WARNINGS 个警告)"
    echo ""
    if [ $WARNINGS -gt 0 ]; then
        echo "建议安装可选工具以获得完整体验："
        echo "  - golangci-lint: go install github.com/golangci/golangci-lint/cmd/golangci-lint@latest"
        echo "  - gosec: go install github.com/securego/gosec/v2/cmd/gosec@latest"
        echo "  - graphify: pip install graphifyy"
    fi
    exit 0
else
    echo "[PREFLIGHT] ❌ 失败 ($ERRORS 个错误, $WARNINGS 个警告)"
    echo ""
    echo "请修复上述错误后重试"
    exit 1
fi
