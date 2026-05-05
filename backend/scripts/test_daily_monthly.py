"""
测试daily和monthly查询
"""
import sys
sys.path.insert(0, r'F:\ai\.accelerate\tmall-dashboard\backend')

from app.core.database import SessionLocal
from app.models import DailyData, MonthlyData
from app.core.utils import get_data_model, get_prev_period, get_latest_period, calculate_change, safe_float
from sqlalchemy import func, desc

db = SessionLocal()

try:
    print("测试daily_data查询...")
    latest_daily = db.query(func.max(DailyData.date)).scalar()
    print(f"  最新日期: {latest_daily}")
    
    if latest_daily:
        count = db.query(DailyData).filter(DailyData.date == latest_daily).count()
        print(f"  记录数: {count}")
    
    print("\n测试monthly_data查询...")
    latest_monthly = db.query(func.max(MonthlyData.month)).scalar()
    print(f"  最新月份: {latest_monthly}")
    
    if latest_monthly:
        count = db.query(MonthlyData).filter(MonthlyData.month == latest_monthly).count()
        print(f"  记录数: {count}")
    
except Exception as e:
    print(f"测试失败: {e}")
    import traceback
    traceback.print_exc()
finally:
    db.close()
