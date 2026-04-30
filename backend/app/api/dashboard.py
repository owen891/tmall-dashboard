from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import desc

from app.core import get_db
from app.models import Product, WeeklyData
from app.schemas import ResponseModel
from app.services import ProductService

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


@router.get("/summary", response_model=ResponseModel)
def get_dashboard_summary(db: Session = Depends(get_db)):
    service = ProductService(db)
    summary = service.get_dashboard_summary()
    return ResponseModel(data=summary)


@router.get("/top-products", response_model=ResponseModel)
def get_top_products(db: Session = Depends(get_db)):
    latest_week = db.query(WeeklyData).order_by(desc(WeeklyData.week_start)).first()
    
    if not latest_week:
        return ResponseModel(data=[])
    
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
            "visitors": w.visitors,
            "conversion": w.payment_conversion,
            "roi": w.total_roi,
            "ad_spend": w.ad_spend
        })
    
    return ResponseModel(data=result)


@router.get("/quadrant", response_model=ResponseModel)
def get_quadrant_data(db: Session = Depends(get_db)):
    latest_week = db.query(WeeklyData).order_by(desc(WeeklyData.week_start)).first()
    
    if not latest_week:
        return ResponseModel(data={"products": [], "quadrants": {}})
    
    week_data = db.query(WeeklyData).filter(
        WeeklyData.week_start == latest_week.week_start
    ).all()
    
    product_ids = [w.product_id for w in week_data]
    products = db.query(Product).filter(Product.product_id.in_(product_ids)).all()
    product_map = {p.product_id: p for p in products}
    
    products_list = []
    quadrants = {
        "star": [],
        "cash_cow": [],
        "question": [],
        "dog": []
    }
    
    all_gmv = [w.net_sales for w in week_data if w.net_sales > 0]
    all_roi = [w.total_roi for w in week_data if w.total_roi > 0]
    
    gmv_mid = sorted(all_gmv)[len(all_gmv) // 2] if all_gmv else 0
    roi_mid = sorted(all_roi)[len(all_roi) // 2] if all_roi else 0
    
    for w in week_data:
        product = product_map.get(w.product_id)
        if not product:
            continue
        
        gmv = w.net_sales or 0
        roi = w.total_roi or 0
        
        quadrant = ""
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
            "title": product.title if product else None,
            "tier": product.tier if product else None,
            "gmv": gmv,
            "roi": roi,
            "quadrant": quadrant
        }
        
        products_list.append(product_info)
        quadrants[quadrant].append(product_info)
    
    return ResponseModel(data={
        "products": products_list,
        "quadrants": quadrants,
        "gmv_mid": gmv_mid,
        "roi_mid": roi_mid
    })
