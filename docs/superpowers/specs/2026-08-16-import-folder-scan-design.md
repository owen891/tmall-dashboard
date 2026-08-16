# Import Engine and Local Folder Scan Design

**Date:** 2026-08-16

## 1. Goal

将经营数据导入统一为一套逻辑引擎，并增加本地固定文件夹扫描能力。扫描发现的文件必须复用现有的 preview、字段映射、质量校验、confirm、import batch、audit 和 revert 协议。

旧的 scheduled_tasks/file_pattern 定时导入链路下线。新调度只负责触发本地扫描 worker，不在 Flask 请求钩子中执行导入。

## 2. Scope

### Included

- product_day
- dmp_product_day
- store_day
- refund_day
- customer_day
- product_week
- product_month
- promotion_channel_day
- promotion_campaign_day
- promotion_unit_day
- promotion_product_day
- 本地固定文件夹扫描
- 自动导入调度、手动运行、运行历史、文件去重和失败重试

### Excluded

- 评价、市场、关键词、图片等独立上传功能
- SMB/UNC 网络路径
- 递归扫描子目录
- 多进程内嵌 scheduler
- 第二套专用于扫描的解析或写库逻辑

## 3. Architecture

### Canonical import engine

ImportService 是唯一业务入口，分为以下纯职责模块：

- import_specs：来源、必填字段、允许字段、业务键、目标表。
- import_readers：xlsx、旧式 xls HTML、csv、zip 读取和表头提升。
- import_quality：字段类型、必填校验、重复键、字段级告警。
- import_normalizers：DataFrame 转标准业务行。
- ImportRepo：批次事务写入、来源解析、变更记录、撤销和审计。
- legacy_import_adapter：兼容旧异步上传和命令行入口，但内部只调用 ImportService。

所有 UI、旧异步接口、定时扫描都只能调用这套 engine。

### Local scanner

新增独立 worker：

    scripts/run_import_scanner.py --once

worker 每次执行：

1. 读取启用且到期的 import_scan_jobs。
2. 使用数据库租约取得任务执行权。
3. 校验 folder_path 的 realpath 和允许根目录。
4. 枚举目录本层的匹配文件。
5. 忽略扩展名不支持、正在写入和已处理的文件。
6. 为新文件建立文件指纹和 scan file 记录。
7. 调用 ImportService.preview。
8. required_unmapped、invalid_rows 或 duplicate_keys 非空时标记 blocked，不写入业务表。
9. 预览通过后调用 ImportService.confirm，产生标准 import batch。
10. 写入 scan run 和 scan file 结果，更新任务的 last_run/next_run。

worker 不依赖 HTTP 请求。Windows Task Scheduler 每分钟调用一次 --once；同一任务只能被一个 worker 租约执行。

## 4. Data Model

### import_scan_jobs

新增表：

- id INTEGER PRIMARY KEY
- task_name TEXT NOT NULL
- folder_path TEXT NOT NULL
- file_pattern TEXT NOT NULL DEFAULT '*'
- source_type TEXT NOT NULL DEFAULT 'auto'
- mapping_template_json TEXT NOT NULL DEFAULT '{}'
- cron_expr TEXT NOT NULL
- enabled INTEGER NOT NULL DEFAULT 1
- status TEXT NOT NULL DEFAULT 'active'
- last_run TEXT
- next_run TEXT
- lease_token TEXT
- lease_until TEXT
- last_error TEXT
- created_at TEXT
- updated_at TEXT

约束：

- folder_path 必须是本机绝对路径，realpath 后必须位于配置的 IMPORT_SCAN_ALLOWED_ROOTS 之一。
- file_pattern 只能匹配目录本层；禁止 ..、通配到目录外或执行文件。
- source_type 必须来自 SourceSpec 注册表。
- mapping_template_json 必须是 JSON object。

### import_scan_files

新增表：

- id INTEGER PRIMARY KEY
- job_id INTEGER NOT NULL
- canonical_path TEXT NOT NULL
- source_filename TEXT NOT NULL
- size_bytes INTEGER NOT NULL
- mtime_ns INTEGER NOT NULL
- source_hash TEXT NOT NULL
- status TEXT NOT NULL
- preview_id TEXT
- batch_id TEXT
- error_code TEXT
- error_message TEXT
- discovered_at TEXT
- imported_at TEXT
- updated_at TEXT
- UNIQUE(job_id, canonical_path, source_hash)

status 枚举：

- discovered
- blocked
- importing
- imported
- failed
- ignored

同一路径文件内容变化后，source_hash 变化，允许产生新的 scan file 记录；同一文件版本不会重复 confirm。

### import_scan_runs

新增表：

- id TEXT PRIMARY KEY
- job_id INTEGER NOT NULL
- started_at TEXT NOT NULL
- completed_at TEXT
- status TEXT NOT NULL
- discovered_count INTEGER NOT NULL DEFAULT 0
- imported_count INTEGER NOT NULL DEFAULT 0
- blocked_count INTEGER NOT NULL DEFAULT 0
- failed_count INTEGER NOT NULL DEFAULT 0
- error_message TEXT

status 枚举：

- running
- completed
- partial
- failed

### Existing import tables

import_batches、import_batch_changes、import_previews 保持原有结构和语义。自动导入的 batch 通过 import_scan_files.batch_id 关联，不在现有 batch 表中复制扫描字段。

## 5. File Stability and Safety

扫描前检查：

- 文件扩展名属于 xlsx、xls、csv、zip。
- 文件不是目录、符号链接或目录外路径。
- 文件大小大于 0 且不超过 MAX_CONTENT_LENGTH。
- 文件 mtime 距当前时间至少 60 秒，避免读取正在上传的文件。
- 连续两次扫描中 size_bytes 和 mtime_ns 不变才允许 preview。
- zip 内部文件数量和解压后大小受限，不允许路径穿越。

路径必须经过 os.path.realpath；只允许配置的 IMPORT_SCAN_ALLOWED_ROOTS。默认根目录为 data/import-inbox，不把 data/uploads 作为新扫描目录。

## 6. API

### GET /api/import-scans

返回任务列表、启用状态、路径、cron、last_run、next_run、最近错误和统计。

### POST /api/import-scans

请求字段：

- task_name
- folder_path
- file_pattern
- source_type
- mapping_template
- cron_expr
- enabled

创建前完成路径、模式、source_type、cron 和 mapping_template 校验。

### PUT /api/import-scans/<id>

允许修改 task_name、folder_path、file_pattern、source_type、mapping_template、cron_expr、enabled。修改 folder_path 或 source_type 时清除任务租约，不删除历史 scan files。

### DELETE /api/import-scans/<id>

软停用任务并保留 runs/files/audit 历史，不物理删除历史数据。

### POST /api/import-scans/<id>/run

手动触发一次扫描，复用 worker 的 run-once 函数。若任务已有有效租约，返回 409。

### GET /api/import-scans/<id>/runs

返回扫描运行历史和统计。

### GET /api/import-scans/<id>/files

返回发现文件、状态、preview_id、batch_id、错误和更新时间，支持按 status 过滤。

## 7. Old Schedule Removal

下线以下执行入口：

- api/schedules_api.py 的 /api/manage/schedules*
- api/data_api.py 的 /api/scheduled_tasks*
- data_api.before_request 中的 _check_and_run_scheduled_tasks
- 旧 scheduled_tasks.file_pattern 扫描和 scripts/import_data.import_excel_file 定时调用

迁移策略：

1. 新版本启动时保留 scheduled_tasks 表和历史数据，但全部标记 disabled/legacy。
2. 不再读取 scheduled_tasks 执行任务。
3. 旧 API 返回 410 LEGACY_SCHEDULE_REMOVED，并指向 import-scans API。
4. 前端设置页移除旧 schedule 控件，改为 import scan job 配置。
5. 完成一个发布周期后，再提供显式迁移脚本删除 scheduled_tasks 表；不在首次发布中静默删除历史数据。

## 8. Error and Retry Policy

- 路径或配置非法：任务创建/更新返回 422，不创建 scan job。
- 租约冲突：手动运行返回 409，不重复扫描。
- 文件不稳定：本次 run 标记 ignored，下一次重新检测。
- 预览字段缺失、质量异常、重复键：scan file 标记 blocked，保留 preview_id 和质量摘要，不写业务表。
- ImportService.confirm 失败：scan file 标记 failed，保存错误，不改变已有 batch。
- 单文件失败不影响同一 run 的其他文件；run 状态为 partial。
- 同一文件版本重试时复用已有 source_hash，不能创建第二个 batch；只有显式重试且原状态为 failed/blocked 才重新尝试。
- worker 未完成时租约过期，下一次执行可接管；import batch 事务保证不会产生半批数据。

## 9. Testing

新增测试：

- path realpath、允许根目录、符号链接和 .. 拒绝。
- 文件扩展名、空文件、文件稳定性和大小上限。
- 同一路径同 hash 去重，文件修改后生成新版本。
- preview 阻塞不写 daily_data/import_batches。
- 通过 preview 自动 confirm，scan file 能关联 batch。
- DMP、promotion 和多店铺数据仍遵循统一 source resolution。
- 单文件失败不影响同 run 其他文件。
- 租约冲突返回 409，过期租约可接管。
- worker 重复执行不会重复导入。
- 旧 schedule API 返回 410，scheduled_tasks 不再被执行。
- 删除/停用任务后历史 runs/files/audit 仍可查询。
- 现有 tests/test_import_workflow.py、tests/test_source_resolution.py、tests/test_shop_scope_api.py 和发布门禁全部保持通过。

## 10. Acceptance Criteria

- 所有经营数据入口共用 ImportService canonical engine。
- 新建扫描任务可配置本地文件夹、匹配规则、来源类型、字段模板和 cron。
- worker 可被 Windows Task Scheduler 每分钟调用，且不依赖 Flask 请求。
- 合法稳定文件自动导入；异常文件不会写入业务事实表。
- 同一文件版本最多产生一个 import batch。
- 每个自动 batch 可追溯到 scan job、scan run、文件 hash 和审计记录。
- 旧 scheduled_tasks 不再触发导入；旧 API 明确返回迁移错误。
- 扫描、导入、失败、阻塞、重试和撤销均有可查询记录。
- 不支持 SMB/UNC、不递归子目录、不增加第二套导入规则。

## 11. Rollback

- 新表只做 additive migration；回滚代码不会影响现有 import_batches 和业务事实。
- 禁用 worker 即可停止自动扫描，手动 UI 导入仍可用。
- 若扫描 worker 出现问题，将 import_scan_jobs.enabled 全部置 0，恢复旧版本代码；不重新启用 scheduled_tasks。
- 在删除旧 schedule API 前保留一个版本的 410 兼容响应，避免客户端收到无意义的 404。

