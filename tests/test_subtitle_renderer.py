"""Unit tests for subtitle renderer, path escaping, and FFmpeg burning."""

import subprocess
from pathlib import Path
import pytest

from config.settings import AppSettings, SubtitleStyle
from core.speech_to_text import export_srt
from core.subtitle_renderer import SubtitleRenderer, escape_ffmpeg_filter_path, parse_ffmpeg_time


def test_escape_ffmpeg_filter_path():
    path_win = r"C:\Users\Admin\Desktop\Test Sub.srt"
    escaped = escape_ffmpeg_filter_path(path_win)
    assert "\\:" in escaped
    assert "\\" not in escaped.replace("\\:", "")


def test_parse_ffmpeg_time():
    assert parse_ffmpeg_time("00:01:23.45") == 83.45
    assert parse_ffmpeg_time("00:00:05.00") == 5.0
    assert parse_ffmpeg_time("invalid") == 0.0


def test_subtitle_render_vietnamese_text(tmp_path):
    settings = AppSettings.load()
    renderer = SubtitleRenderer(settings.ffmpeg_path, settings.ffprobe_path)

    # Path with spaces and Vietnamese characters in folder name!
    special_folder = tmp_path / "Thư Mục Video 2026"
    special_folder.mkdir(parents=True, exist_ok=True)

    vid_path = special_folder / "test_source.mp4"
    cmd = [
        settings.ffmpeg_path, "-y",
        "-f", "lavfi", "-i", "testsrc=duration=1:size=480x854:rate=24",
        "-f", "lavfi", "-i", "sine=frequency=800:duration=1",
        "-c:v", "libx264", "-pix_fmt", "yuv420p",
        "-c:a", "aac",
        str(vid_path)
    ]
    subprocess.run(cmd, check=True, capture_output=True)

    srt_path = special_folder / "phụ đề việt.srt"
    segments = [
        {"id": 1, "start": 0.1, "end": 0.9, "text": "Đây là kiểm thử tiếng Việt có dấu: Đ, ư, ơ, ắ, ễ."}
    ]
    export_srt(segments, srt_path)

    out_video = special_folder / "thành phẩm vi.mp4"
    rendered = renderer.render(
        video_input=vid_path,
        srt_input=srt_path,
        video_output=out_video,
        style=SubtitleStyle(font_size=20, font_name="Segoe UI")
    )

    assert rendered.exists()
    assert rendered.stat().st_size > 0
    # Probe output to confirm audio and video streams intact
    info = renderer.media_probe.probe(rendered)
    assert info.has_video is True
    assert info.has_audio is True
    assert info.duration >= 0.9
