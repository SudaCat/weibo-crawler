"""临时测试：media_downloader 模块（新路径格式）"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.browser import BrowserManager
from core.cookie_manager import CookieManager
from core.media_downloader import MediaDownloader


def main():
    print("=" * 50)
    print("测试 Media Downloader（新路径格式）")
    print("=" * 50)

    # 1. 测试文件名净化
    print("\n测试 1: sanitize_text 文件名清理")
    test_cases = [
        ("今天天气真好，出去玩了！", "正常文案"),
        ('含非法字符 \\/:*?"<>| 测试', "非法字符"),
        ("a" * 60 + "超长", "超长截断"),
        ("", "空字符串"),
    ]
    for text, desc in test_cases:
        result = MediaDownloader.sanitize_text(text)
        print(f"  [{desc}] '{text[:30]}...' → '{result}' (长度: {len(result)})")

    # 2. 启动浏览器并登录
    print("\n" + "=" * 50)
    print("测试 2: 启动浏览器并登录")
    bm = BrowserManager()
    bm.start()
    cm = CookieManager(bm)
    cm.ensure_valid_cookie()
    cookies = bm.context.cookies()

    # 3. 打开用户主页提取图片
    page = bm.new_page()
    user_id = "1685872053"
    page.goto(f"https://weibo.com/u/{user_id}", wait_until="domcontentloaded")
    page.wait_for_timeout(5_000)

    # 尝试只在微博正文卡片中提取图片
    img_elements = page.query_selector_all("article div[class*='Feed_body'] img[src*='sinaimg']")
    test_urls = []
    for el in img_elements[:5]:
        src = el.get_attribute("src")
        if src and "http" in src:
            src = src.replace("thumb150", "large").replace("orj360", "large")
            test_urls.append(src)

    if not test_urls:
        print("\n⚠️ 未在正文中找到图片，尝试全局提取...")
        img_elements = page.query_selector_all("img[src*='sinaimg']")
        for el in img_elements[:3]:
            src = el.get_attribute("src")
            if src and "http" in src:
                src = src.replace("thumb150", "large").replace("orj360", "large")
                test_urls.append(src)

    if not test_urls:
        print("⚠️ 仍未找到图片，跳过下载测试")
        bm.stop()
        return

    print(f"\n找到 {len(test_urls)} 张图片，开始下载...")

    # 4. 使用新接口下载
    downloader = MediaDownloader(user_id=user_id, cookies=cookies)
    result = downloader.download_weibo_media(
        weibo_id="TestId001",
        weibo_time="20250525_140000",
        content='测试微博_含特殊字符\\/:*?"<>|_的文案',
        image_urls=test_urls,
        live_photo_pairs=[],   # 暂不测 Live 图，crawler 阶段再测
        video_urls=[],
    )
    print(f"\n✅ 下载统计: {result}")

    # 5. 查看输出目录结构
    base = Path(f"output/downloads/{user_id}")
    print(f"\n📁 输出目录结构 ({base}):")
    for item in sorted(base.rglob("*"), key=lambda x: (x.is_dir(), str(x))):
        if item.is_file():
            size_kb = item.stat().st_size / 1024
            rel = item.relative_to(base)
            print(f"  📄 {rel} ({size_kb:.1f} KB)")
        else:
            rel = item.relative_to(base)
            print(f"  📁 {rel}/")

    bm.stop()
    print("\n✅ media_downloader 测试完成")


if __name__ == "__main__":
    main()