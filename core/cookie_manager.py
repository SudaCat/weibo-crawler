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
    # ... 方法签名和 page 创建不变 ...

    def login_with_qr(self) -> bool:
        page = self._bm.new_page()

        try:
            # 打开登录页
            logger.info("🔑 正在打开微博登录页...")
            page.goto(WEIBO_LOGIN, wait_until="domcontentloaded")
            page.wait_for_timeout(3_000)

            # ── 直接提示用户在浏览器中扫码 ──
            print("\n" + "=" * 60)
            print("📱 请在浏览器中扫描微博登录二维码")
            print("   扫码成功并登录后，在此终端按 Enter 继续...")
            print("=" * 60)
            input()

            # ── 验证登录状态（原逻辑不变）──
            logger.info("🔍 正在验证登录状态...")
            start_time = time.time()
            while time.time() - start_time < LOGIN_TIMEOUT / 1000:
                try:
                    current_url = page.url

                    if "passport" in current_url or "login" in current_url.lower():
                        page.wait_for_timeout(2_000)
                        continue

                    try:
                        page.goto(COOKIE_CHECK_URL, wait_until="domcontentloaded", timeout=15_000)
                        page.wait_for_timeout(2_000)

                        check_selectors = [
                            COOKIE_CHECK_ELEMENT,
                            "article",
                            "div[class*='Frame_header']",
                            "a[class*='gn_nav']",
                            "div[class*='m_wrap']",
                        ]
                        for sel in check_selectors:
                            try:
                                page.wait_for_selector(sel, timeout=3_000)
                                logger.info(f"✅ 登录成功！（匹配: {sel}）")
                                return True
                            except Exception:
                                continue

                        logger.warning("⚠️ 已跳离登录页但未检测到登录标志，假定成功")
                        return True

                    except Exception:
                        logger.warning(f"⚠️ 验证过程异常，但 URL 已变化: {current_url}")
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