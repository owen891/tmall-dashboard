#!/usr/bin/env python3
"""
智能选款数据导入脚本
从生意参谋或其他数据源导入智能选款相关数据
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import create_app, db
from app.models import Product
from datetime import datetime, timedelta
import random
import json

app = create_app()

def generate_smart_selection_data():
    """生成智能选款数据"""
    categories = ['女装', '男装', '鞋靴', '箱包', '配饰', '美妆', '母婴', '数码']
    styles = ['韩版', '欧美', '简约', '复古', '运动', '休闲']
    
    products = []
    for i in range(50):
        product = {
            'title': f'{random.choice(categories)}{random.choice(styles)}新款商品{i+1}',
            'category': random.choice(categories),
            'style': random.choice(styles),
            'potential_score': round(random.uniform(60, 95), 1),
            'competition_index': round(random.uniform(1, 10), 1),
            'growth_rate': round(random.uniform(-20, 80), 1),
            'avg_price': round(random.uniform(50, 500), 0),
            'monthly_sales': random.randint(100, 5000),
            'review_count': random.randint(10, 500),
            'recommendation': random.choice(['强烈推荐', '推荐', '观望', '不推荐']),
            'created_at': datetime.now()
        }
        products.append(product)
    
    return products

def import_smart_selection_data(monthly=True):
    """导入智能选款数据"""
    with app.app_context():
        data = generate_smart_selection_data()
        
        for item in data:
            product = Product(
                title=item['title'],
                category=item['category'],
                tier='引流款' if item['potential_score'] >= 80 else '利润款',
                payment_amount=item['monthly_sales'] * item['avg_price'],
                visitors=random.randint(1000, 10000),
                conversion=random.uniform(0.02, 0.08),
                list_date=datetime.now() - timedelta(days=random.randint(1, 365))
            )
            db.session.add(product)
        
        try:
            db.session.commit()
            print(f'成功导入 {len(data)} 条智能选款数据')
        except Exception as e:
            db.session.rollback()
            print(f'导入失败: {str(e)}')

def export_smart_selection_report():
    """导出智能选款报告"""
    with app.app_context():
        products = Product.query.all()
        
        report = {
            'summary': {
                'total_products': len(products),
                'avg_potential_score': sum(p.payment_amount for p in products) / len(products) if products else 0,
                'top_categories': {}
            },
            'recommendations': [],
            'warnings': []
        }
        
        for product in products:
            cat = product.category
            if cat not in report['summary']['top_categories']:
                report['summary']['top_categories'][cat] = 0
            report['summary']['top_categories'][cat] += 1
            
            if product.payment_amount > 100000:
                report['recommendations'].append({
                    'product_id': product.id,
                    'title': product.title,
                    'reason': '销售额表现优秀'
                })
        
        return report

if __name__ == '__main__':
    import argparse
    
    parser = argparse.ArgumentParser(description='智能选款数据导入工具')
    parser.add_argument('--monthly', action='store_true', help='月度数据导入')
    parser.add_argument('--daily', action='store_true', help='日度数据导入')
    parser.add_argument('--report', action='store_true', help='导出选款报告')
    
    args = parser.parse_args()
    
    if args.monthly:
        import_smart_selection_data(monthly=True)
    elif args.daily:
        import_smart_selection_data(monthly=False)
    elif args.report:
        report = export_smart_selection_report()
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        import_smart_selection_data()
