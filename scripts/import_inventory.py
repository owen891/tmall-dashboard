#!/usr/bin/env python3
"""
库存数据导入脚本
支持从ERP系统或Excel文件导入库存数据
自动计算：周转天数、缺货率、安全库存
"""

import sys
import os
import json
import sqlite3
from datetime import datetime, timedelta

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from db import get_db_path

def calculate_inventory_metrics(stock_qty, sales_qty, safety_threshold=7):
    """计算库存指标"""
    turnover_days = (stock_qty / max(sales_qty, 1)) * 30 if sales_qty > 0 else 999

    shortage_rate = 0
    if stock_qty < sales_qty:
        shortage_rate = round((sales_qty - stock_qty) / max(sales_qty, 1), 2)

    safety_stock = int(sales_qty * safety_threshold) if sales_qty > 0 else 0

    alert_level = 'green'
    if shortage_rate > 0.3:
        alert_level = 'red'
    elif shortage_rate > 0.1:
        alert_level = 'yellow'

    return {
        'turnover_days': round(turnover_days, 1),
        'shortage_rate': shortage_rate,
        'safety_stock': safety_stock,
        'alert_level': alert_level
    }


def import_inventory_data(db_path, items):
    """导入库存数据"""
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    imported = 0
    alerts = []

    for item in items:
        product_id = item.get('product_id', '')
        date = item.get('date', '')
        stock_qty = item.get('stock_qty', 0)
        sales_qty = item.get('sales_qty', 0)
        warehouse = item.get('warehouse', '')

        metrics = calculate_inventory_metrics(stock_qty, sales_qty)

        cursor.execute('''
            INSERT OR REPLACE INTO inventory
            (product_id, date, stock_qty, sales_qty, turnover_days,
             shortage_rate, safety_stock, warehouse, alert_level)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (product_id, date, stock_qty, sales_qty,
              metrics['turnover_days'], metrics['shortage_rate'],
              metrics['safety_stock'], warehouse, metrics['alert_level']))

        imported += 1

        if metrics['alert_level'] != 'green':
            alerts.append({
                'product_id': product_id,
                'date': date,
                'alert_level': metrics['alert_level'],
                'shortage_rate': metrics['shortage_rate']
            })

    conn.commit()
    conn.close()

    return {
        'imported': imported,
        'alerts': alerts,
        'timestamp': datetime.now().isoformat()
    }


def import_from_excel(db_path, excel_path):
    """从Excel文件导入库存数据"""
    try:
        import pandas as pd
        df = pd.read_excel(excel_path)

        required_cols = ['product_id', 'date', 'stock_qty', 'sales_qty']
        for col in required_cols:
            if col not in df.columns:
                return {'error': f'缺少必需列: {col}'}

        items = df.to_dict('records')
        return import_inventory_data(db_path, items)
    except ImportError:
        return {'error': '请安装pandas: pip install pandas openpyxl'}
    except Exception as e:
        return {'error': str(e)}


def generate_inventory_report(db_path, days=30):
    """生成库存分析报告"""
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    report_date = (datetime.now() - timedelta(days=days)).strftime('%Y-%m-%d')

    cursor.execute('''
        SELECT
            COUNT(DISTINCT product_id) as total_products,
            AVG(turnover_days) as avg_turnover,
            MAX(turnover_days) as max_turnover,
            MIN(turnover_days) as min_turnover,
            AVG(shortage_rate) as avg_shortage,
            SUM(CASE WHEN alert_level = 'red' THEN 1 ELSE 0 END) as critical_alerts,
            SUM(CASE WHEN alert_level = 'yellow' THEN 1 ELSE 0 END) as warning_alerts
        FROM inventory
        WHERE date >= ?
    ''', (report_date,))

    row = cursor.fetchone()
    conn.close()

    return {
        'period': f'最近{days}天',
        'start_date': report_date,
        'total_products': row[0] or 0,
        'avg_turnover_days': round(row[1], 1) if row[1] else 0,
        'max_turnover_days': round(row[2], 1) if row[2] else 0,
        'min_turnover_days': round(row[3], 1) if row[3] else 0,
        'avg_shortage_rate': round(row[4], 3) if row[4] else 0,
        'critical_alerts': row[5] or 0,
        'warning_alerts': row[6] or 0
    }


if __name__ == '__main__':
    db_path = get_db_path()

    if len(sys.argv) > 1:
        excel_path = sys.argv[1]
        result = import_from_excel(db_path, excel_path)
    else:
        sample_data = [
            {'product_id': 'P001', 'date': '2026-05-01', 'stock_qty': 100, 'sales_qty': 50},
            {'product_id': 'P001', 'date': '2026-05-02', 'stock_qty': 80, 'sales_qty': 30},
            {'product_id': 'P002', 'date': '2026-05-01', 'stock_qty': 20, 'sales_qty': 50},
            {'product_id': 'P002', 'date': '2026-05-02', 'stock_qty': 0, 'sales_qty': 40},
        ]
        result = import_inventory_data(db_path, sample_data)

    print(json.dumps(result, ensure_ascii=False, indent=2))
