"""
微博爬虫 - 全局配置常量
所有模块通过 from config.settings import ... 引用
"""

import os
from pathlib import Path

# ============================================================
# 项目根目录
# ============================================================
BASE_DIR = Path(__file__).resolve().parent.parent  # weibo-crawler/

# ============================================================
# 输出目录（运行时自动创建）
# ============================================================
OUTPUT_DIR = BASE_DIR / "output"
COOKIE_DIR = OUTPUT_DIR / "cookies"
DOWNLOAD_DIR = OUTPUT_DIR / "downloads"
RESULT_DIR = OUTPUT_DIR / "results"

# Cookie 文件路径
COOKIE_FILE = COOKIE_DIR / "weibo_cookies.json"

# ============================================================
# 日志目录
# ============================================================
LOG_DIR = BASE_DIR / "logs"

# ============================================================
# 配置文件路径
# ============================================================
USERS_CSV = BASE_DIR / "config" / "users.csv"

# ============================================================
# 微博 URL 模板
# ============================================================
WEIBO_HOMEPAGE = "https://weibo.com"                    # 微博首页（验证cookie）
WEIBO_LOGIN = "https://weibo.com/login.php"             # 登录页
WEIBO_USER_PAGE = "https://weibo.com/u/{user_id}"       # 用户主页
WEIBO_SEARCH = "https://s.weibo.com/weibo?q=@{username}&typeall=1&suball=1&timescope=custom:{start}:{end}&Refer=g"

# ============================================================
# 浏览器配置
# ============================================================
HEADLESS = False                        # 是否无头模式（调试时建议 False）
VIEWPORT_WIDTH = 1920                   # 视口宽度
VIEWPORT_HEIGHT = 1080                  # 视口高度
PAGE_TIMEOUT = 30_000                   # 页面加载超时（毫秒）
ELEMENT_TIMEOUT = 10_000                # 元素等待超时（毫秒）
LOGIN_TIMEOUT = 120_000                 # 登录等待超时（毫秒），给用户扫码留足时间
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/120.0.0.0 Safari/537.36"
)

# ============================================================
# 反检测脚本（隐藏 Playwright 特征）
# ============================================================
STEALTH_JS = """
// 隐藏 webdriver 属性
Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
// 覆盖 chrome 对象
window.chrome = { runtime: {} };
// 覆盖权限查询
const originalQuery = window.navigator.permissions.query;
window.navigator.permissions.query = (parameters) => (
    parameters.name === 'notifications' ?
        Promise.resolve({ state: Notification.permission }) :
        originalQuery(parameters)
);
"""

# ============================================================
# Cookie 验证配置
# ============================================================
COOKIE_CHECK_URL = WEIBO_HOMEPAGE          # 验证时访问的页面
COOKIE_CHECK_ELEMENT = "div[class*='UG_box']"  # 登录成功后才会出现的元素（输入框/头像区域）
COOKIE_REDIRECT_KEYWORD = "login.php"      # 被重定向到登录页的 URL 关键词

# ============================================================
# 爬虫配置
# ============================================================
SCROLL_WAIT = 2000                      # 每次滚动后等待时间（毫秒）
MAX_SCROLL_NO_NEW = 3                   # 连续无新内容滚动的最大次数，之后停止
MAX_WEIBO_COUNT = 0                     # 单用户最大爬取条数，0 = 不限制

# ============================================================
# 防封禁 - 随机延时（秒）
# ============================================================
DELAY_MIN = 3                           # 最小延时
DELAY_MAX = 8                           # 最大延时
DELAY_BEFORE_SCROLL = 1                 # 滚动前额外延时（秒）
DELAY_AFTER_CLICK = 2                   # 点击后额外延时（秒）

# ============================================================
# 媒体下载配置
# ============================================================
IMAGE_DIR_NAME = "images"               # 图片子目录名
LIVE_DIR_NAME = "live_photos"           # Live图子目录名
VIDEO_DIR_NAME = "videos"               # 视频子目录名
SCREENSHOT_DIR_NAME = "screenshots"     # 截图子目录名
DOWNLOAD_RETRY = 3                      # 下载失败重试次数
DOWNLOAD_CONCURRENCY = 3                # 并发下载数

# ============================================================
# 截图配置
# ============================================================
SCREENSHOT_FORMAT = "png"               # 截图格式
SCREENSHOT_QUALITY = 90                 # 截图质量（仅 jpeg 有效）
SCREENSHOT_FULL_PAGE = False            # 是否截整页（False = 仅截微博正文区域）

# 微博正文区域 XPath（按优先级尝试，取第一个匹配到的）
WEIBO_CONTENT_XPATHS = [
    "//article",                                    # 通常微博卡片用 <article>
    "//div[@class='WB_detail']",                   # 老版微博正文
    "//div[contains(@class,'detail_wbtext')]",     # 旧版正文容器
    "//div[@class='Feed_body_3R0rO']",             # 新版Feed正文
]

# ============================================================
# Excel 输出配置
# ============================================================
EXCEL_HEADERS = [
    "用户id",
    "用户名",
    "微博发布时间",
    "微博类型",
    "文案",
    "图片数量",
    "Live图数量",
    "视频数量",
    "图片下载数量",
    "Live图下载数量",
    "视频下载数量",
    "爬虫结果",
    "微博url",
]
EXCEL_FILENAME_PREFIX = "爬虫结果"                 # 文件名前缀
EXCEL_COL_WIDTHS = {                               # 列宽（字符数）
    "用户id": 18,
    "用户名": 12,
    "微博发布时间": 20,
    "微博类型": 10,
    "文案": 50,
    "图片数量": 8,
    "Live图数量": 8,
    "视频数量": 8,
    "图片下载数量": 10,
    "Live图下载数量": 10,
    "视频下载数量": 10,
    "爬虫结果": 12,
    "微博url": 40,
}

# ============================================================
# 日志配置
# ============================================================
LOG_LEVEL = "INFO"
LOG_FORMAT = (
    "<green>{time:YYYY-MM-DD HH:mm:ss}</green> | "
    "<level>{level: <8}</level> | "
    "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> | "
    "<level>{message}</level>"
)
LOG_ROTATION = "10 MB"                  # 日志轮转大小
LOG_RETENTION = "7 days"                # 日志保留天数