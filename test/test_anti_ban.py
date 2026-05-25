"""临时测试：anti_ban 模块"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))  # 将项目根目录加入路径

from utils.anti_ban import random_delay, human_like_delay

print("=" * 50)
print("测试 1: 基础随机延时（1~3秒，重复3次）")
for i in range(3):
    random_delay(1, 3, reason=f"第{i+1}次测试")

print("\n" + "=" * 50)
print("测试 2: 人类模拟延时（3~8秒，重复2次）")
for i in range(2):
    human_like_delay(3, 8)

print("\n✅ anti_ban 模块测试完成")