import sys
sys.path.insert(0, "f:/ai/.accelerate/tmall-dashboard/backend")

from app.core.database import SessionLocal
from app.models import User

db = SessionLocal()

print("数据库中的用户:")
users = db.query(User).all()
print(f"  找到 {len(users)} 个用户")

for user in users:
    print(f"\n  用户名: {user.username}")
    print(f"  密码哈希: {user.hashed_password}")
    print(f"  角色: {user.role}")
    print(f"  活跃: {user.is_active}")

db.close()
