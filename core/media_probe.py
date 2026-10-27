"""Media probe utility using ffprobe and ffmpeg for video inspection."""

from __future__ import annotations

import json
import logging
import os
import shutil
import subprocess
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

from pydantic import BaseModel

logger = logging.getLogger(__name__)


class MediaInfo(BaseModel):
    """Structured media information extracted via ffprobe."""
    file_path: str
    file_size_bytes: int
    duration: float
    format_name: str
    bitrate: int

    # Video stream info
    has_video: bool = False
    video_codec: str = ""
    width: int = 0
    height: int = 0
    aspect_ratio: str = ""
    is_vertical: bool = False  # e.g. 9:16 for Douyin / TikTok
    fps: float = 0.0
    pixel_format: str = ""

    # Audio stream info
    has_audio: bool = False
    audio_codec: str = ""
    channels: int = 0
    sample_rate: int = 0


class MediaProbe:
    """Wrapper around ffprobe to inspect and validate media files."""

    def __init__(self, ffprobe_path: str = "ffprobe", ffmpeg_path: str = "ffmpeg"):
        self.ffprobe_path = ffprobe_path or "ffprobe"
        self.ffmpeg_path = ffmpeg_path or "ffmpeg"

    def probe(self, file_path: str | Path) -> MediaInfo:
        """Run ffprobe on the given file and parse stream information."""
        p = Path(file_path).resolve()
        if not p.exists():
            raise FileNotFoundError(f"File không tồn tại: {p}")
        if p.stat().st_size == 0:
            raise ValueError(f"File video rỗng (0 bytes): {p}")

        cmd = [
            self.ffprobe_path,
            "-v", "error",
            "-show_format",
            "-show_streams",
            "-of", "json",
            str(p)
        ]

        try:
            res = subprocess.run(cmd, capture_output=True, text=True, check=True, encoding="utf-8", errors="replace")
            data = json.loads(res.stdout)
        except subprocess.CalledProcessError as e:
            raise RuntimeError(f"Lỗi khi chạy ffprobe trên {p}: {e.stderr}") from e
        except Exception as e:
            raise RuntimeError(f"Không thể đọc thông tin video: {e}") from e

        fmt = data.get("format", {})
        streams = data.get("streams", [])

        duration = float(fmt.get("duration", 0.0) or 0.0)
        file_size = int(fmt.get("size", p.stat().st_size) or p.stat().st_size)
        bitrate = int(fmt.get("bit_rate", 0) or 0)
        format_name = fmt.get("format_name", "")

        has_video = False
        video_codec = ""
        width = 0
        height = 0
        fps = 0.0
        pixel_format = ""
        aspect_ratio = ""

        has_audio = False
        audio_codec = ""
        channels = 0
        sample_rate = 0

        for st in streams:
            codec_type = st.get("codec_type")
            if codec_type == "video" and not has_video:
                has_video = True
                video_codec = st.get("codec_name", "")
                width = int(st.get("width", 0) or 0)
                height = int(st.get("height", 0) or 0)
                pixel_format = st.get("pix_fmt", "")

                # Calculate FPS
                r_frame_rate = st.get("r_frame_rate", "0/1")
                if "/" in r_frame_rate:
                    num, den = r_frame_rate.split("/")
                    fps = round(float(num) / float(den), 2) if float(den) > 0 else 0.0
                else:
                    fps = float(r_frame_rate or 0.0)

                # Duration fallback from stream if format duration is 0
                if duration == 0.0 and "duration" in st:
                    duration = float(st.get("duration", 0.0) or 0.0)

            elif codec_type == "audio" and not has_audio:
                has_audio = True
                audio_codec = st.get("codec_name", "")
                channels = int(st.get("channels", 0) or 0)
                sample_rate = int(st.get("sample_rate", 0) or 0)

        # Aspect ratio
        if width > 0 and height > 0:
            aspect_ratio = f"{width}:{height}"
            is_vertical = height > width
        else:
            is_vertical = False

        return MediaInfo(
            file_path=str(p),
            file_size_bytes=file_size,
            duration=duration,
            format_name=format_name,
            bitrate=bitrate,
            has_video=has_video,
            video_codec=video_codec,
            width=width,
            height=height,
            aspect_ratio=aspect_ratio,
            is_vertical=is_vertical,
            fps=fps,
            pixel_format=pixel_format,
            has_audio=has_audio,
            audio_codec=audio_codec,
            channels=channels,
            sample_rate=sample_rate,
        )

    def check_free_space(self, target_dir: str | Path, required_bytes: int = 500 * 1024 * 1024) -> Tuple[bool, int]:
        """Check if target drive has sufficient free space (default 500MB)."""
        target = Path(target_dir).resolve()
        while not target.exists() and target.parent != target:
            target = target.parent
        usage = shutil.disk_usage(str(target))
        return usage.free >= required_bytes, usage.free

    def validate_video_integrity(self, file_path: str | Path) -> bool:
        """Lightweight verification that video decode stream can be parsed without critical failure."""
        cmd = [
            self.ffmpeg_path,
            "-v", "error",
            "-i", str(file_path),
            "-t", "10",  # Test first 10 seconds
            "-f", "null",
            "-"
        ]
        try:
            res = subprocess.run(cmd, capture_output=True, text=True, check=False)
            return res.returncode == 0
        except Exception:
            return False

    def extract_thumbnail(self, file_path: str | Path, output_image_path: str | Path, time_sec: float = 1.0) -> bool:
        """Extract a single frame image for UI preview."""
        out_path = Path(output_image_path).resolve()
        out_path.parent.mkdir(parents=True, exist_ok=True)
        cmd = [
            self.ffmpeg_path,
            "-y",
            "-ss", str(time_sec),
            "-i", str(file_path),
            "-vframes", "1",
            "-q:v", "2",
            str(out_path)
        ]
        try:
            res = subprocess.run(cmd, capture_output=True, text=True, check=False)
            return res.returncode == 0 and out_path.exists() and out_path.stat().st_size > 0
        except Exception:
            return False
