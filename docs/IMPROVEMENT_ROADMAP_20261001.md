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
