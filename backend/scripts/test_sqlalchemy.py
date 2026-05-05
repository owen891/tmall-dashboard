"""
测试SQLAlchemy查询
"""
import sys
sys.path.insert(0, r'F:\ai\.accelerate\tmall-dashboard\backend')

from app.core.database import SessionLocal
from app.models import WeeklyData
from sqlalchemy import desc

db = SessionLocal()

try:
    print("测试SQLAlchemy查询...")
    
    # 测试查询最新周期
    latest = db.query(WeeklyData).order_by(desc(WeeklyData.week_start)).first()
    if latest:
        print(f"最新周期: {latest.week_start}")
        print(f"支付金额: {latest.payment_amount}")
        print(f"访客数(ipv): {latest.ipv}")
    else:
        print("没有找到数据")
    
    # 测试聚合查询
    from sqlalchemy import func
    result = db.query(
        func.sum(WeeklyData.payment_amount).label('payment'),
        func.sum(WeeklyData.ipv).label('visitors'),
        func.avg(WeeklyData.payment_conversion).label('conversion'),
        func.sum(WeeklyData.ad_spend).label('ad_spend'),
        func.sum(WeeklyData.refund_amount).label('refund'),
    ).filter(WeeklyData.week_start == '2026-05-04').first()
    
    print(f"\n聚合查询结果:")
    print(f"  支付金额: {result.payment}")
    print(f"  访客数: {result.visitors}")
    print(f"  转化率: {result.conversion}")
    print(f"  广告花费: {result.ad_spend}")
    print(f"  退款金额: {result.refund}")
    
except Exception as e:
    print(f"查询失败: {e}")
    import traceback
    traceback.print_exc()
finally:
    db.close()
