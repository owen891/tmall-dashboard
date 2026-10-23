# 数据库架构边界说明

> 基于 `data/dashboard.db` 的实际 schema、行数和当前代码调用关系整理。
> 本文只定义边界和保留策略，不执行删除、归档或迁库。

## 1. 当前结论

当前数据库不是单一模型，而是以下生命周期不同的层叠在一个 SQLite 文件中：

```text
业务主数据/配置
  -> 在线事实数据
  -> 原始证据与字段血缘
  -> 导入暂存与采集运行状态
  -> 兼容接口和历史遗留表
```

这套结构目前可用，问题主要是边界没有集中声明，而不是某一张表必须立即删除。

截至本次核查：

| 项目 | 实际值 |
|---|---:|
| 主数据库文件 | 约 3.11 GiB |
| `daily_data` | 97,118 行 |
| `monthly_data` | 76,709 行 |
| `fact_field_lineage` | 2,564,934 行 |
| `daily_data_observations` | 112,530 行 |
| `reconciliation_results` | 26,387 行 |
| `collector_data_staging` | 127,608 行 |
| `monthly_source_payload` | 69,484 行 |
| `bi_product_daily_raw` | 12,350 行 |

## 2. 权威数据合同

| 数据域 | 权威表 | 粒度 | 页面用途 | 页面可直接查询 |
|---|---|---|---|---|
| 商品经营日事实 | `daily_data` | 店铺/商品/日 | 商品运营、商品详情、日趋势 | 是 |
| 商品经营月事实 | `monthly_data` | 商品/月 | 月度商品分析、生命周期 | 是 |
| 店铺经营日事实 | `store_daily_facts` | 店铺/日 | 总览、店铺趋势 | 是 |
| 推广日事实 | `promotion_daily_facts` | 推广对象/日 | 推广分析 | 是 |
| 推广创意日事实 | `promotion_creative_daily` | 创意/日 | 素材点击率 | 是 |
| 流量来源日事实 | `sycm_flow_source_daily` | 渠道/日 | 流量来源 | 是 |
| 商品流量来源日事实 | `sycm_item_flow_source_daily` | 商品/渠道/日 | 商品流量结构 | 是 |
| 市场事实 | `sycm_market_*` | 市场对象/日或批次 | 市场分析、竞店竞品 | 是 |
| 商品主数据 | `products` | 商品 | 商品名称、分类、标签和状态 | 是 |
| 原始 BI 证据 | `bi_product_daily_raw` | 来源商品记录/日 | 回溯、重放、字段核对 | 否 |
| 月度原始证据 | `monthly_source_payload` | 商品/月/来源文件 | 月度字段审计 | 否 |

### 2.1 不应合并的表

- `daily_data` 是商品级日事实，`store_daily_facts` 是店铺级日汇总，粒度不同，不是重复表。
- `promotion_daily_facts`、`sycm_flow_source_daily`、`sycm_market_*` 分别对应推广、流量、市场域，不应塞进商品经营事实表。
- 原始 payload、观测、字段血缘用于证据和审计，不应直接作为页面展示事实。

## 3. 原始证据与血缘层

| 表 | 角色 | 当前保留建议 | 说明 |
|---|---|---|---|
| `bi_product_daily_raw` | BI 原始快照 | 长期保留近期，历史可外置归档 | 用于核对 BI 原字段和重放采集 |
| `monthly_source_payload` | 月度原始 payload | 历史月份压缩归档 | JSON 体积大，不作为在线事实查询 |
| `daily_data_observations` | 来源标准字段观测 | 保留审计窗口，历史可归档 | 记录来源系统、批次和字段值 |
| `fact_field_lineage` | 字段级生效来源 | 不直接删除 | 支撑来源解释、冲突和回溯 |
| `reconciliation_results` | 字段冲突结果 | 保留冲突记录 | 用于质量审计和口径复核 |
| `daily_data_observations_quarantine` | 无效/隔离观测 | 长期保留失败证据 | 行数小，便于问题追踪 |

当前链路是：

```text
BI/API/导入文件
  -> 原始 payload
  -> daily_data_observations
  -> fact_field_lineage / reconciliation_results
  -> daily_data 或 monthly_data
```

同一字段在多个层级保存是有审计价值的，但完整 JSON 不应无限期留在热库。

## 4. 采集、导入和运行层

| 表 | 生命周期 | 建议 |
|---|---|---|
| `collector_runs` | 运行记录 | 长期保留摘要，明细按周期归档 |
| `collector_checkpoints` | 单元进度 | 保留近期运行，成功批次可压缩 |
| `collector_data_staging` | 发布前暂存 | 成功发布后保留 14～30 天 |
| `collector_quality_results` | 质量门禁 | 保留质量摘要和失败记录 |
| `collector_artifacts` | 日志/产物索引 | 成功产物按周期归档，失败产物保留更久 |
| `collector_schema_snapshots` | 来源 schema 快照 | 每次变更保留，重复快照可去重 |
| `collector_leases` | 并发锁 | 只保留当前有效锁，过期锁应清理 |
| `import_batches` | 导入批次 | 长期保留摘要和 hash |
| `import_staging_rows` | 文件导入暂存 | 导入完成后按批次清理或归档 |
| `import_scan_*` | 文件扫描任务 | 保留任务和失败摘要，扫描明细按周期清理 |

原则：运行态表不应和业务事实采用相同的无限保留策略。

### 4.1 达摩盘事实表（dmp_shop_* 与 dmp_competition_*，2026-10-07 新增）

采集器 `E:\www\BI采集\collectors\collect_dmp_shop.py`（采集中心源 `dmp_shop`）与
`collect_dmp_competition.py`（源 `dmp_competition`，复用前者的浏览器/令牌机件），
均为挖象浏览器 CDP 9224 页内 fetch，见各自源内注释。

**全店洞察（dmp_shop_*）**：

| 表 | 粒度 | 保留 |
|---|---|---|
| `dmp_shop_runs` | 每次采集一行 | 摘要长期保留 |
| `dmp_shop_overview` | run × period × benchmark(0本店/1同行同层) | 随 run 清理 |
| `dmp_shop_items` | run × period × 单品（row_json 去 indicators） | 默认 120 天（TMALL_DMP_RETENTION_DAYS） |
| `dmp_shop_item_indicators` | run × period × 单品 × 指标（value/peer_value/growth_rate/分档） | 同上 |
| `dmp_shop_indicator_dict` | run × 指标 key 的名称/分组/tips | 同上 |

同行同层数据两个层级都在：overview `benchmark=1`（店铺级，GMV/IPV 只有分档串
`generalizedIpv` 等）；单品行 `indicators[].peerValue`（数值，覆盖 14 个核心指标）。
采集器自带保留期清理（先删子表再删 runs）；同一采集中心 batch_id 重跑会先清旧批。

**竞争分析（dmp_competition_*）**：`dmp_competition_runs`（批次，含
end_date/peer_end_date 双窗口）、`dmp_competitors_detection`（竞对探测快照：
competitor_name + competitive_score + recall_method + GMV/进店/支付分档）、
`dmp_competitor_monitor`（监控列表快照；competitor_token 存的是**监控关系数字 ID**，
即 indicator 接口的 id 参数；列表行内 competitorId 加密串恒为 null，entityInfo 是
本店参照信息）、`dmp_competition_indicators`（每竞对：day_cost/day_cost_rate、
intersection_click_uv 人群争夺交集、buy_uv_rate + payload_json 含
controlRatio/periodControlRatio 份额分档）。三张事实表冗余 end_date 供采集中心
通用状态查询。保留期默认 365 天（TMALL_DMP_COMP_RETENTION_DAYS）。
v1.1 已补 `dmp_competition_ad_strategy`（v1.1，2026-10-07）：TOP 单品
（TMALL_DMP_AD_TOPN，默认 10，按最新 dmp_shop 批次支付金额取）×
`ad/similarity`（相似画像）+ `ad/strategyLesson`（竞品投放策略簇：渠道占比/
计划名/圈选人群/购买关键词/簇均ROI）。注意该接口 entityId=**我方商品ID**、
competitionType=2 商品维度（店铺维度返回空），POST body {"competitionType":2,
"entityId":...,"period":"30"}；借鉴失败不阻塞监控主批次。
看板展示：竞店竞品页「达摩盘竞争」Tab（api/dmp_api.py 五端点含
`/api/dmp/shop/summary` 本店 vs 同行同层概览 +
rival-analysis-live.js），控比语义=**我方**在共同人群中的占比（>50% 优势）。

## 5. 业务主数据与运营配置

以下表属于应用业务状态，应长期保留：

- `products`、`product_identity_map`
- `product_tags`、`product_notes`
- `product_targets`、`shop_targets`
- `product_actions`、`product_action_history`、`operation_actions`、`operation_logs`
- `period_reviews`、`review_summary`
- `app_settings`、`alert_rules`、`alerts`
- `daily_goals`、`goal_versions`、`goal_adjustments`、`goal_locks`
- `lifecycle_profiles`、`lifecycle_history`

这些表不能因为事实数据归档而删除；归档事实时必须保留能回溯主数据的 ID、批次和时间范围。

## 6. Legacy 和迁移边界

当前仓库同时存在：

```text
应用启动时 db.py 自动初始化/迁移
+
schema_migrations 记录
+
部分预留的 Alembic 入口
+
legacy API 兼容层
```

这属于双轨迁移机制。后续规则：

1. 新功能只能依赖本文件第 2 节的权威事实表。
2. 新 API 必须明确数据粒度，禁止用 `daily_data` 代替店铺、推广或市场事实。
3. Legacy 表和 Legacy API 暂不删除，但冻结新增依赖。
4. 新 schema 变更要同时更新迁移记录、字段目录和本文件。
5. 任何归档都必须保留 `source_batch_id`、`source_hash`、日期范围和归档位置。

## 7. 多店边界

当前事实表逐步具备 `shop_id`，但部分主数据和 legacy API 仍按单店/`product_id` 工作。因此当前状态是“部分多店、部分单店兼容”。

在真正启用多店前，不建议只添加零散字段。需要一次性核对：

- `products` 是否需要 `shop_id` 及复合唯一键；
- 所有 legacy 表是否需要店铺键；
- API 是否从 `default` 兼容逻辑切换到显式 shop scope；
- 商品 ID 跨店重复时的身份映射规则。

## 8. 推荐的后续顺序

### 阶段一：边界冻结

- 以本文件作为 schema contract。
- 给每个新字段登记来源、粒度、是否允许 NULL。
- 禁止新页面直接读取 raw、observation、lineage 表。

### 阶段二：控制增长

- `collector_data_staging`：成功发布后保留 14～30 天。
- `collector_checkpoints`、扫描明细和成功 artifacts：按运行批次压缩。
- `bi_product_daily_raw`、`monthly_source_payload`：迁移到压缩归档目录，主库保留索引。
- `fact_field_lineage`：先评估是否能把重复的完整值移出主库，再决定压缩方案。

### 阶段三：统一迁移

- 统一 schema migration 入口。
- 冻结 legacy API，只修缺陷，不扩充字段。
- 给事实表命名和接口文档补齐粒度后缀。

### 阶段四：分析库（可选）

只有当跨月分析、宽表聚合明显影响 SQLite 在线读写时，再考虑把历史分析数据复制到 DuckDB；不建议现在直接引入 PostgreSQL。

## 9. 明确禁止的操作

- 不直接清空 `fact_field_lineage` 或 `daily_data_observations`。
- 不把 `store_daily_facts` 与 `daily_data` 强行合并。
- 不把 raw JSON 当作在线事实表使用。
- 不在没有备份和批次索引的情况下执行 `VACUUM`、批量删除或表重建。
- 不因为某个字段当前为 NULL 就回填 0；必须先确认来源是否真的提供该字段。
## Operational addendum (schema version 4)

The database now has two explicit control tables:

- `retention_policies` is the single source of truth for retention days, archive mode, and protected tables. Current defaults are 14 days for published staging, 30 days for collector runtime records, and 180 days for raw payloads. `daily_data_observations` and `fact_field_lineage` are protected and are not eligible for routine deletion.
- `archive_catalog` records every verified external archive with source table, batch identifier, archive path, SHA-256, row count, and value range. An archive is not complete unless this record exists.

The following commands are read-only by default:

```text
python scripts/db_maintenance.py --database data/dashboard.db --output report.json
python scripts/archive_monthly_payload.py --database data/dashboard.db --output report.json
```

The enforcement loop is `scripts/enforce_retention.py`: it reads
`retention_policies`, archives or purges past-cutoff rows, records every
archive in `archive_catalog` with SHA-256 manifests, and skips protected
tables. Default is dry-run; `--apply` mutates.

```text
python -m scripts.enforce_retention --database data/dashboard.db --output report.json        # dry-run
python -m scripts.enforce_retention --database data/dashboard.db --apply --output report.json
```

Applying an archive requires an integrity-checked backup destination. Do not run `VACUUM`, direct `DELETE`, or archive derived observation/lineage tables without a reviewed manifest and dependency check.

## Operational record (2026-09-23 volume cleanup)

Executed with a verified backup at `data/backups/dashboard-20260923-232137.db`:

- Deleted two stale 2.5 GiB `.bak` copies from `data/` (5 GiB disk freed).
- Archived `monthly_source_payload` months 2025-04..2026-02 (48,783 rows) to
  `data/monthly_payload_archive/monthly_source_payload-before-2026-03.jsonl.gz`
  (34 MiB gzip) with manifest; cataloged as `verified`. 20,701 rows remain in
  the live table (2026-03 onward).
- Dropped zero-caller lineage indexes `idx_fact_lineage_product_date` and
  `idx_fact_lineage_source` (~236 MiB); all lineage readers resolve via the
  UNIQUE(shop_id, product_id, date, field_key) auto-index. `db.py` no longer
  recreates them.
- `collector_data_staging`: no rows past the 14-day policy yet (oldest is
  2026-09-18); future purges are handled by `enforce_retention.py`.
- `collector_checkpoints` mode `compact` is intentionally reported as
  unsupported by the enforcer until a compaction format is defined.

## 9. 外部消费者契约（2026-10-05 起生效）

主库自 2026-10 起是多个外部 SKILL 的唯一数据源（数据中台角色），不再只是本应用的私有存储。
本节登记外部消费面；**改动下列表/字段前必须先评估并通知下游**。

### 9.1 消费方清单

| 消费方 | 访问方式 | 位置 |
|---|---|---|
| 本应用（唯一写者） | 导入/补数脚本 + API | 本仓库 |
| 月复盘SKILL `ecommerce-monthly-review` | `scripts/master_db.py`（mode=ro + query_only） | 私有月复盘技能目录 |
| 点击率看板 | `master_db.py`（mode=ro） | 私有点击率看板目录 |
| 产品矩阵地图 | 各脚本 mode=ro 直连 | 私有产品矩阵目录 |

### 9.2 被消费的表和字段（稳定面）

| 表.字段 | 消费方 | 用途 | 口径备注 |
|---|---|---|---|
| `monthly_data.net_sales` | 全部 | GSV/月度汇总/同比/趋势 | =支付金额−退款；`payment_amount` 是支付毛额，勿当GSV |
| `monthly_data.ad_spend / visitors / buyers / cart_users / payment_qty` | 月复盘 | 核心指标卡/趋势 | daily_data 访客叫 `ipv`，两表字段名不同 |
| `monthly_data.gross_profit / operating_profit` | 月复盘 | 利润 | 2026-08 前有值；08-10 由 backfill_monthly_cost_fields 回填 |
| `daily_data.ipv / buyers / operating_profit / net_sales / ad_spend` | 月复盘 | 当月周度聚合、利润 | operating_profit=BI支付预估口径（2026-08=-2.30万已对账） |
| `products.product_tags` | 月复盘/矩阵 | 品类筛选（'默认品类'） | 注意与 `shop_label` 是两个字段，勿混 |
| `products.image_url / status / list_date / title` | 月复盘 | 主图/在架/新品判断 | status是当前快照，非月末快照 |
| `promotion_daily_facts.*`（channel/product粒度） | 月复盘/矩阵 | 推广费/渠道对比 | `channel='全部'` 与分渠道行并存会重复计数，取数方须防重 |
| `promotion_creatives.*` + `promotion_creative_daily.*` | 点击率看板 | 创意CTR分析 | 创意粒度（非素材图片粒度） |
| `sycm_market_rival_shop / rival_item / search_rank` | 月复盘 | 竞店/竞品/搜索词 | 2026-09-15 起；更早月份下游走冻结归档库 |

### 9.3 变更规则

1. 上表的表名/字段名**重命名或删除**前，必须先改完下游消费方并在各消费方 README 登记变更。
2. 新增字段/表不破坏契约，但落入 9.2 语义的字段（如新增一个"支付金额"列）要在本文件补口径说明。
3. 应用升级后，下游 canary 必须重跑：`E:\skill-dianshang\月复盘SKILL\scripts\verify_master_data.py --month <最近完整月>`。
4. 下游消费一律 mode=ro 只读连接、不复制库文件；**写操作只允许通过本仓库 `scripts/import_*` 与 `scripts/backfill_*`**，禁止外部 SKILL 直写。
5. 下游发现数据异常（对不上账）先跑 canary 与 `scripts/verify_market_backfill.py`，再怀疑应用导入。

### 9.4 下游旁路数据（不在主库，需知晓）

| 数据 | 位置 | 说明 |
|---|---|---|
| 2026-08 及更早市场/竞店/搜索词 | 私有冻结只读库（历史市场数据） | 等待经 import_market_* 收编 |
| 素材图片粒度CTR（2026-08/09三商品） | 私有冻结只读库（素材粒度） | 主库只有创意粒度 |
| BI 市场明细（蓝海探测 panel） | 月复盘工作目录 CSV/JSON | 最后一条未收编旁路 |
