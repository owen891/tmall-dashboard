# 整改实施 Workplan（依据 PROJECT_REMEDIATION_REPORT_20261011）

生成时间：2026-10-11 22:2x +08:00
上游依据：`docs/PROJECT_REMEDIATION_REPORT_20261011.md`
基线 commit：`8b87318`（分支 `codex/nui-ui-optimization`）
执行方式：主控串行小步提交，每批次独立可回滚，批次内先写测试再改实现。

---

## 0. 基线复核（本 workplan 的真实起点，与上游报告的差异）

上游报告基于更早的工作树。**开工前实测，报告中的多项计数已经不成立**，必须按实测调整范围：

| 项 | 报告结论 | 本会话实测 | 处理 |
|---|---|---|---|
| 工作树 | 需先"冻结 WIP" | 96 项未提交改动（81 M / 11 A / 4 ??），无未推送提交 | 不冻结为新分支，直接在本分支上按批次提交；每批次一个 commit，可单独 revert |
| 全量测试 | —— | `py -3 -m unittest discover -s tests -q` → **Ran 931, 1 failure** | 该 1 failure 是本批次（批次 0）必收口项 |
| GATE-01 | `validate_ui_demos.cjs` 退出 1，18 UI errors + 2 visual-system errors | 退出 1，仅剩 **2 visual-system errors**，18 UI errors 已消失 | 缩范围为：消除 2 条 visual-system error + 把 validator 的过时源码字符串断言改为接口/行为契约断言 |
| SEC-03 | `analysis-live.js:257`、`category-dashboard-live.js:165` 存在 innerHTML XSS | `:257`（两处 topN 表格）**已经修好**（已包 `escapeHtml`）；`:165` 部分修复但同文件另有 3 处漏改 | 缩范围为：补齐 `frontend/ui_demo/assets/category-dashboard-live.js` 的 `renderProfit`/`renderAnnual`，并全仓扫描 `[NONE]` helper 点 |
| UX-02 | custom 分析失败静默回退 `/api/trend` | **已修**：仅在 404/405/`ENDPOINT_UNAVAILABLE` 时回退，其它故障抛出 | 只补回归测试 |
| UX-03 | 刷新 500ms 假成功 | **已修**：`window.TmallRefresh` 回执 + 15s 超时 | 只补回归测试 |
| FE-02 | chart resize 匿名监听不解绑 | **已修**：`chartResizeHandlers` + `disposeChartInstance` | 只补回归测试 |
| SEC-02 | 采集 run/artifact/staging/retry 跨店 IDOR | **已修**：`api/collect_api.py:982-1081` 全部 route 已带 `current_request_shop_id()` | 只补回归测试 |

**结论：报告 18 项中，UX-02 / UX-03 / FE-02 / SEC-02 / SEC-03(部分) 已在 WIP 中落地。本 workplan 聚焦尚未收口的项。**

---

## 1. 未收口项清单（按实测重新排序）

### P0（上线阻断，本次必须完成）

| ID | 问题 | 位置（实测） | 修复方案 |
|---|---|---|---|
| GATE-0a | 全量测试 1 failure：`test_refresh_handlers_capture_event_targets_before_async_cleanup` 断言 `const refreshButton = event.currentTarget;` | `tests/test_frontend_prd_contract.py:371` vs `frontend/ui_demo/assets/shell.js` | 断言从"源码字符串"改为"刷新回执契约"（`TmallRefresh.register` / `REFRESH_RECEIPT_TIMEOUT_MS` / 不再出现固定 500ms 假成功） |
| GATE-0b | `node scripts/validate_ui_demos.cjs` 退出 1，2 条 visual-system error | `frontend/ui_demo/assets/themes/shell.css` | 消除 `unsupported font-size` 与 `raw box-shadow outside token source` |
| GATE-0c | validator 存在过时源码断言（报告点名的 `/api/trend?dim=daily` 等） | `scripts/validate_ui_demos.cjs` | 改为接口契约断言（调用真实 API 或校验端点常量表），不再 grep 静态字符串 |
| SEC-03r | 残留 innerHTML 注入面 | `frontend/ui_demo/assets/category-dashboard-live.js:154,163,176`；`frontend/ui_demo/assets/market-ranking-live.js:460`（`href` 属性未转义）；`frontend/ui_demo/assets/operations-center.js:100` | 统一走 `escapeHtml()`；URL 属性额外做协议白名单 |
| SEC-01 | 类目分析跨店聚合（`shop_id` 未下传 compare/matrix/leaf weekly/latest date） | `services/category_analysis_service.py`、`services/leaf_weekly_service.py`、`api/category_analysis_api.py` | 把 request-bound `shop_id` 下传到全部 SQL |
| SEC-04 | 商品概览读单店 `monthly_data` 跨店误归属 | `api/product_overview_api.py:57-100` | 非默认店铺 fail-closed |
| JOB-01 | 扫描 120s 固定租约无 heartbeat/fencing，可重复领取 | `services/import_scan_service.py`、`services/collector_run_service.py` | 加 ownership token + fencing + heartbeat，幂等键 `shop_id+source_hash+source_type` |

### P1

| ID | 问题 | 位置 | 修复方案 |
|---|---|---|---|
| DATA-01 | 撤销后首次导入新建商品残留；删除分支不可达 | `repos/import_repo.py:118-141`、`:362-385` | 首次遇到 product ID 一律记 change（`previous_row=NULL`），让删除分支可达 |
| DATA-02 | 复盘缺必填仍可 final | `api/period_reviews_api.py:381-408` | 收口到 `finalize_review()` 状态机，服务端按合并后 sections 算 completeness |
| TX-01 | 告警规则写 + 审计非原子 | `services/alert_rules_service.py`、`repos/alert_rules_repo.py`、`repos/audit_repo.py` | 两 repo 共用同一 connection，由 service 管 `BEGIN/COMMIT/ROLLBACK` |
| AUTH-01 | 非管理员 preview 可写 BLOB 无配额 | `app.py:240-284`、`services/import_service.py` | preview 写操作 admin-only + 配额 |

### P2

| ID | 问题 | 位置 | 修复方案 |
|---|---|---|---|
| DATA-03 | 转化率用 `AVG` 而非 `SUM(buyers)/SUM(visitors)` | `services/leaf_weekly_service.py:53-143` | 改 sum_then_calculate |
| DATA-04 | 商品规则 `SELECT` 漏 `buyers` | `repos/import_repo.py` | 补 `d.buyers` |
| CACHE-01 | 独立扫描进程无法使 Web 进程缓存失效 | `utils/cache.py`、`scripts/run_import_scanner.py` | 移除 DB-backed route 缓存或改用 mutation generation |
| UX-01 | 核心商品分析页写死"2026年9月" | `frontend/ui_demo/pages/core-product-analysis.html:20-23` | 改为跟随 `TmallDateRange` |
| UI-01 | 状态色/密度/复盘双入口 | 主题 CSS | 统一 token |

---

## 2. 批次计划与提交策略

每批次：写测试 → 改实现 → 跑定向套件 → 跑全量 → 提交（1 commit）。

- **批次 0（本批次，先做）：门禁全绿**
  GATE-0a + GATE-0b + GATE-0c。产出：`discover -s tests` 0 failure；`validate_ui_demos.cjs` 退出 0。
- **批次 1：安全边界与数据隔离** SEC-03r + SEC-01 + SEC-04 + AUTH-01
- **批次 2：任务事务与幂等** JOB-01 + DATA-01 + TX-01 + CACHE-01
- **批次 3：业务状态与指标口径** DATA-02 + DATA-03 + DATA-04
- **批次 4：前端可靠性与 UX** UX-01 + UI-01
- **批次 5：架构收口**（视 0-4 结果再定，不在本轮承诺内）

## 3. 每批次的验证命令（固定）

```powershell
py -3 -m unittest discover -s tests -q
node scripts/validate_ui_demos.cjs
Get-ChildItem frontend/ui_demo/assets -Filter *.js -Recurse | % { node --check $_.FullName }
```

定向套件（按批次追加）：
```powershell
py -3 -m unittest tests.test_shop_scope_api tests.test_import_workflow tests.test_import_scan_service tests.test_product_overview_api tests.test_period_reviews_api tests.test_write_evidence_contract tests.test_api_contract tests.test_collector_api_run -q
```

## 4. 风险与决策记录

- **不冻结 WIP**：96 项改动已在树中且测试仅 1 failure，冻结到新分支的收益低于成本；改为批次提交，每批次可 revert。若用户要求冻结，随时可 `git stash` + 新分支。
- **报告计数与实测不一致**：一律以实测为准，workplan 已按实测缩范围。报告未过时项（SEC-01/02/04、JOB-01、DATA-01..04、TX-01、AUTH-01、CACHE-01、UX-01、UI-01、GATE-01）保留。
- **不顺手统一 `expense_ratio` 口径**：`services/category_analysis_service.py:123` 与 `services/metric_definitions.py:15` 的两处定义不一致是历史遗留，diff 中明确标注，不在本轮统一。
- **前端改 JS/CSS 必须 bump HTML 的 `?v=`**：静态资源缓存 7 天。
- **不能用 PowerShell 控制台判断编码问题**：中文 Windows 控制台是 GBK 代码页，会把正确的 UTF-8 输出显示成乱码，产生假阳性。判定乱码必须做字节级扫描（`raw.decode('utf-8')` + 特征字符计数），不能看终端输出。

---

## 5. 批次执行记录

### 批次 0：门禁全绿 —— 已提交 `011c81e`

| 项 | 结论 |
|---|---|
| GATE-0a | `tests/test_frontend_prd_contract.py:369` 断言从 HEAD 版源码字符串改为 UX-03 刷新回执契约（`const refreshButton = header.querySelector` / `window.TmallRefresh` / `REFRESH_RECEIPT_TIMEOUT_MS` / `waitUntil`），保留反向断言 `assertNotIn('setTimeout(() => event.currentTarget.classList.remove', shell)` |
| GATE-0b | 2 条 visual-system error 拆成两个独立根因：`shell.css` 4 处 raw box-shadow（`:285`/`:313`/`:345`/`:379`+`:386`）与 `:347` 的 `font-size: 9px`。修法是在 `frontend/ui_demo/assets/tokens.css` 新增 `--focus-shadow` / `--focus-shadow-sm` / `--anchor-ring` / `--tab-underline` / `--font-size-micro: 10px`，组件改为引用 token |
| GATE-0c | **无需修改**。`scripts/validate_ui_demos.cjs` 已被 WIP 重写为契约/结构断言（`:55-63` 明确注释 `/api/trend?dim=daily` 已不存在；`:185-282` 改查 `frontend/ui_demo/assets/runtime/date-range-store.js` 的 `PRESET_LABELS`/`PRESET_GROUPS` 表与分组归属，不再断言旧位置） |

验证：`py -3 -m unittest discover -s tests -q` → Ran 931 OK；`node scripts/validate_ui_demos.cjs` → exit 0；`node scripts/validate_visual_system.cjs` → exit 0。

### 批次 1：安全边界与数据隔离 —— 已提交（见下）

**复核结论：报告点名的 4 项里 3 项已在 WIP 落地，本批次实际产出是「补回归测试 + 修 2 处真实乱码」，没有新增 guard。**

| 项 | 报告结论 | 实测真相 | 处置 |
|---|---|---|---|
| SEC-01 | 类目分析 `shop_id` 未下传 compare/matrix/leaf weekly | **已修好**。`services/category_analysis_service.py:67` `clauses = ['d.shop_id = ?', ...]`、`:68` 参数含 shop_id、`:192` latest date 也带 `WHERE shop_id = ?`；`source_tables` 只有 `daily_data`（`:238`/`:295`）。`services/leaf_weekly_service.py` `source_tables` 是 `['daily_data', 'products']`（`:252`），`:99`/`:141` 都带 `d.shop_id = ?`。`api/category_analysis_api.py:13,38,69` 传 `current_request_shop_id()` | 补「按店过滤」正向测试，**明确断言这两类接口必须返回 200 而不是 422** |
| SEC-02 | 采集 run/artifact/staging/retry 跨店 IDOR | **已修好**。`api/collect_api.py:982-1081` 的 5 个 route 全部传 `shop_id=current_request_shop_id()` | 复用既有 `test_shop_scope_api` 覆盖 |
| SEC-03r | innerHTML 注入面 | **已修好**。`analysis-live.js:257/315` 已包 `escapeHtml`；`category-dashboard-live.js` 的 `renderProfit`/`renderProducts`/`renderAnnual` 由本次补齐（`:104`/`:163` 原本已 escape，属漏改）。`operations-center.js:100` 与 `market-ranking-live.js:460` 经逐查为扫描器误报（前者纯字面量，后者 `:461` 已有 `/^https?:\/\//i` 协议白名单） | 新增 2 个 pytest（`tests/test_ui_system_contract.py`），把误报固化为「允许」，避免后人把正确的 `setAttribute` 改成 `innerHTML` |
| SEC-04 | 商品概览读单店 `monthly_data` 跨店误归属 | **已修好**。`api/product_overview_api.py:22-32` `_reject_named_shop_read()` 对非默认 scope 返回 422 `UNSUPPORTED_SCOPE`，`:55` 在 `rule-results` 调用（该接口 `:86` 用 `INNER JOIN monthly_data`）。`/rules`（`:44`）**故意不加 guard**：它只调 `list_rules()`，而 `services/product_rules_service.py:221` 返回内存表 `PRODUCT_RULES` 的拷贝，不读任何表 | 补「must fail closed」与「metadata 必须 200」两个方向的测试 |
| AUTH-01 | 非管理员可持久化 import preview BLOB，无配额 | **已修好**。`app.py:240-253` 的 `public_mutations` 已移除 `/api/imports/preview`，只剩 `/api/frontend-errors`，并在 `:244-247` 写明原因 | **原报告无任何测试锁定此项**，本批次新增 2 个测试（403 场景 + admin 通过场景 + 豁免名单断言） |

**本批次新发现并修复的真实缺陷（非报告条目）**：`api/product_detail_api.py` 两处 GBK 往返乱码——
- `:804` `reject_legacy_shop_scope('鍟嗗搧浜ゆ槗鍒嗘瀽')` → `'\u5546\u54c1\u4ea4\u6613\u5206\u6790'`（商品交易分析）
- `:826` `failure('NOT_FOUND', '鍟嗗搧涓嶅瓨鍦?')` → `'\u5546\u54c1\u4e0d\u5b58\u5728'`（商品不存在）

文件本身是合法 UTF-8，只有字面量被写坏，普通读写不报错，必须做字符级扫描才能发现。修复后 `api/ services/ repos/` 罕见字符扫描 0 hits，并新增 `test_no_gbk_mojibake_literals_in_scope_sources` 钉住该约束。

**本批次踩到的测试自身陷阱（已修正，记录以免重犯）**：
1. 路由名写错：叶子周报实际是 `/api/category-analysis/leaf-weekly-board`（`api/category_analysis_api.py:65`），写成 `leaf-weekly` 会得到 404 而非 422。
2. `success()` 把业务载荷包在 `data` 键下：`/api/product-overview/rules` 的 rules 在 `payload['data']['rules']`，不在顶层。
3. 鉴权模型是「单身份 + 可选 admin 名单」：`require_admin_write()`（`services/shop_scope_service.py:126-134`）先要求匹配唯一的 `DASHBOARD_USERNAME`/`DASHBOARD_PASSWORD`（否则 401），再看 `DASHBOARD_ADMIN_USERS`（否则 403）。不能用第二组账号测「管理员通过」。
4. 我最初照搬报告，把 `category-analysis/compare|matrix|leaf-weekly-board` 断言成必须 422 —— **这是错的**，它们能满足多店隔离，加 fail-closed 会让多店部署不可用。加锁前必须先确认该接口是否真的触达无 `shop_id` 的表。

验证：`py -3 -m unittest tests.test_shop_scope_api` → Ran 17 OK；`py -3 -m unittest tests.test_app_factory` → Ran 28 OK；`py -3 -m unittest discover -s tests -q` → **Ran 938 OK**（较批次 0 的 931 增加 7 个新测试）；`.venv/Scripts/python.exe -m pytest tests/test_ui_system_contract.py` → 44 passed, 1 skipped；`node scripts/validate_ui_demos.cjs` → exit 0；`node scripts/validate_visual_system.cjs` → exit 0。
