"""Subtitle rendering module using FFmpeg to burn styled Vietnamese subtitles onto video."""

from __future__ import annotations

import logging
import os
import re
import subprocess
from pathlib import Path
from typing import Callable, Optional

from config.settings import SubtitleStyle
from core.media_probe import MediaProbe

logger = logging.getLogger(__name__)


def escape_ffmpeg_filter_path(file_path: str | Path) -> str:
    """
    Format Windows path safely for FFmpeg filtergraph:
    Convert backslashes to forward slashes, and escape drive colon: C:/ -> C\\:/
    """
    p = str(Path(file_path).resolve()).replace("\\", "/")
    # Escape colon after drive letter: e.g. C:/ -> C\\:/
    if len(p) >= 2 and p[1] == ":":
        p = p[0] + "\\:" + p[2:]
    return p


def parse_ffmpeg_time(time_str: str) -> float:
    """Parse FFmpeg progress timestamp HH:MM:SS.micro to seconds."""
    try:
        parts = time_str.strip().split(":")
        if len(parts) == 3:
            return float(parts[0]) * 3600 + float(parts[1]) * 60 + float(parts[2])
    except Exception:
        pass
    return 0.0


class SubtitleRenderer:
    """Burns subtitles directly into video using FFmpeg."""

    def __init__(self, ffmpeg_path: str = "ffmpeg", ffprobe_path: str = "ffprobe"):
        self.ffmpeg_path = ffmpeg_path or "ffmpeg"
        self.ffprobe_path = ffprobe_path or "ffprobe"
        self.media_probe = MediaProbe(self.ffprobe_path, self.ffmpeg_path)

    def generate_force_style(self, style: SubtitleStyle, video_height: int = 1080) -> str:
        """Generate ASS force_style string with dynamic scaling."""
        # Scale font size slightly if video resolution is different from 1080p
        scale_factor = max(0.5, min(2.5, video_height / 1080.0))
        effective_font_size = int(style.font_size * scale_factor)
        effective_margin_v = int(style.margin_v * scale_factor)
        effective_outline = round(style.outline_width * scale_factor, 1)

        bold_val = 1 if style.bold else 0
        italic_val = 1 if style.italic else 0

        force_style = (
            f"FontName={style.font_name},"
            f"FontSize={effective_font_size},"
            f"PrimaryColour={style.primary_color},"
            f"OutlineColour={style.outline_color},"
            f"BackColour={style.back_color},"
            f"Outline={effective_outline},"
            f"Shadow=1,"
            f"Bold={bold_val},"
            f"Italic={italic_val},"
            f"Alignment={style.alignment},"
            f"MarginV={effective_margin_v},"
            f"MarginL={style.margin_l},"
            f"MarginR={style.margin_r}"
        )
        return force_style

    def render(
        self,
        video_input: str | Path,
        srt_input: str | Path,
        video_output: str | Path,
        style: Optional[SubtitleStyle] = None,
        crf: int = 18,
        preset: str = "medium",
        progress_callback: Optional[Callable[[int, str], None]] = None,
        is_cancelled: Optional[Callable[[], bool]] = None,
    ) -> Path:
        """
        Burn SRT subtitles onto input video and produce final MP4.
        Keeps original audio stream without re-encoding when possible.
        """
        in_vid = Path(video_input).resolve()
        in_srt = Path(srt_input).resolve()
        out_vid = Path(video_output).resolve()
        out_vid.parent.mkdir(parents=True, exist_ok=True)

        if not in_vid.exists():
            raise FileNotFoundError(f"Video nguồn không tồn tại: {in_vid}")

        media_info = self.media_probe.probe(in_vid)
        duration = media_info.duration or 1.0
        height = media_info.height or 1080

        # Check if SRT has valid subtitles. If not (e.g. video has no speech), produce clean output safely
        has_subtitles = False
        if in_srt.exists() and in_srt.stat().st_size > 0:
            try:
                content = in_srt.read_text(encoding="utf-8", errors="replace").strip()
                has_subtitles = "-->" in content
            except Exception:
                has_subtitles = False

        if not has_subtitles:
            logger.info("Không có phụ đề lời thoại cần ghi vào video. Xuất trực tiếp video đã xóa chữ.")
            if progress_callback:
                progress_callback(20, "Không có phụ đề lời thoại. Đang hoàn thiện video...")

            cmd = [
                self.ffmpeg_path,
                "-y",
                "-i", str(in_vid),
                "-c:v", "libx264",
                "-preset", preset,
                "-crf", str(crf),
                "-pix_fmt", "yuv420p",
            ]
            if media_info.has_audio:
                cmd.extend(["-c:a", "aac", "-b:a", "192k"])
            else:
                cmd.extend(["-an"])
            cmd.extend(["-movflags", "+faststart", str(out_vid)])
            subprocess.run(cmd, check=True, capture_output=True)
            if progress_callback:
                progress_callback(100, "Hoàn tất tạo video thành phẩm.")
            return out_vid

        subtitle_style = style or SubtitleStyle()
        force_style_str = self.generate_force_style(subtitle_style, video_height=height)
        escaped_srt = escape_ffmpeg_filter_path(in_srt)

        # Subtitles filter syntax
        vf_filter = f"subtitles='{escaped_srt}':force_style='{force_style_str}'"

        # Construct FFmpeg command
        cmd = [
            self.ffmpeg_path,
            "-y",
            "-i", str(in_vid),
            "-vf", vf_filter,
            "-c:v", "libx264",
            "-preset", preset,
            "-crf", str(crf),
            "-pix_fmt", "yuv420p",
        ]

        if media_info.has_audio:
            # Encode to standard high-compatibility AAC-LC (192kbps) for universal Windows & player support
            cmd.extend(["-c:a", "aac", "-b:a", "192k"])
        else:
            cmd.extend(["-an"])

        # Faststart allows immediate playback in Windows players and web browsers
        cmd.extend(["-movflags", "+faststart"])
        cmd.append(str(out_vid))

        logger.info(f"Chạy FFmpeg render: {' '.join(cmd)}")
        if progress_callback:
            progress_callback(5, "Bắt đầu ghi phụ đề vào video bằng FFmpeg...")

        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            errors="replace",
        )

        time_regex = re.compile(r"time=(\d+:\d+:\d+\.\d+)")

        try:
            while True:
                if is_cancelled and is_cancelled():
                    process.terminate()
                    raise RuntimeError("Quá trình xuất video bị hủy bởi người dùng.")

                line = process.stderr.readline()
                if not line and process.poll() is not None:
                    break

                if line:
                    match = time_regex.search(line)
                    if match and progress_callback and duration > 0:
                        cur_sec = parse_ffmpeg_time(match.group(1))
                        pct = min(98, max(5, int((cur_sec / duration) * 100)))
                        progress_callback(pct, f"Đang xuất video: {pct}% ({round(cur_sec, 1)}s / {round(duration, 1)}s)")

            ret = process.poll()
            if ret != 0:
                err_text = process.stderr.read()
                raise RuntimeError(f"FFmpeg render thất bại (mã {ret}): {err_text[-500:]}")
        finally:
            if process.poll() is None:
                process.kill()

        # Validate result
        if not out_vid.exists() or out_vid.stat().st_size == 0:
            raise RuntimeError(f"File video kết quả không tồn tại hoặc bị rỗng: {out_vid}")

        out_probe = self.media_probe.probe(out_vid)
        if not out_probe.has_video:
            raise RuntimeError(f"File video kết quả bị lỗi codec/stream: {out_vid}")

        if progress_callback:
            progress_callback(100, "Xuất video MP4 có phụ đề thành công!")

        return out_vid
