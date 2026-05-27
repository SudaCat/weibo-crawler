"""
微博内容截图模块
- 按 XPath 定位微博正文区域并截图
- 保存至对应微博媒体文件夹内
- 自动清理文件名非法字符
- 完全独立，不依赖爬虫或下载器模块
"""

import re
from pathlib import Path
from typing import Optional

from loguru import logger
from playwright.sync_api import Page, Locator

from config.settings import (
    DOWNLOAD_DIR,
    SCREENSHOT_FORMAT,
    SCREENSHOT_QUALITY,
    WEIBO_CONTENT_XPATHS,
)


class ScreenshotCapture:
    """微博内容截图器（独立模块，可单独启用/禁用）"""

    def __init__(self):
        pass

    # ================================================================
    # 公开方法：截取单条微博正文
    # ================================================================
    def capture_weibo(
        self,
        page: Page,
        user_id: str,
        weibo_time: str,
        weibo_id: str,
        content: str,
        weibo_element: Optional[Locator] = None,
    ) -> Optional[Path]:
        """
        截取一条微博的正文区域并保存

        Args:
            page:          Playwright Page 对象
            user_id:       用户 ID
            weibo_time:    发布时间 YYYYMMDD_hhmmss
            weibo_id:      微博唯一标识
            content:       文案（用于文件夹命名和截图区域查找）
            weibo_element: 可选，已定位的微博元素 Locator。若为 None 则在页面全文中按 xpath 查找

        Returns:
            截图文件路径，失败返回 None
        """
        # 1. 确定目标目录（与下载同一文件夹）
        folder_name = self._make_folder_name(weibo_time, weibo_id, content)
        target_dir = DOWNLOAD_DIR / user_id / folder_name
        target_dir.mkdir(parents=True, exist_ok=True)

        # 2. 截图文件名
        filename = f"{folder_name}_screenshot.{SCREENSHOT_FORMAT}"
        save_path = target_dir / filename

        # 3. 定位要截图的元素
        target = None
        if weibo_element:
            target = weibo_element
        else:
            target = self._locate_content_area(page)

        if target is None:
            logger.warning(f"⚠️ 未找到微博正文区域，将截取整页（微博 {weibo_id}）")
            try:
                page.screenshot(path=str(save_path), full_page=False)
                logger.info(f"📸 已截取整页: {save_path}")
                return save_path
            except Exception as e:
                logger.error(f"❌ 整页截图失败: {e}")
                return None

        # 4. 执行元素截图
        try:
            target.screenshot(path=str(save_path))
            logger.info(f"📸 微博正文截图已保存: {save_path}")
            return save_path
        except Exception as e:
            logger.error(f"❌ 元素截图失败: {e}")
            return None

    # ================================================================
    # 内部定位逻辑：按 settings 中 XPath 列表依次尝试
    # ================================================================
    def _locate_content_area(self, page: Page) -> Optional[Locator]:
        """
        在页面中查找第一条可见的微博正文区域

        按 WEIBO_CONTENT_XPATHS 优先级尝试，
        返回第一个可见且矩形区域 > 0 的元素
        """
        for xpath in WEIBO_CONTENT_XPATHS:
            try:
                loc = page.locator(f"xpath={xpath}").first
                if loc.count() > 0:
                    # 检查是否可见且有一定大小
                    box = loc.bounding_box()
                    if box and box["width"] > 100 and box["height"] > 50:
                        logger.debug(f"✅ 定位到微博正文区域 (xpath: {xpath})")
                        return loc
            except Exception:
                continue

        # 备选：尝试用 Playwright 内置角色
        try:
            loc = page.get_by_role("article").first
            if loc.count() > 0:
                box = loc.bounding_box()
                if box and box["width"] > 100 and box["height"] > 50:
                    logger.debug("✅ 定位到微博正文区域 (role=article)")
                    return loc
        except Exception:
            pass

        return None

    # ================================================================
    # 文件夹命名工具
    # ================================================================
    @staticmethod
    def _make_folder_name(weibo_time: str, weibo_id: str, content: str) -> str:
        safe = ScreenshotCapture._sanitize_text(content)
        return f"{weibo_time}_{weibo_id}_{safe}"

    @staticmethod
    def _sanitize_text(text: str, max_len: int = 50) -> str:
        """清理文件名中的非法字符"""
        if not text:
            return "无文案"
        text = re.sub(r'[\\/:*?"<>|]', '', text)
        text = re.sub(r'\s+', ' ', text).strip()
        return text[:max_len]