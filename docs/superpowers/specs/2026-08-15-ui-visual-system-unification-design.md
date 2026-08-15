# UI Visual System Unification Design

## Goal

Unify the `frontend/ui_demo` dashboard into a restrained operations UI: TMall orange remains the brand and high-priority action color, while neutral surfaces carry the information-dense working interface. Preserve every page's data, markup contract, interaction, and responsive structure.

## Evidence And Scope

- `tokens.css` currently mixes raw values and semantic aliases in one small flat layer.
- `shell.css` and `components.css` contain 398 direct visual declarations. `components.css` is 690 lines and contains repeated visual values outside the token layer.
- Font sizes currently range from 9px to 25px, icon sizes from 13px to 24px, weights include 400/500/600/650/700, and component states use raw colors and ad hoc shadows.
- All pages share the same CSS import order, so the implementation can centralize visual behavior without changing page-level scripts.

In scope: typography, color, spacing, radius, elevation, icons, common component states, shell structure, page-level CSS exceptions, and desktop/tablet/mobile consistency. Out of scope: changing API contracts, data structure, product copy, navigation hierarchy, or dashboard features.

## Design Direction

The dashboard is an operational tool, not a marketing surface. It should be compact, calm, and easy to scan:

- Orange is reserved for primary calls to action, active navigation, selected controls, and exceptional metric emphasis. It is not a general-purpose decoration color.
- Neutral surfaces, borders, and text establish hierarchy; semantic success, warning, danger, and info colors explain state without competing with the brand.
- Panels use one border, 8px radius, and the smallest elevation by default. Larger shadow is reserved for dialogs and floating overlays.
- Mobile preserves the same hierarchy and increases interactive targets, rather than introducing a separate visual language.

## Token Architecture

`assets/tokens.css` becomes the single source of truth, organized in one file with three layers.

1. Primitive tokens: raw gray, orange, semantic-state color ramps; 4px spacing scale; font families; type sizes; radius; shadows; icon sizes; transition durations.
2. Semantic tokens: page/surface/text/border roles; brand and state roles; focus ring; content spacing; control height; elevation roles.
3. Component tokens: button, input, panel, table, badge, segmented control, dialog, navigation, and icon roles.

Dark mode overrides semantic values only. Existing public variable names remain as compatibility aliases while callers are migrated, so the change does not break current page scripts or CSS selectors.

## Typography And Iconography

Typography uses the existing CJK-capable sans stack and tabular mono stack.

| Role | Size | Weight | Line height |
| --- | ---: | ---: | ---: |
| Page title | 20px | 700 | 28px |
| Section title | 16px | 600 | 24px |
| Panel title / control label | 14px | 600 | 20px |
| Body / table cell | 13px | 400 | 20px |
| Secondary text | 12px | 400 or 500 | 18px |
| Metadata / badge | 11px | 500 or 600 | 16px |

Numerical KPIs use the mono stack at 24px/700. The only valid text weights are 400, 500, 600, and 700; existing `650` uses become 600.

Lucide icons use `stroke-width: 1.75` by default. Valid sizes are 14px for inline metadata, 16px for navigation and standard controls, 18px for toolbar/icon buttons, 20px for prominent actions, and 24px for empty states. Icon-only controls use the shared square control token, never locally sized padding.

## Color, Spacing, Radius, And Elevation

- Use a gray surface system for page, base surface, raised surface, muted surface, and borders.
- Use orange for `brand`, `brand-hover`, `brand-subtle`, and `focus`; use success/warning/danger/info only through semantic status tokens.
- Use a 4px spacing scale: 4, 8, 12, 16, 20, 24, 32. Component gaps and paddings must reference it.
- Use 4px for compact content and tables, 6px for controls, 8px for panels and dialogs. Full radius is limited to pills, progress bars, and circular indicators.
- Use `shadow-sm` on ordinary panels only where separation is necessary; `shadow-md` for popovers; `shadow-lg` for dialogs. No component-specific raw shadow literals.

## Component Contract

The shared CSS will define consistent default, hover, focus-visible, active/selected, disabled, and semantic variants for the following primitives:

- Shell: sidebar, top bar, page intro, navigation, toolbar, responsive controls.
- Form controls: `.button`, `.input`, `.select`, icon buttons, segmented controls, chips.
- Surfaces: metric cards, panels, charts, tables, empty states, message/alert rows.
- Data/status: badges, deltas, progress, status dots, timeline and lifecycle state chips.
- Overlays: dialogs, popovers, toolboxes, form layouts, toast feedback.

Page-specific selectors remain only for data visualization, information layout, or business-specific composition. Their visual properties must consume shared tokens and component rules rather than introduce a competing vocabulary.

## Implementation Sequence

1. Expand `tokens.css` with primitives, semantic aliases, component tokens, dark-mode semantic overrides, and temporary backward-compatible aliases.
2. Normalize `shell.css` to the shared type, icon, spacing, focus, and responsive control rules.
3. Normalize the generic primitives at the top of `components.css`; convert direct colors, ad hoc sizes, non-system weights, radius, and shadows to tokens.
4. Sweep page-specific component selectors and migrate remaining direct visual values to the shared system. Preserve non-visual dimensional rules required by charts and tables.
5. Run static token checks, existing UI validation/smoke tests, and browser screenshots at 1440x900, 1024x768, and 390x844. Fix only defects caused by the visual migration.

## Acceptance Criteria

- Shared CSS exposes a documented three-layer token system and all common primitives consume it.
- No direct hex/rgb colors, arbitrary shadows, or ad hoc font-size/font-weight values remain in shared shell/component rules except documented compatibility values and data-visualization color swatches.
- Shared typography and icon sizes follow the role tables above across every demo page.
- Buttons, inputs, cards, tables, badges, dialogs, navigation, and feedback states have matching visual states and accessible focus indicators.
- Light and dark themes retain text contrast and visual hierarchy.
- Desktop, tablet, and mobile screenshots render without overlap, clipped controls, or unexpected horizontal page scrolling.
- Existing validation and smoke scripts pass without backend or interaction regressions.

## Risks And Guardrails

- The worktree contains substantial unrelated uncommitted work. The implementation changes only the three shared CSS files plus narrowly required page selectors; it will not revert, reformat, or rewrite existing functional changes.
- Some page components are not currently generic enough to eliminate their layout selectors. Those selectors will stay, but their color/type/radius/elevation values will be tokenized.
- The dashboard's existing chart and product-thumbnail assets are not restyled unless their surrounding UI requires token integration.
