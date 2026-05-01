from fastapi import APIRouter
from sqlalchemy import func, desc
from app.core.database import get_db
from app.models.product import Product, WeeklyData

router = APIRouter(prefix="/dashboard", tags=["dashboard"])

@router.get("/summary")
def get_dashboard_summary():
    db = next(get_db())
    try:
        latest_week = db.query(WeeklyData).order_by(desc(WeeklyData.week_start)).first()
        if not latest_week:
            return {
                "code": 200,
                "data": {
                    "total_gmv": 0,
                    "total_visitors": 0,
                    "avg_conversion": 0,
                    "avg_roi": 0,
                    "product_count": 0
                }
            }

        week_data = db.query(WeeklyData).filter(
            WeeklyData.week_start == latest_week.week_start
        ).all()

        total_gmv = sum(w.net_sales for w in week_data)
        total_visitors = sum(w.visitors for w in week_data)
        valid_conversions = [w.payment_conversion for w in week_data if w.payment_conversion]
        avg_conversion = sum(valid_conversions) / len(valid_conversions) if valid_conversions else 0
        valid_rois = [w.total_roi for w in week_data if w.total_roi]
        avg_roi = sum(valid_rois) / len(valid_rois) if valid_rois else 0
        product_count = len(set(w.product_id for w in week_data))

        return {
            "code": 200,
            "data": {
                "total_gmv": total_gmv,
                "total_visitors": total_visitors,
                "avg_conversion": avg_conversion,
                "avg_roi": avg_roi,
                "product_count": product_count
            }
        }
    except Exception as e:
        return {
            "code": 500,
            "message": str(e),
            "data": None
        }
    finally:
        db.close()

@router.get("/top-products")
def get_top_products():
    db = next(get_db())
    try:
        latest_week = db.query(WeeklyData).order_by(desc(WeeklyData.week_start)).first()
        if not latest_week:
            return {"code": 200, "data": []}

        week_data = db.query(WeeklyData).filter(
            WeeklyData.week_start == latest_week.week_start
        ).order_by(desc(WeeklyData.net_sales)).limit(10).all()

        product_ids = [w.product_id for w in week_data]
        products = db.query(Product).filter(Product.product_id.in_(product_ids)).all()
        product_map = {p.product_id: p for p in products}

        result = []
        for w in week_data:
            product = product_map.get(w.product_id)
            result.append({
                "product_id": w.product_id,
                "title": product.title if product else None,
                "tier": product.tier if product else None,
                "net_sales": w.net_sales,
                "visitors": w.ipv,
                "conversion": w.payment_conversion,
                "roi": w.ad_roi,
                "ad_spend": w.ad_spend
            })
        return {"code": 200, "data": result}
    except Exception as e:
        return {"code": 500, "message": str(e), "data": []}
    finally:
        db.close()

@router.get("/quadrant")
def get_quadrant_data():
    db = next(get_db())
    try:
        latest_week = db.query(WeeklyData).order_by(desc(WeeklyData.week_start)).first()
        if not latest_week:
            return {"code": 200, "data": {"products": [], "quadrants": {}}}

        week_data = db.query(WeeklyData).filter(
            WeeklyData.week_start == latest_week.week_start
        ).all()

        product_ids = [w.product_id for w in week_data]
        products = db.query(Product).filter(Product.product_id.in_(product_ids)).all()
        product_map = {p.product_id: p for p in products}

        gmv_list = [w.net_sales for w in week_data if w.net_sales > 0 and w.ad_roi > 0]
        roi_list = [w.ad_roi for w in week_data if w.net_sales > 0 and w.ad_roi > 0]

        if not gmv_list or not roi_list:
            return {"code": 200, "data": {"products": [], "quadrants": {}}}

        gmv_sorted = sorted(gmv_list)
        roi_sorted = sorted(roi_list)
        gmv_mid = gmv_sorted[len(gmv_sorted) // 2]
        roi_mid = roi_sorted[len(roi_sorted) // 2]

        products_list = []
        quadrants = {"star": [], "cash_cow": [], "question": [], "dog": []}

        for w in week_data:
            if not w.net_sales or not w.ad_roi:
                continue
            product = product_map.get(w.product_id)
            if not product:
                continue
            gmv = w.net_sales
            roi = w.ad_roi
            quadrant = "star"
            if gmv >= gmv_mid and roi >= roi_mid:
                quadrant = "star"
            elif gmv >= gmv_mid and roi < roi_mid:
                quadrant = "cash_cow"
            elif gmv < gmv_mid and roi >= roi_mid:
                quadrant = "question"
            else:
                quadrant = "dog"
            product_info = {
                "product_id": w.product_id,
                "title": product.title,
                "tier": product.tier,
                "gmv": gmv,
                "roi": roi,
                "quadrant": quadrant
            }
            products_list.append(product_info)
            quadrants[quadrant].append(product_info)

        return {"code": 200, "data": {
            "products": products_list,
            "quadrants": quadrants,
            "gmv_mid": gmv_mid,
            "roi_mid": roi_mid
        }}
    except Exception as e:
        return {"code": 500, "message": str(e), "data": {"products": [], "quadrants": {}}}
    finally:
        db.close()
