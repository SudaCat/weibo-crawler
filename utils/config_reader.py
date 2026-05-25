"""
配置文件读取模块
解析 users.csv（| 分隔），返回结构化用户列表
"""

import csv
from pathlib import Path
from typing import Optional

from loguru import logger

from config.settings import USERS_CSV


def read_users(csv_path: Optional[Path] = None) -> list[dict]:
    """
    读取用户配置文件

    Args:
        csv_path: CSV 文件路径，默认使用 settings.USERS_CSV

    Returns:
        用户列表，每条记录为 dict:
        {
            "user_id": str,
            "username": str,
            "start_date": str,
            "end_date": str | None   # None 表示无结束时间限制
        }

    Raises:
        FileNotFoundError: 文件不存在
        ValueError: 必填字段缺失
    """
    if csv_path is None:
        csv_path = USERS_CSV

    if not csv_path.exists():
        raise FileNotFoundError(f"用户配置文件不存在: {csv_path}")

    users = []

    with open(csv_path, "r", encoding="utf-8-sig") as f:  # utf-8-sig 自动去除 BOM
        reader = csv.DictReader(f, delimiter="|")

        # 校验表头
        expected_fields = ["用户id", "用户名", "微博发布时间_开始", "微博发布时间_结束"]
        actual_fields = reader.fieldnames
        if actual_fields is None:
            raise ValueError("CSV 文件为空或格式错误")

        # 去除字段名两端空格
        actual_fields = [f.strip() for f in actual_fields]
        if actual_fields != expected_fields:
            raise ValueError(
                f"CSV 表头不匹配\n"
                f"  期望: {expected_fields}\n"
                f"  实际: {actual_fields}"
            )

        for line_no, row in enumerate(reader, start=2):  # 第2行开始是数据
            # 去除每个字段的空白
            row = {k.strip(): v.strip() if v else "" for k, v in row.items()}

            user_id = row.get("用户id", "")
            username = row.get("用户名", "")
            start_date = row.get("微博发布时间_开始", "")
            end_date = row.get("微博发布时间_结束", "")

            # 必填校验
            if not user_id:
                logger.warning(f"第 {line_no} 行: 用户id 为空，跳过")
                continue
            if not start_date:
                logger.warning(f"第 {line_no} 行 ({user_id}): 微博发布时间_开始 为空，跳过")
                continue

            # 空字符串 → None
            end_date = end_date if end_date else None

            user = {
                "user_id": user_id,
                "username": username or "",  # 用户名为空时用空字符串
                "start_date": start_date,
                "end_date": end_date,
            }
            users.append(user)

    logger.info(f"成功读取 {len(users)} 个用户配置")
    return users


def validate_user(user: dict) -> bool:
    """
    校验单条用户记录的日期格式是否合法

    Args:
        user: 用户 dict

    Returns:
        True = 校验通过
    """
    from utils.time_utils import parse_date

    start_dt = parse_date(user.get("start_date", ""))
    if start_dt is None:
        logger.error(f"用户 {user.get('user_id')}: 开始日期格式无效: {user.get('start_date')}")
        return False

    if user.get("end_date"):
        end_dt = parse_date(user["end_date"])
        if end_dt is None:
            logger.error(f"用户 {user.get('user_id')}: 结束日期格式无效: {user.get('end_date')}")
            return False
        if end_dt < start_dt:
            logger.error(f"用户 {user.get('user_id')}: 结束日期早于开始日期")
            return False

    return True