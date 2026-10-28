"""Verify a built macOS .app carries a real bundle seal and (optionally) notarization.

Run this on the macOS runner right after `npm run dist:mac`, before the artifacts are
uploaded. A .app without `Contents/_CodeSignature/CodeResources` is what macOS reports
as "已损坏，无法打开" once the download picks up a quarantine attribute, so this gate
fails the build instead of shipping it.
"""

from __future__ import annotations

import argparse
import pathlib
import subprocess
import sys


def run(args: list[str]) -> tuple[int, str]:
    completed = subprocess.run(args, capture_output=True, text=True)
    output = (completed.stdout + completed.stderr).strip()
    return completed.returncode, output


def check_bundle(app: pathlib.Path) -> list[str]:
    """Return human readable problems found in the bundle layout."""
    problems: list[str] = []
    if not app.is_dir():
        return [f'找不到 app bundle: {app}']
    sealed = app / 'Contents' / '_CodeSignature' / 'CodeResources'
    if not sealed.is_file():
        problems.append(f'缺少 bundle 封印: {sealed.relative_to(app)}')
    executable = app / 'Contents' / 'MacOS'
    if not executable.is_dir() or not any(executable.iterdir()):
        problems.append('Contents/MacOS 下没有可执行文件')
    return problems


def check_signature(app: pathlib.Path) -> list[str]:
    code, output = run(['codesign', '--verify', '--deep', '--strict', '--verbose=2', str(app)])
    if code != 0:
        return [f'codesign --verify 失败: {output}']
    return []


def signing_authority(app: pathlib.Path) -> tuple[str, str]:
    code, output = run(['codesign', '--display', '--verbose=4', str(app)])
    authority = ''
    team = ''
    for line in output.splitlines():
        line = line.strip()
        if line.startswith('Authority=') and not authority:
            authority = line.split('=', 1)[1]
        elif line.startswith('TeamIdentifier='):
            team = line.split('=', 1)[1]
    return authority, team


def check_notarization(app: pathlib.Path) -> list[str]:
    code, output = run(['spctl', '--assess', '--type', 'execute', '--verbose=4', str(app)])
    if code != 0:
        return [f'spctl --assess 未通过（Gatekeeper 会拦截该包）: {output}']
    code, output = run(['xcrun', 'stapler', 'validate', str(app)])
    if code != 0:
        return [f'stapler validate 失败（未钉公证票据）: {output}']
    return []


def verify(app: pathlib.Path, require_developer_id: bool, require_notarization: bool) -> int:
    problems = check_bundle(app)
    if problems:
        for item in problems:
            print(f'FAIL  {item}')
        return 1

    problems = check_signature(app)
    if problems:
        for item in problems:
            print(f'FAIL  {item}')
        return 1

    authority, team = signing_authority(app)
    is_adhoc = authority in ('', '-') or authority.startswith('adhoc')
    print(f'INFO  authority={authority or "未命名"} team={team or "无"}')

    if require_developer_id and is_adhoc:
        print('FAIL  要求 Developer ID 签名，实际是 ad-hoc（证书没被 keychain 接住）')
        return 1
    if is_adhoc:
        print('WARN  ad-hoc 签名：bundle 已封印，用户仍需先移除 quarantine 才能打开')

    if require_notarization and not is_adhoc:
        problems = check_notarization(app)
        if problems:
            for item in problems:
                print(f'FAIL  {item}')
            return 1
        print('INFO  公证票据已钉入 app bundle')

    executable = next((app / 'Contents' / 'MacOS').iterdir())
    print(f'PASS  {app.name} 封印完整，主可执行文件 {executable.name}')
    return 0


def resolve_app(target: pathlib.Path) -> pathlib.Path:
    """Accept either the .app itself or the release directory that holds it.

    electron-builder writes the unpacked bundle to `release/mac/<name>.app` for the
    default arch and `release/mac-<arch>/<name>.app` otherwise, so a directory
    argument is resolved by globbing instead of hard-coding the arch suffix.
    """
    if target.suffix == '.app':
        return target
    if target.is_dir():
        bundles = sorted(target.glob('*.app'))
        if len(bundles) == 1:
            return bundles[0]
        if not bundles:
            raise SystemExit(f'在 {target} 下找不到 .app')
        raise SystemExit(f'{target} 下有 {len(bundles)} 个 .app，请直接指定其中一个')
    return target


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        'app',
        type=pathlib.Path,
        help='.app 路径，或包含它的 desktop/release/mac* 目录',
    )
    parser.add_argument(
        '--require-developer-id',
        default='false',
        help='true 时 ad-hoc 签名直接判失败；false 时只要求存在 bundle 封印',
    )
    parser.add_argument(
        '--require-notarization',
        action='store_true',
        help='额外要求 spctl 通过且 stapler 已钉票据',
    )
    args = parser.parse_args()
    require_developer_id = str(args.require_developer_id).strip().lower() in {'1', 'true', 'yes'}
    return verify(resolve_app(args.app.resolve()), require_developer_id, args.require_notarization)


if __name__ == '__main__':
    sys.exit(main())
