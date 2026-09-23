"""Unified project data-source integration API."""

from flask import Blueprint, current_app, request

from api.api_response import failure, success
from services.data_integration_service import (
    INTEGRATION_SOURCES,
    READINESS_LABELS,
    build_integration_catalog,
)


data_integration_bp = Blueprint("data_integration", __name__)


@data_integration_bp.route("/api/data-integration/catalog", methods=["GET"])
def get_data_integration_catalog():
    """Return the cross-project source registry merged with live collector state."""
    domain = request.args.get("domain") or None
    readiness = request.args.get("readiness") or None
    accepted_domains = sorted({item["domain"] for item in INTEGRATION_SOURCES})
    if domain and domain not in accepted_domains:
        return failure("VALIDATION_ERROR", "未知业务域", {"domain": domain, "accepted": accepted_domains}, status=422)
    if readiness and readiness not in READINESS_LABELS:
        return failure("VALIDATION_ERROR", "未知接入状态", {"readiness": readiness, "accepted": list(READINESS_LABELS)}, status=422)

    try:
        # Calling the view directly would create a Flask response. Keep the
        # integration API independent by reading the same durable source data.
        from api.collect_api import DATA_SOURCES, collect_tasks
        from db import get_db, get_shop_id
        from services.collector_run_service import latest_runs_by_source

        db_path = current_app.config.get("DATABASE_PATH")
        durable_runs = latest_runs_by_source(db_path=db_path, shop_id=get_shop_id())
        actual_sources = []
        with get_db(db_path) as conn:
            for key, config in DATA_SOURCES.items():
                try:
                    row = conn.execute(
                        f'SELECT MAX({config["date_col"]}) AS latest_date, COUNT(*) AS record_count FROM {config["table"]}'
                    ).fetchone()
                    live_run = durable_runs.get(key)
                    status = "idle"
                    if live_run:
                        status = live_run["status"]
                        if status in {"succeeded", "succeeded_with_warnings"}:
                            status = "completed"
                    elif collect_tasks.get(key):
                        status = collect_tasks[key].get("status", "idle")
                    actual_sources.append({
                        "key": key,
                        "latest_date": row["latest_date"],
                        "record_count": row["record_count"] or 0,
                        "status": status,
                        "run_status": live_run["status"] if live_run else None,
                        "run_id": live_run["id"] if live_run else None,
                        "last_run": (live_run.get("finished_at") or live_run.get("updated_at")) if live_run else None,
                        "last_run_record": dict(live_run) if live_run else None,
                    })
                except Exception:
                    # A missing optional table should not hide the other
                    # connectors from the unified registry.
                    actual_sources.append({"key": key, "status": "error", "latest_date": None, "record_count": 0})
        catalog = build_integration_catalog(actual_sources)
    except Exception:
        current_app.logger.exception("Unified data integration catalog failed")
        return failure("DATA_INTEGRATION_ERROR", "数据整合目录暂时不可用，请稍后重试", status=500)

    if domain:
        catalog["sources"] = [item for item in catalog["sources"] if item["domain"] == domain]
    if readiness:
        catalog["sources"] = [item for item in catalog["sources"] if item["readiness"] == readiness]
    catalog["domains"] = sorted({item["domain"] for item in catalog["sources"]})
    catalog["filters"] = {key: value for key, value in (("domain", domain), ("readiness", readiness)) if value}
    return success(catalog, evidence=[{"source": "data_integration_registry", "count": len(catalog["sources"])}])
