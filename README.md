# 天猫数据仪表盘

版本：`1.0.0`

面向单店铺运营团队的数据分析和商品运营闭环工具。项目保持 Flask + SQLite + 原生 HTML/CSS/JavaScript，不引入第二套前端或数据库。

## 快速开始

当前发布基线使用 Python 3.14；请使用与之匹配的依赖版本安装。

```powershell
py -3 -m venv .venv
.\.venv\Scripts\Activate.ps1
py -3 -m pip install -r requirements.txt
py -3 app.py
```

打开 `http://127.0.0.1:5000/`。主工作台固定为总览、商品、推广、生命周期、复盘、数据中心、设置七页；旧页面仅通过 `/legacy/` 兼容访问。

## 本地生产启动

本机生产运行使用 Waitress，不使用 Flask 开发服务器。先完成数据库备份，再以局域网监听地址启动：

```powershell
Copy-Item data/dashboard.db data/dashboard.db.bak
$env:DASHBOARD_USERNAME = 'operator'
$env:DASHBOARD_PASSWORD = 'replace-with-a-long-random-password'
& .\scripts\start_production.ps1 -BackupBeforeStart
```

启动后在本机验证：

```powershell
Invoke-WebRequest http://127.0.0.1:5000/healthz | Select-Object -ExpandProperty Content
```

返回 `"ok":true` 且 `"database":"ok"` 才可进入局域网访问。非本机访问必须携带上述 Basic Auth 凭据；部署前将 `data/dashboard.db` 放在本机受控路径，Windows 防火墙仅允许受信任网段访问端口 `5000`。

启动前可运行只读预检；默认使用临时数据库，不会修改运营数据：

```powershell
py -3 scripts/production_preflight.py
```

## 数据导入

数据中心规划三种数据接入方式：

1. 手动导表：支持 `.xlsx`、`.xls`、`.csv`、`.zip`，可多选，先预览和字段映射，再做质量校验与事务确认；这是当前版本已交付的方式。
2. 固定目录定时扫描：按受控目录、文件规则和扫描计划发现最新日期文件，生成待确认批次；这是下一阶段能力，不能绕过现有导入门禁。
3. AI 扫描/采集处理：辅助发现来源、识别字段和提出采集建议，最终仍必须回到同一套预览、质量校验、人工确认和批次审计；这是未来扩展能力。

三种方式共用 `source_type`、业务键、字段映射模板、质量摘要、幂等 upsert 和审计/撤销协议。缺少 R1 必填字段会阻止写入，缺失或不足数据显示为无数据/数据不足，不补造 0。

每个批次记录 `source_type`、业务键、映射模板、质量摘要和审计日志。撤销只恢复该批次实际影响且没有被后续批次覆盖的事实；存在覆盖冲突时返回 409，不做静默删除。

## 数据库迁移、备份与恢复

启动时 `db.init_db()` 执行幂等迁移。升级前备份 SQLite 文件：

```powershell
Copy-Item data/dashboard.db data/dashboard.db.bak
py -3 -c "from db import init_db; init_db()"
```

恢复时停止 Flask，将备份复制回 `data/dashboard.db` 后重新启动。不要直接编辑运行中的数据库；目标、动作、生命周期人工调整均保留版本和审计记录。

## 已知边界

- 推广计划、单元、创意、地域、内容归因只有在对应粒度事实导入后才开放，下钻不会构造不存在的行。
- 生命周期需要连续有效日达到 60 天；季节性需要 12 个完整自然月。数据不足显示“数据积累中”，人工覆盖会标记来源并保留历史。
- 目标原子值是日目标，年、季、月、周、日由日目标聚合；调整校验锁定周期、版本和年度守恒。

## 验证

## Local Import Scanner

Automatic imports use the same `ImportService` engine as manual preview and
confirm. Configure a local folder under `IMPORT_SCAN_ALLOWED_ROOTS` (the
default is `data/import-inbox`), create a job through `/api/import-scans`, and
schedule `python scripts/run_import_scanner.py --once` with Windows Task
Scheduler. The worker scans direct children only, waits for two stable
observations, blocks failed quality checks, and records scan files, runs, and
the resulting import batch. The old `/api/manage/schedules*` and
`/api/scheduled_tasks*` endpoints return `410 LEGACY_SCHEDULE_REMOVED`.

```powershell
py -3 -m unittest discover -s tests -v
Get-ChildItem frontend/ui_demo/assets -Filter *.js | ForEach-Object { node --check $_.FullName }
node scripts/validate_ui_demos.cjs
py -3 scripts/production_preflight.py
py -3 scripts/production_preflight.py --recovery-source data/dashboard.db
py -3 scripts/release_audit.py --database data/dashboard.db
```

发布前使用 `py -3 scripts/release_audit.py --database data/dashboard.db --strict`。
该检查只读，会明确报告脏工作树、演示/真实批次混合和数据库完整性问题。

## PRD 验收矩阵（2026-08-14）

最新验证：458 项完整回归通过，包含 39 个子测试；全部正式 JS 语法检查、七页静态门禁和浏览器 PRD 门禁通过。跨店回归覆盖日度导入、KPI、趋势、总览、商品、对比、推广查询及导入批次审计/撤销；周/月事实、目标、生命周期、动作及依赖单店旧表的工具接口仍是单店结构，非 `default` 店铺请求或周/月导入（包括预览和确认）会返回 `UNSUPPORTED_SCOPE`，避免静默串店。

演示数据必须写入独立数据库，不允许命令行默认修改 `data/dashboard.db`。使用 `py scripts/seed_demo_data.py --demo-database` 创建或更新 `data/demo/dashboard.db`；测试或受控演练可使用 `--database <path>`，只有明确添加 `--allow-production-database` 才能触碰生产库。演示命名空间使用 `DEMO-*` 或“演示”标记，包含 8 个商品、2025-01-01 至 2026-08-12 的日/周/月事实、推广四级粒度、生命周期历史、动作和复盘；种子脚本幂等，不覆盖目标库中的非演示事实。

| PRD 范围 | 当前状态 | 说明 |
|---|---|---|
| 第 5 节全局规则 | 已验证 | URL 参数、页面能力清理、前进后退、不支持筛选提示和七种 API 状态均有浏览器证据。 |
| 第 7 节目标体系 | 已验证 | 年/季/月/周/日从日原子目标聚合；增长倍率建议、自动拆解、版本、锁定、冲突和审计有测试。 |
| 第 8 节运营动作 | 已验证 | 动作状态机、待复盘默认列表、观察窗口回算、完整动作历史和复盘字段有测试。 |
| 第 9 节生命周期 | 已验证 | 数据门槛、阶段/季节性、依据、置信度、迁移历史和人工锁定已有测试。 |
| 第 10 节七页工作台 | 已验证 | 七个一级页面、商品详情、推广下钻、完整筛选导出、数据中心报告和模板跨刷新消费均已接通。 |
| 第 12 节视觉规范 | 已验证 | 32 个页面/视口组合无页面错误、HTTP 错误或不可恢复横向溢出，图表画布有像素输出。 |
| 第 13 节 API 契约 | 已验证 | 标准 envelope、availability、来源批次、完整导出、导入报告和页面支持矩阵均有契约或浏览器证据。 |
| 第 15 节非功能 | 已验证 | 上传限制、事务导入、冲突安全撤销、分页、写审计和首页 5 秒门禁均有自动化测试。 |
| 第 16 节验收 | 已验证 | 完整测试、浏览器行为、四视口、预检、恢复演练和独立代码复核全部通过；周/月单店边界已在 API 和 PRD 中明确。 |

明确边界：评价/市场/周期对比/工具箱等历史能力仍保留在兼容 API 或 `/legacy/`；它们不是当前七个一级页面的主导航。`docs/ui_demo/` 是旧归档，可能含 Chart.js 引用；主应用 `frontend/ui_demo/` 不含 Chart.js，统一使用 ECharts。

字段、来源、R1/R2 状态和公式见 [docs/FIELD_DICTIONARY.md](docs/FIELD_DICTIONARY.md)，产品验收条款见 [docs/PRD_KEEP_EXISTING_ARCHITECTURE.md](docs/PRD_KEEP_EXISTING_ARCHITECTURE.md)。
