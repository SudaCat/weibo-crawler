"""
核心爬虫模块（API 优先版本）
通过 WeiboAPIClient 拦截 AJAX 接口获取结构化微博数据，
仅在 API 不可用时回退到 DOM/XPath 解析（可选）。
"""

import re
import time as time_module
from datetime import datetime, timedelta
from typing import Callable, Optional

from loguru import logger
from playwright.sync_api import Page, Locator

from config.settings import (
    WEIBO_USER_PAGE,
    SCROLL_WAIT,
    MAX_SCROLL_NO_NEW,
    MAX_WEIBO_COUNT,
    SEARCH_RETRY_MAX,
    POST_RETRY_MAX,
    USE_API_DATA_SOURCE,
    API_FALLBACK_TO_DOM,
)
from core.weibo_api import WeiboAPIClient, WeiboPost
from core.media_downloader import MediaDownloader
from utils.anti_ban import random_delay, human_like_delay
from utils.time_utils import parse_weibo_time, is_before_start, is_in_range


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
        self._processed_ids: set[str] = set()  # 跨重试去重
        self._post_retry_max = POST_RETRY_MAX

    # ================================================================
    # 主入口
    # ================================================================
    def crawl(self) -> list[dict]:
        logger.info(f"🔍 开始爬取用户: {self.username} ({self.user_id})")
        logger.info(f"   时间范围: {self.start_date} ~ {self.end_date or '最新'}")

        # ✅ 先初始化 API 拦截（必须在 goto 之前！）
        if USE_API_DATA_SOURCE:
            self.api_client = WeiboAPIClient(self.page)
            logger.info("📡 已启用 API 拦截模式")
        else:
            self.api_client = None
            logger.info("📄 使用 DOM 解析模式（API 已禁用）")

        if not self.api_client:
            raise RuntimeError("API 数据源未启用，无法爬取")

        last_error = None
        for attempt in range(1, SEARCH_RETRY_MAX + 1):
            try:
                self._search_and_collect()
                break
            except Exception as e:
                last_error = e
                if attempt < SEARCH_RETRY_MAX:
                    wait_s = attempt * 3
                    logger.warning(
                        f"⚠️ 搜索接口异常（第 {attempt}/{SEARCH_RETRY_MAX} 次）: {e}，"
                        f"{wait_s}s 后重试..."
                    )
                    time_module.sleep(wait_s)
        else:
            raise RuntimeError(
                f"搜索接口重试 {SEARCH_RETRY_MAX} 次后仍失败: {last_error}"
            )

        logger.info(f"✅ 用户 {self.username} 爬取完成，共 {len(self.results)} 条微博")
        return self.results

    # ================================================================
    # 搜索接口分页获取
    # ================================================================
    def _search_and_collect(self) -> None:
        """通过搜索接口按时间范围分页获取微博（超过一个月则按月拆分）"""

        SEARCH_URL = (
            "https://weibo.com/ajax/statuses/searchProfile"
            "?uid={uid}&page={page}&starttime={start_ts}&endtime={end_ts}"
            "&hasori=1&hasret=1&hastext=1&haspic=1&hasvideo=1&hasmusic=1"
        )

        # 解析时间范围
        start_dt = datetime.strptime(self.start_date, "%Y-%m-%d %H:%M:%S")
        if self.end_date:
            end_dt = datetime.strptime(self.end_date, "%Y-%m-%d %H:%M:%S")
        else:
            end_dt = datetime.now()

        # 按自然月拆分
        segments = self._split_by_month(start_dt, end_dt)
        logger.info(f"📅 时间范围拆分为 {len(segments)} 个月段")

        # 导航到用户主页建立浏览器上下文（仅一次）
        homepage_url = WEIBO_USER_PAGE.format(user_id=self.user_id)
        self.page.goto(homepage_url, wait_until="domcontentloaded")
        self.page.wait_for_timeout(3_000)
        self.api_client.get_intercepted_posts(clear=True)

        for seg_idx, (seg_start, seg_end) in enumerate(segments, start=1):
            start_ts = int(seg_start.timestamp())
            end_ts = int(seg_end.timestamp())

            logger.info(
                f"📅 [{seg_idx}/{len(segments)}] "
                f"{seg_start.strftime('%Y-%m-%d')} ~ {seg_end.strftime('%Y-%m-%d')}"
            )

            cur_page = 1
            while True:
                url = SEARCH_URL.format(
                    uid=self.user_id, page=cur_page,
                    start_ts=start_ts, end_ts=end_ts,
                )
                logger.info(f"🔍 搜索第 {cur_page} 页")

                raw_data = self.page.evaluate("""
                    async (url) => {
                        const resp = await fetch(url);
                        return await resp.json();
                    }
                """, url)

                if not isinstance(raw_data, dict) or raw_data.get("ok") != 1:
                    logger.warning(f"⚠️ 搜索接口返回异常: {str(raw_data)[:200]}")
                    break

                new_posts = self.api_client._parse_response(raw_data)

                if not new_posts:
                    logger.info("⏹ 搜索无更多结果，停止")
                    break

                new_processed = 0
                for post in new_posts:
                    wid = post.weibo_id
                    if not wid or wid in self._processed_ids:
                        continue

                    if post.is_pinned:
                        logger.info(f"📌 跳过置顶微博: {wid}")
                        self._processed_ids.add(wid)
                        continue

                    if post.is_comment:
                        logger.info(f"💬 跳过非本人发布微博: {wid}")
                        self._processed_ids.add(wid)
                        continue

                    weibo_dt = post.created_at_dt
                    if weibo_dt is None:
                        logger.warning(f"⚠️ 微博 {wid} 时间解析失败，跳过")
                        self._processed_ids.add(wid)
                        continue

                    if not is_in_range(weibo_dt, self.start_date, self.end_date):
                        if is_before_start(weibo_dt, self.start_date):
                            logger.info(
                                f"⏹ 微博时间 {weibo_dt} 早于 {self.start_date}，停止"
                            )
                            return
                        else:
                            logger.info(
                                f"⏭ 微博 {wid} ({weibo_dt}) 超出时间范围，跳过"
                            )
                            self._processed_ids.add(wid)
                            continue

                    random_delay(reason="处理下一条微博")
                    try:
                        result = self._process_single_post(post)
                    except Exception as e:
                        logger.error(f"❌ 处理微博 {wid} 时发生未预期异常: {e}")
                        result = self._make_fail_result(post, str(e))
                    self.results.append(result)
                    self._processed_ids.add(wid)
                    new_processed += 1

                    if self.on_post_processed:
                        try:
                            self.on_post_processed(result)
                        except Exception as e:
                            logger.error(f"❌ 回调处理失败（微博 {wid}）: {e}")

                    if MAX_WEIBO_COUNT > 0 and len(self.results) >= MAX_WEIBO_COUNT:
                        logger.info(f"⏹ 已达最大爬取数 {MAX_WEIBO_COUNT}，停止")
                        return

                cur_page += 1
                if cur_page > 50:
                    logger.warning("⚠️ 已搜索 50 页，停止以避免无限循环")
                    break

    @staticmethod
    def _split_by_month(start_dt: datetime, end_dt: datetime) -> list[tuple[datetime, datetime]]:
        """将时间范围按自然月拆分"""
        segments = []
        current = start_dt
        while current < end_dt:
            if current.month == 12:
                next_month = current.replace(
                    year=current.year + 1, month=1, day=1,
                    hour=0, minute=0, second=0,
                )
            else:
                next_month = current.replace(
                    month=current.month + 1, day=1,
                    hour=0, minute=0, second=0,
                )
            month_end = next_month - timedelta(seconds=1)
            seg_end = min(month_end, end_dt)
            segments.append((current, seg_end))
            current = next_month
        return segments

    # ================================================================
    # 滚动加载 + 逐条处理
    # ================================================================
    def _scroll_and_collect(self) -> None:
        """滚动页面，从 API 拦截数据中提取微博信息"""
        no_new_count = 0

        while True:
            # ---------- 从 API 获取本轮新增微博 ----------
            if self.api_client:
                new_posts = self.api_client.get_intercepted_posts(clear=True)
            else:
                new_posts = self._fallback_dom_extract()

            new_processed = 0

            for post in new_posts:
                wid = post.weibo_id
                if not wid or wid in self._processed_ids:
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
                new_processed += 1

                # 回调：写入 Excel 结果 & 更新最后抓取时间等
                if self.on_post_processed:
                    try:
                        self.on_post_processed(result)
                    except Exception as e:
                        logger.error(f"❌ 回调处理失败（微博 {wid}）: {e}")

                if MAX_WEIBO_COUNT > 0 and len(self.results) >= MAX_WEIBO_COUNT:
                    logger.info(f"⏹ 已达最大爬取数 {MAX_WEIBO_COUNT}，停止")
                    return

            # --- 停止判断（MAX_SCROLL_NO_NEW <= 0 时禁用）---
            if new_processed == 0 and MAX_SCROLL_NO_NEW > 0:
                no_new_count += 1
                if no_new_count >= MAX_SCROLL_NO_NEW:
                    logger.info("⏹ 连续多次无新内容，停止滚动")
                    return
            else:
                no_new_count = 0

            # --- 滚动 ---
            self._scroll_down()

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
    # DOM 回退模式（当 API 不可用时）
    # ================================================================
    def _fallback_dom_extract(self) -> list[WeiboPost]:
        """
        回退：DOM 解析转 WeiboPost
        仅在 USE_API_DATA_SOURCE=False 时使用
        """
        posts: list[WeiboPost] = []
        if not API_FALLBACK_TO_DOM:
            return posts

        try:
            cards = self.page.locator("article").all()
            for card in cards:
                weibo_id = self._deprecated_extract_weibo_id(card)
                time_text = self._deprecated_extract_time(card)
                content = self._deprecated_extract_content(card)
                image_urls = self._deprecated_extract_image_urls(card)

                weibo_dt = parse_weibo_time(time_text) if time_text else None

                posts.append(
                    WeiboPost(
                        weibo_id=weibo_id or "",
                        mid="",
                        created_at=time_text or "",
                        created_at_dt=weibo_dt,
                        text_raw=content,
                        text_html=content,
                        image_urls=image_urls,
                        live_photo_pairs=[],
                        video_urls=[],
                    )
                )
        except Exception as e:
            logger.warning(f"DOM 回退提取失败: {e}")

        return posts

    # ================================================================
    # 以下为原 DOM/XPath 提取方法（降级为回退/废弃）
    # ================================================================
    def _deprecated_extract_weibo_id(self, card: Locator) -> Optional[str]:
        try:
            links = card.locator("a[href*='weibo.com']").all()
            for link in links:
                href = link.get_attribute("href") or ""
                m = re.search(r"weibo\.com/\d+/([A-Za-z0-9]+)", href)
                if m:
                    return m.group(1)
        except Exception:
            pass
        return None

    def _deprecated_extract_time(self, card: Locator) -> Optional[str]:
        try:
            time_el = card.locator("time").first
            if time_el.count() > 0:
                return time_el.inner_text()
            time_el = card.locator("a[href*='/status/']").first
            if time_el.count() > 0:
                return time_el.inner_text()
        except Exception:
            pass
        return None

    def _deprecated_extract_content(self, card: Locator) -> str:
        from config.settings import WEIBO_TEXT_XPATHS

        for xpath in WEIBO_TEXT_XPATHS:
            try:
                el = card.locator(f"xpath=.{xpath}").first
                if el.count() > 0:
                    return el.inner_text().strip()
            except Exception:
                continue
        return ""

    def _deprecated_extract_image_urls(self, card: Locator) -> list[str]:
        urls = []
        try:
            imgs = card.locator("img[src*='sinaimg']").all()
            for img in imgs:
                src = img.get_attribute("src") or ""
                if not src or "http" not in src:
                    continue
                width = img.get_attribute("width") or ""
                if width and int(width) < 100:
                    continue
                src = (
                    src.replace("thumb150", "large")
                    .replace("orj360", "large")
                )
                urls.append(src)
        except Exception:
            pass
        return urls

    # ================================================================
    # 滚动辅助
    # ================================================================
    def _scroll_down(self) -> None:
        human_like_delay(1, 2)
        current_scroll = self.page.evaluate("window.scrollY")
        view_height = self.page.evaluate("window.innerHeight")
        new_scroll = current_scroll + view_height * 0.8
        self.page.evaluate(f"window.scrollTo(0, {new_scroll})")
        self.page.wait_for_timeout(SCROLL_WAIT)
        logger.debug(f"📜 滚动: {current_scroll:.0f} → {new_scroll:.0f}")