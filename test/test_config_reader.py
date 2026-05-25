"""临时测试：config_reader 模块"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from utils.config_reader import read_users, validate_user

print("=" * 50)
print("测试 1: 读取 users.csv")
try:
    users = read_users()
    print(f"读取到 {len(users)} 条记录:\n")
    for i, u in enumerate(users, 1):
        print(f"  [{i}] user_id={u['user_id']}, "
              f"username={u['username']}, "
              f"start={u['start_date']}, "
              f"end={u['end_date']}")
except Exception as e:
    print(f"❌ 读取失败: {e}")

print("\n" + "=" * 50)
print("测试 2: 日期格式校验")
for u in users:
    ok = validate_user(u)
    status = "✅" if ok else "❌"
    print(f"  {status} {u['user_id']}: {u['start_date']} ~ {u['end_date'] or '最新'}")

print("\n✅ config_reader 模块测试完成")