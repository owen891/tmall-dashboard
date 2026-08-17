# 工具箱文件夹扫描设计

## 目标

将数据工具箱中的“定时导入任务”替换为“文件夹扫描任务”。用户选择本机文件夹后，可配置文件规则、报表来源、执行计划和启用状态；任务统一写入现有 `/api/import-scans`，不再使用已下线的 `/api/manage/schedules`。

## 交互

- 工具卡和面板统一命名为“文件夹扫描任务”。
- 表单包含任务名称、文件夹路径、文件匹配规则、报表来源、执行频率、执行时间和启用开关。
- Electron 桌面端提供“选择文件夹”按钮，通过系统目录选择器回填路径；浏览器模式仍可手动输入绝对路径。
- 任务列表显示任务名称、文件夹、计划、状态和最近运行时间，并提供立即扫描、启停和刷新操作。
- 加载、空状态、保存失败和扫描失败都显示中文状态，不向界面注入服务器 HTML。

## 架构

- `frontend/ui_demo/assets/shell.js` 负责工具箱表单、列表和 `/api/import-scans` 交互。
- `desktop/src/preload.ts` 只暴露受限的 `selectScanFolder()` 能力。
- `desktop/src/main.ts` 使用 Electron `dialog.showOpenDialog` 打开系统目录选择器。
- 浏览器模式继续受 `IMPORT_SCAN_ALLOWED_ROOTS` 限制；桌面模式允许用户选择已存在的本地绝对目录，仍拒绝 UNC、相对路径、`..` 和符号链接。

## 验证

- Python 前端契约测试确认工具箱不再引用旧调度接口，并完整使用扫描任务字段和接口。
- Python 服务测试确认桌面模式目录校验与浏览器白名单边界。
- Electron 测试确认目录选择 IPC、取消语义及 preload 暴露。
- 运行 Python 目标测试、Electron 测试和 TypeScript 构建。
