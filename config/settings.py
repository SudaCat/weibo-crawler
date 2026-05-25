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
WEIBO_LOGIN = (
    "https://passport.weibo.com/sso/signin"
    "?entry=miniblog&source=miniblog&disp=popup"
    "&url=https%3A%2F%2Fweibo.com%2Fnewlogin%3Ftabtype%3Dweibo%26gid%3D102803%26openLoginLayer%3D0%26url%3D"
    "&from=weibopro"
)                                                       # 登录页（新版 passport）
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
COOKIE_CHECK_ELEMENT = "article"           # 修改后（推荐使用 article，已登录首页一定有微博卡片）
COOKIE_REDIRECT_KEYWORD = "passport.weibo.com"  # 被重定向到登录页的 URL 关键词（新版 passport）

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
SCREENSHOT_DIR_NAME = "screenshots"     # 截图子目录名
DOWNLOAD_RETRY = 3                      # 下载失败重试次数
DOWNLOAD_CONCURRENCY = 3                # 并发下载数

# 图片尺寸偏好（从大到小排列，优先选择靠前的可用尺寸）
# 可用选项：largest, original, mw2000, large, bmiddle, thumbnail
IMAGE_SIZE_PREFERENCE = ["largest", "original", "mw2000", "large"]

# ============================================================
# API 数据源配置
# ============================================================
USE_API_DATA_SOURCE = True              # 优先使用 API 拦截数据（推荐开启）
API_FALLBACK_TO_DOM = True              # API 获取失败时回退到 DOM 解析

# ============================================================
# 截图配置
# ============================================================
SCREENSHOT_FORMAT = "png"               # 截图格式
SCREENSHOT_QUALITY = 90                 # 截图质量（仅 jpeg 有效）
SCREENSHOT_FULL_PAGE = False            # 是否截整页（False = 仅截微博正文区域）

# 微博正文区域 XPath（用于截图定位）
WEIBO_CONTENT_XPATHS = [
    "//article",                                     # 微博卡片
    "//div[contains(@class, '_body_')]",             # 新版正文整体区域
    "//div[@class='WB_detail']",                     # 老版微博正文
    "//div[contains(@class,'detail_wbtext')]",       # 旧版正文容器
    "//div[@class='Feed_body_3R0rO']",               # 新版Feed正文
]

# 微博文案文本区域 XPath（用于提取纯文案文字）
WEIBO_TEXT_XPATHS = [
    "//div[starts-with(@class, '_wbtext')]",         # 新版微博文案区域
    "//div[contains(@class, 'WB_text')]",            # 老版微博文案
    "//div[contains(@class, 'detail_wbtext')]",      # 旧版
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