"""Merge per-architecture electron-builder macOS update metadata."""

from __future__ import annotations

import argparse
from pathlib import Path

import yaml


def merge_metadata(documents: list[dict]) -> dict:
    if not documents:
        raise ValueError('至少需要一份 macOS 更新元数据')
    versions = {str(document.get('version', '')) for document in documents}
    if len(versions) != 1 or '' in versions:
        raise ValueError('macOS 更新元数据版本不一致')
    files_by_url: dict[str, dict] = {}
    for document in documents:
        files = document.get('files') or []
        if not isinstance(files, list):
            raise ValueError('macOS 更新元数据 files 格式错误')
        for item in files:
            if not isinstance(item, dict) or not item.get('url') or not item.get('sha512'):
                raise ValueError('macOS 更新文件缺少 url 或 sha512')
            files_by_url[str(item['url'])] = item
    if not files_by_url:
        raise ValueError('macOS 更新元数据没有可下载文件')
    merged = {
        'version': versions.pop(),
        'files': [files_by_url[url] for url in sorted(files_by_url)],
    }
    release_dates = [document.get('releaseDate') for document in documents if document.get('releaseDate')]
    if release_dates:
        merged['releaseDate'] = max(release_dates)
    return merged


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument('inputs', nargs='+', type=Path)
    parser.add_argument('-o', '--output', required=True, type=Path)
    args = parser.parse_args()
    documents = [yaml.safe_load(path.read_text(encoding='utf-8')) for path in args.inputs]
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(yaml.safe_dump(merge_metadata(documents), allow_unicode=True, sort_keys=False), encoding='utf-8')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
