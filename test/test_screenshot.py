"""临时测试：screenshot 模块"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.browser import BrowserManager
from core.cookie_manager import CookieManager
from core.screenshot import ScreenshotCapture


def main():
    print("=" * 50)
    print("测试 ScreenshotCapture")
    print("=" * 50)

    # 1. 启动浏览器并登录
    bm = BrowserManager()
    bm.start()
    cm = CookieManager(bm)
    cm.ensure_valid_cookie()

    page = bm.new_page()
    user_id = "1685872053"  # 你 csv 中的用户

    # 2. 打开用户主页
    print(f"\n访问用户主页: https://weibo.com/u/{user_id}")
    page.goto(f"https://weibo.com/u/{user_id}", wait_until="domcontentloaded")
    page.wait_for_load_state("networkidle")
    page.wait_for_timeout(3_000)

    # 3. 定位第一条微博卡片
    first_article = page.locator("article").first
    if first_article.count() == 0:
        print("❌ 未找到任何微博卡片（article），请检查页面或Cookie状态")
        bm.stop()
        return

    # 取微博正文区域（在 article 内找正文 div）
    content_area = first_article.locator("xpath=.//div[contains(@class, '_body_')]")
    if content_area.count() == 0:
        # 回退：直接截 article
        print("⚠️ 未找到 _body_ 区域，将以 article 整体截图")
        content_area = first_article

    # 提取微博内容作为文件夹名素材
    content_text = first_article.inner_text()[:50] if first_article.count() > 0 else "无文案"

    # 4. 从 article 中尝试获取微博链接（用于提取 weibo_id）
    try:
        # 微博链接通常在 article 内的 a 标签中，href 包含 /数字/字母组合
        link_el = first_article.locator("a[href*='weibo.com']").first
        href = link_el.get_attribute("href") or ""
        weibo_id = href.rstrip("/").split("/")[-1] if "/" in href else "UnknownId"
    except Exception:
        weibo_id = "UnknownId"

    print(f"  微博链接: {href}")
    print(f"  微博 ID: {weibo_id}")
    print(f"  文案片段: {content_text[:50]}")

    # 5. 截图（传入已定位的 weibo_element，避免全页扫描）
    capturer = ScreenshotCapture()
    result_path = capturer.capture_weibo(
        page=page,
        user_id=user_id,
        weibo_time="20250525_150000",  # 测试用假时间
        weibo_id=weibo_id,
        content=content_text,
        weibo_element=content_area,    # 直接传入定位好的正文区域
    )

    if result_path:
        print(f"\n✅ 截图成功: {result_path}")
        print(f"   文件大小: {result_path.stat().st_size / 1024:.1f} KB")
    else:
        print("\n❌ 截图失败")

    bm.stop()
    print("\n✅ screenshot 模块测试完成")


if __name__ == "__main__":
    main()