<!-- GRAPHFLOW:BEGIN managed block — edit outside these markers only -->
# GraphFlow for Claude Code

Use GraphFlow as a local orchestration and context service.

## Recommended setup

Add a local MCP server entry that launches GraphFlow over stdio:

```json
{
  "mcpServers": {
    "graphflow": {
      "command": "npx",
      "args": ["-y", "--package=@roarpeng/graphflow", "graphflow-mcp"]
    }
  }
}
```

During repository development you can also point Claude Code at this checkout:

```json
{
  "mcpServers": {
    "graphflow": {
      "command": "npm",
      "args": ["run", "start:mcp"],
      "cwd": "."
    }
  }
}
```

## Usage guidance

- Ask GraphFlow to plan before broad changes: `graphflow_plan`.
- Ask GraphFlow to compress and anchor code context: `graphflow_context`.
- Always pass `rootDir` = this project's absolute path. **Never** pass your home directory, AppData, or an unexpanded `${workspaceFolder}` placeholder — GraphFlow refuses unsafe workspace roots. If a call answers `unsafe workspace root`, retry the same call without `rootDir` (the server then uses its configured workspace).
- Ask GraphFlow to inspect graph state or skill learnings when the repo history matters.
- After executing work from a `graphflow_run` `executionDescriptor`, **must** call `graphflow_report_outcome` with the `episodeId` from the run result, a `success` boolean, and optional `lessons` to close the skill flywheel loop.
- Fall back to `graphflow ... --json` only if MCP is not available (including `graphflow --json outcome report <episodeId> <success>`).

DeepSeek Harness: `dsh plugin --profile web add @roarpeng/graphflow` (or `npx @roarpeng/graphflow install` when `~/.dsh` exists).
<!-- GRAPHFLOW:END -->

<!-- ===== 以下为项目记忆与变更规则，不由 GraphFlow 管理。GraphFlow 只应覆写上方块。 ===== -->

# 项目记忆与变更规则 — tmall-dashboard

> 本文件是**规则入口**，不是事实细节的存放处。事实在下列记忆库与文档中，本文件只做索引与约定。

## 1. 记忆入口（动手前按需读取）

| 文件 | 管什么 | 最后更新 |
|---|---|---|
| `.workbuddy-ai/memory/MEMORY.md` | 指标口径、前端约定、验证与高频坑、治理与安全加固（最常查） | 2026-10-16 |
| `.workbuddy-ai/memory/PROJECT-NOTES.md` | 数据源、BI 采集链路、断档诊断、告警与补数手法、治理批次补记 | 2026-10-16 |
| `.workbuddy-ai/memory/YYYY-MM-DD.md` | 当日工作流水（2026-09-22 ~ 2026-10-08，**非每日连续**：有 09-24 / 10-01 / 10-02 / 10-03 / 10-08 等断档） | 逐日 |
| `.workbuddy/memory/2026-09-2{0,1}.md` | 更早的日流水（09-20、09-21） | — |
| `DATABASE_ARCHITECTURE.md` | 数据库分层、表关系、迁移策略（301 行） | — |
| `DESIGN_SYSTEM.md` | 设计系统契约、token、组件目录（1416 行） | — |
| `docs/` | 方案、评审、运行手册、字段字典（62 份） | — |

**记忆库与代码的同步状态**：`MEMORY.md` / `PROJECT-NOTES.md` 已于 2026-10-16 补齐至 2026-10-13 的提交区间（`PROJECT-NOTES.md` 第 12 节）。工作区仍有约 94 个未提交改动，其中 `tests/test_cache_invalidation.py` 是未跟踪的新测试文件。**读记忆后仍要核对代码与 `git log`。**

## 2. 存量保护

- 不得删除既有内容，只能**增量增补**。
- 失效内容保留原文，并标注 **【已作废】** + 作废日期 + 原因。
- 发现多份记忆文件冲突时，**先说明冲突**由人决定，不静默覆盖。

## 3. 参数与事实归档

- 未指定的参数写「未指定」，**不推定**为无限制或默认值。
- 事实必须来自实际读取（`rg --files`、读代码、跑命令），不凭印象填写；不把空白模块写成成熟系统。
- **读到某段逻辑后，必须再验证「它是否实际作用于本仓库」，才能据此下结论。** 光确认代码里存在该逻辑不够。
  - 反例（本仓库真实踩过）：看到 `agent-installer.js:594-605` 的 `indexOf(标记)` 不匹配就走追加分支，就断言「项目 `AGENTS.md` 标记非标准 → 下次安装会追加第二个块 → 应改成短标记」。机制读对了，但漏了下一层：该追加逻辑只对**安装器管理的文件**生效，而 3.2.1 已不再管理任何项目级规则文件（`workspaceRoot` 仅用于 `--workspace` 的 `.mcp.json`），所以风险根本不存在，改标记反而是错的。
  - 自查三问：① 这段代码在**当前装的版本**里还在吗（本仓库装了多个版本，`~/.dsh/profiles/desktop/node_modules/@roarpeng/graphflow` 才是生效的那个）？② 它作用的**文件/路径集合**包含本仓库的目标文件吗？③ 触发它的**入口**（哪个命令、哪个参数）在本仓库会被调用吗？
  - 工具用法同样适用：用 `Select-String -notmatch` 之类过滤时，先确认过滤条件没有把待检文件本身排除掉（曾因 `-notmatch '\\node_modules\\'` 把整个 `node_modules` 包排除，得出"包是裁剪版"的错误结论；实际与 npm 官方 SHA256 逐文件一致）。

## 4. 变更日志格式

追加到 `PROJECT-NOTES.md` 末尾或当日 `.workbuddy-ai/memory/YYYY-MM-DD.md`：

```
YYYY-MM-DD | 操作人 | 修改板块 | 修改详情 | 变更原因 | 生效范围
```

## 5. 调用指令

| 指令 | 动作 |
|---|---|
| `读取全部记忆` | 完整读取第 1 节所有记忆文件与结构文档 |
| `更新agents.md` | 更新本文件的规则部分 |
| `更新项目结构` | 更新 `DATABASE_ARCHITECTURE.md` / `DESIGN_SYSTEM.md` |
| `同步双文档更新` | 上述两者一起更新，并核对是否一致 |

## 6. 提交前验证

权威清单是 `.github/workflows/quality-gate.yml`（本机跑法与 CI 有差异，见下）。CI 矩阵：`windows-latest` + `macos-14`，Python **3.14**、Node **24**。**本机 Python 是 3.11.15** —— 本地通过不等于 CI 通过。

### 6.1 后端与契约测试

```powershell
# CI 带 -W error::ResourceWarning（资源未关闭直接判失败），本地建议同样加上
python -W error::ResourceWarning -m unittest discover -s tests -v
# 4 个纯 pytest 风格文件（无 unittest.TestCase 子类），unittest discover 收集到 0 个用例，
# 必须补跑一次 pytest。注意 test_ui_system_contract.py 内含浏览器门禁用例，
# 未起服务时会以 "无法连接 Chrome DevTools Protocol" 失败，属预期。
python -m pytest tests/test_ui_system_contract.py tests/test_overview_kpi_ui.py `
  tests/test_settings_scan_ui.py tests/test_update_notifications_ui.py -q
node scripts/validate_ui_demos.cjs
# 逐个语法检查前端 JS（CI 用 find|xargs，Windows 下等价写法）
Get-ChildItem frontend\ui_demo\assets -Recurse -Filter *.js | ForEach-Object { node --check $_.FullName }
npm test --prefix desktop
npm run build --prefix desktop
python scripts/production_preflight.py
```

### 6.2 静态设计系统门禁（全部 `--strict`，任一失败即阻断）

```powershell
python scripts/check_css_syntax.py --strict      # CSS 语法错误会被浏览器静默丢弃
python scripts/check_design_system.py --strict   # 颜色走 token、浮层走原语
python scripts/check_css_tokens.py --strict      # 幽灵 token
python scripts/check_event_binding.py --strict   # 禁止把事件绑在 class 选择器上
```

### 6.3 前端类型检查

```powershell
node desktop/node_modules/typescript/bin/tsc -p tsconfig.json --noEmit
```

### 6.4 浏览器门禁（需先起服务，健康检查 `/healthz`）

```powershell
$env:TMALL_PORT=8770; python scripts/run_test_server.py   # CI 会轮询 /healthz 最多 30s
$env:TMALL_SMOKE_BASE='http://127.0.0.1:8770'
node scripts/smoke_core_pages.cjs
node scripts/browser_prd_gates.cjs
$env:TMALL_CAPABILITY_ONLY=1; node scripts/browser_prd_gates.cjs   # 能力探测模式，需单独跑一遍
node scripts/audit_core_interactions.cjs
node scripts/audit_ui_contrast.cjs --states
node scripts/smoke_popover.cjs
node scripts/smoke_date_picker.cjs
```

### 6.5 发布前（CI 末尾两步）

```powershell
# CI 会注入 DASHBOARD_USERNAME / DASHBOARD_PASSWORD
python scripts/production_smoke.py --database <tmp.db>
python scripts/release_audit.py --database <tmp.db> --strict
```

## 7. 禁止事项

- **不要手写用户级 GraphFlow 规则文件**，尤其 `~/.claude/rules/graphflow.md`（安装器里是 `dedicated-md` 目标，**整文件**会被覆写，`agent-installer.js:113`）；`~/.claude/CLAUDE.md`、`~/.codex/AGENTS.md` 等 `managed-md` 目标则只会被覆写托管块（`agent-installer.js:593-607`）。项目内的 `.claude/rules/graphflow.md`、`.trae/rules/graphflow.md`、`.github/copilot-instructions.md` 是 **GraphFlow 2.x 时代**的项目级产物，当前 3.2.1 已不再管理项目级规则文件。
- **上方 GraphFlow 块保持原样，不需要改标记。** 第 1 行的长标记 `<!-- GRAPHFLOW:BEGIN managed block — edit outside these markers only -->` 是 **GraphFlow 2.x 的官方标记**（`2.3.0/dist/integrations/managed-block.js:21`），不是野标记。当前装的是 **3.2.1**，标记已简化为 `<!-- GRAPHFLOW:BEGIN -->`（`agent-installer.js:21`），但 **3.x 安装器已完全不再写项目级规则文件**：3.1.0 / 3.2.0 / 3.2.1 均无 `agentic-md`、`copilot-instructions`、`getProjectLevelRuleTargets` 等符号，`workspaceRoot` 仅用于 `--workspace` 时的 `.mcp.json`（`agent-installer.js:706-708`），其余规则目标全在 `home` 下（`agent-installer.js:100/112/113/164/219/231/283/301/315/372/387`）。所以**不存在「下次安装会追加第二个块」的风险**，也无需把标记改成短形式——改了反而与产生该文件的 2.x 版本脱节。
- 不要新建与 `DATABASE_ARCHITECTURE.md` 重复的结构文档。
