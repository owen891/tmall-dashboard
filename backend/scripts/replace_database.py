"""
使用完整数据库替换空数据库
"""
import sqlite3
import shutil
import os
from datetime import datetime

# Paths
DB_SOURCE = r"F:\ai\.accelerate\tmall-dashboard\backend\data\db\dashboard.db"
DB_TARGET = r"F:\ai\.accelerate\tmall-dashboard\backend\data\dashboard.db"
BACKUP_DIR = r"F:\ai\.accelerate\tmall-dashboard\backend\data\backups"

def replace_database():
    """用完整数据库替换空数据库"""
    print("=" * 70)
    print("使用完整数据库替换")
    print("=" * 70)
    
    # Backup current db
    if os.path.exists(DB_TARGET):
        os.makedirs(BACKUP_DIR, exist_ok=True)
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        backup_path = os.path.join(BACKUP_DIR, f'dashboard_backup_{timestamp}.db')
        shutil.copy2(DB_TARGET, backup_path)
        print(f"✓ 已备份当前数据库到: {backup_path}")
    
    # Copy source to target
    if os.path.exists(DB_SOURCE):
        shutil.copy2(DB_SOURCE, DB_TARGET)
        print(f"✓ 已从 {DB_SOURCE} 复制到 {DB_TARGET}")
    else:
        print(f"✗ 源数据库不存在: {DB_SOURCE}")
        return False
    
    # Verify
    conn = sqlite3.connect(DB_TARGET)
    cursor = conn.execute("PRAGMA table_info(weekly_data)")
    cols = [row[1] for row in cursor.fetchall()]
    count = conn.execute("SELECT COUNT(*) FROM weekly_data").fetchone()[0]
    conn.close()
    
    print(f"\nweekly_data表有 {len(cols)} 列")
    print(f"数据记录: {count} 条")
    return True

if __name__ == "__main__":
    replace_database()
