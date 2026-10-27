"""Subtitle removal module supporting dynamic timeline text detection, multi-interval delogo, and video sharpness restoration."""

from __future__ import annotations

import logging
import os
import shutil
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, List, Optional, Tuple

from core.media_probe import MediaProbe

logger = logging.getLogger(__name__)


def _sanitize_box(x: int, y: int, w: int, h: int, max_w: int, max_h: int) -> Tuple[int, int, int, int]:
    """
    Ensure coordinates and dimensions strictly satisfy FFmpeg delogo band requirements:
    FFmpeg delogo requires at least a 2-pixel band of background pixels on all sides:
    - x >= 2
    - y >= 2
    - x + w <= max_w - 2
    - y + h <= max_h - 2
    - w and h are even positive integers >= 4
    """
    x = max(2, min(x, max_w - 8))
    y = max(2, min(y, max_h - 8))
    w = max(4, min(w, max_w - x - 4))
    h = max(4, min(h, max_h - y - 4))
    if w % 2 != 0:
        w -= 1
    if h % 2 != 0:
        h -= 1
    return (x, y, max(4, w), max(4, h))


@dataclass
class TextInterval:
    """Represents a spatiotemporal text appearance in the video."""
    start_sec: float
    end_sec: float
    x: int
    y: int
    w: int
    h: int
    texts: List[str] = field(default_factory=list)


class SubtitleRemover:
    """Manages subtitle and hardcoded text removal using dynamic timeline detection, multi-interval FFmpeg delogo, and sharpness enhancement."""

    def __init__(
        self,
        vsr_path: str = "",
        ffmpeg_path: str = "ffmpeg",
        ffprobe_path: str = "ffprobe",
        inpaint_mode: str = "sttn-auto",
    ):
        self.vsr_path = vsr_path
        self.ffmpeg_path = ffmpeg_path or "ffmpeg"
        self.ffprobe_path = ffprobe_path or "ffprobe"
        self.inpaint_mode = inpaint_mode
        self.media_probe = MediaProbe(self.ffprobe_path, self.ffmpeg_path)

    def is_vsr_available(self) -> bool:
        """Check if VSR is configured and found on system."""
        if not self.vsr_path:
            return False
        p = Path(self.vsr_path)
        if p.is_file() and p.name.lower().endswith(".exe"):
            return True
        if p.is_dir() and (p / "backend" / "main.py").exists():
            return True
        return False

    def detect_text_timeline(
        self,
        video_path: Path,
        duration: float,
        width: int,
        height: int,
        step_sec: float = 1.0,
        progress_callback: Optional[Callable[[int, str], None]] = None,
        is_cancelled: Optional[Callable[[], bool]] = None,
    ) -> List[TextInterval]:
        """
        Scan video across the timeline with RapidOCR, clustering text into spatiotemporal intervals.
        Detects top banners, middle title cards, bottom subtitles, and any dynamic annotations.
        """
        intervals: List[TextInterval] = []

        try:
            from rapidocr_onnxruntime import RapidOCR  # type: ignore
            import cv2
            try:
                engine = RapidOCR()
            except Exception as e:
                logger.warning(f"Lỗi khởi tạo RapidOCR mặc định trong subtitle_remover: {e}. Thử tìm cấu hình...")
                import sys
                from pathlib import Path
                engine = None
                candidates = [
                    Path(sys.executable).parent / "_internal" / "rapidocr_onnxruntime" / "config.yaml",
                    Path(__file__).parent.parent / "dist" / "DouyinVNStudio" / "_internal" / "rapidocr_onnxruntime" / "config.yaml",
                    Path(__file__).parent.parent / ".venv" / "Lib" / "site-packages" / "rapidocr_onnxruntime" / "config.yaml",
                ]
                for cfg in candidates:
                    if cfg.exists():
                        try:
                            engine = RapidOCR(config_path=str(cfg))
                            break
                        except Exception:
                            continue
                if engine is None:
                    raise RuntimeError("Không thể nạp bất kỳ cấu hình RapidOCR hợp lệ nào.")
        except Exception as e:
            logger.warning(f"Không thể tải RapidOCR hoặc OpenCV ({e}). Dùng vùng mặc định.")
            # Fallback: full top and bottom default
            intervals.append(TextInterval(0.0, duration, int(width * 0.1), int(height * 0.06), int(width * 0.8), int(height * 0.10)))
            intervals.append(TextInterval(0.0, duration, int(width * 0.05), int(height * 0.72), int(width * 0.9), int(height * 0.20)))
            return intervals
        cap = cv2.VideoCapture(str(video_path))
        fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
        cur_s = 0.0
        sample_times = []
        while cur_s < duration:
            sample_times.append(cur_s)
            cur_s += step_sec

        total_steps = max(1, len(sample_times))
        logger.info(f"Bắt đầu quét timeline phụ đề video ({total_steps} mẫu, bước {step_sec}s)...")

        for idx, s in enumerate(sample_times):
            if is_cancelled and is_cancelled():
                cap.release()
                raise RuntimeError("Hủy tác vụ quét chữ bởi người dùng.")

            if progress_callback:
                pct = int((idx / total_steps) * 40)
                progress_callback(pct, f"Đang quét nhận diện chữ trên toàn video ({int(s)}s / {int(duration)}s)...")

            cap.set(cv2.CAP_PROP_POS_MSEC, s * 1000.0)
            ret, frame = cap.read()
            if not ret or frame is None:
                continue

            res, _ = engine(frame)
            if not res:
                continue

            for item in res:
                box = item[0]
                txt = item[1]
                conf = float(item[2])
                if conf < 0.60:
                    continue

                xs = [p[0] for p in box]
                ys = [p[1] for p in box]
                xmin, xmax = int(min(xs)), int(max(xs))
                ymin, ymax = int(min(ys)), int(max(ys))

                # Discard tiny single-noise artifacts
                if (xmax - xmin) < 20 or (ymax - ymin) < 12:
                    continue

                # Add padding margin so text strokes are never clipped
                pad_x = 12
                pad_y = 8
                xmin = max(0, xmin - pad_x)
                xmax = min(width, xmax + pad_x)
                ymin = max(0, ymin - pad_y)
                ymax = min(height, ymax + pad_y)

                # Match with existing active interval
                matched = False
                for inv in intervals:
                    # Within 3.5 seconds and vertical overlap or very close center
                    time_diff = abs(s - inv.end_sec)
                    inv_cen_y = inv.y + inv.h / 2.0
                    y_diff = abs((ymin + ymax) / 2.0 - inv_cen_y) / height
                    if time_diff <= 3.5 and y_diff < 0.08:
                        inv.end_sec = min(duration, s + step_sec + 0.5)
                        new_x = min(inv.x, xmin)
                        new_y = min(inv.y, ymin)
                        new_xmax = max(inv.x + inv.w, xmax)
                        new_ymax = max(inv.y + inv.h, ymax)
                        inv.x = new_x
                        inv.y = new_y
                        inv.w = new_xmax - new_x
                        inv.h = new_ymax - new_y
                        inv.texts.append(txt)
                        matched = True
                        break

                if not matched:
                    intervals.append(TextInterval(
                        start_sec=max(0.0, s - 0.5),
                        end_sec=min(duration, s + step_sec + 0.5),
                        x=xmin,
                        y=ymin,
                        w=xmax - xmin,
                        h=ymax - ymin,
                        texts=[txt],
                    ))

        cap.release()

        # Sanitize all intervals and calculate w, h
        clean_intervals: List[TextInterval] = []
        for inv in intervals:
            x, y, w, h = _sanitize_box(inv.x, inv.y, inv.w, inv.h, width, height)
            inv.x = x
            inv.y = y
            inv.w = w
            inv.h = h
            clean_intervals.append(inv)

        logger.info(f"Hoàn tất quét timeline: Phát hiện {len(clean_intervals)} phân đoạn xuất hiện chữ.")
        return clean_intervals

    def remove_subtitles(
        self,
        input_video: str | Path,
        output_video: str | Path,
        mode: str = "ffmpeg_delogo",
        zone_mode: str = "auto",
        area_coords: Optional[Tuple[int, int, int, int]] = None,
        area_ratio: Optional[Tuple[float, float, float, float]] = None,
        progress_callback: Optional[Callable[[int, str], None]] = None,
        is_cancelled: Optional[Callable[[], bool]] = None,
    ) -> Path:
        """
        Execute intelligent subtitle removal.
        Outputs clean, sharp video without hardcoded Chinese text.
        """
        in_p = Path(input_video).resolve()
        out_p = Path(output_video).resolve()
        out_p.parent.mkdir(parents=True, exist_ok=True)

        if not in_p.exists():
            raise FileNotFoundError(f"Video đầu vào không tồn tại: {in_p}")

        if in_p == out_p:
            raise ValueError("File đầu ra không được trùng với file video gốc.")

        media_info = self.media_probe.probe(in_p)
        width, height = media_info.width or 1080, media_info.height or 1920
        duration = media_info.duration or 10.0

        # Mode 1: Skip removal (bypass)
        if mode == "skip" or (mode == "vsr" and not self.is_vsr_available()):
            if progress_callback:
                if mode == "vsr":
                    progress_callback(20, "VSR chưa được cài đặt. Tự động bỏ qua xóa nền...")
                else:
                    progress_callback(20, "Bỏ qua bước xóa phụ đề Trung Quốc theo cấu hình...")
            cmd = [
                self.ffmpeg_path,
                "-y",
                "-i", str(in_p),
                "-c", "copy",
                str(out_p),
            ]
            subprocess.run(cmd, capture_output=True, check=True)
            if progress_callback:
                progress_callback(100, "Đã chuẩn bị xong video cho bước ghi phụ đề tiếng Việt.")
            return out_p

        # Dynamic Timeline Detection
        if progress_callback:
            progress_callback(5, "Đang khởi chạy AI nhận dạng dòng thời gian phụ đề tiếng Trung...")

        intervals = self.detect_text_timeline(
            video_path=in_p,
            duration=duration,
            width=width,
            height=height,
            step_sec=1.0,
            progress_callback=progress_callback,
            is_cancelled=is_cancelled,
        )

        # Mode 2: Multi-interval dynamic FFmpeg Delogo with sharpness restoration
        if mode in ("ffmpeg_delogo", "auto"):
            return self._run_ffmpeg_multi_delogo(in_p, out_p, intervals, width, height, progress_callback, is_cancelled)

        # Mode 3: Multi-interval dynamic FFmpeg Boxblur
        if mode == "ffmpeg_blur":
            return self._run_ffmpeg_multi_blur(in_p, out_p, intervals, width, height, progress_callback, is_cancelled)

        # Mode 4: VSR fallback
        if mode == "vsr":
            if intervals:
                primary = intervals[0]
                vsr_coords = (primary.y, primary.y + primary.h, primary.x, primary.x + primary.w)
            else:
                vsr_coords = None
            return self._run_vsr(in_p, out_p, vsr_coords, progress_callback, is_cancelled)

        raise ValueError(f"Chế độ xóa phụ đề không hợp lệ: {mode}")

    def _run_ffmpeg_multi_delogo(
        self,
        in_p: Path,
        out_p: Path,
        intervals: List[TextInterval],
        width: int,
        height: int,
        progress_callback: Optional[Callable[[int, str], None]],
        is_cancelled: Optional[Callable[[], bool]],
    ) -> Path:
        """Apply time-gated FFmpeg delogo on all detected intervals and apply unsharp detail enhancement."""
        if progress_callback:
            progress_callback(45, f"Đang xóa {len(intervals)} phân đoạn phụ đề và khôi phục độ nét...")

        filters = []
        for inv in intervals:
            filters.append(
                f"delogo=x={inv.x}:y={inv.y}:w={inv.w}:h={inv.h}:enable='between(t,{inv.start_sec:.2f},{inv.end_sec:.2f})'"
            )

        # Append unsharp filter to enhance video clarity and restore micro-textures
        filters.append("unsharp=lx=5:ly=5:la=0.7:cx=5:cy=5:ca=0.3")
        vf_str = ",".join(filters)

        cmd = [
            self.ffmpeg_path,
            "-y",
            "-i", str(in_p),
            "-vf", vf_str,
            "-c:v", "libx264",
            "-crf", "18",
            "-preset", "veryfast",
            "-c:a", "copy",
            "-movflags", "+faststart",
            str(out_p),
        ]

        logger.info(f"FFmpeg multi-delogo command with {len(intervals)} intervals.")
        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="replace",
        )

        output_lines = []
        try:
            while True:
                if is_cancelled and is_cancelled():
                    process.terminate()
                    raise RuntimeError("Hủy tác vụ xóa phụ đề bởi người dùng.")

                line = process.stdout.readline()
                if not line and process.poll() is not None:
                    break
                if line:
                    output_lines.append(line)
                    if len(output_lines) > 50:
                        output_lines.pop(0)
                    if "time=" in line and progress_callback:
                        progress_callback(75, "Đang tái tạo khung hình video sạch và sắc nét...")
            ret = process.poll()
            if ret != 0:
                err_tail = "".join(output_lines)
                raise RuntimeError(f"FFmpeg multi-delogo thất bại với mã lỗi {ret}:\n{err_tail}")
        finally:
            if process.poll() is None:
                process.kill()

        if progress_callback:
            progress_callback(100, f"Đã xóa thành công toàn bộ {len(intervals)} đoạn chữ và phục hồi video siêu nét.")
        return out_p

    def _run_ffmpeg_multi_blur(
        self,
        in_p: Path,
        out_p: Path,
        intervals: List[TextInterval],
        width: int,
        height: int,
        progress_callback: Optional[Callable[[int, str], None]],
        is_cancelled: Optional[Callable[[], bool]],
    ) -> Path:
        """Apply time-gated blur on all detected intervals."""
        if progress_callback:
            progress_callback(45, f"Đang làm mờ {len(intervals)} phân đoạn phụ đề...")

        if not intervals:
            shutil.copy2(in_p, out_p)
            return out_p

        # For multiple intervals, we can use boxblur or delogo
        filters = []
        for inv in intervals:
            filters.append(
                f"delogo=x={inv.x}:y={inv.y}:w={inv.w}:h={inv.h}:enable='between(t,{inv.start_sec:.2f},{inv.end_sec:.2f})'"
            )
        filters.append("unsharp=lx=5:ly=5:la=0.5:cx=5:cy=5:ca=0.2")

        cmd = [
            self.ffmpeg_path,
            "-y",
            "-i", str(in_p),
            "-vf", ",".join(filters),
            "-c:v", "libx264",
            "-crf", "18",
            "-preset", "veryfast",
            "-c:a", "copy",
            "-movflags", "+faststart",
            str(out_p),
        ]

        res = subprocess.run(cmd, capture_output=True, text=True, check=False)
        if res.returncode != 0:
            raise RuntimeError(f"Lỗi khi chạy FFmpeg blur: {res.stderr}")

        if progress_callback:
            progress_callback(100, "Hoàn tất làm mờ vùng phụ đề.")
        return out_p

    def _run_vsr(
        self,
        in_p: Path,
        out_p: Path,
        area_coords: Optional[Tuple[int, int, int, int]],
        progress_callback: Optional[Callable[[int, str], None]],
        is_cancelled: Optional[Callable[[], bool]],
    ) -> Path:
        """Run official Video-Subtitle-Remover CLI."""
        p = Path(self.vsr_path)
        if p.is_dir():
            script_path = p / "backend" / "main.py"
            cmd = ["python", str(script_path), "-i", str(in_p), "-o", str(out_p), "--inpaint-mode", self.inpaint_mode]
        else:
            cmd = [str(p), "-i", str(in_p), "-o", str(out_p), "--inpaint-mode", self.inpaint_mode]

        if area_coords:
            ymin, ymax, xmin, xmax = area_coords
            cmd.extend(["-c", str(ymin), str(ymax), str(xmin), str(xmax)])

        if progress_callback:
            progress_callback(10, "Đang khởi động VSR (AI Inpainting)...")

        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="replace",
        )

        try:
            while True:
                if is_cancelled and is_cancelled():
                    process.terminate()
                    raise RuntimeError("Hủy tác vụ VSR bởi người dùng.")

                line = process.stdout.readline()
                if not line and process.poll() is not None:
                    break
                if line:
                    logger.debug(f"[VSR] {line.strip()}")
                    if progress_callback and "%" in line:
                        progress_callback(50, f"VSR đang xử lý: {line.strip()[:40]}")
            ret = process.poll()
            if ret != 0:
                raise RuntimeError(f"VSR kết thúc với mã lỗi {ret}")
        finally:
            if process.poll() is None:
                process.kill()

        if not out_p.exists() or out_p.stat().st_size == 0:
            raise RuntimeError(f"VSR không xuất được file video kết quả tại: {out_p}")

        return out_p
