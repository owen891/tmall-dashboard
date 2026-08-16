# TM Data Capability Catalog Design

**Date:** 2026-08-14
**Status:** Proposed for Phase 2
**Scope:** Current single-store SQLite deployment and its existing imported facts

## 1. Problem

Phase 1 standardized metric formulas and API capability envelopes, but the system still lacks one authoritative answer to three questions:

1. What raw data can the system currently obtain?
2. What metrics can be derived from that data, and under which prerequisites?
3. Which pages and operations are justified by those facts?

Today these answers are spread across the database schema, import mappings, repositories, metric code, API adapters, and page JavaScript. That makes page design drift back toward assumptions.

## 2. Decision

Build a hybrid data capability catalog:

- Code owns semantic definitions: domain name, grain, standard fields, derived metrics, formulas, prerequisites, limitations, consumer pages, and supported operations.
- The database supplies live evidence: row count, entity count, date range, latest update, populated fields, missing ranges where available, and source batches.
- The API combines both into one response. It never treats an empty table or a schema-only field as an available business capability.

Rejected alternatives:

- Database introspection only: accurate about columns, but unable to explain business meaning, formulas, or page ownership.
- Editable catalog stored in settings: flexible, but creates a second source of truth and permits configuration to claim unsupported capabilities.

## 3. Catalog Model

Each data domain returns:

```json
{
  "key": "promotion_daily",
  "label": "Promotion daily facts",
  "source_tables": ["promotion_daily_facts"],
  "grain": ["date", "channel", "campaign_id", "unit_id", "product_id"],
  "raw_fields": [
    {"key": "ad_spend", "label": "Ad spend", "availability": "available"}
  ],
  "coverage": {
    "row_count": 0,
    "entity_count": 0,
    "start": null,
    "end": null,
    "latest_update": null
  },
  "availability": "no-data",
  "derived_metrics": [
    {
      "key": "ad_roi",
      "formula": "attributed_payment_amount / ad_spend",
      "dependencies": ["attributed_payment_amount", "ad_spend"],
      "availability": "no-data"
    }
  ],
  "consumer_pages": ["promotion", "overview", "product-detail"],
  "capabilities": ["trend", "drilldown", "export"],
  "limitations": []
}
```

Top-level response fields:

- `summary`: total domains and counts by `available`, `partial`, `no-data`, and `source-unavailable`.
- `domains`: all defined domains, including unavailable domains.
- `unsupported_capabilities`: profit, inventory, user cohort, strict causal attribution, and complete market opportunity analysis, each with its missing prerequisite.
- Standard response context: `capabilities`, `filters`, `missing_fields`, `missing_ranges`, and `source_batches`.

## 4. Initial Domains

The catalog covers the current operating loop:

| Domain | Primary evidence | Main consumers |
|---|---|---|
| Store daily | `store_daily_facts` | Overview, goals, comparison |
| Product master | `products` | Products, product detail, lifecycle |
| Product daily | `daily_data` | Products, product detail, actions |
| Product weekly | `weekly_data` | Comparison, reviews, actions |
| Product monthly | `monthly_data` | Products, lifecycle, promotion summaries |
| Promotion daily | `promotion_daily_facts` | Promotion, overview, product detail |
| Reviews | `reviews`, `review_summary` | Product detail, reviews |
| Product health | `product_health` | Products, overview |
| Lifecycle | `lifecycle_profiles`, `lifecycle_history` | Lifecycle, product detail |
| Actions | `product_actions`, legacy read history | Reviews, product detail, overview |
| Goals | goal and lock/version tables | Goals, overview |
| Imports | `import_batches`, audit records | Data Center |
| Market | current market/keyword tables | Data Center only until sufficient |

An absent table yields `source-unavailable`. An existing empty table yields `no-data`. A populated domain with incomplete required fields or coverage yields `partial` or `missing-fields`, never `available` by default.

## 5. Metric Ownership

`services/metric_definitions.py` remains the sole calculation registry. Phase 2 adds display metadata to that module without duplicating formulas in the capability service:

- label
- dependencies
- formula text
- unit
- aggregation rule

Existing `derive_metrics()` behavior remains compatible. The catalog evaluates metric availability from live domain evidence; it does not recalculate page values.

## 6. API

Add `GET /api/data-capabilities`.

Supported filters:

- `domain`: exact domain key
- `availability`: exact availability state

Response capabilities:

- `can_export`: true when at least one domain is returned
- `can_view_schema`: true
- `can_edit_catalog`: false
- `can_design_pages`: true when at least one returned domain is `available` or `partial`

The endpoint is read-only. It has no mutation route because the catalog describes evidence, not user preference.

## 7. Data Center Surface

Add an unframed “Data capability map” section above import operations. It contains:

- Compact summary counters for available, partial, unavailable, and unsupported capabilities.
- Availability filter and domain search.
- One table with domain, grain, coverage, available raw fields, derived metrics, consumer pages, and limitations.
- A detail drawer (`data-modal-kind="detail"`) for field dependencies, formula text, source tables, source batches, and limitations.

The section is operational, not explanatory marketing content. Empty and error states use the existing `DemoApi.renderDataState()` helper. Unsupported capabilities remain visible as explicit boundaries and cannot be clicked as if implemented.

## 8. Data Flow

```text
semantic domain definitions + canonical metric metadata
                         |
                         v
database schema and live coverage inspection
                         |
                         v
GET /api/data-capabilities
                         |
                         v
Data Center summary -> domain table -> evidence detail drawer
```

No page consumes this endpoint to decide its runtime controls in Phase 2. Existing domain APIs remain the authority for request-specific capabilities. The catalog is the design and governance view; request-level envelopes are the execution view.

## 9. Error Handling

- One broken domain inspection does not fail the whole catalog; that domain returns `source-unavailable` with a concise limitation.
- Database connection failure returns the existing error envelope.
- Unknown filters return `VALIDATION_ERROR` rather than silently returning an empty catalog.
- Missing or zero denominators mark the affected metric `insufficient-data`.
- Source batches are returned only when they can be tied to the selected domain.

## 10. Testing

Backend tests must prove:

- Empty schema reports `no-data`, not `available`.
- Seeded facts produce correct row/entity/date coverage.
- Derived metric metadata comes from the canonical registry.
- Missing dependencies downgrade only affected metrics.
- Unsupported capabilities and their prerequisites are always present.
- Domain and availability filters validate and filter deterministically.

Frontend contract and browser tests must prove:

- Data Center loads `/api/data-capabilities`.
- Summary, filters, domain rows, and limitations render without fabricated values.
- Detail drawer declares `data-modal-kind="detail"`, closes correctly, and restores focus.
- `no-data`, `partial`, and API failure states remain distinct.

## 11. Non-Goals

- No new profit, cost, inventory, customer-level, or market facts.
- No editable formulas or catalog definitions.
- No automatic page generation.
- No replacement of request-specific capability flags.
- No multi-store permission model.

## 12. Acceptance Criteria

- One API response can answer which source data exists, its grain and coverage, what can be derived, and which pages consume it.
- Every catalog claim is backed by either a semantic definition or live database evidence.
- Empty and missing sources are visible and never promoted to available capabilities.
- The Data Center exposes the catalog without weakening the existing import workflow.
- Existing Phase 1 metric, API, navigation, and action contracts remain green.
