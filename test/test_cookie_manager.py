"""临时测试：cookie_manager 模块"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.browser import BrowserManager
from core.cookie_manager import CookieManager

print("=" * 50)
print("测试 Cookie Manager")
print("=" * 50)

# 1. 启动浏览器
bm = BrowserManager()
bm.start()

# 2. 初始化 Cookie 管理器
cm = CookieManager(bm)

# 3. 检查 cookie 并自动处理登录
try:
    cm.ensure_valid_cookie()
    print("\n✅ Cookie 有效，可以开始爬取")
except RuntimeError as e:
    print(f"\n❌ 登录失败: {e}")

# 4. 可选：验证一下登录态
print("\n验证：再次访问首页...")
page = bm.new_page()
page.goto("https://weibo.com", wait_until="domcontentloaded")
page.wait_for_timeout(3_000)
print(f"   当前 URL: {page.url}")
page.close()

# 5. 关闭浏览器
bm.stop()
print("\n✅ cookie_manager 测试完成")