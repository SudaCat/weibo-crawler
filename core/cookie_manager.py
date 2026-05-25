"""
Cookie 管理器
- 检测本地 Cookie 文件是否存在并有效
- 无效时弹出微博登录二维码供用户扫码
- 登录成功后持久化 Cookie 供后续使用
"""

import asyncio
import time
from pathlib import Path

from loguru import logger
from PIL import Image

from config.settings import (
    WEIBO_HOMEPAGE,
    WEIBO_LOGIN,
    COOKIE_FILE,
    COOKIE_CHECK_URL,
    COOKIE_CHECK_ELEMENT,
    COOKIE_REDIRECT_KEYWORD,
    LOGIN_TIMEOUT,
    ELEMENT_TIMEOUT,
)
from core.browser import BrowserManager


class CookieManager:
    """Cookie 生命周期管理"""

    def __init__(self, browser_manager: BrowserManager):
        self._bm = browser_manager

    # ================================================================
    # 1. 检查 Cookie 是否有效
    # ================================================================
    def is_cookie_valid(self) -> bool:
        """
        加载本地 Cookie 并验证是否仍然有效

        策略：
        1. 加载 cookie 文件到浏览器上下文
        2. 访问微博首页
        3. 检测是否被重定向到登录页（URL 含 login.php）
        4. 或者检测是否出现登录后才有的元素

        Returns:
            True = 有效，False = 无效/不存在
        """
        # 加载 cookie
        if not self._bm.load_cookies():
            return False

        # 访问首页验证
        page = self._bm.new_page()
        try:
            page.goto(COOKIE_CHECK_URL, wait_until="domcontentloaded", timeout=ELEMENT_TIMEOUT)
            page.wait_for_timeout(2_000)

            current_url = page.url

            # 检查是否被重定向到登录页
            if COOKIE_REDIRECT_KEYWORD in current_url:
                logger.info(f"🔒 Cookie 已失效（被重定向到登录页: {current_url}）")
                return False

# 检查是否有登录后才出现的元素（多个备选）
            check_selectors = [
                COOKIE_CHECK_ELEMENT,
                "article",                          # 微博卡片
                "div[class*='Frame_header']",       # 顶部导航栏
                "a[class*='gn_nav']",               # 导航链接
                "div[class*='m_wrap']",             # 首页 wrap
            ]
            logged_in = False
            for sel in check_selectors:
                try:
                    page.wait_for_selector(sel, timeout=3_000)
                    logger.info(f"✅ Cookie 有效（匹配: {sel}）")
                    logged_in = True
                    break
                except Exception:
                    continue

            if logged_in:
                return True
            else:
                logger.warning("⚠️ 未能找到任何登录标志元素，假定 Cookie 无效")
                return False
            
        except Exception as e:
            logger.error(f"❌ Cookie 验证过程异常: {e}")
            return False
        finally:
            if not page.is_closed():
                page.close()

    # ================================================================
    # 2. 二维码登录流程
    # ================================================================
    def login_with_qr(self) -> bool:
        """
        打开微博登录页，截取二维码，让用户扫码登录

        Returns:
            True = 登录成功，False = 超时或其他异常
        """
        page = self._bm.new_page()
        qr_image_path = COOKIE_FILE.parent / "weibo_qrcode.png"

        try:
            # 打开登录页
            logger.info("🔑 正在打开微博登录页...")
            page.goto(WEIBO_LOGIN, wait_until="domcontentloaded")
            page.wait_for_timeout(3_000)

            # 等待二维码图片加载
            # 微博二维码可能在 iframe 中，也可能在 img 标签中
            # 常见选择器：
            qr_selectors = [
                ".qrcode_img",      # PC 登录页二维码
                ".WB_qrcode_img",
                "img[src*='qrcode']",
                "img[src*='QR']",
                ".qrcode img",
                "img[alt*='二维码']",
            ]

            logger.info("⏳ 等待二维码加载...")
            qr_element = None
            for selector in qr_selectors:
                try:
                    qr_element = page.wait_for_selector(selector, timeout=10_000)
                    if qr_element:
                        logger.info(f"✅ 找到二维码元素: {selector}")
                        break
                except Exception:
                    continue

            if qr_element is None:
                # 最后兜底：截整个页面，用户自己扫
                logger.warning("⚠️ 未能精确定位二维码元素，将对整个登录区域截图")
                page.screenshot(path=str(qr_image_path), full_page=False)
            else:
                # 截取二维码元素截图
                qr_element.screenshot(path=str(qr_image_path))

            logger.info(f"📱 二维码已保存至: {qr_image_path}")

            # 打开二维码图片（用系统默认图片查看器）
            try:
                img = Image.open(qr_image_path)
                img.show()  # 自动调用系统默认查看器
            except Exception as e:
                logger.warning(f"⚠️ 无法自动打开图片查看器: {e}")

            # 等待用户扫码确认
            print("\n" + "=" * 60)
            print("📱 请使用微博 App 扫描弹出的二维码")
            print(f"   如果图片未自动打开，请手动查看: {qr_image_path}")
            print("   扫码成功后，在此终端按 Enter 继续...")
            print("=" * 60)
            input()

            # 检测登录是否成功
            logger.info("🔍 正在验证登录状态...")
            start_time = time.time()
            while time.time() - start_time < LOGIN_TIMEOUT / 1000:
                try:
                    current_url = page.url
                    # 如果 URL 不再是登录页，说明登录成功
                    if COOKIE_REDIRECT_KEYWORD not in current_url and "login" not in current_url:
                        logger.info(f"✅ 登录成功！当前 URL: {current_url}")
                        return True

                    # 或者检测登录成功元素
                    page.wait_for_selector(COOKIE_CHECK_ELEMENT, timeout=3_000)
                    logger.info("✅ 检测到登录成功标志")
                    return True
                except Exception:
                    pass
                page.wait_for_timeout(2_000)

            logger.error("❌ 登录超时")
            return False

        except Exception as e:
            logger.error(f"❌ 登录流程异常: {e}")
            return False
        finally:
            if not page.is_closed():
                page.close()

    # ================================================================
    # 3. 统一入口：确保 Cookie 有效
    # ================================================================
    def ensure_valid_cookie(self) -> None:
        """
        确保浏览器上下文中已加载有效 Cookie
        无效则引导用户扫码登录，并自动保存
        """
        if self.is_cookie_valid():
            return

        logger.info("🔐 需要重新登录...")
        success = self.login_with_qr()

        if not success:
            raise RuntimeError("登录失败，无法继续爬虫")

        # 登录成功，持久化 Cookie
        self._bm.save_cookies()
        logger.info("🎉 登录成功，Cookie 已保存")