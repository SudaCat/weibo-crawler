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
            "end_date": str,          # 为空时自动取当前系统时间
            "last_crawl_time": str,   # 最近一次抓取时间
            "last_run_time": str,     # 最近一次运行时间
            "enabled": bool,          # 是否生效
            "download_media": bool,   # 是否下载媒体文件
        }

    Raises:
        FileNotFoundError: 文件不存在
        ValueError: 必填字段缺失
    """
    if csv_path is None:
        csv_path = USERS_CSV

    if not csv_path.exists():
        csv_path.parent.mkdir(parents=True, exist_ok=True)
        with open(csv_path, "w", encoding="utf-8") as f:
            f.write("用户id,用户名,抓取开始时间,抓取停止时间,最后抓取时间,最后运行时间,是否生效,是否下载媒体文件\n")
        logger.info(f"📄 已创建用户配置文件: {csv_path}")
        return []

    users = []

    with open(csv_path, "r", encoding="utf-8-sig") as f:  # utf-8-sig 自动去除 BOM
        reader = csv.DictReader(f, delimiter=",")

        # 校验表头
        expected_fields = ["用户id", "用户名", "抓取开始时间", "抓取停止时间", "最后抓取时间", "最后运行时间", "是否生效", "是否下载媒体文件"]
        actual_fields = reader.fieldnames
        if actual_fields is None:
            raise ValueError("CSV 文件为空或格式错误")

        # 去除字段名两端空格
        actual_fields = [f.strip() for f in actual_fields]

        # 自动迁移旧格式
        _migrate_csv_if_needed(csv_path, actual_fields, expected_fields)

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
            start_date = row.get("抓取开始时间", "")
            end_date = row.get("抓取停止时间", "")
            last_crawl_time = row.get("最后抓取时间", "")
            last_run_time = row.get("最后运行时间", "")
            enabled = row.get("是否生效", "是")
            download_media = row.get("是否下载媒体文件", "是")

            # 必填校验
            if not user_id:
                logger.warning(f"第 {line_no} 行: 用户id 为空，跳过")
                continue
            if not start_date:
                logger.warning(f"第 {line_no} 行 ({user_id}): 抓取开始时间 为空，跳过")
                continue

            # 抓取停止时间为空 → 默认当前系统时间
            if not end_date:
                from datetime import datetime
                end_date = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

            user = {
                "user_id": user_id,
                "username": username or "",  # 用户名为空时用空字符串
                "start_date": start_date,
                "end_date": end_date,
                "last_crawl_time": last_crawl_time or "",
                "last_run_time": last_run_time or "",
                "enabled": enabled.strip() == "是",
                "download_media": download_media.strip() == "是",
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


def _migrate_csv_if_needed(
    csv_path: Path, actual_fields: list[str], expected_fields: list[str]
) -> None:
    """自动迁移旧版 CSV 格式，添加缺失列（默认值"是"）"""
    missing = [f for f in expected_fields if f not in actual_fields]
    if not missing:
        return

    logger.info(f"📄 检测到旧版 CSV 格式，自动添加 {len(missing)} 列: {missing}")
    rows_migrate = []
    with open(csv_path, "r", encoding="utf-8-sig") as f:
        old_reader = csv.DictReader(f, delimiter=",")
        for row in old_reader:
            row = {k.strip(): v.strip() if v else "" for k, v in row.items()}
            for col in missing:
                row[col] = "是"
            rows_migrate.append(row)

    with open(csv_path, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=expected_fields, delimiter=",")
        writer.writeheader()
        writer.writerows(rows_migrate)

    actual_fields.clear()
    actual_fields.extend(expected_fields)


def update_last_crawl_time(
    user_id: str, timestamp: str, csv_path: Optional[Path] = None
) -> None:
    """更新指定用户的最后抓取时间（应为最后一条微博的发布时间）

    Args:
        user_id: 用户 ID
        timestamp: 时间字符串（格式 YYYY-MM-DD HH:MM:SS）
        csv_path: CSV 文件路径，默认使用 settings.USERS_CSV
    """
    import csv

    if csv_path is None:
        csv_path = USERS_CSV

    if not csv_path.exists():
        logger.warning(f"CSV 文件不存在，无法更新最后抓取时间: {csv_path}")
        return

    rows = []
    with open(csv_path, "r", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f, delimiter=",")
        fieldnames = reader.fieldnames
        for row in reader:
            row = {k.strip(): v.strip() if v else "" for k, v in row.items()}
            if row.get("用户id") == user_id:
                row["最后抓取时间"] = timestamp
            rows.append(row)

    with open(csv_path, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, delimiter=",")
        writer.writeheader()
        writer.writerows(rows)


def update_last_run_time(
    user_id: str, timestamp: str, csv_path: Optional[Path] = None
) -> None:
    """更新指定用户的最后运行时间（当前系统时间）

    Args:
        user_id: 用户 ID
        timestamp: 时间字符串（格式 YYYY-MM-DD HH:MM:SS）
        csv_path: CSV 文件路径，默认使用 settings.USERS_CSV
    """
    import csv

    if csv_path is None:
        csv_path = USERS_CSV

    if not csv_path.exists():
        logger.warning(f"CSV 文件不存在，无法更新最后运行时间: {csv_path}")
        return

    rows = []
    with open(csv_path, "r", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f, delimiter=",")
        fieldnames = reader.fieldnames
        for row in reader:
            row = {k.strip(): v.strip() if v else "" for k, v in row.items()}
            if row.get("用户id") == user_id:
                row["最后运行时间"] = timestamp
            rows.append(row)

    with open(csv_path, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, delimiter=",")
        writer.writeheader()
        writer.writerows(rows)