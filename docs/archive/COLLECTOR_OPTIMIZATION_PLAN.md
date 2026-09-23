# 天猫数据仪表盘采集系统落地优化方案

> 文档版本：v1.0  
> 适用项目：`tmall-dashboard` 及其外部采集器目录  
> 编制日期：2026-09-18  
> 目标：把当前“多个脚本 + Chrome CDP + SQLite”的采集能力，升级为可调度、可恢复、可审计、可扩展的采集平台。

---

## 1. 结论摘要

当前项目已经具备较强的数据采集能力：

- BI 商品日度、月度数据采集
- 生意参谋店铺流量、单品流量、市场排行采集
- 万相台推广数据采集
- Chrome CDP 登录态复用
- Excel/CSV/ZIP 自动扫描导入
- 导入批次、文件 hash、字段血缘、审计记录

但当前采集系统仍是“脚本集合”，还不是统一的采集平台。主要问题是：

1. 采集器代码位于主项目外部目录，版本无法和看板绑定。
2. API 采集状态依赖进程内锁和 `collect_state.json`，不适合多进程和重启恢复。
3. API 采集、PowerShell 调度、文件扫描存在多套调度入口，可能重复执行。
4. 各采集器自行取 Cookie、调用接口、写数据库、判断成功，落库协议不一致。
5. 多个采集器采用“先删正式数据、再写新数据”，中途失败会产生部分数据或空数据。
6. 退出码通常只代表脚本结束，不代表数据完整、质量通过或发布成功。
7. 店铺 ID、数据库路径、CDP 端口、接口 token 等配置存在硬编码。
8. 万相台区间汇总存在日期归属错误，可能污染日趋势和 ROI。

最终目标不是继续增加脚本，而是建立统一的：

```text
任务模型 → Worker → 会话管理 → 原始数据 → 标准化 → 质量门禁 → 原子发布 → 血缘审计
```

---

## 2A. 项目总体分析（前次分析整合）

### 2A.1 项目定位

这个项目不是单纯的报表页面，而是一个面向单店铺运营团队的：

```text
多源数据采集平台
        +
数据治理与来源血缘仓库
        +
经营分析和商品运营工作台
        +
Web / Electron 双运行形态
```

核心业务闭环是：

```text
采集 / 导入 → 质量校验 → 来源解析 → 事实数据 → 指标计算
      → 总览 / 商品 / 推广 / 市场分析 → 行动 → 复盘 → 审计
```

采集系统优化不能只改脚本。采集任务、数据库事实表、API 响应、前端状态和发布审计必须一起设计，否则会出现“采集成功但看板不可用”或“看板显示成功但来源不可追溯”的断层。

### 2A.2 当前技术栈

| 层次 | 当前实现 | 判断 |
|---|---|---|
| Web 后端 | Flask 3.1、应用工厂、Blueprint | 适合当前单机/内网形态 |
| 数据库 | SQLite、WAL、原生 SQL、部分 Flask-SQLAlchemy | 简单可靠，但数据规模已需治理 |
| 前端 | 原生 HTML/CSS/JavaScript、ECharts、Lucide | 部署简单，长期维护成本偏高 |
| 桌面端 | Electron + PyInstaller Flask/Waitress | 适合离线和本地采集场景 |
| 自动化 | Chrome CDP、PowerShell、Windows Task Scheduler | 能复用登录态，但任务编排分散 |
| 数据治理 | import batch、observation、lineage、audit | 是项目的核心竞争力 |

后端入口是 [app.py](E:/www/tmall-dashboard/app.py)，数据库初始化和大部分表结构在 [db.py](E:/www/tmall-dashboard/db.py)。当前应用大约有 192 个路由，其中约 186 个是 API 路由，说明业务面已经比较宽，采集改造必须保持旧接口兼容并逐步迁移。

### 2A.3 当前已经做得好的地方

1. **应用工厂边界清晰。** `create_app()` 支持测试、桌面、生产配置，数据库路径和环境变量可以隔离。
2. **统一 API 响应协议。** [api/api_response.py](E:/www/tmall-dashboard/api/api_response.py) 能区分 `available`、`no-data`、`partial`、`source-unavailable`，避免把缺失数据伪装为零。
3. **数据治理基础较完整。** 已有 `import_batches`、`daily_data_observations`、`fact_field_lineage`、`reconciliation_results`、`audit_logs` 等结构。
4. **文件扫描器设计成熟。** [services/import_scan_service.py](E:/www/tmall-dashboard/services/import_scan_service.py) 已实现白名单目录、稳定文件判断、SHA-256、lease、失败重试和审计，这部分可以作为 API 采集任务的模板。
5. **测试覆盖较好。** 使用项目虚拟环境运行 `416` 项 unittest，当前基线结果为 `OK`。系统 Python 的依赖缺失不能作为项目失败结论，验证必须使用 `.venv`。
6. **Web 和桌面运行路径都已考虑。** 健康检查、版本检查、生产预检、发布审计和桌面打包测试已经存在。

### 2A.4 当前工作区与发布状态

前次检查时工作区存在多处未提交改动，并新增了万相台 API 和 service。采集优化实施前必须先明确这些改动属于：

- 已确认要发布的功能；
- 正在开发的实验功能；
- 临时调试或应回滚的改动。

采集系统不能在“看板代码一个版本、外部采集器另一个版本、数据库 schema 又是第三个版本”的状态下直接发布。建议建立一个发布清单，至少绑定：

```text
dashboard commit
collector commit / package version
database schema version
VERSION
desktop/package.json
发布 tag
```

### 2A.5 版本一致性风险

当前根目录 `VERSION` 和桌面端 package 已进入 `2.0.2`，但 README 中仍有多处 `2.0.0` 的开发基线、tag 和发布说明。

这会影响：

- `/api/version` 返回值；
- Electron 自动更新元数据；
- 安装包命名；
- GitHub/GitCode Release；
- 发布审计和用户看到的版本。

在采集平台化改造开始前，先统一 `VERSION`、`desktop/package.json`、`desktop/package-lock.json`、README、CHANGELOG、CI tag 规则。采集器也应增加独立版本或随主项目 tag 固定，不能继续依赖本机外部目录的任意修改。

### 2A.6 数据库规模和运行约束

前次检查到生产库大约包含：

| 表/对象 | 规模 |
|---|---:|
| `products` | 约 9.8K |
| `daily_data` | 约 91.8K |
| `monthly_data` | 约 76.3K |
| `promotion_daily_facts` | 约 27.8K |
| `daily_data_observations` | 约 93.9K |
| `fact_field_lineage` | 约 120 万 |
| SQLite 文件 | 约 1.9GB |

这意味着采集优化必须考虑：

- 批量写入和事务时间；
- WAL 文件和锁等待；
- staging 数据是否会放大数据库；
- 原始响应保存位置；
- lineage 和 observation 的归档；
- 备份与恢复时间；
- 桌面端复制大数据库的成本。

短期继续使用 SQLite 是可行的，但必须补充容量监控、备份恢复演练、索引检查和历史数据归档。raw 响应不建议全部直接塞进 SQLite，优先保存为压缩文件，数据库只记录路径、hash 和摘要。

### 2A.7 后端边界和兼容性风险

当前 API 数量较多，并存在新旧接口并存的情况，例如：

- `/api/actions` 与 `/api/legacy/actions`；
- `/api/alert-rules` 与 `/api/alert_rules`；
- `/api/import-scans` 与旧的 `scheduled_tasks` 兼容路由；
- `/api/tasks`、`/api/manage/tasks`、`/api/scheduled_tasks`。

采集平台改造时不宜直接删除旧 API。推荐：

1. 新增正式 `/api/collector/*` 接口。
2. 旧 `/api/collect/*` 保留兼容，内部转成 `collector_runs`。
3. 在响应中标记 deprecated 接口和迁移目标。
4. 为每个正式领域确定唯一 API 所有者。
5. 把采集状态、导入状态和业务事实状态分开，不让前端通过解析日志文本判断成功。

### 2A.8 数据层的单店约束

部分事实表已经包含 `shop_id`，但部分旧表仍是单店结构；项目当前对非 `default` 或特定店铺 scope 存在边界限制。

采集系统必须从任务创建阶段就绑定：

```text
shop_id
platform
account / session
source_key
```

不能出现：

```text
请求使用店铺 A
采集器写入店铺 B
看板查询 default
```

在真正多店化完成前，所有采集器都应该执行 fail-closed 校验：任务店铺、页面当前店铺、请求参数店铺和落库店铺不一致时，阻止发布。

### 2A.9 总体改造原则

结合项目整体架构，采集优化必须遵守以下原则：

```text
采集器不直接决定业务事实
采集器不直接删除正式数据
脚本退出码不等于数据成功
没有质量证据就不能发布
没有 shop scope 就不能写库
没有 run_id 就不能审计
没有 source hash 就不能判断幂等
```

---

## 2. 当前采集架构

```text
                    Web / Electron
                          │
                          ▼
                Flask /api/collect/*
                          │
              进程内线程 + subprocess
                          │
       ┌──────────────────┼──────────────────┐
       ▼                  ▼                  ▼
   BI采集器           SYCM采集器          万相台采集器
   Chrome CDP         Cookie + API         Chrome CDP + API
       │                  │                  │
       └──────────────────┼──────────────────┘
                          ▼
                    SQLite 正式表

另一条独立链路：

Windows Task Scheduler
       ├── auto-collect.ps1
       ├── run_daily_collect.ps1
       └── run_import_scanner.py
                │
                ▼
        文件扫描 / Excel 导入服务
```

### 2.1 当前主要入口

| 入口 | 作用 | 当前问题 |
|---|---|---|
| `api/collect_api.py` | Web 手动触发脚本 | 状态在 JSON 文件和内存中 |
| `scripts/auto-collect.ps1` | 启动 Chrome、登录、触发多个任务 | 通过 HTTP 轮询等待，和其他调度可能重复 |
| `scripts/run_daily_collect.ps1` | 顺序直接运行脚本 | 绕过统一采集状态和 API |
| `scripts/run_import_scanner.py` | 执行本地文件扫描 | 与 API 采集没有统一 run 记录 |
| `services/import_scan_service.py` | 文件发现、稳定性、hash、导入 | 这是目前最适合复用的作业模型 |

### 2.2 当前数据源

| source_key | 来源 | 粒度 | 主要方式 | 目标表 |
|---|---|---|---|---|
| `bi_daily` | BI 商品总览 | 日度 | CDP 页面内 API | `daily_data` |
| `bi_monthly` | BI 月度聚合 | 月度 | 本地聚合脚本 | `monthly_data` |
| `sycm_flow` | 生意参谋店铺流量 | 日度/渠道树 | Cookie + HTTP API | `sycm_flow_source_daily` |
| `sycm_item_flow` | 生意参谋单品流量 | 日度/商品/渠道 | Cookie + HTTP API | `sycm_item_flow_source_daily` |
| `sycm_market` | 生意参谋市场数据 | 日度/类目 | Cookie + HTTP API | 多张市场表 |
| `wanxiangtai` | 万相台推广 | 日度/计划/渠道 | CDP + HTTP API | `promotion_daily_facts` |
| `file_import` | Excel/CSV/ZIP | 文件批次 | 本地目录扫描 | 多张事实表 |

---

## 3. 优化目标和非目标

### 3.1 目标

- 任何采集都能通过 `run_id` 完整追踪。
- 任务重启后可以恢复或安全重试。
- 网络失败只重试失败单元，不重复跑整批。
- 正式数据只允许通过质量门禁后原子发布。
- 原始响应可保存、可校验、可重放。
- Web、桌面端、Windows 任务计划使用同一个任务模型。
- 新增数据源只需实现标准 Adapter，不再复制整套脚本逻辑。
- 数据延迟、覆盖率、失败次数和质量问题可在页面查看。

### 3.2 非目标

本方案第一阶段不要求：

- 立即迁移 PostgreSQL。
- 立即重写所有前端页面。
- 立即取消现有兼容 API。
- 立即实现所有平台的实时流式采集。

先在 SQLite + Windows 环境内完成采集平台化，再决定是否迁移基础设施。

---

## 4. 总体目标架构

```text
                    Web / Electron
                          │
                          ▼
                 Collector Control API
                  创建 / 查询 / 取消 / 重试
                          │
                          ▼
                 collector_runs 数据表
                          │
                          ▼
                 Collector Worker 进程
                  lease / retry / checkpoint
                          │
            ┌─────────────┼─────────────┐
            ▼             ▼             ▼
        BI Adapter    SYCM Adapter   WXT Adapter
            │             │             │
            └─────────────┼─────────────┘
                          ▼
                  Browser Session Manager
                          │
                          ▼
                       Chrome CDP
                          │
                          ▼
                    平台真实接口
                          │
                          ▼
              Raw → Staging → Quality Gate
                          │
                          ▼
                    原子发布正式表
                          │
                          ▼
              batch / observation / lineage
```

### 4.1 代码目录建议

```text
tmall-dashboard/
├── collector_runtime/
│   ├── worker.py
│   ├── scheduler.py
│   ├── session_manager.py
│   ├── retry_policy.py
│   ├── quality_gate.py
│   ├── artifacts.py
│   └── contracts.py
├── collectors/
│   ├── base.py
│   ├── bi/
│   │   └── overview.py
│   ├── sycm/
│   │   ├── flow.py
│   │   ├── item_flow.py
│   │   └── market.py
│   └── wanxiangtai/
│       ├── account.py
│       ├── campaign.py
│       ├── unit.py
│       └── channel.py
├── api/
│   └── collector_api.py
├── services/
│   └── collector_service.py
└── tests/
    ├── test_collector_runtime.py
    ├── test_bi_collector.py
    ├── test_sycm_collector.py
    └── test_wanxiangtai_collector.py
```

### 4.2 采集器统一接口

```python
class CollectorAdapter:
    source_key: str

    def healthcheck(self, context):
        """检查 CDP、登录态、来源接口和配置。"""

    def plan(self, context):
        """把日期、类目、商品、分页拆成可重试的采集单元。"""

    def fetch(self, unit, session):
        """获取原始响应，不直接写正式表。"""

    def normalize(self, raw, unit, context):
        """转换为统一标准行。"""

    def validate(self, rows, raw, context):
        """执行完整性、字段、覆盖率和业务质量校验。"""

    def publish(self, rows, context):
        """通过 staging 和事务原子发布。"""
```

---

## 5. 第一阶段：止血改造（P0，1～3 天）

目标：不改变大架构，先阻止数据丢失、错误成功和重复采集。

### 5.1 统一采集器路径和配置

立即消除以下硬编码：

- `E:\www\BI采集\collectors`
- `E:\www\tmall-dashboard\data\dashboard.db`
- `SHOP_ID = "3828498662"`
- `CDP_PORT = 9222`
- SYCM 固定 token

统一通过以下配置获取：

```text
TMALL_PROJECT_ROOT
TMALL_DB_PATH
TMALL_COLLECTORS_DIR
TMALL_COLLECT_PYTHON
TMALL_SHOP_ID
TMALL_CDP_PORT
TMALL_LOG_DIR
```

采集器必须支持：

```powershell
python collector.py `
  --run-id <run_id> `
  --shop-id <shop_id> `
  --start 2026-09-17 `
  --end 2026-09-17
```

### 5.2 禁止直接删除正式数据

以下模式必须停止使用：

```sql
DELETE FROM formal_table WHERE date = ?;
INSERT INTO formal_table ...;
```

改为：

```text
写入 staging_table
      ↓
质量检查
      ↓
BEGIN TRANSACTION
替换目标日期/店铺范围
写入 batch、observation、lineage
COMMIT
```

如果质量检查失败，保留旧数据，任务状态设置为 `blocked` 或 `partial`。

### 5.3 修复万相台日期口径

当前 `chargeSum` 区间汇总不能直接写到 `end_date`。

规则调整：

- `splitType=day`：每一天独立写入日事实。
- 只有区间总额：写入 `promotion_period_summary`，不能写入日事实。
- `query.json` 的粒度必须和目标表粒度一致。
- `chargeSum.json` 不能覆盖 query 明细中的同粒度字段。

### 5.4 修复万相台字段映射

重点核对：

```python
'alipayDirNum': 'direct_payment_amount'
```

需要建立字段字典，明确：

- 金额
- 订单数
- 买家数
- 直接归因
- 间接归因
- 是否可求和
- 是否为累计值

### 5.5 统一采集脚本退出协议

每个脚本结束时生成 JSON 结果文件：

```json
{
  "run_id": "abc123",
  "status": "succeeded_with_warnings",
  "source": "sycm_market",
  "shop_id": "3828498662",
  "window": {"start": "2026-09-17", "end": "2026-09-17"},
  "requested_rows": 1200,
  "fetched_rows": 1200,
  "normalized_rows": 1188,
  "published_rows": 1188,
  "skipped_rows": 12,
  "coverage": 1.0,
  "quality_status": "passed",
  "warnings": []
}
```

退出码统一为：

| 退出码 | 含义 |
|---:|---|
| 0 | 完整成功 |
| 10 | 成功但有警告 |
| 20 | 部分成功 |
| 30 | 需要重新登录 |
| 40 | 来源字段或接口结构变化 |
| 50 | 可重试的网络/平台错误 |
| 60 | 发布失败 |

### 5.6 防止重复调度

明确只保留一个正式入口：

```text
Windows Task Scheduler
        ↓
collector-worker --once
```

`auto-collect.ps1`、`run_daily_collect.ps1` 只能作为兼容包装器，不能同时配置为计划任务。

---

## 6. 第二阶段：统一任务和运行状态（P1，1～2 周）

### 6.1 新增 `collector_runs`

```sql
CREATE TABLE collector_runs (
    id TEXT PRIMARY KEY,
    source_key TEXT NOT NULL,
    shop_id TEXT NOT NULL,
    window_start TEXT,
    window_end TEXT,
    mode TEXT NOT NULL DEFAULT 'scheduled',
    status TEXT NOT NULL,
    priority INTEGER NOT NULL DEFAULT 100,
    attempt INTEGER NOT NULL DEFAULT 0,
    worker_id TEXT,
    lease_until TEXT,
    requested_by TEXT,
    started_at TEXT,
    finished_at TEXT,
    checkpoint_json TEXT NOT NULL DEFAULT '{}',
    stats_json TEXT NOT NULL DEFAULT '{}',
    error_code TEXT,
    error_message TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_collector_runs_due
ON collector_runs(status, priority, created_at);

CREATE INDEX idx_collector_runs_source_window
ON collector_runs(source_key, shop_id, window_start, window_end);
```

### 6.2 新增 `collector_checkpoints`

```sql
CREATE TABLE collector_checkpoints (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id TEXT NOT NULL,
    unit_type TEXT NOT NULL,
    unit_key TEXT NOT NULL,
    page_no INTEGER,
    cursor TEXT,
    status TEXT NOT NULL,
    row_count INTEGER NOT NULL DEFAULT 0,
    source_hash TEXT,
    last_error_code TEXT,
    last_error_message TEXT,
    started_at TEXT,
    finished_at TEXT,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(run_id, unit_type, unit_key, page_no),
    FOREIGN KEY(run_id) REFERENCES collector_runs(id)
);
```

典型 unit：

| 数据源 | unit_type | unit_key |
|---|---|---|
| BI 日度 | `date` | `2026-09-17` |
| 单品流量 | `product` | 商品 ID |
| 市场排行 | `category` | 类目 ID |
| 市场分页 | `category_page` | `类目 ID:page` |
| 万相台 | `report` | `query:day` |

### 6.3 新增 `collector_artifacts`

```sql
CREATE TABLE collector_artifacts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id TEXT NOT NULL,
    source_key TEXT NOT NULL,
    artifact_type TEXT NOT NULL,
    file_path TEXT NOT NULL,
    sha256 TEXT NOT NULL,
    size_bytes INTEGER NOT NULL,
    content_type TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(run_id, artifact_type, sha256),
    FOREIGN KEY(run_id) REFERENCES collector_runs(id)
);
```

原始数据目录建议：

```text
data/raw/{shop_id}/{source_key}/{run_id}/
data/staging/{shop_id}/{source_key}/{run_id}/
data/results/{shop_id}/{source_key}/{run_id}.json
```

### 6.4 新增 `collector_quality_results`

```sql
CREATE TABLE collector_quality_results (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id TEXT NOT NULL,
    rule_key TEXT NOT NULL,
    severity TEXT NOT NULL,
    expected_value TEXT,
    actual_value TEXT,
    status TEXT NOT NULL,
    message TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(run_id) REFERENCES collector_runs(id)
);
```

### 6.5 状态机

```text
queued
  ↓
running
  ├── succeeded
  ├── succeeded_with_warnings
  ├── partial
  ├── blocked
  ├── auth_required
  ├── failed
  └── cancelled
```

规则：

- `queued` 只能被一个 worker lease。
- `running` 超过 lease 时间可被恢复。
- `auth_required` 不自动重试，等待重新登录。
- `schema_changed` 进入 `blocked`。
- `partial` 必须保留失败 unit 清单。
- `succeeded` 必须有发布批次和质量结果。

---

## 7. 第三阶段：统一采集流水线（P1，2～4 周）

所有数据源统一执行：

```text
healthcheck
    ↓
plan units
    ↓
fetch raw response
    ↓
calculate source hash
    ↓
normalize
    ↓
validate
    ↓
write staging
    ↓
quality gate
    ↓
atomic publish
    ↓
write batch / observation / lineage
    ↓
emit result
```

### 7.1 healthcheck

检查：

- Chrome CDP 是否可达
- 目标页面是否存在
- 当前页面域名是否正确
- 是否已登录
- Cookie 是否存在
- token/csrf 是否有效
- 数据库是否可写
- 采集器版本是否匹配

### 7.2 plan

将一次大任务拆分为可恢复单元：

- 日期
- 店铺
- 类目
- 商品
- 页码
- 报表类型

### 7.3 fetch

只负责获取原始响应，不负责正式写入。

要求：

- 记录请求参数摘要
- 记录响应状态
- 记录请求耗时
- 记录原始 hash
- 不记录 Cookie、密码和完整认证头

### 7.4 normalize

将平台字段映射到项目统一字段，保留：

- `source_field`
- `normalized_field`
- `raw_value`
- `normalized_value`
- `unit`
- `quality_flag`

### 7.5 validate

至少包含：

- 日期范围检查
- 店铺 scope 检查
- 主键重复检查
- 必填字段检查
- 数值范围检查
- 分页完整性检查
- 覆盖率检查
- 和历史数据对比
- schema 变化检查

### 7.6 publish

只有质量通过后才允许：

```text
staging → formal fact
```

发布操作必须与以下内容在同一个事务中完成：

- 正式事实表
- import batch
- observation
- lineage
- quality summary

---

## 8. 数据质量门禁

### 8.1 通用规则

| 规则 | 阻断级别 |
|---|---|
| shop_id 与任务不一致 | BLOCK |
| 日期超出任务范围 | BLOCK |
| 主键重复 | BLOCK |
| 接口返回空且历史有数据 | WARN/BLOCK，按来源配置 |
| 行数低于近 7 日均值 70% | WARN |
| 关键字段缺失 | BLOCK |
| 分页未完成 | BLOCK |
| 采集达到人工上限 | WARN，必须标记 capped |
| 金额为负 | BLOCK |
| Cookie 失效 | AUTH_REQUIRED |
| 字段 schema 变化 | BLOCK |

### 8.2 BI 商品日度

```text
商品数 >= 过去7天均值 × 70%
实际行数 = 接口 total
有效商品 ID 比例 >= 99%
目标日期只有一个完整快照
返回的店铺 ID 与配置一致
```

### 8.3 生意参谋店铺流量

```text
顶级渠道数 > 0
level、parent_channel 层级关系完整
level=0 的汇总和子节点不会重复计入同一指标
stat_date 全部等于任务日期
```

### 8.4 生意参谋单品流量

```text
目标商品数、成功商品数、失败商品数可追踪
MAX_ITEMS 限制必须写入 coverage
失败商品必须进入 checkpoint
不能用部分商品结果标记为完整成功
```

### 8.5 市场排行

```text
类目列表完整
实际页数、平台总数、采集行数都要保存
Top N 模式必须标记 is_complete=false
商品排行、关键词排行、竞店和竞品分开统计
```

### 8.6 万相台

```text
start_date <= end_date
日粒度事实必须有真实日期
query 与 chargeSum 不覆盖同一粒度
花费、成交金额、点击量不可为负
字段映射版本必须记录
区间汇总不能伪装成日事实
```

---

## 9. 重试与恢复策略

不要对所有异常统一重跑 3 次，应按错误类型处理：

| 错误类型 | 自动重试 | 处理 |
|---|---:|---|
| 网络超时 | 是 | 指数退避 |
| HTTP 429/5xx | 是 | 延迟重试 |
| Cookie 失效 | 否 | `auth_required` |
| 页面不存在 | 否 | `environment_error` |
| 字段结构变化 | 否 | `schema_changed` |
| 空数据 | 视规则 | 质量门禁 |
| 数据库锁 | 是 | 短间隔重试 |
| 单个商品失败 | 是 | 只重试失败商品 |
| 质量门禁失败 | 否 | 保留旧数据，人工确认 |

推荐退避：

```text
30 秒 → 2 分钟 → 10 分钟 → 30 分钟
```

### 9.1 断点续采示例

单品流量任务：

```text
总商品：500
成功：312
失败：8
待采：180
```

重试时只能执行 8 个失败商品，而不是重新请求 500 个商品。

---

## 10. 各数据源改造要点

### 10.1 BI 商品日度

当前风险：固定 `pageSize=2000`、完整快照判断不足、直接改正式表。

改造：

1. 改为分页请求。
2. 保存每页原始响应和 checkpoint。
3. 校验 `total` 与实际数量。
4. 完整快照通过门禁后再替换目标日期。
5. 商品元数据与日事实分开发布。
6. 缺失商品先标记 `not_seen`，不要立即物理删除。

### 10.2 生意参谋店铺流量

当前风险：Cookie 选择不稳定、token 硬编码、先删后写。

改造：

1. 通过公共 session manager 获取页面和登录态。
2. token 进行动态检查。
3. 先写 staging，再原子替换。
4. 保存渠道树快照和层级校验结果。
5. 业务 code 非 0 时视为失败，即使 HTTP 是 200。

### 10.3 生意参谋单品流量

当前风险：最多 500 个商品、逐个请求、中间失败后不易恢复。

改造：

1. 先生成商品 unit 清单。
2. 一个商品一个 checkpoint。
3. 成功、失败、跳过分别统计。
4. 有限并发，建议 2～4。
5. 失败只重试失败商品。
6. `MAX_ITEMS` 明确写入 coverage。

### 10.4 生意参谋市场

当前风险：商品排行最多 6 页，可能把 Top 300 误认为完整市场数据。

改造：

1. 类目作为独立 unit。
2. 商品、关键词、竞店、竞品拆为不同 source。
3. 记录 page_count、total_count、row_count。
4. 区分“完整采集”和“Top N 采集”。
5. 结果中明确 `is_complete` 和 `coverage`。

### 10.5 万相台

建议拆分事实粒度：

```text
promotion_account_daily
promotion_channel_daily
promotion_campaign_daily
promotion_unit_daily
promotion_product_daily
promotion_period_summary
```

职责划分：

```text
query.json     计划/单元/商品/关键词明细
chargeSum.json 账户或渠道汇总
```

如果 `chargeSum` 只有区间汇总，写入 `promotion_period_summary`，不能写入日事实。

---

## 11. Chrome 会话和安全改造

### 11.1 统一 Browser Session Manager

所有采集器禁止自行实现：

- 查找页面
- 获取 Cookie
- 获取 WebSocket
- 获取 token
- 判断登录状态

统一由 `session_manager.py` 提供：

```python
session = browser.get_session(
    domain='one.alimama.com',
    page_hint='report',
)

session.assert_authenticated()
session.fetch_json(url, payload)
```

### 11.2 CDP 安全要求

- 只绑定 `127.0.0.1`。
- 使用独立 Chrome profile。
- 使用可配置或随机 CDP 端口。
- 不允许端口暴露到局域网。
- 采集完成后关闭或回收专用 profile。
- 日志中禁止打印 Cookie、密码、完整 token。

### 11.3 登录凭据

不建议通过命令行参数传密码，因为进程查看工具可能读取参数。

优先级：

1. 人工登录后复用会话。
2. Windows Credential Manager。
3. 环境变量。
4. 禁止写入仓库、日志和任务计划命令行。

---

## 12. API 设计建议

新增正式 API：

```text
GET  /api/collector/sources
POST /api/collector/runs
GET  /api/collector/runs
GET  /api/collector/runs/<run_id>
POST /api/collector/runs/<run_id>/retry
POST /api/collector/runs/<run_id>/cancel
GET  /api/collector/runs/<run_id>/quality
GET  /api/collector/runs/<run_id>/artifacts
GET  /api/collector/health
```

创建任务示例：

```json
{
  "source_key": "sycm_item_flow",
  "shop_id": "3828498662",
  "window_start": "2026-09-17",
  "window_end": "2026-09-17",
  "mode": "manual",
  "options": {
    "max_items": 500,
    "belong": "farthest"
  }
}
```

返回：

```json
{
  "ok": true,
  "data": {
    "run_id": "01J...",
    "status": "queued",
    "source_key": "sycm_item_flow"
  }
}
```

现有 `/api/collect/trigger` 保留兼容，但内部改成创建 `collector_runs`，不要再直接启动 Flask daemon thread。

---

## 13. 采集页面优化

现有采集页面建议增加四个区域。

### 13.1 数据源健康

- 最近成功时间
- 当前数据日期
- 数据延迟
- 连续失败次数
- 认证状态
- 最近一次耗时
- 最近一次行数

### 13.2 运行记录

- run_id
- 来源
- 店铺
- 时间范围
- 状态
- 耗时
- 重试次数
- 写入行数
- 质量状态

### 13.3 数据质量

- 覆盖率
- 缺失天数
- 重复数
- 截断状态
- 字段变化
- 异常金额
- 失败 unit 数量

### 13.4 原始证据

- 原始响应文件
- source_hash
- 请求参数摘要
- 接口地址
- 响应摘要
- 采集时间

---

## 14. 调度策略建议

| 数据源 | 建议时间 | 范围 | 失败回补 |
|---|---:|---|---|
| BI 商品日度 | 次日 08:00 | 昨日 | 最近 3 天 |
| 生意参谋店铺流量 | 次日 09:00 | 昨日 | 最近 3 天 |
| 单品流量 | 次日 09:30 | 昨日 | 失败商品 |
| 市场排行 | 次日 10:00 | 昨日 | 失败类目 |
| 万相台 | 次日 10:30 | 昨日 | 最近 7 天 |
| 月度聚合 | 每月 2 日 | 上月 | 手动重跑 |
| 历史回补 | 手动 | 指定区间 | 可暂停 |

任务属性必须包含：

- 计划时间
- 优先级
- 最大运行时长
- 最大重试次数
- 重试间隔
- 是否允许部分成功
- 是否允许覆盖旧数据

---

## 15. 测试与验收标准

### 15.1 单元测试

- Adapter 字段映射
- 日期和粒度转换
- 重试策略
- 状态机迁移
- checkpoint 恢复
- quality gate
- 原子发布
- source hash 幂等

### 15.2 集成测试

- Chrome 不可用
- Cookie 失效
- 页面找不到
- API 返回 429
- API 返回 200 但业务 code 非 0
- 分页中断
- 单个商品失败
- 数据库锁
- 进程中断后恢复
- 重复提交相同 run

### 15.3 数据一致性测试

- 同一 run 重试不能产生重复事实。
- 同一 source/date/shop 重复采集必须幂等。
- 质量门禁失败不能删除旧数据。
- 导入失败后不能留下 `completed` 批次。
- 万相台区间汇总不能写入错误日份。
- 多店铺数据不能互相覆盖。

### 15.4 发布前验收

```powershell
.venv\Scripts\python.exe -m unittest discover -s tests -v
.venv\Scripts\python.exe scripts/production_preflight.py
.venv\Scripts\python.exe scripts/release_audit.py --database data/dashboard.db --strict
node scripts/validate_ui_demos.cjs
```

额外增加：

```powershell
.venv\Scripts\python.exe -m unittest discover -s tests -p 'test_collector*.py' -v
.venv\Scripts\python.exe scripts/collector_healthcheck.py
.venv\Scripts\python.exe scripts/collector_recovery_drill.py
```

---

## 16. 分阶段实施清单

### 阶段 0：准备

- [ ] 确认采集器目录归属：并入主仓库或独立版本库。
- [ ] 统一 `TMALL_DB_PATH`、`TMALL_SHOP_ID`、`TMALL_CDP_PORT`。
- [x] 已核对现有 Windows 计划任务，未发现同一来源重复调度；新增注册脚本使用独立任务名，避免覆盖现有任务。
- [x] 已记录数据库备份、SHA-256、integrity check 和恢复演练结果。
- [x] 已建立 `TMALL_COLLECTOR_VERSION` 与脚本 manifest hash。

### 阶段 1：止血

- [x] 正式数据删除仅在完整快照校验或 staging 原子发布事务中执行；局部重试禁止整日清理。
- [x] BI 增加完整快照校验。
- [x] SYCM 增加分页/覆盖率结果。
- [x] 万相台修复日粒度和区间汇总问题：单日 `chargeSum` 才写日事实，多日区间汇总拒绝写入日事实。
- [x] 万相台修复字段映射：`alipayDirNum` 不再误映射为金额，修正 query 字段请求。
- [x] worker 为所有采集运行统一生成 `RESULT_JSON` 终态事件（schema version 1），覆盖成功、进程失败、异常、超时和环境失败，兼容旧采集器普通日志。
- [x] 失败导入不能返回成功：自动采集脚本会传播导入失败状态，批次异常标记为 `failed`。

### 阶段 2：任务平台化

- [x] 增加 `collector_runs`。
- [x] 增加 `collector_checkpoints`。
- [x] 增加 `collector_artifacts`。
- [x] 增加 `collector_quality_results`。
- [x] 用数据库 lease 约束跨进程重复执行（进程内锁保留作快速路径）。
- [x] 当前 subprocess worker 已由 API 统一创建运行记录、注入环境、收集结果和释放 lease；独立常驻 worker 作为后续并发扩展项。
- [x] API 负责创建和管理任务，采集脚本通过标准环境变量和 `RESULT_JSON` 回传结果。

### 阶段 3：统一数据管道

- [x] 外部来源 raw artifact/staging 已落地；BI raw 与 lineage 已有可审计归档工具。
- [x] 主要来源已进入 staging，旧式来源由 worker 建立快照适配层。
- [x] 主要来源已接入质量门禁和原子发布。
- [x] BI 导入统一使用 batch、observation、lineage；运行平台保存 source batch 关联。
- [x] 按 unit 支持 checkpoint 和局部重试。
- [x] 已建立 `/api/collect/catalog` 来源字段目录。

### 阶段 4：可观测性和扩展

- [x] 新增采集健康页面。
- [x] 新增连续失败告警：健康检查按来源计算最近运行的连续失败次数，达到 3 次时创建/更新持久化告警。
- [x] 新增数据延迟告警（健康接口超过 3 天降级，报告支持 webhook）。
- [x] 新增 schema 变化告警：`scripts/collector_schema_check.py` 保存字段目录签名，漂移时返回退出码 2 并持久化告警。
- [x] 增加数据库容量和备份监控基础（备份、完整性、恢复演练已验证）。
- [x] 已提供 `scripts/archive_collector_artifacts.py`：默认 dry-run，`--apply` 时复制、hash 校验、更新索引后再删除原文件。
- [x] 新增 `scripts/archive_lineage_raw.py`：按日期导出 BI raw、observation、field lineage 为 gzip JSONL，生成 manifest/hash，校验后再事务删除。
- [x] 已提供 `scripts/postgres_migration_assessment.py`，基于当前 72 张表、约 183 万行和 SQLite 文件规模生成迁移评估报告。

---

## 17. 优先级和预计收益

| 优先级 | 工作项 | 收益 |
|---|---|---|
| P0 | 禁止先删后写 | 避免采集中断造成数据丢失 |
| P0 | 修复万相台日粒度 | 避免趋势和 ROI 失真 |
| P0 | 统一路径和店铺配置 | 避免跨环境写错库/错店 |
| P0 | 统一退出协议 | 避免“脚本成功但数据失败” |
| P1 | `collector_runs` | 获得完整运行审计 |
| P1 | checkpoint | 支持断点续采、局部重试 |
| P1 | staging + 原子发布 | 提升数据一致性 |
| P1 | Browser Session Manager | 降低 CDP 和登录态故障 |
| P1 | 质量门禁 | 阻止坏数据进入正式表 |
| P2 | 统一采集页面 | 提升运维效率 |
| P2 | raw/artifact 管理 | 支持回放和问题定位 |
| P2 | 采集器 Adapter 化 | 降低新增数据源成本 |
| P2 | 数据归档/迁移 | 控制 SQLite 规模 |

---

## 18. 最终判断

项目当前已经拥有“采集器”和“数据看板”，下一步应建设的是“采集控制平面”。

最重要的七个基础能力是：

```text
统一任务模型
统一运行记录
统一断点机制
统一会话管理
统一质量门禁
统一原子发布
统一来源血缘
```

在这七项完成之前，不建议继续大量增加新的采集源。否则每增加一个脚本，都会同步增加一套状态、重试、落库和排错逻辑，最终会让系统变得难以维护。

推荐优先级：

```text
先保证数据不丢、不重、不乱
再保证任务可恢复、可审计
最后提升并发、性能和数据源覆盖
```

---

## 19. 首周开工方案（可直接拆分任务）

这一周只做“止血和统一入口”，不同时重写所有采集器。

### Day 1：建立基线和备份

负责人：后端/运维

- [x] 已备份 `data/dashboard.db` 并完成完整性与恢复演练。
- [x] 已通过 production audit 记录采集器目录、脚本 hash、Python、CDP 配置。
- [x] 已导出状态、计划任务和最近日志摘要到生产审计报告。
- [x] 已核对当前计划任务，无同源重复调度。
- [x] 外部采集器暂保持独立目录，并以 manifest/hash 作为明确版本证据。

验收：任何人拿到项目、配置说明和采集器版本后，都能复现一次“昨日 BI 日度采集”的运行环境。

### Day 2：统一配置和参数

负责人：后端

改动范围：

- `api/collect_api.py`
- 所有外部 collector 脚本
- `config.py` / `.env.example`
- `scripts/auto-collect.ps1`
- `scripts/run_daily_collect.ps1`

新增统一配置：

```text
TMALL_DB_PATH
TMALL_SHOP_ID
TMALL_COLLECTORS_DIR
TMALL_COLLECT_PYTHON
TMALL_CDP_PORT
TMALL_LOG_DIR
TMALL_COLLECT_TIMEOUT_SECONDS
```

所有脚本必须支持：

```text
--run-id
--shop-id
--start
--end
--db-path
--cdp-port
--result-file
```

验收：修改数据库路径和店铺 ID 后，脚本不会写回硬编码路径；参数缺失时应明确失败，而不是默默使用错误默认值。

### Day 3：统一结果和失败语义

负责人：后端

新增公共模块：

```text
collector_runtime/result.py
collector_runtime/errors.py
collector_runtime/logging.py
```

每个采集器必须生成：

```text
result.json
stdout.log
stderr.log
```

禁止以下情况：

- 导入异常被捕获后仍返回 0。
- 返回空数据但状态标记完整成功。
- 部分商品失败但没有失败清单。
- 数据库只写入部分结果却没有事务失败标记。

验收：构造网络失败、空数据、Cookie 失效和数据库锁四种场景，脚本状态分别可区分，且退出码和 JSON 结果一致。

### Day 4：改造 staging 发布

负责人：后端/数据层

先选 `sycm_flow` 或 `bi_daily` 作为试点，不要一次改全部数据源。

实施顺序：

1. 新增 staging 表或临时表。
2. 采集结果全部先写 staging。
3. 执行行数、日期、店铺、主键和字段质量检查。
4. 质量通过后开始正式表事务。
5. 正式表替换、batch、observation、lineage 同一事务提交。
6. 任一步失败，回滚正式表并保留 staging 和原始证据。

验收：人为中断写入过程，旧正式数据仍然存在；重跑同一个 run 不产生重复记录。

### Day 5：先修万相台

负责人：推广/数据后端

- [x] 区分日粒度、计划粒度、单元粒度和区间汇总。
- [x] 禁止区间 `chargeSum` 写到 `end_date` 的日事实。
- [x] 修正 `alipayDirNum` 等字段映射。
- [x] query 和 chargeSum 已明确来源职责。
- [x] 失败导入返回失败状态并保留失败批次。
- [x] 万相台已有字段目录与服务/API 回归 fixture。

验收：导入 7 天样例后，日事实必须有 7 个日期；区间汇总只能出现在 summary 表或明确的 summary 粒度中。

### Day 6：统一采集任务状态

负责人：后端

先增加 `collector_runs`，再把旧 API 映射过去：

```text
POST /api/collect/trigger
        ↓
创建 collector_runs
        ↓
worker 执行
        ↓
/api/collect/status 查询 collector_runs
```

第一阶段允许继续使用 subprocess，但不再以进程内字典作为唯一状态源。

验收：重启 Flask 后，任务状态和运行记录仍然可查询；同一来源同一时间窗不能创建两个未完成 run。

### Day 7：回补、审计和发布门禁

负责人：运维/产品

- [x] 已完成回补/局部重试的 fixture、checkpoint 和 retry-diff 演练；真实登录态回补仍需生产窗口执行。
- [x] 已对失败 unit 完成局部重试逻辑与差异报告验证。
- [x] 采集页面显示运行状态、失败原因、质量和 staging 结果。
- [x] 已执行完整测试、生产预检、release audit。
- [x] 已生成健康、schema 和生产审计报告。

验收：业务人员可以回答以下问题：

```text
昨天哪些来源采集成功？
哪些数据是部分成功？
哪个商品/类目失败？
正式表何时被发布？
数据来自哪个原始响应？
如果异常，如何只重试失败部分？
```

---

## 20. 数据库迁移顺序和兼容策略

### 20.1 迁移原则

采用“先加表、再双写、后切读、最后清理”的方式，不直接改掉现有表。

```text
新增 collector_* 表
        ↓
旧采集入口创建 run 并双写状态
        ↓
页面读取新状态
        ↓
采集器全部接入新状态
        ↓
观察一个完整周期
        ↓
下线 collect_state.json 唯一职责
```

### 20.2 迁移步骤

1. 新增 `collector_runs`、`collector_checkpoints`、`collector_artifacts`、`collector_quality_results`。
2. 为表增加必要索引，不修改已有事实表主键。
3. `api/collect/trigger` 创建 run，并把旧 source key 映射到 run。
4. 旧 `collect_state.json` 只作为兼容缓存，不再作为真实状态源。
5. `api/collect/status` 优先读取数据库，JSON 只作为没有历史 run 时的兜底。
6. 所有采集器改成写 result.json 和 batch/run 关联。
7. 连续运行 7 天无状态分叉后，再删除 JSON 状态的写入逻辑。

### 20.3 回滚方案

任何阶段发现异常时：

- 保留新增表，不删除数据。
- 将页面查询切回旧状态接口。
- 停止新 worker，只允许旧脚本手动运行。
- 从迁移前数据库备份恢复正式事实表。
- 使用原始 artifact 重新验证问题，不直接手改业务事实。

严禁使用 `git reset --hard` 或直接删除生产数据库作为回滚手段。

---

## 21. 第一批建议创建的开发任务

建议按以下顺序建立 issue 或任务卡：

| 编号 | 任务 | 交付物 | 优先级 |
|---|---|---|---|
| C-001 | 采集器配置集中化 | 配置读取模块、`.env.example` 更新 | P0 |
| C-002 | 采集结果和退出码协议 | result schema、错误码、单元测试 | P0 |
| C-003 | BI 日度 staging 发布 | staging 表、质量门禁、原子替换 | P0 |
| C-004 | 万相台粒度和字段修复 | 字段字典、fixture、导入测试 | P0 |
| C-005 | collector_runs 迁移 | schema、service、兼容 API | P1 |
| C-006 | checkpoint 和局部重试 | checkpoint service、重试接口 | P1 |
| C-007 | Browser Session Manager | CDP 页面选择、登录态、token 管理 | P1 |
| C-008 | SYCM 覆盖率和截断标记 | coverage 统计和质量结果 | P1 |
| C-009 | raw artifact 管理 | 压缩 JSON、hash、路径索引 | P1 |
| C-010 | 采集健康页面 | 运行、质量、证据三个面板 | P2 |
| C-011 | 采集器版本绑定 | collector manifest、发布检查 | P2 |
| C-012 | SQLite 容量治理 | 备份、恢复、归档脚本 | P2 |

---

## 22. 最小可行版本（MVP）定义

如果资源有限，第一版不必一次完成全部目标。只要满足以下条件，就可以认为采集平台 MVP 成立：

```text
1. 所有运行都有 run_id。
2. 所有运行都有明确状态和退出原因。
3. 正式数据不会因采集失败而被清空。
4. 同一时间窗重复执行是幂等的。
5. 至少一个来源支持 checkpoint 和局部重试。
6. 万相台日粒度不再发生日期错配。
7. 采集结果能够追溯到原始响应 hash。
8. Web 页面可以看到最近一次质量结果。
```

MVP 达成后，再逐步扩展到：

- 多来源并发
- 更细粒度的计划/单元采集
- 自动告警
- 原始数据回放
- PostgreSQL 或分库
- 多店铺正式支持

---

## 23. 已实施进度（2026-09-18）

第一阶段已完成“持久化运行记录 + 进程级 checkpoint”切片：

- [x] 新增 `collector_runs` 表。
- [x] 新增 `collector_checkpoints` 表。
- [x] 新增 `collector_quality_results` 表结构。
- [x] 新增 `services/collector_run_service.py`。
- [x] `/api/collect/trigger` 返回 `run_id`。
- [x] 采集进程生命周期写入 `queued/running/succeeded/failed`。
- [x] 超时、环境失败、进程失败和异常写入结构化错误。
- [x] 新增 `GET /api/collect/runs/<run_id>` 查询运行、checkpoint 和质量结果。
- [x] `process` checkpoint 支持幂等更新。
- [x] 新增采集运行服务、API 和 checkpoint 测试。
- [x] 使用项目 `.venv` 执行全量测试并通过。
- [x] 万相台 `chargeSum/query` 粒度与字段映射修复，并增加服务/API 回归测试。
- [x] 通用导入增加 `import_staging_rows`：标准化行先落 staging，再在同一事务内发布；发布状态可审计。
- [x] 采集运行增加数据库级 `collector_leases`，跨进程阻止同一店铺/来源重复执行，并在结束时释放。
- [x] 采集运行持久化质量门禁结果，覆盖环境检查、退出码和空输出检测，并在运行详情返回门禁结论。
- [x] 采集 API 兼容结构化 checkpoint 日志事件（`CHECKPOINT_JSON`），可按商品、类目和页码写入断点。
- [x] BI 商品日度、SYCM 店铺流量、SYCM 单品流量、SYCM 市场排行、万相台脚本已输出对应业务单元 checkpoint 事件。
- [x] 新增 `/api/collect/runs/<run_id>/retry`：默认生成失败 unit 计划，`execute=true` 时创建 retry run 并只传递失败 unit。

当前仍未完成：

- [x] 采集脚本支持 `TMALL_RETRY_UNITS_JSON` 过滤失败商品/类目。
- [x] 新增 `services/collector_retry_service.py`，按 checkpoint 创建 retry run 并执行脚本。
- [x] 新增 `collector_artifacts` 和压缩 raw output 保存，运行详情可查询 artifact hash/path。
- [x] 新增 artifact 回放接口 `/api/collect/runs/<run_id>/artifacts/<artifact_id>`，读取前校验路径和 SHA-256。
- [x] retry worker 解析子 run checkpoint，并在 `stats_json.retry_summary` 写入成功/失败/缺失 unit 差异。
- [x] 新增 `/api/collect/runs/<parent_run_id>/retry-diff/<child_run_id>`，返回恢复率及未解决 unit。
- [x] BI 商品日度试点接入两阶段 staging 发布：正式写入异常时回滚事实表并保留 rejected staging 证据。
- [x] 新增采集 staging 查询接口 `/api/collect/runs/<run_id>/staging`，可查看每个 unit 的发布状态。
- [x] 外部登录采集器（SYCM 店铺流量、单品流量、市场数据、万相台）已迁移到统一 staging + 质量门禁 + 原子发布；BI 月度属于本地聚合任务，沿用日度发布结果，不单独视为外部采集器。
- [x] 其余旧式采集器在 worker 成功后自动生成最新分区 staging 快照，并执行非空质量门禁；后续仍需将脚本自身改造成 staging-first 原子发布。
- [x] 店铺流量采集器 `collect_sycm_flow.py` 已接入 staging-first：通过 `TMALL_COLLECT_RUN_ID/TMALL_DB_PATH` 获取运行上下文，在同一事务内完成 staging、质量校验和正式分区替换。
- [x] 单品流量采集器 `collect_sycm_item_flow_v6.py` 和市场采集器 `collect_sycm_market.py` 已接入同样的 staging-first 事务流程。
- [x] 万相台 API 导入已接入 staging-first：日事实和区间汇总均先写 staging，质量通过后在同一事务发布。
- [x] 万相台自动采集携带 `TMALL_COLLECT_RUN_ID`，staging 批次与 collector run 关联，可通过 `/api/collect/runs/<run_id>/staging` 追溯。
- [x] 修复单品流量采集器正式表字段不一致（`page_level`/`collect_count`），并通过临时 SQLite 写入冒烟验证。
- [x] worker 向所有外部采集器传递运行 ID 与数据库路径，避免脚本写入错误数据库并支持逐个迁移为原子发布。
- [x] 失败 unit 重试后的正式 checkpoint 差异报告。
- [x] raw artifact 保存与回放。

万相台区间汇总已落地到 `promotion_period_summary`，日粒度仍写入 `promotion_daily_facts`，两者不再混用；区间汇总不会再伪装成结束日期的日事实。

因此当前状态是“平台化基础层已接入，正式采集器迁移仍在进行”，不能把现有进程级 checkpoint 误认为已经完成全部断点续采能力。

### 23.1 运营查询与 staging 质量摘要（2026-09-18）

- [x] 新增 `GET /api/wanxiangtai/period-summary`，按日期交集和渠道查询 `promotion_period_summary`，明确区间汇总与日事实分离。
- [x] 采集 staging 查询返回 `quality` 摘要：状态计数、空 payload、重复业务单元、rejected 行和总体门禁结论。
- [x] 增加万相台区间汇总查询回归测试，防止区间数据被误读为结束日期日数据。

### 23.2 生产闭环补齐（2026-09-18）

- [x] worker 统一传递 `TMALL_COLLECT_RUN_ID`、`TMALL_DB_PATH`，外部采集器不再依赖固定数据库路径。
- [x] 新增 `/api/collect/health`，汇总来源最新事实、最近运行、7 日失败数和 staging 状态。
- [x] 新增 `scripts/collector_healthcheck.py`，可定时生成 JSON 健康报告并返回健康/降级退出码。
- [x] 数据采集页面接入采集健康摘要，展示异常来源、7 日失败运行和 staging 发布/拒绝统计。
- [x] 已有 `scripts/backup_database.py`、`scripts/run_daily_backup.ps1` 和 `scripts/production_preflight.py` 形成备份、完整性与恢复演练基础。
- [x] 健康接口在空库/缺历史表场景下返回可审计的降级结果，不再因单表缺失直接报 500。
- [x] 健康接口增加事实数据延迟判断（超过 3 天进入降级），健康报告支持通过 `TMALL_HEALTH_WEBHOOK` 或 `--webhook` 在降级时通知。
- [x] 新增 `/api/collect/catalog` 来源字段目录，统一描述来源表、日期字段、业务单元、发布模式和关键字段。
- [x] SYCM 店铺流量、单品流量、市场采集输出覆盖率事件，worker 将预期/成功/失败单元和覆盖率写入运行统计。
- [x] 使用临时 SQLite 完成备份 SHA-256 和 `integrity_check` 冒烟验证。
- [x] 外部采集器统一读取 `TMALL_DB_PATH`、`TMALL_CDP_PORT`，worker 注入 `TMALL_COLLECTOR_VERSION`。
- [x] 新增 `scripts/collector_manifest.py`，记录采集器脚本 SHA-256、Python、数据库和 CDP 配置。
- [x] BI 商品日度增加完整快照校验：接口总数与实际商品数不一致时拒绝发布；局部重试只更新指定商品，不执行整日缺失清理。
- [x] SYCM 覆盖率事件已归一化写入 `collector_runs.stats_json.coverage`，包含预期、成功、失败单元和覆盖率。
- [x] 全量回归测试通过：705 tests，0 failures。
- [x] 新增健康告警、schema 快照、终态结果协议和生产审计测试；专项采集测试 28 tests 通过。
- [x] 2026-09-18 已对 `data/dashboard.db` 完成生产备份与恢复演练：备份文件 `data/backups/dashboard-production-20260918-222354.db`，大小约 2.1GB，源/备份 `integrity_check=ok`，恢复副本迁移后 71 张表可用。
- [x] 已只读核对 Windows 计划任务：BI 11:30、SYCM/万相台 09:30、备份 03:00，未发现同一来源重复调度。
- [x] 新增 `scripts/run_collector_observability.ps1`，统一执行健康检查和 schema 漂移检查并保留 JSON 证据。
- [x] 健康检查和 schema 检查在服务不可用时输出结构化 JSON 错误并返回退出码 1；降级/漂移仍分别返回 2。
- [x] 新增 `scripts/install_collector_tasks.ps1`，幂等注册/删除采集、观测、备份三个 Windows 计划任务。
- [x] `run_daily_collect.ps1` 自动识别外部采集器目录 `E:\www\BI采集\collectors`，避免计划任务未设置环境变量时找不到脚本。
- [x] `run_daily_collect.ps1` 支持 `RunId/ShopId/Start/End/DbPath/CdpPort/ResultFile/Sources` 标准参数，并输出 `batch_result` JSON；兼容 API source key 和脚本名筛选。
- [x] 新增 `scripts/collector_production_audit.py`，只读导出数据库完整性、采集器脚本 hash、状态文件、计划任务和最近日志，形成可审计生产证据包。
- [x] 生成 `logs/postgres-migration-assessment.json` 和 `logs/collector-artifact-archive-dry-run.json`，归档与数据库迁移均先有证据再执行变更。
- [x] 生成 `logs/lineage-raw-archive-dry-run.json`：按 180 天策略评估 raw/lineage 归档范围，当前未执行删除。

### 23.3 生产任务注册

最终收敛验收入口见 `COLLECTOR_CONVERGENCE_CHECKLIST.md`。后续仅执行其中列出的生产操作，不再新增采集平台功能。

首次部署（管理员 PowerShell）：

```powershell
.\scripts\install_collector_tasks.ps1 -ProjectRoot E:\www\tmall-dashboard
```

任务名称和默认时间：

| 任务 | 时间 | 作用 |
|---|---:|---|
| `TmallDashboard-Collectors` | 11:30 | 顺序执行 BI/SYCM/万相台采集 |
| `TmallDashboard-Observability` | 12:15 | 健康检查、连续失败告警、schema 漂移检查 |
| `TmallDashboard-Backup` | 03:00 | 数据库备份和保留策略清理 |

删除任务使用：

```powershell
.\scripts\install_collector_tasks.ps1 -ProjectRoot E:\www\tmall-dashboard -Remove
```

观测脚本返回码约定：`0` 正常，`2` 降级或 schema 漂移，`1` 执行错误。计划任务不应配置 `auto-collect.ps1` 与 `run_daily_collect.ps1` 同时运行。

生产审计导出：

```powershell
.venv\Scripts\python.exe scripts\collector_production_audit.py `
  --database E:\www\tmall-dashboard\data\dashboard.db `
  --collectors-dir E:\www\BI采集\collectors `
  --output logs\collector-production-audit.json
```
