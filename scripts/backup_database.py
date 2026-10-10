"""Create an integrity-checked SQLite backup without mutating the source DB."""

import argparse
import hashlib
import json
import sqlite3
from datetime import datetime
from pathlib import Path


def _sha256(path):
    digest = hashlib.sha256()
    with open(path, 'rb') as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b''):
            digest.update(chunk)
    return digest.hexdigest()


def _integrity(path):
    connection = sqlite3.connect(path)
    try:
        return connection.execute('PRAGMA integrity_check').fetchone()[0]
    finally:
        connection.close()


def backup_database(source, destination=None):
    source_path = Path(source).resolve()
    if not source_path.is_file():
        raise FileNotFoundError(source_path)
    if destination is None:
        stamp = datetime.now().strftime('%Y%m%d-%H%M%S')
        destination = source_path.parent / 'backups' / f'{source_path.stem}-{stamp}.db'
    destination_path = Path(destination).resolve()
    if source_path == destination_path:
        raise ValueError('backup destination must differ from source')
    destination_path.parent.mkdir(parents=True, exist_ok=True)
    if destination_path.exists():
        raise FileExistsError(destination_path)

    source_connection = sqlite3.connect(source_path)
    destination_connection = sqlite3.connect(destination_path)
    try:
        source_connection.backup(destination_connection)
    finally:
        destination_connection.close()
        source_connection.close()

    integrity = _integrity(destination_path)
    report = {
        'ok': integrity == 'ok',
        'source': str(source_path),
        'destination': str(destination_path),
        'source_sha256': _sha256(source_path),
        'destination_sha256': _sha256(destination_path),
        'integrity': integrity,
        'size_bytes': destination_path.stat().st_size,
    }
    # 改进路线 2026-10-01 P1.3：轮转以前只挂在「默认落点」的 CLI 路径上，
    # aggregate_store_daily / backfill_* 这类显式指定目的地的调用方从未被
    # 裁剪，data/backups 因此堆到 7 份 24GB（config 上限 4 份 20GB）。
    # 移到函数级：每次备份后都按 config.yaml 裁剪，刚生成的这份受 protected
    # 保护；轮转失败不影响备份本身的成立。
    #
    # 数据安全（2026-10-08 修复）：裁剪范围是 destination 所在目录的 ``*.db``。
    # 当调用方把 --backup-destination 指到与源库相同的目录时，**源库本身也匹配
    # ``*.db``**，于是被当成「陈旧备份」删除——实测 aggregate_store_daily 等
    # 约 30 个脚本都会因此当场删掉生产库
    # （``before: source exists = True`` → ``after: source exists = False``）。
    # 源库必须与本次备份一样受保护；protected 占用 keep 配额，源库与本次备份
    # 同时受保护时二者都留存。
    try:
        try:
            from scripts.backup_retention import prune_backups, retention_settings
        except ImportError:
            from backup_retention import prune_backups, retention_settings
        keep_newest, max_total_bytes = retention_settings()
        report['pruned'] = [str(item) for item in prune_backups(
            destination_path.parent, keep_newest=keep_newest,
            max_total_bytes=max_total_bytes, protected=[destination_path, source_path])]
    except Exception as error:
        report['pruned'] = None
        report['prune_warning'] = str(error)
    return report


def main():
    parser = argparse.ArgumentParser(description='Create an integrity-checked SQLite backup')
    parser.add_argument('--source', required=True)
    parser.add_argument('--destination', default=None)
    args = parser.parse_args()
    report = backup_database(args.source, args.destination)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    raise SystemExit(0 if report['ok'] else 1)


if __name__ == '__main__':
    main()
