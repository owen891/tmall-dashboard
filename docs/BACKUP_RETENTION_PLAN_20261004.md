# 备份轮转语义修正 —— 方案 v2

> 版本：**v2.0**（v1 经 L1 架构对抗审核，结论 **需修订**）
> 日期：2026-10-04
> 依据：`docs/BACKUP_RETENTION_SPEC_20261004.md`（L0，已过 Gate 1）
> 规程：`docs/AGENT_TEAM_PLAYBOOK.md`；技能 `team-orchestration`
> 原则：**先冻结契约，再动实现；只改逻辑，不动存量**
> ⚠️ 本文件第 2 节的契约**取代 spec §4**；spec §5 的 T-A3 已被否决（见第 3 节）
> **v2.1（2026-10-04）**：T1–T5 落地后经 L3 独立审核得 **FAIL**（`docs/BACKUP_RETENTION_REVIEW_20261004.md` **F-01**：C4 在 `len(protected) > keep` 分支既不 warning 也不回填 `over_capacity`）。已开 **T6/T7/T8** 返工，修完须由同一 verifier 复验。本版同时补 C1.1「protected 指实际存在且匹配项」与 C3「跳过超容量项并继续」两处文字澄清（对应审核 F-02 / F-05）。

---

## 0. 怎么用这份方案

- 每个任务带 **`文件:行号`**；没有行号的条目**不开工**。
- 每批结束跑第 6 节验证命令，拿数字比对基线。
- **不做的事写在第 8 节**（已按对抗意见补全）。

---

## 1. 目标与验收基线

| 指标 | 现状 | 目标 | 验证方式 |
|---|---|---|---|
| 裁剪后目录内匹配份数（`max_backups: 4`） | **5** | **≤ 4** | T-A2 契约测试 |
| `len(protected) >= keep_newest` | 未定义行为 | protected 全留，总数 = `len(protected)` | T-A3（**已修正**） |
| `max_backups ≤ 0` 时的行为 | **删光全部非 protected** | 夹取到 ≥ 1 | T-A9 |
| **真实 `data/backups/` 前后快照** | 5 份 / 14.221 GB | **name+size 逐项一致** | 强化版 A6 |
| Python 回归 | 912 passed | 无新增失败 | `pytest tests/ -q` |
| 一体化门禁 | `TEST_ALL_OK` | 保持 | `scripts/test_all.ps1` |

---

## 2. 冻结契约 v2.1（取代 spec §4）

| 条款 | 内容 |
|---|---|
| **C1** | `keep_newest` = 裁剪后**目录内匹配文件的总数上限**；protected 项**占用**该配额 |
| **C1.1** | 若 `len(protected) >= keep_newest`：protected **全部保留**，非 protected **全部裁掉**，总数 = `len(protected)`。此处 protected 指**实际存在且匹配 `pattern` 的项**（不存在 / 不匹配的传入路径不占配额） |
| **C2** | 非 protected 的保留数 = `max(0, keep_newest - len(protected))` |
| **C3** | 容量：**全部** protected 项的字节计入 `max_total_bytes`（**不得因数量配额而漏计**）；扣除后，非 protected 按「新的在前」逐个记账。**遇到单项超出剩余容量时：跳过该项并继续尝试更旧的项，不中断** |
| **C4** | **超限终态**：若裁光全部非 protected 后总字节仍 > `max_total_bytes`（protected 自身超限），**不抛异常**：保留全部 protected 并记录 warning；若调用方传入可选 `report` dict，则回填 `report['over_capacity'] = True`。**返回值类型不变**（见 C5），避免破坏 6 个调用点 |
| **C5** | 返回被删除路径列表；目录不存在返回 `[]`；单个 `unlink` 失败继续处理其余项 |
| **C6** | `keep_newest` 一律经 `max(1, ·)` 夹取（**下游不得绕过**） |
| **C7** | `backup_database` 的 `sha256` / `integrity` / `FileExistsError` / `source != destination` 语义全部保持 |

> **契约冻结后才允许并行。** 写测试的人不等实现完成，只依赖 C1–C7。

---

## 3. v1 被判否的三处（记录在案，防止复发）

| # | v1 的说法 | 实测结论 | 证据 |
|---|---|---|---|
| 1 | 「调用方全部经 `prune_backups` 委托，单点修复即可」 | **伪**。存在第 6 个完全绕过点 | `scripts/backfill_promo_detail_from_bi.py:136-141` 直接 `sqlite3.connect` + `source.backup(target)`，全文无 prune/retention 引用 |
| 2 | 「改动局限 3 文件，A1 全绿」 | **伪**。既有测试固化旧语义，冻结 C1 后必红 | `tests/test_backup_retention_enforcement.py:43-53`（`:43` keep=1 + protected=[新备份]、`:48`/`:52` 断言保留 2 份）；用参考 C1 实现实测 → `failures: 1`，`AssertionError: ... 'dashboard-2.db'`；改动前 2 passed |
| 3 | spec §5 T-A3「总数 = 4」 | **与 C1 自相矛盾** | C1 下 2 份 protected 已占满 `keep_newest=2`，总数必须为 **2**。T-A3 把待修行为固化成了验收断言 |

**另有两处 v1 遗漏（对抗审核发现）**：

- `scripts/import_data.py:305-306` 用 `pattern='dashboard_*.db'`，而磁盘上的 `dashboard-20261002-015552.db`（**连字符**）fnmatch 实测**不匹配** → 只裁自家命名空间。该路径是活体入口：`api/schedules_api.py:183-187` 定时任务处理器 → `import_excel_file`。
- `scripts/import_data.py:278` 缺 `max(1,·)` 夹取：`max_backups: 0` 实测 retention 路径得 `4`、import_data 路径得 `0` → **删光全部非 protected 备份**。

---

## 4. 批次与写域（契约已冻结，可并行）

| 任务 | 位置 | 改法 | owner | 写 scope |
|---|---|---|---|---|
| **T1** | `scripts/backup_retention.py:52-62` | 实现 C1–C6：protected 占用配额、字节计入容量、`over_capacity` 暴露 | writer-A | `scripts/backup_retention.py` |
| **T2** | `tests/test_backup_retention_enforcement.py:43-53` | **重写**断言为 C1/C2 语义（这是 v1 漏掉的破坏点，必须显式在写域） | writer-C | `tests/test_backup_retention_enforcement.py` |
| **T3** | `tests/test_backup_retention_semantics.py`（新增） | T-A2 / **T-A3 修正版** / T-A4 / T-A7 / T-A8 / T-A9 + 旧行为回归护栏 | writer-C | `tests/test_backup_retention_semantics.py` |
| **T4** | `scripts/import_data.py:275-278, 304-306` | keep 改走 `retention_settings()`（含夹取）、删除 `:304` 死赋值、`pattern` 统一 `*.db` | writer-B | `scripts/import_data.py` |
| **T5** | `scripts/backfill_promo_detail_from_bi.py:136-141` | 改为委托 `scripts/backup_database.backup_database()`，消除完全绕过点 | writer-B | `scripts/backfill_promo_detail_from_bi.py` |

**写域互斥检查**：A=`backup_retention.py`；B=`import_data.py` + `backfill_promo_detail_from_bi.py`；C=两个测试文件。**无重叠。**

**依赖**：全部只依赖冻结契约，**无 blocked_by**（契约先行就是为了免掉串行）。

### 测试用例清单（T3）

| 用例 | 构造 | 断言 |
|---|---|---|
| T-A2 | 5 份，`keep=4`，`protected=[最新]` | 剩余 **4** 份 |
| **T-A3（修正）** | 4 份，`keep=2`，`protected=[最新两份]` | 总数 = **2**，protected 全留（C1.1） |
| T-A4 | 若干小份 + 1 份超 cap | 超限项被裁（C3） |
| T-A7 | 单体 protected 超 cap | 保留 protected，`over_capacity=True`，不抛异常（C4） |
| T-A8 | C1.1 × C3 组合 | 终态明确、无异常 |
| T-A9 | `max_backups: 0` / 负值 | 夹取到 ≥ 1（C6） |
| T-A5 | 目录不存在 | 返回 `[]` |
| 回归护栏 | 固定「剔除 protected 再 keep」的旧行为 | 得到 5 份 → 证明新测试真的能抓到旧实现 |

---

## 5. 审核安排

| 任务 | 级别 | 审核者 | 硬性要求 |
|---|---|---|---|
| T1 契约实现 | **L3 独立** | verifier（未参与实现） | 必须**重新执行** `pytest`；独立构造 fixture 复现「5→4」；附复现命令与原始输出 |
| T2/T3 测试 | L2 交叉 | writer-A | 审「这些测试对旧实现真的会失败」——回归护栏用例是关键 |
| T4/T5 收口 | L2 交叉 | writer-A 或 writer-C | 核对是否真的消除了绕过点 |
| 终局 | **L3 + 主控** | verifier + 主控 | 主控在**合并后**最终代码上跑全量门禁 + 强化版 A6 |

**推荐审核者换模型/provider**，避免与实现者同源盲区。

---

## 6. 验证命令

```powershell
# 批次 1 + 2 定向
./.venv/Scripts/python.exe -m pytest tests/test_backup_retention_enforcement.py tests/test_backup_retention_semantics.py -q

# 全量回归（基线：912 passed）
./.venv/Scripts/python.exe -m pytest tests/ -q

# 一体化门禁（不要合并 stderr，否则 $ErrorActionPreference='Stop' 会中止）
Set-ExecutionPolicy -Scope Process Bypass -Force
& .\scripts\test_all.ps1                                  # 期望 TEST_ALL_OK

# A6 强化版：真实备份目录前后逐项一致（不是只比 Count）
Get-ChildItem data\backups -Force | Sort-Object Name |
  ForEach-Object { "{0}|{1}" -f $_.Name, $_.Length }      # 改动前存一份，改动后 diff
```

> A6 说明：仅比 `Count` 是弱断言（删一份再建一份仍是 5）。必须比对 **name + size 列表**。
> 另需明确：合并后**下一次真实备份**会把存量降到 4 份，这是预期行为，**不属于本轮范围**。

---

## 7. 风险与回滚

| 风险 | 缓解 |
|---|---|
| 裁剪语义写错会多删备份 | 全部验证在 `tempfile` fixture 上；A6 强化版比对 name+size |
| 既有测试被破坏（v1 漏项） | T2 显式在写域；A1 必须包含重写后的该文件 |
| `over_capacity` 引入新返回值破坏调用方 | 只**新增**字段，不改既有字段；由 verifier 逐个核对 6 个调用点 |
| 回滚不足 | 真正的回滚依赖 `data/backups/` 快照而非 `git revert`（代码回滚救不回被误删的 2.9GB 备份）；**执行前先把 name+size 快照落 `data/` 之外** |

---

## 8. 不做的事（已按对抗意见补全）

- 不删除、不移动 `data/backups/` 中任何现有文件（存量另行决定）
- 不修改 `config.yaml` 的 `max_backups` / `max_backup_total_gb`
- 不触碰 `data/dashboard.db`，不执行 `VACUUM`
- **不对齐 `scripts/run_daily_backup.ps1:72-96`** 的第二套「7 天日备 / 4 周周备」按龄删除逻辑（该计划任务默认 Disabled，属第二条删除权威，另开任务）
- **不统一备份目录多源**（`config.yaml` `backup_folder` / PS 侧 `TMALL_BACKUP_DIR` / `import_paimi_bi_daily.py:279` 与 `import_paimi_bi_overview.py:419` 硬编码 `ROOT/data/backups`）
- **不处理 `pattern` 盲区**：`*.db` 不匹配 `.db-wal` / `.db-shm` / `.bak` / `*.db.bak_*`，且 glob 不递归子目录。当前实测无此类逃逸产物，本轮只记录，不加断言
- 不对齐 `scripts/cleanup_backups.py:74` 的 `KEEP_NEWEST_BACKUPS`（留 2 份）——有意更激进的手动策略
- 不改动备份正确性语义（C7）

---

## 9. 待 Gate 2 确认

1. **范围**：是否按本 v2 的 T1–T5 + 1 名 verifier 执行（3 writer + 1 verifier）？
2. **C4 超限终态**：采用「保留 protected + 暴露 `over_capacity`、不抛异常」，可以吗？
3. **存量**：合并后首次真实备份会把 5 份降到 4 份——接受为预期行为吗？

---

## 10. L3 复验（V2）未关闭的观察 —— 显式记录，未静默放过

V2 结论为 **PASS**（`docs/BACKUP_RETENTION_REVIEW_20261004.md` 第 304 行起）。以下 4 条**不构成验收失败**，但作为已知限制留档：

| # | 严重度 | 内容 | 处置 |
|---|---|---|---|
| **F-06** | 低 | `tests/test_backup_retention_semantics.py:152` 的 T-A10 只 `assertTrue(captured.output)`，未断言 warning **文案**含「3 项 / 1200 字节」。若文案退化回 `[:keep]` 计数，该用例不会红（C4 本身仍被覆盖） | **本轮不改**。理由是改测试会让已通过的 V2 复验失效，须再开一轮复验；收益与成本不匹配。已留档 |
| **F-07** | 低 | `data/` 目录 mtime 两次瞬时变化（V1 17:22:52、V2 17:30:28）。逐文件采样证明**非**本轮测试与探针所为；同一工作目录存在**另一条并发工作流**（`services/source_resolution_service.py 17:27:02`、`services/period_context.py 17:28:00`、`tests/test_source_resolution.py 17:28:45`、`tests/test_period_reviews_api.py 17:29:28`），另有 15:13:53 起的常驻 `app.py`（pid 4156/7376，未杀未重启） | **Gate 3 判读前提**：全量门禁若失败，**不可直接归因于本轮备份轮转改动**，须先确认那条工作流的归属与状态 |
| **F-08** | 低 | 本文件章节标题原写「冻结契约 v2」 | ✅ 已改为 v2.1 |
| **F-09** | 低/不确定 | 删除失败（`unlink` 抛 `OSError`）的非 protected 文件不计入容量账本，故 `over_capacity` **不是**「磁盘是否超 cap」的可靠信号（实测：100B protected + 9000B 非 protected 删除失败、cap=1000 → `total_on_disk=9100`、`report={}`）。C4 前提「裁光全部非 protected」未成立，按字面**不算违约** | 留档；若日后需要「磁盘占用」信号，应另加独立统计而非复用 `over_capacity` |

**记录原则**：审核提出的每一条都必须有明确去向——修掉、或显式留档并说明理由。**不允许「报告中提过但没人处理」**。
