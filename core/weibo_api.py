"""
微博 API 数据源模块
通过 Playwright 拦截 AJAX 接口获取结构化微博数据
相比 DOM 解析更稳定、信息更完整（多尺寸图片、视频清晰度、Live图等）
"""

import json
import re
from datetime import datetime
from typing import Optional, Dict, Any
from dataclasses import dataclass, field

from loguru import logger
from playwright.sync_api import Page

from config.settings import IMAGE_SIZE_PREFERENCE


# ================================================================
# 数据类：封装一条微博的全部结构化信息
# ================================================================
@dataclass
class WeiboPost:
    """微博帖子结构化数据"""
    weibo_id: str                           # 微博唯一 ID（如 R0rKIdONA）
    mid: str                                # 微博数字 ID
    created_at: str                         # 原始时间字符串
    created_at_dt: Optional[datetime] = None # 解析后的 datetime
    text_raw: str = ""                      # 纯文本正文
    text_html: str = ""                     # HTML 格式正文
    region_name: str = ""                   # 发布位置
    source: str = ""                        # 发布来源
    reposts_count: int = 0                  # 转发数
    comments_count: int = 0                 # 评论数
    attitudes_count: int = 0                # 点赞数

    # 媒体
    image_urls: list[str] = field(default_factory=list)       # 普通图片 URL
    live_photo_pairs: list[tuple[str, str]] = field(default_factory=list)  # [(静态图, 视频), ...]
    video_urls: list[str] = field(default_factory=list)       # 纯视频 URL

    # 标志
    is_retweet: bool = False                # 是否转发
    is_ad: bool = False                     # 是否广告
    is_long_text: bool = False              # 是否长文
    has_video: bool = False                 # 是否有视频
    has_live_photo: bool = False            # 是否有 Live 图

    # 话题
    topics: list[str] = field(default_factory=list)

    # --- 微博类型（推导属性） ---
    @property
    def weibo_type(self) -> str:
        """根据字段自动推导微博类型"""
        if self.is_retweet:
            return "转发"
        if self.has_video:
            return "视频"
        if self.has_live_photo:
            return "Live图"
        if self.image_urls:
            return "图文"
        return "纯文字"

    # 原始数据（用于调试/扩展）
    raw: dict = field(default_factory=dict)


class WeiboAPIClient:
    """
    微博 API 客户端
    通过 Playwright 拦截 page 的网络请求，捕获微博列表接口的 JSON 响应
    """

    # 微博列表 API URL 模式
    LIST_API_PATTERN = re.compile(r"/ajax/statuses/(mymblog|searchBlogsByNick|userBlogs)")

    # 时间格式（API 返回）
    TIME_FORMAT = "%a %b %d %H:%M:%S %z %Y"  # "Thu May 21 17:39:36 +0800 2026"

    def __init__(self, page: Page):
        """
        Args:
            page: Playwright Page 对象（已登录）
        """
        self.page = page
        self._intercepted_responses: list[dict] = []
        self._setup_interceptor()

    # ============================================================
    # 拦截器
    # ============================================================
    def _setup_interceptor(self) -> None:
        """设置网络响应拦截器，捕获 API 数据"""
        def on_response(response):
            url = response.url
            logger.debug(f"🌐 网络请求: {url[:120]}")  # 打印日志
            if self.LIST_API_PATTERN.search(url):
                logger.debug(f"🎯 匹配到 API: {url}")    # 打印日志
                try:
                    body = response.json()
                    if isinstance(body, dict) and body.get("ok") == 1:
                        self._intercepted_responses.append(body)
                        logger.debug(f"📡 拦截到 API 响应: {len(body.get('data', {}).get('list', []))} 条微博")
                except Exception:
                    pass  # 非 JSON 响应忽略

        self.page.on("response", on_response)

    # ============================================================
    # 公开方法：获取拦截到的数据
    # ============================================================
    def get_intercepted_posts(self, clear: bool = True) -> list[WeiboPost]:
        """
        获取所有拦截到的微博帖子

        Args:
            clear: 是否清空已取出的数据

        Returns:
            WeiboPost 列表
        """
        all_posts = []
        for resp in self._intercepted_responses:
            posts = self._parse_response(resp)
            all_posts.extend(posts)
        if clear:
            self._intercepted_responses.clear()
        return all_posts

    # ============================================================
    # JSON 解析
    # ============================================================
    def _parse_response(self, response: dict) -> list[WeiboPost]:
        """解析单个 API 响应"""
        data = response.get("data", {})
        raw_list = data.get("list", [])
        posts = []
        for item in raw_list:
            try:
                post = self._parse_single_item(item)
                posts.append(post)
            except Exception as e:
                logger.warning(f"⚠️ 解析单条微博失败: {e}")
                continue
        return posts

    def _parse_single_item(self, item: dict) -> WeiboPost:
        """将 API 返回的单条微博 JSON 解析为 WeiboPost"""
        # --- 基础字段 ---
        weibo_id = str(item.get("id", "") or item.get("mid", ""))
        mid = str(item.get("mid", ""))
        created_at = item.get("created_at", "")
        created_at_dt = self._parse_time(created_at)
        text_raw = item.get("text_raw", "") or item.get("text", "")
        text_html = item.get("text", "")
        region_name = item.get("region_name", "").replace("发布于 ", "").strip()
        source = item.get("source", "")
        reposts_count = item.get("reposts_count", 0)
        comments_count = item.get("comments_count", 0)
        attitudes_count = item.get("attitudes_count", 0)

        # --- 图片 ---
        image_urls, live_photo_pairs, has_live_photo = self._parse_pic_infos(
            item.get("pic_infos", {})
        )

        # --- 视频 ---
        video_urls, has_video = self._parse_page_info(item.get("page_info", {}))

        # --- 标志 ---
        is_retweet = "retweeted_status" in item and bool(item.get("retweeted_status"))
        is_ad = item.get("isAd", False)
        is_long_text = item.get("isLongText", False)

        # --- 话题 ---
        topics = [
            t.get("topic_title", "")
            for t in item.get("topic_struct", [])
            if t.get("topic_title")
        ]

        return WeiboPost(
            weibo_id=weibo_id,
            mid=mid,
            created_at=created_at,
            created_at_dt=created_at_dt,
            text_raw=text_raw,
            text_html=text_html,
            region_name=region_name,
            source=source,
            reposts_count=reposts_count,
            comments_count=comments_count,
            attitudes_count=attitudes_count,
            image_urls=image_urls,
            live_photo_pairs=live_photo_pairs,
            video_urls=video_urls,
            is_retweet=is_retweet,
            is_ad=is_ad,
            is_long_text=is_long_text,
            has_video=has_video,
            has_live_photo=has_live_photo,
            topics=topics,
            raw=item,
        )

    # ============================================================
    # 图片解析
    # ============================================================
    def _parse_pic_infos(self, pic_infos: dict) -> tuple[list[str], list[tuple[str, str]], bool]:
        """
        解析 pic_infos 字典

        Returns:
            (image_urls, live_photo_pairs, has_live_photo)
        """
        image_urls = []
        live_photo_pairs = []
        has_live_photo = False

        if not pic_infos:
            return image_urls, live_photo_pairs, has_live_photo

        for pic_id, info in pic_infos.items():
            if not isinstance(info, dict):
                continue

            pic_type = info.get("type", "pic")

            if pic_type == "livephoto":
                has_live_photo = True
                # 静态图：按偏好选择尺寸
                static_url = self._pick_best_image_url(info)
                # Live Photo 视频
                video_url = info.get("video", "")
                live_photo_pairs.append((static_url, video_url))
            else:
                # 普通图片
                url = self._pick_best_image_url(info)
                if url:
                    image_urls.append(url)

        return image_urls, live_photo_pairs, has_live_photo

    def _pick_best_image_url(self, info: dict) -> str:
        """
        按配置的尺寸偏好选择最佳图片 URL

        可用尺寸（从大到小）：
        original > largest > mw2000 > large > bmiddle > thumbnail
        """
        for size in IMAGE_SIZE_PREFERENCE:
            size_data = info.get(size, {})
            if isinstance(size_data, dict) and size_data.get("url"):
                return size_data["url"]

        # 兜底：遍历所有可能的尺寸
        for size_key in ("largest", "original", "mw2000", "large", "bmiddle", "thumbnail"):
            size_data = info.get(size_key, {})
            if isinstance(size_data, dict) and size_data.get("url"):
                return size_data["url"]

        return ""

    # ============================================================
    # 视频解析
    # ============================================================
    def _parse_page_info(self, page_info: Optional[dict]) -> tuple[list[str], bool]:
        """
        解析 page_info 中的视频信息

        Returns:
            (video_urls, has_video)
        """
        if not page_info or not isinstance(page_info, dict):
            return [], False

        page_type = str(page_info.get("type", ""))

        # type=11 是视频
        if page_type == "11":
            media_info = page_info.get("media_info", {})
            playback_list = media_info.get("playback_list", [])
            if playback_list:
                # 选最高清晰度
                video_urls = self._pick_best_video_urls(playback_list)
                return video_urls, bool(video_urls)

            # 部分情况下 URL 直接在 page_info 中
            mp4_url = page_info.get("mp4_url", "") or page_info.get("url", "")
            if mp4_url:
                return [mp4_url], True

        # type=0 是音频/歌曲，暂不处理
        return [], False

    def _pick_best_video_urls(self, playback_list: list[dict]) -> list[str]:
        """
        从播放列表中选择最佳质量的视频 URL

        质量排序：hd > sd > 其他
        """
        urls_by_quality = {}
        for item in playback_list:
            quality = item.get("quality", "unknown")
            url = item.get("url", "")
            if url:
                urls_by_quality[quality] = url

        # 优先 hd
        for pref in ("hd", "sd"):
            if pref in urls_by_quality:
                return [urls_by_quality[pref]]

        # 兜底：返回第一个
        if urls_by_quality:
            return [list(urls_by_quality.values())[0]]

        return []

    # ============================================================
    # 时间解析
    # ============================================================
    def _parse_time(self, time_str: str) -> Optional[datetime]:
        if not time_str:
            return None
        try:
            dt = datetime.strptime(time_str, self.TIME_FORMAT)
            return dt.replace(tzinfo=None)   # ← 去除时区，转为 naive
        except ValueError:
            pass
        from utils.time_utils import parse_weibo_time
        return parse_weibo_time(time_str)

    # ============================================================
    # 工具方法：从 WeiboPost 生成下载参数
    # ============================================================
    @staticmethod
    def to_download_params(post: WeiboPost) -> dict:
        """
        将 WeiboPost 转为 MediaDownloader.download_weibo_media() 所需的参数字典
        """
        if post.created_at_dt:
            time_formatted = post.created_at_dt.strftime("%Y%m%d_%H%M%S")
            time_display = post.created_at_dt.strftime("%Y-%m-%d %H:%M:%S")
        else:
            time_formatted = datetime.now().strftime("%Y%m%d_%H%M%S")
            time_display = "未知时间"

        return {
            "weibo_id": post.weibo_id,
            "weibo_time": time_formatted,
            "content": post.text_raw,
            "image_urls": post.image_urls,
            "live_photo_pairs": post.live_photo_pairs,
            "video_urls": post.video_urls,
            # 额外信息（用于 Excel）
            "time_display": time_display,
            "region_name": post.region_name,
            "source": post.source,
            "reposts_count": post.reposts_count,
            "comments_count": post.comments_count,
            "attitudes_count": post.attitudes_count,
            "topics": post.topics,
            "weibo_type": post.weibo_type,  # 新增
        }