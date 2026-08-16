# 天猫数据仪表盘桌面 EXE 与 GitHub 在线升级实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 交付 Windows 10/11 x64 中文桌面安装包，双击即可运行完整 Flask 仪表盘，并通过公开 GitHub Releases 检查、下载和安装新版本。

**Architecture:** Electron 负责窗口、托盘、单实例、本地进程和 electron-updater；PyInstaller 把现有 Flask/Waitress 应用打成随安装包分发的后端目录。Electron 启动后端并加载随机回环端口，所有数据库和导入文件写入用户目录，升级只替换程序文件。

**Tech Stack:** Python 3.14、Flask、Waitress、PyInstaller、Electron 42、TypeScript、electron-builder 26、electron-updater 6、NSIS、GitHub Actions、unittest、Vitest。

---

## 文件结构

- `desktop_runtime.py`：PyInstaller 资源目录、用户数据目录和桌面后端配置。
- `desktop_backend.py`：Waitress 桌面后端入口，只监听随机回环端口。
- `packaging/tmall_dashboard_backend.spec`：PyInstaller 后端资源和模块清单。
- `desktop/src/main.ts`：Electron 窗口、托盘、单实例和后端进程生命周期。
- `desktop/src/updater.ts`：GitHub Releases 更新检查、下载和安装。
- `desktop/src/i18n.ts`：桌面壳中文文案。
- `desktop/src/preload.ts`：向设置页暴露最小版本/更新桥接接口。
- `frontend/ui_demo/assets/desktop-integration.js`：设置页桌面版本状态适配器。
- `scripts/build_desktop.ps1`：本机完整构建入口。
- `.github/workflows/desktop-release.yml`：Windows Release 产物构建和上传。

### Task 1：桌面资源与用户数据路径

**Files:**
- Create: `desktop_runtime.py`
- Create: `tests/test_desktop_runtime.py`
- Modify: `config.py`
- Modify: `app.py`

- [ ] **Step 1: 写失败测试**

```python
class DesktopRuntimeTests(unittest.TestCase):
    def test_desktop_paths_use_user_profile_and_never_bundle_directory(self):
        with tempfile.TemporaryDirectory() as appdata, tempfile.TemporaryDirectory() as local:
            paths = desktop_data_paths({'APPDATA': appdata, 'LOCALAPPDATA': local})
            self.assertEqual(paths.database, os.path.join(appdata, 'TmallDashboard', 'data', 'dashboard.db'))
            self.assertEqual(paths.logs, os.path.join(local, 'TmallDashboard', 'logs'))

    def test_desktop_environment_points_flask_and_sqlalchemy_to_same_database(self):
        paths = DesktopPaths('C:/data/dashboard.db', 'C:/data/uploads', 'C:/data/import-inbox', 'C:/logs')
        environment = desktop_environment(paths)
        self.assertEqual(environment['TMALL_DB_PATH'], 'C:/data/dashboard.db')
        self.assertEqual(environment['DATABASE_URL'], 'sqlite:///C:/data/dashboard.db')
        self.assertEqual(environment['TMALL_UPLOAD_FOLDER'], 'C:/data/uploads')
```

- [ ] **Step 2: 运行测试确认 RED**

Run: `py -3 -m unittest tests.test_desktop_runtime -v`

Expected: `ModuleNotFoundError: No module named 'desktop_runtime'`。

- [ ] **Step 3: 实现路径模块并接入 Flask**

```python
@dataclass(frozen=True)
class DesktopPaths:
    database: str
    uploads: str
    import_inbox: str
    logs: str

def resource_root() -> str:
    return os.path.abspath(getattr(sys, '_MEIPASS', os.path.dirname(__file__)))

def desktop_data_paths(environment=None) -> DesktopPaths:
    env = environment or os.environ
    roaming = env.get('APPDATA') or os.path.join(Path.home(), 'AppData', 'Roaming')
    local = env.get('LOCALAPPDATA') or os.path.join(Path.home(), 'AppData', 'Local')
    data = os.path.join(roaming, 'TmallDashboard', 'data')
    return DesktopPaths(
        database=os.path.join(data, 'dashboard.db'),
        uploads=os.path.join(data, 'uploads'),
        import_inbox=os.path.join(data, 'import-inbox'),
        logs=os.path.join(local, 'TmallDashboard', 'logs'),
    )
```

`config.py` 从 `TMALL_UPLOAD_FOLDER` 和 `IMPORT_SCAN_ALLOWED_ROOTS` 读取桌面目录；`app.py` 的模板、静态资源和 `frontend/ui_demo` 目录改用 `resource_root()`。

- [ ] **Step 4: 运行路径与应用工厂测试确认 GREEN**

Run: `py -3 -m unittest tests.test_desktop_runtime tests.test_app_factory -v`

Expected: 全部通过，且临时用户目录外无新增数据库。

- [ ] **Step 5: 提交**

```powershell
git add desktop_runtime.py config.py app.py tests/test_desktop_runtime.py
git commit -m "feat: add desktop resource and data paths"
```

### Task 2：独立 Flask/Waitress 后端进程

**Files:**
- Create: `desktop_backend.py`
- Create: `tests/test_desktop_backend.py`
- Modify: `requirements.txt`

- [ ] **Step 1: 写失败测试**

```python
class DesktopBackendTests(unittest.TestCase):
    def test_parser_requires_loopback_port_and_parent_pid(self):
        args = parse_args(['--port', '49152', '--parent-pid', '321'])
        self.assertEqual(args.host, '127.0.0.1')
        self.assertEqual(args.port, 49152)
        self.assertEqual(args.parent_pid, 321)

    def test_build_config_uses_desktop_user_paths(self):
        config = build_app_config(DesktopPaths('D:/db/dashboard.db', 'D:/uploads', 'D:/inbox', 'D:/logs'))
        self.assertEqual(config['DATABASE_PATH'], 'D:/db/dashboard.db')
        self.assertEqual(config['UPLOAD_FOLDER'], 'D:/uploads')
```

- [ ] **Step 2: 运行测试确认 RED**

Run: `py -3 -m unittest tests.test_desktop_backend -v`

Expected: `ModuleNotFoundError: No module named 'desktop_backend'`。

- [ ] **Step 3: 实现桌面后端入口**

```python
def main(argv=None) -> int:
    args = parse_args(argv)
    paths = desktop_data_paths()
    ensure_desktop_directories(paths)
    os.environ.update(desktop_environment(paths))
    from app import create_app
    server = create_server(create_app(build_app_config(paths)), host='127.0.0.1', port=args.port)
    monitor_parent(args.parent_pid, server.close)
    server.run()
    return 0
```

参数端口限制为 `1024..65535`，host 不对外开放。父进程消失后调用 `server.close()`，避免 Electron 异常退出留下后台服务。

- [ ] **Step 4: 运行真实进程冒烟测试**

Run: `py -3 -m unittest tests.test_desktop_backend -v`

Expected: 测试启动子进程后，`/healthz` 返回 200、`/` 返回 HTML，结束父测试时子进程退出。

- [ ] **Step 5: 提交**

```powershell
git add desktop_backend.py desktop_runtime.py tests/test_desktop_backend.py requirements.txt
git commit -m "feat: add standalone desktop backend"
```

### Task 3：PyInstaller 后端构建

**Files:**
- Create: `requirements-desktop.txt`
- Create: `packaging/tmall_dashboard_backend.spec`
- Create: `scripts/build_backend.ps1`
- Create: `tests/test_desktop_packaging_contract.py`
- Modify: `.gitignore`

- [ ] **Step 1: 写失败契约测试**

```python
def test_pyinstaller_spec_bundles_required_runtime_assets(self):
    spec = Path('packaging/tmall_dashboard_backend.spec').read_text(encoding='utf-8')
    for asset in ('frontend/ui_demo', 'templates', 'static', 'config.yaml'):
        self.assertIn(asset, spec)
    self.assertIn("name='TmallDashboardServer'", spec)
```

- [ ] **Step 2: 运行测试确认 RED**

Run: `py -3 -m unittest tests.test_desktop_packaging_contract -v`

Expected: `FileNotFoundError` 指向缺失的 spec。

- [ ] **Step 3: 添加后端 spec 和构建脚本**

`requirements-desktop.txt` 固定：

```text
-r requirements.txt
pyinstaller==6.22.1
```

spec 使用 `Analysis(['desktop_backend.py'])`，将四类资源加入 `datas`，输出 `TmallDashboardServer` onedir 目录。`scripts/build_backend.ps1` 使用当前 Python 创建 `build/desktop/backend`，失败时返回非零退出码。

- [ ] **Step 4: 构建并执行打包后端冒烟**

Run: `powershell -ExecutionPolicy Bypass -File scripts/build_backend.ps1`

Expected: `build/desktop/backend/TmallDashboardServer.exe` 存在；以随机端口启动后 `/healthz` 返回 200。

- [ ] **Step 5: 提交**

```powershell
git add requirements-desktop.txt packaging/tmall_dashboard_backend.spec scripts/build_backend.ps1 tests/test_desktop_packaging_contract.py .gitignore
git commit -m "build: package Flask backend with PyInstaller"
```

### Task 4：Electron 窗口、托盘与后端生命周期

**Files:**
- Create: `desktop/package.json`
- Create: `desktop/tsconfig.json`
- Create: `desktop/electron-builder.yml`
- Create: `desktop/src/main.ts`
- Create: `desktop/src/backend.ts`
- Create: `desktop/src/i18n.ts`
- Create: `desktop/src/preload.ts`
- Create: `desktop/tests/backend.test.ts`
- Create: `desktop/tests/main-contract.test.ts`

- [ ] **Step 1: 写失败 Vitest 测试**

```ts
it('spawns only the packaged loopback backend', () => {
  const launch = backendLaunchOptions('C:\\Program Files\\TmallDashboard\\resources', 49152, 123)
  expect(launch.command).toMatch(/TmallDashboardServer\.exe$/)
  expect(launch.args).toEqual(['--port', '49152', '--parent-pid', '123'])
  expect(launch.env.TMALL_DESKTOP_MODE).toBe('1')
})
```

契约测试同时断言 `contextIsolation: true`、`sandbox: true`、`nodeIntegration: false`、`requestSingleInstanceLock()` 和 `127.0.0.1`。

- [ ] **Step 2: 运行测试确认 RED**

Run: `npm ci --prefix desktop && npm test --prefix desktop`

Expected: TypeScript 模块缺失导致失败。

- [ ] **Step 3: 实现 Electron 主进程**

`backend.ts` 负责选择端口、spawn、健康检查、日志转发和退出；`main.ts` 负责：

```ts
const gotLock = app.requestSingleInstanceLock()
if (!gotLock) app.quit()

app.whenReady().then(async () => {
  const backend = await startBackend(process.resourcesPath)
  createMainWindow(backend.url)
  createTray()
})
```

窗口关闭时隐藏到托盘；托盘提供“显示主窗口”“检查更新”“开机启动”“退出天猫数据仪表盘”。明确退出时先停止后端，再 `app.exit(0)`。

- [ ] **Step 4: 运行 Electron 单元测试和 TypeScript 构建**

Run: `npm test --prefix desktop && npm run build --prefix desktop`

Expected: Vitest 全绿，`desktop/dist/main.js` 和 `desktop/dist/preload.js` 存在。

- [ ] **Step 5: 提交**

```powershell
git add desktop
git commit -m "feat: add Electron desktop shell"
```

### Task 5：Hermes 风格 GitHub 自动升级

**Files:**
- Create: `desktop/src/updater.ts`
- Create: `desktop/src/updater-helpers.ts`
- Create: `desktop/tests/updater.test.ts`
- Modify: `desktop/src/main.ts`
- Modify: `desktop/src/i18n.ts`
- Modify: `desktop/electron-builder.yml`

- [ ] **Step 1: 写失败升级器测试**

```ts
it('checks once on startup without forcing download', () => {
  expect(source).toContain('autoUpdater.autoDownload = false')
  expect(source).toContain('autoUpdater.autoInstallOnAppQuit = true')
  expect(source).toContain("https://github.com/owen891/tmall-dashboard/releases/latest/download")
  expect(source).not.toContain('setInterval(')
})

it('stops the backend before quitAndInstall', () => {
  expect(source.indexOf('await beforeQuitAndInstall()')).toBeLessThan(source.indexOf('autoUpdater.quitAndInstall()'))
})
```

- [ ] **Step 2: 运行测试确认 RED**

Run: `npm test --prefix desktop -- updater.test.ts`

Expected: updater 文件缺失导致失败。

- [ ] **Step 3: 实现更新流程**

```ts
autoUpdater.setFeedURL({
  provider: 'generic',
  url: 'https://github.com/owen891/tmall-dashboard/releases/latest/download',
})
autoUpdater.autoDownload = false
autoUpdater.autoInstallOnAppQuit = true
```

发现新版本时使用中文对话框询问“下载 / 稍后”；下载完成询问“立即重启安装 / 稍后安装”。Windows 文件锁错误会清理 `%LOCALAPPDATA%` 和 `%APPDATA%` 下本应用 updater 的 `pending` 目录后允许重试。

- [ ] **Step 4: 验证升级器测试与 builder 配置**

Run: `npm test --prefix desktop && npm run build --prefix desktop`

Expected: 升级器测试全绿，builder 配置包含 NSIS x64、`extraResources` 后端目录和 `latest.yml` 产物。

- [ ] **Step 5: 提交**

```powershell
git add desktop/src desktop/tests desktop/electron-builder.yml
git commit -m "feat: add GitHub desktop auto updates"
```

### Task 6：设置页版本管理入口

**Files:**
- Create: `frontend/ui_demo/assets/desktop-integration.js`
- Modify: `frontend/ui_demo/pages/settings.html`
- Modify: `frontend/ui_demo/assets/components.css`
- Modify: `desktop/src/preload.ts`
- Modify: `desktop/src/main.ts`
- Modify: `tests/test_frontend_prd_contract.py`

- [ ] **Step 1: 写失败页面契约测试**

```python
def test_settings_exposes_desktop_version_management(self):
    html = self.read('frontend/ui_demo/pages/settings.html')
    self.assertIn('data-desktop-version', html)
    self.assertIn('data-desktop-check-update', html)
    self.assertIn('desktop-integration.js', html)
```

- [ ] **Step 2: 运行测试确认 RED**

Run: `py -3 -m unittest tests.test_frontend_prd_contract -v`

Expected: 缺少桌面版本管理标记而失败。

- [ ] **Step 3: 添加中文版本管理面板与安全 preload API**

```html
<section class="plain-panel panel" id="settings-desktop" hidden data-desktop-settings>
  <div class="panel__header">
    <div><h3 class="panel__title">桌面应用</h3><p class="panel__hint">当前版本 <span data-desktop-version>--</span></p></div>
    <button class="button" type="button" data-desktop-check-update>检查更新</button>
  </div>
  <p class="panel__hint" data-desktop-update-status role="status" aria-live="polite"></p>
</section>
```

preload 只暴露 `getVersion()` 和 `checkForUpdates()`；普通浏览器访问时面板保持隐藏，现有 Web 运行方式不受影响。

- [ ] **Step 4: 运行前端契约和桌面桥接测试**

Run: `py -3 -m unittest tests.test_frontend_prd_contract -v; npm test --prefix desktop`

Expected: 全部通过。

- [ ] **Step 5: 提交**

```powershell
git add frontend/ui_demo/pages/settings.html frontend/ui_demo/assets/desktop-integration.js frontend/ui_demo/assets/components.css desktop/src/preload.ts desktop/src/main.ts tests/test_frontend_prd_contract.py
git commit -m "feat: add desktop version management settings"
```

### Task 7：一键构建与 GitHub Release 工作流

**Files:**
- Create: `scripts/sync_desktop_version.py`
- Create: `scripts/build_desktop.ps1`
- Create: `.github/workflows/desktop-release.yml`
- Modify: `README.md`
- Modify: `.gitignore`
- Modify: `tests/test_release_gates.py`

- [ ] **Step 1: 写失败发布契约测试**

```python
def test_desktop_release_uses_version_file_and_uploads_updater_assets(self):
    workflow = pathlib.Path(PROJECT_ROOT, '.github', 'workflows', 'desktop-release.yml').read_text(encoding='utf-8')
    self.assertIn('scripts/build_desktop.ps1', workflow)
    self.assertIn('latest.yml', workflow)
    self.assertIn('*.exe.blockmap', workflow)
    self.assertIn('softprops/action-gh-release', workflow)
```

- [ ] **Step 2: 运行测试确认 RED**

Run: `py -3 -m unittest tests.test_release_gates -v`

Expected: 缺少 desktop release workflow 而失败。

- [ ] **Step 3: 实现版本同步和完整构建**

`sync_desktop_version.py` 读取根目录 `VERSION`，验证 `MAJOR.MINOR.PATCH`，更新 `desktop/package.json`。`build_desktop.ps1` 顺序执行 Python 测试、后端打包、桌面测试、桌面构建和 electron-builder NSIS 打包。

GitHub Actions 使用 Windows runner、Python 3.14 和 Node 24，构建完成后上传：

```text
desktop/release/TmallDashboard-Setup-*-x64.exe
desktop/release/TmallDashboard-Setup-*-x64.exe.blockmap
desktop/release/latest.yml
```

- [ ] **Step 4: 本地执行完整构建**

Run: `powershell -ExecutionPolicy Bypass -File scripts/build_desktop.ps1`

Expected: `desktop/release` 下生成 exe、blockmap 和 `latest.yml`；命令退出码 0。

- [ ] **Step 5: 提交**

```powershell
git add scripts/sync_desktop_version.py scripts/build_desktop.ps1 .github/workflows/desktop-release.yml README.md .gitignore tests/test_release_gates.py
git commit -m "build: add desktop release pipeline"
```

### Task 8：安装包端到端验收

**Files:**
- Create: `scripts/desktop_smoke.ps1`
- Modify: `docs/RELEASE_STATUS.md`

- [ ] **Step 1: 编写安装包冒烟脚本**

脚本在临时目录静默安装，启动桌面 exe，轮询后端日志获取端口，验证 `/healthz`、总览页和设置页，写入临时 SQLite，退出应用并确认后端进程消失，最后执行卸载。脚本只操作自己创建的临时安装目录和临时 APPDATA。

- [ ] **Step 2: 运行目标测试集**

Run: `py -3 -m unittest tests.test_desktop_runtime tests.test_desktop_backend tests.test_desktop_packaging_contract tests.test_frontend_prd_contract tests.test_release_gates -v`

Expected: 全部通过。

- [ ] **Step 3: 运行桌面测试和生产构建**

Run: `npm test --prefix desktop; npm run build --prefix desktop; powershell -ExecutionPolicy Bypass -File scripts/build_desktop.ps1`

Expected: 所有命令退出码 0，安装器和更新元数据存在。

- [ ] **Step 4: 运行安装包冒烟**

Run: `powershell -ExecutionPolicy Bypass -File scripts/desktop_smoke.ps1`

Expected: 输出 `DESKTOP_SMOKE_OK`，卸载后临时安装目录不存在，用户数据库测试副本仍存在。

- [ ] **Step 5: 运行现有回归门禁**

Run: `py -3 -m unittest discover -s tests -v`

Expected: 现有回归与新增桌面测试全部通过。

- [ ] **Step 6: 更新发布状态并提交**

```powershell
git add scripts/desktop_smoke.ps1 docs/RELEASE_STATUS.md
git commit -m "test: verify desktop installer lifecycle"
```
