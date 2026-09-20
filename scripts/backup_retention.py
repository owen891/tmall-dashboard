"""数据库备份的保留策略：按「数量」+「总容量」双重裁剪。

导入脚本每次运行都会整库备份。当前库 2.6GB，一份备份约 2.5GB；
不设上限时会迅速吃掉磁盘——2026-09-20 实测：22:13~22:27 的一批导入就生成了
5 份（≈12.5GB），`data/backups/` 累计到 47.3GB，而 E 盘总余量只有 65.9GB。
盘满的后果是导入和看板一起挂，所以备份必须定期裁剪。

用法：
    from scripts.backup_retention import prune_backups, retention_settings
    keep, cap = retention_settings()
    prune_backups(backup_dir, keep_newest=keep, max_total_bytes=cap)
"""

from __future__ import annotations

from pathlib import Path

DEFAULT_KEEP_NEWEST = 4
DEFAULT_MAX_TOTAL_BYTES = 20 * 1024 ** 3  # 20GB


def retention_settings(config_path=None):
    """从 ``config.yaml`` 的 ``data`` 段读保留策略，缺失或读取失败时用默认值。"""
    try:
        import yaml

        path = Path(config_path) if config_path else Path(__file__).resolve().parents[1] / 'config.yaml'
        with open(path, encoding='utf-8') as handle:
            data = (yaml.safe_load(handle) or {}).get('data') or {}
        keep = int(data.get('max_backups') or DEFAULT_KEEP_NEWEST)
        cap_gb = float(data.get('max_backup_total_gb') or DEFAULT_MAX_TOTAL_BYTES / 1024 ** 3)
        return max(1, keep), max(0, int(cap_gb * 1024 ** 3))
    except Exception:
        return DEFAULT_KEEP_NEWEST, DEFAULT_MAX_TOTAL_BYTES


def prune_backups(
    backup_dir,
    keep_newest=DEFAULT_KEEP_NEWEST,
    max_total_bytes=DEFAULT_MAX_TOTAL_BYTES,
    pattern='*.db',
    protected=(),
):
    """保留最新的 ``keep_newest`` 份且总容量不超过 ``max_total_bytes``，其余删除。

    ``protected`` 里的文件名（或路径）永不删除，留给「本次导入前的快照」这类
    必须留着做回滚的对象。返回被删除的文件路径列表。
    """
    directory = Path(backup_dir)
    if not directory.is_dir():
        return []
    protected_names = {Path(item).name for item in protected}
    candidates = [item for item in directory.glob(pattern) if item.is_file() and item.name not in protected_names]
    candidates.sort(key=lambda item: item.stat().st_mtime, reverse=True)  # 新的在前

    removed = []
    kept_bytes = 0
    for index, path in enumerate(candidates):
        size = path.stat().st_size
        if index < keep_newest and kept_bytes + size <= max_total_bytes:
            kept_bytes += size
            continue
        try:
            path.unlink()
        except OSError:
            continue
        removed.append(path)
    return removed
