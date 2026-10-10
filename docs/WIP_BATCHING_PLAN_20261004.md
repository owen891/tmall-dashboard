# 未提交 WIP 分批提交方案（2026-10-04）

> 依据：`docs/IMPROVEMENT_ROADMAP_20261001.md` §1.1 / P0「WIP 先落地是硬前提」
> 现状：18 个 tracked 文件未提交（+130 / -34），合计挡住 `release_audit.py --strict`（要求干净工作树）
> 立场：**本文件只做分流与验证设计，不代替原作者判断其改动是否完工**

---

## 0. 结论摘要

18 个文件**不是同一主题**，实测分成 **5 批**；其中 **2 批是在修「当前 HEAD 上的真实缺陷」**，应优先提交。

| 批次 | 主题 | 文件数 | 性质 | 优先级 |
|---|---|---|---|---|
| **1** | 首屏口径条 / 洞察卡 / 投放决策的样式 | 1 | **修 HEAD 缺陷**（JS 已提交、CSS 缺失） | **最高** |
| **2** | `available_periods` 收 `day` 粒度 | 1 | **修 HEAD 缺陷**（day 请求返回空选项） | **最高** |
| 3 | 文案统一「周月复盘」→「周期复盘」 | 11 | 纯文案/注释，零行为 | 中 |
| 4 | 初稿生成器：对比周期语义 + 百分数格式化 | 1 | 行为改动（用户可见） | 中（需浏览器验证） |
| 5 | 货品表「创建动作」入口 | 1 | 新功能 | 中（需浏览器验证） |
| — | 同上两个文件内的文案改名 | （含在 1/4 内） | — | — |

**建议顺序：1 → 2 → 3 → 4 → 5。** 先把 HEAD 修好，再做零风险统一，最后是两个需浏览器验证的功能。

---

## 1. 批次 1 —— 首屏样式补全（修 HEAD 缺陷）

**文件**：`frontend/ui_demo/assets/period-review.css`（+72 / −1）

**为什么是缺陷而不是新功能**（已用 `git grep … HEAD` 证实）：

```text
HEAD 的 *.css 中 pr-insight-card / pr-scope-pill / pr-ad-decision /
              pr-command-center__scope 定义数：0
HEAD 的 frontend/ui_demo/assets/period-review-live.js 引用数：各 5 处（已提交）
```

⇒ **检出 HEAD 时，首屏「口径条 / 三张洞察卡 / 投放决策块」是无样式的裸元素。** JS 那一半已提交，CSS 这一半还在工作树里——这是典型的「本地看着好、仓库是坏的」。

CSS 首行还含一处「周月复盘 → 周期复盘」注释改名，建议**并入本批**（拆开会造成同一文件两批之间还要再改一次）。

**验收**：
```powershell
git grep -c -e 'pr-insight-card' HEAD -- '*.css'    # 提交后应 ≥ 1（提交前为 0）
node scripts/validate_ui_demos.cjs                   # 退出码 0
# 真浏览器（需先起服务，后端无自动重载）
$env:TMALL_SMOKE_BASE='http://127.0.0.1:5000'; node scripts/smoke_period_review_tabs.js
```

**提交信息建议**：`补全周期复盘首屏样式（口径条/洞察卡/投放决策）—— HEAD 上 JS 已引用但 CSS 缺失`

---

## 2. 批次 2 —— `available_periods` 收 `day`（修 HEAD 缺陷）

**文件**：`services/period_parsing.py`（+1 / −1）

```python
# 工作树（修后）              # HEAD（修前）
if period_type not in ('day', 'week', 'month'):   ←   ('week', 'month')
```

**为什么是缺陷**：`api/period_reviews_api.py` 在 HEAD 上就是

```python
PERIOD_TYPES = ('day', 'week', 'month')
...
options = reviews_service.available_periods(period_type, limit=limit)
```

`day` 在 `period_parsing.py:69/:155/:171`、`period_templates.py:135`、`db.py:770` 的 CHECK 约束中**都已支持**，唯独 `available_periods` 的白名单漏了它 ⇒ **HEAD 上 `period_type='day'` 的选项接口返回空列表**。改动是修复，不是半成品。

**验收**：
```powershell
./.venv/Scripts/python.exe -m pytest tests/test_period_reviews_api.py -q
# 建议额外补一条断言：available_periods('day') 非空（当前无用例覆盖）
```

---

## 3. 批次 3 —— 文案统一「周月复盘」→「周期复盘」（零行为）

**文件（11 个，均为字符串/注释/文档串）**：

```text
frontend/ui_demo/assets/shell.js                                  导航标签 + 页面说明（含「日周月复盘」→「周期复盘」）
services/page_capability_service.py                               PAGE_DEFINITIONS.label、2 处 CAPABILITY_DEFINITIONS.label
services/period_matrix.py                                         docstring
scripts/audit_dialog_dismiss.cjs                                  注释
scripts/build_ui_audit_report.py                                  PAGES 表 label
scripts/shot_period_review_matrix.js                              注释
scripts/shot_period_review_products.js                            注释
scripts/shot_period_review_targets.js                             注释
scripts/smoke_period_review_tabs.js                               注释
frontend/ui_demo/assets/pages/period-review/gap-attribution.js    注释
frontend/ui_demo/assets/pages/period-review/leaf-board.js         注释
```

> 实际为 11 个「纯文案」文件 + `metric-cards.js` / `target-cards.js` / `review-export.js` 三个同样只有注释改名，一并计入本批 ⇒ **本批共 14 个文件**。

**已完成的验证**（这是上轮踩过的坑：既有测试可能固化文案）：

```text
pytest tests/test_page_capability_service.py → 11 passed, exit 0
```

即 **label 改名不触发能力注册表契约测试**，本批安全。

**验收**：
```powershell
./.venv/Scripts/python.exe -m pytest tests/test_page_capability_service.py tests/test_smoke.py -q
Get-ChildItem frontend/ui_demo/assets -Filter *.js -Recurse | ForEach-Object { node --check $_.FullName }
./.venv/Scripts/python.exe -m pytest tests/ -q          # 兜底
```

---

## 4. 批次 4 —— 初稿生成器：对比周期语义 + 百分数格式化

**文件**：`frontend/ui_demo/assets/pages/period-review/deterministic-draft.js`（+31 / −14）

含**两个可独立说明的修复**（建议同一批提交，主题为「初稿生成器修正」）：

| # | 改动 | 影响 |
|---|---|---|
| 4a | 拆分 `signedRate`（已是百分数，如 `7.4`）与 `signedPercent`（小数比率 `0.074`） | 修掉「7.4 被显示成 740.0%」这类量纲错误；`payment_change_rate` / `buyers_change_rate` 改用 `signedRate` |
| 4b | 引入 `comparisonAvailable = compare.mode !== 'none' && compare.available !== false`，并贯穿 4 处分支 | 未选对比周期时，不再说「环比无法计算（对比期数据不完整）」，改说「当前未选择对比周期，暂不做环比算术归因」；无对比时问题单品清单过滤掉「下滑榜」来源、`decline` 置空 |

**注意**：该文件首部还有一处「周月复盘 → 周期复盘」注释改名。**不建议拆到批次 3**——同一文件跨两批会让批次 3 之后还要再改一次，主题纯净优先于文案完全一致。

**验收**（需真实浏览器，不能只靠 `node --check`）：
```powershell
node --check frontend/ui_demo/assets/pages/period-review/deterministic-draft.js
node scripts/test_frontend_runtime.cjs
$env:TMALL_SMOKE_BASE='http://127.0.0.1:5000'; node scripts/audit_core_interactions.cjs
# 人工确认：切换「对比周期=无」时首屏文案不再出现「环比无法计算」
```

---

## 5. 批次 5 —— 货品表「创建动作」入口（新功能）

**文件**：`frontend/ui_demo/assets/pages/period-review/product-columns.js`（+9 / −1）

新增 `ACTION_BOARD_KEYS = new Set(['decline','loss','paid','new_paid'])`，命中榜单的行额外渲染「创建动作」按钮（打开单品诊断）。正向榜仍只保留「查看诊断」。

**验收**（浏览器）：在 `decline / loss / paid / new_paid` 四个榜的表行上可见「创建动作」；正向榜不可见；点击能打开单品诊断。

**风险**：这是**新功能**，原作者可能尚未完工。**提交前应向原作者确认**，不要仅凭 diff 判断。

---

## 6. 批次间与终局门禁

- 批次 1–3 风险低，可各自单独提交，每批跑对应定向验证
- 批次 4–5 需真浏览器验证；后端**无自动重载，改完必须重启进程**
- **全部批次完成后**跑一次完整门禁（主控独占）：
  ```powershell
  Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass -Force
  .\.venv\Scripts\python.exe -m pytest tests/ -q      # 当前基线 929 passed / 0 failed
  & .\scripts\test_all.ps1                            # 期望 TEST_ALL_OK（不要合并 stderr）
  py -3 scripts/release_audit.py --database data/dashboard.db --strict
  ```
  最后一条只有在**18 个文件全部提交后**才可能绿——这正是 P0 的目标。

---

## 7. 本方案不做的判断

- **不判断这些改动是否"完工"**：批次 4/5 是用户可见的行为变更与新功能，属原作者职责
- **不代为提交**：这些不是本会话的产物，提交它们等于替他人在途工作定性
- **不碰** `.tmp_audit/`（未跟踪，非本轮产物）
