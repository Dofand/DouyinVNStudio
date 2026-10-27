"""Unit tests for subtitle remover modes (VSR, FFmpeg blur, delogo, skip)."""

import subprocess
from pathlib import Path
import pytest

from config.settings import AppSettings
from core.subtitle_remover import SubtitleRemover


@pytest.fixture
def sample_video(tmp_path):
    settings = AppSettings.load()
    vid_path = tmp_path / "source.mp4"
    cmd = [
        settings.ffmpeg_path, "-y",
        "-f", "lavfi", "-i", "testsrc=duration=1:size=360x640:rate=24",
        "-c:v", "libx264", "-pix_fmt", "yuv420p",
        str(vid_path)
    ]
    subprocess.run(cmd, check=True, capture_output=True)
    return vid_path


def test_subtitle_remover_skip_mode(sample_video, tmp_path):
    settings = AppSettings.load()
    remover = SubtitleRemover(ffmpeg_path=settings.ffmpeg_path, ffprobe_path=settings.ffprobe_path)
    out_video = tmp_path / "out_skip.mp4"

    res = remover.remove_subtitles(
        input_video=sample_video,
        output_video=out_video,
        mode="skip"
    )
    assert res.exists()
    assert res.stat().st_size > 0


def test_subtitle_remover_delogo_mode(sample_video, tmp_path):
    settings = AppSettings.load()
    remover = SubtitleRemover(ffmpeg_path=settings.ffmpeg_path, ffprobe_path=settings.ffprobe_path)
    out_video = tmp_path / "out_delogo.mp4"

    res = remover.remove_subtitles(
        input_video=sample_video,
        output_video=out_video,
        mode="ffmpeg_delogo",
        area_coords=(500, 600, 20, 340)
    )
    assert res.exists()
    assert res.stat().st_size > 0


def test_subtitle_remover_blur_mode(sample_video, tmp_path):
    settings = AppSettings.load()
    remover = SubtitleRemover(ffmpeg_path=settings.ffmpeg_path, ffprobe_path=settings.ffprobe_path)
    out_video = tmp_path / "out_blur.mp4"

    res = remover.remove_subtitles(
        input_video=sample_video,
        output_video=out_video,
        mode="ffmpeg_blur",
        area_coords=(500, 600, 20, 340)
    )
    assert res.exists()
    assert res.stat().st_size > 0


def test_subtitle_remover_same_file_error(sample_video):
    settings = AppSettings.load()
    remover = SubtitleRemover(ffmpeg_path=settings.ffmpeg_path, ffprobe_path=settings.ffprobe_path)
    with pytest.raises(ValueError, match="không được trùng"):
        remover.remove_subtitles(input_video=sample_video, output_video=sample_video, mode="skip")
