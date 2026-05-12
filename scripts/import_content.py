#!/usr/bin/env python3
"""
内容维度分析数据导入脚本
支持从内容平台或Excel文件导入内容数据
分析：直播带货、短视频带货、图文带货
"""

import sys
import os
import json
import sqlite3
from datetime import datetime, timedelta

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from db import get_db_path


def calculate_content_metrics(content_gmv, content_visitors, live_visitors=0, video_visitors=0, article_visitors=0):
    """计算内容指标"""
    uv_value = content_gmv / max(content_visitors, 1)

    content_ctr = 0
    if content_visitors > 0:
        content_ctr = content_visitors / max(content_gmv * 0.01, 1)

    content_cvr = 0
    if content_visitors > 0:
        content_cvr = content_gmv / max(content_visitors * 100, 1)

    return {
        'uv_value': round(uv_value, 2),
        'content_ctr': round(content_ctr, 4),
        'content_cvr': round(content_cvr, 4)
    }


def import_content_data(db_path, items):
    """导入内容分析数据"""
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    imported = 0

    for item in items:
        product_id = item.get('product_id', '')
        date = item.get('date', '')

        uv_value = item.get('uv_value', 0)
        avg_stay_duration = item.get('avg_stay_duration', 0)
        content_gmv = item.get('content_gmv', 0)
        content_visitors = item.get('content_visitors', 0)
        live_gmv = item.get('live_gmv', 0)
        live_visitors = item.get('live_visitors', 0)
        short_video_gmv = item.get('short_video_gmv', 0)
        short_video_visitors = item.get('short_video_visitors', 0)
        article_gmv = item.get('article_gmv', 0)
        article_visitors = item.get('article_visitors', 0)

        metrics = calculate_content_metrics(
            content_gmv, content_visitors,
            live_visitors, short_video_visitors, article_visitors
        )

        cursor.execute('''
            INSERT OR REPLACE INTO content_analysis
            (product_id, date, uv_value, avg_stay_duration, content_gmv,
             content_visitors, live_gmv, live_visitors, short_video_gmv,
             short_video_visitors, article_gmv, article_visitors,
             content_ctr, content_cvr)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (product_id, date, uv_value, avg_stay_duration, content_gmv,
              content_visitors, live_gmv, live_visitors, short_video_gmv,
              short_video_visitors, article_gmv, article_visitors,
              metrics['content_ctr'], metrics['content_cvr']))

        imported += 1

    conn.commit()
    conn.close()

    return {
        'imported': imported,
        'timestamp': datetime.now().isoformat()
    }


def import_from_excel(db_path, excel_path):
    """从Excel文件导入内容数据"""
    try:
        import pandas as pd
        df = pd.read_excel(excel_path)

        required_cols = ['product_id', 'date']
        for col in required_cols:
            if col not in df.columns:
                return {'error': f'缺少必需列: {col}'}

        items = df.to_dict('records')
        return import_content_data(db_path, items)
    except ImportError:
        return {'error': '请安装pandas: pip install pandas openpyxl'}
    except Exception as e:
        return {'error': str(e)}


def generate_content_report(db_path, days=30):
    """生成内容分析报告"""
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    report_date = (datetime.now() - timedelta(days=days)).strftime('%Y-%m-%d')

    cursor.execute('''
        SELECT
            SUM(content_gmv) as total_gmv,
            SUM(live_gmv) as live_gmv,
            SUM(short_video_gmv) as video_gmv,
            SUM(article_gmv) as article_gmv,
            AVG(uv_value) as avg_uv_value,
            AVG(avg_stay_duration) as avg_stay_duration,
            COUNT(DISTINCT product_id) as active_products
        FROM content_analysis
        WHERE date >= ?
    ''', (report_date,))

    row = cursor.fetchone()
    conn.close()

    total_gmv = row[0] or 0

    return {
        'period': f'最近{days}天',
        'start_date': report_date,
        'total_content_gmv': round(total_gmv, 0),
        'live_gmv': round(row[1] or 0, 0),
        'video_gmv': round(row[2] or 0, 0),
        'article_gmv': round(row[3] or 0, 0),
        'live_ratio': round((row[1] or 0) / max(total_gmv, 1) * 100, 1),
        'video_ratio': round((row[2] or 0) / max(total_gmv, 1) * 100, 1),
        'article_ratio': round((row[3] or 0) / max(total_gmv, 1) * 100, 1),
        'avg_uv_value': round(row[4], 2) if row[4] else 0,
        'avg_stay_duration': round(row[5], 1) if row[5] else 0,
        'active_products': row[6] or 0
    }


if __name__ == '__main__':
    db_path = get_db_path()

    if len(sys.argv) > 1:
        excel_path = sys.argv[1]
        result = import_from_excel(db_path, excel_path)
    else:
        sample_data = [
            {
                'product_id': 'P001',
                'date': '2026-05-01',
                'uv_value': 15.5,
                'avg_stay_duration': 120,
                'content_gmv': 50000,
                'content_visitors': 5000,
                'live_gmv': 30000,
                'live_visitors': 2000,
                'short_video_gmv': 15000,
                'short_video_visitors': 2000,
                'article_gmv': 5000,
                'article_visitors': 1000
            },
            {
                'product_id': 'P002',
                'date': '2026-05-01',
                'uv_value': 8.2,
                'avg_stay_duration': 60,
                'content_gmv': 20000,
                'content_visitors': 3000,
                'live_gmv': 15000,
                'live_visitors': 1500,
                'short_video_gmv': 5000,
                'short_video_visitors': 1000,
                'article_gmv': 0,
                'article_visitors': 500
            }
        ]
        result = import_content_data(db_path, sample_data)

    print(json.dumps(result, ensure_ascii=False, indent=2))
