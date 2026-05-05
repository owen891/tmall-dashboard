#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""数据导入脚本"""

import pandas as pd
import os
from datetime import datetime, timedelta
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.core.database import SessionLocal
from app.models import DailyData, WeeklyData, MonthlyData

DATA_DIR = r'F:\bi\海贝海\原始数据'

def main():
    db = SessionLocal()
    
    # 清空数据
    db.query(DailyData).delete()
    db.query(WeeklyData).delete()
    db.query(MonthlyData).delete()
    db.commit()
    print('数据已清空')
    
    files = [f for f in os.listdir(DATA_DIR) if '生意参谋' in f and '商品' in f and f.endswith('.xls')]
    
    print(f'找到 {len(files)} 个文件')
    
    total = 0
    for fname in sorted(files):
        fpath = os.path.join(DATA_DIR, fname)
        print(f'处理: {fname}')
        
        try:
            df = pd.read_excel(fpath, header=4)
        except Exception as e:
            print(f'  错误: {e}')
            continue
        
        count = 0
        errors = []
        for i, (_, row) in enumerate(df.iterrows()):
            try:
                pid = str(int(row['商品ID']))
                date_val = str(row['统计日期'])
                gmv = float(str(row.get('支付金额', 0)).replace(',', ''))
                refund = float(str(row.get('成功退款金额', 0)).replace(',', ''))
                visitors = int(float(str(row.get('商品访客数', 0)).replace(',', '')))
                pv = int(float(str(row.get('商品浏览量', 0)).replace(',', '')))
                conv = float(str(row.get('商品支付转化率', 0)).replace(',', '').replace('%', ''))
                
                existing = db.query(DailyData).filter(DailyData.product_id == pid, DailyData.date == date_val).first()
                if not existing:
                    daily = DailyData(
                        product_id=pid, date=date_val, payment_amount=gmv,
                        refund_amount=refund, ipv=visitors, pv=pv,
                        payment_conversion=conv/100 if conv > 1 else conv
                    )
                    db.add(daily)
                    count += 1
                
                d = datetime.strptime(date_val, '%Y-%m-%d')
                monday = d - timedelta(days=d.weekday())
                week_start = monday.strftime('%Y-%m-%d')
                
                existing_w = db.query(WeeklyData).filter(
                    WeeklyData.product_id == pid, WeeklyData.week_start == week_start
                ).first()
                if not existing_w:
                    weekly = WeeklyData(
                        product_id=pid, week_start=week_start, payment_amount=gmv,
                        refund_amount=refund, ipv=visitors, pv=pv,
                        payment_conversion=conv/100 if conv > 1 else conv
                    )
                    db.add(weekly)
                
                month = date_val[:7]
                existing_m = db.query(MonthlyData).filter(
                    MonthlyData.product_id == pid, MonthlyData.month == month
                ).first()
                if not existing_m:
                    monthly = MonthlyData(
                        product_id=pid, month=month, payment_amount=gmv,
                        refund_amount=refund, visitors=visitors, page_views=pv,
                        payment_conversion=conv/100 if conv > 1 else conv
                    )
                    db.add(monthly)
            except Exception as e:
                if len(errors) < 5:
                    errors.append(f'行{i}: {e}')
        
        if errors:
            print(f'  错误: {errors}')
        
        db.commit()
        total += count
        print(f'  导入 {count} 条')
    
    print()
    print(f'DailyData: {db.query(DailyData).count()}')
    print(f'WeeklyData: {db.query(WeeklyData).count()}')
    print(f'MonthlyData: {db.query(MonthlyData).count()}')
    db.close()

if __name__ == '__main__':
    main()
