# Promotion Field Drag Reorder Implementation Plan

> **For agentic workers:** Execute this plan inline with the existing project patterns.

**Goal:** Allow users to reorder selected promotion fields by dragging preview rows while preserving the existing move buttons as an accessible fallback.

**Architecture:** Extend the existing `DemoFieldSelector` component with native pointer drag state. The selected key array remains the single source of truth; drag completion updates that array, re-renders the preview, and emits the existing `onChange` callback. CSS will expose a grab cursor, dragged-row state, and drop indicator without changing the table or settings API.

**Tech Stack:** Vanilla JavaScript Pointer Events, existing CSS tokens, Playwright smoke verification.

---

### Task 1: Add drag reorder behavior

**Files:**
- Modify: `frontend/ui_demo/assets/field-selector.js`

- [x] Add `draggedPosition` and `dragOverPosition` state.
- [x] Use Pointer Events for pointer capture, target-row hit testing, and drop cancellation outside the list.
- [x] Move the dragged key into the drop position, then call `renderPreview()` and `notify()`.
- [x] Keep existing arrow buttons and keyboard focus behavior unchanged.

### Task 2: Style drag affordances

**Files:**
- Modify: `frontend/ui_demo/assets/components.css`

- [x] Add grab/grabbing cursors to preview rows.
- [x] Add a visible dragged-row opacity state and drop insertion line.
- [x] Preserve the existing mobile layout and button hit targets.

### Task 3: Verify interaction and regressions

**Files:**
- Test: `frontend/ui_demo/assets/field-selector.js`
- Test: `frontend/ui_demo/assets/components.css`

- [x] Run `node --check frontend/ui_demo/assets/field-selector.js`.
- [x] Use Playwright on `/promotion` to verify drop-before, drop-after, and the visible table ordering path.
- [x] Verify arrow buttons still move a row; API/template flows remain covered by the focused suites.
- [x] Run the focused Python settings and promotion API suites.
