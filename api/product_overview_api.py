"""Product overview rule cards and auditable segment results."""

from flask import Blueprint, request

from api.api_response import evidence_level_for, failure, limitations_for, success
from db import get_db
from services.category_mode_service import category_filters_from_request
from services.product_rules_service import evaluate_rule, list_rules


product_overview_bp = Blueprint("product_overview", __name__)


def _period():
    period = request.args.get("period", "").strip()
    with get_db() as conn:
        if period:
            return period
        row = conn.execute("SELECT MAX(month) AS period FROM monthly_data").fetchone()
        return (row["period"] if row else None) or ""


@product_overview_bp.get("/api/product-overview/rules")
def product_overview_rules():
    rules = list_rules()
    return success(
        {"rules": rules, "rule_version": "2026.09"},
        evidence=[{"source": "product_rules_service", "row_count": len(rules), "version": "2026.09"}],
    )


@product_overview_bp.get("/api/product-overview/rule-results")
def product_overview_rule_results():
    period = _period()
    status = (request.args.get("status") or "active").strip()
    category_filters = category_filters_from_request()
    if not period:
        return success(
            {"period": None, "rules": [], "eligible_count": 0},
            availability="no-data",
            evidence_level="insufficient",
            limitations=["monthly_data 当前没有可用周期"],
            evidence=[{"source": "monthly_data", "row_count": 0}],
        )

    where = ["d.product_id IS NOT NULL"]
    params = [period]
    if status != "all":
        where.append("COALESCE(p.status, 'active') = ?")
        params.append(status)
    if category_filters.get("shop_label"):
        where.append("(p.shop_label = ? OR instr(',' || p.shop_label || ',', ',' || ? || ',') > 0)")
        params.extend([category_filters["shop_label"], category_filters["shop_label"]])

    with get_db() as conn:
        rows = conn.execute(
            f"""
            SELECT p.product_id, d.payment_amount, d.refund_amount,
                   d.ad_spend, d.payment_conversion, d.cart_rate,
                   d.avg_order_value, d.visitors
              FROM products p
              INNER JOIN monthly_data d ON d.product_id = p.product_id AND d.month = ?
             WHERE {' AND '.join(where)}
            """,
            params,
        ).fetchall()

    result_rows = [dict(row) for row in rows]
    eligible_count = len(result_rows)
    results = []
    for rule in list_rules():
        matched = []
        not_computable = []
        evidence_examples = []
        for row in result_rows:
            payment = row.get("payment_amount")
            refund = row.get("refund_amount")
            spend = row.get("ad_spend")
            visitors = row.get("visitors")
            buyers = row.get("buyers")
            conversion = row.get("payment_conversion")
            cart_rate = row.get("cart_rate")
            aov = row.get("avg_order_value")
            metrics = {
                "payment_amount": payment,
                "refund_amount": refund,
                "successful_refund_amount": refund,
                "ad_spend": spend,
                "product_visitors": visitors,
                "payment_buyers": buyers,
                "cart_rate": cart_rate,
                "refund_rate": (float(refund) / float(payment)) if payment not in (None, 0) and refund is not None else None,
                "net_sales": (float(payment) - float(refund)) if payment is not None and refund is not None else None,
                "expense_ratio": ((float(spend) / (float(payment) - float(refund)))
                                  if payment is not None and refund is not None
                                  and float(payment) - float(refund) > 0 and spend is not None else None),
                "payment_conversion_rate": conversion,
                "average_order_value": aov if aov is not None else ((float(payment) / float(buyers)) if payment is not None and buyers not in (None, 0) else None),
            }
            evaluation = evaluate_rule(rule["key"], metrics, has_facts=True)
            if evaluation and evaluation.get("status") == "not-computable":
                not_computable.append(row["product_id"])
            if evaluation and evaluation.get("matched"):
                matched.append(row["product_id"])
                if len(evidence_examples) < 5:
                    evidence_examples.append({"product_id": row["product_id"], "checks": evaluation.get("checks", [])})
        count = len(matched)
        results.append(
            {
                **rule,
                "period": period,
                "matched_count": count,
                "eligible_count": eligible_count,
                "share": count / eligible_count if eligible_count else None,
                "matched_product_ids": matched,
                "availability": "available" if eligible_count else "no-data",
                "not_computable_count": len(not_computable),
                "not_computable_product_ids": not_computable[:20],
                "evidence_examples": evidence_examples,
                "evidence_summary": {
                    "source": "monthly_data",
                    "grain": "product-month",
                    "period": period,
                    "matched_product_count": count,
                    "eligible_product_count": eligible_count,
                    "coverage": "full" if eligible_count else "none",
                    "not_computable_product_count": len(not_computable),
                },
            }
        )

    availability = "available" if eligible_count else "no-data"
    missing_inputs = [] if eligible_count else ["monthly_data"]
    return success(
        {"period": period, "rules": results, "eligible_count": eligible_count, "scope": {"status": status, **category_filters}},
        availability=availability,
        evidence_level=evidence_level_for(availability, missing_inputs=missing_inputs),
        missing_inputs=missing_inputs,
        limitations=limitations_for(availability, missing_inputs=missing_inputs),
        freshness={"period": period, "status": status, **category_filters},
        evidence=[{"source": "monthly_data", "row_count": eligible_count}],
    )


@product_overview_bp.get("/api/product-overview/matrix")
def product_overview_matrix():
    """货品矩阵地图：单品自动分层（引流/利润/动销）+ 四象限散点数据。

    口径（2026-10-02 用户拍板）：费比 = 推广花费 ÷ GSV；引流款费比≥30%、
    利润款>0 且费比<10%、动销款有动销无花费；亏损与角色正交（loss 标志）。
    """
    from services.product_matrix_service import product_matrix
    period = request.args.get("period", "").strip() or None
    category_filters = category_filters_from_request()
    with get_db() as conn:
        matrix = product_matrix(conn, period, category_label=category_filters.get("shop_label"))
    availability = "available" if matrix.get("available") else "no-data"
    missing_inputs = matrix.get("missing_inputs") or ([] if availability == "available" else ["daily_data"])
    return success(
        matrix,
        availability=availability,
        evidence_level=evidence_level_for(availability, missing_inputs=missing_inputs),
        missing_inputs=missing_inputs,
        limitations=limitations_for(availability, missing_inputs=missing_inputs),
        freshness={"period": matrix.get("month"), **category_filters},
        evidence=[{"source": "daily_data", "period": matrix.get("month"),
                   "row_count": len(matrix.get("items") or [])}],
    )


@product_overview_bp.post("/api/product-overview/matrix/apply-tier")
def product_overview_matrix_apply():
    """把算法分层写回 products.tier：仅覆盖空值或算法自填（tier_source=matrix）的行。"""
    from services.product_matrix_service import apply_tier_writeback, product_matrix
    period = request.args.get("period", "").strip() or None
    category_filters = category_filters_from_request()
    with get_db() as conn:
        matrix = product_matrix(conn, period, category_label=category_filters.get("shop_label"))
        if not matrix.get("available"):
            return failure("NO_DATA", "当前周期没有可分层的商品数据", status=422)
        result = apply_tier_writeback(conn, matrix)
        conn.commit()
    return success(
        {"period": matrix.get("month"), **result},
        evidence=[{"source": "products.tier", "period": matrix.get("month"),
                   "updated": result.get("updated", 0)}],
    )
