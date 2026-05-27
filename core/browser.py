"""
Playwright 浏览器实例管理
- 启动 Chromium（支持 headless / 有头模式）
- 注入反检测脚本
- 提供统一的新页面获取方法
- 负责浏览器资源的创建与销毁
"""

from pathlib import Path
from typing import Optional

from loguru import logger

from config.settings import (
    HEADLESS,
    VIEWPORT_WIDTH,
    VIEWPORT_HEIGHT,
    PAGE_TIMEOUT,
    USER_AGENT,
    STEALTH_JS,
    COOKIE_FILE,
)
from playwright.sync_api import Browser, BrowserContext, Page, sync_playwright


class BrowserManager:
    """
    浏览器管理器（单例风格，非严格单例）

    用法:
        bm = BrowserManager()
        bm.start()
        page = bm.new_page()
        # ... 操作 ...
        bm.stop()
    """

    def __init__(self):
        self._playwright = None
        self._browser: Optional[Browser] = None
        self._context: Optional[BrowserContext] = None

    # ================================================================
    # 启动浏览器
    # ================================================================
    def start(self, headless: Optional[bool] = None) -> None:
        """启动 Playwright 和 Chromium 浏览器

        Args:
            headless: 是否无头模式，None 则使用 settings.HEADLESS
        """
        if headless is None:
            headless = HEADLESS
        mode = "无头" if headless else "有头"
        logger.info(f"🚀 正在启动浏览器（{mode}模式）...")

        self._playwright = sync_playwright().start()

        # 启动参数
        launch_args = [
            "--disable-blink-features=AutomationControlled",  # 隐藏自动化特征
            "--no-sandbox",
            "--disable-dev-shm-usage",
        ]

        self._browser = self._playwright.chromium.launch(
            headless=headless,
            args=launch_args,
        )

        # 创建上下文（相当于一个独立的浏览器会话）
        self._context = self._browser.new_context(
            viewport={"width": VIEWPORT_WIDTH, "height": VIEWPORT_HEIGHT},
            user_agent=USER_AGENT,
            locale="zh-CN",
            timezone_id="Asia/Shanghai",
        )

        logger.info("✅ 浏览器启动完成")

    # ================================================================
    # 重启浏览器（切换有头/无头模式）
    # ================================================================
    def restart(self, headless: bool) -> None:
        """关闭当前浏览器并以指定模式重新启动"""
        logger.info(f"🔄 正在重启浏览器（{'无头' if headless else '有头'}模式）...")
        self.stop()
        self.start(headless=headless)

    # ================================================================
    # 加载 Cookie（从文件恢复到上下文）
    # ================================================================
    def load_cookies(self) -> bool:
        """
        从 COOKIE_FILE 加载 cookie 到当前上下文

        Returns:
            True 加载成功，False 文件不存在或解析失败
        """
        import json

        if not COOKIE_FILE.exists():
            logger.info("📄 Cookie 文件不存在，需要登录")
            return False

        try:
            with open(COOKIE_FILE, "r", encoding="utf-8") as f:
                cookies = json.load(f)

            if not cookies or not isinstance(cookies, list):
                logger.warning("⚠️ Cookie 文件格式异常，将重新登录")
                return False

            self._context.add_cookies(cookies)
            logger.info(f"✅ 已加载 {len(cookies)} 条 Cookie")
            return True
        except Exception as e:
            logger.error(f"❌ Cookie 加载失败: {e}")
            return False

    # ================================================================
    # 保存 Cookie
    # ================================================================
    def save_cookies(self) -> None:
        """保存当前上下文的 Cookie 到文件"""
        import json

        COOKIE_FILE.parent.mkdir(parents=True, exist_ok=True)
        cookies = self._context.cookies()
        with open(COOKIE_FILE, "w", encoding="utf-8") as f:
            json.dump(cookies, f, ensure_ascii=False, indent=2)
        logger.info(f"💾 Cookie 已保存至: {COOKIE_FILE}")

    # ================================================================
    # 新建页面（自动注入反检测脚本）
    # ================================================================
    def new_page(self) -> Page:
        """
        创建新页面，自动添加反检测脚本和默认超时

        Returns:
            Playwright Page 对象
        """
        page = self._context.new_page()
        page.set_default_timeout(PAGE_TIMEOUT)
        page.add_init_script(STEALTH_JS)
        logger.debug("📄 新页面已创建（已注入反检测脚本）")
        return page

    # ================================================================
    # 获取原始 context / browser（供高级操作使用）
    # ================================================================
    @property
    def context(self) -> BrowserContext:
        if self._context is None:
            raise RuntimeError("浏览器尚未启动，请先调用 start()")
        return self._context

    @property
    def browser(self) -> Browser:
        if self._browser is None:
            raise RuntimeError("浏览器尚未启动，请先调用 start()")
        return self._browser

    # ================================================================
    # 关闭浏览器
    # ================================================================
    def stop(self) -> None:
        """关闭浏览器并释放资源"""
        logger.info("🛑 正在关闭浏览器...")
        try:
            if self._context:
                self._context.close()
            if self._browser:
                self._browser.close()
            if self._playwright:
                self._playwright.stop()
            logger.info("✅ 浏览器已关闭")
        except Exception as e:
            logger.error(f"⚠️ 浏览器关闭异常: {e}")