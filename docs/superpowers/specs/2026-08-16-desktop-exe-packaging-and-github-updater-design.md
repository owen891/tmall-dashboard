# 天猫数据仪表盘桌面版与在线升级设计

## 目标

把现有天猫数据仪表盘交付为 Windows 桌面应用。用户安装后可以双击启动，不需要安装 Python、Node.js、浏览器插件或 WebView2，也不需要手动启动本地服务。

桌面版必须完整保留现有 Flask、SQLite、API、前端页面、数据导入、审计、备份和撤销能力。桌面壳参考 Hermes Studio，采用 Electron、electron-builder、NSIS 和 electron-updater；业务层不迁移到 Electron。

## 非目标

- 不把 Flask API 或数据库逻辑重写为 Node.js。
- 不重写现有业务页面。
- 不在应用完全退出后隐式运行定时导入；如需后台扫描，通过单独的 Windows 计划任务实现。
- 不从 GitHub 下载源码压缩包并覆盖本地程序。
- 首版不做 macOS、Linux 或 Windows ARM64 安装包。

## 中文与 Windows 集成

产品名称统一为“天猫数据仪表盘”。安装向导、桌面快捷方式、开始菜单、卸载项、托盘菜单、启动提示、升级提示、错误提示和恢复提示全部使用简体中文。

现有业务页面继续作为业务术语的唯一来源，桌面壳不复制业务文案。首版目标系统为 Windows 10/11 x64。

## 架构

桌面版使用两层进程：

```text
天猫数据仪表盘.exe
  -> Electron 主进程
  -> 启动 backend/TmallDashboardServer.exe
  -> Waitress 监听 127.0.0.1 随机端口
  -> Electron BrowserWindow 加载本地 Flask 页面
```

Electron 主进程负责单实例锁、窗口、托盘、本地服务生命周期、启动健康检查和在线升级。Flask 后端通过 PyInstaller `--onedir --windowed` 打包为独立运行目录，再作为 electron-builder 的 `extraResources` 放入安装包。

Electron 自带 Chromium，因此初次安装完全离线，也不依赖 WebView2。代价是安装包体积预计增加约 150 MB；这与 Hermes Studio 的桌面路线一致。

## 进程生命周期

Electron 先分配一个仅绑定 `127.0.0.1` 的可用端口，再以参数和环境变量启动 Flask 后端。主进程轮询 `/healthz`，成功后才显示业务窗口。

关闭主窗口默认隐藏到托盘；选择“退出天猫数据仪表盘”时才停止后端并退出。升级安装前必须先优雅停止 Waitress；超时后再终止本应用启动的后端进程。第二个应用实例只激活已有窗口，不再启动第二套服务。

## 资源与用户数据

只读资源由 PyInstaller 资源辅助函数解析，所有可写状态均放到用户目录：

- `%APPDATA%\\TmallDashboard\\data\\dashboard.db`
- `%APPDATA%\\TmallDashboard\\data\\uploads\\`
- `%APPDATA%\\TmallDashboard\\data\\import-inbox\\`
- `%APPDATA%\\TmallDashboard\\data\\backups\\`
- `%LOCALAPPDATA%\\TmallDashboard\\logs\\`

首次启动创建目录并执行现有数据库初始化和幂等迁移。安装和升级均不得覆盖用户数据库。仓库中的现有数据库只能通过明确的一次性迁移或现有导入流程进入桌面数据目录。

## GitHub Releases 在线升级

公开仓库 `owen891/tmall-dashboard` 作为首版更新源。electron-builder 生成并发布：

```text
TmallDashboard-Setup-<version>-x64.exe
TmallDashboard-Setup-<version>-x64.exe.blockmap
latest.yml
```

electron-updater 使用 GitHub Releases 的 `releases/latest/download` 通用源，不调用容易触发限流的 GitHub API。`latest.yml` 中的 SHA-512 由 electron-builder 生成并由 electron-updater 校验，不再维护自定义 `latest.json`。

启动后进行一次非阻塞检查；设置页和托盘提供“检查更新”。发现新版本时先询问是否下载，不强制升级。下载完成后提供“立即重启安装”和“稍后安装”，退出时可自动安装已下载版本。

升级前停止本地服务和本应用的其他实例。Windows 出现安装文件锁或更新缓存损坏时，清理本应用的 pending 更新目录并允许重新下载。升级不修改用户数据库；数据库升级仍由应用启动时的迁移负责。

GitHub 在部分国内网络环境可能较慢或不可达。首次安装不受影响；在线升级失败只显示中文提示，不阻止本地使用。后续可以增加国内静态下载镜像，并保留 GitHub 作为回退源。

## 版本管理

桌面应用、Flask 后端和前端资源使用同一个语义版本号。版本号存放在一个机器可读文件中，构建脚本同步给 Python 包和 Electron `package.json`。

设置页显示当前版本、更新状态和最近一次检查结果。首版不实现独立的 Python Runtime 版本切换，因为后端已经随桌面安装包整体发布；这比照搬 Hermes Studio 的 Node/Python/Git Runtime 管理更适合当前项目。

## 后台任务边界

应用运行或驻留托盘时，现有自动扫描和本地服务能力保持完整。用户明确退出应用后，本地服务和扫描同时停止。

如果需要退出桌面应用后仍定时扫描，提供可选的 Windows 计划任务注册脚本，调用同一套打包后端和同一用户数据目录。安装器默认不静默创建后台任务。

## 错误处理

- 后端端口选择和启动具有有界重试，失败时显示中文诊断信息并写日志。
- `/healthz` 等待超时后停止后端，不显示空白窗口。
- 数据库损坏时保留原文件并报告错误，不自动删除或重建覆盖。
- 更新检查、下载和安装错误不阻止现有版本继续运行。
- 仅执行 electron-updater 根据 `latest.yml` 选择并完成 SHA-512 校验的安装包。
- 未配置代码签名证书时允许生成测试安装包，但发布说明必须明确 Windows SmartScreen 可能提示未知发布者。

## 验证计划

- Python 单元测试覆盖资源路径、用户数据路径和桌面运行配置。
- 后端进程冒烟测试使用随机回环端口验证 `/healthz` 和 `/`。
- Electron 单元测试覆盖端口参数、进程退出、单实例、更新源和中文升级文案。
- electron-builder 配置测试覆盖 NSIS x64、`extraResources`、产品名和更新产物。
- 安装包冒烟测试验证无 Python/Node.js 环境时可以启动、写入 SQLite、关闭和重新启动。
- 更新测试覆盖发现版本、用户拒绝下载、下载完成、退出安装、缓存清理和检查失败继续使用。
- 现有 Python、JavaScript、发布审计和浏览器冒烟测试继续作为门禁。

## 发布流程

1. 更新唯一版本文件和中文发布说明。
2. 构建 PyInstaller Flask 后端。
3. 构建 Electron 主进程并由 electron-builder 生成 NSIS 安装包、blockmap 和 `latest.yml`。
4. 运行后端、桌面壳、安装、数据库写入和更新冒烟测试。
5. GitHub Actions 把三个 Windows x64 产物上传到对应 GitHub Release。
6. 所有产物上传成功后再把该 Release 标记为 latest。

