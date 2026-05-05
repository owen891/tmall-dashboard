"""
数据修复脚本：清空旧数据并重新导入原始数据
"""
import sqlite3
import shutil
import os
import sys
from datetime import datetime
from pathlib import Path

DB_PATH = os.path.join(os.path.dirname(__file__), 'data', 'dashboard.db')
BACKUP_DIR = os.path.join(os.path.dirname(__file__), 'data', 'backups')


def backup_database():
    """备份当前数据库"""
    os.makedirs(BACKUP_DIR, exist_ok=True)
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    backup_path = os.path.join(BACKUP_DIR, f'dashboard_backup_{timestamp}.db')
    
    if os.path.exists(DB_PATH):
        shutil.copy2(DB_PATH, backup_path)
        print(f"✓ 数据库已备份到: {backup_path}")
        return backup_path
    else:
        print("✗ 数据库文件不存在，跳过备份")
        return None


def clear_old_data():
    """清空旧的错误数据"""
    print("\n开始清空旧数据...")
    conn = sqlite3.connect(DB_PATH)
    
    tables_to_clear = [
        'daily_data', 'weekly_data', 'monthly_data',
        'product_traffic_detail', 'traffic_sources',
        'category_data', 'store_daily_data',
        'product', 'product_ranking',
        'operation_action', 'operation_log',
        'product_health',
        'paid_detail', 'paid_source_data',
        'sales_source_monthly', 'product_monthly_summary',
    ]
    
    for table in tables_to_clear:
        try:
            conn.execute(f"DELETE FROM {table}")
            print(f"  ✓ 清空 {table}")
        except Exception as e:
            print(f"  - {table} 不存在或清空失败: {e}")
    
    conn.commit()
    conn.close()
    print("✓ 旧数据已清空")


if __name__ == "__main__":
    print("=" * 70)
    print("数据修复工具")
    print("=" * 70)
    
    # Step 1: Backup
    backup_database()
    
    # Step 2: Clear old data
    clear_old_data()
    
    print("\n" + "=" * 70)
    print("数据清理完成，请运行导入脚本重新导入数据")
    print("=" * 70)
