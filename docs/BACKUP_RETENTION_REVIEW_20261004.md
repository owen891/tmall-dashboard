# 备份轮转契约落地 —— L3 独立审核报告

> 审核者：`verifier`（L3 独立，**未参与 T1–T5 实现**；与 writer-a/b/c 不同源，模型亦不同）
> 日期：2026-10-04
> 被审对象：T1–T5 落地后的工作区（`git status` 中 17:16–17:20 修改的文件）
> 冻结契约：`docs/BACKUP_RETENTION_PLAN_20261004.md` 第 2 节 C1–C7
> 立场：**先设法证明它不满足验收标准**；本文所有结论均附复现命令与原始输出
> 约束遵守：写操作仅限本文件与 `.tmp/agent-reports/V1.md`；未修改任何实现/测试；未运行 `--apply`；未运行全量 `pytest tests/`；未触碰 `data/`（只读）；未杀进程

---

## 0. 开工前预判的三处最可能出错点

| # | 预判 | 结果 |
|---|---|---|
| **P1** | C2/C3 × C6 交互：数量虽对，但字节账本或 `max(1,·)` 夹取可能作用在错的变量上，`len(protected) >= keep` 分支可能算错 | **部分命中**。夹取与数量语义全对；但 `len(protected) > keep` 时字节账本漏计（见 **F-01**），另发现 C3 保留顺序歧义（**F-02**） |
| **P2** | T5：委托 `backup_database()` 可能与其真实返回类型/`source != destination` 不匹配；`FileExistsError → SystemExit` 会破坏重复 `--apply` | **命中**。返回类型处理无误（dict 正常打印）；但重复 `--apply` 由「静默覆盖」变为「硬失败」，且**零测试覆盖**（见 **F-03**） |
| **P3** | T4：`pattern='*.db'` 加宽后仍可能不匹配连字符命名；真实 `data/backups` 可能被该路径删除 | **部分命中**。加宽后 5 个真实文件全部命中（旧 pattern 一个都不命中）；真实目录未被写；但删除权威已跨命名空间扩大（**F-04**） |

---

## 结论

**结论：FAIL**

FAIL 的唯一硬性依据：**冻结契约 C4 未被完整实现**——当 `len(protected) > keep_newest` 且 protected 字节自身超过 `max_total_bytes` 时，函数既不记录 warning，也不回填 `report['over_capacity'] = True`，而 C4 明确要求二者（见 **F-01**，PROBE A 可复现）。
范围声明：第 1 节验收基线 A1–A4（5→4、C1.1、夹取、真实目录逐项一致）、7 项必做动作、以及 C1/C1.1/C2/C3(计数部分)/C5/C6/C7 **全部通过**；C4 仅在 `len(protected) > keep` 这一未被任何测试覆盖的分支上失效。当前 6 个调用点都只传 1 个 protected，故**生产影响为零**，但契约条款确实没落地。

---

## 逐条验收

### 一、方案 §1 验收基线

| # | 条目 | 判定 | 证据 |
|---|---|---|---|
| A1 | 裁剪后匹配份数（`max_backups: 4`）**≤ 4** | **PASS** | 独立 fixture 5 份 + `keep=4` + `protected=[最新]` → 剩 **4**。`CURRENT keep=4 protected=[b5] remaining=4 ['b2.db','b3.db','b4.db','b5.db'] removed=['b1.db']`；真实 `config.yaml:13 max_backups: 4` |
| A2 | `len(protected) >= keep_newest` → protected 全留，总数 = `len(protected)` | **PASS** | 4 份 + `keep=2` + `protected=[b4,b3]` → `remaining=2 ['b3.db','b4.db'] removed=['b1.db','b2.db']` |
| A3 | `max_backups ≤ 0` 夹取到 ≥ 1 | **PASS** | `keep=0` → `remaining=1 ['b5.db']`；`keep=-5` → `remaining=1 ['b5.db']`；`retention_settings()` 对临时 `config.yaml` 的 `max_backups: 0/-7` 亦夹取（T-A9 内置用例通过） |
| A4 | 真实 `data/backups/` **name+size 逐项一致** | **PASS** | 与 `.tmp/backups_baseline.txt`（lead 于 17:16:58 存的改动前快照）`Compare-Object` → **0 differences**；5 份 / 15,269,867,520 B（≈14.22 GiB）；目录 mtime 仍为 `2026-10-03 12:19:50` |
| A5 | 定向回归（本任务第 3 项动作） | **PASS** | `13 passed, 4 subtests passed in 0.24s` |
| A6 | Python 全量回归 912 passed / 一体化门禁 `TEST_ALL_OK` | **未验证** | 任务卡禁止我跑（主控 Gate 3 独占）。见 §5 |

### 二、任务卡 7 项必做动作

| # | 动作 | 判定 | 证据摘要 |
|---|---|---|---|
| 1 | 独立 fixture 复现「5 份 + keep=4 + protected=[最新] → 剩 4」 | **PASS** | `CURRENT remaining=4 ['b2.db','b3.db','b4.db','b5.db'] removed=['b1.db']` |
| 2 | 用**旧实现逻辑**跑同一 fixture → 应得 5 | **PASS**（且更强） | 未用测试里重打的 `legacy_prune_backups`，而是从 `git show HEAD:scripts/backup_retention.py` 载入**真实旧实现**：`OLD remaining=5 ['b1.db','b2.db','b3.db','b4.db','b5.db'] removed=[]` |
| 3 | 重跑定向 pytest | **PASS** | `13 passed, 4 subtests passed in 0.24s`（连续两次一致） |
| 4 | 只读复核 `data/backups` **name+size 逐项** | **PASS** | `baseline lines: 5 ; current lines: 5` / `IDENTICAL: name+size 逐项一致 (0 differences)` |
| 5 | 逐个核对 6 个 `prune_backups` 调用点未破坏 | **PASS** | 全部关键字传参；`report` 追加在签名**末尾**（`(backup_dir, keep_newest=4, max_total_bytes=21474836480, pattern='*.db', protected=(), report=None)`），无位置参数错位；返回类型仍为 `list` |
| 6 | 检查 T4/T5 是否真的消除绕过点 | **PASS** | 全仓 `\.backup\(` 只剩 5 处：`backup_database.py:44`、`import_data.py:286`、`import_paimi_bi_daily.py:285`、`import_paimi_bi_overview.py:264`（**各自紧随 prune**）+ `backfill_promo_detail_from_bi.py:141`（**仅注释**）。`VACUUM INTO` 全仓 0 处 |
| 7 | `over_capacity` 是否破坏调用方 | **PASS（调用方兼容）/ FAIL（C4 语义）** | 兼容：`report` 默认 `None`，无调用点传它，返回类型仍 `list`；但 C4 语义在 `len(protected) > keep` 时失效 → **F-01** |

### 三、冻结契约 C1–C7 逐条

| 条款 | 判定 | 证据 |
|---|---|---|
| C1（keep = 匹配总数上限，protected 占用配额） | **PASS** | A1 fixture：4 份；旧实现 5 份 |
| C1.1（`len(protected) >= keep` → 非 protected 全裁，总数 = `len(protected)`） | **PASS** | `keep=2, protected=[b4,b3]` → 剩 2；`keep=2, protected=[p1,p2,p3]` → 剩 **3**（protected 全留，非 protected 全裁） |
| C2（非 protected 保留数 = `max(0, keep - len(protected))`） | **PASS** | `keep=4, protected=[b5]` → 恰保留 3 份非 protected（b2,b3,b4） |
| C3（protected 字节计入 cap；余量按新的在前） | **计数/容量 PASS，顺序语义有歧义** | 容量：PROBE A 中 3×400B protected 未再放行任何非 protected。顺序：见 **F-02** |
| C4（超限终态：不抛异常 + warning + `report['over_capacity']`） | **FAIL** | **PROBE A**：`kept=['p1.db','p2.db','p3.db']`、`actual retained bytes=1200 cap=1000`、`report={}`（应为 `{'over_capacity': True}` 且有 warning）。见 **F-01** |
| C5（返回删除列表；目录不存在 `[]`；单个 unlink 失败继续） | **PASS** | `missing dir -> []`；`removed type=list`；`test_c5_unlink_failure_is_skipped_and_processing_continues` 通过 |
| C6（`keep_newest` 一律 `max(1,·)` 夹取，下游不得绕过） | **PASS** | `backup_retention.py:113` 与 `:55` 双重夹取；`import_data.py:307` 已改走 `retention_settings()`；`keep=0/-5` 实测剩 1 |
| C7（`backup_database` 的 sha256/integrity/FileExistsError/`source != destination` 全保持） | **PASS（按构造）** | `scripts/backup_database.py` **不在** `git status` 修改列表中 → 文件逐字节未变，语义不可能被本轮改动破坏；`:35-39` 四条语义读毕仍在 |

### 四、T2/T3 是否「真能抓到旧行为」

**PASS（强证据）**：把 `git HEAD` 的真实旧实现注入 `scripts.backup_retention` 的 `prune_backups`/`retention_settings`，再跑这两个测试文件：

```
>>> tests/test_backup_retention_enforcement.py: run=3 failures=2 errors=0
>>> tests/test_backup_retention_semantics.py:  run=10 failures=4 errors=2
=== TOTAL failures+errors against OLD impl: 8 ===
VERDICT: tests DO discriminate old behaviour
```

断言差异例如：`AssertionError: Lists differ: ['b1.db','b2.db','b3.db','b4.db','b5.db'] != ['b2.db','b3.db','b4.db','b5.db']`；`AssertionError: 5 != 4`。新实现下同一批测试 `13 passed`。**测试非空转。**

---

## 发现

### F-01 [高] `scripts/backup_retention.py:119`（配合 `:124,142-149`）—— `len(protected) > keep_newest` 时 C4 的 `over_capacity` 漏报，warning 也不触发

- **描述**：第 119 行 `protected_items = [item for item in matching if item.name in protected_names][:keep]` 把 protected 列表**截断到 `keep`**。第 124 行 `kept_bytes = sum(_size(item) for item in protected_items)` 因此**只统计前 `keep` 个 protected 的字节**。但第 142 行判超限用的是 `kept_bytes`。当 protected 项数 > `keep_newest` 时，超出部分**仍然全部保留在磁盘上**（它们在 `protected_names` 里，永不出现在 `fresh_candidates` 中，故永不删除），其字节却**未计入账本** → 实际占用体积超过 `max_total_bytes`，`over_capacity` 却为假、warning 不打印。
- **契约依据**：C4 要求「裁光全部非 protected 后总字节仍 > `max_total_bytes`（protected 自身超限）→ 保留全部 protected、记录 warning、`report['over_capacity'] = True`」。
- **证据（PROBE A：`keep=2`、`cap=1000`、`protected=[p1,p2,p3]` 各 400B）**：
```
=== PROBE A: len(protected)=3 > keep=2, protected bytes 3*400=1200 > cap=1000 ===
kept=['p1.db', 'p2.db', 'p3.db']
actual retained bytes=1200  cap=1000  -> genuinely over cap: True
report={}  (C4 requires over_capacity=True)
removed=['s1.db']
```
- **复现命令**：见 §4 附录 PROBE A（`tempfile` fixture，只读 `data/`）。
- **影响面**：删除行为仍正确（总数 = `len(protected)`，非 protected 全裁，符合 C1.1），**仅**超限诊断/告警缺失。现有 6 个调用点都只传 1 个 protected → **当前生产影响为零**；但契约 C1.1 显式定义了 `len(protected) >= keep_newest`，其 `>` 分支无任何测试覆盖（T-A3 只测 `==`）。
- **建议修复（一行）**：账本改为统计**全部** protected：
  `kept_bytes = sum(_size(item) for item in matching if item.name in protected_names)`，
  或保留 `protected_items` 用于计数、另用全量 protected 计算 `kept_bytes`；并补一条 `len(protected) > keep` 且 protected 超 cap 的用例。

### F-02 [中] `scripts/backup_retention.py:127-139` —— C3「新的在前」的保留顺序在契约中歧义，实现会「删较新的、留较旧的」

- **描述**：循环遇到超容量的项时 `continue`（不 `break`），继续用剩余 `slots` 保留更旧的**小**文件。因此当最新的一份备份体积过大时，它会被删除，而比它更旧的、体积更小的备份被保留。C3 原文「扣除 protected 后，剩余配额按「新的在前」继续保留非 protected」未说明遇到容量不足时是**停止**还是**跳过继续**。
- **证据（C3 ORDERING PROBE：`keep=4`、`cap=1000`，s1/s2/s3=100B(最新), big=900B(较新), s5=100B(最旧)）**：
```
C3 kept=['s1.db', 's2.db', 's3.db', 's5.db'] removed=['big.db']
C3 NOTE: big.db(mtime rank2,NEWER) deleted while s5.db(rank1,OLDER) kept
```
- **判定**：实现与 T-A4 断言（`tests/test_backup_retention_semantics.py:85-98`：`removed == ['big.db']`、`kept` 含 `s5.db`）**一致**，故不构成验收失败；风险在于「最新备份因体积大而被删、更旧的保留」这一终态未在契约文字中被明确批准。建议在 C3 补一句「容量不足时跳过该项并继续尝试更旧的项」以冻结语义（若采纳，则当前实现无需改动）。

### F-03 [中] `scripts/backfill_promo_detail_from_bi.py:143-146` —— 重复 `--apply` 同一 `--backup-destination` 由「静默覆盖」变为「硬失败」，且该路径**零测试覆盖**

- **描述**：T5 将备份委托给 `backup_database()`（`:144`），并把 `FileExistsError` 翻译为 `SystemExit`（`:145-146`）。旧代码 `backup_path.parent.mkdir()` + `sqlite3.connect(backup_path)` + `source.backup(target)` 会**静默覆盖**已存在的目标。因此：同一目的地重复 `--apply`，旧行为=覆盖后继续；新行为=报错退出（**在写任何数据之前**）。
- **证据（S1 模拟，`tempfile`，目标为「一份合法 SQLite 备份」的真实场景）**：
```
OLD  same --backup-destination re-apply: SUCCEEDED silently; dest size=8192 tables=['t'] (old content REPLACED)
NEW  same --backup-destination re-apply: FileExistsError(...\new-dest.db)
NEW  dest untouched: size 8192 -> 8192
OLD  non-DB pre-existing dest: DatabaseError: file is not a database (uncaught by HEAD code)
```
- **测试覆盖**：`NO MATCH: zero tests reference backfill_promo_detail_from_bi`（`git grep -c --untracked -e 'promo_detail_from_bi' -- tests` 无输出）。该脚本的 `--backup-destination`/`--apply`/`SystemExit` 新路径**完全没有测试**。
- **独立结论（S1）**：**可接受，但须补修订**。
  - 破坏的既有约定：`--apply` 携带同一 `--backup-destination` 的可重跑性（脚本 docstring 给出的用法示例正是这条）。这是 CLI 行为变更，未在 docstring/`--help` 中声明。
  - 与 C7 是否冲突：**不冲突**。C7 约束的是 `backup_database` 内部的 `FileExistsError` 语义，而该文件本轮**逐字节未改**，语义完整保留（见 C7 行）。变化发生在调用方。
  - 若保留旧覆盖语义会与 C7 的哪一条冲突：分两种实现路径——(a) 若为兼容覆盖而让 `backup_database` 吞掉 `FileExistsError`/自动改名，则**直接违反 C7 的 `FileExistsError` 条款**；(b) 若在调用方捕获 `FileExistsError` 后自行 `sqlite3.connect + backup` 覆盖，则会**重新造出一个不经 `prune_backups` 的备份制造点**，与 C6「下游不得绕过」及 T5「消除最后一个绕过点」的目标冲突。故新行为是唯一与契约自洽的选择。
  - 附带改善：旧代码遇到「目标存在但不是合法 SQLite 文件」时抛**未捕获**的 `sqlite3.DatabaseError`（原始输出第三行）；新代码给出明确的 `SystemExit` 文案。
- **建议**：补一条测试（同一 `--backup-destination` 二次 `--apply` → 断言 `SystemExit` 且目标文件未被改写、DB 未被写入），并在 docstring/`--help` 注明「目标必须不存在」。

### F-04 [中] `scripts/import_data.py:305-309` —— `pattern` 由 `dashboard_*.db` 加宽到 `*.db`，删除权威从单一命名空间扩到整个备份目录

- **描述**：`import_data.backup_database()` 现在对 `backup_folder` 内**所有** `*.db` 施加同一 keep=4/20GiB 策略，包括 `aggregate-store-daily-*.db`（由 `scripts/aggregate_store_daily.py` 产生）与 `dashboard-*.db`。该扩大是方案 §4 T4 明确要求的，不属越界；但它是本轮**实际删除面**的扩大，值得书面记录。
- **证据（PROBE B，旧 pattern 前提成立）**：
```
  aggregate-store-daily-20261002-095229.db           old_pattern=dashboard_*.db  match=False   new_pattern='*.db' match=True
  aggregate-store-daily-20261002-1857.db             old_pattern=dashboard_*.db  match=False   new_pattern='*.db' match=True
  aggregate-store-daily-20261003-121846.db           old_pattern=dashboard_*.db  match=False   new_pattern='*.db' match=True
  aggregate-store-daily-20261003-121917.db           old_pattern=dashboard_*.db  match=False   new_pattern='*.db' match=True
  dashboard-20261002-015552.db                       old_pattern=dashboard_*.db  match=False   new_pattern='*.db' match=True
```
  即：改前该路径对真实目录里 5 个文件**一个都不裁剪**（fnmatch 全 False），改后全部纳入。参数已改走 `retention_settings()`（`:307`），`max_backups: 0` 不再删光（C6）。本轮**未发生**任何真实写入（见 S2/A4）。
- **判定**：契约内、已声明，非验收失败项。

### F-05 [低] 契约 C1.1 字面与实现在「protected 项不存在/不匹配 pattern」时的分歧

- **描述**：C1.1 字面为「若 `len(protected) >= keep_newest`……总数 = `len(protected)`」。实现只把**实际匹配 pattern 且存在**的项计入 `protected_items`。因此当传入的 protected 路径不存在时，实现会转而保留 `keep` 份非 protected，而非 C1.1 字面的「非 protected 全裁」。
- **判定**：实现比字面**更安全、更符合直觉**；分歧只在退化输入下出现，且 6 个调用点传入的都是刚创建成功的备份路径。建议契约为「protected 指**实际存在的匹配项**」加一句限定，无需改代码。

---

## 三项专项核查

### S1 — T5 的行为变化是否可接受
见 **F-03**。结论：**可接受（唯一与 C1/C6/C7 自洽的选择），但须补测试与文档**；破坏的是「同一 `--backup-destination` 可重复 `--apply`」的可重跑约定；与 C7 不冲突（`backup_database` 未被改动）；若强行保留覆盖语义，要么违反 C7 的 `FileExistsError` 条款，要么与 C6「下游不得绕过」冲突。该路径**零测试覆盖**。

### S2 — `data/dashboard.db` 的写入者是谁
**只读核查结论：本轮 T1–T5 的改动不可能写入 `data/dashboard.db`；但 `data/` 目录在审核窗口内出现过一次未归属的目录项变更（17:22:52），如实报告。**

证据：
1. 常驻进程（**未杀、未重启**）：
```
ProcessId  CreationDate        CommandLine
     4156  2026/10/4 15:13:53  E:\www\tmall-dashboard\.venv\Scripts\python.exe app.py
     7376  2026/10/4 15:13:53  E:\www\tmall-dashboard\.venv\Scripts\python.exe app.py
```
   全程仅此两个 `python.exe`；无其它 python 进程。
2. `data/dashboard.db`：`3085537280` 字节，mtime `2026-10-04 17:20:20`。该 mtime 在**本审核会话首次工具调用（17:22）之前**，且在整个审核期间（含两次定向 pytest、模块导入、25 秒静置）**三次采样均未变化**：
```
before: data/=17:22:52 dashboard.db=17:20:20
after : data/=17:22:52 dashboard.db=17:20:20
changed: data/=False dashboard.db=False
```
   全 `data/` 树中 17:00 之后有 mtime 的**只有** `dashboard.db` 一个文件；无 `-wal/-shm/-journal` 残留。
3. 改动面排除写入者：`scripts/backup_retention.py` **不 import sqlite3**（仅 `logging`/`pathlib`）；`scripts/import_data.py` 的改动全部位于其局部 `backup_database()` 内，只读源库、写给 `backup_dir`；`scripts/backfill_promo_detail_from_bi.py` 的改动只在 `args.apply` 为真时执行（`--apply` 本轮未运行）。两个测试文件全部使用 `tempfile.TemporaryDirectory`。
4. `data/backups` 与新文件：`data/backups` 目录 mtime 仍为 `2026-10-03 12:19:50`，逐项 0 差异 → 无任何真实备份/裁剪发生。

**未归属项**：`data/` 目录 mtime = `2026-10-04 17:22:52`，而其中无任何文件 mtime 为 17:22:52（瞬时「目录项创建+删除」特征，符合一次回滚的 SQLite journal 或临时文件的生灭），与「常驻 `app.py` 的一次未提交事务」一致。我**无法**在只读、不杀进程、无句柄工具的前提下把它归因到具体进程。已用两次前后对照证明**不是**我的任何命令（含 pytest、模块导入）造成的。**仅报告发现。**

### S3 — 写域合规
**PASS：本轮实现/测试改动全部落在声明写域内。** 以 mtime 切分（本轮窗口 = 17:16–17:20）：

| 分类 | 文件 | mtime | 判定 |
|---|---|---|---|
| 本轮写域内 - 实现 | `scripts/backup_retention.py` | 17:17:50 | ✅ |
| | `scripts/import_data.py` | 17:17:49 | ✅ |
| | `scripts/backfill_promo_detail_from_bi.py` | 17:19:28 | ✅ |
| 本轮写域内 - 测试 | `tests/test_backup_retention_enforcement.py` | 17:17:05 | ✅ |
| | `tests/test_backup_retention_semantics.py`（新增） | 17:17:46 | ✅ |
| 允许的文档 | `docs/BACKUP_RETENTION_SPEC_20261004.md` | 17:16:03 | ✅（L0） |
| | `docs/BACKUP_RETENTION_PLAN_20261004.md` | 17:16:35 | ✅（冻结契约） |
| 编排产物（非实现） | `docs/AGENT_TEAM_PLAYBOOK.md` | 16:58:19 | ⚠️ 不在 `BACKUP_RETENTION_*` 通配内，但属 M0 编排文档，非本轮实现文件，请主控归类 |
| | `.tmp/backups_baseline.txt` | 17:16:58 | 快照（A4 基线，正常） |
| | `.tmp/agent-reports/`、`.tmp/writer-a/`、`.tmp/writer-b/` | 17:17–17:21 | writer 脚手架（非实现文件） |
| **本会话开始前就存在的未提交修改（不属本轮）** | `frontend/ui_demo/...`（11 个文件）、`scripts/audit_dialog_dismiss.cjs`、`scripts/build_ui_audit_report.py`、`scripts/shot_period_review_*.js`、`scripts/smoke_period_review_tabs.js`、`services/page_capability_service.py`、`services/period_context.py`、`services/period_matrix.py`、`services/period_parsing.py`、`tests/test_period_reviews_api.py` | 12:16:48–16:40:34 | 计入「存量」，**未**算作越界，如实列出供主控区分 |
| 本会话前既有目录 | `.agents/`（16:13:02）、`.tmp_audit/`（15:17:14） | — | 存量 |

结论：**未发现任何越界写入**；`scripts/backup_database.py` 未出现在 `git status` 中（C7 按构造成立）。

---

## 未验证 / 不确定

1. **A6：全量 `pytest tests/ -q`（基线 912 passed）与 `scripts/test_all.ps1`（`TEST_ALL_OK`）** —— 任务卡禁止我执行，由主控在 Gate 3 独占。我无法确认全量回归无新增失败；本报告只覆盖两个定向文件（13 passed）。
2. **`data/` 目录 mtime `17:22:52` 的归属**（见 S2「未归属项」）—— 无句柄工具、且被禁止动进程，无法归因。已排除我的全部命令与 T1–T5 改动面；不能排除常驻 `app.py`。
3. **`len(protected) > keep_newest` 分支在生产是否会出现** —— 现有 6 个调用点都只传 1 项，故 F-01 当前无生产影响；但我无法验证未来新增调用方是否会传多项。
4. **审核者独立性声明** —— 我是 `verifier`（L3），未参与 T1–T5 任何实现或测试编写，与 writer-a/b/c 不同源、不同模型；所有结论均基于本报告附带的复现命令与原始输出，未采用 T1–T5.md 的自述作为依据（仅知悉其存在）。
5. **透明披露（我自己的脚手架瑕疵，非被审对象行为）**：S1 模拟脚本因我未关闭抛出 `DatabaseError` 后的 sqlite 连接，导致 `TemporaryDirectory.cleanup()` 抛 `PermissionError`，在 `%TEMP%` 留下一个约 8KB 的临时目录 `v1-s1-*`；输出中该异常出现在结论行**之后**，不影响上述任何结论。注旧实现注入探针的 shell 退出码为 1（`TextTestRunner` 后脚本未显式 `sys.exit(0)` / 清理路径所致），输出完整、结论有效。

---

## 附录：复现命令

### A. 独立 fixture（动作 1/2）+ 条款探针
```powershell
# 用 python -（stdin，不落盘）；fixture 一律 tempfile；旧实现取自 git show HEAD
@'
... (见 §4 正文引用的完整脚本) ...
'@ | .\.venv\Scripts\python.exe -
```
关键原始输出：
```
CURRENT keep=4 protected=[b5] remaining=4 ['b2.db','b3.db','b4.db','b5.db'] removed=['b1.db']
OLD     keep=4 protected=[b5] remaining=5 ['b1.db','b2.db','b3.db','b4.db','b5.db'] removed=[]
C1.1 remaining=2 ['b3.db','b4.db'] removed=['b1.db','b2.db']
C6 keep=0 remaining=1 ['b5.db']   /  C6 keep=-5 remaining=1 ['b5.db']
C4 remaining=1 ['b5.db'] removed=['b1.db','b2.db','b3.db','b4.db'] report={'over_capacity': True}
C3 kept=['s1.db','s2.db','s3.db','s5.db'] removed=['big.db']
removed type=list ; missing dir -> []
signature: (backup_dir, keep_newest=4, max_total_bytes=21474836480, pattern='*.db', protected=(), report=None)
```
> 注：`git show HEAD:...` 必须按 UTF-8 解码（源码含中文注释）；默认 GBK 会 `UnicodeDecodeError`。

### B. PROBE A（F-01 复现）
```python
# keep=2, cap=1000, protected=[p1,p2,p3] 各 400B, s1=50B
removed = prune_backups(d, keep_newest=2, max_total_bytes=1000,
                        protected=[p1, p2, p3], report=rep)
```
```
kept=['p1.db','p2.db','p3.db']
actual retained bytes=1200  cap=1000  -> genuinely over cap: True
report={}  (C4 requires over_capacity=True)
removed=['s1.db']
```

### C. PROBE B（F-04 前提）
```python
fnmatch.fnmatch('dashboard-20261002-015552.db', 'dashboard_*.db')  # False
fnmatch.fnmatch('dashboard-20261002-015552.db', '*.db')            # True
```

### D. 定向 pytest（动作 3，跑两次一致）
```powershell
& .\.venv\Scripts\python.exe -m pytest tests/test_backup_retention_enforcement.py tests/test_backup_retention_semantics.py -q
# 13 passed, 4 subtests passed in 0.24s
```

### E. 旧实现注入（证明测试非空转）
```
>>> tests/test_backup_retention_enforcement.py: run=3  failures=2 errors=0
>>> tests/test_backup_retention_semantics.py:  run=10 failures=4 errors=2
=== TOTAL failures+errors against OLD impl: 8 ===
VERDICT: tests DO discriminate old behaviour
```

### F. 真实目录逐项复核（动作 4，只读）
```powershell
$base = Get-Content .tmp\backups_baseline.txt
$cur  = Get-ChildItem data\backups -Force | Sort-Object Name | ForEach-Object { "{0}|{1}" -f $_.Name,$_.Length }
Compare-Object $base $cur     # 无输出 = 0 differences
Get-Item data\backups -Force | Select-Object LastWriteTime   # 2026/10/3 12:19:50
```

### G. 绕过点全仓 grep（动作 6）
```powershell
git grep -n --untracked -e '\.backup(' -e 'VACUUM INTO' -- '*.py'
# scripts/backfill_promo_detail_from_bi.py:141  (仅注释)
# scripts/backup_database.py:44                 -> :70 prune
# scripts/import_data.py:286                    -> :308 prune
# scripts/import_paimi_bi_daily.py:285          -> :291 prune
# scripts/import_paimi_bi_overview.py:264       -> :270 prune
```

### H. S2 进程与库文件（只读，未杀进程）
```powershell
Get-CimInstance Win32_Process -Filter "Name='python.exe'" | Select ProcessId,CreationDate,CommandLine
Get-ChildItem data -Force -Filter 'dashboard.db*' | Select Name,Length,LastWriteTime
```

---

## 给主控的可执行建议

1. **必改（F-01，一行）**：`backup_retention.py:124` 的 `kept_bytes` 改为统计**全部** protected 匹配项，并补 `len(protected) > keep` + protected 超 cap 的用例后再判定 C4 PASS。修完后我可复跑 PROBE A 复核。
2. **必补（F-03）**：为 `backfill_promo_detail_from_bi.py` 的「同一 `--backup-destination` 二次 `--apply`」补一条测试（断言 `SystemExit` + 目标未被改写），并在 `--help`/docstring 声明「目标必须不存在」。语义变更本身保留。
3. **建议契约补字（F-02 / F-05）**：C3 明确「容量不足时跳过并继续尝试更旧项」；C1.1 明确 protected 指「实际存在的匹配项」。二者均为文字澄清，无需改实现。
4. **Gate 3 请把 A6/H 两项纳入**：全量 `pytest tests/ -q`、`scripts/test_all.ps1`、以及**合并后**强化版 A6（name+size 逐项）。我这份报告 A4 已证明**审核期间**真实目录 0 变化，但「合并后首次真实备份把 5 份降到 4 份」属预期，请勿误判为回归。

---
---

# V2 复验章节（第二次审核，2026-10-04）

> 审核者：同上（`verifier`，L3 独立，未参与 T6/T7/T8 实现；与 writer-a/b/c 不同源）
> 触发：V1 结论 **FAIL**，唯一硬性依据 F-01 已由 T6 返工
> 复验对象：T6（`scripts/backup_retention.py`）、T7（`tests/test_backup_retention_semantics.py` + 新增 `tests/test_backfill_promo_backup_contract.py`）、T8（`scripts/backfill_promo_detail_from_bi.py` 文案）、Lead（契约 v2.1）
> 立场不变：**证明它仍未满足验收标准**；未找到任何未满足的契约条款，故本轮判 PASS

## V2-0 复验前预判的三处

| # | 预判 | 结果 |
|---|---|---|
| **V2-P1** | T6 可能只改了字节账本，而 warning **文案**仍用 `[:keep]` 截断后的计数（报 2 项 / 1200 字节，自相矛盾） | **未命中**。`len(protected_items)` 与账本同为**全部** protected → 实测 warning 报 `3 项、1200 字节` |
| **V2-P2** | T-A10/T-A11 可能不具区分度，或「未修复实现」注入后 T-A10 仍绿 | **未命中**。注入未修复账本后 T-A10 **RED**（`no logs of level WARNING or higher triggered`）；T-A11 双向均绿（符合其「防过度告警」定位） |
| **V2-P3** | T8 可能夹带可执行改动；另发现 `data/` 目录 mtime 再次瞬时变化（17:30:28） | **未命中**。新增可执行语句 **7 行与 V1 已审 T5 集合逐一相同**，无线程外逻辑；`data/` 变化已证明非本轮三个测试文件所为（见 F-07） |

## V2 结论

**结论：PASS**

理由：任务卡 8 项复验要求全部通过；**未发现任何仍未满足的冻结契约条款**（C1–C7 逐条复核见下）。V1 的 F-01（C4）已实证修复，F-02/F-03/F-05 已按 v2.1 契约与测试关闭，F-04 未再变动。剩余三项为**低**severity 的测试严格性 / 文档 / 归因类观察（F-06–F-08）与一项契约范围外的记账边界（F-09），均不构成验收失败。

## V2 逐条复验

| # | 要求 | 判定 | 证据（原始输出） |
|---|---|---|---|
| V2-1 | **PROBE A**：`keep=2 cap=1000 protected=[p1,p2,p3]各400B` → `over_capacity=True` + warning，文案报全部 3 项 / 1200 字节 | **PASS** | `kept=['p1.db','p2.db','p3.db'] removed=['s1.db','s2.db']` / `report={'over_capacity': True}` / warning 文本含 `3 项` 与 `1200 字节`（断言 `-> True`） |
| V2-2 | **反证**：protected ≤ cap → 不报 `over_capacity`、不打 warning | **PASS** | 100B×3（总 300B ≤ 1000）：`report={}`、`warning_text=''`、`ASSERT NOT over_capacity -> True`、`ASSERT NO warning -> True`；另按任务卡字面 **300B×3（总 900B ≤ 1000）** 复测：`report={} warning=''` |
| V2-3 | **回归**：5 份+keep4+protected[最新] → 4；4 份+keep2+protected[最新两份] → 2（C1.1 未被 T6 破坏） | **PASS** | `kept=['b2.db','b3.db','b4.db','b5.db'] removed=['b1.db']`；`kept=['b3.db','b4.db'] removed=['b1.db','b2.db']` |
| V2-4 | 重跑 3 个测试文件 | **PASS** | `17 passed, 4 subtests passed in 1.03s`（= enforcement 3 + semantics 12 + backfill 2） |
| V2-5 | **T-A10 非空转**：注入未修复实现（账本只算 `[:keep]`）→ T-A10 必须转红 | **PASS** | 注入 `kept_bytes = sum(_size(item) for item in quota_protected)` 后：`>>> test_ta10_... -> RED (expected)`，`AssertionError: no logs of level WARNING or higher triggered on scripts.backup_retention` |
| V2-6 | 重跑 V1 的 A1–A4 | **PASS** | A1 见 V2-3；A2 = C1.1（4→2）见 V2-3，另 `5 份 keep=2 protected=[最新]` → `kept=['b4.db','b5.db']`（C2 恰 1 份非 protected）；A3 夹取 `keep=0 → kept=['b3.db']`、`keep=-5 → kept=['b3.db']`；A4 见下 |
| V2-6b | A4：真实 `data/backups` **name+size 逐项** vs `.tmp/backups_baseline.txt` | **PASS** | `baseline=5 current=5` / `IDENTICAL: name+size 逐项一致 (0 differences)`；目录 mtime 仍 `2026-10-03 12:19:50`；`dashboard.db` mtime 仍 `2026-10-04 17:20:20`、size `3085537280` |
| V2-7 | 复核 F-02 / F-05 的 v2.1 契约澄清与实现一致 | **PASS** | 见下「契约 v2.1 复核」 |
| V2-8 | 复核 F-03：T8 **只**改文案（无可执行逻辑变化） | **PASS** | 见下「T8 文案复核」 |

### 契约 v2.1 复核（要求 7）

| 条款（v2.1 新增文字） | 实现对应 | 判定 |
|---|---|---|
| C1.1：「protected 指**实际存在且匹配 `pattern`** 的项（不存在 / 不匹配的传入路径不占配额）」 | `backup_retention.py:118,125`：`protected_items` 由 `directory.glob(pattern)` ∩ `is_file()` ∩ `protected_names` 产生 | **一致 PASS**（关闭 F-05） |
| C3：「**全部** protected 项的字节计入 `max_total_bytes`（不得因数量配额而漏计）」 | `:125` 不再截断；`:131 kept_bytes = sum(_size(item) for item in protected_items)`；`:126 quota_protected = protected_items[:keep]` 仅用于 slots | **一致 PASS**（关闭 F-01） |
| C3：「遇到单项超出剩余容量时：**跳过该项并继续尝试更旧的项，不中断**」 | `:134-140` 循环 `continue`（非 `break`） | **一致 PASS**（关闭 F-02）。实测 `kept=['s1.db','s2.db','s3.db','s5.db'] removed=['big.db']` |
| C1.1 × C2 计数：`slots = max(0, keep - len(quota_protected))` | `:133` | 与 C2 `max(0, keep - len(protected))` 等价（`len(protected) > keep` 时两者同为 0）**PASS** |

> 文档 nit（**F-08，低**）：`docs/BACKUP_RETENTION_PLAN_20261004.md:34` 标题仍为「## 2. 冻结契约 v2」，未随本次 v2.1 澄清更新版本标识；条文内容已更新（C1.1/C3）。不影响语义。

### T8 文案复核（要求 8）—— 逐行 token 分类

方法：`git diff -U0` 取新增/删除行号，再用 `tokenize` 判定该行所有记号是否 ⊆ {COMMENT, STRING}（纯文本）还是含代码记号。

```
=== V2 diff vs HEAD: added=29 removed=10 ===
added total=29  pure-text=20  code=9
--- added CODE lines ---
  +45: import json
  +119: help='Required with --apply: SQLite backup path for this run. '
  +123: 'path for every run.')
  +150: backup_report = None
  +158: from scripts.backup_database import backup_database
  +160: backup_report = backup_database(db_path, backup_path)
  +161: except FileExistsError:
  +162: raise SystemExit(f'备份目标已存在，请改用新的 --backup-destination: {backup_path}')
  +164: print('  备份报告: ' + json.dumps(backup_report, ensure_ascii=False, default=str), flush=True)
--- added pure-text line numbers ---
  [27,28,29,30,31,32,33,34,35,36,37,38,39,40, 120,121,122, 155,156,157]
```

判定：
- **新增可执行语句 7 行**（`+45, +150, +158, +160, +161, +162, +164`）与我在 **V1 报告 F-03 证据中逐字引用的 T5 变更集合完全相同**（`import json`、`backup_report = None`、委托 import、`backup_report = backup_database(...)`、`except FileExistsError:`、`raise SystemExit(...)`、`print('  备份报告: ...')`）。
- `+119` / `+123` 是 `--help` 字符串字面量的**边界行**（同行含 `help=` / `)` 记号故被判为 code），其内容变化属文案。
- 其余 **20 行**（模块 docstring `27–40`、`--help` 字符串内部 `120–122`、`#` 注释 `155–157`）为纯文本。
- 删除行 10 行中 7 行为旧备份块（`mkdir`/`sqlite3.connect`×2/`source.backup`/`finally`/`close`×2，即 V1 已审删除集），3 行为旧用法文案。

⇒ **T8 未引入任何超出 V1 已审集合的可执行变化：PASS**（关闭 F-03）。文案质量：新增 docstring 明确「目标必须不存在 / 不覆盖既有快照 / 失败发生在写库之前」，与 `--help` 一致。

### 新增测试复核（T7）

- `tests/test_backup_retention_semantics.py`：**T-A10** `:132-152`（3×400B > cap → protected 全留、非 protected 全裁、`over_capacity=True`、`assertLogs` WARNING）；**T-A11** `:154-172`（3×100B ≤ cap → 不报、`assertNoLogs`）。文件由 251 行增至 298 行，**T-A2/T-A3/T-A4/T-A7/T-A8 断言逐字未变**（我已比对 V2 读数与 V1 记录），非弱化式改动。
- `tests/test_backfill_promo_backup_contract.py`（新，146 行）：**T-B1** `:110-130`（同一目的地二次 `--apply` → `SystemExit`；目标文件 size+sha256 前后一致；DB size+sha256 与行值均不变）；**T-B2** `:132-142`（`--apply` 缺目的地 → `SystemExit`，无产物、未落库）。全部 fixture 走 `tempfile`，并以 `--db` 指向临时库；`data/` 零触碰（见 F-07 的逐文件采样）。这条测试**直接补上了 V1 F-03 指出的零覆盖路径**。

## V2 发现

### F-06 [低] `tests/test_backup_retention_semantics.py:152` —— T-A10 只断言「有 warning」，未断言 warning 文案的项数/字节数
- 描述：`self.assertTrue(captured.output, 'C4 超限必须记录 warning')` 仅校验有日志。若日后 warning 文案退化为「protected 共 2 项、800 字节」（即 `[:keep]` 截断复发到文案层），该断言不会变红。
- 证据：V2-1 中我独立验证了文案确实为 `3 项、1200 字节`（`ASSERT warning says 3 项 & 1200 字节 -> True`），但该文本约束**只存在于我的探针**，测试本体没有。
- 建议（非阻塞）：`assertIn('3 项', captured.output[0])` 与 `assertIn('1200 字节', ...)`。

### F-07 [低] `data/` 目录 mtime 在审核窗口内两次瞬时变化（V1 `17:22:52`、V2 `17:30:28`）——已排除本轮测试与我的探针；**同一工作目录存在另一条并发工作流**
- 描述：`data/` 目录项发生创建+删除（无任何文件留存，`dashboard.db` mtime 全程 `17:20:20` 不变）。
- 证据（逐文件前后采样，V2）：
```
start          : 17:30:28 | dashboard.db=17:20:20
after test_backup_retention_enforcement.py    : 17:30:28 | dashboard.db=17:20:20
after test_backup_retention_semantics.py      : 17:30:28 | dashboard.db=17:20:20
after test_backfill_promo_backup_contract.py  : 17:30:28 | dashboard.db=17:20:20
after idle 5s : 17:30:28 | dashboard.db=17:20:20
```
- **重要归因线索**：本轮期间同工作目录出现**非本轮**的并发写入（mtime 落在 V2 窗口）：`services/source_resolution_service.py 17:27:02`、`services/period_context.py 17:28:00`、`tests/test_source_resolution.py 17:28:45`、`tests/test_period_reviews_api.py 17:29:28`；候选还有两个 15:13:53 起的常驻 `python.exe app.py`（pid 4156/7376，**未杀未重启**）。
- **风险提示给主控**：Gate 3 的全量 `pytest tests/ -q` 会同时覆盖**另一条工作流**的文件，任何失败**不可直接归因于本轮备份轮转**；建议 Gate 3 前先确认那条工作流的归属与状态。

### F-08 [低] `docs/BACKUP_RETENTION_PLAN_20261004.md:34` 版本标识未升到 v2.1
- 见上「文档 nit」。条文已更新，仅标题未改。

### F-09 [低 / 不确定] 删除失败的非 protected 文件不计入容量账本
- 描述：`unlink` 失败的文件不进 `kept_bytes`（`:141-146`），其字节仍占盘。极端情况下磁盘超 cap 而 `report['over_capacity']` 为假。
- 证据（EXOTIC PROBE：1 份 protected 100B + 1 份 9000B 非 protected 且 `unlink` 抛 `OSError`，cap=1000）：
```
kept=['big-stuck.db', 'prot.db'] total_on_disk=9100 cap=1000 -> over cap=True
report={}
removed=[]
warning='备份裁剪：删除失败，已跳过 ...'   (C5 警告，非 C4 警告)
```
- 判定：**不算契约违约**——C4 的前提是「裁光全部非 protected 后」，此处前提因 `unlink` 失败而未成立；C5 只要求「继续处理其余项」。仅提示 `over_capacity` **不是**「磁盘是否超 cap」的可靠信号。

## V2 未验证 / 不确定

1. 全量 `pytest tests/ -q`（基线 912 passed）与 `scripts/test_all.ps1`（`TEST_ALL_OK`）—— 任务卡禁止我执行，Gate 3 由主控独占。
2. `data/` 目录 mtime 变化的**确切**来源 —— 已排除本轮三个测试文件（逐文件前后采样）与我的全部探针（全 tempfile）；无法在只读、不杀进程、无句柄工具下归因（候选见 F-07）。
3. F-09：删除失败场景是否属 C4 应覆盖的范围 —— 按契约字面不属；若主控认为属，则应改为「账本计入删除失败项」。
4. 独立性声明：我未参与 T6/T7/T8 任何实现或测试编写；本报告全部结论基于自带复现命令与原始输出，未采信 T6/T7/T8 自述。
5. 透明披露：V2 注入探针通过 `tempfile` 落一份「未修复」模块副本，`cleanup()` 因模块对象引用在 Windows 上可能未即时释放（脚本退出码 1），输出完整有效；未留下仓库内文件。

## V2 附录：复现命令

### V2-A. PROBE A / 反证 / 回归（一条脚本，全 tempfile）
```
=== PROBE A (V2): keep=2 cap=1000 protected=[p1,p2,p3] each 400B (total 1200 > cap) ===
kept=['p1.db', 'p2.db', 'p3.db']
removed=['s1.db', 's2.db']
report={'over_capacity': True}
ASSERT over_capacity is True      -> True
ASSERT warning non-empty          -> True
ASSERT warning says 3 项 & 1200 字节 -> True
=== PROBE A' (reverse): each 100B (total 300 <= cap 1000) ===
kept=['p1.db','p2.db','p3.db'] removed=['s1.db','s2.db'] report={}
ASSERT NOT over_capacity -> True ; ASSERT NO warning -> True
=== PROBE A'': 3x300=900 <= cap 1000 ===
kept=['p1.db','p2.db','p3.db'] report={} warning=''
=== REGRESSION: 5 files keep=4 protected=[newest] -> 4 ===
kept=['b2.db','b3.db','b4.db','b5.db'] removed=['b1.db']
=== REGRESSION C1.1: 4 files keep=2 protected=[newest two] -> 2 ===
kept=['b3.db','b4.db'] removed=['b1.db','b2.db']
=== C3 ordering (v2.1: skip oversized, continue to older) ===
kept=['s1.db','s2.db','s3.db','s5.db'] removed=['big.db']
```
> warning 文案在控制台显示为乱码（GBK 控制台代码页），但脚本对**实际 Python 字符串**的断言 `"3 项" in warn and "1200 字节" in warn` 返回 `True`。

### V2-B. 定向 pytest
```powershell
& .\.venv\Scripts\python.exe -m pytest tests/test_backup_retention_enforcement.py tests/test_backup_retention_semantics.py tests/test_backfill_promo_backup_contract.py -q
# 17 passed, 4 subtests passed in 1.03s
```

### V2-C. T-A10 非空转（注入未修复账本）
```
needle occurrences in live source: 1
INJECTING UNFIXED ledger (quota_protected = [:keep] truncation):
   -> kept_bytes = sum(_size(item) for item in quota_protected)
>>> test_ta10_protected_beyond_quota_still_counts_towards_capacity -> RED (expected)
    AssertionError: no logs of level WARNING or higher triggered on scripts.backup_retention
>>> test_ta11_protected_beyond_quota_within_capacity_is_not_over_capacity -> GREEN
```

### V2-D. 真实目录逐项（只读）
```powershell
$base=Get-Content .tmp\backups_baseline.txt
$cur =Get-ChildItem data\backups -Force | Sort-Object Name | ForEach-Object { "{0}|{1}" -f $_.Name,$_.Length }
Compare-Object $base $cur     # 无输出 = 0 differences
```

### V2-E. T8 逐行 token 分类
见上「T8 文案复核」代码块（`git diff -U0` + `tokenize`）。

## V2 给主控的建议

1. **可判定本轮备份轮转 PASS**；F-01/F-02/F-03/F-05 全部关闭，F-04 未再变动。
2. F-06（可选，1 行断言）建议在 Gate 3 前顺手补上，把「warning 文案必须报全部项/字节」固化进测试。
3. **Gate 3 归因风险**：本工作目录存在另一条并发工作流（见 F-07），请在跑全量门禁前确认其状态，避免把他人失败计入本轮。
4. F-08 仅改文档标题；F-09 建议写入契约「不做的事」或忽略。
