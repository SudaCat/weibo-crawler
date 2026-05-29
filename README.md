# Weibo Crawler

基于 Playwright 的微博用户帖子爬虫，通过搜索接口按时间范围分页获取微博数据，支持多媒体下载和 Excel 报告输出。

## 功能特性

- **搜索接口采集** — 通过微博搜索接口 (`searchProfile`) 按时间范围分页获取结构化 JSON 数据，比 DOM 解析更稳定、数据更丰富
- **自然月拆分** — 自动将大时间范围按自然月拆分，避免单次查询数据量过大
- **接口重试** — 搜索接口失败时自动重试，可配置重试次数
- **多媒体下载** — 自动下载图片、Live Photo（静态图 + 视频）、视频，支持并发下载和断点续传
- **日期过滤** — 支持按时间范围筛选微博，自动跳过置顶和评论/赞过等非本人发布内容
- **反爬策略** — stealth JS 注入、类人随机延迟、反自动化浏览器参数
- **Cookie 持久化** — 扫码登录一次后保存 Cookie，后续运行自动复用
- **多用户支持** — CSV 配置用户列表，支持控制是否生效、是否下载媒体，依次爬取
- **逐条写入 Excel** — 每条微博处理完立即写入 Excel，中断时已抓取结果不丢失
- **优雅中断** — 支持 Ctrl+C 中断并保存已爬取结果

## 项目结构

```
weibo-crawler/
├── main.py                     # 程序入口，编排完整爬取流程
├── config/
│   ├── settings.example.py     # 配置模板（首次运行自动复制为 settings.py）
│   └── settings.py             # 全局配置常量（路径、URL、浏览器、延时等）
├── core/
│   ├── browser.py              # BrowserManager — Playwright 浏览器生命周期管理
│   ├── cookie_manager.py       # CookieManager — 扫码登录与 Cookie 校验/持久化
│   ├── crawler.py              # WeiboCrawler — 核心爬取引擎（搜索分页、解析、处理）
│   ├── weibo_api.py            # WeiboAPIClient — 搜索接口调用与 JSON 解析
│   └── media_downloader.py     # MediaDownloader — 图片/视频/Live Photo 下载
├── utils/
│   ├── anti_ban.py             # 随机/类人延时函数
│   ├── config_reader.py        # users.csv 读取、校验与自动迁移
│   ├── excel_writer.py         # 结果写入格式化 Excel
│   └── time_utils.py           # 日期解析与时间范围判断
├── input/                      # 用户输入
│   └── users.csv               # 目标用户列表
├── output/                     # 运行时生成
│   ├── downloads/              # 下载的媒体文件（按用户/帖子分目录）
│   └── results/                # 输出的 Excel 报告
├── state/                      # 运行时状态
│   └── cookies/                # 持久化登录 Cookie
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

### 首次运行

首次运行时，程序会自动从 `config/settings.example.py` 复制一份 `config/settings.py`，无需手动创建配置。

### 目标用户

编辑 `input/users.csv`，格式为逗号分隔（CSV）：

```
用户id,用户名,抓取开始时间,抓取停止时间,最后抓取时间,最后运行时间,是否生效,是否下载媒体文件
7927065948,江衡oc,2024-06-01 00:00:00,2026-01-01 00:00:00,,,是,是
1685872053,李沛恩Pein_,2025-05-21 10:00:00,,,2026-05-28 10:00:00,是,否
```

| 字段 | 说明 |
|------|------|
| `用户id` | 微博数字 UID（必填） |
| `用户名` | 显示名称（可选，留空不影响程序运行） |
| `抓取开始时间` | 爬取起始时间，格式 `YYYY-MM-DD HH:MM:SS`（必填） |
| `抓取停止时间` | 爬取结束时间（可选，留空默认为当前系统时间） |
| `最后抓取时间` | 最近一次抓取到的微博发布时间（**程序自动更新**，无需手动填写） |
| `最后运行时间` | 最近一次程序运行的系统时间（**程序自动更新**，无需手动填写） |
| `是否生效` | `是` 或 `否`，控制本次是否爬取该用户 |
| `是否下载媒体文件` | `是` 或 `否`，控制是否下载图片/视频（`否` 则仅爬取文字内容） |

> CSV 文件会自动迁移旧格式——如果缺少列，程序会自动补充默认值 `是`。

### 爬取参数

所有可调参数集中在 [config/settings.py](config/settings.py)：

| 分类 | 主要参数 |
|------|---------|
| 浏览器 | `HEADLESS`, `VIEWPORT_WIDTH/HEIGHT`, `PAGE_TIMEOUT`, `USER_AGENT` |
| 反爬 | `STEALTH_JS`, `DELAY_MIN/MAX`, `DELAY_BEFORE_SCROLL`, `DELAY_AFTER_CLICK` |
| 爬取 | `MAX_WEIBO_COUNT`（0=不限）, `SCROLL_WAIT`, `SEARCH_RETRY_MAX`（搜索接口重试次数） |
| 下载 | `DOWNLOAD_CONCURRENCY`, `DOWNLOAD_RETRY`, `IMAGE_SIZE_PREFERENCE` |
| API | `USE_API_DATA_SOURCE`, `API_FALLBACK_TO_DOM` |

## 运行

```bash
python main.py
```

### 首次运行

1. 程序自动打开 Chromium 浏览器窗口（即使配置了 `HEADLESS=True`，登录时会自动切回有头模式）
2. 导航到微博登录页，展示二维码
3. 使用微博 App 扫码登录
4. Cookie 自动保存，后续运行无需再次扫码
5. 登录成功后自动切换回无头模式继续爬取

### 爬取流程

1. 读取 `input/users.csv`，校验用户配置
2. 启动浏览器，检查 Cookie 有效性
3. 对每个生效用户，导航到其主页建立浏览器上下文
4. 通过 `page.evaluate` 执行 `fetch()` 调用微博搜索接口，按自然月拆分时间范围
5. 解析返回的 JSON，过滤置顶/评论/赞过等非本人发布内容
6. 下载媒体文件（根据 `是否下载媒体文件` 配置），逐条写入 Excel
7. 爬取完成后自动更新用户的 `最后抓取时间` 和 `最后运行时间`

### 输出

| 路径 | 内容 |
|------|------|
| `output/results/爬虫结果_*.xlsx` | Excel 汇总报告，含用户、时间、类型、正文、媒体数量、下载状态、链接 |
| `output/downloads/{用户id}_{用户名}/{时间}_{微博id}_{正文}/` | 媒体文件（按用户分目录） |
| `state/cookies/weibo_cookies.json` | 持久化 Cookie |
| `logs/crawler_YYYY-MM-DD.log` | 按天轮转的运行日志 |
