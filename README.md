# 天猫数据仪表盘

面向单店铺运营团队的数据分析和商品运营闭环工具。项目保持 Flask + SQLite + 原生 HTML/CSS/JavaScript，不引入第二套前端或数据库。

## 快速开始

当前发布基线使用 Python 3.14；请使用与之匹配的依赖版本安装。

```powershell
py -3 -m venv .venv
.\.venv\Scripts\Activate.ps1
py -3 -m pip install -r requirements.txt
py -3 app.py
```

打开 `http://127.0.0.1:5000/`。主工作台固定为总览、商品、推广、生命周期、复盘、数据中心、设置七页；旧页面仅通过 `/legacy/` 兼容访问。

## 本地生产启动

本机生产运行使用 Waitress，不使用 Flask 开发服务器。先完成数据库备份，再以局域网监听地址启动：

```powershell
Copy-Item data/dashboard.db data/dashboard.db.bak
py -3 -m waitress --host=0.0.0.0 --port=5000 wsgi:application
```

启动后在本机验证：

```powershell
Invoke-WebRequest http://127.0.0.1:5000/healthz | Select-Object -ExpandProperty Content
```

返回 `"ok":true` 且 `"database":"ok"` 才可进入局域网访问。部署前将 `data/dashboard.db` 放在本机受控路径，Windows 防火墙仅允许受信任网段访问端口 `5000`。

启动前可运行只读预检；默认使用临时数据库，不会修改运营数据：

```powershell
py -3 scripts/production_preflight.py
```

## 数据导入

数据中心支持店铺日度、商品日/周/月、推广渠道/计划/单元/商品、退款和新老客来源。导入流程为预览 -> 字段映射 -> 质量校验 -> 事务确认；缺少 R1 必填字段会阻止写入，缺失或不足数据显示为无数据/数据不足，不补造 0。

每个批次记录 `source_type`、业务键、映射模板、质量摘要和审计日志。撤销只恢复该批次实际影响且没有被后续批次覆盖的事实；存在覆盖冲突时返回 409，不做静默删除。

## 数据库迁移、备份与恢复

启动时 `db.init_db()` 执行幂等迁移。升级前备份 SQLite 文件：

```powershell
Copy-Item data/dashboard.db data/dashboard.db.bak
py -3 -c "from db import init_db; init_db()"
```

恢复时停止 Flask，将备份复制回 `data/dashboard.db` 后重新启动。不要直接编辑运行中的数据库；目标、动作、生命周期人工调整均保留版本和审计记录。

## 已知边界

- 推广计划、单元、创意、地域、内容归因只有在对应粒度事实导入后才开放，下钻不会构造不存在的行。
- 生命周期需要连续有效日达到 60 天；季节性需要 12 个完整自然月。数据不足显示“数据积累中”，人工覆盖会标记来源并保留历史。
- 目标原子值是日目标，年、季、月、周、日由日目标聚合；调整校验锁定周期、版本和年度守恒。

## 验证

```powershell
py -3 -m unittest discover -s tests -v
node --check frontend/ui_demo/assets/promotion-live.js
node --check frontend/ui_demo/assets/settings-live.js
node --check frontend/ui_demo/assets/goals-live.js
node --check frontend/ui_demo/assets/reviews-live.js
node --check frontend/ui_demo/assets/lifecycle-live.js
node scripts/validate_ui_demos.cjs
```

## PRD 验收矩阵（2026-08-13）

| PRD 范围 | 当前状态 | 说明 |
|---|---|---|
| 第 5 节全局规则 | 已完成 | 单店、Asia/Shanghai、数据状态、缺失不补零均由服务层和页面状态统一处理。 |
| 第 7 节目标体系 | 已完成 | 年/季/月/周/日从日原子目标聚合；自动拆解、版本、锁定、冲突、审计和首页五层摘要已接通。 |
| 第 8 节运营动作 | 已完成 | 动作状态机、待办排序、观察窗口回算、阻塞/失败、复盘后完成和历史保留。 |
| 第 9 节生命周期 | 已完成 | 数据不足显示“数据积累中”；足量数据提供阶段、依据、置信度、推广依赖、迁移历史和人工锁定。 |
| 第 10 节七页工作台 | 已完成 | 总览、商品、推广、生命周期、复盘、数据中心、设置均使用正式 Flask 路由和 API。 |
| 第 12 节视觉规范 | 已完成 | 统一 tokens、Panel、Table、Filter、Drawer、状态组件；桌面/390px 无横向溢出。 |
| 第 13 节 API 契约 | 已完成 | 新域 API 使用统一 `{ok,data,availability,requestId}`；旧 API 保留兼容入口。 |
| 第 15 节非功能 | 已完成 | 白名单、迁移、事务导入、批次撤销、服务端分页、异步兼容入口和前端语法检查已覆盖。 |
| 第 16 节验收 | 已验证 | 150 项后端测试、全量 JS 检查、7 页静态校验、桌面/移动冒烟均通过。 |

明确边界：评价/市场/周期对比/工具箱等历史能力仍保留在兼容 API 或 `/legacy/`；它们不是当前七个一级页面的主导航。主应用 `frontend/ui_demo/` 统一使用 ECharts。

字段、来源、R1/R2 状态和公式见 [docs/FIELD_DICTIONARY.md](docs/FIELD_DICTIONARY.md)，产品验收条款见 [docs/PRD_KEEP_EXISTING_ARCHITECTURE.md](docs/PRD_KEEP_EXISTING_ARCHITECTURE.md)。
