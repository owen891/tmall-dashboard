# 项目优化方向方案（2026-09-23）

> 基于当日全项目深度体检（后端服务层 / 数据层 / 脚本层 / 前端全量 / 桌面端 / 测试体系）
> 生成。所有引用均经过代码级验证，行号以当日工作区为准。
> 历史方案见 docs/archive/（FRONTEND_ARCHITECTURE_PLAN.md 等 15 份）。

## 0. 背景与已完成工作

本方案不是从零开始。2026-09-23 已完成的后端减脂（六个提交，合计净删约 4600 行）：

| 提交 | 内容 |
|---|---|
| 6a04041 | cached_api 缓存装饰器收编（8 份副本 → data_api 单一出处） |
| 02620d0 | 15 份历史方案文档归档至 docs/archive |
| a875c38 | 下线 market_legacy 全文件（11 条路由，-802 行） |
| 9b28dd5 | 下线 kpi/star/ad 系列/漏斗等 10 条路由（-1322 行） |
| c216592 | 下线 tasks/scheduled/chart_events/user_kpis 等 22 条（-1583 行） |
| f0cdf4b | 孤儿代码清理（data_api import_progress 全套、死白名单副本） |

结果：legacy API 从约 5500 行收缩到约 1500 行现役职责；Flask 路由 228 → 173；
迁移台账 80 → 29 条；测试 832 项全绿（`​.venv` 解释器）。

---

## 1. 现状诊断结论（关键事实）

### 1.1 后端

- **period_review_service.py（2079 行）**与前端 period-review-live.js 同病：六区块拼贴
  （模板/周期解析/素材聚合/指标矩阵/legacy 映射）。**实证死代码**：
  - L720 `_products_block` 被 L1924 同名函数覆盖，前一版本约 55 行是死的；
  - L940 `_market_block_legacy` 全库零调用；
  - `_matrix_aggregate` 反向调用 category_analysis_service 私有函数（穿层）。
- **models/ + alembic + Flask-SQLAlchemy 是零使用的僵尸栈**：无任何 `db.Model` 子类，
  `orm_db.init_app`（app.py:117）是唯一消费者，migrations/versions/ 为空。
- **db.py（1793 行）**：`_run_init_migrations` 约 1200 行单体函数，每次启动全量重放
  73 张表的列检查；`user_version=4` 与唯一的 schema_migrations 固定记录只是装饰。
  没有真正的版本化迁移。
- **repos/ 层覆盖率不足 1/3**：sycm_api 39 处裸 SQL、reviews_api 21 处、
  wanxiangtai_api 18 处绕过 repos；仅 8 个左右 API 文件走 repos。
  参数化纪律良好（无注入风险），但分层名存实亡。
- 三个门面空壳：import_readers.py（14 行）/ import_quality.py（8 行）/
  import_specs.py（53 行）只转发 import_service 私有方法。

### 1.2 脚本层

- **oneoff/ 目录 29 个脚本**：全部写死 `E:\...\dashboard.db` 绝对路径、全库零引用，
  属排障遗留，可整目录删除。
- **import_market.py + market_analyzer.py 孤立二件套（1485 行）**：链路已被
  import_market_ranking.py + market_ranking_api.py 取代，可删。
- import_data.py（1417 行）活跃（schedules_api:183 引用 + 测试依赖），但
  L311-399 新旧导入路径双轨并存。
- clean_number 家族在 import_smart / import_smart_daily / import_paimi_monthly /
  scripts/utils 四处重复。
- **采集双链重叠（隐患）**：计划任务链（run_daily_collect.ps1 → collectors/*.py）
  与 RPA 链（auto-collect.ps1 → Chrome 登录 → /api/collect/trigger）功能重叠，
  归档文档警告"不要同时启用"，但代码无互斥保护。

### 1.3 前端

- 21 个页面全部旧式 IIFE + window 全局；runtime/ 与 pages/products/ 的"新结构"
  实质仍是全局变量暴露，只是换了目录名。
- **组件库闲置**：ui-components.js（TmallUI）有完整的 Modal/confirm/DOM 工厂/
  格式化/状态渲染，但仅 5 页加载、每页约 1 处调用，其余页面手拼 HTML 字符串。
- **重复实现清单（验证过的最小集）**：
  - escapeHtml ×7（lifecycle:159、market-ranking:56、data-collection:55、
    flow-source:35、keyword-promotion:149、rival-analysis:43，+ TmallUI.escape）；
  - fmtWan ×3（market-ranking:50、rival-analysis:33、period-review:1005）；
  - money/percent 家族各页一套，￥/¥ 与小数位不一致；
  - 状态文案表 stateLabels ×5（api.js:192、ui-components.js:21、data-center:381、
    product-detail-live:210、overview-live:261）；
  - TmallDateRange 订阅样板 ×13 页重写。
- **components.css（3280 行）名不副实**：`.ui-*` 通用选择器约 180 个，其余六成
  （.product- 196、.overview- 172、.promotion- 157、.lifecycle- 100）是单页专用样式，
  每页固定背 3.9k 行无关 CSS；L105 重复定义 L74 的 .ui-metric-grid。
- products.html 单页 16 个 <script>，各页 cache-bust 版本号手工同步。

### 1.4 测试

- **test_frontend_prd_contract.py 是重构最大阻力**：1138 行、199 次 read 前端文件、
  **598 处 assertIn/NotIn 直接断言源码字符串**——含 CSS 原文（:40 flex-wrap: nowrap;）
  与魔法版本号（:42 `20260923q`）。前端任何拆分会批量打碎它。
- 无 conftest.py；test_smoke.py 依赖 checked-in 的 data/dashboard.db，缺失时静默换基底。
- services 覆盖缺口：period_review_service / import_service / promotion_service /
  settings_service 均只有 API 级间接测试；E2E 仅 1 例（test_closed_loop_e2e）。
- CI 完整：quality-gate.yml 双平台矩阵 + 真实 Chromium 门 + release_audit --strict。

---

## 2. 优化原则（从历次执行中沉淀）

1. **不开重构专项，小步删除**：每批独立提交、独立可回滚、全绿后才提交。
2. **净行数为负**：每个迭代的验收含"净行数必须为负"（新功能除外）。
3. **调用面验证先行**：任何"删除"决策必须先全仓扫描（前端 assets+pages、
   scripts、tests、desktop）确认调用方为零，唯一调用方为测试本身即视为零。
4. **契约同步走同一个提交**：路由/文件变更与台账、validate_ui_demos、
   PRD 契约断言一起更新，不留"半步迁移"。
5. **WIP 先落地**：动手前必须先提交工作区未提交内容（硬前提，已三次验证
   混工作区的代价）。

---

## 3. 方向与阶段计划

### 方向一：零风险清除（立即可做）

| 项 | 动作 | 预期收益 |
|---|---|---|
| 1.1 | 删 scripts/oneoff/ 整目录（29 个零引用脚本） | -约 3000 行 |
| 1.2 | 删 import_market.py + market_analyzer.py 二件套 | -1485 行 |
| 1.3 | 删 models/ + alembic 骨架 + Flask-SQLAlchemy 依赖（orm_db.init_app 一并清） | 删一个依赖栈；注意 desktop 打包 spec 与 requirements 同步 |
| 1.4 | 合并 import_readers/import_quality/import_specs 门面进 import_service | 3 个碎片文件 |
| 1.5 | period_review_service 死代码：删 L720 被 L1924 覆盖的 `_products_block` 旧版、L940 `_market_block_legacy` | 约 100+ 行实证死代码 |

验收：全量套件 + release_audit 通过。风险：极低（1.3 需确认 desktop spec）。

### 方向二：后端结构收敛（次优先）

2.1 **拆 period_review_service**（2079 行 → 4 个模块）：
    `period_parsing.py`（周期解析/月内分周）、`period_templates.py`（段落模板数据）、
    `period_context.py`（素材聚合）、`period_matrix.py`（指标矩阵/类目拆解）。
    `category_service._summarize` 的穿层调用改为公开接口。
    同时补直接单元测试（当前只有 API 级间接覆盖）。

2.2 **sycm_api repo 化**：39 处裸 SQL 下沉 sycm_repo，路由层只留参数校验与响应
    组装。reviews_api（21 处）、wanxiangtai_api（18 处）随后同法。

2.3 **db.py 迁移机制最小治理**：不动 73 张表的现状，但把 `user_version` 从装饰
    变成真实的单调版本号，避免每次启动全量重放 1200 行检查。
    （alembic 已在方向一删除，不回头。）

### 方向三：前端重复消除（比文件拆分优先）

3.1 **format.js 下沉**（无依赖纯函数模块，全页标配）：
    money/percent/fmtWan/escapeHtml 统一收敛，删除 15+ 处重复，
    顺带统一 ￥/¥ 与小数位行为差异。

3.2 **状态渲染三合一**：api.js:197 的本地降级副本、data-center/settings 的
    renderState、五份 stateLabels 表 → 全部收敛到 TmallUI.renderDataState。

3.3 **ui-components.js 升公共层标配**（21 页全加载），页面逐步改用 TmallUI
    工厂替代手拼 HTML。

3.4 **TmallDateRange 订阅样板收敛**：`subscribeDateRange(handler)` 一个函数，
    13 页受益（复用 products 页 event-scope 思路）。

验收：validate_ui_demos + test_ui_system_contract + 前端 PRD 契约同步更新。
注意：方向三每项都会触碰 598 处字符串断言的一部分，断言更新随同提交。

### 方向四：CSS 按前缀拆分

4.1 components.css 内 `.overview-`/`.promotion-`/`.product-`/`.lifecycle-`/`.settings-`
    等单页前缀迁入对应页面 css；保留 `.ui-*` 通用区（约 180 选择器）。
4.2 删除 L105 重复定义的 .ui-metric-grid。
4.3 顺带统一各页 cache-bust 版本号为发布脚本生成。

验收：每页 CSS 负载预期减 50%+；validate_visual_system 全绿；
PRD 契约的 CSS 原文断言同步更新。

### 方向五：测试体系健壮化（前端模块化的前置）

5.1 **断言瘦身**：test_frontend_prd_contract 中绑定 CSS 原文、整行 JS、
    魔法版本号的断言（含 :40-42、:99-100 等）改为行为断言或删除。
    这一步决定方向六的每步阻力，**先做**。
5.2 conftest.py：统一临时库建库样板（当前数十文件重复）。
5.3 test_smoke 基底：checked-in dashboard.db 改为 fixture 生成的确定性基底。
5.4 补 period_review_service / import_service 直接单元测试。

### 方向六：前端模块化（最后，走老方案路线）

按 docs/archive/FRONTEND_ARCHITECTURE_PLAN 的页面迁移路线执行，但顺序修正：

1. data-center（四 IIFE：导入/identity-review/能力地图/页面能力——机械切分）；
2. period-review-live.js（2395 行，最大单体；后端 2.1 拆完后做，前后端同病同治）；
3. products → promotion → 其余页面；
4. shell.js 只拆 date-range-store 一块（16 页订阅时序，需真实浏览器门验证；
   theme/nav/error-reporter 评估为低收益不拆）。

Vite 不设阶段，设触发条件：出现"需要 npm 依赖复用 / TypeScript / 产物压缩"的
真实需求时再引入。

### 方向七：运营决策项（需拍板，代码不动）

7.1 **采集双链二选一**：计划任务链（run_daily_collect.ps1）与 RPA 链
    （auto-collect.ps1）功能重叠。若砍 RPA 链，可删 auto-collect.ps1 +
    auto_login_* 两脚本 + 对应测试；若并存，需加互斥锁。
7.2 scripts/import_data.py 双轨（L311-399 legacy 路径）收敛到 ImportService
    的时机——影响 schedules_api:183 的请求内 import scripts 反向依赖，
    建议随 2.1 一起下沉为 service。

---

## 4. 执行顺序总览

```
第 0 步（硬前提）  提交当前 WIP
第 1 步  方向一全部（零风险，-约 5000 行 + 删僵尸依赖栈）
第 2 步  方向五之 5.1 断言瘦身（为前端铺路）
第 3 步  方向二之 2.1 拆 period_review_service + 死代码
第 4 步  方向三之 3.1/3.2/3.3（前端重复消除三连）
第 5 步  方向二之 2.2 sycm repo 化
第 6 步  方向四 CSS 拆分
第 7 步  方向六页面模块化（data-center → period-review → products → …）
持续项  每批：净行数为负 + 契约同步 + 全绿提交
决策项  7.1 采集双链（用户拍板）
```

预期总量级：方向一至五完成后，代码库净减约 8000-10000 行（含前端重复消除），
测试从"脆弱字符串绑定"转向"行为断言"，前后端最大单体（period-review 前后端）
双双模块化。

---

## 5. 风险清单

| 风险 | 等级 | 缓解 |
|---|---|---|
| WIP 与重构冲突 | 高 | 第 0 步硬前提；拆不开的文件在提交信息注明混入内容 |
| 598 处字符串断言批量打碎 | 高 | 先做 5.1 断言瘦身再动前端 |
| date-range 拆分时序破坏 16 页 | 高 | 放最后、需真实浏览器门；事件名与 payload 冻结 |
| desktop 打包依赖 ORM 栈 | 低 | 方向一 1.3 前核对 packaging spec 与 requirements-desktop |
| test_smoke 基底漂移 | 中 | 5.3 fixture 化 |
| 采集双链同时运行 | 中 | 7.1 决策；短期加互斥标记 |

---

## 6. 执行日志（2026-09-24 更新）

已按执行顺序完成第 0-5 步与第 6 步大部分：

| 步骤 | 状态 | 提交 |
|---|---|---|
| 第 0 步 WIP 落地 | ✅ | 77d79eb/26463f9/0f07df1/04c8d15（enforce_retention 执行器、market_item_links 导入器、两份文档） |
| 第 1 步 方向一 | ✅（此前完成） | dc3918b、fbeb68a 等 |
| 第 2 步 5.1 断言瘦身 | ✅（此前完成） | af2aa95 |
| 第 3 步 2.1 拆 period_review_service | ✅（此前完成） | fa9bb62；遗留 date 导入缺失已修复 c8fc8d0（含 API 回归测试） |
| 第 4 步 方向三 3.1/3.2/3.3/3.4 | ✅ | 3.2 状态文案收敛 DemoLabels + 删 data-center-live 兼容壳 5da1161；3.3 ui-components 全页标配 + api.js 降级副本删除 bda528e |
| 第 5 步 2.2 sycm repo 化 | ✅ 收口 | d19109a：19 个路由/辅助的全部裸 SQL 下沉，sycm_api 1183 → 约 490 行 |
| 第 6 步 方向四 CSS 拆分 | ✅（此前完成） | 3d24992 |
| 第 7 步 方向六 | 🔄 进行中 | data-center ✅ 29a3e0c；products 第一步 ✅ 07095ab；period-review 第一步 ✅ a9ef57c（货品表格列设置 280 行模块，主文件 2443 → 2207 行） |

已知预存问题（待另立任务）：
- products 页 `GET /api/sycm/item-flow/summary?category_mode=sock` 对无数据范围返回 400，
  `audit_core_interactions` 把 4xx 记为 browserError（基线 3 项失败，与本轮改动无关）。
- data-center 390x844 视口 toolbox 按钮在视口外（demo-sidebar 移动端布局），audit 点击超时。

方向六下一步：period-review 继续拆（候选：目标卡 TARGET_* 簇、动作/工作台簇），
然后 products → promotion → 其余页面；shell.js 只拆 date-range-store（需真实浏览器门）。
