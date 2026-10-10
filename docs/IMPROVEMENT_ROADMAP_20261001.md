# 项目改进路线（2026-10-01）

> 基于当日工作区实测生成。所有引用均经代码级/文件系统级核验。
> 前置文档：`OPTIMIZATION_ROADMAP_20260923.md`（结构减脂，已基本执行完）、
> `DATABASE_GOVERNANCE_BASELINE_20260930.md`（数据库基线，留有未决项）、
> `DATABASE_ARCHITECTURE.md`（schema 契约）。
> 本文件只规划「下一步」，不重复已完成的减脂工作。

## 0. 当前状态核对（相对 09-23 路线图的增量）

09-23 路线图的第 0-6 步已落地，实测确认：

| 已完成项 | 实测证据 |
|---|---|
| models/ + alembic + Flask-SQLAlchemy 栈删除 | `models/` 仅剩 `__pycache__`；`migrations/`、`alembic/` 不存在 |
| scripts/oneoff/ 清除 | 目录仅剩 `__pycache__` |
| import_market.py + market_analyzer.py 删除 | 文件不存在 |
| db.py 迁移版本门（2.3） | `_skip_if_schema_current` 用 `PRAGMA user_version` 跳过全量重放 |
| sycm_api repo 化（2.2） | 已收口 |
| period_review_service 拆分（2.1） | 已拆为 period_parsing/templates/context/matrix |
| CSS 按前缀拆分（方向四） | themes/*-domain.css 已就位 |

**因此本路线聚焦三类尚未收口的问题：交付卫生、存储失控、数据库治理未决项，以及若干需拍板的运营决策。**

## 1. 现状关键事实（实测）

### 1.1 交付卫生 —— 102 个文件未提交

工作区有 **102 个未提交变更**（NUI 抽屉统一化重构 + `compare-live.js`/`manage-live.js` 删除）。
09-23 路线图原则 #5 明确「WIP 先落地是硬前提，已三次验证混工作区的代价」。
当前状态一旦继续叠加新工作，回滚粒度和 `release_audit --strict`（要求干净工作树）都会被破坏。

### 1.2 存储失控 —— data/ 已达 32 GB

| 路径 | 体积 | 性质 |
|---|---:|---|
| `data/backups/` | **24 GB** | 已超 `config.yaml` 的 `max_backup_total_gb: 20` 上限 |
| `data/dashboard.db` | 3.4 GB | 主库（在线） |
| `data/backup_before_aggregate.db` | 3.4 GB | 一次性历史备份，滞留在 data/ 根 |
| `data/demo/` | 1.4 GB | 演示数据 |
| `data/dashboard-archive.db` | 119 MB | 归档库 |

两个信号：① 备份轮转策略（`max_backups: 4` / `max_backup_total_gb: 20`）**未被强制执行**，
backups 实际 24 GB；② `backup_before_aggregate.db` 这类一次性备份没有清理入口，
09-23 已删过两个 2.5 GB 的 `.bak`，同类问题复发。主库 freelist 页 159,580（09-30 基线），是增长信号。

### 1.3 数据库治理未决项（09-30 基线遗留）

- **5 条孤儿 action-history 行**（ID 6-10）引用已不存在的 `product_actions`，导致
  `db_quality_check.py` 返回 `error`。基线明确要求「不删证据、做显式 reconciliation 决策」。
- **263 条未解析的 product-grain 推广行**（外部标识未在 `product_identity_map` 落地），
  需用 identity map / catalog backfill 解决，禁止凭未核验标识在 `products` 造行。
- 14 张「db.py 解析器未声明」的表已在 `schema_baseline.py` 的 `RUNTIME_TABLES` 登记（此项已闭环）。

### 1.4 代码层小残留

- `config.py:120-125` 仍保留 `SQLALCHEMY_DATABASE_URI` / `SQLALCHEMY_TRACK_MODIFICATIONS`
  键，但 Flask-SQLAlchemy 栈已删。这些键现在只被 `app.py` 的 URI 归一化逻辑消费，
  命名与实际用途已脱节，属误导性死配置。

### 1.5 运营决策未拍板（09-23 方向七遗留）

- **采集双链并存**：`run_daily_collect.ps1`（计划任务链）与 `auto-collect.ps1`（RPA 登录链）
  两个脚本实测都在，功能重叠，归档文档警告「不要同时启用」，但代码层无互斥保护。

## 2. 改进原则（沿用已验证的纪律）

1. **WIP 先落地**：任何新工作前，先把 102 个未提交变更按主题拆分提交、跑全绿。
2. **小步、独立提交、可回滚**：不开大重构专项，每批净行数为负或风险明确。
3. **调用面验证先行**：删除前全仓扫描（前端 assets+pages、scripts、tests、desktop）确认零调用。
4. **数据库只读优先**：任何 DELETE/VACUUM/归档前先备份 + 出 manifest + 记 `archive_catalog`，
   默认 dry-run。绝不清空 lineage/observations，绝不把 NULL 回填 0。
5. **契约同步同一提交**：schema/路由/文件变更与台账、`validate_ui_demos`、PRD 契约断言一起改。

## 3. 分阶段计划

### P0 —— 交付卫生（立即，零风险，1-2 小时）

| 项 | 动作 | 验收 |
|---|---|---|
| 0.1 | 把 102 个未提交变更按主题分批提交（NUI 抽屉统一 / compare-live 删除 / manage-live 删除 / 其余），每批跑全量套件 | `git status` 干净；测试全绿 |
| 0.2 | 提交后跑 `release_audit.py --strict` 确认工作树门禁通过 | audit 绿 |

> 这是后续所有阶段的硬前提。不做完 P0，任何新改动都会污染回滚粒度。

### P1 —— 存储治理（高价值，低风险）

| 项 | 动作 | 预期收益 |
|---|---|---|
| 1.1 | 清点 `data/backups/`：列出份数/时间/体积，按 `max_backups: 4` 保留最新 4 份，其余移入系统回收站（**不永久删**） | 释放约 15-20 GB |
| 1.2 | 处置 `data/backup_before_aggregate.db`（3.4 GB 一次性备份）：确认无脚本引用后移入回收站或外置归档 | 释放 3.4 GB |
| 1.3 | 让备份轮转策略真正生效：核查 `db.py` / 备份脚本是否在写备份后执行 `max_backup_total_gb` 裁剪；缺失则补一个 `enforce_backup_cap` 步骤挂到备份流程 | 防复发 |
| 1.4 | 评估主库 freelist（159,580 页）：在**有 integrity-checked 备份**前提下做一次 `VACUUM`（单独任务，非 routine） | 主库回收若干百 MB |

验收：`data/` 总体积回落到 <15 GB；备份份数 ≤ 4 且轮转脚本可重复执行。
风险：低——全部走「移入回收站」而非永久删除，且删前扫描引用。

### P2 —— 数据库未决项收口（中风险，需决策）

| 项 | 动作 | 前置 |
|---|---|---|
| 2.1 | 5 条孤儿 action-history：做显式 reconciliation 决策——保留为「归档遗留历史例外」（在 quality_check 加白名单）或从可信导出恢复父记录，二选一并写审计 | 用户拍板保留/恢复 |
| 2.2 | 263 条未解析 product 推广标识：先跑 `backfill_product_identity_map`（dry-run 预览），人工抽查命中来源后再 apply | 覆盖率 + 来源标注 |
| 2.3 | 收口后重跑 `db_inventory` / `db_quality_check` / query-plan 基线，确认 quality 从 `error` 转 `ok` | 2.1 + 2.2 完成 |

验收：`db_quality_check.py` 返回 `ok`；identity backfill 每行标命中来源供抽查。
风险：中——涉及生产库写入，必须先备份、dry-run、人工核验命中率。

### P3 —— 代码/配置清理与决策项（低优先，穿插做）

| 项 | 动作 | 说明 |
|---|---|---|
| 3.1 | `config.py` 的 `SQLALCHEMY_*` 残留键改名为语义准确的 `DATABASE_URL` 归一化配置，或加注释说明其唯一消费者 | 消除误导性死配置 |
| 3.2 | **采集双链决策**：若砍 RPA 链 → 删 `auto-collect.ps1` + `auto_login_*` + 对应测试；若并存 → 加互斥锁标记 | 需用户拍板 |
| 3.3 | 前端模块化收尾（09-23 方向六残余）：products 主闭包已到 761 行、耦合最深建议收口；period-review 剩余簇、shell.js 的 date-range-store 拆分延后，需真实浏览器门验证 | 低收益项可暂缓 |

## 4. 执行顺序总览

```
P0  提交 102 个 WIP + release_audit 绿        ← 硬前提，先做
P1  备份轮转清理 + 一次性备份处置 + VACUUM     ← 释放 ~20 GB，防复发
P2  孤儿行决策 + identity backfill + 基线复跑  ← quality 转 ok
P3  config 残留 / 采集双链决策 / 前端收尾      ← 穿插，低优先
```

## 5. 需用户拍板的决策项

1. **P1.1/1.2 备份清理**：确认「保留最新 4 份、其余移入回收站」是否符合你的备份习惯，
   是否有需要长期留存的关键时点备份。
2. **P2.1 孤儿 action-history**：保留为归档例外（改 quality_check 白名单）还是从导出恢复父记录？
3. **P3.2 采集双链**：计划任务链与 RPA 链二选一，还是并存加互斥锁？

## 6. 风险清单

| 风险 | 等级 | 缓解 |
|---|---|---|
| WIP 拆分提交混入无关改动 | 中 | 按主题分批，提交信息注明混入内容 |
| 备份误删关键时点 | 中 | 只移入回收站不永久删；删前列清单让用户确认 |
| VACUUM 期间锁库影响服务 | 中 | 服务停机窗口执行；先 integrity-checked 备份 |
| identity backfill 误配 | 中 | dry-run 预览 + 人工抽查命中来源 + 每行标注 |
| 采集双链同时运行 | 中 | 3.2 决策；短期先加互斥标记 |

---

> 本路线的净效果：交付卫生恢复（工作树干净）、`data/` 从 32 GB 回落到 <15 GB、
> 数据库质量审计从 `error` 转 `ok`、清除误导性死配置。均为低风险、可回滚、
> 不触碰 schema 契约与血缘/观测层的保守改进。

---

## 7. 执行进度与实测复核（2026-10-08）

对第 3 节各项做了一次**实测复核**（不照抄本文档的历史结论），结果如下。

### 7.1 已完成

| 项 | 实测证据 |
|---|---|
| P1 存储治理 | `data/` 实测 **6.50 GB**（目标 <15 GB）；`data/backups/` 仅 **1 份 3.35 GB**（≤4）；`backup_before_aggregate.db` 已不存在 |
| P2.1 孤儿 action-history | `db_quality_check` 的 `action_history_orphans` = **ok**，全库 `errors: 0` |
| P2.3 基线复跑 | quality 从 `error` 转 **warning**（`errors: 0`）——原「转 ok」目标未完全达成，见 7.3 |
| P3.1 `SQLALCHEMY_*` 残留 | `config.py` 已改名为语义准确的 `DATABASE_URL` 并附注释，`TRACK_MODIFICATIONS` 已删 |

### 7.2 本轮新增修复（本次复核中发现）

| 项 | 性质 | 证据 |
|---|---|---|
| `backup_database` 删除源库 | **P0 数据丢失**。裁剪 `destination.parent` 的 `*.db` 时，源库与备份同目录即被当「旧备份」删除。`max_backups: 1` 使其从潜伏变必现 | 最小复现：`source exists: True → False`，`pruned=['...dashboard.db']`；修复后 `pruned=[]` 且数据可读 |
| `enforce_retention` 边界整天不可清 | 中等。cutoff 用纯日期 `YYYY-MM-DD` 做字符串比较，`'2026-09-24 01:30:28' < '2026-09-24'` 为假 ⇒ 截止日当天全部行**永不清理**，与 `db_quality_check` 永久矛盾（0 vs 8316） | 修复后 `collector_data_staging` eligible **0 → 8316**，与 quality_check 一致 |
| `db_maintenance` 同一 bug（第 3 处实例） | 中等。`_cutoff` 是**另一份独立实现**，同样返回纯日期 ⇒ 只读预览报 0、执行器报 8316，运维据预览误判「无待清理数据」 | 修复后 5 张表预览/执行器 `eligible_count` **全部一致**（8316/0/0/4361/4920） |
| cutoff **格式与列类型不匹配**（修复 1 引入的回归） | 中等。一刀切改为时间戳 cutoff 后，**纯日期列**（`bi_product_daily_raw.date`）出现反向错位：`'2026-04-11' < '2026-04-11 22:32:56'` 为真 ⇒ **边界当天行被提前一天归档** | 改为按列真实取值探测格式（`_column_has_time` / `_cutoff_for`）：时间戳列给时间戳 cutoff、纯日期列给纯日期 cutoff。5 张表全部格式正确且两工具一致 |
| 预览器**漏套行过滤** | 中等。`enforce_retention` 对 `collector_data_staging` 带 `status='published'`，`db_maintenance` 无此过滤 ⇒ 未发布的超期行会被预览器多算，数字大于执行器实删数 | 新增 `ROW_FILTERS` 与执行器逐字对齐；插入非 published 超期行的用例可逼出差异（修复前必红） |
| 预览器**不暴露「策略无执行器」** | 低。`collector_checkpoints` 声明 30 天保留但 mode=`compact` 未实现，预览器仍照常报 `eligible_count` ⇒ 读者误以为「0 行超期 = 已被妥善管理」，实为**悬空策略** | `build_report` 新增 `enforceable` 字段（`mode in {archive, purge_after_archive}`）；测试锁定 compact 必须为 False |
| 格式探测**依赖行序** | 低（潜在）。`_column_has_time` 原用 ``LIMIT 1`` 单行取样，混合格式列会因先扫到纯日期而误判，结果不确定 | 改用 ``MAX(LENGTH(...))``：只要列中出现过时间戳即判定为时间戳列，与行序无关；空表/异常安全返回 False。测试用「纯日期在前」的混合列锁定 |
| `test_desktop_paths...` **环境依赖假失败** | 低（测试卫生）。该用例用 `tempfile.TemporaryDirectory()` 充当 APPDATA，再断言其不在 `PROJECT_ROOT` 内；但系统临时目录不可写时 `tempfile` 回退到**当前工作目录**（即仓库本身），断言**逻辑上无法满足**，报出与产品无关的假失败 | `desktop_data_paths` 实为**纯字符串派生**、不触碰文件系统，故改用合成的仓库外路径字符串，去掉临时目录依赖。该用例从「依赖环境 → skip」变为**任何环境都真正执行**；注入「打包进安装目录」缺陷仍能被抓住 |
| `connect_readonly` 缺 `temp_store=MEMORY` | 中等健壮性。SQLite 默认 `temp_store=FILE`，大 `GROUP BY` 落临时文件；系统 Temp 不可写时报误导性的 `unable to open database file` | 同一查询：默认 FAIL，`PRAGMA temp_store=MEMORY` 后返回 2021 行 |
| 另 3 个脚本同样缺 `temp_store` | 中等。逐一实测「默认 FILE vs MEMORY」后确认受影响的是 `backfill_store_daily_facts`、`reconcile_observation_batches`、`enforce_retention`（归档导出）——三者的 dry-run 在 Temp 不可写时**必然失败** | 补 pragma 后三者 dry-run 全部 `exit=0`（实测返回 67 / 204957 / 4361 行）。未盲目全改 139 处连接，只改实测受影响的 |
| `schema_alignment` 12 张表未声明 | 低（元数据）。95 张实际 vs 83 张声明 | 登记到 `RUNTIME_TABLES` 后 warning 消除（4 → 3） |

三项缺陷均补了**回归测试并验证其在修复前会失败**：
`test_backup_retention_enforcement.SourceDatabaseSurvivesPruneTests`（3 项）、
`test_enforce_retention.TimestampCutoffTests`（3 项）。

### 7.3 P2.2 结论修正：263 条不是「待回填」问题

原文档假设「跑 `backfill_product_identity_map` 即可解决 263 条未解析推广标识」。
**实测否定该假设**：

- 精确复现 263 条（口径：`grain='product'` 且 product_id 不在 `products`，且 map 缺失或 `unresolved`）
- 263 条**全部**是 `identity_status='unresolved'`，对应 **151 个 distinct product_id**
- 这 151 个 id 在 `products`（10010 行）中**确实不存在**
- `backfill_product_identity_map` 的 dry-run 产出 2021 行，与现有 `product_identity_map` **2021 行完全一致**；逐字段比对 **0 处**会改变 ⇒ **apply 完全幂等，已跑过，再跑不解决任何问题**

因此 263 条的正确定性是：**这些推广商品确实不在商品目录中**，属既成事实而非待办回填。
可选处置（需业务拍板，均未执行）：
1. 接受为「外部投放对象，非本店商品」并在 `db_quality_check` 加白名单（与 P2.1 孤儿行同一处置思路）；
2. 补齐 `products` 目录后再回填（需业务提供缺失商品主数据）；
3. 保留 warning 作为持续提示。

### 7.4 仍未闭环

- **staging_retention**：`collector_data_staging` 有 8316 行超期（`mode=purge_after_archive`）。工具已可用（7.2 已修），但 **apply 会删生产数据**，未执行。
  执行命令：`py -3 scripts/enforce_retention.py --database data/dashboard.db --apply`
- **provenance_and_orphans**：见 7.3，待业务决策。
- 两处 `publish_without_published_at`：4 行 `published_at IS NULL`，可一并处置。
- **`collector_checkpoints` 声明了 30 天保留但从未执行**：`retention_policies` 里 mode 为
  `compact`，而 `enforce_retention` 明确未实现该模式（模块 docstring 已注明
  「compact / retain not implemented here」），dry-run 报 `unsupported_mode:compact`。
  当前 16795 行、最早 2026-09-18，**尚无行超过 30 天**（`older than 30 days = 0`），
  所以暂未造成体积问题；但策略是「声明了却不生效」的悬空状态。收口需先定义
  「compact」语义（去重？合并 checkpoint？），属产品决策，本轮未擅自实现。

### 7.5 需用户拍板（沿用第 5 节，更新）

1. **263 条未解析标识**：三选一（见 7.3）。
2. **8316 行超期 staging**：是否执行 purge（工具已修好，默认 dry-run）。
3. **`max_backups: 1`**：P0 缺陷已修，但单份 3.35 GB 同目录备份无冗余，建议放宽到 3。
4. **采集双链**（P3.2）：仍待决策。
5. **`requirements-lock.txt` 是否入库**：建议入库；若入库，建议补 `pillow`（UI 审计脚本用）。
