"""Unit tests for speech-to-text formatting, SRT export, and transcription."""

from pathlib import Path
import pytest

from core.speech_to_text import (
    SpeechToTextEngine,
    export_srt,
    seconds_to_srt_time,
    srt_time_to_seconds,
)


def test_seconds_to_srt_time():
    assert seconds_to_srt_time(0.0) == "00:00:00,000"
    assert seconds_to_srt_time(65.123) == "00:01:05,123"
    assert seconds_to_srt_time(3661.050) == "01:01:01,050"


def test_srt_time_to_seconds():
    assert srt_time_to_seconds("00:00:00,000") == 0.0
    assert abs(srt_time_to_seconds("00:01:05,123") - 65.123) < 0.001
    assert abs(srt_time_to_seconds("01:01:01,050") - 3661.050) < 0.001


def test_export_srt(tmp_path):
    segments = [
        {"id": 1, "start": 0.5, "end": 2.5, "text": "你好世界"},
        {"id": 2, "start": 3.0, "end": 5.0, "text": "欢迎来到中国"},
    ]
    out_file = tmp_path / "test.srt"
    export_srt(segments, out_file)

    assert out_file.exists()
    content = out_file.read_text(encoding="utf-8")
    assert "00:00:00,500 --> 00:00:02,500" in content
    assert "你好世界" in content
    assert "00:00:03,000 --> 00:00:05,000" in content
    assert "欢迎来到中国" in content


def test_speech_to_text_mock_mode(tmp_path):
    dummy_file = tmp_path / "dummy.mp4"
    dummy_file.write_bytes(b"dummy")

    engine = SpeechToTextEngine(mock_mode=True)
    results = engine.transcribe(dummy_file, total_duration=5.0)

    assert len(results) == 3
    assert results[0]["id"] == 1
    assert "text" in results[0]
    assert results[0]["start"] == 0.0
    assert results[0]["end"] <= 5.0
