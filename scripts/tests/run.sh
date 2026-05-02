#!/bin/bash
# scripts/tests/run.sh
# 脚手架自测：验证生成物能约束 agent，而不是只提供说明文档。

set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
TEST_ROOT="$(mktemp -d)"
PASSED=0
FAILED=0
SKIPPED=0

cleanup() {
    rm -rf "$TEST_ROOT"
}
trap cleanup EXIT

copy_fixture() {
    local fixture="$1"
    mkdir -p "$fixture"
    cp -R "$PROJECT_ROOT/.claude" "$fixture/.claude"
    cp -R "$PROJECT_ROOT/.agent" "$fixture/.agent"
    cp -R "$PROJECT_ROOT/scripts" "$fixture/scripts"
    cp "$PROJECT_ROOT/CLAUDE.md" "$fixture/CLAUDE.md"
    cp "$PROJECT_ROOT/README.md" "$fixture/README.md"
    cp "$PROJECT_ROOT/Makefile" "$fixture/Makefile"
    if [ -f "$PROJECT_ROOT/.gitattributes" ]; then
        cp "$PROJECT_ROOT/.gitattributes" "$fixture/.gitattributes"
    fi
}

pass() {
    echo "[PASS] $1"
    PASSED=$((PASSED+1))
}

fail() {
    echo "[FAIL] $1"
    FAILED=$((FAILED+1))
}

skip() {
    echo "[SKIP] $1"
    SKIPPED=$((SKIPPED+1))
}

run_test() {
    local name="$1"
    shift

    echo "--- $name ---"
    if "$@"; then
        pass "$name"
    else
        fail "$name"
    fi
    echo ""
}

test_validate_config_passes() {
    local fixture="$TEST_ROOT/validate-pass"
    copy_fixture "$fixture"
    (cd "$fixture" && bash scripts/validate-config.sh >/tmp/scaffold-validate-pass.log 2>&1)
}

test_invalid_json_fails() {
    if ! command -v jq >/dev/null 2>&1; then
        skip "invalid JSON detection requires jq"
        return 0
    fi

    local fixture="$TEST_ROOT/invalid-json"
    copy_fixture "$fixture"
    printf '{ invalid json\n' > "$fixture/.claude/settings.json"

    if (cd "$fixture" && bash scripts/validate-config.sh >/tmp/scaffold-invalid-json.log 2>&1); then
        cat /tmp/scaffold-invalid-json.log
        return 1
    fi

    grep -q "无效JSON" /tmp/scaffold-invalid-json.log
}

test_crlf_shell_fails() {
    local fixture="$TEST_ROOT/crlf-shell"
    copy_fixture "$fixture"
    printf '#!/bin/bash\r\necho bad\r\n' > "$fixture/scripts/gates/crlf-test.sh"

    if (cd "$fixture" && bash scripts/validate-config.sh >/tmp/scaffold-crlf.log 2>&1); then
        cat /tmp/scaffold-crlf.log
        return 1
    fi

    grep -q "Shell脚本包含CRLF换行" /tmp/scaffold-crlf.log
}

test_dry_run_is_honest() {
    local fixture="$TEST_ROOT/dry-run"
    copy_fixture "$fixture"

    (cd "$fixture" && bash scripts/gates/all.sh --dry-run >/tmp/scaffold-dry-run.log 2>&1)

    grep -q "干运行完成，未执行实际门控" /tmp/scaffold-dry-run.log
    ! grep -q "所有门控通过" /tmp/scaffold-dry-run.log
}

test_g3_blocks_go_without_tests() {
    local fixture="$TEST_ROOT/g3-missing-tests"
    copy_fixture "$fixture"
    cat > "$fixture/go.mod" <<'EOF'
module example.com/scaffold-test

go 1.22
EOF
    cat > "$fixture/main.go" <<'EOF'
package main

func main() {}
EOF

    if (cd "$fixture" && bash scripts/gates/G3-verify.sh >/tmp/scaffold-g3.log 2>&1); then
        cat /tmp/scaffold-g3.log
        return 1
    fi

    grep -q "缺少对应测试" /tmp/scaffold-g3.log
}

test_g7_blocks_missing_gosec() {
    local fixture="$TEST_ROOT/g7-missing-gosec"
    copy_fixture "$fixture"
    cat > "$fixture/go.mod" <<'EOF'
module example.com/scaffold-test

go 1.22
EOF
    jq '.stacks.go.required_tools.security = ["__missing_gosec_for_scaffold_test__", "jq"]' \
        "$fixture/.agent/project.json" > "$fixture/.agent/project.json.tmp"
    mv "$fixture/.agent/project.json.tmp" "$fixture/.agent/project.json"

    local log_file="$fixture/.agent/logs/scaffold-g7.log"
    mkdir -p "$(dirname "$log_file")"

    if (cd "$fixture" && bash scripts/gates/G7-verify.sh >"$log_file" 2>&1); then
        cat "$log_file"
        return 1
    fi

    if ! grep -q "缺少工具: __missing_gosec_for_scaffold_test__" "$log_file"; then
        cat "$log_file"
        return 1
    fi
}

test_node_stack_uses_configured_lint_command() {
    local fixture="$TEST_ROOT/node-configured-lint"
    copy_fixture "$fixture"
    cat > "$fixture/package.json" <<'EOF'
{"scripts":{"lint":"echo lint-ok"}}
EOF
    jq '.stack = "node" | .stacks.node.commands.lint = "echo node-lint-ok > .agent/logs/node-lint.txt" | .stacks.node.required_tools.lint = []' \
        "$fixture/.agent/project.json" > "$fixture/.agent/project.json.tmp"
    mv "$fixture/.agent/project.json.tmp" "$fixture/.agent/project.json"

    (cd "$fixture" && bash scripts/gates/G4-verify.sh >/tmp/scaffold-node-lint.log 2>&1)

    grep -q "lint 命令通过" /tmp/scaffold-node-lint.log
    grep -q "node-lint-ok" "$fixture/.agent/logs/node-lint.txt"
}

echo "========================================"
echo "[SCAFFOLD TESTS] 运行脚手架自测"
echo "========================================"
echo ""

run_test "validate-config passes on clean fixture" test_validate_config_passes
run_test "invalid JSON is rejected" test_invalid_json_fails
run_test "CRLF shell scripts are rejected" test_crlf_shell_fails
run_test "gate dry-run is honest" test_dry_run_is_honest
run_test "G3 blocks Go implementation without tests" test_g3_blocks_go_without_tests
run_test "G7 blocks missing gosec" test_g7_blocks_missing_gosec
run_test "Node stack uses configured lint command" test_node_stack_uses_configured_lint_command

echo "========================================"
echo "[SCAFFOLD TESTS] 结果: $PASSED 通过, $FAILED 失败, $SKIPPED 跳过"
echo "========================================"

if [ "$FAILED" -eq 0 ]; then
    exit 0
fi

exit 1
