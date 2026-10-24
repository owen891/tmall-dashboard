"""Build a clean public/manual-import tree from the private source tree.

The exporter is deliberately file-oriented: it never edits the source tree,
never follows symlinks, and only copies paths named by release/public-manifest.yaml.
The generated tree is a release artifact, not a second development checkout.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
from pathlib import Path, PurePosixPath


PROJECT_ROOT = Path(__file__).resolve().parents[1]
MANIFEST_PATH = PROJECT_ROOT / "release" / "public-manifest.yaml"
PUBLIC_METADATA_NAME = "PUBLIC-EDITION.json"

PUBLIC_CONFIG = """app:\n  host: \"127.0.0.1\"\n  port: 5000\n  debug: false\n\ndata:\n  db_path: \"data/dashboard.db\"\n  watch_folder: \"~/Downloads/tmall_data/\"\n  backup_folder: \"data/backups/\"\n  backup_on_import: true\n  max_backups: 3\n  max_backup_total_gb: 20\n\nthresholds:\n  refund_warning: 0.20\n  refund_consecutive_weeks: 2\n  anomaly_decline: 0.20\n  ppc_warning: null\n  health_warning: 40\n\nrefresh:\n  auto_refresh_interval: 300\n"""

PUBLIC_REQUIREMENTS = """flask==3.1.0\nwaitress==3.0.2\npandas==3.0.5\nopenpyxl==3.1.5\nxlrd==2.0.1\npyyaml==6.0.3\npython-dateutil==2.9.0.post0\n"""

PUBLIC_REQUIREMENTS_DESKTOP = """-r requirements.txt\npyinstaller==6.22.1\n"""

PUBLIC_BUILD_BACKEND = '''"""Build the public desktop backend with the public PyInstaller spec."""

from __future__ import annotations

import platform
import subprocess
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SPEC_PATH = PROJECT_ROOT / "packaging" / "tmall_dashboard_backend.spec"
DIST_PATH = PROJECT_ROOT / "build" / "desktop"
WORK_PATH = PROJECT_ROOT / "build" / "pyinstaller"


def main() -> int:
    if not SPEC_PATH.is_file():
        raise SystemExit(f"Public backend spec not found: {SPEC_PATH}")
    command = [
        sys.executable, "-m", "PyInstaller", "--clean", "--noconfirm",
        f"--distpath={DIST_PATH}", f"--workpath={WORK_PATH}", str(SPEC_PATH),
    ]
    subprocess.run(command, cwd=PROJECT_ROOT, check=True)
    executable_name = "TmallDashboardServer.exe" if platform.system() == "Windows" else "TmallDashboardServer"
    executable = DIST_PATH / "backend" / executable_name
    if not executable.is_file():
        raise SystemExit(f"Packaged backend executable was not created: {executable}")
    if platform.system() != "Windows":
        executable.chmod(executable.stat().st_mode | 0o111)
    print(executable)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
'''

PUBLIC_BUILD_DESKTOP = '''[CmdletBinding()]
param([switch]$SkipInstall)

$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$desktopRoot = Join-Path $projectRoot 'desktop'

Push-Location $projectRoot
try {
    if (-not $SkipInstall) {
        & py -3 -m pip install -r requirements-desktop.txt
        if ($LASTEXITCODE -ne 0) { throw "Python dependency installation failed with exit code $LASTEXITCODE." }
        & npm ci --prefix desktop
        if ($LASTEXITCODE -ne 0) { throw "Desktop dependency installation failed with exit code $LASTEXITCODE." }
    }

    & py -3 scripts/build_backend.py
    if ($LASTEXITCODE -ne 0) { throw "Public backend packaging failed with exit code $LASTEXITCODE." }
    & npm run build --prefix desktop
    if ($LASTEXITCODE -ne 0) { throw "Desktop TypeScript build failed with exit code $LASTEXITCODE." }

    $env:CSC_IDENTITY_AUTO_DISCOVERY = 'false'
    & npm run dist --prefix desktop
    if ($LASTEXITCODE -ne 0) { throw "Public NSIS packaging failed with exit code $LASTEXITCODE." }
    Write-Output "PUBLIC_DESKTOP_BUILD_OK"
    Write-Output (Join-Path $desktopRoot 'release')
}
finally {
    Pop-Location
}
'''

PUBLIC_ELECTRON_BUILDER = '''appId: org.tmalldashboard.public
productName: Tmall Dashboard Public Edition

directories:
  output: release

files:
  - dist/**/*
  - package.json

extraResources:
  - from: ../build/desktop/backend
    to: backend
    filter:
      - "**/*"

win:
  target:
    - target: nsis
      arch: [x64]
  artifactName: "TmallDashboard-Public-Setup-${version}-${arch}.${ext}"

nsis:
  oneClick: false
  allowToChangeInstallationDirectory: true
  perMachine: false
  createDesktopShortcut: true
  createStartMenuShortcut: true
'''

PUBLIC_DESKTOP_TSCONFIG = '''{
  "compilerOptions": {
    "target": "ES2022",
    "module": "CommonJS",
    "moduleResolution": "Node",
    "rootDir": "src",
    "outDir": "dist",
    "strict": true,
    "esModuleInterop": true,
    "skipLibCheck": true,
    "types": ["node"]
  },
  "include": ["src/**/*.ts"]
}
'''

PUBLIC_UPDATER = '''export type UpdateStatus =
  | { state: "development" }
  | { state: "error"; message: string }

interface UpdaterOptions {
  beforeQuitAndInstall: () => Promise<void>
  getWindow: () => Electron.BrowserWindow | null
  onStatus: (status: UpdateStatus) => void
}

export interface DesktopUpdater {
  checkForUpdates: (manual?: boolean) => Promise<UpdateStatus>
}

export function createDesktopUpdater(options: UpdaterOptions): DesktopUpdater {
  void options
  return { checkForUpdates: async () => ({ state: "development" }) }
}
'''

PUBLIC_DESKTOP_INTEGRATION = '''(function () {
  const panel = document.querySelector('[data-sidebar-meta]') || document.querySelector('[data-desktop-settings]')
  if (!panel) return
  const desktop = window.tmallDesktop
  const sidebar = panel.matches('[data-sidebar-meta]')
  const version = panel.querySelector(sidebar ? '[data-sidebar-version]' : '[data-desktop-version]')
  const button = sidebar ? document.querySelector('[data-sidebar-check-update]') : panel.querySelector('[data-desktop-check-update]')
  const status = panel.querySelector(sidebar ? '[data-sidebar-update-status]' : '[data-desktop-update-status]')
  const setStatus = text => {
    if (status) status.textContent = text
  }
  panel.hidden = false
  if (!desktop?.isDesktop) {
    if (button) button.hidden = true
    if (window.TMALL_WEB_VERSION && version) version.textContent = window.TMALL_WEB_VERSION
    return
  }
  if (button) button.hidden = false
  desktop.getVersion().then(value => { if (version) version.textContent = value }).catch(() => {})
  button?.addEventListener('click', async () => {
    button.disabled = true
    setStatus('公开版不检查在线更新')
    try { await desktop.checkForUpdates() } finally { button.disabled = false }
  })
  setStatus('公开版不检查在线更新')
})()
'''

PUBLIC_VERSION_CHECK = '''(function () {
  const version = document.querySelector('[data-sidebar-version]') || document.querySelector('[data-desktop-version]')
  if (!version || window.tmallDesktop?.isDesktop) return
  fetch(new URL('/api/version?client=web', window.location.origin), { cache: 'no-store' })
    .then(response => response.ok ? response.json() : null)
    .then(payload => { if (payload?.data?.version) version.textContent = payload.data.version })
    .catch(() => {})
})()
'''

PUBLIC_VERSION_JS = '''window.TMALL_WEB_VERSION = "2.0.2";
window.TMALL_PROJECT = Object.freeze({
  edition: "public-manual",
  repository: null,
  releases: null,
  latestRelease: null,
  latestReleaseApi: null,
});
'''

PUBLIC_README = """# Tmall Dashboard Public Edition\n\nThis tree is the manually-imported/open-source edition of the dashboard.\nIt keeps file upload, template mapping, preview, batch publication, local\nfolder scanning, analysis and rollback. Platform browser collectors, login\ncredentials, browser profiles and private production data are not included.\n\nStart locally with a fresh SQLite database and import an exported report file:\n\n```text\npython -m pip install -r requirements.txt\npython -c \"from app import create_app; create_app()\"\n```\n\nThe public tree is generated from the private source with `export_public.py`;\nit is not a second hand-maintained implementation.\n\nBuild the optional Windows desktop package from this tree only:\n\n```text\npython -m pip install -r requirements-desktop.txt\npowershell -ExecutionPolicy Bypass -File scripts/build_desktop.ps1\n```\n\nThe public desktop build has no configured update feed. Publishing an installer\nrequires a separately supplied repository, release channel and license.\n"""


def _public_data_integration_service() -> str:
    return '''"""Catalog of data domains that can be supplied by local report files."""\n\nfrom copy import deepcopy\nfrom datetime import datetime\n\nINTEGRATION_SOURCES = (\n    {"key": "product_day", "domain": "manual-import", "name": "商品日度报表",\n     "content": "访客、支付、加购、收藏、转化及商品经营指标", "frequency": "每日",\n     "dependency": "本地 CSV / Excel 文件", "readiness": "manual"},\n    {"key": "dmp_product_day", "domain": "manual-import", "name": "商品补充报表",\n     "content": "商品补充字段和交叉分析指标", "frequency": "每日",\n     "dependency": "本地 CSV / Excel 文件", "readiness": "manual"},\n    {"key": "shop_day", "domain": "manual-import", "name": "店铺日度报表",\n     "content": "店铺经营汇总指标", "frequency": "每日",\n     "dependency": "本地 CSV / Excel 文件", "readiness": "manual"},\n    {"key": "promotion_daily", "domain": "manual-import", "name": "推广报表",\n     "content": "花费、点击、转化、成交和投产指标", "frequency": "按需",\n     "dependency": "本地 CSV / Excel 文件", "readiness": "manual"},\n    {"key": "refund", "domain": "manual-import", "name": "退款报表",\n     "content": "退款金额和退款订单", "frequency": "按需",\n     "dependency": "本地 CSV / Excel 文件", "readiness": "manual"},\n    {"key": "customer", "domain": "manual-import", "name": "客户报表",\n     "content": "客户和复购分析所需字段", "frequency": "按需",\n     "dependency": "本地 CSV / Excel 文件", "readiness": "manual"},\n)\n\nREADINESS_LABELS = {"manual": "人工导入"}\n\n\ndef _freshness(latest_date):\n    if not latest_date:\n        return "unknown", None\n    try:\n        parsed = datetime.strptime(str(latest_date)[:10], "%Y-%m-%d").date()\n    except (TypeError, ValueError):\n        return "unknown", None\n    age_days = max(0, (datetime.now().date() - parsed).days)\n    return ("today" if age_days == 0 else "recent" if age_days <= 3 else "stale"), age_days\n\n\ndef build_integration_catalog(actual_sources):\n    """Merge the static manual-file registry with imported batch summaries."""\n    actual_by_key = {item.get("key"): item for item in actual_sources or []}\n    sources = []\n    for definition in INTEGRATION_SOURCES:\n        item = deepcopy(definition)\n        live = actual_by_key.get(item["key"])\n        item["readiness_label"] = READINESS_LABELS[item["readiness"]]\n        item["runtime_status"] = "available" if live else "not_imported"\n        item["run_status"] = live.get("run_status") if live else None\n        item["run_id"] = live.get("run_id") if live else None\n        item["latest_date"] = live.get("latest_date") if live else None\n        item["record_count"] = live.get("record_count") if live else None\n        item["freshness"], item["age_days"] = _freshness(item["latest_date"])\n        item["last_run"] = live.get("last_run") if live else None\n        sources.append(item)\n    domains = list(dict.fromkeys(item["domain"] for item in sources))\n    summary = {"total": len(sources), "connected": 0, "manual": len(sources),\n               "planned": 0, "blocked": 0,\n               "stale": sum(1 for item in sources if item["freshness"] in {"recent", "stale"})}\n    return {"sources": sources, "domains": domains, "summary": summary, "version": "public-manual-1"}\n'''


def _load_manifest(path: Path) -> dict:
    # The manifest is JSON-shaped YAML so the exporter has no parser dependency.
    return json.loads(path.read_text(encoding="utf-8"))


def _posix(path: Path) -> str:
    return path.as_posix().lstrip("./")


def _matches(rel: PurePosixPath, pattern: str) -> bool:
    pattern = pattern.replace("\\", "/").lstrip("./")
    if pattern.endswith("/**"):
        prefix = pattern[:-3].rstrip("/")
        return str(rel) == prefix or str(rel).startswith(prefix + "/")
    return rel.match(pattern) or str(rel) == pattern


def _is_excluded(rel: PurePosixPath, patterns: list[str]) -> bool:
    return any(_matches(rel, pattern) for pattern in patterns)


def _iter_sources(source: Path, manifest: dict):
    seen: set[Path] = set()
    for pattern in manifest["include"]:
        candidates = [source / pattern] if not any(ch in pattern for ch in "*?[") else list(source.glob(pattern))
        for candidate in candidates:
            if candidate.is_dir():
                candidates = list(candidate.rglob("*"))
            for item in candidates:
                if not item.is_file():
                    continue
                rel = PurePosixPath(item.relative_to(source).as_posix())
                if rel in seen or _is_excluded(rel, manifest["exclude"]):
                    continue
                if item.is_symlink():
                    raise SystemExit(f"refusing symlink in public input: {rel}")
                seen.add(rel)
                yield rel, item


def _replace_required(text: str, old: str, new: str, path: str) -> str:
    if old not in text:
        raise SystemExit(f"public transform anchor missing in {path}: {old[:80]!r}")
    return text.replace(old, new, 1)


def _sanitize_settings_service(text: str) -> str:
    text = re.sub(r"^.*Collector credentials.*\n", "", text, flags=re.M | re.I)
    text = text.replace("from services.credentials_crypto import decrypt_password, encrypt_password\n", "")
    text = re.sub(
        r"\n    'collector_credentials': \{.*?\n    \},",
        "",
        text,
        count=1,
        flags=re.S,
    )
    text = re.sub(
        r"\n    def _mask_collector_credentials\(.*?(?=\n    @staticmethod|\n    def |\nclass )",
        "",
        text,
        count=1,
        flags=re.S,
    )
    text = re.sub(
        r"\n    def get_collector_credentials\(.*?(?=\n    @staticmethod|\n    def |\nclass )",
        "",
        text,
        count=1,
        flags=re.S,
    )
    text = re.sub(
        r"\n        if 'collector_credentials' in values:.*?(?=\n        if 'classification_dictionaries' in values:)",
        "",
        text,
        count=1,
        flags=re.S,
    )
    text = _replace_required(
        text,
        "        values['collector_credentials'] = self._mask_collector_credentials(values.get('collector_credentials'))\n",
        "",
        "services/settings_service.py",
    )
    text = re.sub(r"^.*collector_credentials.*\n", "", text, flags=re.M)
    if "collector_credentials" in text or "credentials_crypto" in text:
        raise SystemExit("public settings transform left collector credential code")
    return text


def _sanitize_frontend(text: str, rel: str) -> str:
    if rel.endswith(".css"):
        text = "\n".join(line for line in text.splitlines() if 'data-page="data-collection"' not in line) + "\n"
    if rel.endswith(".js"):
        text = text.replace("'data-collection'", "'__public_removed_page__'")
        text = text.replace('"data-collection"', '"__public_removed_page__"')
    if rel == "frontend/ui_demo/assets/shell.js":
        text = re.sub(r"^\s*\['data-collection'.*\n", "", text, flags=re.M)
        text = re.sub(r"^\s*'data-collection':.*\n", "", text, flags=re.M)
    elif rel == "frontend/ui_demo/pages/settings.html":
        text = re.sub(
            r"\n\s*<section class=\"set-card\">(?:(?!</section>).)*data-collector-credentials-status.*?</section>",
            "",
            text,
            count=1,
            flags=re.S,
        )
    elif rel == "frontend/ui_demo/assets/settings-live.js":
        text = text.replace(
            "      collector_username: data.get('collector_username') || '', collector_password: data.get('collector_password') || '',\n",
            "",
        )
        text = re.sub(
            r"    const rawCredentials = data\.collector_credentials.*?\n    if \(storeBadge\).*?\n",
            "",
            text,
            count=1,
            flags=re.S,
        )
        text = text.replace("const data = new FormData(form); const existingCredentials = settingsPayload.data?.collector_credentials || {};", "const data = new FormData(form);")
        text = re.sub(r"\s*collector_credentials: \{.*?\},\n", "\n", text, count=1)
        text = re.sub(r"^\s*form\.elements\.collector_(?:username|password).*\n", "", text, flags=re.M)
        if "collector_" in text or "collectorCredentials" in text or "collector_credentials" in text:
            raise SystemExit("public settings frontend transform left collector credential code")
    return text


def _public_data_integration_api() -> str:
    return '''"""Public data-source catalog for manual files and local analysis."""\n\nfrom flask import Blueprint, request\n\nfrom api.api_response import failure, success\nfrom services.data_integration_service import INTEGRATION_SOURCES, READINESS_LABELS, build_integration_catalog\n\ndata_integration_bp = Blueprint("data_integration", __name__)\n\n\n@data_integration_bp.route("/api/data-integration/catalog", methods=["GET"])\ndef get_data_integration_catalog():\n    domain = request.args.get("domain") or None\n    readiness = request.args.get("readiness") or None\n    accepted_domains = sorted({item["domain"] for item in INTEGRATION_SOURCES})\n    if domain and domain not in accepted_domains:\n        return failure("VALIDATION_ERROR", "未知业务域", {"domain": domain, "accepted": accepted_domains}, status=422)\n    if readiness and readiness not in READINESS_LABELS:\n        return failure("VALIDATION_ERROR", "未知接入状态", {"readiness": readiness, "accepted": list(READINESS_LABELS)}, status=422)\n    catalog = build_integration_catalog([])\n    if domain:\n        catalog["sources"] = [item for item in catalog["sources"] if item["domain"] == domain]\n    if readiness:\n        catalog["sources"] = [item for item in catalog["sources"] if item["readiness"] == readiness]\n    catalog["domains"] = sorted({item["domain"] for item in catalog["sources"]})\n    catalog["filters"] = {key: value for key, value in (("domain", domain), ("readiness", readiness)) if value}\n    return success(catalog, evidence=[{"source": "manual_file_catalog", "count": len(catalog["sources"])}])\n'''


def _transform(rel: PurePosixPath, text: str) -> str:
    name = rel.as_posix()
    if name == "README.md":
        return PUBLIC_README
    if name == "desktop/package.json":
        package = json.loads(text)
        package.get("dependencies", {}).pop("electron-updater", None)
        return json.dumps(package, ensure_ascii=False, indent=2) + "\n"
    if name == "app.py":
        text = _replace_required(text, "from api.collect_api import collect_bp\n", "", name)
        text = _replace_required(text, "    app.register_blueprint(collect_bp)\n", "", name)
        text = _replace_required(text, "            '/data-center', '/data-collection', '/settings', '/goals', '/period-review',\n", "            '/data-center', '/settings', '/goals', '/period-review',\n", name)
        text = text.replace("configured collector shop", "configured shop")
        text = re.sub(
            r"\n# The web client used to call the upstream release API.*?\n\ndef _database_path_from_uri",
            "\n\ndef _latest_release():\n    return None\n\n\ndef _database_path_from_uri",
            text,
            count=1,
            flags=re.S,
        )
    elif name == "frontend/ui_demo/assets/desktop-integration.js":
        return PUBLIC_DESKTOP_INTEGRATION
    elif name == "frontend/ui_demo/assets/version-check.js":
        return PUBLIC_VERSION_CHECK
    elif name == "frontend/ui_demo/assets/version.js":
        return PUBLIC_VERSION_JS
    elif name == "api/data_integration_api.py":
        return _public_data_integration_api()
    elif name == "services/settings_service.py":
        text = _sanitize_settings_service(text)
    elif name == "services/data_integration_service.py":
        return _public_data_integration_service()
    elif name == "api/dmp_api.py":
        text = text.replace(
            "数据来源：collect_dmp_competition.py / collect_dmp_shop.py 采集落库的 dmp_* 表",
            "数据来源：通过本地文件导入的 dmp_* 表",
        )
        text = text.replace(
            "暂无达摩盘竞争分析数据，请先在采集中心运行 dmp_competition",
            "暂无达摩盘竞争分析数据，请先手动导入对应报表",
        )
    elif name == "services/source_resolution_service.py":
        text = text.replace(
            "Derived by the BI collectors (cart_users / product_visitors and",
            "Derived by imported observations (cart_users / product_visitors and",
        )
    elif name == "services/profit_structure_service.py":
        text = re.sub(r"与导入字段合同保持一致", "与导入字段合同保持一致", text)
    elif name == "services/market_monitor_service.py":
        text = re.sub(r"口径由公开版月度复盘规则定义", "口径由公开版月度复盘规则定义", text)
    elif name == "services/application_pages.py":
        text = _replace_required(text, "    'data-collection',\n", "", name)
    elif name == "services/page_capability_service.py":
        text = re.sub(
            r"\n    \{\n        'key': 'data-collection'.*?\n    \},",
            "",
            text,
            count=1,
            flags=re.S,
        )
        text = "\n".join(line for line in text.splitlines() if "'data-collection" not in line) + "\n"
    elif name == "desktop/src/updater.ts":
        return PUBLIC_UPDATER
    elif name == "desktop/src/main.ts":
        text = text.replace(
            "  window.webContents.setWindowOpenHandler(details => {\n"
            "    try {\n"
            "      const target = new URL(details.url)\n"
            "      if (target.protocol === 'https:' && target.hostname === 'github.com') void shell.openExternal(target.toString())\n"
            "    } catch {\n"
            "      // Keep malformed and untrusted popup URLs blocked.\n"
            "    }\n"
            "    return { action: 'deny' }\n"
            "  })",
            "  window.webContents.setWindowOpenHandler(() => ({ action: 'deny' }))",
        )
    elif name == "frontend/ui_demo/assets/shell.js":
        text = text.replace("GitHub", "代码仓库").replace("GitCode", "公开版")
    if name.startswith("frontend/ui_demo/"):
        text = _sanitize_frontend(text, name)
    text = re.sub(r"https://(?:gitcode\.com|github\.com)/owen891/tmall-dashboard[^\s\"'<>)]*", "#", text)
    text = text.replace("owen891/tmall-dashboard", "public-source")
    return text


def _write_text(path: Path, text: str):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8", newline="\n")


def _hash_tree(root: Path) -> tuple[list[dict], str]:
    files = []
    for path in sorted(item for item in root.rglob("*") if item.is_file()):
        rel = path.relative_to(root).as_posix()
        if rel == PUBLIC_METADATA_NAME:
            continue
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        files.append({"path": rel, "bytes": path.stat().st_size, "sha256": digest})
    payload = json.dumps(files, ensure_ascii=True, separators=(",", ":"))
    return files, hashlib.sha256(payload.encode("utf-8")).hexdigest()


def export_public(source: Path, output: Path) -> dict:
    source = source.resolve()
    output = output.resolve()
    if source == output or source in output.parents:
        raise SystemExit("output must be outside the source tree")
    if output.exists():
        if not output.is_dir() or any(output.iterdir()):
            raise SystemExit(f"output must be a new empty directory: {output}")
    else:
        output.mkdir(parents=True)
    manifest = _load_manifest(source / "release" / "public-manifest.yaml")
    copied = []
    for rel, path in _iter_sources(source, manifest):
        target = output / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        if path.suffix.lower() in {".py", ".js", ".ts", ".html", ".css", ".md", ".txt", ".yaml", ".yml", ".json"}:
            text = path.read_text(encoding="utf-8-sig")
            _write_text(target, _transform(rel, text))
        else:
            shutil.copyfile(path, target)
        copied.append(rel.as_posix())
    _write_text(output / "config.yaml", PUBLIC_CONFIG)
    _write_text(output / "requirements.txt", PUBLIC_REQUIREMENTS)
    _write_text(output / "requirements-desktop.txt", PUBLIC_REQUIREMENTS_DESKTOP)
    _write_text(output / "scripts/build_backend.py", PUBLIC_BUILD_BACKEND)
    _write_text(output / "scripts/build_desktop.ps1", PUBLIC_BUILD_DESKTOP)
    _write_text(output / "desktop/electron-builder.yml", PUBLIC_ELECTRON_BUILDER)
    _write_text(output / "desktop/tsconfig.json", PUBLIC_DESKTOP_TSCONFIG)
    _write_text(output / "OPEN_SOURCE_EDITION.md", PUBLIC_README)
    npm = shutil.which("npm") or shutil.which("npm.cmd")
    if not npm:
        raise SystemExit("npm is required to produce the public desktop lockfile")
    subprocess.run(
        [npm, "install", "--package-lock-only", "--offline", "--ignore-scripts", "--no-audit", "--no-fund"],
        cwd=output / "desktop",
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    files, tree_sha256 = _hash_tree(output)
    metadata = {
        "manifest_version": manifest["manifest_version"],
        "edition": "public",
        # Keep the artifact reproducible and avoid disclosing the maintainer's path.
        "source_root": "private-source",
        "source_ref": os.environ.get("TMALL_PUBLIC_SOURCE_REF", "working-tree"),
        "private_features": False,
        "generated_files": sorted(copied + [
            "config.yaml", "requirements.txt", "requirements-desktop.txt",
            "scripts/build_backend.py", "scripts/build_desktop.ps1",
            "desktop/electron-builder.yml", "desktop/tsconfig.json",
            "OPEN_SOURCE_EDITION.md",
        ]),
        "tree_sha256": tree_sha256,
        "file_count": len(files),
        "files": files,
    }
    _write_text(output / "PUBLIC-EDITION.json", json.dumps(metadata, ensure_ascii=True, indent=2) + "\n")
    return metadata


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Export the public manual-import edition")
    parser.add_argument("--source", type=Path, default=PROJECT_ROOT)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    metadata = export_public(args.source, args.output)
    print(json.dumps({"output": str(args.output.resolve()), "tree_sha256": metadata["tree_sha256"], "file_count": metadata["file_count"]}, ensure_ascii=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
