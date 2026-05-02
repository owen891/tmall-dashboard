#!/bin/bash
# scripts/lib/project-config.sh
# 读取 .agent/project.json，为门控提供技术栈和命令配置。

if [ -z "${PROJECT_ROOT:-}" ]; then
    PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
fi

PROJECT_CONFIG_FILE="$PROJECT_ROOT/.agent/project.json"

require_project_config() {
    if [ ! -f "$PROJECT_CONFIG_FILE" ]; then
        echo "[CONFIG] ❌ 缺少项目配置: .agent/project.json"
        exit 1
    fi

    if ! command -v jq >/dev/null 2>&1; then
        echo "[CONFIG] ❌ jq 未安装，无法读取 .agent/project.json"
        exit 1
    fi
}

configured_stack() {
    require_project_config
    jq -r '.stack // "auto"' "$PROJECT_CONFIG_FILE"
}

detect_stack() {
    require_project_config

    local selected
    selected="$(configured_stack)"
    if [ "$selected" != "auto" ] && [ "$selected" != "null" ] && [ -n "$selected" ]; then
        echo "$selected"
        return 0
    fi

    while IFS= read -r stack; do
        while IFS= read -r marker; do
            if [ -e "$PROJECT_ROOT/$marker" ]; then
                echo "$stack"
                return 0
            fi
        done < <(jq -r --arg stack "$stack" '.stacks[$stack].detect[]?' "$PROJECT_CONFIG_FILE")
    done < <(jq -r '.stacks | keys[]' "$PROJECT_CONFIG_FILE")

    echo "none"
}

stack_exists() {
    local stack="$1"
    require_project_config
    jq -e --arg stack "$stack" '.stacks[$stack] != null' "$PROJECT_CONFIG_FILE" >/dev/null
}

gate_command() {
    local stack="$1"
    local gate="$2"
    require_project_config
    jq -r --arg stack "$stack" --arg gate "$gate" '.stacks[$stack].commands[$gate] // empty' "$PROJECT_CONFIG_FILE"
}

coverage_threshold() {
    require_project_config
    jq -r '.coverage_threshold // 80' "$PROJECT_CONFIG_FILE"
}

required_tools() {
    local stack="$1"
    local gate="$2"
    require_project_config
    jq -r --arg stack "$stack" --arg gate "$gate" '(.stacks[$stack].required_tools[$gate] // [])[]' "$PROJECT_CONFIG_FILE"
}

check_required_tools() {
    local stack="$1"
    local gate="$2"
    local missing=0

    while IFS= read -r tool; do
        if [ -n "$tool" ] && ! command -v "$tool" >/dev/null 2>&1; then
            echo "[$gate] ❌ 缺少工具: $tool"
            missing=$((missing+1))
        fi
    done < <(required_tools "$stack" "$gate")

    if [ "$missing" -gt 0 ]; then
        return 1
    fi
}

run_gate_command() {
    local stack="$1"
    local gate="$2"
    local command="$3"
    local label="${4:-$gate}"

    if [ -z "$command" ]; then
        echo "[$label] ℹ️ $stack 未配置 $gate 命令，门控不适用"
        return 0
    fi

    check_required_tools "$stack" "$gate"
    mkdir -p "$PROJECT_ROOT/.agent/logs"
    (cd "$PROJECT_ROOT" && bash -lc "$command")
}
