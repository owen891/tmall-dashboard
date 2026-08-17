# README Screenshot Restructure Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Rebuild the GitHub README around three deterministic, safe product screenshots and a concise product-first narrative.

**Architecture:** A repeatable Playwright capture script writes three screenshots from an isolated demo database into `docs/assets/readme/`. The README references those repository-relative assets and links detailed PRD, field, release, and deployment material instead of duplicating it.

**Tech Stack:** Markdown, Playwright/Chromium, Flask test server, SQLite demo seed, Node.js, GitHub CLI

---

### Task 1: Add deterministic README screenshot capture

**Files:**
- Create: `scripts/capture_readme_screenshots.cjs`
- Create: `docs/assets/readme/overview.png`
- Create: `docs/assets/readme/products.png`
- Create: `docs/assets/readme/data-center.png`

- [ ] **Step 1: Add a capture script with fixed routes and selectors**

Create `scripts/capture_readme_screenshots.cjs` with these contracts:

```javascript
const fs = require('node:fs');
const path = require('node:path');
const { chromium } = require('C:/Users/Administrator/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright');

const base = process.env.TMALL_SCREENSHOT_BASE || 'http://127.0.0.1:8774';
const outputDir = path.resolve(__dirname, '..', 'docs', 'assets', 'readme');
const captures = [
  { name: 'overview', route: '/', ready: '[data-overview-root], [data-page="overview"]' },
  { name: 'products', route: '/products?start=2026-07-14&end=2026-08-12', ready: '[data-products-body] tr' },
  { name: 'data-center', route: '/data-center', ready: '[data-capability-domain]' },
];

(async () => {
  fs.mkdirSync(outputDir, { recursive: true });
  const browser = await chromium.launch({ headless: true });
  const page = await browser.newPage({ viewport: { width: 1440, height: 900 }, deviceScaleFactor: 1 });
  page.on('pageerror', (error) => { throw error; });
  for (const capture of captures) {
    await page.goto(`${base}${capture.route}`, { waitUntil: 'networkidle', timeout: 15000 });
    await page.waitForSelector(capture.ready, { timeout: 10000 });
    await page.evaluate(() => document.fonts.ready);
    const overflow = await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth);
    if (overflow > 1) throw new Error(`${capture.name} has ${overflow}px horizontal overflow`);
    await page.screenshot({ path: path.join(outputDir, `${capture.name}.png`), fullPage: false });
  }
  await browser.close();
})().catch((error) => { console.error(error); process.exitCode = 1; });
```

- [ ] **Step 2: Verify the script syntax**

Run:

```powershell
node --check scripts/capture_readme_screenshots.cjs
```

Expected: exit code `0` with no output.

- [ ] **Step 3: Seed an isolated demo database**

Run:

```powershell
py -3 scripts/seed_demo_data.py --demo-database
```

Expected: JSON counts for demo products, facts, promotions, lifecycle, actions, reviews, and goals. The command must not modify `data/dashboard.db`.

- [ ] **Step 4: Start a hidden test server on the demo database**

Run:

```powershell
$env:TMALL_PORT = '8774'
$env:TMALL_DB_PATH = (Resolve-Path 'data/demo/dashboard.db').Path
py -3 scripts/run_test_server.py
```

Expected: `http://127.0.0.1:8774/healthz` returns HTTP 200 and database status `ok`.

- [ ] **Step 5: Capture all three screenshots**

Run:

```powershell
node scripts/capture_readme_screenshots.cjs
```

Expected: three `1440x900` PNG files under `docs/assets/readme/`, each larger than 50 KB and visually nonblank.

- [ ] **Step 6: Commit the capture script and screenshot assets**

```powershell
git add scripts/capture_readme_screenshots.cjs docs/assets/readme
git commit -m "docs: add deterministic product screenshots"
```

### Task 2: Rewrite README around the product narrative

**Files:**
- Modify: `README.md`

- [ ] **Step 1: Replace the long-form README with the approved section order**

The resulting README must contain these headings in this order:

```markdown
# 天猫数据仪表盘
## 产品界面
## 核心能力
## 数据来源策略
## 快速开始
## 生产启动
## 数据导入与定时扫描
## 验证状态
## 已知限制
## 详细文档
```

Place `![经营总览](docs/assets/readme/overview.png)` immediately after the product positioning paragraph. Render the two supporting screenshots in a two-column HTML table so they stay aligned on GitHub:

```html
<table>
  <tr>
    <td width="50%"><img src="docs/assets/readme/products.png" alt="商品运营工作台"></td>
    <td width="50%"><img src="docs/assets/readme/data-center.png" alt="数据中心与来源治理"></td>
  </tr>
  <tr>
    <td align="center">商品运营</td>
    <td align="center">数据中心</td>
  </tr>
</table>
```

- [ ] **Step 2: Preserve the source-precedence contract**

Add this concise table:

```markdown
| 字段类型 | 主来源 | DMP 角色 |
|---|---|---|
| 生意与转化指标 | 生意参谋 | 参考或缺失补充 |
| 推广花费与归因指标 | 推广工具 | 参考或缺失补充 |
| 搜索、推荐、预售、复购、连带购买等独有字段 | DMP | 有效来源 |
```

- [ ] **Step 3: Keep deployment and verification commands executable**

Retain commands for virtualenv installation, `scripts/start_production.ps1`, `scripts/production_preflight.py`, `scripts/release_audit.py`, and `scripts/run_import_scanner.py --once`. Do not include production credentials or local absolute paths.

- [ ] **Step 4: Keep the production-data blocker explicit**

State that 5,674 historical/demo daily facts still lack verified observation/lineage and must be verified, isolated, or supplied with real provenance before production decision use.

- [ ] **Step 5: Commit the README rewrite**

```powershell
git add README.md
git commit -m "docs: rebuild README around product screenshots"
```

### Task 3: Verify the rendered documentation and asset safety

**Files:**
- Verify: `README.md`
- Verify: `docs/assets/readme/*.png`
- Verify: `scripts/capture_readme_screenshots.cjs`

- [ ] **Step 1: Check required links and assets**

Run:

```powershell
rg -n "overview.png|products.png|data-center.png|v1.0.0|RELEASE_STATUS|FIELD_DICTIONARY|PRD_KEEP_EXISTING_ARCHITECTURE" README.md
Get-Item docs/assets/readme/*.png | Select-Object Name,Length
```

Expected: all three relative image paths and all detailed documentation links exist; every PNG is larger than 50 KB.

- [ ] **Step 2: Inspect every screenshot visually**

Open each PNG and verify it is `1440x900`, nonblank, free of overlapping UI, and contains only demo product and demo operations data. Reject any screenshot containing production file paths, credentials, real import filenames, or local absolute paths.

- [ ] **Step 3: Run repository documentation and UI gates**

Run:

```powershell
git diff --check
node --check scripts/capture_readme_screenshots.cjs
node scripts/validate_ui_demos.cjs
```

Expected: all commands exit `0`; UI output includes `7 API-backed pages validated` and `Visual-system static contract validated`.

- [ ] **Step 4: Confirm production data is not staged**

Run:

```powershell
git diff --cached --name-only | Select-String '^data/(dashboard\.db|import_log\.json)$'
```

Expected: no output.

### Task 4: Publish the README update without hiding branch divergence

**Files:**
- GitHub branch: `refactor/demo-phase1`
- Git tag: `v1.0.0`

- [ ] **Step 1: Push the verified release branch**

```powershell
git push origin refactor/demo-phase1
```

Expected: remote branch resolves to local `HEAD`.

- [ ] **Step 2: Move the task-owned `v1.0.0` tag to the final README commit**

Verify the existing remote tag points to the immediately previous task-owned release commit, delete that tag, recreate the annotated tag at `HEAD`, and push it without force-pushing the branch.

- [ ] **Step 3: Verify GitHub rendering paths**

Run:

```powershell
gh release view v1.0.0 --repo owen891/tmall-dashboard --json url,tagName,isDraft,isPrerelease
git ls-remote --heads origin refactor/demo-phase1
git ls-remote --tags origin 'v1.0.0^{}'
```

Expected: Release is public, branch and peeled tag both point to final `HEAD`.

- [ ] **Step 4: Preserve the default-branch boundary**

Do not merge or overwrite `main`. Record that `origin/main...HEAD` is currently `22 33`; a later merge must go through an explicit PR because both branches contain unique commits.
