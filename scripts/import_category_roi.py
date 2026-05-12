#!/usr/bin/env python3
"""
品类投产ROI分析数据导入脚本
支持按品类聚合广告投放效果
分析：品类级ROI、利润率、转化率
"""

import sys
import os
import json
import sqlite3
from datetime import datetime, timedelta

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from db import get_db_path


def calculate_category_roi_metrics(ad_spend, gmv, orders, visitors, cost_price=0, selling_price=0):
    """计算品类ROI指标"""
    roi = gmv / max(ad_spend, 1)
    conversion_rate = orders / max(visitors, 1)
    avg_order_value = gmv / max(orders, 1)

    profit_margin = 0
    if gmv > 0 and cost_price > 0:
        profit = (selling_price - cost_price) / selling_price
        profit_margin = profit * 100

    return {
        'roi': round(roi, 2),
        'conversion_rate': round(conversion_rate, 4),
        'avg_order_value': round(avg_order_value, 2),
        'profit_margin': round(profit_margin, 2)
    }


def import_category_roi(db_path, items):
    """导入品类ROI数据"""
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    imported = 0

    for item in items:
        category = item.get('category', '')
        period = item.get('period', '')
        ad_spend = item.get('ad_spend', 0)
        gmv = item.get('gmv', 0)
        orders = item.get('orders', 0)
        visitors = item.get('visitors', 0)
        cost_price = item.get('cost_price', 0)
        selling_price = item.get('selling_price', 0)

        metrics = calculate_category_roi_metrics(ad_spend, gmv, orders, visitors, cost_price, selling_price)

        cursor.execute('''
            INSERT OR REPLACE INTO category_roi
            (category, period, ad_spend, gmv, roi, orders, visitors,
             conversion_rate, avg_order_value, profit_margin)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (category, period, ad_spend, gmv, metrics['roi'],
              orders, visitors, metrics['conversion_rate'],
              metrics['avg_order_value'], metrics['profit_margin']))

        imported += 1

    conn.commit()
    conn.close()

    return {
        'imported': imported,
        'timestamp': datetime.now().isoformat()
    }


def import_from_excel(db_path, excel_path):
    """从Excel文件导入品类ROI数据"""
    try:
        import pandas as pd
        df = pd.read_excel(excel_path)

        required_cols = ['category', 'period']
        for col in required_cols:
            if col not in df.columns:
                return {'error': f'缺少必需列: {col}'}

        items = df.to_dict('records')
        return import_category_roi(db_path, items)
    except ImportError:
        return {'error': '请安装pandas: pip install pandas openpyxl'}
    except Exception as e:
        return {'error': str(e)}


def aggregate_by_category(db_path):
    """从现有数据按品类聚合"""
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    cursor.execute('''
        SELECT
            p.category,
            d.month as period,
            SUM(d.ad_spend) as ad_spend,
            SUM(d.payment_amount) as gmv,
            SUM(d.buyers) as orders,
            SUM(d.visitors) as visitors
        FROM products p
        JOIN monthly_data d ON p.product_id = d.product_id
        GROUP BY p.category, d.month
        HAVING p.category IS NOT NULL AND p.category != ''
    ''')

    rows = cursor.fetchall()
    conn.close()

    items = []
    for row in rows:
        items.append({
            'category': row[0],
            'period': row[1],
            'ad_spend': row[2],
            'gmv': row[3],
            'orders': row[4],
            'visitors': row[5]
        })

    return import_category_roi(db_path, items)


def generate_category_roi_report(db_path, top_n=10):
    """生成品类ROI分析报告"""
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    cursor.execute('''
        SELECT
            category,
            SUM(ad_spend) as total_spend,
            SUM(gmv) as total_gmv,
            AVG(roi) as avg_roi,
            AVG(profit_margin) as avg_margin,
            COUNT(DISTINCT period) as active_periods
        FROM category_roi
        GROUP BY category
        ORDER BY total_gmv DESC
        LIMIT ?
    ''', (top_n,))

    rows = cursor.fetchall()
    conn.close()

    results = []
    for row in rows:
        total_spend = row[2] or 0
        total_gmv = row[3] or 0
        roi = row[4] or 0
        avg_margin = row[5] or 0

        results.append({
            'category': row[0],
            'total_spend': round(total_spend, 0),
            'total_gmv': round(total_gmv, 0),
            'avg_roi': round(roi, 2),
            'avg_profit_margin': round(avg_margin, 2),
            'active_periods': row[6],
            'roi_grade': 'A' if roi >= 3 else 'B' if roi >= 2 else 'C' if roi >= 1.5 else 'D',
            'margin_grade': 'A' if avg_margin >= 30 else 'B' if avg_margin >= 20 else 'C' if avg_margin >= 10 else 'D'
        })

    return {
        'report_date': datetime.now().strftime('%Y-%m-%d'),
        'top_categories': results,
        'total': len(results)
    }


def get_roi_stop_recommendations(db_path, threshold=1.5):
    """获取需要停投的品类"""
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    cursor.execute('''
        SELECT
            category,
            AVG(roi) as avg_roi,
            SUM(ad_spend) as total_spend,
            COUNT(*) as periods_count
        FROM category_roi
        GROUP BY category
        HAVING avg_roi < ?
        ORDER BY avg_roi ASC
    ''', (threshold,))

    rows = cursor.fetchall()
    conn.close()

    recommendations = []
    for row in rows:
        roi = row[2] or 0
        spend = row[3] or 0
        wasted_spend = spend * (1 - roi / threshold) if roi > 0 else spend

        recommendations.append({
            'category': row[0],
            'avg_roi': round(roi, 2),
            'threshold': threshold,
            'total_spend': round(spend, 0),
            'potential_waste': round(wasted_spend, 0),
            'action': '停投' if roi < threshold * 0.5 else '预警',
            'severity': 'danger' if roi < threshold * 0.5 else 'warning'
        })

    return recommendations


if __name__ == '__main__':
    db_path = get_db_path()

    if len(sys.argv) > 1:
        command = sys.argv[1]
        if command == 'aggregate':
            result = aggregate_by_category(db_path)
        elif command == 'report':
            result = generate_category_roi_report(db_path)
        elif command == 'stop':
            threshold = float(sys.argv[2]) if len(sys.argv) > 2 else 1.5
            result = get_roi_stop_recommendations(db_path, threshold)
        else:
            excel_path = sys.argv[1]
            result = import_from_excel(db_path, excel_path)
    else:
        sample_data = [
            {'category': '美妆', 'period': '2026-05', 'ad_spend': 50000, 'gmv': 150000, 'orders': 500, 'visitors': 10000},
            {'category': '护肤', 'period': '2026-05', 'ad_spend': 80000, 'gmv': 280000, 'orders': 800, 'visitors': 15000},
            {'category': '彩妆', 'period': '2026-05', 'ad_spend': 30000, 'gmv': 45000, 'orders': 200, 'visitors': 5000},
            {'category': '个护', 'period': '2026-05', 'ad_spend': 20000, 'gmv': 80000, 'orders': 400, 'visitors': 8000},
        ]
        result = import_category_roi(db_path, sample_data)

    print(json.dumps(result, ensure_ascii=False, indent=2))
