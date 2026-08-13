# Tmall Dashboard UI Demo Pages Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a complete, standalone UI demo set for the ten non-overview dashboard pages, using the existing `数据概览（标题最左+时间选择器）` page as the visual reference and preserving the information domains defined by `REFACTOR_PLAN.md` and `REFACTOR_GUIDE.md`.

**Architecture:** Create an offline-friendly `docs/ui_demo/` package. Every page is a focused HTML document with shared CSS and JavaScript assets; `shell.js` injects the common 220px sidebar and title/time toolbar, while page HTML owns only its business content. Mock data is local and deterministic so demos do not depend on Flask or API availability.

**Tech Stack:** Semantic HTML5, CSS custom properties, vanilla JavaScript, Lucide UMD, Chart.js UMD, Node.js validation script.

---

## File Structure

```text
docs/ui_demo/
├── README.md
├── index.html
├── assets/
│   ├── tokens.css
│   ├── shell.css
│   ├── components.css
│   ├── shell.js
│   ├── charts.js
│   └── mock-data.js
└── pages/
    ├── products.html
    ├── health.html
    ├── reviews.html
    ├── market.html
    ├── lifecycle.html
    ├── compare.html
    ├── postmortem.html
    ├── keywords.html
    ├── traffic.html
    └── manage.html

scripts/
└── validate_ui_demos.cjs
```

### Task 1: Lock the shared visual contract

**Files:**
- Create: `docs/ui_demo/README.md`
- Create: `docs/ui_demo/assets/tokens.css`
- Create: `docs/ui_demo/assets/shell.css`
- Create: `docs/ui_demo/assets/components.css`

- [ ] **Step 1: Document the page inventory and visual rules**

Write `README.md` with the ten-page route table, the reference page path, viewport targets (`1440x900`, `1024x768`, `390x844`), and the rule that the reference HTML is read-only.

- [ ] **Step 2: Define the exact design tokens**

Use the reference values: primary `#E4400F`, primary hover `#C7380D`, page background `#F7F8FA`, card `#FFFFFF`, foreground `#1A1D23`, muted foreground `#6B7280`, border `#E5E7EB`, success `#16A34A`, warning `#D97706`, danger `#DC2626`, info `#2563EB`, radii `4px/6px/8px`, and spacing based on a 4px scale.

- [ ] **Step 3: Define the common application shell**

Implement a fixed 220px sidebar, 56px sticky top bar, collapsible 72px tablet rail, mobile drawer, scrollable main region, title anchored left, time selector immediately after the title, and compact icon tools on the right.

- [ ] **Step 4: Define reusable operational components**

Implement `.metric-grid`, `.metric-card`, `.section-toolbar`, `.data-table`, `.status-dot`, `.tier-badge`, `.chart-panel`, `.empty-state`, `.alert-list`, `.filter-group`, `.segmented-control`, `.progress-bar`, `.drawer`, and responsive table wrappers. Cards use radius `8px` or less and no nested cards.

- [ ] **Step 5: Run CSS contract checks**

Run:

```powershell
rg -n "#E4400F|--sidebar-width: 220px|\.metric-card|\.data-table|@media" docs/ui_demo/assets
```

Expected: matches in all three CSS files and no purple theme token.

### Task 2: Build the shared shell runtime and catalog

**Files:**
- Create: `docs/ui_demo/assets/shell.js`
- Create: `docs/ui_demo/assets/charts.js`
- Create: `docs/ui_demo/assets/mock-data.js`
- Create: `docs/ui_demo/index.html`

- [ ] **Step 1: Implement shell injection**

`shell.js` reads `body.dataset.page`, injects the shared sidebar/header, marks the active navigation item, exposes working period presets, day/week/month controls, previous/next period navigation, mobile drawer behavior, and re-runs `lucide.createIcons()`.

- [ ] **Step 2: Implement deterministic chart helpers**

`charts.js` exports helpers for line, bar, doughnut, radar, and horizontal-bar charts. Every helper disables animation when `prefers-reduced-motion` is active and uses the shared design tokens.

- [ ] **Step 3: Define mock data contracts**

`mock-data.js` exports data grouped by the same business domains as the API split: `products`, `health`, `reviews`, `market`, `lifecycle`, `compare`, `postmortem`, `keywords`, `traffic`, `manage`.

- [ ] **Step 4: Build the catalog page**

`index.html` lists the reference overview and all ten new demos with page title, purpose, key modules, and direct links. The catalog is unframed and uses a dense two-column list on desktop and one column on mobile.

- [ ] **Step 5: Verify local navigation**

Open `docs/ui_demo/index.html`, click every page link, and confirm each resolves through relative paths without Flask.

### Task 3: Build product, health, and review demos

**Files:**
- Create: `docs/ui_demo/pages/products.html`
- Create: `docs/ui_demo/pages/health.html`
- Create: `docs/ui_demo/pages/reviews.html`

- [ ] **Step 1: Build product operations**

Include KPI strip, compact search/filter toolbar, metric-view tabs, sortable product table, product image/name cell, tier/style/status badges, inline row actions, batch selection, pagination, and a right-side detail drawer. Keep the table stable at a minimum width of 1120px inside a horizontal wrapper.

- [ ] **Step 2: Build health analysis**

Include total health score, healthy/warning/danger counts, score distribution doughnut, 12-dimension radar, dimension ranking bars, and a prioritized abnormal-product table with action owner and deadline.

- [ ] **Step 3: Build review analysis**

Include review volume/positive rate/negative rate/responded rate cards, upload command, sentiment doughnut, topic bar chart, issue-theme chips, product filter, and a scan-friendly review list with sentiment, product, date, and response status.

- [ ] **Step 4: Verify the three pages**

Confirm every page has one `h1`, at least one chart canvas, a meaningful empty state, visible keyboard focus, and no nested card container.

### Task 4: Build market, lifecycle, and comparison demos

**Files:**
- Create: `docs/ui_demo/pages/market.html`
- Create: `docs/ui_demo/pages/lifecycle.html`
- Create: `docs/ui_demo/pages/compare.html`

- [ ] **Step 1: Build market analysis**

Include market size/growth/competition/opportunity cards, keyword opportunity table, demand-vs-competition quadrant, price histogram, demand category bars, ranking list, and report history command.

- [ ] **Step 2: Build lifecycle analysis**

Include stage counts, lifecycle pipeline, stage distribution, stage performance trend, transition-risk list, and product table grouped by launch/growth/maturity/decline stages.

- [ ] **Step 3: Build period comparison**

Include two explicit period selectors, comparison basis switch, KPI delta row, paired line chart, contribution waterfall substitute using horizontal bars, and a metric difference table with positive/negative/neutral states.

- [ ] **Step 4: Verify analysis semantics**

Use green only for favorable business movement, red only for unfavorable movement, orange for attention, and blue for neutral information. Refund-rate decreases must render as favorable.

### Task 5: Build postmortem, keywords, traffic, and management demos

**Files:**
- Create: `docs/ui_demo/pages/postmortem.html`
- Create: `docs/ui_demo/pages/keywords.html`
- Create: `docs/ui_demo/pages/traffic.html`
- Create: `docs/ui_demo/pages/manage.html`

- [ ] **Step 1: Build operating postmortem**

Include target completion, variance cards, event timeline, metric attribution table, decisions, owner/action/deadline table, and open follow-up tasks.

- [ ] **Step 2: Build keyword efficiency**

Include keyword count/search visitors/search conversion/opportunity count cards, search-volume vs conversion matrix, keyword efficiency table, opportunity level, product coverage, and add-to-tracking command.

- [ ] **Step 3: Build traffic structure**

Include total visitors, paid/free ratio, search share, channel doughnut, visitor trend, source funnel, channel contribution table, and abnormal-channel alert list.

- [ ] **Step 4: Build management workspace**

Include task board columns, KPI target progress, scheduled job table, latest operation log, owner filters, and compact create/edit modals represented as functional demo dialogs.

- [ ] **Step 5: Verify repeated workflows**

Confirm filters, segmented controls, table row hover, pagination, dialogs, and nav links behave consistently across all four pages.

### Task 6: Add automated structural validation

**Files:**
- Create: `scripts/validate_ui_demos.cjs`

- [ ] **Step 1: Write the validator**

The script must enumerate the ten required HTML files, assert shared asset references, one page title, one main landmark, one active navigation key, no inline SVG, no `TODO`/`TBD`, and no duplicate IDs per file.

- [ ] **Step 2: Run the validator and confirm it fails before all pages exist**

Run:

```powershell
node scripts/validate_ui_demos.cjs
```

Expected before implementation: non-zero exit with missing-page names.

- [ ] **Step 3: Run the validator after implementation**

Run the same command.

Expected after implementation: `10 demo pages validated` and exit code `0`.

### Task 7: Browser verification and handoff

**Files:**
- Modify only if validation reveals defects: `docs/ui_demo/assets/*.css`, `docs/ui_demo/assets/*.js`, `docs/ui_demo/pages/*.html`

- [ ] **Step 1: Start a static preview server**

Run:

```powershell
python -m http.server 4173 --directory docs/ui_demo
```

- [ ] **Step 2: Verify desktop layouts**

At `1440x900` and `1024x768`, inspect all ten pages for nonblank charts, stable fixed shell dimensions, no incoherent overlap, no clipped buttons, and working navigation.

- [ ] **Step 3: Verify mobile layouts**

At `390x844`, inspect all ten pages for a working drawer, single-column page bands, scrollable data tables, legible values, and no text overflow.

- [ ] **Step 4: Verify accessibility and runtime logs**

Check keyboard focus order, `aria-current`, dialog labels, button names, reduced-motion behavior, and browser console errors. Expected: zero uncaught errors.

- [ ] **Step 5: Final verification**

Run:

```powershell
node scripts/validate_ui_demos.cjs
git diff --check -- docs/ui_demo scripts/validate_ui_demos.cjs
```

Expected: both commands exit `0`.
