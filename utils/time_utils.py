"""
时间工具模块
- 解析 CSV 中的日期字符串
- 微博时间格式转换（如 "1小时前" 等相对时间）
- 判断微博时间是否在配置的时间范围内
"""

import re
from datetime import datetime, timedelta
from typing import Optional, Union


# ============================================================
# 日期格式常量
# ============================================================
DATE_FORMATS = [
    "%Y-%m-%d",          # 2025-01-15
    "%Y/%m/%d",          # 2025/01/15
    "%Y%m%d",            # 20250115
    "%Y-%m-%d %H:%M:%S", # 2025-01-15 10:30:00
    "%Y/%m/%d %H:%M:%S", # 2025/01/15 10:30:00
    "%Y-%m-%d %H:%M",    # 2025-01-15 10:30
    "%Y/%m/%d %H:%M",    # 2025/01/15 10:30
]

# 微博列表页常见时间格式
WEIBO_TIME_PATTERNS = [
    re.compile(r"^(\d+)分钟前$"),
    re.compile(r"^(\d+)小时前$"),
    re.compile(r"^昨天\s*(\d{2}):(\d{2})$"),
    re.compile(r"^前天\s*(\d{2}):(\d{2})$"),
    re.compile(r"^(\d{1,2})月(\d{1,2})日\s*(\d{2}):(\d{2})$"),
    re.compile(r"^(\d{4})-(\d{2})-(\d{2})\s*(\d{2}):(\d{2})$"),
    re.compile(r"^(\d{4})/(\d{2})/(\d{2})\s*(\d{2}):(\d{2})$"),
]


# ============================================================
# 核心函数
# ============================================================
def parse_date(date_str: str) -> Optional[datetime]:
    """
    尝试用预定义的多种格式解析日期字符串

    Args:
        date_str: 日期字符串，如 "2025-01-15"

    Returns:
        解析成功返回 datetime 对象，失败返回 None
    """
    if not date_str or not isinstance(date_str, str):
        return None

    date_str = date_str.strip()

    for fmt in DATE_FORMATS:
        try:
            return datetime.strptime(date_str, fmt)
        except ValueError:
            continue

    return None


def parse_weibo_time(time_str: str, now: Optional[datetime] = None) -> Optional[datetime]:
    """
    解析微博列表页的相对时间文本，转为绝对 datetime

    支持格式：
        - "X分钟前"
        - "X小时前"
        - "昨天 HH:MM"
        - "前天 HH:MM"
        - "MM月DD日 HH:MM"（跨年自动推断年份）
        - "YYYY-MM-DD HH:MM"

    Args:
        time_str: 微博页面上的时间文本
        now: 参考时间（默认为当前时间）

    Returns:
        datetime 对象，解析失败返回 None
    """
    if not time_str or not isinstance(time_str, str):
        return None

    if now is None:
        now = datetime.now()

    time_str = time_str.strip()

    # "X分钟前"
    m = re.match(r"^(\d+)分钟前$", time_str)
    if m:
        minutes = int(m.group(1))
        return now - timedelta(minutes=minutes)

    # "X小时前"
    m = re.match(r"^(\d+)小时前$", time_str)
    if m:
        hours = int(m.group(1))
        return now - timedelta(hours=hours)

    # "昨天 HH:MM"
    m = re.match(r"^昨天\s*(\d{1,2}):(\d{2})$", time_str)
    if m:
        yesterday = now - timedelta(days=1)
        return yesterday.replace(hour=int(m.group(1)), minute=int(m.group(2)), second=0, microsecond=0)

    # "前天 HH:MM"
    m = re.match(r"^前天\s*(\d{1,2}):(\d{2})$", time_str)
    if m:
        two_days_ago = now - timedelta(days=2)
        return two_days_ago.replace(hour=int(m.group(1)), minute=int(m.group(2)), second=0, microsecond=0)

    # "MM月DD日 HH:MM"
    m = re.match(r"^(\d{1,2})月(\d{1,2})日\s*(\d{1,2}):(\d{2})$", time_str)
    if m:
        month, day = int(m.group(1)), int(m.group(2))
        hour, minute = int(m.group(3)), int(m.group(4))
        year = now.year
        # 如果推算出的时间比当前晚，说明是去年
        result = datetime(year, month, day, hour, minute)
        if result > now:
            result = datetime(year - 1, month, day, hour, minute)
        return result

    # "YYYY-MM-DD HH:MM"
    m = re.match(r"^(\d{4})-(\d{2})-(\d{2})\s*(\d{1,2}):(\d{2})$", time_str)
    if m:
        return datetime(int(m.group(1)), int(m.group(2)), int(m.group(3)),
                        int(m.group(4)), int(m.group(5)))

    # "YYYY/MM/DD HH:MM"
    m = re.match(r"^(\d{4})/(\d{2})/(\d{2})\s*(\d{1,2}):(\d{2})$", time_str)
    if m:
        return datetime(int(m.group(1)), int(m.group(2)), int(m.group(3)),
                        int(m.group(4)), int(m.group(5)))

    # 最后尝试标准日期解析（不含时间的）
    return parse_date(time_str)


def is_in_range(
    weibo_time: Union[str, datetime],
    start: Union[str, datetime],
    end: Union[str, datetime]
) -> bool:
    """
    判断微博时间是否在 [start, end] 范围内（含边界）

    Args:
        weibo_time: 微博发布时间
        start: 配置的开始日期
        end: 配置的结束日期

    Returns:
        True 表示在范围内
    """
    # 转为 datetime
    if isinstance(start, str):
        start_dt = parse_date(start)
        if start_dt is None:
            raise ValueError(f"无法解析开始日期: {start}")
    else:
        start_dt = start

    if isinstance(end, str):
        end_dt = parse_date(end)
        if end_dt is None:
            raise ValueError(f"无法解析结束日期: {end}")
    else:
        end_dt = end

    if isinstance(weibo_time, str):
        weibo_dt = parse_weibo_time(weibo_time)
        if weibo_dt is None:
            # 宽松处理：解析失败时不拦截，返回 True
            return True
    else:
        weibo_dt = weibo_time
        
    # 防御：如果 weibo_dt 带时区，去除
    if weibo_dt.tzinfo is not None:
        weibo_dt = weibo_dt.replace(tzinfo=None)

    # end 只给到日期的话，补全到当天 23:59:59
    if end_dt.hour == 0 and end_dt.minute == 0 and end_dt.second == 0:
        end_dt = end_dt.replace(hour=23, minute=59, second=59)

    return start_dt <= weibo_dt <= end_dt


def is_before_start(
    weibo_time: Union[str, datetime],
    start: Union[str, datetime]
) -> bool:
    if isinstance(start, str):
        start_dt = parse_date(start)
    else:
        start_dt = start

    if isinstance(weibo_time, str):
        weibo_dt = parse_weibo_time(weibo_time)
        if weibo_dt is None:
            return False
    else:
        weibo_dt = weibo_time

    # 防御：如果 weibo_dt 带时区，去除
    if weibo_dt.tzinfo is not None:
        weibo_dt = weibo_dt.replace(tzinfo=None)

    return weibo_dt < start_dt