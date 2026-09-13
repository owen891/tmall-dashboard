# 天猫数据仪表盘

[![Release](https://img.shields.io/badge/release-v1.0.2-167d4a)](https://github.com/owen891/tmall-dashboard/releases/tag/v1.0.2)
![Python](https://img.shields.io/badge/Python-3.14-3776ab)
![Flask](https://img.shields.io/badge/Flask-SQLite-111111)

面向单店铺运营团队的经营分析与商品运营工作台。系统以 Flask、SQLite 和原生 HTML/CSS/JavaScript 构建，把经营结果、商品表现、推广投放、生命周期、行动复盘和数据治理放在同一套可追溯流程中。

当前版本：[`v1.0.2`](https://github.com/owen891/tmall-dashboard/releases/tag/v1.0.2)。更新说明和安装包均在 GitHub Release 页面提供。

## 产品界面

总览先给出净销售额、转化、目标进度和待处理动作；商品运营承接筛选、分析和行动；数据中心负责导入、校验、审计与来源治理。

## 核心能力

| 能力 | 1.0.0 交付内容 |
|---|---|
| 经营分析 | 总览、趋势、目标进度、商品对比与经营异常提示 |
| 商品运营 | 商品分层、筛选、生命周期、运营动作、复盘与历史追踪 |
| 推广分析 | 推广汇总及计划、单元、创意、地域等已导入粒度的下钻分析 |
| 数据接入 | Excel、旧版 HTML `.xls`、CSV、ZIP 手动导入与受控目录定时扫描 |
| 数据治理 | 字段映射、质量门禁、批次审计、来源 observation/lineage 与冲突安全撤销 |
| 发布防护 | 生产预检、数据库备份恢复、店铺隔离检查和发布审计 |

## 数据来源策略

重复字段不做简单覆盖，以业务系统的权威来源为准；DMP 用于交叉参考、补充缺失以及承接其他表格没有的独有字段。

| 字段类型 | 主来源 | DMP 角色 |
|---|---|---|
| 生意与转化指标 | 生意参谋 | 参考或缺失补充 |
| 推广花费与归因指标 | 推广工具 | 参考或缺失补充 |
| 搜索、推荐、预售、复购、连带购买等独有字段 | DMP | 有效来源 |

导入时保留 `source_type`、源批次、字段映射、质量摘要和写入审计。缺失或不足的数据展示为“无数据 / 数据不足”，不会用 `0` 或推测值填充。

## 快速开始

当前发布基线使用 Python 3.14：

```powershell
py -3 -m venv .venv
.\.venv\Scripts\Activate.ps1
py -3 -m pip install -r requirements.txt
py -3 app.py
```

打开 `http://127.0.0.1:5000/`。主工作台包括总览、商品运营、推广分析、生命周期、经营复盘、数据中心和设置。

Web 版会通过 `/api/version` 检查当前发布版本；检测到服务器已发布新版本时，页面顶部会提示刷新，刷新后加载新的前端资源。Web 版的实际升级仍由服务器部署流程完成，浏览器不会直接覆盖服务器文件。

## Windows 桌面版

桌面版将 Electron 窗口、Chromium 和 PyInstaller Flask/Waitress 后端一起打包，目标电脑不需要预装 Python、Node.js、浏览器或 WebView2。首次安装包可离线运行；在线更新从公开 GitHub Releases 下载。

本地构建 Windows x64 安装包：

```powershell
.\scripts\build_desktop.ps1
```

产物位于 `desktop/release/`，包含 NSIS 安装器、blockmap 和 `latest.yml`。发布前请从干净 checkout 开始（不要在带有本地构建产物、数据库或未提交改动的工作树上打 tag）：

```powershell
git fetch --tags origin
git checkout --detach origin/main
git clean -fdx
(Get-Content VERSION -Raw).Trim()
git tag v1.0.2
git push origin v1.0.2
```

标签必须与根目录 `VERSION` 完全一致（例如 `VERSION=1.0.2` 对应 `v1.0.2`）。`desktop-release.yml` 只允许 `push` 的 `v*` 标签进入发布；手动 `workflow_dispatch` 不会发布，避免从非 tag 提交创建 Release。Windows 与 macOS 使用相同的 Python/Node 运行时、锁定依赖、桌面测试和 Chromium 门禁，构建完成后由单一串行 job 合并并发布 Release。

本地运行真实浏览器门禁前安装仓库依赖和 Chromium：

```powershell
npm ci --prefix desktop
npx --prefix desktop playwright install chromium
$env:TMALL_SMOKE_BASE = 'http://127.0.0.1:8770'
node scripts/smoke_core_pages.cjs
node scripts/audit_core_interactions.cjs
```

发布审计要求干净工作树，并检查敏感产物、数据库完整性、导入批次和事实 observation/lineage；发布前可单独执行 `py -3 scripts/release_audit.py --database data/dashboard.db --strict`。

## 生产启动

本机生产运行使用 Waitress。先备份 SQLite 数据库并配置 Basic Auth，再启动服务：

```powershell
Copy-Item data/dashboard.db data/dashboard.db.bak
$env:DASHBOARD_USERNAME = 'operator'
$env:DASHBOARD_PASSWORD = 'replace-with-a-long-random-password'
& .\scripts\start_production.ps1 -BackupBeforeStart
```

启动前可运行只读预检，启动后检查健康状态：

```powershell
py -3 scripts/production_preflight.py
Invoke-WebRequest http://127.0.0.1:5000/healthz | Select-Object -ExpandProperty Content
```

只有健康检查返回 `"ok": true` 且 `"database": "ok"` 才可开放访问。

## 数据导入与定时扫描

数据中心支持多文件预览、字段映射、质量校验和事务确认。受控目录扫描与手动导入共用同一套 `ImportService`、质量门禁和批次审计协议。

Web 版填写的是运行 Flask 服务主机上的本地目录，浏览器不会把用户电脑路径授权给服务器；目录仍必须位于 `IMPORT_SCAN_ALLOWED_ROOTS` 允许根目录内。桌面版在 `TMALL_DESKTOP_MODE=1` 时显示原生文件夹选择器。需要多人分权时可额外设置 `IMPORT_SCAN_VIEW_USERS` 和 `IMPORT_SCAN_MANAGE_USERS`，它们只控制扫描 API 能力，不会写入普通系统设置。


```powershell
py -3 scripts/run_import_scanner.py --once
```

扫描器只处理允许目录的直接子文件；文件连续两次保持稳定后才进入导入。质量不通过的文件会保留为阻塞或失败记录，并支持显式重试。

## 验证状态

发布前建议依次运行：

```powershell
py -3 -m unittest discover -s tests -v
Get-ChildItem frontend/ui_demo/assets -Filter *.js | ForEach-Object { node --check $_.FullName }
node scripts/validate_ui_demos.cjs
py -3 scripts/production_preflight.py
py -3 scripts/production_preflight.py --recovery-source data/dashboard.db
py -3 scripts/release_audit.py --database data/dashboard.db --strict
```

浏览器门禁覆盖七个 API 驱动主页面、响应式视口、图表像素输出、错误状态和横向溢出；发布审计会检查脏工作树、未核验批次、数据库完整性和来源血缘。

## 已知限制

> **生产数据血缘：** 已根据可核验的原始生意参谋工作簿补齐此前 **277 条**历史日事实的 observation/lineage；回填脚本具备来源哈希校验、冲突拒绝和幂等保护。后续生产库变更仍须通过 `py -3 scripts/release_audit.py --database data/dashboard.db --strict` 审计。

- 推广计划、单元、创意、地域和内容归因只有在对应粒度事实导入后才开放，下钻不会构造不存在的数据。
- 生命周期判断需要至少 60 个连续有效日；季节性判断需要 12 个完整自然月，数据不足时明确显示“数据积累中”。
- 周/月事实及部分依赖旧表的工具接口仍限定单店结构；非 `default` 店铺请求会返回 `UNSUPPORTED_SCOPE`，避免静默串店。
- `main` 与当前发布分支存在独立提交历史，后续合并应通过显式 Pull Request 审查，不直接覆盖默认分支。

## 发布

当前版本、更新说明与桌面端安装包见 [GitHub Release v1.0.2](https://github.com/owen891/tmall-dashboard/releases/tag/v1.0.2)。
