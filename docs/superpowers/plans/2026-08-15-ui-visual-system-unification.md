# UI Visual System Unification Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make every `frontend/ui_demo` page consume one coherent TMall-orange operational visual system without changing data, interaction, navigation, or responsive behavior.

**Architecture:** Keep the current three CSS entry points. `tokens.css` owns primitive, semantic, and component variables; `shell.css` consumes them for app chrome; `components.css` consumes them for reusable and page-specific UI. A small Node validator prevents shared CSS from reintroducing unapproved font, weight, icon, color, radius, and shadow values.

**Tech Stack:** Static HTML, CSS custom properties, Lucide 1.8, Node.js, Playwright, existing Flask demo server and UI smoke scripts.

---

## File Map

- Modify: `frontend/ui_demo/assets/tokens.css` - three-layer visual tokens, dark-mode semantic overrides, compatibility aliases.
- Modify: `frontend/ui_demo/assets/shell.css` - shell typography, controls, icons, focus, responsive sizing.
- Modify: `frontend/ui_demo/assets/components.css` - generic primitives and page-specific visual values tokenized without changing business layouts.
- Create: `scripts/validate_visual_system.cjs` - static token/visual-rule regression gate.
- Modify: `scripts/validate_ui_demos.cjs` - call the new visual gate from the existing UI validation entry point.

### Task 1: Lock the Visual Contract With a Static Gate

**Files:**
- Create: `scripts/validate_visual_system.cjs`
- Modify: `scripts/validate_ui_demos.cjs`

- [x] **Step 1: Write the standalone failing visual-rule validator**

Create `scripts/validate_visual_system.cjs` with these source files and assertions:

```javascript
const fs = require('node:fs');
const path = require('node:path');

const root = path.resolve(__dirname, '..', 'frontend', 'ui_demo', 'assets');
const tokens = fs.readFileSync(path.join(root, 'tokens.css'), 'utf8');
const shared = ['shell.css', 'components.css']
  .map((file) => ({ file, css: fs.readFileSync(path.join(root, file), 'utf8') }));
const errors = [];
const assert = (condition, message) => { if (!condition) errors.push(message); };

for (const name of [
  '--color-orange-600', '--surface-page', '--text-primary', '--border-default',
  '--font-size-body', '--font-size-meta', '--font-size-title', '--icon-control',
  '--button-primary-bg', '--panel-radius', '--dialog-shadow', '--focus-ring',
]) assert(tokens.includes(name), `tokens.css: missing ${name}`);

for (const { file, css } of shared) {
  assert(!/font-weight:\s*650\b/.test(css), `${file}: unsupported font-weight 650`);
  assert(!/font-size:\s*(?:9|10|25)px\b/.test(css), `${file}: unsupported font-size`);
  assert(!/#[0-9a-f]{3,8}\b/i.test(css), `${file}: raw hex color outside token source`);
  assert(!/rgb\(/i.test(css), `${file}: raw rgb color outside token source`);
}

assert(/\.demo-tool[\s\S]*?width:\s*var\(--icon-button-size\)/.test(shared[0].css), 'shell.css: icon buttons must use a shared size token');
assert(/\.button\s*\{[\s\S]*?min-height:\s*var\(--control-height\)/.test(shared[1].css), 'components.css: buttons must use shared control height');
assert(/\.metric-card__value[\s\S]*?font-size:\s*var\(--font-size-kpi\)/.test(shared[1].css), 'components.css: KPI values must use the KPI token');

if (errors.length) {
  console.error(`${errors.length} visual-system error(s)`);
  errors.forEach((message) => console.error(`- ${message}`));
  process.exitCode = 1;
} else {
  console.log('Visual-system static contract validated');
}
```

- [x] **Step 2: Run the validator and confirm the baseline fails**

Run:

```powershell
node scripts/validate_visual_system.cjs
```

Expected: non-zero exit with missing token names and existing raw-color/non-system type failures.

- [x] **Step 3: Wire the gate into the existing validation command**

At the end of `scripts/validate_ui_demos.cjs`, before its final success message, add:

```javascript
const { spawnSync } = require('node:child_process');
const visualGate = spawnSync(process.execPath, [path.resolve(__dirname, 'validate_visual_system.cjs')], { stdio: 'inherit' });
if (visualGate.status !== 0) process.exitCode = 1;
```

Keep `validate_ui_demos.cjs`'s existing API and markup assertions unchanged.

- [x] **Step 4: Verify the gate is called from the normal UI check**

Run:

```powershell
node scripts/validate_ui_demos.cjs
```

Expected: the existing UI checks still run and the process exits non-zero because the visual-system baseline has not yet been migrated.

### Task 2: Establish Three-Layer Tokens and Compatibility Aliases

**Files:**
- Modify: `frontend/ui_demo/assets/tokens.css:1-90`
- Test: `scripts/validate_visual_system.cjs`

- [x] **Step 1: Add primitive token groups**

Replace the root declarations with explicit primitive groups. Define neutral, orange, success, warning, danger, info, and purple ramps; a 4px spacing scale through `--space-8: 32px`; type tokens; icon tokens; three radius tokens; and three shadows. Keep the existing font-family stack.

Use these canonical type and control declarations:

```css
--font-size-meta: 11px;
--font-size-secondary: 12px;
--font-size-body: 13px;
--font-size-label: 14px;
--font-size-section: 16px;
--font-size-title: 20px;
--font-size-kpi: 24px;
--line-height-meta: 16px;
--line-height-secondary: 18px;
--line-height-body: 20px;
--line-height-title: 28px;
--icon-inline: 14px;
--icon-nav: 16px;
--icon-control: 18px;
--icon-emphasis: 20px;
--icon-empty: 24px;
--control-height: 36px;
--icon-button-size: 36px;
```

- [x] **Step 2: Add semantic and component token groups**

Define semantic aliases for `--surface-page`, `--surface-base`, `--surface-muted`, `--text-primary`, `--text-secondary`, `--text-tertiary`, `--border-default`, `--border-strong`, `--brand`, `--brand-hover`, `--brand-tint`, state colors, and `--focus-ring`.

Then define component aliases such as:

```css
--button-primary-bg: var(--brand);
--button-primary-bg-hover: var(--brand-hover);
--button-height: var(--control-height);
--input-height: var(--control-height);
--panel-radius: var(--radius-lg);
--panel-shadow: var(--shadow-sm);
--dialog-radius: var(--radius-lg);
--dialog-shadow: var(--shadow-lg);
--nav-item-height: 40px;
```

Retain existing public variables (`--page`, `--surface`, `--text`, `--border`, `--success`, and their current variants) as aliases to the semantic roles so existing selectors keep rendering through the migration.

- [x] **Step 3: Limit dark mode to semantic overrides**

Rewrite `:root[data-theme="dark"]` so it reassigns only semantic aliases and shadows. Do not redefine component token names in dark mode. Preserve `color-scheme: dark` and ensure `--text-primary` and `--text-secondary` remain visibly distinct.

- [x] **Step 4: Normalize document defaults**

Set `body` to `font-size: var(--font-size-body)`, `line-height: var(--line-height-body)`, `color: var(--text-primary)`, and retain the current font smoothing, minimum width, accessible `.sr-only`, and `font: inherit` control reset.

- [x] **Step 5: Run the visual gate and inspect token-only failures**

Run:

```powershell
node scripts/validate_visual_system.cjs
```

Expected: token-name failures are gone; remaining failures identify only `shell.css` and `components.css` migrations.

### Task 3: Normalize the Application Shell

**Files:**
- Modify: `frontend/ui_demo/assets/shell.css:1-229`
- Test: `scripts/validate_visual_system.cjs`, `scripts/validate_ui_demos.cjs`

- [x] **Step 1: Convert the sidebar, topbar, and page-intro type hierarchy**

Replace shell raw type values with the roles below:

```css
.demo-brand__name { font-size: var(--font-size-body); font-weight: 700; line-height: var(--line-height-secondary); }
.demo-nav__item { min-height: var(--nav-item-height); font-size: var(--font-size-body); font-weight: 500; }
.demo-nav__item[aria-current="page"] { font-weight: 600; }
.demo-topbar__title { font-size: var(--font-size-title); line-height: var(--line-height-title); }
.demo-page__intro h2 { font-size: var(--font-size-section); line-height: 24px; }
.demo-page__intro p, .demo-sidebar__status { font-size: var(--font-size-secondary); line-height: var(--line-height-secondary); }
```

Use the spacing tokens for all shell gaps/padding that currently use 4/8/10/12/14/16/20/24px; keep fixed chart/calendar dimensions only where a token would obscure intentional geometry.

- [x] **Step 2: Unify shell icon and control rules**

Replace per-selector icon widths with `--icon-nav`, `--icon-inline`, `--icon-control`, and `--icon-empty`. Use this baseline:

```css
.demo-nav__item i { width: var(--icon-nav); height: var(--icon-nav); stroke-width: 1.75; }
.demo-tool { width: var(--icon-button-size); height: var(--icon-button-size); min-width: var(--icon-button-size); min-height: var(--icon-button-size); }
.demo-tool i, .demo-tool .lucide { width: var(--icon-control); height: var(--icon-control); stroke-width: 1.75; }
```

For the `max-width: 520px` breakpoint, set `--icon-button-size: 44px` on `.demo-topbar__tools` or the mobile `.demo-tool` rule, while retaining the 18px icon glyph.

- [x] **Step 3: Tokenize overlays, focus, and white foreground values**

Replace direct `#fff` references with `--text-on-brand`, direct `rgb(...)` focus/backdrop/shadow declarations with `--focus-ring`, `--overlay-backdrop`, and component shadow tokens, and raw calendar `4px` radius with `--radius-sm`.

- [x] **Step 4: Run static and shell regression checks**

Run:

```powershell
node scripts/validate_visual_system.cjs
node scripts/validate_ui_demos.cjs
```

Expected: no shell visual contract errors; existing shell validation assertions for date controls, dialogs, theme controls, and local Lucide still pass.

### Task 4: Normalize Shared Components

**Files:**
- Modify: `frontend/ui_demo/assets/components.css:1-443`
- Test: `scripts/validate_visual_system.cjs`, `scripts/validate_ui_demos.cjs`

- [x] **Step 1: Rewrite generic primitive declarations at the top of the file**

Normalize `.metric-card`, `.chart-panel`, `.table-panel`, `.plain-panel`, `.panel`, `.button`, `.input`, `.select`, `.data-table`, `.badge`, `.segmented`, `.chip`, `.progress`, `.empty-state`, `.modal-form`, and `.alert-list` to reference component/semantic tokens.

Use these required contracts:

```css
.metric-card__value { font-size: var(--font-size-kpi); font-weight: 700; line-height: var(--line-height-title); }
.panel__title { font-size: var(--font-size-label); font-weight: 600; line-height: 20px; }
.button, .input, .select { min-height: var(--control-height); font-size: var(--font-size-secondary); }
.button i { width: var(--icon-inline); height: var(--icon-inline); stroke-width: 1.75; }
.data-table { font-size: var(--font-size-body); }
.data-table th { font-size: var(--font-size-meta); font-weight: 600; }
.badge { font-size: var(--font-size-meta); font-weight: 600; line-height: var(--line-height-meta); }
```

Convert every `font-weight: 650` in this area to 600. Convert 9px/10px text to `--font-size-meta`; convert 25px metrics to `--font-size-kpi`.

- [x] **Step 2: Define complete generic interaction states**

Use shared tokenized styles for `.button`, `.input`, `.select`, `.segmented button`, `.chip`, and `.data-table tbody tr` in default, hover, focus-visible, selected/pressed, and disabled states. Required focus rule:

```css
.button:focus-visible,
.input:focus-visible,
.select:focus-visible,
.segmented button:focus-visible {
  outline: 2px solid var(--focus-ring);
  outline-offset: 2px;
}
```

Disabled controls must retain `cursor: not-allowed`, use muted foreground/border tokens, and never depend on color alone where state text already exists.

- [x] **Step 3: Tokenize status, chip, dialog, and feedback colors**

Replace raw chip borders (`#fecaca`, `#fed7aa`, `#bbf7d0`), timeline/overlay raw colors, and direct shadows with `--border-danger-subtle`, `--border-warning-subtle`, `--border-success-subtle`, `--overlay-backdrop`, and component elevation tokens. Preserve purposeful chart gradients and any JavaScript-configured data visualization swatches.

- [x] **Step 4: Run the visual gate**

Run:

```powershell
node scripts/validate_visual_system.cjs
```

Expected: generic component selectors satisfy the visual contract; failures, if any, are confined to page-specific sections below the shared primitives.

### Task 5: Sweep Page-Specific Visual Exceptions

**Files:**
- Modify: `frontend/ui_demo/assets/components.css:218-690`
- Test: `scripts/validate_visual_system.cjs`, `scripts/validate_ui_demos.cjs`

- [x] **Step 1: Migrate lifecycle, promotion, review, data-center, and product-detail regions**

Replace raw font sizes, weights, colors, radius, shadows, and icon dimensions in lifecycle cards, promotion dialogs/drilldowns, review details, data-center stepper, and product-detail dialogs with the role/component tokens. Preserve their grid definitions, `min-width`, chart heights, dialog viewport bounds, and overflow behavior.

Use `--font-size-meta` for compact labels, `--font-size-secondary` for supporting copy, `--font-size-body` for action content, and `--font-size-label` for subheadings. Replace all remaining 650 weights with 600.

- [x] **Step 2: Migrate the overview-v2 presentation without changing data layout**

Tokenize `.overview-v2-*` focus, selected state, KPU card, progress, alert, product metric, and rank styles. Remove the raw `#64748b`, `#f7fafb`, `#cbd8df`, and `rgb(55 78 92 / .08)` values; map them to focus, selected-surface, selected-border, and selected-elevation tokens.

Keep all `data-overview-*` hooks, grid tracks, product image geometry, chart dimensions, and overflow handling unchanged.

- [x] **Step 3: Re-run the full static validation**

Run:

```powershell
node scripts/validate_visual_system.cjs
node scripts/validate_ui_demos.cjs
```

Expected: both commands exit 0. The normal UI validator still reports the same required API-backed pages as before.

### Task 6: Verify Rendered System Consistency and Regression Safety

**Files:**
- No source changes expected unless validation identifies a visual regression.
- Test: `scripts/smoke_core_pages.cjs`, `scripts/smoke_overview_polish.cjs`, CSS static gate, existing tests.

- [x] **Step 1: Start the existing local application server**

Use the project runner that binds a disposable local port, then set `TMALL_SMOKE_BASE` to that address. Do not use static file hosting because the demo is API-backed.

```powershell
$env:TMALL_PORT = '8773'
Start-Process -WindowStyle Hidden -FilePath .\.venv\Scripts\python.exe -ArgumentList 'scripts/run_test_server.py' -PassThru
```

Expected: `http://127.0.0.1:8773` serves the dashboard and API endpoints.

- [x] **Step 2: Run core-page browser smoke at desktop and mobile sizes**

Run:

```powershell
$env:TMALL_SMOKE_BASE = 'http://127.0.0.1:8773'
node scripts/smoke_core_pages.cjs
```

Expected: all configured pages load without console/HTTP errors, visible charts contain painted pixels, dialogs remain inside the viewport, and no page has horizontal document overflow.

- [x] **Step 3: Run overview interaction and responsive smoke**

Run:

```powershell
$env:TMALL_SMOKE_BASE = 'http://127.0.0.1:8773'
$env:TMALL_SMOKE_SHOTS = (Get-Location).Path
node scripts/smoke_overview_polish.cjs
```

Expected: desktop and 390px mobile pass focus restoration, dialog bounds, interactive state, report rows, chart event lifecycle, and horizontal-overflow checks. Review the two generated screenshots once for visual clipping or hierarchy breaks.

- [x] **Step 4: Run syntax and automated regression checks**

Run:

```powershell
node --check scripts/validate_visual_system.cjs
node scripts/validate_visual_system.cjs
node scripts/validate_ui_demos.cjs
.\.venv\Scripts\python.exe -m unittest tests.test_frontend_prd_contract tests.test_template_integration tests.test_release_gates -v
```

Expected: every command exits 0.

- [ ] **Step 5: Commit the implementation as one focused visual-system change**

```powershell
git add frontend/ui_demo/assets/tokens.css frontend/ui_demo/assets/shell.css frontend/ui_demo/assets/components.css scripts/validate_visual_system.cjs scripts/validate_ui_demos.cjs
git commit -m "refactor: unify dashboard visual system"
```

Do not stage unrelated files already present in the worktree.

## Completion Criteria

- The three shared CSS files follow the token/component contracts in the approved design.
- The static gate prevents recurrence of raw visual values and unsupported typography in shared CSS.
- Every existing page retains its data hooks, feature behavior, and responsive layout while presenting the same type, icon, color, component, spacing, radius, and elevation vocabulary.
- `validate_ui_demos`, visual static validation, focused frontend tests, and desktop/mobile Playwright smoke checks pass.
