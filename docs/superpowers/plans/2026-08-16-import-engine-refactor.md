# Import Engine Refactor Implementation Plan

> For agentic workers: use subagent-driven-development or executing-plans. Steps use checkbox syntax.

**Goal:** 将经营数据导入收敛为一套可测试、可回滚、可扩展的导入引擎，同时保持现有 API、数据库表和导入结果兼容。

**Architecture:** 保留 ImportService 作为唯一业务入口，把来源定义、文件读取、字段映射、质量校验、行标准化和批次写入拆成明确模块。旧的 scripts/import_data.py 改成调用统一服务的兼容适配器；评价、市场、关键词等非经营数据导入不在本次范围内。

**Tech Stack:** Flask、SQLite、pandas、Python dataclasses、现有 unittest/pytest 测试体系。

---

## 现状与约束

- services/import_service.py 约 994 行，混合文件读取、自动识别、映射、质量校验、预览、确认、报告和撤销前置逻辑。
- repos/import_repo.py 同时负责两套批次写入、动态 upsert、批次撤销和动作重开。
- scripts/import_data.py 仍实现另一套 Excel/CSV/ZIP、DMP、经营参谋导入逻辑；/api/upload/data 和定时任务会调用它。
- 现有 /api/imports/preview、/api/imports、/api/imports/<id>/revert 合约不能破坏。
- import_batches、import_batch_changes、import_previews 和业务事实表不改表结构。
- DMP 来源优先级、shop_id 隔离、批次撤销冲突和缺失值不补 0 的语义必须保持。

## 目标边界

本次纳入：product_day、dmp_product_day、store_day、refund_day、customer_day、product_week、product_month 和四种 promotion 粒度。

本次不纳入：评价、市场分析、关键词、图片和其他独立上传接口。

## 文件设计

### 新建

- services/import_specs.py：SourceSpec 注册表，集中保存 required/allowed/key/target/粒度。
- services/import_readers.py：Excel、旧式 .xls HTML、CSV、ZIP 的统一读取。
- services/import_quality.py：字段类型推断、必填字段校验、重复业务键检测和质量摘要。
- services/import_normalizers.py：按 SourceSpec 将 DataFrame 转成业务行，不访问数据库。
- services/legacy_import_adapter.py：把旧文件入口适配到统一 ImportService。

### 修改

- services/import_service.py：保留 preview/confirm/list_batches/revert，对上述模块做编排。
- repos/import_repo.py：拆出批次创建、变更记录、事实写入、来源解析和撤销内部步骤。
- scripts/import_data.py：经营数据入口改为适配器；保留非经营数据函数。
- api/data_api.py、api/schedules_api.py：旧异步接口和定时任务切到适配器。
- api/imports_api.py：审计查询改走 ImportRepo，不在 API 层直接 SQL。
- tests/test_import_workflow.py、tests/test_source_resolution.py：补齐模块契约、旧入口等价性和回滚边界。
- README.md、docs/PRODUCTION_RUNBOOK.md：更新入口和恢复说明。

---

## Task 1: 锁定现有行为

Files:
- Modify: tests/test_import_workflow.py
- Modify: tests/test_source_resolution.py
- Create: tests/test_import_legacy_parity.py

- [ ] Step 1: 为旧入口建立最小等价性测试。对同一份 product-day、DMP、promotion 文件，分别通过新 API 流程和旧 import_excel_file，比较 shop_id、业务键、核心数值、source_type、source_batch_id、quality_summary。
- [ ] Step 2: 运行基线：
  .\.venv\Scripts\python.exe -m pytest -q tests/test_import_workflow.py tests/test_source_resolution.py tests/test_dmp_daily_import.py
  预期：当前基线通过，记录测试数量和耗时。
- [ ] Step 3: 提交：
  git add tests/test_import_workflow.py tests/test_source_resolution.py tests/test_import_legacy_parity.py
  git commit -m "test: lock import engine behavior before refactor"

## Task 2: 建立唯一来源规格

Files:
- Create: services/import_specs.py
- Modify: services/import_service.py
- Modify: tests/test_import_workflow.py

- [ ] Step 1: 定义不可变 SourceSpec：
  SourceSpec(name, required_fields, allowed_fields, key_fields, target_table, target_key_fields, source_system)
  并提供 SOURCE_SPECS 和 get_source_spec(source_type)。
- [ ] Step 2: 把 SOURCE_REQUIREMENTS、SOURCE_ALLOWED_FIELDS、SOURCE_KEY_FIELDS、_estimate_changes 和 _confirm_generic 中的来源/目标映射迁移到注册表；preview、confirm、估算和 generic confirm 全部通过 get_source_spec 查找。
- [ ] Step 3: 保持 mapping_schema.required 和 mapping_schema.allowed 的内容与排序不变；添加 required_fields <= allowed_fields、未知来源和每个来源非空 key 的测试。
- [ ] Step 4: 运行：
  .\.venv\Scripts\python.exe -m pytest -q tests/test_import_workflow.py tests/test_source_resolution.py
  提交：
  git add services/import_specs.py services/import_service.py tests/test_import_workflow.py
  git commit -m "refactor: centralize import source specifications"

## Task 3: 抽离文件读取和质量校验

Files:
- Create: services/import_readers.py
- Create: services/import_quality.py
- Modify: services/import_service.py
- Create: tests/test_import_readers.py
- Create: tests/test_import_quality.py

- [ ] Step 1: 提供纯函数 read_import_frame(content: bytes, filename: str) -> DataFrame，把 _read_csv、_promote_header、_drop_summary_rows、_read_workbook 迁入；读取异常统一为 ImportReadError。
- [ ] Step 2: 提供 validate_frame(frame, mapping, spec, field_aliases, numeric_fields, percentage_fields) -> dict，不访问数据库，并保留 total_rows、raw_total_rows、excluded_summary_rows、valid_rows、invalid_rows、date_range、product_count、duplicate_keys、invalid_details、invalid_field_count、field_warnings、invalid_field_rows。
- [ ] Step 3: 锁定 DMP 语义：optional 坏值进入 invalid_field_rows 但不增加 invalid_rows；required 坏值仍增加 invalid_rows；覆盖 766.67%、空值、-- 和 0。
- [ ] Step 4: 替换 ImportService 调用并运行：
  .\.venv\Scripts\python.exe -m pytest -q tests/test_import_readers.py tests/test_import_quality.py tests/test_import_workflow.py tests/test_source_resolution.py
- [ ] Step 5: 提交：
  git add services/import_readers.py services/import_quality.py services/import_service.py tests/test_import_readers.py tests/test_import_quality.py
  git commit -m "refactor: separate import reading and quality validation"

## Task 4: 抽离行标准化

Files:
- Create: services/import_normalizers.py
- Modify: services/import_service.py
- Create: tests/test_import_normalizers.py

- [ ] Step 1: 提供 normalize_rows(frame, mapping, spec, quality, shop_id, preview_id) -> list[dict]，只返回可交给 ImportRepo 的行，不打开数据库。
- [ ] Step 2: 迁移 _date、_number、_optional_number 以及 confirm/_confirm_generic 的字段转换。optional 缺失不写入 dict；退款字段有效时才生成 net_sales。
- [ ] Step 3: 为每个 SourceSpec 测试一条有效行；覆盖 promotion 空层级、week/month 粒度、DMP 坏 optional 字段隔离和 shop_id 注入。
- [ ] Step 4: 让 confirm 只负责加载预览、校验 mapping、重跑 quality、拒绝 invalid/duplicate、调用 normalize_rows、创建 batch、交给 repo、删除预览和生成报告。
- [ ] Step 5: 运行：
  .\.venv\Scripts\python.exe -m pytest -q tests/test_import_workflow.py tests/test_source_resolution.py tests/test_dmp_daily_import.py tests/test_import_normalizers.py
  提交：
  git add services/import_normalizers.py services/import_service.py tests/test_import_normalizers.py
  git commit -m "refactor: isolate import row normalization"

## Task 5: 收敛批次写入与撤销仓储

Files:
- Modify: repos/import_repo.py
- Modify: api/imports_api.py
- Create: tests/test_import_repo_contract.py

- [ ] Step 1: 在不改公共方法名的前提下增加内部方法：
  _create_batch(connection, batch)
  _record_change(connection, batch_id, table_name, business_key, previous_row)
  _upsert_rows(connection, table_name, key_columns, rows, batch_id)
  _record_daily_resolution(connection, batch, rows)
  _complete_batch(connection, batch, inserted_count, updated_count, quality_summary)
- [ ] Step 2: 表名和 key 列只能来自 SourceSpec 或仓储白名单；未知目标必须抛 ValueError 且不创建 batch。
- [ ] Step 3: 把撤销拆成冲突检测、恢复事实、重算 lineage、动作影响、审计五段；保持 reverted、partially_reverted、后续批次跳过、跨店铺隔离和同事务审计。
- [ ] Step 4: 增加 ImportRepo.list_changes(batch_id)，让 api/imports_api.py 不再直接 import get_db。
- [ ] Step 5: 运行：
  .\.venv\Scripts\python.exe -m pytest -q tests/test_import_repo_contract.py tests/test_import_workflow.py tests/test_source_resolution.py
  提交：
  git add repos/import_repo.py api/imports_api.py tests/test_import_repo_contract.py
  git commit -m "refactor: isolate import batch persistence and rollback"

## Task 6: 让旧入口成为统一引擎适配器

Files:
- Create: services/legacy_import_adapter.py
- Modify: scripts/import_data.py
- Modify: api/data_api.py
- Modify: api/schedules_api.py
- Modify: tests/test_import_legacy_parity.py

- [ ] Step 1: 定义 import_business_file(path: str, shop_id: str = "default") -> dict。读取 bytes，调用 ImportService.preview(source_type="auto")，质量门禁通过后 confirm，返回 rows_imported、batch_id、report。
- [ ] Step 2: 保留 /api/upload/data 的任务创建、轮询、任务 ID 和错误 JSON，只把后台 _do_import 从 import_excel_file 改为 import_business_file。
- [ ] Step 3: 把 api/schedules_api.py 和 api/data_api.py 的经营数据定时扫描改用适配器；评价、市场等函数保持不动。
- [ ] Step 4: parity 测试通过后，删除 scripts/import_data.py 中仅服务于经营数据的 import_daily、import_dmp_daily、import_shengyi_canmou 及重复读取/解析辅助；保留非经营数据函数和兼容导出名。
- [ ] Step 5: 运行：
  .\.venv\Scripts\python.exe -m pytest -q tests/test_import_legacy_parity.py tests/test_import_workflow.py tests/test_dmp_daily_import.py tests/test_schedules_api.py
  提交：
  git add services/legacy_import_adapter.py scripts/import_data.py api/data_api.py api/schedules_api.py tests/test_import_legacy_parity.py
  git commit -m "refactor: route legacy business imports through canonical engine"

## Task 7: 加固预览存储和并发边界

Files:
- Modify: services/import_service.py
- Modify: db.py only if an index is needed
- Create: tests/test_import_preview_safety.py
- Modify: config.py and README.md

- [ ] Step 1: 复用 MAX_CONTENT_LENGTH，增加单预览字节数、ZIP 文件数量/大小和 TTL 门禁；拒绝超限时不得创建 import_previews 行。
- [ ] Step 2: 固定重复确认行为：同一 preview_id 第二次确认返回现有“预览不存在或已过期”，不产生第二个 batch；用两个 service 实例验证持久化路径。
- [ ] Step 3: 注入 batch 写入异常，确认业务表、import_batches、import_batch_changes、observations 和 audit 均不留下半批数据。
- [ ] Step 4: 运行：
  .\.venv\Scripts\python.exe -m pytest -q tests/test_import_preview_safety.py tests/test_import_workflow.py tests/test_source_resolution.py
  提交：
  git add services/import_service.py db.py config.py README.md tests/test_import_preview_safety.py
  git commit -m "hardening: enforce import preview limits and atomicity"

## Task 8: 实现本地固定文件夹扫描与独立 worker

**Files:**
- Create: services/import_scan_service.py
- Create: scripts/run_import_scanner.py
- Modify: db.py
- Modify: config.py
- Create: api/import_scans_api.py
- Modify: app.py
- Create: tests/test_import_scan_service.py
- Create: tests/test_import_scanner_api.py

- [ ] Step 1: Add additive scan tables and config

Add import_scan_jobs, import_scan_files, and import_scan_runs with indexes and uniqueness on (job_id, canonical_path, source_hash). Add IMPORT_SCAN_ALLOWED_ROOTS with data/import-inbox as the default root. Do not change import_batches, import_batch_changes, or import_previews.

- [ ] Step 2: Add scan job validation and CRUD service

Implement ImportScanService.create_job, update_job, disable_job, list_jobs, list_runs, and list_files. Resolve folder_path with os.path.realpath; reject UNC/SMB paths, symlinks, .., paths outside allowed roots, unsupported source types, invalid mapping templates, and invalid cron expressions.

- [ ] Step 3: Add stable-file discovery and fingerprinting

Implement discover_files(job) for the folder's direct children only. Accept .xlsx, .xls, .csv, and .zip; require non-empty files, size <= MAX_CONTENT_LENGTH, mtime older than 60 seconds, and unchanged size/mtime across observations. Calculate SHA-256 and deduplicate by job/path/hash.

- [ ] Step 4: Route discovered files through the canonical engine

For each new fingerprint call ImportService.preview(..., source_type=job.source_type, mapping_template=job.mapping_template). Mark blocked previews when required mappings, invalid rows, or duplicate keys exist. Only a clean preview calls ImportService.confirm; save preview_id, batch_id, error details, and status in import_scan_files.

- [ ] Step 5: Add lease-protected run-once worker

Implement run_due_jobs(now=None) and run_job_once(job_id). Acquire a SQLite lease before scanning, create an import_scan_runs row, continue after single-file failures, mark run completed/partial/failed, and release the lease in finally. Add scripts/run_import_scanner.py --once as the Windows Task Scheduler entrypoint; it must not depend on Flask requests.

- [ ] Step 6: Add scan APIs and register the blueprint

Expose GET/POST /api/import-scans, PUT/DELETE /api/import-scans/<id>, POST /api/import-scans/<id>/run, GET /api/import-scans/<id>/runs, and GET /api/import-scans/<id>/files. Return 409 for an active lease and 422 for invalid local paths or schedules. Register the blueprint in app.py.

- [ ] Step 7: Remove the old schedule execution path

Stop reading scheduled_tasks from request hooks and old run endpoints. Keep existing rows disabled for one release and return 410 LEGACY_SCHEDULE_REMOVED from old schedule endpoints. Update settings UI contracts and tests to use /api/import-scans.

- [ ] Step 8: Test and commit

Run:
    .\\.venv\\Scripts\\python.exe -m pytest -q tests/test_import_scan_service.py tests/test_import_scanner_api.py tests/test_import_workflow.py tests/test_source_resolution.py tests/test_shop_scope_api.py

Then commit:
    git add services/import_scan_service.py scripts/run_import_scanner.py db.py config.py api/import_scans_api.py app.py tests/test_import_scan_service.py tests/test_import_scanner_api.py
    git commit -m "feat: add local folder import scanner"

## Task 9: 全量验证、文档和移除重复代码

Files:
- Modify: README.md
- Modify: docs/PRODUCTION_RUNBOOK.md
- Modify: docs/RELEASE_NOTES.md
- Delete only after parity is green: obsolete business-import functions in scripts/import_data.py

- [ ] Step 1: 运行：
  .\.venv\Scripts\python.exe -m pytest -q tests/test_import_workflow.py tests/test_source_resolution.py tests/test_dmp_daily_import.py tests/test_import_legacy_parity.py tests/test_shop_scope_api.py tests/test_release_gates.py tests/test_production_preflight.py
  预期：exit code 0；旧入口和新入口的 batch、report、fact 结果一致。
- [ ] Step 2: 静态检查：
  rg -n "def import_daily|def import_dmp_daily|def import_shengyi_canmou|def _read_workbook|def _quality|SOURCE_REQUIREMENTS|SOURCE_KEY_FIELDS" services scripts
  预期：经营数据的读取、质量和写入逻辑只在 canonical modules 出现。
- [ ] Step 3: 更新运行手册，明确 UI 预览确认、旧异步接口、定时扫描三条入口都经过 canonical engine；补充失败恢复、批次撤销、partially_reverted 和预览过期处理。
- [ ] Step 4: 提交：
  git add README.md docs/PRODUCTION_RUNBOOK.md docs/RELEASE_NOTES.md scripts/import_data.py
  git commit -m "docs: finalize canonical import engine migration"

## 验收标准

- 所有现有导入 API 路径和响应字段保持兼容。
- 经营数据只有一套解析、质量校验和业务写入规则。
- DMP 来源优先级、字段级告警、跨店铺隔离、重复业务键拒绝、后续批次冲突撤销全部保持原行为。
- 预览只读业务事实表；确认失败不留下半批数据。
- 旧 /api/upload/data 和定时任务不再直接调用旧经营数据写入函数。
- 导入相关回归、店铺隔离、发布门禁全部通过。
- 删除旧代码前必须先通过 parity 测试；任一阶段失败都可以回滚到上一个提交，不需要数据库降级。

## 风险与回滚

- 最大风险是旧脚本对历史文件存在未文档化的容错。Task 1 的 parity 样本必须覆盖 Excel、旧式 .xls、CSV、ZIP、DMP 和经营参谋表；未覆盖格式先保留适配器，不删除旧分支。
- 所有写入继续由 ImportRepo 单事务完成；异常必须 rollback。
- /api/upload/data 只换内部实现，不改任务 ID、轮询字段和错误状态。
- 先保持 pandas 和 SQLite 方案；只有基准证明大文件变慢，才单独优化分块读取或预览存储。

## 提交节奏

每个 Task 一个小提交，顺序为：行为基线 -> 来源规格 -> 读取/质量 -> 标准化 -> 仓储/撤销 -> 旧入口适配 -> 安全加固 -> 文档收尾。任何提交都必须能独立运行聚焦测试并可单独回滚。
