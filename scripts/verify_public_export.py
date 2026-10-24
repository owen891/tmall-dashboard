"""Verify that a generated public tree contains the importable public boundary."""

from __future__ import annotations

import argparse
import ast
import hashlib
import json
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path


FORBIDDEN_PATH_PATTERNS = (
    ".git",
    "data",
    "api/collect_api.py",
    "services/collector_",
    "services/credentials_crypto.py",
    "scripts/collect_",
    "scripts/browser_",
    "scripts/runtime_paths.py",
    "check_login_state.py",
    "open_bi_overview.py",
    "frontend/ui_demo/assets/downloads",
)
PRIVATE_PATH_MARKERS = {
    "collector",
    "collectors",
    "credentials",
    "cookies",
    "profiles",
    "secrets",
    "downloads",
}
FORBIDDEN_BINARY_SUFFIXES = {
    ".7z", ".dmp", ".dll", ".dylib", ".exe", ".pyd", ".rar", ".so", ".sqlite", ".sqlite3", ".zip"
}
FORBIDDEN_TEXT = re.compile(
    r"api\.collect_api|/api/collect/|collector_credentials|data-collection|"
    r"browser_runtime|TMALL_COLLECT|collector_retry|credentials_crypto|"
    r"collect_dmp_|Chrome\s*调试|万相台登录|(?:[A-Za-z]:)?[\/](?:BI采集|skill-dianshang)",
)


def _fail(message: str):
    raise SystemExit(f"PUBLIC_EXPORT_INVALID: {message}")


def _check_paths(root: Path):
    for path in root.rglob("*"):
        rel = path.relative_to(root).as_posix()
        if any(rel == pattern or rel.startswith(pattern + "/") for pattern in FORBIDDEN_PATH_PATTERNS):
            _fail(f"forbidden path: {rel}")
        if path.is_symlink():
            _fail(f"symlink is not allowed: {rel}")


def _check_binary_and_private_assets(root: Path):
    text_suffixes = {".css", ".html", ".js", ".md", ".py", ".txt", ".yaml", ".yml"}
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        rel = path.relative_to(root).as_posix()
        components = {part.lower() for part in Path(rel).parts}
        if components & PRIVATE_PATH_MARKERS:
            _fail(f"private asset path: {rel}")
        if path.suffix.lower() in FORBIDDEN_BINARY_SUFFIXES:
            _fail(f"forbidden binary asset: {rel}")
        if path.suffix.lower() not in text_suffixes:
            sample = path.read_bytes()[:4096]
            if b"\x00" in sample and path.suffix.lower() in {".bin", ".dat"}:
                _fail(f"unclassified binary asset: {rel}")


def _check_text(root: Path):
    for path in root.rglob("*"):
        if not path.is_file() or path.suffix.lower() not in {".py", ".js", ".html", ".css", ".yaml", ".yml", ".md", ".txt"}:
            continue
        text = path.read_text(encoding="utf-8-sig")
        if FORBIDDEN_TEXT.search(text):
            _fail(f"private collector reference in {path.relative_to(root)}")


def _check_python(root: Path):
    for path in root.rglob("*.py"):
        ast.parse(path.read_text(encoding="utf-8-sig"), filename=str(path))


def _hash_tree(root: Path) -> tuple[list[dict], str]:
    files = []
    for path in sorted(item for item in root.rglob("*") if item.is_file()):
        rel = path.relative_to(root).as_posix()
        if rel == "PUBLIC-EDITION.json":
            continue
        files.append({"path": rel, "bytes": path.stat().st_size,
                      "sha256": hashlib.sha256(path.read_bytes()).hexdigest()})
    payload = json.dumps(files, ensure_ascii=True, separators=(",", ":"))
    return files, hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _check_runtime(root: Path):
    probe = (
        "import json,sys,tempfile; "
        "import config as config_module; "
        "config_module.DEFAULT_IMPORT_SCAN_INBOX=sys.argv[3]; "
        "import app as app_module; "
        "app_module.DEFAULT_IMPORT_SCAN_INBOX=sys.argv[3]; "
        "from app import create_app; "
        "assert 'api.collect_api' not in sys.modules; "
        "app=create_app({'TESTING':True,'DATABASE_PATH':sys.argv[1]," 
        "'IMPORT_SCAN_ALLOWED_ROOTS':[sys.argv[2]]}); "
        "rules={r.rule for r in app.url_map.iter_rules()}; "
        "assert '/api/imports/preview' in rules; "
        "assert not any(r.startswith('/api/collect') for r in rules); "
        "print(json.dumps({'routes':len(rules),'public_imports':True}))"
    )
    with tempfile.TemporaryDirectory(prefix="tmall-public-verify-") as temp:
        scan_root = str(Path(temp) / "import-inbox")
        command = [
            sys.executable,
            "-c",
            probe,
            str(Path(temp) / "dashboard.db"),
            scan_root,
            scan_root,
        ]
        probe_env = os.environ.copy()
        probe_env["PYTHONDONTWRITEBYTECODE"] = "1"
        result = subprocess.run(command, cwd=root, text=True, capture_output=True, env=probe_env)
    if result.returncode:
        _fail(f"public runtime probe failed: {result.stdout.strip()} {result.stderr.strip()}")
    return result.stdout.strip()


def verify_public(root: Path) -> dict:
    root = root.resolve()
    if not root.is_dir():
        _fail(f"missing output directory: {root}")
    metadata_path = root / "PUBLIC-EDITION.json"
    if not metadata_path.is_file():
        _fail("missing PUBLIC-EDITION.json")
    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    if metadata.get("edition") != "public" or metadata.get("private_features") is not False:
        _fail("edition metadata is not public")
    _check_paths(root)
    _check_binary_and_private_assets(root)
    _check_text(root)
    _check_python(root)
    files, tree_sha256 = _hash_tree(root)
    if metadata.get("files") != files or metadata.get("file_count") != len(files):
        _fail("metadata file inventory does not match output tree")
    if metadata.get("tree_sha256") != tree_sha256:
        _fail("metadata tree hash does not match output tree")
    if metadata.get("source_root") != "private-source":
        _fail("metadata discloses a local source path")
    runtime = _check_runtime(root)
    return {"result": "PASS_PUBLIC_EXPORT", "root": str(root), "tree_sha256": tree_sha256, "runtime": runtime}


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Verify a public manual-import export")
    parser.add_argument("--root", type=Path, required=True)
    args = parser.parse_args(argv)
    print(json.dumps(verify_public(args.root), ensure_ascii=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
