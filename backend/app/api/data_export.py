from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import func, desc
from typing import Optional, List
from app.core.database import get_db
from app.models import DailyData, WeeklyData, MonthlyData, Product
from app.schemas.common import ResponseModel
from fastapi.responses import StreamingResponse
import io
import csv
from datetime import datetime

router = APIRouter(prefix="/export", tags=["数据导出"])

DIMENSION_MAP = {
    'monthly': {'table': 'monthly_data', 'date_col': 'month', 'visitors_col': 'visitors'},
    'weekly': {'table': 'weekly_data', 'date_col': 'week_start', 'visitors_col': 'ipv'},
    'daily': {'table': 'daily_data', 'date_col': 'date', 'visitors_col': 'ipv'},
}

HEADER_MAP = {
    'product_id': '商品ID',
    'product_name': '商品名称',
    'category': '类目',
    'tier': '分层',
    'style': '风格',
    'scene': '场景',
    'manager': '负责人',
    'payment_amount': 'GMV',
    'net_sales': '净销售额',
    'refund_amount': '退款额',
    'refund_rate': '退款率',
    'visitors': '访客数',
    'aov': '客单价',
    'conversion': '转化率',
    'ad_spend': '广告花费',
    'roi': 'ROI',
    'payment_count': '支付订单数',
    'order_count': '订单数',
    'ad_ratio': '广告占比',
    'score': '综合评分'
}

DEFAULT_FIELDS = [
    'product_id', 'product_name', 'category', 'tier', 'style', 'scene',
    'manager', 'payment_amount', 'net_sales', 'refund_amount', 'refund_rate',
    'visitors', 'aov', 'conversion', 'ad_spend', 'roi', 'payment_count'
]

@router.get("/products")
def export_products(
    dim: str = Query("weekly", alias="dim", description="时间维度: daily/weekly/monthly"),
    format: str = Query("csv", description="导出格式: csv/json"),
    period: Optional[str] = Query(None, description="指定周期"),
    tier: Optional[str] = Query(None, description="分层筛选"),
    style: Optional[str] = Query(None, description="风格筛选"),
    scene: Optional[str] = Query(None, description="场景筛选"),
    search: Optional[str] = Query(None, description="搜索关键词"),
    manager: Optional[str] = Query(None, description="负责人筛选"),
    status: Optional[str] = Query(None, description="状态筛选"),
    category: Optional[str] = Query(None, description="类目筛选"),
    columns: Optional[str] = Query(None, description="指定导出字段，用逗号分隔"),
    db: Session = Depends(get_db)
):
    """
    导出商品数据为多种格式
    """
    dim_cfg = DIMENSION_MAP.get(dim, DIMENSION_MAP['weekly'])
    visitors_col = dim_cfg['visitors_col']
    date_col = dim_cfg['date_col']
    
    if dim == "monthly":
        Model = MonthlyData
    elif dim == "daily":
        Model = DailyData
    else:
        Model = WeeklyData
    
    if not period:
        period = get_latest_period(Model, date_col, db)
    
    if not period:
        raise HTTPException(status_code=404, detail="无数据可导出")
    
    base_cols = [
        Model.product_id,
        func.max(Product.title).label('product_name'),
        func.max(Product.category).label('category'),
        func.max(Product.tier).label('tier'),
        func.max(Product.style).label('style'),
        func.max(Product.scene).label('scene'),
        func.max(Product.manager).label('manager'),
        func.sum(Model.payment_amount).label('payment_amount'),
        func.sum(Model.refund_amount).label('refund_amount'),
        func.sum(getattr(Model, visitors_col)).label('visitors'),
        func.avg(Model.payment_conversion).label('conversion'),
        func.sum(Model.ad_spend).label('ad_spend'),
        func.avg(Model.ad_roi).label('roi'),
    ]
    
    if dim == 'monthly':
        base_cols.append(func.sum(Model.payment_qty).label('payment_count'))
    elif dim == 'daily':
        base_cols.append(func.sum(Model.payment_qty).label('payment_count'))
    else:
        base_cols.append(func.sum(Model.presale_qty).label('payment_count'))
    
    if hasattr(Model, 'order_count'):
        base_cols.append(func.sum(Model.order_count).label('order_count'))
    
    if dim == 'monthly':
        monthly_cols = []
        monthly_only_fields = [
            'overall_roi', 'uv_value', 'search_ratio', 'click_rate', 
            'buyers', 'avg_order_value', 'paid_ratio', 'refund_paid_ratio',
            'keyword_spend', 'keyword_roi', 'crowd_spend', 'crowd_roi',
            'site_spend', 'site_roi', 'paid_ipv', 'organic_ipv',
            'search_ipv', 'recommend_ipv', 'cart_users', 'industry_ctr',
            'cross_sell_qty', 'cross_sell_rate', 'repurchase_rate',
            'new_buyers', 'new_buyer_ratio', 'score'
        ]
        for col_name in monthly_only_fields:
            if hasattr(Model, col_name):
                if col_name in ['overall_roi', 'uv_value', 'search_ratio', 'click_rate', 
                               'avg_order_value', 'paid_ratio', 'refund_paid_ratio', 
                               'keyword_roi', 'crowd_roi', 'site_roi', 'industry_ctr',
                               'repurchase_rate', 'cross_sell_rate', 'new_buyer_ratio', 'score']:
                    monthly_cols.append(func.avg(getattr(Model, col_name)).label(col_name))
                else:
                    monthly_cols.append(func.sum(getattr(Model, col_name)).label(col_name))
        base_cols.extend(monthly_cols)
    
    query = db.query(*base_cols).join(Product, Model.product_id == Product.product_id)
    filter_conditions = [getattr(Model, date_col) == period]
    
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
    query = query.order_by(desc(func.sum(Model.payment_amount)))
    
    products_data = query.all()
    
    # 解析用户指定的字段
    selected_fields = DEFAULT_FIELDS
    if columns:
        custom_fields = [f.strip() for f in columns.split(',')]
        selected_fields = [f for f in custom_fields if f in DEFAULT_FIELDS] or DEFAULT_FIELDS
    
    # 处理数据
    processed_data = []
    for row in products_data:
        payment = row.payment_amount or 0
        refund = row.refund_amount or 0
        visitors = row.visitors or 0
        
        row_dict = {
            'product_id': row.product_id,
            'product_name': row.product_name,
            'category': row.category,
            'tier': row.tier,
            'style': row.style,
            'scene': row.scene,
            'manager': row.manager,
            'payment_amount': round(payment, 2),
            'net_sales': round(payment - refund, 2),
            'refund_amount': round(refund, 2),
            'refund_rate': round(refund / payment if payment > 0 else 0, 4),
            'visitors': visitors,
            'aov': round(payment / visitors if visitors > 0 else 0, 2),
            'conversion': round(row.conversion or 0, 4),
            'ad_spend': round(row.ad_spend or 0, 2),
            'roi': round(row.roi or 0, 2),
            'payment_count': row.payment_count or 0,
            'order_count': row.order_count or 0 if hasattr(row, 'order_count') else 0,
            'ad_ratio': round((row.ad_spend or 0) / payment if payment > 0 else 0, 4),
            'score': row.score if hasattr(row, 'score') else 0
        }
        
        # 添加月度特定字段
        if dim == 'monthly':
            for field in ['overall_roi', 'uv_value', 'search_ratio', 'click_rate', 
                         'buyers', 'avg_order_value', 'paid_ratio', 'keyword_spend',
                         'keyword_roi', 'crowd_spend', 'crowd_roi', 'site_spend',
                         'site_roi']:
                if hasattr(row, field) and field not in row_dict:
                    value = getattr(row, field)
                    row_dict[field] = round(value, 4) if isinstance(value, (int, float)) else value
        
        processed_data.append(row_dict)
    
    if format == 'json':
        filename = f"products_{dim}_{period}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        output = io.BytesIO()
        import json
        output.write(json.dumps({
            'meta': {
                'dim': dim,
                'period': period,
                'generated_at': datetime.now().isoformat(),
                'count': len(processed_data)
            },
            'data': processed_data
        }, ensure_ascii=False, indent=2).encode('utf-8'))
        output.seek(0)
        return StreamingResponse(
            output,
            media_type='application/json',
            headers={
                'Content-Disposition': f'attachment; filename="{filename}"',
                'Access-Control-Expose-Headers': 'Content-Disposition'
            }
        )
    else:
        # 导出CSV
        output = io.StringIO()
        writer = csv.writer(output)
        
        # 写入表头
        writer.writerow([HEADER_MAP.get(f, f) for f in selected_fields])
        
        # 写入数据
        for row_dict in processed_data:
            writer.writerow([row_dict.get(f, '') for f in selected_fields])
        
        output.seek(0)
        
        # 生成文件名
        filename = f"products_{dim}_{period}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        
        return StreamingResponse(
            output,
            media_type='text/csv',
            headers={
                'Content-Disposition': f'attachment; filename="{filename}"',
                'Access-Control-Expose-Headers': 'Content-Disposition'
            }
        )

@router.get("/products/fields")
def get_export_fields():
    """获取可导出的字段列表"""
    return ResponseModel(data={
        'fields': DEFAULT_FIELDS,
        'field_labels': {k: HEADER_MAP.get(k, k) for k in DEFAULT_FIELDS}
    })

def get_latest_period(Model, date_col, db):
    """获取最新周期"""
    latest = db.query(Model).order_by(desc(getattr(Model, date_col))).first()
    if latest:
        return getattr(latest, date_col)
    return None
