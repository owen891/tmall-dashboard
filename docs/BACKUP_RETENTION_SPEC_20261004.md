# 备份轮转语义修正 —— spec（L0 产出）

> 阶段：**L0 讨论收敛**
> 状态：**待 Gate 1 确认**（人未确认前不进入 L1，不派生任何执行者）
> 日期：2026-10-04
> 依据：本机实测 + `docs/IMPROVEMENT_ROADMAP_20261001.md` §1.2 / P1.3
> 执行规程：`docs/AGENT_TEAM_PLAYBOOK.md`；技能 `team-orchestration`
> 命名说明：技能里的 `spec.md` 按本仓库惯例落成 `docs/<TOPIC>_SPEC_YYYYMMDD.md`
> ⚠️ **L1 对抗审核后修订**：本文档 §4 的契约与 §5 的 **T-A3 已被否决**（T-A3 与 C1 自相矛盾）。冻结契约以 `docs/BACKUP_RETENTION_PLAN_20261004.md` v2 第 2 节的 **C1–C7** 为准。

---

## 1. 问题（实测证据，非推测）

| 事实 | 证据 |
|---|---|
| 配置上限 4 份 | `config.yaml` → `data.max_backups: 4` |
| 实际 5 份 | `data/backups/` 实测 `count=5`，全为 `.db`，合计 14.22 GB |
| 裁剪把 protected 排除在候选之外 | `scripts/backup_retention.py:52-53` |
| 再对剩余候选应用 `keep_newest` | `scripts/backup_retention.py:58-62` |
| 调用方把「刚生成的那份」传入 protected | `scripts/backup_database.py:70-72`、`scripts/import_paimi_bi_daily.py:291`、`scripts/import_paimi_bi_overview.py:270` |

**机制**：`prune_backups` 先剔除 `protected`，再对剩余保留 `keep_newest` 份 ⇒

```text
稳态总数 = keep_newest + len(protected) = 4 + 1 = 5
```

与实测 `count=5` 完全吻合。路线图 §1.2 记录的「堆到 7 份（config 上限 4 份 20GB）」是同一偏移在多保护对象下的累积结果。

**性质**：`max_backups` 的字面语义是「目录内备份总份数上限」，实现却变成「除本次快照外的份数上限」，恒多 1 份。

---

## 2. 目标

让 `max_backups` 恢复字面语义：**裁剪后目录内匹配 `pattern` 的文件总数 ≤ `keep_newest`（含刚生成的那一份）**，同时总量仍受 `max_backup_total_gb` 约束。

---

## 3. 非目标（本轮绝不做）

- 不删除、不移动 `data/backups/` 中任何现有文件（存量另行决定）
- 不修改 `config.yaml` 的 `max_backups` / `max_backup_total_gb` 数值
- 不触碰 `data/dashboard.db`，不执行 `VACUUM`
- 不改动备份本身的正确性语义（`sha256` / `integrity` / `FileExistsError` / `source != destination` 全部保持）
- 不引入新策略（不做时间窗口、前缀分层、异地归档）

---

## 4. 待冻结的契约（L1 第一步：先冻结，再并行）

`prune_backups(backup_dir, keep_newest, max_total_bytes, pattern='*.db', protected=())`

- **语义**：`keep_newest` = 裁剪后**目录内匹配文件的总数上限**；protected 项**占用**该配额。
- **优先级**：protected 永不删除。若 `len(protected) >= keep_newest`，则保留全部 protected，总数允许 > `keep_newest`——这是刻意保留的例外，必须写测试固化，不能靠注释。
- **容量**：保留项累计超过 `max_total_bytes` 时继续裁剪非 protected 项（保持现有 AND 行为，行为变更需在方案中显式说明）。
- **返回值**：被删除路径列表；目录不存在返回 `[]`。
- **容错**：单个 `unlink` 失败继续处理其余项（保持现状）。

---

## 5. 验收标准（Gate 3 用；必须是可执行命令 + 期望输出）

| # | 命令 / 动作 | 期望输出 |
|---|---|---|
| A1 | `./.venv/Scripts/python.exe -m pytest tests/test_backup_retention_enforcement.py -q` | 全绿 |
| A2 | **新增契约测试**：5 个假 `.db` + `keep_newest=4` + `protected=[最新那份]` | 断言剩余 **4 份**（不是 5） |
| A3 | **新增边界测试**：`len(protected) >= keep_newest` | 断言 protected 全部保留，且行为与契约第 4 节一致 |
| A4 | 回归：`./.venv/Scripts/python.exe -m pytest tests/ -q` | 无新增失败（基线 912 passed） |
| A5 | 门禁：`Set-ExecutionPolicy -Scope Process Bypass -Force` 后 `& ./scripts/test_all.ps1` | 输出 `TEST_ALL_OK` |
| A6 | **只读复核**：`Get-ChildItem data/backups` | 份数与改动前一致（**5**）——证明测试全程未触碰真实数据 |

> A6 是硬性项：本轮只改逻辑，**不清理存量**。

---

## 6. 风险与回滚

- **风险**：裁剪语义改动写错会多删备份。**缓解**：全部验证在 `tempfile` fixture 上完成，并由 A6 强制证明真实目录未被触碰。
- **回滚**：改动局限在少数文件、独立提交，`git revert` 即可。

---

## 7. 待你确认的开放问题（Gate 1）

1. `len(protected) >= keep_newest` 时按「protected 优先、总数允许超限」处理，可以吗？（备选：报错/告警）
2. 是否顺带把 `scripts/cleanup_backups.py:74` 的手动清理语义（`KEEP_NEWEST_BACKUPS`，留 2 份）一并对齐？
3. 存量的第 5 份与 `dashboard-20261002-015552.db` 是否在本轮之后单独处理？**本轮不动。**
