"""临时测试：browser 模块（诊断版）"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.browser import BrowserManager

print("=" * 50)
print("测试 1: 启动浏览器")
bm = BrowserManager()
bm.start()

print("\n测试 2: 新建页面")
page = bm.new_page()

# ---- 监听控制台错误 ----
page.on("console", lambda msg: print(f"  [浏览器控制台] [{msg.type}] {msg.text}"))
# ---- 监听请求失败 ----
page.on("requestfailed", lambda req: print(f"  [请求失败] {req.url[:80]} | {req.failure}"))

print("\n测试 3: 访问微博首页")
try:
    # 先用默认的 'load' 事件，超时 30 秒
    page.goto("https://weibo.com", wait_until="load", timeout=30_000)
    print("  ✅ load 事件触发")

    # 再额外等 5 秒渲染
    page.wait_for_timeout(5_000)
    print("  ✅ 额外等待 5 秒完成")
except Exception as e:
    print(f"  ⚠️ goto 异常: {e}")

print(f"  当前页面标题: {page.title()}")
print(f"  当前 URL: {page.url}")

# 打印页面 HTML 前 500 字符，诊断是否真的加载了内容
html = page.content()
print(f"  页面 HTML 长度: {len(html)} 字符")
print(f"  页面 HTML 前 300 字符:\n{html[:300]}\n")
print("\n测试 4: 截图保存")
output_dir = Path(__file__).resolve().parent.parent / "output" / "test_screenshots"
output_dir.mkdir(parents=True, exist_ok=True)
page.screenshot(path=str(output_dir / "browser_test.png"), full_page=False)
print(f"  截图已保存至: {output_dir / 'browser_test.png'}")

print("\n测试 5: 关闭浏览器")
bm.stop()

print("\n✅ browser 模块测试完成")
print("请把终端输出内容贴给我，方便定位白页原因")
