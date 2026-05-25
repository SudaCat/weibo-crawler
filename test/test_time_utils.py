"""临时测试：time_utils 模块"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from utils.time_utils import parse_date, parse_weibo_time, is_in_range, is_before_start
from datetime import datetime

print("=" * 50)
print("测试 1: parse_date 解析标准日期")
dates = ["2025-01-15", "2025/01/15", "20250115", "2025-01-15 10:30:00", " 2025-01-15 "]
for d in dates:
    result = parse_date(d)
    print(f"  '{d}' → {result}")

print("\n" + "=" * 50)
print("测试 2: parse_weibo_time 解析微博相对时间")
times = [
    ("5分钟前", datetime(2025, 1, 15, 12, 0, 0)),
    ("3小时前", datetime(2025, 1, 15, 12, 0, 0)),
    ("昨天 08:30", datetime(2025, 1, 15, 10, 0, 0)),
    ("前天 22:00", datetime(2025, 1, 17, 10, 0, 0)),
    ("1月15日 10:30", datetime(2025, 1, 20, 12, 0, 0)),
    ("2025-01-15 10:30", datetime(2025, 1, 20, 12, 0, 0)),
    ("12月31日 23:59", datetime(2025, 1, 5, 12, 0, 0)),  # 跨年的
]
for time_str, now in times:
    result = parse_weibo_time(time_str, now)
    print(f"  '{time_str}' (now={now}) → {result}")

print("\n" + "=" * 50)
print("测试 3: is_in_range 判断时间范围")
weibo_time = "2025-01-15 10:30"
print(f"  '{weibo_time}' 在 2025-01-01 ~ 2025-01-31 内? → {is_in_range(weibo_time, '2025-01-01', '2025-01-31')}")
print(f"  '{weibo_time}' 在 2025-02-01 ~ 2025-02-28 内? → {is_in_range(weibo_time, '2025-02-01', '2025-02-28')}")

print("\n" + "=" * 50)
print("测试 4: is_before_start 判断是否早于开始日期")
times_to_test = [
    "2025-01-01 08:00",
    "2025-01-15 12:00",
]
start = "2025-01-10"
for t in times_to_test:
    print(f"  '{t}' 早于 {start}? → {is_before_start(t, start)}")

print("\n✅ time_utils 模块测试完成")