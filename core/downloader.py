"""Video downloader adapter supporting Douyin URLs and yt-dlp fallback."""

from __future__ import annotations

import logging
import os
import re
from pathlib import Path
from typing import Callable, Optional, Tuple

import requests
import yt_dlp

logger = logging.getLogger(__name__)

# Standard user agent for Douyin
USER_AGENT_DESKTOP = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36"
)
USER_AGENT_MOBILE = (
    "Mozilla/5.0 (iPhone; CPU iPhone OS 16_6 like Mac OS X) AppleWebKit/605.1.15 "
    "(KHTML, like Gecko) Version/16.6 Mobile/15E148 Safari/604.1"
)


class DownloaderAdapter:
    """Adapter for downloading videos from Douyin and fallback sources."""

    def __init__(self, download_dir: Optional[str | Path] = None):
        self.download_dir = Path(download_dir) if download_dir else Path.cwd() / "workspace" / "downloads"
        self.download_dir.mkdir(parents=True, exist_ok=True)

    @staticmethod
    def extract_url(text: str) -> Optional[str]:
        """Extract first valid HTTP/HTTPS URL from raw string or Douyin share text."""
        if not text:
            return None
        match = re.search(r"https?://[^\s<>\"']+", text)
        if match:
            return match.group(0).rstrip(".,;!?")
        return None

    def resolve_short_url(self, short_url: str) -> Tuple[str, Optional[str]]:
        """Follow redirects from v.douyin.com to full URL and extract video ID."""
        session = requests.Session()
        session.headers.update({"User-Agent": USER_AGENT_DESKTOP})
        try:
            resp = session.get(short_url, allow_redirects=True, timeout=15)
            final_url = resp.url
            # Extract video ID from URL like https://www.douyin.com/video/7123456789012345678
            vid_match = re.search(r"/video/(\d+)", final_url)
            video_id = vid_match.group(1) if vid_match else None
            return final_url, video_id
        except Exception as e:
            logger.warning(f"Không thể resolve URL {short_url}: {e}")
            return short_url, None

    def download_with_ytdlp(
        self,
        url: str,
        output_filename: str,
        progress_callback: Optional[Callable[[int, str], None]] = None,
    ) -> Path:
        """Download using yt-dlp with progress tracking."""
        target_path_template = str(self.download_dir / f"{output_filename}.%(ext)s")

        def hook(d: dict):
            if progress_callback and d.get("status") == "downloading":
                total = d.get("total_bytes") or d.get("total_bytes_estimate") or 0
                downloaded = d.get("downloaded_bytes", 0)
                if total > 0:
                    pct = int(downloaded / total * 100)
                    progress_callback(pct, f"Đang tải video: {pct}% ({downloaded // 1024} KB)")
                else:
                    progress_callback(50, "Đang tải dữ liệu...")

        ydl_opts = {
            "outtmpl": target_path_template,
            "format": "bestvideo+bestaudio/best",
            "merge_output_format": "mp4",
            "progress_hooks": [hook],
            "quiet": True,
            "no_warnings": True,
            "http_headers": {
                "User-Agent": USER_AGENT_DESKTOP,
                "Referer": "https://www.douyin.com/",
            },
            "retries": 3,
        }

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([url])

        # Find resulting mp4
        candidates = list(self.download_dir.glob(f"{output_filename}.*"))
        if not candidates:
            raise RuntimeError("yt-dlp không xuất được file video.")
        mp4_files = [c for c in candidates if c.suffix.lower() == ".mp4"]
        return mp4_files[0] if mp4_files else candidates[0]

    def download_direct_douyin(
        self,
        final_url: str,
        video_id: str,
        output_filename: str,
        progress_callback: Optional[Callable[[int, str], None]] = None,
    ) -> Path:
        """Attempt direct download via Douyin web endpoint if available."""
        target_path = self.download_dir / f"{output_filename}.mp4"
        headers = {
            "User-Agent": USER_AGENT_DESKTOP,
            "Referer": "https://www.douyin.com/",
        }

        # Query web aweme detail endpoint
        api_url = f"https://www.douyin.com/aweme/v1/web/aweme/detail/?aweme_id={video_id}"
        resp = requests.get(api_url, headers=headers, timeout=12)
        if resp.status_code == 200:
            data = resp.json()
            aweme_detail = data.get("aweme_detail", {})
            video_obj = aweme_detail.get("video", {})
            play_list = video_obj.get("play_addr", {}).get("url_list", [])
            if play_list:
                play_url = play_list[0].replace("playwm", "play")
                # Download stream
                with requests.get(play_url, headers=headers, stream=True, timeout=30) as r:
                    r.raise_for_status()
                    total_len = int(r.headers.get("content-length", 0))
                    downloaded = 0
                    with open(target_path, "wb") as f:
                        for chunk in r.iter_content(chunk_size=65536):
                            if chunk:
                                f.write(chunk)
                                downloaded += len(chunk)
                                if progress_callback and total_len > 0:
                                    pct = int(downloaded / total_len * 100)
                                    progress_callback(pct, f"Đang tải: {pct}%")
                    if target_path.exists() and target_path.stat().st_size > 0:
                        return target_path

        raise RuntimeError("Không thể trích xuất stream trực tiếp từ Douyin.")

    def download(
        self,
        raw_input: str,
        task_id: str,
        progress_callback: Optional[Callable[[int, str], None]] = None,
    ) -> Path:
        """Main download entrypoint with fallback logic."""
        url = self.extract_url(raw_input)
        if not url:
            raise ValueError(f"Không tìm thấy URL hợp lệ trong chuỗi: '{raw_input}'")

        if progress_callback:
            progress_callback(5, "Đang phân tích liên kết Douyin...")

        final_url, video_id = self.resolve_short_url(url)
        output_name = f"douyin_{task_id[:8]}"

        # Try direct extraction if video ID was found
        if video_id:
            try:
                if progress_callback:
                    progress_callback(15, f"Đang thử tải trực tiếp ID {video_id}...")
                return self.download_direct_douyin(final_url, video_id, output_name, progress_callback)
            except Exception as e:
                logger.info(f"Tải trực tiếp thất bại, chuyển sang yt-dlp: {e}")

        # Fallback to yt-dlp
        if progress_callback:
            progress_callback(20, "Đang tải video bằng yt-dlp adapter...")
        try:
            return self.download_with_ytdlp(final_url, output_name, progress_callback)
        except Exception as e:
            logger.error(f"yt-dlp tải thất bại: {e}")
            raise RuntimeError(
                f"Không thể tải video từ URL: {url}.\n"
                f"Nguyên nhân: Douyin có thể yêu cầu CAPTCHA, xác thực cookie hoặc đổi cấu trúc API.\n"
                f"Gợi ý: Hãy tải video về máy tính bằng trình duyệt và chọn file MP4 trực tiếp."
            ) from e
