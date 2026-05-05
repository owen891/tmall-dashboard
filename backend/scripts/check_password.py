import sqlite3
import hashlib
import sys

SALT = "haibeihai_dashboard_2026"

def hash_password(password):
    return hashlib.sha256((password + SALT).encode()).hexdigest()

DB_PATH = "F:\\ai\\.accelerate\\tmall-dashboard\\data\\dashboard.db"

conn = sqlite3.connect(DB_PATH)
cursor = conn.execute("SELECT username, hashed_password FROM users")
rows = cursor.fetchall()

print("=" * 60)
print("数据库中的密码哈希:")
print("=" * 60)
for username, stored_hash in rows:
    print(f"  {username}: {stored_hash}")

print("\n" + "=" * 60)
print("实际生成的哈希 (用于验证):")
print("=" * 60)
test_passwords = {"admin": "admin123", "manager": "manager123", "viewer": "viewer123"}
for username, password in test_passwords.items():
    expected = hash_password(password)
    print(f"  {username}: {expected}")
    
    # 检查匹配
    for db_user, db_hash in rows:
        if db_user == username:
            if db_hash == expected:
                print(f"    ✓ 密码匹配成功")
            else:
                print(f"    ✗ 密码不匹配!")
                print(f"    数据库: {db_hash}")
                print(f"    期望:   {expected}")

conn.close()
