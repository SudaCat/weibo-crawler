"""临时测试：crawler 模块"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.browser import BrowserManager
from core.cookie_manager import CookieManager
from core.crawler import WeiboCrawler


def main():
    print("=" * 50)
    print("测试 WeiboCrawler")
    print("=" * 50)

    # 1. 启动浏览器并登录
    bm = BrowserManager()
    bm.start()
    cm = CookieManager(bm)
    cm.ensure_valid_cookie()

    page = bm.new_page()
    cookies = bm.context.cookies()

    # 2. 读取用户配置（取第一个测试）
    from utils.config_reader import read_users
    users = read_users()
    if not users:
        print("❌ 无用户配置")
        bm.stop()
        return

    user = users[0]
    print(f"\n测试用户: {user['username']} ({user['user_id']})")
    print(f"时间范围: {user['start_date']} ~ {user['end_date'] or '最新'}")

    # 3. 执行爬虫（测试时限制 3 条）
    # 临时修改最大条数
    from config import settings
    original_max = settings.MAX_WEIBO_COUNT
    settings.MAX_WEIBO_COUNT = 3  # 限制 3 条用于测试

    crawler = WeiboCrawler(
        page=page,
        user_id=user["user_id"],
        username=user["username"],
        start_date=user["start_date"],
        end_date=user["end_date"],
        cookies=cookies,
    )

    results = crawler.crawl()

    # 恢复配置
    settings.MAX_WEIBO_COUNT = original_max

    # 4. 输出结果
    print(f"\n{'=' * 50}")
    print(f"爬取结果: {len(results)} 条微博")
    print(f"{'=' * 50}")
    for i, r in enumerate(results, 1):
        print(f"\n[{i}] {r['微博发布时间']} | {r['微博类型']}")
        print(f"    文案: {r['文案'][:60]}...")
        print(f"    图片: {r['图片下载数量']} | Live: {r['Live图下载数量']} | 视频: {r['视频下载数量']}")
        print(f"    URL: {r['微博url']}")
        print(f"    结果: {r['爬虫结果']}")

    bm.stop()
    print(f"\n✅ crawler 测试完成（共 {len(results)} 条）")


if __name__ == "__main__":
    main()