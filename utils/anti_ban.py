"""
防封禁模块 - 随机延时 + 模拟人类行为
每完成一次操作（爬取一条微博、滚动页面等）后调用，降低被封风险
"""

import random
import time
from loguru import logger


def random_delay(min_sec: float = 2.0, max_sec: float = 5.0, reason: str = "") -> float:
    """
    在 [min_sec, max_sec] 范围内随机休眠

    Args:
        min_sec: 最小秒数
        max_sec: 最大秒数
        reason: 延时原因（用于日志，可选）

    Returns:
        实际休眠的秒数
    """
    delay = round(random.uniform(min_sec, max_sec), 2)
    msg = f"⏳ 随机延时 {delay}s"
    if reason:
        msg += f"（{reason}）"
    logger.info(msg)
    time.sleep(delay)
    return delay


def human_like_delay(min_sec: float = 3.0, max_sec: float = 8.0) -> float:
    """
    模拟人类浏览行为的复合延时

    人类不会匀速间隔操作，而是偶尔连续、偶尔停顿。
    此函数将总延时拆成 2~3 小段，中间夹杂微小的"思考"停顿，
    整体更接近真实浏览节奏。

    Args:
        min_sec: 总最小秒数
        max_sec: 总最大秒数

    Returns:
        实际总休眠秒数
    """
    total_delay = round(random.uniform(min_sec, max_sec), 2)
    chunks = random.randint(2, 4)  # 拆成 2~4 段
    remaining = total_delay

    logger.debug(f"🕐 模拟人类浏览，总延时 {total_delay}s，拆分为 {chunks} 段")

    for i in range(chunks - 1):
        segment = round(random.uniform(0.5, remaining - 0.5 * (chunks - i - 1)), 2)
        if segment > 0:
            time.sleep(segment)
            remaining -= segment
    time.sleep(round(remaining, 2))

    logger.info(f"⏳ 人类模拟延时完成，共 {total_delay}s")
    return total_delay