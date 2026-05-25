"""临时测试：excel_writer 模块"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from utils.excel_writer import write_results

print("=" * 50)
print("测试 1: 写入模拟数据到 Excel")

fake_data = [
    {
        "用户id": "1685872053",
        "用户名": "李沛恩Pein_",
        "微博发布时间": "2025-05-22 14:30:00",
        "微博类型": "原创",
        "文案": "今天天气真好，出去玩了一整天！",
        "图片数量": 3,
        "Live图数量": 1,
        "视频数量": 0,
        "图片下载数量": 3,
        "Live图下载数量": 1,
        "视频下载数量": 0,
        "爬虫结果": "成功",
        "微博url": "https://weibo.com/1685872053/AbCdEfGhIj",
    },
    {
        "用户id": "1685872053",
        "用户名": "李沛恩Pein_",
        "微博发布时间": "2025-05-22 10:00:00",
        "微博类型": "转发",
        "文案": "转发微博",
        "图片数量": 0,
        "Live图数量": 0,
        "视频数量": 1,
        "图片下载数量": 0,
        "Live图下载数量": 0,
        "视频下载数量": 1,
        "爬虫结果": "成功",
        "微博url": "https://weibo.com/1685872053/XyZ123",
    },
    {
        "用户id": "7927065948",
        "用户名": "江衡oc",
        "微博发布时间": "2025-05-21 18:00:00",
        "微博类型": "原创",
        "文案": "今天是520的后一天，补发一条❤️",
        "图片数量": 6,
        "Live图数量": 2,
        "视频数量": 0,
        "图片下载数量": 6,
        "Live图下载数量": 2,
        "视频下载数量": 0,
        "爬虫结果": "成功",
        "微博url": "https://weibo.com/7927065948/MnOpQrSt",
    },
]

output_path = write_results(fake_data)
print(f"\n✅ 文件已生成: {output_path}")
print("请手动打开检查字段是否完整、格式是否正确")