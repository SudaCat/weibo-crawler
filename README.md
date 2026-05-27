# Weibo Crawler

基于 Playwright 的微博用户帖子爬虫，支持 API 拦截采集、多媒体下载、截图和 Excel 报告输出。

## 功能特性

- **API 拦截采集** — 拦截微博前端 AJAX 请求获取结构化 JSON 数据，比 DOM 解析更稳定、数据更丰富
- **DOM 降级解析** — API 拦截失效时自动回退到 DOM/XPath 解析
- **多媒体下载** — 自动下载图片、Live Photo（静态图 + 视频）、视频，支持并发下载和断点续传
- **截图留存** — 对每条微博内容区域截图保存
- **日期过滤** — 支持按时间范围筛选微博
- **反爬策略** — stealth JS 注入、类人随机延迟、反自动化浏览器参数
- **Cookie 持久化** — 扫码登录一次后保存 Cookie，后续运行自动复用
- **多用户支持** — CSV 配置用户列表，依次爬取
- **Excel 报告** — 输出带格式的 Excel 汇总文件
- **优雅中断** — 支持 Ctrl+C 中断并保存已爬取结果

## 项目结构

```
weibo-crawler/
├── main.py                     # 程序入口，编排完整爬取流程
├── config/
│   ├── settings.py             # 全局配置常量（路径、URL、浏览器、延时等）
│   └── users.csv               # 目标用户列表
├── core/
│   ├── browser.py              # BrowserManager — Playwright 浏览器生命周期管理
│   ├── cookie_manager.py       # CookieManager — 扫码登录与 Cookie 校验/持久化
│   ├── crawler.py              # WeiboCrawler — 核心爬取引擎（滚动、采集、处理）
│   ├── weibo_api.py            # WeiboAPIClient — AJAX 请求拦截与 JSON 解析
│   ├── media_downloader.py     # MediaDownloader — 图片/视频/Live Photo 下载
│   └── screenshot.py           # ScreenshotCapture — 微博内容区域截图
├── utils/
│   ├── anti_ban.py             # 随机/类人延时函数
│   ├── config_reader.py        # users.csv 读取与校验
│   ├── excel_writer.py         # 结果写入格式化 Excel
│   └── time_utils.py           # 日期解析与时间范围判断
├── test/
│   ├── test_anti_ban.py        # anti_ban 模块测试
│   └── test_time_utils.py      # time_utils 模块测试
├── output/                     # 运行时生成
│   ├── cookies/                # 持久化登录 Cookie
│   ├── downloads/              # 下载的媒体文件（按用户/帖子分目录）
│   └── results/                # 输出的 Excel 报告
└── logs/                       # 运行时日志
```

## 环境要求

- Python 3.8+
- Chromium 浏览器

## 安装

```bash
pip install playwright loguru openpyxl httpx Pillow
playwright install chromium
```

## 配置

### 目标用户

编辑 `config/users.csv`，格式为竖线分隔：

```
用户id|用户名|抓取开始时间|抓取停止时间|最后抓取时间
1685872053|李沛恩Pein_|2025-05-21 10:00:00||
1234567890|另一个用户|2025-05-01 00:00:00|2025-06-01 23:59:59|
```

- `用户id` — 微博数字 UID（必填）
- `用户名` — 显示名称（可选）
- `抓取开始时间` — 爬取起始时间（必填）
- `抓取停止时间` — 爬取结束时间（可选，留空默认为当前系统时间）
- `最后抓取时间` — 最近一次抓取时间（程序自动更新，无需手动填写）

### 爬取参数

所有可调参数集中在 [config/settings.py](config/settings.py)：

| 分类 | 主要参数 |
|------|---------|
| 浏览器 | `HEADLESS`, `VIEWPORT_WIDTH/HEIGHT`, `PAGE_TIMEOUT` |
| 反爬 | `SCROLL_WAIT`, `DELAY_MIN/MAX`, `STEALTH_JS` |
| 爬取 | `MAX_WEIBO_COUNT`（0=不限）, `MAX_SCROLL_NO_NEW` |
| 下载 | `DOWNLOAD_CONCURRENCY`, `DOWNLOAD_RETRY`, `IMAGE_SIZE_PREFERENCE` |
| 截图 | 格式/质量/全页开关 |

## 运行

```bash
python main.py
```

### 首次运行

1. 程序自动打开 Chromium 浏览器窗口
2. 导航到微博登录页，展示二维码
3. 使用微博 App 扫码登录
4. 终端按 Enter 确认登录成功
5. Cookie 自动保存，后续运行无需再次扫码

### 输出

| 路径 | 内容 |
|------|------|
| `output/results/crawler_results_*.xlsx` | Excel 汇总报告，含用户、时间、类型、正文、媒体数量、下载状态、链接 |
| `output/downloads/{uid}/{时间}_{微博id}_{正文}/` | 媒体文件与截图 |
| `output/cookies/weibo_cookies.json` | 持久化 Cookie |
| `logs/crawler_YYYY-MM-DD.log` | 按天轮转的运行日志 |
