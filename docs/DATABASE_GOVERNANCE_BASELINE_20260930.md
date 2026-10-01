# Database Governance Baseline (2026-09-30)

This baseline records the read-only database review performed against the local SQLite database on 2026-09-30. It is an operational reference, not a cleanup authorization.

## Reproduce the Baseline

Run these commands from the repository root. The commands below are read-only; write reports outside the repository when possible.

```powershell
python scripts/db_inventory.py --database data/dashboard.db --output $env:TEMP\tmall-db-inventory.json
python scripts/db_maintenance.py --database data/dashboard.db --output $env:TEMP\tmall-db-maintenance.json
python scripts/db_quality_check.py --database data/dashboard.db --output $env:TEMP\tmall-db-quality.json --as-of-date 2026-09-30
python scripts/schema_baseline.py --database data/dashboard.db --output $env:TEMP\tmall-schema-baseline.json
```

For query-plan checks, use a read-only SQLite connection and `EXPLAIN QUERY PLAN`. Do not run `DELETE`, `VACUUM`, or retention enforcement as part of this baseline.

## Storage and Schema Snapshot

- Database: `data/dashboard.db`
- Size: approximately 3.62 GiB
- SQLite journal mode: `WAL`
- SQLite `user_version`: `4`
- Tables discovered: `85`
- Runtime tables classified by the schema baseline: `15`
- Migration records: `4`, all applied
- SQLite integrity check: `ok`
- Freelist pages: `159,580`; this is a growth signal, not permission to vacuum
- Verified archive catalog records: `1`

The schema inventory found 14 tables that are present in the database but are not declared by the current `db.py` table parser. Ownership classification (2026-09-30): all 14 are registered in `scripts/schema_baseline.py` `RUNTIME_TABLES` with domain/owner/lifecycle metadata, and `db_quality_check.py` treats registered runtime tables as owned tables, not schema drift. They are covered by the existing retention/archive policies where applicable (`bi_product_daily_raw` is in the 180-day archive policy). Do not drop or recreate them based only on this report.

## Fact Table Inventory

| Domain | Primary table(s) | Grain and scope | Current observation |
| --- | --- | --- | --- |
| Daily product facts | `daily_data` | One product/date/shop row | Production data is scoped to shop `3828498662`; business-key duplicate check passed |
| Store daily facts | `store_daily_facts` | One shop/date row | Production data is scoped to shop `3828498662`; business-key duplicate check passed |
| Promotion facts | `promotion_daily_facts` | Shop/date plus channel/campaign/unit/product grain | Grain values are nonblank; business-key duplicate check passed |
| Monthly facts | `monthly_data` | Product/month row without a shop key | Must remain default-single-shop only unless a shop key is introduced |
| Observations | `daily_data_observations` | Source observation for product/date/shop | Protected from routine deletion |
| Field lineage | `fact_field_lineage` | Field-level provenance for product/date/shop | Protected from routine deletion |
| Collector staging | `collector_data_staging` | Source batch/unit payload | 239,873 published rows; none older than the 14-day retention cutoff |
| Collector runtime | `collector_runs`, `collector_artifacts`, `collector_checkpoints` | Run/artifact/checkpoint lifecycle | No stale runs or missing artifact files in the audit |

## Retention and Archive Findings

The dry-run maintenance report found no eligible rows under current policies:

- `collector_data_staging`: 14-day `purge_after_archive`, 0 eligible rows
- `collector_artifacts`: 30-day archive policy, 0 eligible rows
- `collector_checkpoints`: 30-day compact policy, 0 eligible rows
- `monthly_source_payload`: 180-day archive policy, 0 eligible rows
- `bi_product_daily_raw`: 180-day archive policy, 0 eligible rows

The report performed no deletion, archive mutation, or vacuum. Continue to require an archive target, row-count verification, SHA-256 catalog record, and explicit backup before applying retention.

## Quality Findings

The quality audit passed integrity, schema alignment, future-fact checks, duplicate business-key checks, staging retention, collector-run health, collector-artifact presence, shop-scope checks, and query-statistics checks.

The audit still returned `error` because five rows in `product_action_history` reference action IDs that are no longer present in `product_actions`:

- Orphan history row IDs: `6` through `10`
- The rows are historical `draft`/`blocked` transitions created on 2026-09-29
- `product_actions` currently contains no rows

Do not delete these history rows or recreate parent actions automatically. They are historical evidence. The next safe action is an explicit reconciliation decision: either preserve them as an archived legacy-history exception or restore valid parent records from a trusted export, with an audit record for whichever choice is made.

The audit also reported 263 unresolved product-grain promotion rows. The broader 1,550-row promotion linkage count includes non-product grains and identifiers classified as external-only, shop identifiers, negative identifiers, or unresolved. Only the 263 product-grain rows are a direct product-identity warning. Resolve them through `product_identity_map` or catalog backfill; do not fabricate rows in `products` from an unverified promotion identifier.

## Query-Plan Baseline

The following representative queries were checked on the production database:

- Store overview by shop/date: uses the unique `(shop_id, date)` index
- Product daily overview by shop/date: uses `idx_daily_date` and the product primary-key index
- Promotion trend by shop/date: uses the promotion fact primary-key index
- Promotion product detail: uses promotion and daily-fact indexes; temporary B-tree for the expected product aggregation
- New-products aggregation: uses promotion and product indexes; temporary B-tree for the expected grouping
- Monthly breakdown: uses `idx_monthly_month` and product primary-key index; temporary B-trees for grouping and ordering

No representative query performed an unindexed full table scan. The temporary B-trees are caused by aggregation/order operations and are not, by themselves, evidence for adding an index. Any new index must be justified by a measured query and write/storage tradeoff.

## Next Safe Database Work

1. ~~Classify the 14 undeclared tables by owner, lifecycle, and retention policy.~~ Done 2026-09-30: all 14 are registered runtime tables in `scripts/schema_baseline.py` `RUNTIME_TABLES`; quality checks exclude them from schema-drift errors.
2. Decide how to represent the five orphan action-history rows without deleting evidence.
3. Decide the disposition of the 151 unresolved external product identities (263 product-grain rows); remediation preview is available via `python -m scripts.backfill_product_identity_map --database data/dashboard.db --output <temp>`.
4. Add one low-risk, repeatable schema migration only after the ownership decision is recorded.
5. Re-run the read-only inventory, quality audit, and query-plan baseline after each database change.

Do not introduce PostgreSQL/DuckDB, run a production vacuum, clear lineage/observations, or apply retention solely from this baseline.
