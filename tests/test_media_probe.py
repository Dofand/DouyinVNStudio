"""Unit tests for media probe and file validation."""

import os
import subprocess
import tempfile
from pathlib import Path
import pytest

from config.settings import AppSettings
from core.media_probe import MediaInfo, MediaProbe


@pytest.fixture
def media_probe():
    settings = AppSettings.load()
    return MediaProbe(settings.ffprobe_path, settings.ffmpeg_path)


@pytest.fixture
def sample_video(tmp_path, media_probe):
    """Generate a valid 2-second vertical MP4 test video with audio."""
    vid_path = tmp_path / "sample_vertical.mp4"
    cmd = [
        media_probe.ffmpeg_path, "-y",
        "-f", "lavfi", "-i", "testsrc=duration=2:size=720x1280:rate=25",
        "-f", "lavfi", "-i", "sine=frequency=1000:duration=2",
        "-c:v", "libx264", "-pix_fmt", "yuv420p",
        "-c:a", "aac",
        str(vid_path)
    ]
    subprocess.run(cmd, check=True, capture_output=True)
    return vid_path


def test_media_probe_valid_video(media_probe, sample_video):
    info = media_probe.probe(sample_video)
    assert isinstance(info, MediaInfo)
    assert info.has_video is True
    assert info.width == 720
    assert info.height == 1280
    assert info.is_vertical is True
    assert info.has_audio is True
    assert info.duration >= 1.9
    assert info.fps == 25.0


def test_media_probe_nonexistent_file(media_probe, tmp_path):
    with pytest.raises(FileNotFoundError):
        media_probe.probe(tmp_path / "does_not_exist.mp4")


def test_media_probe_empty_file(media_probe, tmp_path):
    empty_file = tmp_path / "empty.mp4"
    empty_file.write_bytes(b"")
    with pytest.raises(ValueError, match="0 bytes"):
        media_probe.probe(empty_file)


def test_media_probe_corrupted_file(media_probe, tmp_path):
    corrupt_file = tmp_path / "corrupt.mp4"
    corrupt_file.write_bytes(b"NOT_A_VALID_MP4_HEADER_DATA_123456789")
    with pytest.raises(RuntimeError):
        media_probe.probe(corrupt_file)


def test_check_free_space(media_probe, tmp_path):
    has_space, free_bytes = media_probe.check_free_space(tmp_path, required_bytes=1024)
    assert has_space is True
    assert free_bytes > 0


def test_extract_thumbnail(media_probe, sample_video, tmp_path):
    thumb_path = tmp_path / "thumb.jpg"
    ok = media_probe.extract_thumbnail(sample_video, thumb_path, time_sec=0.5)
    assert ok is True
    assert thumb_path.exists()
    assert thumb_path.stat().st_size > 0
