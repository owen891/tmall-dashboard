from sqlalchemy.orm import Session
from sqlalchemy import func, desc, asc
from typing import Optional, List, Dict, Any, Tuple
from datetime import datetime, timedelta

from app.core.utils import DIMENSION_MAP, get_prev_period, get_latest_period, get_data_model, calc_score
from app.models import DailyData, WeeklyData, MonthlyData, Product

PRODUCT_SORTABLE_FIELDS = {
    'payment_amount', 'net_sales', 'refund_rate', 'visitors',
    'conversion', 'ad_spend', 'roi', 'title', 'refund_amount',
    'aov', 'ad_ratio', 'score',
}


class ProductService:
    def __init__(self, db: Session):
        self.db = db

    def get_products(
        self,
        dimension: str = 'weekly',
        period: Optional[str] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        tier: Optional[str] = None,
        style: Optional[str] = None,
        scene: Optional[str] = None,
        search: Optional[str] = None,
        manager: Optional[str] = None,
        status: Optional[str] = None,
        category: Optional[str] = None,
        sort_by: str = 'payment_amount',
        order: str = 'desc',
        limit: int = 20,
        offset: int = 0,
    ) -> Dict[str, Any]:
        Model, date_col, visitors_col = get_data_model(dimension)

        if not period and not start_date:
            period = get_latest_period(Model, date_col, self.db)

        if not period and not start_date:
            return {"data": [], "total": 0, "limit": limit, "offset": offset, "dimension": dimension, "period": None}

        base_cols = [
            Model.product_id,
            func.max(Product.title).label('title'),
            func.max(Product.image_url).label('image_url'),
            func.max(Product.category).label('category'),
            func.max(Product.tier).label('tier'),
            func.max(Product.style).label('style'),
            func.max(Product.scene).label('scene'),
            func.max(Product.manager).label('manager'),
            func.max(Product.list_date).label('list_date'),
            func.max(Product.status).label('status'),
            func.max(Product.starred).label('starred'),
            func.sum(Model.payment_amount).label('payment_amount'),
            func.sum(Model.refund_amount).label('refund_amount'),
            func.sum(getattr(Model, visitors_col)).label('visitors'),
            func.avg(Model.payment_conversion).label('conversion'),
            func.avg(Model.ad_roi).label('roi'),
            func.sum(Model.ad_spend).label('ad_spend'),
        ]

        query = self.db.query(*base_cols).join(Product, Model.product_id == Product.product_id)

        filter_conditions = []
        if start_date and end_date:
            filter_conditions.append(getattr(Model, date_col) >= start_date)
            filter_conditions.append(getattr(Model, date_col) <= end_date)
        elif period:
            filter_conditions.append(getattr(Model, date_col) == period)

        if tier:
            filter_conditions.append(Product.tier == tier)
        if style:
            filter_conditions.append(Product.style == style)
        if scene:
            filter_conditions.append(Product.scene == scene)
        if manager:
            filter_conditions.append(Product.manager == manager)
        if category:
            filter_conditions.append(Product.category == category)
        if search:
            filter_conditions.append(
                Product.title.ilike(f"%{search}%") | Product.product_id.ilike(f"%{search}%")
            )
        if status:
            filter_conditions.append(Product.status == status)
        else:
            filter_conditions.append(Product.status == 'active')

        query = query.filter(*filter_conditions)
        query = query.group_by(Model.product_id)
        total = query.count()

        sort_dir = desc if order == "desc" else asc
        if sort_by not in PRODUCT_SORTABLE_FIELDS:
            sort_by = 'payment_amount'
        if sort_by == 'net_sales':
            query = query.order_by(sort_dir(func.sum(Model.payment_amount) - func.sum(Model.refund_amount)))
        elif sort_by == 'refund_rate':
            query = query.order_by(sort_dir(func.sum(Model.refund_amount) / func.nullif(func.sum(Model.payment_amount), 0)))
        elif sort_by == 'visitors':
            query = query.order_by(sort_dir(func.sum(getattr(Model, visitors_col))))
        elif sort_by == 'conversion':
            query = query.order_by(sort_dir(func.avg(Model.payment_conversion)))
        elif sort_by == 'ad_spend':
            query = query.order_by(sort_dir(func.sum(Model.ad_spend)))
        elif sort_by == 'roi':
            query = query.order_by(sort_dir(func.avg(Model.ad_roi)))
        elif sort_by == 'title':
            query = query.order_by(sort_dir(func.lower(func.max(Product.title))))
        elif sort_by in ('payment_amount', 'refund_amount'):
            query = query.order_by(sort_dir(func.sum(getattr(Model, sort_by))))
        else:
            query = query.order_by(sort_dir(func.sum(Model.payment_amount)))

        products_data = query.offset(offset).limit(limit).all()

        products = []
        for p in products_data:
            payment = float(p.payment_amount or 0)
            refund = float(p.refund_amount or 0)
            visitors = int(p.visitors or 0)
            ad_spend = float(p.ad_spend or 0)
            roi = float(p.roi or 0) if p.roi else 0
            conversion = float(p.conversion or 0)

            net_sales = payment - refund
            refund_rate = (refund / payment) if payment > 0 else 0
            aov = (payment / visitors) if visitors > 0 else 0

            row_data = {
                'product_id': p.product_id,
                'title': p.title,
                'image_url': p.image_url,
                'category': p.category,
                'tier': p.tier,
                'style': p.style,
                'scene': p.scene,
                'manager': p.manager,
                'list_date': str(p.list_date) if p.list_date else None,
                'status': p.status,
                'starred': bool(p.starred) if p.starred is not None else False,
                'payment_amount': payment,
                'net_sales': net_sales,
                'refund_amount': refund,
                'refund_rate': refund_rate,
                'visitors': visitors,
                'aov': aov,
                'conversion': conversion,
                'ad_spend': ad_spend,
                'roi': roi,
                'ad_ratio': (ad_spend / payment) if payment > 0 else 0,
                'score': calc_score({'conversion': conversion, 'roi': roi, 'refund_rate': refund_rate}),
                'changes': {},
            }
            products.append(row_data)

        return {
            "data": products,
            "total": total,
            "limit": limit,
            "offset": offset,
            "dimension": dimension,
            "period": str(period) if period else None,
        }

    def get_product_detail(self, product_id: str, dimension: str = 'weekly') -> Dict[str, Any]:
        product = self.db.query(Product).filter(Product.product_id == product_id).first()
        if not product:
            return {"product": None, "trend": []}

        Model, date_col, visitors_col = get_data_model(dimension)

        data_list = self.db.query(Model).filter(
            Model.product_id == product_id
        ).order_by(desc(getattr(Model, date_col))).limit(12).all()

        trend = []
        for model_data in reversed(data_list):
            period_val = getattr(model_data, date_col)
            period_str = period_val.isoformat() if hasattr(period_val, 'isoformat') else str(period_val)

            payment = model_data.payment_amount or 0
            refund = model_data.refund_amount or 0
            visitors = getattr(model_data, visitors_col) or 0

            trend.append({
                "period": period_str,
                "payment_amount": payment,
                "net_sales": payment - refund,
                "refund_amount": refund,
                "refund_rate": round((refund / payment), 4) if payment > 0 else 0,
                "visitors": visitors,
                "aov": round((payment / visitors), 2) if visitors > 0 else 0,
                "conversion": model_data.payment_conversion,
                "ad_spend": model_data.ad_spend or 0,
                "roi": model_data.ad_roi,
            })

        return {
            "product_id": product.product_id,
            "product_name": product.title,
            "title": product.title,
            "image_url": product.image_url,
            "category": product.category,
            "tier": product.tier,
            "style": product.style,
            "scene": product.scene,
            "manager": product.manager,
            "list_date": str(product.list_date) if product.list_date else None,
            "status": product.status,
            "starred": bool(product.starred) if product.starred is not None else False,
            "trend": trend,
        }

    def get_top_products(
        self,
        dimension: str = 'weekly',
        period: Optional[str] = None,
        limit: int = 10,
    ) -> Dict[str, Any]:
        Model, date_col, visitors_col = get_data_model(dimension)

        if not period:
            period = get_latest_period(Model, date_col, self.db)

        if not period:
            return {"products": []}

        top_query = self.db.query(
            Model.product_id,
            func.max(Product.title).label('product_name'),
            func.max(Product.category).label('category'),
            func.sum(Model.payment_amount).label('payment_amount'),
            func.sum(Model.refund_amount).label('refund_amount'),
            func.sum(getattr(Model, visitors_col)).label('visitors'),
            func.avg(Model.payment_conversion).label('conversion'),
            func.sum(Model.ad_spend).label('ad_spend'),
            func.avg(Model.ad_roi).label('roi'),
        ).join(
            Product, Model.product_id == Product.product_id
        ).filter(
            getattr(Model, date_col) == period
        ).group_by(Model.product_id).order_by(
            desc(func.sum(Model.payment_amount))
        ).limit(limit).all()

        products = []
        for p in top_query:
            payment = float(p.payment_amount or 0)
            refund = float(p.refund_amount or 0)
            visitors = int(p.visitors or 0)
            ad_spend = float(p.ad_spend or 0)

            products.append({
                "product_id": p.product_id,
                "product_name": p.product_name,
                "category": p.category,
                "payment_amount": round(payment, 2),
                "value": round(payment, 2),
                "net_sales": round(payment - refund, 2),
                "refund_amount": round(refund, 2),
                "refund_rate": round((refund / payment), 4) if payment > 0 else 0,
                "visitors": visitors,
                "aov": round((payment / visitors), 2) if visitors > 0 else 0,
                "conversion": round(float(p.conversion or 0), 4),
                "ad_spend": round(ad_spend, 2),
                "roi": round(float(p.roi or 0), 2) if p.roi else 0,
                "ad_ratio": round((ad_spend / payment), 4) if payment > 0 else 0,
            })

        return {"products": products, "dimension": dimension, "period": str(period) if period else None}

    def get_filter_options(self) -> Dict[str, Any]:
        categories = self.db.query(Product.category).distinct().filter(Product.category.isnot(None)).all()
        tiers = self.db.query(Product.tier).distinct().filter(Product.tier.isnot(None)).all()
        styles = self.db.query(Product.style).distinct().filter(Product.style.isnot(None)).all()
        scenes = self.db.query(Product.scene).distinct().filter(Product.scene.isnot(None)).all()
        managers = self.db.query(Product.manager).distinct().filter(Product.manager.isnot(None)).all()

        return {
            "categories": [c[0] for c in categories if c[0]],
            "tiers": [t[0] for t in tiers if t[0]],
            "styles": [s[0] for s in styles if s[0]],
            "scenes": [s[0] for s in scenes if s[0]],
            "managers": [m[0] for m in managers if m[0]],
        }


class DashboardService:
    def __init__(self, db: Session):
        self.db = db

    def get_summary(
        self,
        dimension: str = 'weekly',
        period: Optional[str] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
    ) -> Dict[str, Any]:
        Model, date_col, visitors_col = get_data_model(dimension)

        if not period and not start_date:
            period = get_latest_period(Model, date_col, self.db)

        if not period and not start_date:
            return {"kpi": {}, "trends": []}

        period_str = str(period) if period else None
        prev_period_str = get_prev_period(period_str, dimension) if period_str else None

        base_query = self.db.query(
            func.sum(Model.payment_amount).label('total_payment'),
            func.sum(Model.refund_amount).label('total_refund'),
            func.sum(getattr(Model, visitors_col)).label('total_visitors'),
            func.sum(Model.ad_spend).label('total_ad_spend'),
            func.avg(Model.payment_conversion).label('avg_conversion'),
            func.avg(Model.ad_roi).label('avg_roi'),
        )

        if start_date and end_date:
            current_data = base_query.filter(
                getattr(Model, date_col) >= start_date,
                getattr(Model, date_col) <= end_date
            ).first()
        else:
            current_data = base_query.filter(getattr(Model, date_col) == period).first()

        if not current_data:
            return {"kpi": {}, "trends": []}

        total_payment = float(current_data.total_payment or 0)
        total_refund = float(current_data.total_refund or 0)
        total_visitors = int(current_data.total_visitors or 0)
        total_ad_spend = float(current_data.total_ad_spend or 0)
        avg_conversion = float(current_data.avg_conversion or 0)
        avg_roi = float(current_data.avg_roi or 0) if current_data.avg_roi else 0

        prev_base_query = self.db.query(
            func.sum(Model.payment_amount).label('total_payment'),
            func.sum(Model.refund_amount).label('total_refund'),
            func.sum(getattr(Model, visitors_col)).label('total_visitors'),
            func.avg(Model.payment_conversion).label('avg_conversion'),
            func.avg(Model.ad_roi).label('avg_roi'),
        )

        prev_data = None
        if prev_period_str:
            prev_data = prev_base_query.filter(getattr(Model, date_col) == prev_period_str).first()

        prev_payment = float(prev_data.total_payment or 0) if prev_data else 0
        prev_visitors = int(prev_data.total_visitors or 0) if prev_data else 0
        prev_conversion = float(prev_data.avg_conversion or 0) if prev_data else 0
        prev_roi = float(prev_data.avg_roi or 0) if prev_data and prev_data.avg_roi else 0

        net_sales = total_payment - total_refund
        refund_rate = (total_refund / total_payment * 100) if total_payment > 0 else 0
        uv_value = (total_payment / total_visitors) if total_visitors > 0 else 0

        kpi = {
            "total_gmv": {
                "value": round(total_payment, 2),
                "change": round(((total_payment - prev_payment) / prev_payment * 100), 1) if prev_payment > 0 else 0,
                "label": "总GMV"
            },
            "net_sales": {
                "value": round(net_sales, 2),
                "label": "净销售额"
            },
            "visitors": {
                "value": total_visitors,
                "change": round(((total_visitors - prev_visitors) / prev_visitors * 100), 1) if prev_visitors > 0 else 0,
                "label": "访客数"
            },
            "uv_value": {
                "value": round(uv_value, 2),
                "label": "UV价值"
            },
            "conversion": {
                "value": round(avg_conversion * 100, 2),
                "label": "转化率",
                "unit": "%"
            },
            "roi": {
                "value": round(avg_roi, 2),
                "label": "平均ROI"
            },
            "refund_rate": {
                "value": round(refund_rate, 2),
                "label": "退款率",
                "unit": "%"
            }
        }

        trends_query = self.db.query(
            getattr(Model, date_col).label('period'),
            func.sum(Model.payment_amount).label('payment'),
            func.sum(Model.refund_amount).label('refund'),
            func.sum(getattr(Model, visitors_col)).label('visitors'),
        ).group_by(getattr(Model, date_col)).order_by(getattr(Model, date_col)).limit(12).all()

        trends = []
        for t in trends_query:
            period_val = t.period
            period_str = period_val.isoformat() if hasattr(period_val, 'isoformat') else str(period_val)

            trends.append({
                "period": period_str,
                "payment_amount": round(float(t.payment or 0), 2),
                "net_sales": round(float(t.payment or 0) - float(t.refund or 0), 2),
                "visitors": int(t.visitors or 0)
            })

        return {
            "kpi": kpi,
            "trends": trends,
            "period": period_str,
            "dimension": dimension
        }
