"""
媒体下载模块
下载微博图片、Live 图、视频
目录结构：用户id / 发布时间_微博id_文案(前50字) / 同前缀_序号.后缀
Live 图静态与动态保持相同序号不同后缀，便于检索
"""

import re
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Optional
from urllib.parse import urlparse

import httpx
from loguru import logger

from config.settings import DOWNLOAD_DIR, DOWNLOAD_RETRY, DOWNLOAD_CONCURRENCY


class MediaDownloader:
    """微博媒体下载器"""

    IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".gif", ".webp", ".bmp"}
    VIDEO_EXTENSIONS = {".mp4", ".mov", ".m3u8", ".flv", ".avi", ".mkv"}

    # Windows 文件名非法字符正则
    ILLEGAL_CHARS_PATTERN = re.compile(r'[\\/:*?"<>|\n\r\t]')

    def __init__(
        self,
        user_id: str,
        cookies: Optional[list[dict]] = None,
        headers: Optional[dict] = None,
    ):
        self.user_id = user_id
        self.base_dir = DOWNLOAD_DIR / user_id
        self.base_dir.mkdir(parents=True, exist_ok=True)

        self.headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            ),
            "Referer": "https://weibo.com/",
        }
        if headers:
            self.headers.update(headers)

        self.cookies = {}
        if cookies:
            for c in cookies:
                self.cookies[c.get("name", "")] = c.get("value", "")

    # ================================================================
    # 静态工具方法
    # ================================================================
    @staticmethod
    def sanitize_text(text: str, max_len: int = 50) -> str:
        """
        去除 Windows 文件名非法字符，截断至指定长度

        Args:
            text: 原始文本
            max_len: 最大保留长度（中文字符按1个计）

        Returns:
            安全的文件名片段，非法字符被移除后截断
        """
        if not text:
            return "无文案"
        # 移除非法字符
        text = MediaDownloader.ILLEGAL_CHARS_PATTERN.sub("", text)
        # 合并连续空白为单个空格
        text = re.sub(r"\s+", " ", text).strip()
        # 截断（按字符数）
        if len(text) > max_len:
            text = text[:max_len].strip()
        return text if text else "无文案"

    # ================================================================
    # 公开方法：下载一条微博的全部媒体
    # ================================================================
    def download_weibo_media(
        self,
        weibo_id: str,
        weibo_time: str,
        content: str,
        image_urls: list[str],
        live_photo_pairs: list[tuple[str, str]],
        video_urls: list[str],
    ) -> dict:
        """
        下载一条微博的所有媒体文件，统一编号

        Args:
            weibo_id:      微博唯一标识（如 R0rKIdONA）
            weibo_time:    发布时间，格式 YYYYMMDD_hhmmss
            content:       文案原文（用于文件夹命名，自动净化）
            image_urls:    普通图片 URL 列表
            live_photo_pairs: Live 图 [(静态图URL, 动态视频URL), ...]
            video_urls:    视频 URL 列表

        Returns:
            {"images": int, "live_photos": int, "videos": int}
        """
        folder_name = self._make_folder_name(weibo_time, weibo_id, content)
        target_dir = self.base_dir / folder_name
        target_dir.mkdir(parents=True, exist_ok=True)

        all_tasks = []  # [(url, filepath, media_type), ...]
        seq = 1

        # --- 普通图片 ---
        for url in image_urls:
            if url:
                ext = self._get_extension(url, "图片")
                filename = f"{folder_name}_{seq:03d}{ext}"
                all_tasks.append((url, target_dir / filename, "图片"))
                seq += 1

        # --- Live 图：静态与动态同序号不同后缀 ---
        for static_url, video_url in live_photo_pairs:
            if static_url:
                ext = self._get_extension(static_url, "图片")
                filename = f"{folder_name}_{seq:03d}{ext}"
                all_tasks.append((static_url, target_dir / filename, "Live图(静态)"))
            if video_url:
                ext = self._get_extension(video_url, "视频")
                filename = f"{folder_name}_{seq:03d}{ext}"
                all_tasks.append((video_url, target_dir / filename, "Live图(视频)"))
            seq += 1

        # --- 视频 ---
        for url in video_urls:
            if url:
                ext = self._get_extension(url, "视频")
                filename = f"{folder_name}_{seq:03d}{ext}"
                all_tasks.append((url, target_dir / filename, "视频"))
                seq += 1

        if not all_tasks:
            logger.info(f"  📭 无媒体文件（微博 {weibo_id}）")
            return {"images": 0, "live_photos": 0, "videos": 0}

        # --- 并发下载 ---
        results = self._batch_download(all_tasks)

        # --- 统计 ---
        image_count = 0
        live_count = 0
        video_count = 0
        for (_, _, mtype), ok in zip(all_tasks, results):
            if ok:
                if mtype == "图片":
                    image_count += 1
                elif mtype == "Live图(静态)":
                    live_count += 1  # 每对只计一次
                elif mtype == "视频":
                    video_count += 1

        logger.info(
            f"  📥 下载完成: 图片{image_count} | Live图{live_count} | 视频{video_count}"
            f"（微博 {weibo_id}）"
        )
        return {"images": image_count, "live_photos": live_count, "videos": video_count}

    # ================================================================
    # 内部方法
    # ================================================================
    def _make_folder_name(self, weibo_time: str, weibo_id: str, content: str) -> str:
        """构建文件夹名：发布时间_微博id_安全文案"""
        safe = self.sanitize_text(content)
        return f"{weibo_time}_{weibo_id}_{safe}"

    def _batch_download(self, tasks: list[tuple]) -> list[bool]:
        """线程池并发下载，返回每个任务的成功状态"""
        results = [False] * len(tasks)
        with ThreadPoolExecutor(max_workers=DOWNLOAD_CONCURRENCY) as executor:
            future_to_idx = {}
            for idx, (url, filepath, media_type) in enumerate(tasks):
                future = executor.submit(self._download_single, url, filepath, media_type)
                future_to_idx[future] = idx

            for future in as_completed(future_to_idx):
                idx = future_to_idx[future]
                try:
                    results[idx] = future.result()
                except Exception:
                    results[idx] = False

        total_ok = sum(results)
        logger.info(f"  📥 {total_ok}/{len(tasks)} 个文件下载成功")
        return results

    def _download_single(self, url: str, filepath: Path, media_type: str) -> bool:
        """下载单个文件，带重试和跳过已有"""
        if filepath.exists() and filepath.stat().st_size > 0:
            logger.debug(f"  ⏭ 跳过: {filepath.name}")
            return True

        for attempt in range(1, DOWNLOAD_RETRY + 1):
            try:
                with httpx.Client(
                    cookies=self.cookies,
                    headers=self.headers,
                    timeout=60.0,
                    follow_redirects=True,
                ) as client:
                    resp = client.get(url)
                    resp.raise_for_status()
                    filepath.write_bytes(resp.content)
                    size_kb = len(resp.content) / 1024
                    logger.debug(f"  ✅ {filepath.name} ({size_kb:.1f} KB)")
                    return True
            except httpx.HTTPStatusError as e:
                logger.warning(f"  ⚠️ HTTP {e.response.status_code} - {filepath.name} ({attempt}/{DOWNLOAD_RETRY})")
                if e.response.status_code in (403, 404):
                    return False
            except (httpx.TimeoutException, httpx.ConnectError) as e:
                logger.warning(f"  ⚠️ 网络错误 - {filepath.name} ({attempt}/{DOWNLOAD_RETRY})")
            except Exception as e:
                logger.error(f"  ❌ 异常 - {filepath.name}: {e}")
                return False
            if attempt < DOWNLOAD_RETRY:
                time.sleep(2 * attempt)

        logger.error(f"  ❌ 下载失败: {filepath.name}")
        return False

    def _get_extension(self, url: str, media_type: str) -> str:
        """从 URL 推断文件扩展名"""
        parsed = urlparse(url)
        path = parsed.path
        if "." in path:
            ext = Path(path).suffix.lower()
            if ext and ext in self.IMAGE_EXTENSIONS | self.VIDEO_EXTENSIONS:
                return ext
        return ".mp4" if media_type in ("视频", "Live图") else ".jpg"