# 采集平台收敛验收清单

更新时间：2026-09-18

## 已验收

- [x] 运行生命周期：`collector_runs`、lease、checkpoint、质量门禁。
- [x] 数据安全：staging-first、原子发布、BI 完整快照校验、局部重试不误删。
- [x] 可追溯：raw artifact、SHA-256、回放、observation、lineage。
- [x] 可观测：健康接口、健康页面、连续失败/延迟/schema 告警、`RESULT_JSON`。
- [x] 运维：备份、恢复演练、生产预检、release audit、生产审计报告。
- [x] 生命周期：artifact 与 raw/lineage 归档工具，默认 dry-run。
- [x] 回归：705 tests，0 failures。

## 证据文件

- `logs/collector-production-audit.json`
- `logs/postgres-migration-assessment.json`
- `logs/lineage-raw-archive-dry-run.json`
- `logs/collector-artifact-archive-dry-run.json`
- `logs/collector-schema-latest.json`
- `COLLECTOR_OPTIMIZATION_PLAN.md`

## 生产执行顺序

1. 确认 Chrome 已登录对应平台，再执行真实采集或失败 unit 回补。
2. 先执行健康检查和 schema 检查，确认返回码为 `0`。
3. 业务确认保留周期后，先 review 归档 dry-run，再显式执行 `--apply`。
4. 归档后执行 `production_preflight.py` 和完整测试。
5. PostgreSQL 仅在并发写入或查询性能达到阈值后启动双写迁移。

## 禁止事项

- 没有登录态时不要伪造真实采集结果。
- 没有业务确认时不要执行 raw/lineage `--apply`。
- 不要同时启用 `auto-collect.ps1` 和 `run_daily_collect.ps1`。
- 不要用 dirty worktree 的 release audit 结果作为正式发布批准。

## 当前状态

代码与测试收敛完成。剩余工作仅为生产窗口内的真实回补、归档批准和未来是否迁移 PostgreSQL 的决策，不再继续扩大实现范围。
