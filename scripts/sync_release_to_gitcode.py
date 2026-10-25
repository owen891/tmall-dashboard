"""把已下载的 v2.1.0 产物同步到 GitCode Release。

用法：
    python scripts/sync_release_to_gitcode.py --token <GITCODE_TOKEN>

token 在 https://gitcode.com/setting/token 创建，勾选 repo 权限（写）。
脚本做三件事：确保 v2.1.0 release 存在、逐个上传附件、打印最终校验。
已存在同名附件时先删除再上传（GitCode 附件不支持原地替换）。
"""
from __future__ import annotations

import argparse
import json
import mimetypes
import subprocess
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
ASSET_DIR = PROJECT_ROOT / '.tmp_release_assets'
OWNER = 'owen891'
REPO = 'tmall-dashboard'
API = 'https://gitcode.com/api/v5'
TAG = 'v2.1.0'

# 本地文件名 -> GitCode 附件名（沿用 v2.0.3 的命名习惯）
ASSETS = [
    'TmallDashboard-2.1.0-arm64.dmg',
    'TmallDashboard-2.1.0-arm64.dmg.blockmap',
    'TmallDashboard-2.1.0-arm64.zip',
    'TmallDashboard-2.1.0-arm64.zip.blockmap',
    'TmallDashboard-2.1.0-x64.dmg',
    'TmallDashboard-2.1.0-x64.dmg.blockmap',
    'TmallDashboard-2.1.0-x64.zip',
    'TmallDashboard-2.1.0-x64.zip.blockmap',
    'TmallDashboard-Setup-2.1.0-x64.exe',
    'TmallDashboard-Setup-2.1.0-x64.exe.blockmap',
    'latest.yml',
    'latest-mac.yml',
]


def request(method: str, path: str, token: str, *, payload=None, raw_body=None, content_type=None):
    url = f'{API}{path}'
    headers = {'private-token': token}
    data = None
    if payload is not None:
        data = json.dumps(payload).encode('utf-8')
        headers['Content-Type'] = 'application/json'
    elif raw_body is not None:
        data = raw_body
        if content_type:
            headers['Content-Type'] = content_type
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=120) as response:
            body = response.read()
            return response.status, (json.loads(body) if body else None)
    except urllib.error.HTTPError as error:
        return error.code, error.read().decode('utf-8', errors='replace')


def release_path() -> str:
    return f'/repos/{OWNER}/{REPO}/releases/tags/{TAG}'


def ensure_release(token: str, body: str) -> None:
    status, payload = request('GET', release_path(), token)
    if status == 200:
        print(f'· release {TAG} 已存在（id={payload.get("id")}）')
        return
    print(f'· 创建 release {TAG} ...')
    status, payload = request('POST', f'/repos/{OWNER}/{REPO}/releases', token, payload={
        'tag_name': TAG,
        'name': f'V{TAG.lstrip("v")}',
        'body': body,
        'prerelease': False,
    })
    if status not in (200, 201):
        raise SystemExit(f'创建 release 失败: {status} {payload}')


def existing_assets(token: str) -> dict:
    status, payload = request('GET', release_path(), token)
    if status != 200:
        raise SystemExit(f'读取 release 失败: {status} {payload}')
    return {item.get('name'): item for item in (payload.get('assets') or [])}


def delete_asset(token: str, asset_id) -> None:
    status, payload = request('DELETE', f'/repos/{OWNER}/{REPO}/releases/assets/{asset_id}', token)
    if status not in (200, 204):
        raise SystemExit(f'删除旧附件失败: {status} {payload}')


def upload_multipart(token: str, path: Path) -> None:
    """GitCode 附件上传走 multipart/form-data，字段名 file。"""
    boundary = '----tmallrelease' + str(abs(hash(path.name)))
    content_type = mimetypes.guess_type(path.name)[0] or 'application/octet-stream'
    head = (
        f'--{boundary}\r\n'
        f'Content-Disposition: form-data; name="file"; filename="{path.name}"\r\n'
        f'Content-Type: {content_type}\r\n\r\n'
    ).encode('utf-8')
    tail = f'\r\n--{boundary}--\r\n'.encode('utf-8')
    body = head + path.read_bytes() + tail
    status, payload = request(
        'POST', f'{release_path()}/upload_assets', token,
        raw_body=body, content_type=f'multipart/form-data; boundary={boundary}',
    )
    if status not in (200, 201):
        raise SystemExit(f'上传 {path.name} 失败: {status} {payload}')


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument('--token', required=True)
    parser.add_argument('--body-file', type=Path, default=PROJECT_ROOT / 'CHANGELOG.md')
    args = parser.parse_args()

    missing = [name for name in ASSETS if not (ASSET_DIR / name).is_file()]
    if missing:
        raise SystemExit('缺少产物，请先下载：' + ', '.join(missing))

    body = ''
    if args.body_file.is_file():
        text = args.body_file.read_text(encoding='utf-8')
        start = text.find('## V2.1.0')
        end = text.find('## V2.0.3')
        body = text[start:end].strip() if start >= 0 else ''

    ensure_release(args.token, body)
    have = existing_assets(args.token)
    for name in ASSETS:
        if name in have:
            print(f'· 替换旧附件 {name}')
            delete_asset(args.token, have[name].get('id'))
        print(f'· 上传 {name} ({(ASSET_DIR / name).stat().st_size / 1048576:.1f} MB)')
        upload_multipart(args.token, ASSET_DIR / name)

    final = existing_assets(args.token)
    print(f'\n完成。{TAG} 现有 {len(final)} 个附件：')
    for name in sorted(final):
        print('  -', name)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
