"""OCR module for extracting on-screen Chinese subtitles when speech is absent or hardcoded."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


class OCRSubtitleExtractor:
    """Extracts on-screen subtitles and titles using RapidOCR."""

    def __init__(self, use_gpu: bool = False):
        self.use_gpu = use_gpu
        self._engine = None

    def is_ocr_available(self) -> bool:
        """Check if RapidOCR is installed and available."""
        try:
            import rapidocr_onnxruntime  # type: ignore
            return True
        except ImportError:
            return False

    def _get_engine(self):
        """Lazy load RapidOCR engine with automatic config resolution and fallback."""
        if self._engine is None and self.is_ocr_available():
            try:
                from rapidocr_onnxruntime import RapidOCR  # type: ignore
                self._engine = RapidOCR()
            except Exception as e:
                logger.warning(f"Lỗi khởi tạo RapidOCR mặc định: {e}. Đang tìm nạp cấu hình dự phòng...")
                try:
                    import sys
                    from pathlib import Path
                    from rapidocr_onnxruntime import RapidOCR  # type: ignore
                    candidates = [
                        Path(sys.executable).parent / "_internal" / "rapidocr_onnxruntime" / "config.yaml",
                        Path(__file__).parent.parent / "dist" / "DouyinVNStudio" / "_internal" / "rapidocr_onnxruntime" / "config.yaml",
                        Path(__file__).parent.parent / ".venv" / "Lib" / "site-packages" / "rapidocr_onnxruntime" / "config.yaml",
                    ]
                    for cfg in candidates:
                        if cfg.exists():
                            self._engine = RapidOCR(config_path=str(cfg))
                            logger.info(f"Đã nạp RapidOCR thành công từ cấu hình: {cfg}")
                            break
                except Exception as inner_e:
                    logger.error(f"Khởi tạo RapidOCR thất bại: {inner_e}")
                    self._engine = None
        return self._engine

    def extract_subtitles_from_video(
        self,
        video_path: str | Path,
        sample_step_sec: float = 2.0,
        area_ratio: Optional[Tuple[float, float, float, float]] = None,
        progress_callback: Optional[Callable[[int, str], None]] = None,
        is_cancelled: Optional[Callable[[], bool]] = None,
    ) -> List[Dict[str, Any]]:
        """
        Extract on-screen subtitles by sampling video frames.
        Returns list of segments: [{"id": 1, "start": 6.0, "end": 60.0, "text": "..."}]
        """
        engine = self._get_engine()
        if engine is None:
            logger.info("RapidOCR chưa khả dụng, bỏ qua trích xuất OCR.")
            return []

        import cv2

        in_p = Path(video_path).resolve()
        if not in_p.exists():
            return []

        cap = cv2.VideoCapture(str(in_p))
        if not cap.isOpened():
            return []

        fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        duration = total_frames / fps
        width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))

        if duration <= 0:
            cap.release()
            return []

        if progress_callback:
            progress_callback(10, f"Đang quét nhận dạng chữ trên màn hình ({int(duration)}s)...")

        # Sample timestamps
        step = max(1.0, float(sample_step_sec))
        timestamps = []
        cur_t = 0.0
        while cur_t < duration:
            timestamps.append(cur_t)
            cur_t += step

        # Track on-screen text over time
        sampled_records = []  # list of (timestamp, text)
        total_samples = len(timestamps)

        try:
            for idx, t in enumerate(timestamps):
                if is_cancelled and is_cancelled():
                    break

                cap.set(cv2.CAP_PROP_POS_MSEC, t * 1000.0)
                ret, frame = cap.read()
                if not ret or frame is None:
                    continue

                res, _ = engine(frame)
                frame_text = ""
                if res:
                    # Filter candidates: prioritize prominent subtitle/title lines
                    valid_lines = []
                    for line in res:
                        box, txt, score = line[0], str(line[1]).strip(), float(line[2])
                        if not txt or len(txt) < 2 or score < 0.60:
                            continue
                        ys = [p[1] for p in box]
                        y_center = (sum(ys) / len(ys)) / height

                        # If area_ratio specified, filter strictly
                        if area_ratio:
                            ymin_r, ymax_r, xmin_r, xmax_r = area_ratio
                            xs = [p[0] for p in box]
                            x_center = (sum(xs) / len(xs)) / width
                            if ymin_r <= y_center <= ymax_r and xmin_r <= x_center <= xmax_r:
                                valid_lines.append((score, txt))
                        else:
                            # Prioritize subtitle zones (top banner: < 0.25 or bottom subtitles: > 0.65)
                            if y_center < 0.25 or y_center > 0.65 or (0.42 <= y_center <= 0.58):
                                valid_lines.append((score, txt))

                    if valid_lines:
                        # Pick highest score line or join
                        valid_lines.sort(key=lambda x: x[0], reverse=True)
                        frame_text = valid_lines[0][1]

                sampled_records.append((t, frame_text))

                if progress_callback and (idx % 5 == 0 or idx == total_samples - 1):
                    pct = int(10 + (idx / total_samples) * 80)
                    progress_callback(pct, f"Đang trích xuất chữ OCR: {idx}/{total_samples} khung hình...")
        finally:
            cap.release()

        # Merge contiguous frames with same text into segments
        raw_segments: List[Dict[str, Any]] = []
        current_text = ""
        current_start = 0.0

        for t, txt in sampled_records:
            if txt != current_text:
                if current_text:
                    raw_segments.append({
                        "text": current_text,
                        "start": current_start,
                        "end": t,
                    })
                current_text = txt
                current_start = t

        if current_text:
            raw_segments.append({
                "text": current_text,
                "start": current_start,
                "end": duration,
            })

        # Post-filter: remove blips lasting less than 1.5 seconds
        final_segments = []
        seg_id = 1
        for seg in raw_segments:
            dur_seg = seg["end"] - seg["start"]
            if dur_seg >= 1.5 and seg["text"]:
                final_segments.append({
                    "id": seg_id,
                    "start": round(seg["start"], 2),
                    "end": round(seg["end"], 2),
                    "text": seg["text"],
                })
                seg_id += 1

        if progress_callback:
            progress_callback(100, f"Hoàn tất quét OCR: tìm thấy {len(final_segments)} đoạn phụ đề chữ.")

        return final_segments

    @staticmethod
    def merge_with_whisper_subtitles(
        whisper_subs: List[Dict[str, Any]],
        ocr_subs: List[Dict[str, Any]],
        time_threshold_sec: float = 1.0,
    ) -> List[Dict[str, Any]]:
        """
        Merge Whisper speech subtitles with OCR subtitles, deduplicating overlapping segments.
        Whisper transcript is given higher priority for speech audio.
        """
        if not ocr_subs:
            return whisper_subs
        if not whisper_subs:
            return ocr_subs

        combined = list(whisper_subs)
        for ocr_item in ocr_subs:
            o_start = ocr_item["start"]
            o_end = ocr_item["end"]
            o_text = ocr_item["text"].strip()

            overlaps = False
            for w in whisper_subs:
                w_start = w["start"]
                w_end = w["end"]
                if max(o_start, w_start) <= min(o_end, w_end):
                    overlaps = True
                    break

            if not overlaps and o_text:
                combined.append(ocr_item)

        combined.sort(key=lambda x: x["start"])
        for idx, item in enumerate(combined, start=1):
            item["id"] = idx
        return combined
