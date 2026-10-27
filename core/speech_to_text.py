"""Speech-to-Text module using faster-whisper for Chinese audio transcription."""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger(__name__)


def patch_av_metadata_errors():
    """Ensure av.open safely handles metadata_errors kwarg across PyAV versions."""
    try:
        import av
        orig_open = av.open

        def safe_av_open(*args, **kwargs):
            try:
                return orig_open(*args, **kwargs)
            except TypeError as e:
                if "metadata_errors" in str(e):
                    kwargs.pop("metadata_errors", None)
                    return orig_open(*args, **kwargs)
                raise

        av.open = safe_av_open
    except Exception:
        pass


patch_av_metadata_errors()


def seconds_to_srt_time(seconds: float) -> str:
    """Convert float seconds to SRT timestamp format HH:MM:SS,mmm."""
    if seconds < 0:
        seconds = 0.0
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    millis = int(round((seconds - int(seconds)) * 1000))
    if millis >= 1000:
        secs += 1
        millis = 0
    return f"{hours:02d}:{minutes:02d}:{secs:02d},{millis:03d}"


def srt_time_to_seconds(time_str: str) -> float:
    """Convert SRT timestamp HH:MM:SS,mmm to float seconds."""
    time_str = time_str.strip().replace(".", ",")
    parts = time_str.split(":")
    if len(parts) == 3:
        h, m, rest = parts
        s, ms = rest.split(",") if "," in rest else (rest, "0")
        return int(h) * 3600 + int(m) * 60 + int(s) + int(ms) / 1000.0
    return 0.0


def export_srt(segments: List[Dict[str, Any]], output_path: str | Path, text_key: str = "text") -> Path:
    """Write list of segment dicts to an SRT file in UTF-8."""
    out_file = Path(output_path).resolve()
    out_file.parent.mkdir(parents=True, exist_ok=True)
    with open(out_file, "w", encoding="utf-8") as f:
        for idx, seg in enumerate(segments, start=1):
            start_str = seconds_to_srt_time(seg["start"])
            end_str = seconds_to_srt_time(seg["end"])
            text = seg.get(text_key, "").strip()
            f.write(f"{idx}\n{start_str} --> {end_str}\n{text}\n\n")
    return out_file


def find_cached_whisper_snapshot(model_size: str, download_root: Optional[str | Path]) -> Optional[str]:
    """Find local snapshot folder for faster-whisper model."""
    if not download_root:
        return None
    root_path = Path(download_root).resolve()
    repo_folder = f"models--Systran--faster-whisper-{model_size}"
    snapshots_dir = root_path / repo_folder / "snapshots"
    if snapshots_dir.exists() and snapshots_dir.is_dir():
        for snap in snapshots_dir.iterdir():
            if snap.is_dir() and (snap / "model.bin").exists():
                return str(snap)
    return None


class SpeechToTextEngine:
    """Wrapper for faster-whisper Chinese transcription."""

    def __init__(
        self,
        model_size: str = "base",
        device: str = "cpu",
        compute_type: str = "int8",
        download_root: Optional[str | Path] = None,
        mock_mode: bool = False,
    ):
        self.model_size = model_size
        self.device = device
        self.compute_type = compute_type
        self.download_root = str(download_root) if download_root else None
        self.mock_mode = mock_mode
        self._model = None

    def _load_model(self):
        """Lazy load Whisper model."""
        if self._model is not None:
            return self._model

        if self.mock_mode:
            logger.info("Chạy chế độ Whisper Mock (không nạp model nặng).")
            return None

        from faster_whisper import WhisperModel

        snapshot_path = find_cached_whisper_snapshot(self.model_size, self.download_root)
        model_target = snapshot_path or self.model_size
        logger.info(
            f"Nạp WhisperModel(model_size_or_path='{model_target}', device='{self.device}', compute_type='{self.compute_type}')..."
        )
        self._model = WhisperModel(
            model_target,
            device=self.device,
            compute_type=self.compute_type,
            download_root=self.download_root if not snapshot_path else None,
        )
        return self._model

    def transcribe(
        self,
        audio_or_video_path: str | Path,
        total_duration: float = 0.0,
        progress_callback: Optional[Callable[[int, str], None]] = None,
        is_cancelled: Optional[Callable[[], bool]] = None,
    ) -> List[Dict[str, Any]]:
        """
        Transcribe Chinese speech from video/audio file.
        Returns list of segments: [{"id": 1, "start": 0.0, "end": 2.5, "text": "你好"}]
        """
        input_file = Path(audio_or_video_path).resolve()
        if not input_file.exists():
            raise FileNotFoundError(f"File âm thanh/video không tồn tại: {input_file}")

        if progress_callback:
            progress_callback(5, "Đang chuẩn bị mô hình nhận dạng giọng nói...")

        if self.mock_mode:
            # Deterministic mock transcript based on duration
            dur = total_duration if total_duration > 0 else 6.0
            mock_segments = [
                {"id": 1, "start": 0.0, "end": min(2.0, dur), "text": "大家好，今天给大家分享一个非常实用的技巧。"},
                {"id": 2, "start": min(2.2, dur), "end": min(4.5, dur), "text": "如果觉得有用，请点赞收藏关注我。"},
                {"id": 3, "start": min(4.8, dur), "end": dur, "text": "我们下期视频再见！"},
            ]
            if progress_callback:
                progress_callback(100, "Hoàn tất nhận dạng lời thoại (Mock)!")
            return mock_segments

        model = self._load_model()

        if progress_callback:
            progress_callback(15, "Đang nhận dạng lời thoại tiếng Trung...")

        try:
            segments_iter, info = model.transcribe(
                str(input_file),
                language="zh",
                beam_size=5,
                vad_filter=True,
                vad_parameters=dict(min_silence_duration_ms=500),
            )
            first_seg = next(segments_iter, None)
        except Exception as e:
            logger.warning(f"Lỗi VAD filter ({e}). Tự động fallback sang vad_filter=False...")
            segments_iter, info = model.transcribe(
                str(input_file),
                language="zh",
                beam_size=5,
                vad_filter=False,
            )
            first_seg = next(segments_iter, None)

        effective_duration = total_duration or getattr(info, "duration", 0.0) or 1.0
        results: List[Dict[str, Any]] = []

        all_segments = []
        if first_seg is not None:
            all_segments.append(first_seg)

        for seg in all_segments:
            text = seg.text.strip()
            if text:
                results.append({
                    "id": 1,
                    "start": round(seg.start, 3),
                    "end": round(seg.end, 3),
                    "text": text,
                })

        for idx, segment in enumerate(segments_iter, start=len(results) + 1):
            if is_cancelled and is_cancelled():
                logger.info("Nhận dạng lời thoại bị hủy bởi người dùng.")
                break

            text = segment.text.strip()
            if text:
                results.append({
                    "id": idx,
                    "start": round(segment.start, 3),
                    "end": round(segment.end, 3),
                    "text": text,
                })

            if progress_callback and effective_duration > 0:
                pct = min(95, int(15 + (segment.end / effective_duration) * 80))
                progress_callback(pct, f"Đang nhận dạng ({round(segment.end, 1)}s / {round(effective_duration, 1)}s): {text[:20]}...")

        if progress_callback:
            progress_callback(100, f"Đã nhận dạng {len(results)} câu thoại tiếng Trung.")

        return results
