"""Product identity resolution shared by imports, APIs, and audits."""

from __future__ import annotations

from collections.abc import Iterable


SOURCE_PROMOTION = "promotion"


def _clean(value) -> str:
    return str(value or "").strip()


def classify_external_product(
    connection,
    *,
    shop_id: str,
    external_product_id: str,
    source_system: str = SOURCE_PROMOTION,
) -> dict:
    """Resolve an external ID without creating a product master row."""
    external_product_id = _clean(external_product_id)
    shop_id = _clean(shop_id) or "default"
    source_system = _clean(source_system) or SOURCE_PROMOTION
    product = connection.execute(
        "SELECT product_id, title, image_url FROM products WHERE product_id = ?",
        (external_product_id,),
    ).fetchone()
    if product:
        return {
            "identity_status": "catalog_linked",
            "canonical_product_id": product["product_id"],
            "display_title": product["title"] or "",
            "image_url": product["image_url"] or "",
            "resolution_reason": "products.product_id matched",
        }
    if external_product_id.startswith("-") and external_product_id[1:].isdigit():
        status = "non_product_identifier"
        reason = "negative identifier from external report"
    elif external_product_id == shop_id:
        status = "shop_identifier"
        reason = "identifier equals shop scope"
    else:
        status = "unresolved"
        reason = "no local catalog match"
    title = ""
    image_url = ""
    edge = connection.execute(
        """SELECT product_name, image_url FROM promotion_campaign_items
           WHERE shop_id = ? AND product_id = ?
           ORDER BY updated_at DESC LIMIT 1""",
        (shop_id, external_product_id),
    ).fetchone()
    if edge:
        title = _clean(edge["product_name"])
        image_url = _clean(edge["image_url"])
        if status == "unresolved":
            status = "external_only"
            reason = "promotion campaign mapping exists without catalog match"
    if not title:
        creative = connection.execute(
            """SELECT product_name, image_url FROM promotion_creatives
               WHERE shop_id = ? AND product_id = ?
               ORDER BY updated_at DESC LIMIT 1""",
            (shop_id, external_product_id),
        ).fetchone()
        if creative:
            title = _clean(creative["product_name"])
            image_url = image_url or _clean(creative["image_url"])
            if status == "unresolved":
                status = "external_only"
                reason = "promotion creative mapping exists without catalog match"
    return {
        "identity_status": status,
        "canonical_product_id": None,
        "display_title": title or external_product_id,
        "image_url": image_url,
        "resolution_reason": reason,
    }


def upsert_identity_rows(connection, rows: Iterable[dict]) -> int:
    count = 0
    for row in rows:
        connection.execute(
            """INSERT INTO product_identity_map
               (shop_id, source_system, external_product_id, canonical_product_id,
                identity_status, display_title, image_url, first_seen_date, last_seen_date,
                fact_row_count, ad_spend, attributed_payment_amount,
                first_source_batch_id, last_source_batch_id, resolution_reason, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
               ON CONFLICT(shop_id, source_system, external_product_id) DO UPDATE SET
                 canonical_product_id=excluded.canonical_product_id,
                 identity_status=excluded.identity_status,
                 display_title=CASE WHEN excluded.display_title != '' THEN excluded.display_title ELSE product_identity_map.display_title END,
                 image_url=CASE WHEN excluded.image_url != '' THEN excluded.image_url ELSE product_identity_map.image_url END,
                 first_seen_date=CASE WHEN product_identity_map.first_seen_date IS NULL OR excluded.first_seen_date < product_identity_map.first_seen_date THEN excluded.first_seen_date ELSE product_identity_map.first_seen_date END,
                 last_seen_date=CASE WHEN product_identity_map.last_seen_date IS NULL OR excluded.last_seen_date > product_identity_map.last_seen_date THEN excluded.last_seen_date ELSE product_identity_map.last_seen_date END,
                 fact_row_count=excluded.fact_row_count,
                 ad_spend=excluded.ad_spend,
                 attributed_payment_amount=excluded.attributed_payment_amount,
                 first_source_batch_id=COALESCE(excluded.first_source_batch_id, product_identity_map.first_source_batch_id),
                 last_source_batch_id=COALESCE(excluded.last_source_batch_id, product_identity_map.last_source_batch_id),
                 resolution_reason=excluded.resolution_reason,
                 updated_at=CURRENT_TIMESTAMP""",
            (
                row["shop_id"], row["source_system"], row["external_product_id"],
                row.get("canonical_product_id"), row["identity_status"],
                row.get("display_title", ""), row.get("image_url", ""),
                row.get("first_seen_date"), row.get("last_seen_date"),
                row.get("fact_row_count", 0), row.get("ad_spend", 0),
                row.get("attributed_payment_amount", 0),
                row.get("first_source_batch_id"), row.get("last_source_batch_id"),
                row.get("resolution_reason", ""),
            ),
        )
        count += 1
    return count


def refresh_promotion_identities(connection, *, shop_id: str, product_ids: Iterable[str]) -> int:
    """Refresh identity records for product IDs seen by a promotion import."""
    ids = sorted({_clean(value) for value in product_ids if _clean(value)})
    if not ids:
        return 0
    placeholders = ",".join("?" for _ in ids)
    facts = connection.execute(
        f"""SELECT product_id, COUNT(*) AS fact_row_count, MIN(date) AS first_seen_date,
                   MAX(date) AS last_seen_date, SUM(COALESCE(ad_spend, 0)) AS ad_spend,
                   SUM(COALESCE(attributed_payment_amount, 0)) AS attributed_payment_amount,
                   MIN(NULLIF(source_batch_id, '')) AS first_source_batch_id,
                   MAX(NULLIF(source_batch_id, '')) AS last_source_batch_id
            FROM promotion_daily_facts
            WHERE shop_id = ? AND grain = 'product' AND product_id IN ({placeholders})
            GROUP BY product_id""",
        [shop_id, *ids],
    ).fetchall()
    rows = []
    for fact in facts:
        resolution = classify_external_product(
            connection,
            shop_id=shop_id,
            external_product_id=fact["product_id"],
        )
        rows.append({
            "shop_id": shop_id,
            "source_system": SOURCE_PROMOTION,
            "external_product_id": fact["product_id"],
            **resolution,
            "first_seen_date": fact["first_seen_date"],
            "last_seen_date": fact["last_seen_date"],
            "fact_row_count": int(fact["fact_row_count"] or 0),
            "ad_spend": float(fact["ad_spend"] or 0),
            "attributed_payment_amount": float(fact["attributed_payment_amount"] or 0),
            "first_source_batch_id": fact["first_source_batch_id"],
            "last_source_batch_id": fact["last_source_batch_id"],
        })
    return upsert_identity_rows(connection, rows)


def list_identity_candidates(
    connection,
    *,
    shop_id: str,
    status: str = "unresolved",
    limit: int = 100,
    offset: int = 0,
) -> dict:
    """Return promotion identities that still need an explicit operator decision."""
    shop_id = _clean(shop_id) or "default"
    status = _clean(status)
    allowed_statuses = {"unresolved", "external_only", "all"}
    if status not in allowed_statuses:
        raise ValueError("status must be unresolved, external_only, or all")
    limit = max(1, min(int(limit), 500))
    offset = max(0, int(offset))
    where = "shop_id = ? AND source_system = 'promotion'"
    params: list[object] = [shop_id]
    if status != "all":
        where += " AND identity_status = ?"
        params.append(status)
    total = connection.execute(
        f"SELECT COUNT(*) FROM product_identity_map WHERE {where}", params
    ).fetchone()[0]
    rows = connection.execute(
        f"""SELECT external_product_id, canonical_product_id, identity_status,
                   display_title, image_url, first_seen_date, last_seen_date,
                   fact_row_count, ad_spend, attributed_payment_amount,
                   first_source_batch_id, last_source_batch_id, resolution_reason,
                   updated_at
            FROM product_identity_map
            WHERE {where}
            ORDER BY fact_row_count DESC, ad_spend DESC, external_product_id
            LIMIT ? OFFSET ?""",
        [*params, limit, offset],
    ).fetchall()
    items = []
    for row in rows:
        item = dict(row)
        evidence = connection.execute(
            """SELECT
                 (SELECT COUNT(*) FROM promotion_campaign_items
                    WHERE shop_id = ? AND product_id = ?) AS campaign_item_count,
                 (SELECT COUNT(*) FROM promotion_creatives
                    WHERE shop_id = ? AND product_id = ?) AS creative_count""",
            (shop_id, row["external_product_id"], shop_id, row["external_product_id"]),
        ).fetchone()
        item["evidence"] = {
            "campaign_item_count": int(evidence["campaign_item_count"] or 0),
            "creative_count": int(evidence["creative_count"] or 0),
        }
        items.append(item)
    return {
        "items": items,
        "total": int(total or 0),
        "limit": limit,
        "offset": offset,
        "shop_id": shop_id,
        "status": status,
    }


def resolve_identity(
    connection,
    *,
    shop_id: str,
    external_product_id: str,
    canonical_product_id: str,
    operator: str,
    reason: str,
) -> dict:
    """Bind an external promotion ID to an existing catalog product only."""
    shop_id = _clean(shop_id) or "default"
    external_product_id = _clean(external_product_id)
    canonical_product_id = _clean(canonical_product_id)
    if not external_product_id or not canonical_product_id:
        raise ValueError("external_product_id and canonical_product_id are required")
    product = connection.execute(
        "SELECT product_id, title, image_url FROM products WHERE product_id = ?",
        (canonical_product_id,),
    ).fetchone()
    if product is None:
        raise LookupError("canonical product does not exist")
    current = connection.execute(
        """SELECT * FROM product_identity_map
           WHERE shop_id = ? AND source_system = 'promotion'
             AND external_product_id = ?""",
        (shop_id, external_product_id),
    ).fetchone()
    if current is None:
        raise LookupError("external identity does not exist")
    before = dict(current)
    resolution_reason = f"manual mapping by {operator}: {reason}"
    connection.execute(
        """UPDATE product_identity_map
           SET canonical_product_id = ?, identity_status = 'catalog_linked',
               display_title = ?, image_url = ?, resolution_reason = ?,
               updated_at = CURRENT_TIMESTAMP
           WHERE shop_id = ? AND source_system = 'promotion'
             AND external_product_id = ?""",
        (
            canonical_product_id,
            product["title"] or canonical_product_id,
            product["image_url"] or "",
            resolution_reason,
            shop_id,
            external_product_id,
        ),
    )
    after = dict(connection.execute(
        """SELECT * FROM product_identity_map
           WHERE shop_id = ? AND source_system = 'promotion'
             AND external_product_id = ?""",
        (shop_id, external_product_id),
    ).fetchone())
    return {"before": before, "after": after}
