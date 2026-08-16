# 商品分类字典与中文化 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在设置页管理分层、风格、生命周期和季节属性，并在商品与生命周期页面统一显示中文。

**Architecture:** 将默认字典、规范化和中文查找集中到独立服务模块；设置服务负责持久化与系统项保护；生命周期服务只允许启用字典值，同时保留自动算法的固定内置编码。前端从设置接口加载字典，设置页提供编辑器，商品页与生命周期页复用同一份显示名称。

**Tech Stack:** Flask、SQLite、Python unittest、原生 JavaScript、HTML/CSS。

---

### Task 1: 字典领域模型与设置 API

**Files:**
- Create: `services/classification_service.py`
- Modify: `services/settings_service.py`
- Test: `tests/test_settings_api.py`

- [x] 写失败测试，断言默认设置包含四组中文分类字典，并覆盖新增、改名、停用、重复值、空名称和系统项保护。
- [x] 运行 `python -m unittest tests.test_settings_api -v`，确认新增测试因缺少 `classification_dictionaries` 失败。
- [x] 在 `classification_service.py` 定义默认字典、深拷贝默认值、规范化、校验、启用值查找和显示名称查找函数。
- [x] 将 `classification_dictionaries` 加入设置默认值，并在设置更新时使用字典校验器。
- [x] 再次运行设置 API 测试，确认通过。

### Task 2: 生命周期自定义值与中文元数据

**Files:**
- Modify: `services/lifecycle_service.py`
- Test: `tests/test_lifecycle_api.py`

- [x] 写失败测试，断言启用的自定义生命周期/季节属性可人工保存，停用或未知值返回 422，响应包含中文标签。
- [x] 运行 `python -m unittest tests.test_lifecycle_api -v`，确认测试因固定白名单或缺少标签失败。
- [x] 从当前设置字典解析启用值；保留系统算法固定输出；在 assessment 和 history 响应消费端所需数据中提供稳定编码。
- [x] 运行生命周期 API 测试，确认通过且原有自动判断测试不回归。

### Task 3: 设置页字典编辑器

**Files:**
- Modify: `frontend/ui_demo/pages/settings.html`
- Modify: `frontend/ui_demo/assets/settings-live.js`
- Modify: `frontend/ui_demo/assets/components.css`
- Test: `tests/test_frontend_prd_contract.py`

- [x] 写失败的前端契约测试，断言设置页存在四组字典编辑器挂载点、设置脚本提交字典且没有原始 JSON 编辑器。
- [x] 运行 `python -m unittest tests.test_frontend_prd_contract -v`，确认失败。
- [x] 在设置页加入独立“商品分类字典”区块；使用紧凑行编辑中文名、启用状态和新增项；内置编码只读。
- [x] 将编辑状态并入现有设置 PUT 请求，保存失败保留本地状态并显示错误。
- [x] 添加适配桌面和移动布局的样式并运行前端契约测试。

### Task 4: 商品页与生命周期页中文化

**Files:**
- Modify: `frontend/ui_demo/assets/products-live.js`
- Modify: `frontend/ui_demo/assets/lifecycle-live.js`
- Modify: `frontend/ui_demo/pages/lifecycle.html`
- Test: `tests/test_frontend_prd_contract.py`

- [x] 写失败测试，扫描业务脚本和生命周期页面，要求已知英文枚举必须通过中文标签函数展示，且编辑选项由设置字典生成。
- [x] 运行目标测试，确认现有硬编码或原值直出导致失败。
- [x] 商品页加载设置字典，筛选器显示中文标签、提交稳定值；分层/风格编辑候选合并字典与历史值，允许自由输入。
- [x] 生命周期页加载设置字典，动态生成编辑选项，并中文化阶段、季节、置信度和来源。
- [x] 运行目标前端契约测试。

### Task 5: 集成验证

**Files:**
- Modify only if verification exposes a scoped defect.

- [x] 运行 `python -m unittest tests.test_settings_api tests.test_lifecycle_api tests.test_frontend_prd_contract tests.test_smoke -v`。
- [x] 运行 `python scripts/production_preflight.py` 检查完整生产门禁。
- [x] 启动本地测试服务，用浏览器在桌面与移动尺寸检查设置字典、商品编辑和生命周期对话框。
- [x] 检查浏览器控制台、网络请求、文本溢出和英文枚举漏出；修复后重复目标验证。
