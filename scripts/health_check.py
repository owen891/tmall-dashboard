#!/usr/bin/env python3
"""每日健康检查：数据是否正常更新"""
import sqlite3
import sys
from datetime import datetime, timedelta
from pathlib import Path


def check_health():
    """检查数据库健康状态"""
    project_root = Path(__file__).parent.parent
    db_path = project_root / 'data' / 'dashboard.db'
    
    if not db_path.exists():
        print(f'❌ 数据库不存在: {db_path}')
        return False
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    print('\n' + '='*60)
    print('📊 天猫数据仪表盘 - 健康检查')
    print('='*60)
    
    # 1. 数据库基本信息
    size_mb = db_path.stat().st_size / 1024 / 1024
    print(f'\n💾 数据库大小: {size_mb:.1f} MB')
    print(f'📁 数据库路径: {db_path}')
    
    # 2. 检查最近数据
    today = datetime.now().strftime('%Y-%m-%d')
    yesterday = (datetime.now() - timedelta(days=1)).strftime('%Y-%m-%d')
    week_ago = (datetime.now() - timedelta(days=7)).strftime('%Y-%m-%d')
    
    cursor.execute('''
        SELECT date, payment_amount, successful_refund_amount, product_visitors, payment_buyers 
        FROM store_daily_facts 
        WHERE date >= ? 
        ORDER BY date DESC 
        LIMIT 7
    ''', (week_ago,))
    recent_data = cursor.fetchall()
    
    print(f'\n📈 最近 7 天数据:')
    if recent_data:
        for row in recent_data:
            date, payment, refund, visitors, buyers = row
            net_sales = (payment or 0) - (refund or 0)
            status = '✅' if payment and visitors else '⚠️'
            print(f'  {status} {date}: 支付金额 ¥{payment or 0:>10,.0f} | 退款 ¥{refund or 0:>8,.0f} | 访客 {visitors or 0:>5} | 买家 {buyers or 0:>4}')
    else:
        print(f'  ⚠️ 最近 7 天没有数据')
    
    # 3. 统计总记录数
    cursor.execute('SELECT COUNT(*) FROM store_daily_facts')
    total_records = cursor.fetchone()[0]
    print(f'\n📊 历史记录总数: {total_records:,} 条')
    
    # 4. 检查日期范围
    cursor.execute('''
        SELECT MIN(date), MAX(date) 
        FROM store_daily_facts 
        WHERE date IS NOT NULL
    ''')
    date_range = cursor.fetchone()
    if date_range[0]:
        print(f'📅 数据范围: {date_range[0]} ~ {date_range[1]}')
        days_span = (datetime.strptime(date_range[1], '%Y-%m-%d') - 
                     datetime.strptime(date_range[0], '%Y-%m-%d')).days
        print(f'⏱️  总天数: {days_span} 天')
    
    # 5. 检查商品数量
    cursor.execute("SELECT COUNT(*) FROM products WHERE COALESCE(status, 'active') = 'active'")
    active_products = cursor.fetchone()[0]
    cursor.execute('SELECT COUNT(*) FROM products')
    total_products = cursor.fetchone()[0]
    print(f'\n🛍️  商品数量: {active_products} 个在售 / {total_products} 个总计')
    
    # 6. 检查最近的批次导入
    cursor.execute('''
        SELECT id, source_type, created_at, inserted_count, total_rows
        FROM import_batches
        ORDER BY created_at DESC
        LIMIT 5
    ''')
    recent_batches = cursor.fetchall()
    if recent_batches:
        print(f'\n📥 最近 5 次导入:')
        for batch in recent_batches:
            batch_id, source, created_at, inserted_count, total_rows = batch
            source = source or 'unknown'
            created_at = created_at or 'unknown'
            print(f'  • {str(created_at)[:19]} | {source:15} | 写入 {inserted_count or 0:>4}/{total_rows or 0:<4} 条 | {str(batch_id)[:8]}...')
    
    # 7. 数据质量警告
    print(f'\n⚠️  数据质量检查:')
    
    # 检查是否有昨天的数据
    cursor.execute('SELECT COUNT(*) FROM store_daily_facts WHERE date = ?', (yesterday,))
    has_yesterday = cursor.fetchone()[0] > 0
    
    if has_yesterday:
        print(f'  ✅ 昨天 ({yesterday}) 有数据')
    else:
        print(f'  ⚠️  昨天 ({yesterday}) 没有数据')
    
    # 检查是否有空支付金额
    cursor.execute('''
        SELECT COUNT(*) 
        FROM store_daily_facts 
        WHERE date >= ? AND (payment_amount IS NULL OR payment_amount = 0)
    ''', (week_ago,))
    null_payment = cursor.fetchone()[0]
    
    if null_payment > 0:
        print(f'  ⚠️  最近 7 天有 {null_payment} 条记录支付金额为空或 0')
    else:
        print(f'  ✅ 最近 7 天支付数据完整')
    
    conn.close()
    
    print('\n' + '='*60)
    print('✅ 健康检查完成')
    print('='*60 + '\n')
    
    return True


if __name__ == '__main__':
    try:
        success = check_health()
        sys.exit(0 if success else 1)
    except Exception as e:
        print(f'\n❌ 健康检查失败: {e}')
        sys.exit(1)
