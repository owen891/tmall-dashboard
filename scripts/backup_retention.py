"""数据库备份的保留策略：按「数量」+「总容量」双重裁剪。

导入脚本每次运行都会整库备份。当前库 2.6GB，一份备份约 2.5GB；
不设上限时会迅速吃掉磁盘——2026-09-20 实测：22:13~22:27 的一批导入就生成了
5 份（≈12.5GB），`data/backups/` 累计到 47.3GB，而 E 盘总余量只有 65.9GB。
盘满的后果是导入和看板一起挂，所以备份必须定期裁剪。

裁剪语义（冻结契约 v2，见 ``docs/BACKUP_RETENTION_PLAN_20261004.md`` 第 2 节）：

* **C1** ``keep_newest`` 是裁剪后目录内**匹配文件的总数上限**；
  ``protected`` 项**占用**该配额，不再是额外加在配额之上的豁免项。
  因此稳态份数 = ``keep_newest``，而不是旧实现的 ``keep_newest + len(protected)``。
* **C1.1** 若 ``len(protected) >= keep_newest``：protected 全部保留，
  非 protected 全部裁掉，总数 = ``len(protected)``。
* **C2** 非 protected 的保留数 = ``max(0, keep_newest - len(protected))``。
* **C3** 容量：protected 的字节**计入** ``max_total_bytes``；扣除 protected 后，
  剩余配额按「新的在前」继续保留非 protected。
* **C4** 超限终态：裁光全部非 protected 后总字节仍超限时（protected 自身超限），
  **不抛异常**——保留全部 protected 并记录 warning；调用方传入 ``report`` dict 时
  回填 ``report['over_capacity'] = True``。
* **C5** 返回被删除路径列表；目录不存在返回 ``[]``；单个 ``unlink`` 失败继续处理其余项。
* **C6** ``keep_newest`` 一律经 ``max(1, ·)`` 夹取，调用方不得绕过。

用法：
    from scripts.backup_retention import prune_backups, retention_settings
    keep, cap = retention_settings()
    prune_backups(backup_dir, keep_newest=keep, max_total_bytes=cap)
"""

from __future__ import annotations

import logging
from pathlib import Path

DEFAULT_KEEP_NEWEST = 4
DEFAULT_MAX_TOTAL_BYTES = 20 * 1024 ** 3  # 20GB

logger = logging.getLogger(__name__)


def retention_settings(config_path=None):
    """从 ``config.yaml`` 的 ``data`` 段读保留策略，缺失或读取失败时用默认值。

    返回 ``(keep_newest, max_total_bytes)``；``keep_newest`` 已按 C6 夹取到 ≥ 1
    （``max_backups: 0`` 或负值都会被夹到 1，而不是「删光全部非 protected」）。
    """
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


def _mtime(path):
    """取 ``st_mtime``；文件在并发删除下消失时按「最旧」处理（排到最后）。"""
    try:
        return path.stat().st_mtime
    except OSError:
        return float('-inf')


def _size(path):
    """取 ``st_size``；取不到（已消失）按 0 计。"""
    try:
        return path.stat().st_size
    except OSError:
        return 0


def prune_backups(
    backup_dir,
    keep_newest=DEFAULT_KEEP_NEWEST,
    max_total_bytes=DEFAULT_MAX_TOTAL_BYTES,
    pattern='*.db',
    protected=(),
    report=None,
):
    """按 C1–C6 裁剪 ``backup_dir`` 下匹配 ``pattern`` 的备份文件。

    契约要点（完整契约见 ``docs/BACKUP_RETENTION_PLAN_20261004.md`` 第 2 节）：

    - ``keep_newest`` 是裁剪后**匹配文件总数上限**，``protected`` 占用该配额；
      ``len(protected) >= keep_newest`` 时 protected 全留、非 protected 全裁，
      总数 = ``len(protected)``（C1/C1.1/C2）。
    - ``protected`` 的字节计入 ``max_total_bytes``，剩余配额按「新的在前」
      保留非 protected（C3）。容量账本统计**全部** protected 匹配项；
      ``len(protected) > keep_newest`` 时被超出 keep 配额的那部分 protected
      仍会保留、也仍计入容量，因此可能触发 C4 的 ``over_capacity``。
    - 裁光非 protected 后仍超限时保留 protected、记 warning，不抛异常；
      ``report`` 传入时回填 ``report['over_capacity'] = True``（C4）。
    - 返回**被删除的文件路径列表**；目录不存在返回 ``[]``；单个 ``unlink``
      失败继续处理其余项（C5）。
    - ``keep_newest`` 一律经 ``max(1, ·)`` 夹取（C6）。

    ``protected`` 里的文件名（或路径）永不删除，留给「本次导入前的快照」这类
    必须留着做回滚的对象。``report`` 是可选 dict，仅用于回传
    ``over_capacity`` 等诊断字段——为保持向后兼容默认 ``None``，
    6 个既有调用点无需改动。

    容错细节（C5）：每项**先按 C1/C2/C3 判定是否纳入保留配额**，判定为保留则
    直接跳过（不调用 unlink）；判定为裁剪才执行 ``unlink``，失败则记 warning
    并继续处理后续项。因此删除失败的项不会被计入返回列表，配额账本也不会
    出现「计入已删除文件」的虚占。
    """
    directory = Path(backup_dir)
    if not directory.is_dir():
        return []

    keep = max(1, int(keep_newest))  # C6：下游不得绕过
    protected_names = {Path(item).name for item in protected}

    matching = [item for item in directory.glob(pattern) if item.is_file()]
    matching.sort(key=_mtime, reverse=True)  # 新的在前
    # C1：protected 占用 keep_newest 配额，不再是额外豁免项。
    # protected 一律「永不删除」，因此实际留存的是**全部** protected 匹配项；
    # 只有「占用 keep 配额」的那部分才参与 slots 计算。两者必须分开：
    # 若把 [:keep] 的截断结果同时当作容量账本（旧实现的 F-01），
    # len(protected) > keep 时就会漏计被截断 protected 的字节 → C4 漏报。
    protected_items = [item for item in matching if item.name in protected_names]
    quota_protected = protected_items[:keep]
    fresh_candidates = [item for item in matching if item.name not in protected_names]

    removed = []
    # C3：protected 的字节计入容量配额（统计全部 protected，与截断无关）。
    kept_bytes = sum(_size(item) for item in protected_items)
    # C2：非 protected 的保留数 = max(0, keep - len(protected))。
    slots = max(0, keep - len(quota_protected))
    for path in fresh_candidates:
        size = _size(path)
        if slots > 0 and kept_bytes + size <= max_total_bytes:
            # 判定为保留：按 C1/C2/C3 记账后直接跳过，不调用 unlink。
            kept_bytes += size
            slots -= 1
            continue
        try:
            path.unlink()
        except OSError:  # C5：单个 unlink 失败不影响其余项
            logger.warning('备份裁剪：删除失败，已跳过 %s', path)
            continue
        removed.append(path)

    # C4：超限终态——protected 自身超限时不抛异常，只记录并可选回传。
    if protected_items and kept_bytes > max_total_bytes:
        logger.warning(
            '备份裁剪：protected 共 %d 项、%d 字节，已超过 max_total_bytes=%s；'
            '保留全部 protected，不删除 protected。',
            len(protected_items), kept_bytes, max_total_bytes,
        )
        if report is not None:
            report['over_capacity'] = True
    return removed
