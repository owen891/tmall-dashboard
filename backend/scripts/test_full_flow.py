"""
测试SQLAlchemy查询和utils函数
"""
import sys
sys.path.insert(0, r'F:\ai\.accelerate\tmall-dashboard\backend')

from app.core.database import SessionLocal
from app.models import WeeklyData
from app.core.utils import get_data_model, get_prev_period, get_latest_period, calculate_change, safe_float
from sqlalchemy import func, desc

db = SessionLocal()

try:
    print("测试get_data_model...")
    Model, date_col, visitors_col = get_data_model('weekly')
    print(f"Model: {Model}")
    print(f"date_col: {date_col}")
    print(f"visitors_col: {visitors_col}")
    
    print("\n测试get_latest_period...")
    latest = get_latest_period(Model, date_col, db)
    print(f"最新周期: {latest}")
    
    if latest:
        print("\n测试get_prev_period...")
        prev = get_prev_period(latest, 'weekly')
        print(f"上一周期: {prev}")
        
        print(f"\n测试聚合查询 - 当前周期 ({latest}):")
        curr_data = db.query(
            func.sum(Model.payment_amount).label('payment'),
            func.sum(Model.refund_amount).label('refund'),
            func.sum(getattr(Model, visitors_col)).label('visitors'),
            func.avg(Model.payment_conversion).label('conversion'),
            func.sum(Model.ad_spend).label('ad_spend'),
        ).filter(getattr(Model, date_col) == latest).first()
        
        print(f"  payment: {curr_data.payment}")
        print(f"  refund: {curr_data.refund}")
        print(f"  visitors: {curr_data.visitors}")
        print(f"  conversion: {curr_data.conversion}")
        print(f"  ad_spend: {curr_data.ad_spend}")
        
        print(f"\n测试聚合查询 - 上一周期 ({prev}):")
        prev_data = db.query(
            func.sum(Model.payment_amount).label('payment'),
            func.sum(Model.refund_amount).label('refund'),
            func.sum(getattr(Model, visitors_col)).label('visitors'),
            func.avg(Model.payment_conversion).label('conversion'),
            func.sum(Model.ad_spend).label('ad_spend'),
        ).filter(getattr(Model, date_col) == prev).first()
        
        print(f"  payment: {prev_data.payment}")
        print(f"  refund: {prev_data.refund}")
        print(f"  visitors: {prev_data.visitors}")
        print(f"  conversion: {prev_data.conversion}")
        print(f"  ad_spend: {prev_data.ad_spend}")
        
        print("\n测试calculate_change...")
        curr_payment = safe_float(curr_data.payment)
        prev_payment = safe_float(prev_data.payment)
        change = calculate_change(curr_payment, prev_payment)
        print(f"  变化: {change}")

except Exception as e:
    print(f"测试失败: {e}")
    import traceback
    traceback.print_exc()
finally:
    db.close()
