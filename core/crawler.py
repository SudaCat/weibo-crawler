"""
核心爬虫模块
通过页面滚动触发微博时间线 AJAX 接口，由 WeiboAPIClient 拦截响应，
解析为结构化微博数据后逐条处理（下载媒体、写入 Excel）。
滚动方式相比搜索接口能抓全定时微博（搜索接口不返回定时微博）。
"""

import time as time_module
from datetime import datetime
from typing import Callable, Optional

from loguru import logger
from playwright.sync_api import Page

from config.settings import (
    WEIBO_USER_PAGE,
    SCROLL_WAIT,
    MAX_WEIBO_COUNT,
    POST_RETRY_MAX,
    USE_API_DATA_SOURCE,
)
from core.weibo_api import WeiboAPIClient, WeiboPost
from core.media_downloader import MediaDownloader
from utils.anti_ban import random_delay, human_like_delay
from utils.time_utils import is_before_start, is_in_range


class WeiboCrawler:
    """微博用户爬虫（API 优先）"""

    def __init__(
        self,
        page: Page,
        user_id: str,
        username: str,
        start_date: str,
        end_date: Optional[str] = None,
        cookies: Optional[list[dict]] = None,
        download_media: bool = True,
        on_post_processed: Optional[Callable[[dict], None]] = None,
        excluded_ids: Optional[set[str]] = None,
    ):
        self.page = page
        self.user_id = user_id
        self.username = username
        self.start_date = start_date
        self.end_date = end_date
        self.download_media = download_media

        # 每处理完一条微博后的回调（用于更新最后抓取时间等）
        self.on_post_processed = on_post_processed

        # API 客户端（在 crawl 时初始化，需要页面已导航到目标）
        self.api_client: Optional[WeiboAPIClient] = None

        # 下载
        self.downloader = MediaDownloader(user_id=user_id, username=username, cookies=cookies)

        self.results: list[dict] = []
        # 已排除 ID（历史爬过的 + 本次运行已处理的）
        self._excluded_ids = excluded_ids or set()
        self._processed_ids: set[str] = self._excluded_ids.copy()
        self._skipped_existing = 0  # 命中排除列表的跳过数
        self._post_retry_max = POST_RETRY_MAX

    # ================================================================
    # 主入口
    # ================================================================
    def crawl(self) -> list[dict]:
        logger.info(f"🔍 开始爬取用户: {self.username} ({self.user_id})")
        logger.info(f"   时间范围: {self.start_date} ~ {self.end_date or '最新'}")

        # 初始化 API 拦截（必须在 goto 之前！）
        if USE_API_DATA_SOURCE:
            self.api_client = WeiboAPIClient(self.page)
            logger.info("📡 已启用 API 拦截模式")
        else:
            self.api_client = None

        if not self.api_client:
            raise RuntimeError("API 数据源未启用，无法爬取")

        # 导航到用户主页，建立浏览器上下文
        homepage_url = WEIBO_USER_PAGE.format(user_id=self.user_id)
        self.page.goto(homepage_url, wait_until="domcontentloaded")
        self.page.wait_for_timeout(3_000)

        self._scroll_and_collect()

        logger.info(
            f"✅ 用户 {self.username} 爬取完成，共 {len(self.results)} 条微博"
            + (f"（跳过已爬 {self._skipped_existing} 条）" if self._skipped_existing else "")
        )
        return self.results

    # ================================================================
    # 滚动加载 + 逐条处理
    # ================================================================
    def _scroll_and_collect(self) -> None:
        """滚动页面，从 API 拦截数据中提取微博信息"""
        empty_scrolls = 0
        MAX_EMPTY_SCROLLS = 30  # 连续 30 次滚动无新数据则停止

        while True:
            new_posts, had_api_response = self.api_client.get_intercepted_posts(clear=True)

            if new_posts:
                empty_scrolls = 0
            elif had_api_response:
                # API 有响应但返回 0 条 → 没有更多数据了
                logger.info("⏹ API 返回 0 条微博，已到达末尾，停止爬取")
                return
            else:
                empty_scrolls += 1
                if empty_scrolls >= MAX_EMPTY_SCROLLS:
                    logger.info(
                        f"⏹ 连续 {empty_scrolls} 次滚动无 API 响应，停止爬取"
                    )
                    return

            for post in new_posts:
                wid = post.weibo_id
                if not wid or wid in self._processed_ids:
                    if wid and wid in self._excluded_ids:
                        self._skipped_existing += 1
                    continue

                # 置顶微博跳过（避免其过旧的时间导致提前停止爬取）
                if post.is_pinned:
                    logger.info(f"📌 跳过置顶微博: {wid}")
                    self._processed_ids.add(wid)
                    continue

                # 评论/赞过等非本人发布微博跳过
                if post.is_comment:
                    logger.info(f"💬 跳过非本人发布微博: {wid}")
                    self._processed_ids.add(wid)
                    continue

                # --- 时间范围判断 ---
                weibo_dt = post.created_at_dt

                if weibo_dt is None:
                    logger.warning(f"⚠️ 微博 {wid} 时间解析失败，跳过")
                    self._processed_ids.add(wid)
                    continue

                if not is_in_range(weibo_dt, self.start_date, self.end_date):
                    if is_before_start(weibo_dt, self.start_date):
                        logger.info(
                            f"⏹ 微博时间 {weibo_dt} 早于 {self.start_date}，停止滚动"
                        )
                        return
                    else:
                        logger.info(f"⏭ 微博 {wid} ({weibo_dt}) 超出时间范围，跳过")
                        self._processed_ids.add(wid)
                        continue

                # --- 处理单条 ---
                random_delay(reason="处理下一条微博")
                try:
                    result = self._process_single_post(post)
                except Exception as e:
                    logger.error(f"❌ 处理微博 {wid} 时发生未预期异常: {e}")
                    result = self._make_fail_result(post, str(e))
                self.results.append(result)
                self._processed_ids.add(wid)

                # 回调：写入 Excel 结果 & 更新最后抓取时间等
                if self.on_post_processed:
                    try:
                        self.on_post_processed(result)
                    except Exception as e:
                        logger.error(f"❌ 回调处理失败（微博 {wid}）: {e}")

                if MAX_WEIBO_COUNT > 0 and len(self.results) >= MAX_WEIBO_COUNT:
                    logger.info(f"⏹ 已达最大爬取数 {MAX_WEIBO_COUNT}，停止")
                    return

            # --- 滚动 ---
            self._scroll_down()
            # 滚动后如有新数据到达，立即处理，避免再次滚动触发多余请求
            if self.api_client._intercepted_responses:
                continue

    # ================================================================
    # 单条微博处理（API 版本）
    # ================================================================
    def _make_fail_result(self, post: WeiboPost, error_msg: str) -> dict:
        """为处理失败的微博生成一条失败记录"""
        time_display = (
            post.created_at_dt.strftime("%Y-%m-%d %H:%M:%S")
            if post.created_at_dt else "未知时间"
        )
        return {
            "用户id": self.user_id,
            "用户名": self.username,
            "微博发布时间": time_display,
            "微博类型": post.weibo_type,
            "文案": post.text_raw or "",
            "爬虫结果": f"失败: {error_msg[:80]}",
            "微博url": f"https://weibo.com/{self.user_id}/{post.weibo_id}",
            "图片数量": len(post.image_urls),
            "Live图数量": len(post.live_photo_pairs),
            "视频数量": len(post.video_urls),
            "图片下载数量": 0,
            "Live图下载数量": 0,
            "视频下载数量": 0,
        }

    def _process_single_post(self, post: WeiboPost) -> dict:
        """
        根据 WeiboPost（API 数据）处理一条微博：
        下载媒体（带重试）→ 组装结果
        """
        # 1. 时间格式化
        if post.created_at_dt:
            time_formatted = post.created_at_dt.strftime("%Y%m%d_%H%M%S")
            time_display = post.created_at_dt.strftime("%Y-%m-%d %H:%M:%S")
        else:
            time_formatted = datetime.now().strftime("%Y%m%d_%H%M%S")
            time_display = "未知时间"

        content = post.text_raw or ""

        # 2. 微博 URL
        weibo_url = f"https://weibo.com/{self.user_id}/{post.weibo_id}"

        # 3. 下载媒体（带重试）
        download_result = {"images": 0, "live_photos": 0, "videos": 0}
        download_error = None

        if self.download_media:
            for attempt in range(1, self._post_retry_max + 1):
                try:
                    download_result = self.downloader.download_weibo_media(
                        weibo_id=post.weibo_id,
                        weibo_time=time_formatted,
                        content=content,
                        image_urls=post.image_urls,
                        live_photo_pairs=post.live_photo_pairs,
                        video_urls=post.video_urls,
                    )
                    download_error = None
                    break
                except Exception as e:
                    download_error = str(e)
                    if attempt < self._post_retry_max:
                        wait_s = attempt * 3
                        logger.warning(
                            f"⚠️ 媒体下载失败（微博 {post.weibo_id}，"
                            f"第 {attempt}/{self._post_retry_max} 次）: {e}，{wait_s}s 后重试..."
                        )
                        time_module.sleep(wait_s)
                    else:
                        logger.error(
                            f"❌ 媒体下载失败（微博 {post.weibo_id}），"
                            f"已重试 {self._post_retry_max} 次: {e}"
                        )

        # 4. 微博类型与结果
        weibo_type = post.weibo_type
        status = "成功" if download_error is None else f"失败: {download_error[:80]}"

        return {
            "用户id": self.user_id,
            "用户名": self.username,
            "微博发布时间": time_display,
            "微博类型": weibo_type,
            "文案": content,
            "爬虫结果": status,
            "微博url": weibo_url,
            "图片数量": len(post.image_urls),
            "Live图数量": len(post.live_photo_pairs),
            "视频数量": len(post.video_urls),
            "图片下载数量": download_result.get("images", 0),
            "Live图下载数量": download_result.get("live_photos", 0),
            "视频下载数量": download_result.get("videos", 0),
        }

    # ================================================================
    # 滚动辅助
    # ================================================================
    def _scroll_down(self) -> None:
        human_like_delay(1.5, 2.5)
        current_scroll = self.page.evaluate("window.scrollY")
        view_height = self.page.evaluate("window.innerHeight")
        page_height = self.page.evaluate("document.body.scrollHeight")
        # 直接滚到接近页面底部，触发下一页 API 加载
        new_scroll = max(
            current_scroll + view_height,
            page_height - view_height * 1.5
        )
        self.page.evaluate(f"window.scrollTo(0, {new_scroll})")
        self.page.wait_for_timeout(SCROLL_WAIT)
        logger.info(f"📜 滚动: {current_scroll:.0f} → {new_scroll:.0f}（页面高度 {page_height:.0f}）")