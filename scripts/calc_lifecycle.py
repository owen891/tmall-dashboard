#!/usr/bin/env python3
"""
生命周期评分计算脚本
根据培训图片"8、生命周期管理"要求：
- 导入期：ROI警戒 <1.5停投
- 成长期：持续内容投放
- 成熟期：毛利最大化
- 衰退期：打折+清仓
- 全周期评分≥80保留
"""

import sys
import os
import json
import sqlite3
from datetime import datetime, timedelta

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from db import get_db_path


def detect_lifecycle_stage(product_data):
    """判断商品生命周期阶段"""
    total_months = len(product_data)
    if total_months == 0:
        return '未知', {}

    total_gsv = sum(m['payment_amount'] or 0 for m in product_data)
    recent_months = product_data[-3:] if len(product_data) >= 3 else product_data
    earlier_months = product_data[:-3] if len(product_data) > 3 else []

    recent_gsv = sum(m['payment_amount'] or 0 for m in recent_months)
    earlier_gsv = sum(m['payment_amount'] or 0 for m in earlier_months)

    avg_roi = sum(m['ad_roi'] or 0 for m in product_data if m.get('ad_roi')) / max(
        len([m for m in product_data if m.get('ad_roi')]), 1
    )

    avg_refund_rate = sum(
        (m['refund_amount'] or 0) / max(m['payment_amount'] or 1, 1)
        for m in product_data
    ) / max(total_months, 1)

    avg_content_gmv = 0
    if product_data and 'content_gmv' in product_data[0]:
        avg_content_gmv = sum(m.get('content_gmv', 0) or 0 for m in product_data) / total_months

    stage = '导入期'
    if total_months <= 3:
        stage = '导入期'
        if avg_roi < 1.5:
            stage = '导入期-警戒'
    elif earlier_gsv > 0 and recent_gsv > earlier_gsv * 1.5:
        stage = '成长期'
    elif total_months > 6 and earlier_gsv > 0 and abs(recent_gsv - earlier_gsv) / earlier_gsv < 0.2:
        stage = '成熟期'
    elif earlier_gsv > 0 and recent_gsv < earlier_gsv * 0.7:
        stage = '衰退期'

    return stage, {
        'total_months': total_months,
        'total_gsv': round(total_gsv, 0),
        'recent_3m_gsv': round(recent_gsv, 0),
        'avg_roi': round(avg_roi, 2),
        'avg_refund_rate': round(avg_refund_rate, 3),
        'avg_content_gmv': round(avg_content_gmv, 0)
    }


def calculate_lifecycle_score(stage, metrics, avg_roi, avg_refund_rate):
    """计算全周期评分（100分制）"""
    score = 100

    if avg_roi < 1.5:
        score -= 40
    elif avg_roi < 2.0:
        score -= 20
    elif avg_roi >= 3.0:
        score += 10

    if avg_refund_rate > 0.3:
        score -= 20
    elif avg_refund_rate > 0.15:
        score -= 10
    elif avg_refund_rate < 0.05:
        score += 5

    if stage == '衰退期':
        score -= 15
    elif stage == '成熟期':
        score += 10
    elif stage == '成长期':
        score += 5

    return max(min(score, 100), 0)


def get_lifecycle_action(stage, score, avg_roi):
    """根据阶段和评分给出建议操作"""
    if score < 60:
        return '清仓淘汰'
    elif score < 80:
        return '观察优化'

    if stage == '衰退期':
        return '打折清仓'
    elif stage == '成熟期':
        return '毛利最大化'
    elif stage == '成长期':
        return '持续内容投放'
    elif stage == '导入期-警戒' or avg_roi < 1.5:
        return 'ROI警戒-考虑停投'
    elif stage == '导入期':
        return '观察培育'

    return '保留'


def calculate_all_products_lifecycle(db_path):
    """计算所有商品的生命周期评分"""
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    cursor.execute('''
        SELECT
            p.product_id, p.title, p.category, p.tier, p.style,
            d.month, d.payment_amount, d.payment_qty, d.refund_amount,
            d.ad_spend, d.ad_roi, d.visitors, d.payment_conversion,
            d.cart_rate, d.buyers, d.avg_order_value, d.repurchase_rate,
            COALESCE(c.content_gmv, 0) as content_gmv
        FROM products p
        LEFT JOIN monthly_data d ON p.product_id = d.product_id
        LEFT JOIN content_analysis c ON p.product_id = c.product_id
        ORDER BY p.product_id, d.month
    ''')

    rows = cursor.fetchall()
    conn.close()

    product_data = {}
    for row in rows:
        pid = row[0]
        if pid not in product_data:
            product_data[pid] = {
                'product_id': pid,
                'title': row[1],
                'category': row[2],
                'tier': row[3],
                'style': row[4],
                'months': []
            }
        if row[5]:
            product_data[pid]['months'].append({
                'month': row[5],
                'payment_amount': row[6],
                'payment_qty': row[7],
                'refund_amount': row[8],
                'ad_spend': row[9],
                'ad_roi': row[10],
                'visitors': row[11],
                'payment_conversion': row[12],
                'cart_rate': row[13],
                'buyers': row[14],
                'avg_order_value': row[15],
                'repurchase_rate': row[16],
                'content_gmv': row[17]
            })

    results = []
    for pid, data in product_data.items():
        if not data['months']:
            continue

        stage, metrics = detect_lifecycle_stage(data['months'])

        avg_roi = metrics.get('avg_roi', 0)
        avg_refund_rate = metrics.get('avg_refund_rate', 0)

        score = calculate_lifecycle_score(stage, metrics, avg_roi, avg_refund_rate)
        action = get_lifecycle_action(stage, score, avg_roi)

        results.append({
            'product_id': pid,
            'title': data['title'],
            'category': data['category'],
            'tier': data['tier'],
            'stage': stage,
            'score': score,
            'action': action,
            **metrics
        })

    results.sort(key=lambda x: x['score'], reverse=True)
    return results


def generate_lifecycle_report(db_path, top_n=20):
    """生成生命周期分析报告"""
    results = calculate_all_products_lifecycle(db_path)

    stage_counts = {}
    action_counts = {}
    score_ranges = {'≥90': 0, '80-89': 0, '70-79': 0, '60-69': 0, '<60': 0}

    for r in results:
        stage_counts[r['stage']] = stage_counts.get(r['stage'], 0) + 1
        action_counts[r['action']] = action_counts.get(r['action'], 0) + 1

        if r['score'] >= 90:
            score_ranges['≥90'] += 1
        elif r['score'] >= 80:
            score_ranges['80-89'] += 1
        elif r['score'] >= 70:
            score_ranges['70-79'] += 1
        elif r['score'] >= 60:
            score_ranges['60-69'] += 1
        else:
            score_ranges['<60'] += 1

    return {
        'report_date': datetime.now().strftime('%Y-%m-%d'),
        'total_products': len(results),
        'stage_distribution': stage_counts,
        'action_distribution': action_counts,
        'score_distribution': score_ranges,
        'top_products': results[:top_n],
        'stop_recommendations': [r for r in results if '停投' in r['action']],
        'clearance_recommendations': [r for r in results if '淘汰' in r['action']]
    }


if __name__ == '__main__':
    db_path = get_db_path()

    if len(sys.argv) > 1:
        command = sys.argv[1]
        if command == 'report':
            result = generate_lifecycle_report(db_path)
        elif command == 'top':
            top_n = int(sys.argv[2]) if len(sys.argv) > 2 else 20
            results = calculate_all_products_lifecycle(db_path)
            result = {'products': results[:top_n]}
        else:
            result = {'error': f'未知命令: {command}'}
    else:
        results = calculate_all_products_lifecycle(db_path)
        result = {
            'total': len(results),
            'products': results[:10]
        }

    print(json.dumps(result, ensure_ascii=False, indent=2))
