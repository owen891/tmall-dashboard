# TM Dashboard Release Status

发布版本：`1.0.0`

更新时间：2026-08-16

## 当前结论

当前代码可以在本机或受信内网运行，但当前版本仍不可直接上线。代码回归和运行恢复门禁通过；正式发布前必须完成工作区分类、来源血缘回填和生产库备份。

桌面包装链路已在 Windows 11 x64 本机完成构建：PyInstaller 后端、Electron 42、NSIS x64 安装器、`.exe.blockmap` 和 `latest.yml` 均已生成。构建机需要首次下载 Electron/NSIS 构建工具；最终用户安装包不需要 Python、Node.js、WebView2 或翻墙。签名证书未配置，发布前应补充 Windows code signing。

## 证据状态

| 状态 | 当前结论 |
| --- | --- |
| `implemented` | 七个一级页面、正式域 API、数据能力目录和写入证据合同已存在 |
| `preview_verified` | 458 个 Python 测试、39 个子测试，JS 语法、7 个 UI 页面、浏览器 PRD gates、恢复演练均通过 |
| `data_ready` | 当前库有 20,831 条商品日事实；DMP 原始文件已完成扫描但尚未进入当前正式库，推广、市场和行业基准仍有覆盖边界 |
| `production_ready` | 未达到。`release_audit` 当前阻断：`dirty_worktree`、`untraceable_daily_facts`；当前仅按单店范围设计，公网和多租户不在范围内 |

## 必须通过的命令

```powershell
py -3 -m pytest -q tests --ignore=Program
Get-ChildItem frontend/ui_demo/assets -Filter *.js | ForEach-Object { node --check $_.FullName }
node scripts/validate_ui_demos.cjs
py -3 scripts/production_preflight.py
py -3 scripts/release_audit.py --database data/dashboard.db --strict
```

`release_audit.py --strict` 在工作树有修改、数据库混合演示/真实批次、来源血缘缺失或数据库完整性异常时返回非零。它只读，不会清理文件、迁移数据或修改数据库。

## 当前上线阻断

以下不是测试失败，而是生产数据治理门禁，必须处理后才能标记 `production_ready`：

- 工作树当前有 84 个已修改文件和 221 个未跟踪文件，不能直接作为发布包。
- `data/dashboard.db` 需要继续完成来源批次和历史数据清理，发布前不得混入未核验的运行数据。
- `daily_data` 的 20,831 条事实全部缺少 `daily_data_observations` 和 `fact_field_lineage`，当前无法按字段追溯来源、回放裁决或安全撤销历史数据。
- 当前正式库 `import_batches` 没有 `dmp_product_day` 批次；DMP 文件中的补齐字段和参考字段尚未进入正式数据链路。
- 旧事实表和兼容 API 将大量缺失值物化为 `0`（例如 `daily_data` 多个可选字段零值覆盖全部 20,831 行），与“缺失保持缺失、不可计算不显示零”的 PRD 约束冲突；必须完成空值迁移后才能宣称完整数据治理。
- 除带 `shop_id` 的新事实表外，部分商品、周/月事实、推广旧明细、生命周期、动作、目标和评价表仍未完成全链路店铺隔离；本版本只能按单店部署。

数据库恢复演练和完整性检查已通过，但这只能证明 SQLite 文件可复制恢复，不能替代上述来源和发布门禁。

## 数据边界

- `data/dashboard.db` 是生产数据路径，生产运行前必须先备份。
- 当前能力不承诺利润、库存、客户 cohort、严格因果归因或完整市场机会分析。
- 推广贡献分析只能描述已导入的归因构成，不能解释为增量成交或因果结论。

## 遗留治理

- 新页面和新写入必须使用正式域 API 与 service/repository 边界。
- `api/data_api.py` 和 `/legacy/` 仅作为兼容层，不再新增业务逻辑。
- 新增 schema 必须有可回放、可验证的迁移记录；启动时的幂等补列逻辑只用于兼容旧库。
- 完成正式 API 迁移并保留兼容期后，才允许冻结和移除旧写入口。
