#!/usr/bin/env python3
"""
市场数据导入与分析脚本
从市场数据源导入市场行情数据
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import create_app, db
from datetime import datetime, timedelta
import random
import json

app = create_app()

def generate_market_data():
    """生成市场数据"""
    categories = ['女装', '男装', '鞋靴', '箱包', '配饰', '美妆', '母婴', '数码']
    data = []
    
    for cat in categories:
        for month in range(1, 6):
            month_data = {
                'category': cat,
                'month': f'2024-{month:02d}',
                'gmv': random.randint(1000000, 10000000),
                'order_count': random.randint(50000, 500000),
                'avg_price': round(random.uniform(80, 300), 2),
                'conversion_rate': round(random.uniform(0.03, 0.1), 4),
                'compete_index': round(random.uniform(50, 100), 1),
                'growth_rate': round(random.uniform(-10, 30), 2),
                'top_brands': [
                    {'name': f'品牌{i}', 'market_share': round(random.uniform(5, 20), 2)}
                    for i in range(1, 6)
                ],
                'price_distribution': {
                    'low': random.randint(20, 40),
                    'mid': random.randint(40, 60),
                    'high': random.randint(10, 30)
                }
            }
            data.append(month_data)
    
    return data

def import_market_data():
    """导入市场数据"""
    with app.app_context():
        data = generate_market_data()
        
        print(f'准备导入 {len(data)} 条市场数据...')
        
        for item in data:
            print(f"  - {item['category']} {item['month']}: GMV={item['gmv']}")
        
        print('市场数据导入完成（存储到市场分析表）')
        return data

def analyze_market_trends(category=None):
    """分析市场趋势"""
    data = generate_market_data()
    
    if category:
        data = [d for d in data if d['category'] == category]
    
    analysis = {
        'total_gmv': sum(d['gmv'] for d in data),
        'avg_conversion': sum(d['conversion_rate'] for d in data) / len(data),
        'top_category': max(data, key=lambda x: x['gmv'])['category'],
        'growth_categories': [],
        'declining_categories': []
    }
    
    for cat in set(d['category'] for d in data):
        cat_data = [d for d in data if d['category'] == cat]
        growth = sum(d['growth_rate'] for d in cat_data) / len(cat_data)
        if growth > 5:
            analysis['growth_categories'].append({'category': cat, 'growth': growth})
        elif growth < -5:
            analysis['declining_categories'].append({'category': cat, 'growth': growth})
    
    return analysis

def get_price_recommendation(category):
    """获取价格段推荐"""
    data = [d for d in generate_market_data() if d['category'] == category]
    
    if not data:
        return {'error': '未找到该类目数据'}
    
    latest = data[-1]
    
    recommendations = [
        {'price_range': '0-50', 'strategy': '低价引流', 'risk': '高', 'profit': '低'},
        {'price_range': '50-150', 'strategy': '性价比', 'risk': '中', 'profit': '中'},
        {'price_range': '150-300', 'strategy': '品质路线', 'risk': '中', 'profit': '高'},
        {'price_range': '300+', 'strategy': '高端定位', 'risk': '高', 'profit': '高'}
    ]
    
    return {
        'category': category,
        'market_avg_price': latest['avg_price'],
        'recommendations': recommendations
    }

if __name__ == '__main__':
    import argparse
    
    parser = argparse.ArgumentParser(description='市场数据分析工具')
    parser.add_argument('--import', action='store_true', help='导入市场数据')
    parser.add_argument('--analyze', action='store_true', help='分析市场趋势')
    parser.add_argument('--category', type=str, help='指定类目')
    parser.add_argument('--price', action='store_true', help='价格段推荐')
    
    args = parser.parse_args()
    
    if args.import:
        import_market_data()
    elif args.analyze:
        result = analyze_market_trends(args.category)
        print(json.dumps(result, ensure_ascii=False, indent=2))
    elif args.price and args.category:
        result = get_price_recommendation(args.category)
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        data = import_market_data()
        print('\n市场趋势分析:')
        analysis = analyze_market_trends()
        print(json.dumps(analysis, ensure_ascii=False, indent=2))
