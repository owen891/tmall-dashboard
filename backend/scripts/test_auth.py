import sys
sys.path.insert(0, "f:/ai/.accelerate/tmall-dashboard/backend")

from app.core.database import SessionLocal
from app.core.security import authenticate_user, hash_password

db = SessionLocal()

print("测试密码哈希:")
print(f"  admin123: {hash_password('admin123')}")
print(f"  manager123: {hash_password('manager123')}")

print("\n测试认证:")
user = authenticate_user(db, "admin", "admin123")
if user:
    print(f"  ✓ admin 认证成功: {user.username} / {user.role}")
else:
    print("  ✗ admin 认证失败")

user = authenticate_user(db, "manager", "manager123")
if user:
    print(f"  ✓ manager 认证成功: {user.username} / {user.role}")
else:
    print("  ✗ manager 认证失败")

user = authenticate_user(db, "viewer", "viewer123")
if user:
    print(f"  ✓ viewer 认证成功: {user.username} / {user.role}")
else:
    print("  ✗ viewer 认证失败")

db.close()
