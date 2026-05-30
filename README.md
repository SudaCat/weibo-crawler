# Weibo Crawler

基于 Playwright 的微博用户爬虫。通过拦截微博 AJAX 接口获取结构化数据，支持多媒体下载和 Excel 报告输出。

## 核心逻辑

```
用户主页 → 滚动触发 API → 拦截 JSON 响应 → 解析 WeiboPost → 下载媒体 → 写入 Excel
```

1. **浏览器启动** — Playwright 启动 Chromium，注入 stealth JS 隐藏自动化特征
2. **Cookie 管理** — 加载本地 Cookie 并验证有效性；失效时自动切有头模式弹出二维码，扫码后持久化
3. **API 拦截** — 每个用户独立页面，导航到其主页后，通过 `page.on("response")` 拦截微博列表 AJAX 请求（匹配 `/ajax/statuses/`），捕获结构化 JSON
4. **滚动采集** — 逐步滚动页面触发更多 API 请求，每次滚动后取走拦截到的数据，直到连续多次无新数据或时间超出范围
5. **逐条处理** — 每条微博：过滤置顶/评论/赞过 → 判断时间范围 → 下载媒体（可选）→ 回调写入 Excel
6. **断点续爬** — 已爬过的微博 ID 记录在 `state/excluded_weibo_ids.txt`，下次运行自动跳过

## 项目结构

```
weibo-crawler/
├── main.py                     # 程序入口，编排完整爬取流程
├── config/
│   ├── settings.example.py     # 配置模板（首次运行自动复制为 settings.py）
│   └── settings.py             # 全局配置（路径、浏览器、反爬、下载等）
├── core/
│   ├── browser.py              # BrowserManager — 浏览器生命周期管理
│   ├── cookie_manager.py       # CookieManager — 扫码登录与 Cookie 校验/持久化
│   ├── crawler.py              # WeiboCrawler — 滚动 + API 拦截 + 逐条处理
│   ├── weibo_api.py            # WeiboAPIClient — AJAX 拦截与 JSON → WeiboPost 解析
│   └── media_downloader.py     # MediaDownloader — 图片/视频/Live Photo 并发下载
├── utils/
│   ├── anti_ban.py             # 随机/类人延时
│   ├── config_reader.py        # users.csv 读取、校验、自动迁移、时间回写
│   ├── excel_writer.py         # 结果写入格式化 Excel
│   └── time_utils.py           # 日期解析与时间范围判断
├── input/
│   └── users.csv               # 待爬取用户列表
├── output/
│   ├── downloads/              # 下载的媒体文件
│   └── results/                # 输出 Excel 报告
├── state/
│   ├── weibo_cookies.json      # 持久化登录 Cookie
│   └── excluded_weibo_ids.txt  # 已爬微博 ID（断点续爬）
└── logs/                       # 按天轮转的运行日志
```

## 环境要求

- Python 3.8+
- Chromium 浏览器

## 安装

```bash
pip install playwright loguru openpyxl httpx Pillow tqdm
playwright install chromium
```

## 配置

### 首次运行

首次运行时程序会自动从 `config/settings.example.py` 复制 `config/settings.py`，无需手动创建。

### 目标用户 — input/users.csv

编辑 `input/users.csv`，逗号分隔（CSV）。首次运行如文件不存在，程序自动创建含表头的空模板。

```
用户id,用户名,抓取开始时间,抓取停止时间,最后抓取时间,最后运行时间,是否生效,是否下载媒体文件
1234567890,示例用户A,2024-01-01 00:00:00,2025-12-31 00:00:00,,,是,是
9876543210,示例用户B,2025-03-01 10:00:00,,,,是,否
```

| 字段 | 必填 | 说明 |
|------|------|------|
| `用户id` | 是 | 微博数字 UID（在用户主页 URL 中可获取，如 `weibo.com/u/1234567890`） |
| `用户名` | 否 | 仅用于文件夹命名和日志显示，留空不影响运行 |
| `抓取开始时间` | 是 | 爬取起始时间，格式 `YYYY-MM-DD HH:MM:SS` |
| `抓取停止时间` | 否 | 爬取结束时间，留空默认为当前系统时间 |
| `最后抓取时间` | — | **程序自动维护**，记录最近一次抓取到的最新微博发布时间，无需手动填写 |
| `最后运行时间` | — | **程序自动维护**，记录最近一次运行的系统时间，无需手动填写 |
| `是否生效` | 否 | `是`/`否`，默认 `是`。设为 `否` 则本次跳过该用户 |
| `是否下载媒体文件` | 否 | `是`/`否`，默认 `是`。设为 `否` 则仅爬取文字内容，不下载图片/视频，也不会创建下载目录 |

> 旧版 CSV（缺少列）会自动迁移：缺失列补默认值 `是`。

### 爬取参数 — config/settings.py

所有可调参数集中在此文件，按功能分组：

**浏览器**

| 参数 | 默认值 | 说明 |
|------|--------|------|
| `HEADLESS` | `True` | 无头模式。设为 `False` 可观察浏览器操作（调试用）。登录时自动临时切回有头模式 |
| `VIEWPORT_WIDTH` | `1920` | 浏览器视口宽度 |
| `VIEWPORT_HEIGHT` | `1080` | 浏览器视口高度 |
| `PAGE_TIMEOUT` | `30000` | 页面加载超时（毫秒） |
| `USER_AGENT` | Chrome 120 | 浏览器 UA 标识 |

**爬取**

| 参数 | 默认值 | 说明 |
|------|--------|------|
| `SCROLL_WAIT` | `2000` | 每次滚动后等待时间（毫秒），过短可能导致 API 来不及响应 |
| `MAX_WEIBO_COUNT` | `0` | 单用户最大爬取条数，`0` 不限制 |
| `POST_RETRY_MAX` | `3` | 单条微博处理（含下载）最大重试次数 |

**反封禁**

| 参数 | 默认值 | 说明 |
|------|--------|------|
| `DELAY_MIN` | `3` | 处理每条微博的最小随机延时（秒） |
| `DELAY_MAX` | `8` | 处理每条微博的最大随机延时（秒） |
| `DELAY_BEFORE_SCROLL` | `1` | 滚动前额外延时（秒） |
| `DELAY_AFTER_CLICK` | `2` | 点击后额外延时（秒） |

**媒体下载**

| 参数 | 默认值 | 说明 |
|------|--------|------|
| `DOWNLOAD_RETRY` | `3` | 单个文件下载失败重试次数 |
| `DOWNLOAD_CONCURRENCY` | `3` | 并发下载线程数 |
| `IMAGE_SIZE_PREFERENCE` | `["largest", "original", "mw2000", "large"]` | 图片尺寸偏好，从大到小依次尝试。可用：`largest`, `original`, `mw2000`, `large`, `bmiddle`, `thumbnail` |

**API 数据源**

| 参数 | 默认值 | 说明 |
|------|--------|------|
| `USE_API_DATA_SOURCE` | `True` | 必须开启。通过拦截 AJAX 接口获取结构化数据 |

**Excel 输出**

| 参数 | 默认值 | 说明 |
|------|--------|------|
| `EXCEL_HEADERS` | 13 列 | 输出的 Excel 列定义（用户id、用户名、微博发布时间、微博类型、文案、爬虫结果、微博url、图片数量、Live图数量、视频数量、图片下载数量、Live图下载数量、视频下载数量） |
| `EXCEL_FILENAME_PREFIX` | `爬虫结果` | 输出文件名前缀，完整名称格式为 `爬虫结果_YYYY-MM-DD_HH-MM-SS.xlsx` |
| `EXCEL_COL_WIDTHS` | — | 各列宽度配置 |

**日志**

| 参数 | 默认值 | 说明 |
|------|--------|------|
| `LOG_LEVEL` | `INFO` | 日志级别 |
| `LOG_ROTATION` | `10 MB` | 日志轮转大小 |
| `LOG_RETENTION` | `7 days` | 日志保留天数 |

## 运行

```bash
python main.py
```

### 首次运行

1. 程序自动创建 `config/settings.py` 和 `input/users.csv`（如不存在）
2. 编辑 `input/users.csv` 填入目标用户
3. 重新运行 `python main.py`，程序启动浏览器
4. 检测到无有效 Cookie → 自动切有头模式，打开微博登录页展示二维码
5. 使用**微博 App** 扫码登录（不是微信）
6. 终端按 Enter 确认
7. Cookie 自动保存，切回无头模式，开始爬取

### 后续运行

Cookie 有效时全程静默运行。若 Cookie 过期，程序会自动弹出登录窗口。

### 中断与续爬

- 按 `Ctrl+C` 可随时中断，已爬取结果会保存到 Excel
- 重新运行 `python main.py` 即可继续：已爬过的微博 ID 会从 `state/excluded_weibo_ids.txt` 加载并自动跳过
- 用户的 `最后抓取时间` 也会自动更新，下次可调整 `抓取开始时间` 为新值以只爬增量

## 输出

### Excel 报告 — `output/results/爬虫结果_YYYY-MM-DD_HH-MM-SS.xlsx`

每条微博一行，包含以下列：

| 列名 | 说明 |
|------|------|
| 用户id | 微博数字 UID |
| 用户名 | 用户显示名称 |
| 微博发布时间 | 格式 `YYYY-MM-DD HH:MM:SS` |
| 微博类型 | `原创` 或 `转发` |
| 文案 | 微博正文（纯文本） |
| 爬虫结果 | `成功` 或 `失败: 错误信息` |
| 微博url | 微博详情页链接 |
| 图片数量 | 该微博包含的普通图片数 |
| Live图数量 | 该微博包含的 Live Photo 数 |
| 视频数量 | 该微博包含的视频数 |
| 图片下载数量 | 实际下载成功的图片数 |
| Live图下载数量 | 实际下载成功的 Live 图数 |
| 视频下载数量 | 实际下载成功的视频数 |

### 媒体文件 — `output/downloads/`

仅在微博有媒体文件且开启下载时才创建目录，无媒体则不创建空目录。

```
output/downloads/
└── {用户id}_{用户名}/                  # 用户级目录
    └── {发布时间}_{微博id}_{文案前50字}/   # 单条微博目录
        ├── {同上前缀}_001.jpg
        ├── {同上前缀}_002.jpg
        ├── {同上前缀}_003.mp4
        └── ...
```

Live Photo 的静态图和动态视频同序号不同后缀，便于对应检索。

### 状态文件 — `state/`

| 文件 | 说明 |
|------|------|
| `weibo_cookies.json` | 持久化登录 Cookie，下次运行自动加载 |
| `excluded_weibo_ids.txt` | 已爬微博 ID 列表（每行一个），支持 `#` 注释 |

### 日志 — `logs/crawler_YYYY-MM-DD.log`

按天轮转，同时输出到控制台。日志级别、轮转大小、保留天数均可在 `config/settings.py` 中调整。

## 常见问题

**Q: 提示"API 数据源未启用"？**
`USE_API_DATA_SOURCE` 必须为 `True`，这是唯一的数据获取方式。

**Q: 扫码后一直不登录？**
确认使用的是**微博 App** 扫码，而非微信。如果微博账号存在安全风险，登录可能被拦截，建议换号。

**Q: 爬取速度慢？**
可以适当降低 `DELAY_MIN`/`DELAY_MAX`，但过快可能触发风控。建议不低于 2 秒。

**Q: Cookie 频繁失效？**
微博 Cookie 有效期通常较短。检查 `SCROLL_WAIT` 是否过短导致请求频率过高。

**Q: 如何只爬取增量？**
利用 `最后抓取时间`：上次运行后该字段已自动更新，将 `抓取开始时间` 设为该值即可只爬新微博。
