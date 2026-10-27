"""End-to-end processing pipeline orchestrating all stages from input to final video."""

from __future__ import annotations

import json
import logging
import os
import shutil
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from config.settings import AppSettings
from core.downloader import DownloaderAdapter
from core.media_probe import MediaInfo, MediaProbe
from core.ocr_subtitles import OCRSubtitleExtractor
from core.speech_to_text import SpeechToTextEngine, export_srt
from core.subtitle_remover import SubtitleRemover
from core.subtitle_renderer import SubtitleRenderer
from core.translator import TranslatorEngine
from storage.task_repository import SubtitleItem, TaskModel, TaskRepository

logger = logging.getLogger(__name__)


class PipelineCancelledException(Exception):
    """Raised when user cancels the pipeline execution."""
    pass


def sanitize_output_name(raw_name: str) -> str:
    """
    Remove hashtags (#tag), URI fragment delimiters, and illegal Windows characters.
    Ensures output filenames never cause 'Server execution failed' or URL truncation.
    """
    import re
    cleaned = re.sub(r'#\S+', '', raw_name).strip()
    cleaned = re.sub(r'[#%?*:"<>|/\\\t\r\n]+', '_', cleaned)
    cleaned = re.sub(r'[ _]+', ' ', cleaned).strip(' ._')
    if not cleaned:
        cleaned = "video_output"
    return cleaned


class VideoProcessingPipeline:
    """Orchestrates video acquisition, transcription, translation, subtitle removal, and rendering."""

    def __init__(self, settings: Optional[AppSettings] = None, repository: Optional[TaskRepository] = None):
        self.settings = settings or AppSettings.load()
        self.repository = repository or TaskRepository()
        self._is_cancelled = False

        # Core engines
        self.downloader = DownloaderAdapter(download_dir=Path(self.settings.workspace_dir) / "downloads")
        self.media_probe = MediaProbe(self.settings.ffprobe_path, self.settings.ffmpeg_path)
        self.stt_engine = SpeechToTextEngine(
            model_size=self.settings.whisper_model,
            device=self.settings.whisper_device,
            compute_type=self.settings.whisper_compute_type,
            download_root=self.settings.models_cache_dir,
            mock_mode=self.settings.mock_mode,
        )
        self.translator = TranslatorEngine(
            model_name_or_path=self.settings.translator_model,
            cache_dir=self.settings.models_cache_dir,
            device=self.settings.translator_device,
            mock_mode=self.settings.mock_mode,
        )
        self.subtitle_remover = SubtitleRemover(
            vsr_path=self.settings.vsr_path,
            ffmpeg_path=self.settings.ffmpeg_path,
            ffprobe_path=self.settings.ffprobe_path,
            inpaint_mode=self.settings.vsr_inpaint_mode,
        )
        self.subtitle_renderer = SubtitleRenderer(
            ffmpeg_path=self.settings.ffmpeg_path,
            ffprobe_path=self.settings.ffprobe_path,
        )
        self.ocr_extractor = OCRSubtitleExtractor()

    def cancel(self) -> None:
        """Signal pipeline to stop at the earliest opportunity."""
        self._is_cancelled = True

    def check_cancelled(self) -> None:
        """Raise exception if cancellation flag is active."""
        if self._is_cancelled:
            raise PipelineCancelledException("Tác vụ đã bị người dùng hủy.")

    def run_pipeline(
        self,
        task: TaskModel,
        start_from_stage: str = "acquire",
        progress_callback: Optional[Callable[[int, str], None]] = None,
        stage_callback: Optional[Callable[[str, str], None]] = None,
        log_callback: Optional[Callable[[str], None]] = None,
    ) -> TaskModel:
        """
        Execute pipeline stages sequentially.
        Stages: acquire -> inspect -> transcribe -> translate -> review -> remove_subtitles -> render -> validate
        """
        # Task workspace directory
        task_workspace = Path(self.settings.workspace_dir) / task.id
        task_workspace.mkdir(parents=True, exist_ok=True)
        task.workspace_dir = str(task_workspace)

        log_file = task_workspace / "processing_log.txt"

        def emit_log(msg: str) -> None:
            now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            line = f"[{now_str}] {msg}"
            logger.info(line)
            with open(log_file, "a", encoding="utf-8") as f:
                f.write(line + "\n")
            if log_callback:
                log_callback(line)

        def emit_progress(pct: int, msg: str) -> None:
            if progress_callback:
                progress_callback(pct, msg)
            emit_log(f"Tiến độ {pct}%: {msg}")

        def emit_stage(stage: str, msg: str) -> None:
            task.status = stage
            task.current_step = msg
            self.repository.update_progress(task.id, stage, task.progress, msg)
            if stage_callback:
                stage_callback(stage, msg)
            emit_log(f">>> Giai đoạn: [{stage}] - {msg}")

        try:
            self.check_cancelled()

            input_video_path = task_workspace / "input_video.mp4"
            clean_video_path = task_workspace / "clean_video.mp4"
            safe_title = sanitize_output_name(task.title)
            final_video_path = Path(self.settings.output_dir) / f"{safe_title}_{task.id[:6]}.mp4"
            srt_output_path = Path(self.settings.output_dir) / f"{safe_title}_{task.id[:6]}.srt"
            zh_json_path = task_workspace / "transcript_zh.json"
            zh_srt_path = task_workspace / "transcript_zh.srt"
            vi_json_path = task_workspace / "transcript_vi.json"
            vi_srt_path = task_workspace / "subtitles_vi.srt"

            # -------------------------------------------------------------
            # Stage 1: ACQUIRE
            # -------------------------------------------------------------
            if start_from_stage in ("acquire", "start"):
                emit_stage("acquiring", "Đang tiếp nhận và tải video...")
                self.check_cancelled()

                if task.source_type == "url":
                    downloaded_file = self.downloader.download(
                        task.source_path,
                        task_id=task.id,
                        progress_callback=emit_progress,
                    )
                    shutil.copy2(downloaded_file, input_video_path)
                else:
                    src_file = Path(task.source_path).resolve()
                    if not src_file.exists():
                        raise FileNotFoundError(f"File video nguồn không tồn tại: {src_file}")
                    shutil.copy2(src_file, input_video_path)

                emit_progress(10, "Tiếp nhận video thành công.")
                self.check_cancelled()

            # -------------------------------------------------------------
            # Stage 2: INSPECT
            # -------------------------------------------------------------
            if start_from_stage in ("acquire", "inspect", "start"):
                emit_stage("inspecting", "Đang phân tích định dạng và thông số video...")
                self.check_cancelled()

                media_info = self.media_probe.probe(input_video_path)
                task.video_width = media_info.width
                task.video_height = media_info.height
                task.duration = media_info.duration
                task.fps = media_info.fps
                task.has_audio = media_info.has_audio

                self.repository.update_media_info(
                    task.id, media_info.width, media_info.height,
                    media_info.duration, media_info.fps, media_info.has_audio
                )

                # Check disk space
                has_space, free_bytes = self.media_probe.check_free_space(self.settings.output_dir)
                if not has_space:
                    raise RuntimeError(f"Dung lượng đĩa còn trống quá thấp ({free_bytes // (1024*1024)} MB). Cần ít nhất 500MB.")

                # Extract thumbnail for UI preview
                thumb_path = task_workspace / "thumbnail.jpg"
                self.media_probe.extract_thumbnail(input_video_path, thumb_path, time_sec=min(1.0, media_info.duration / 2))

                emit_log(f"Thông số video: {media_info.width}x{media_info.height}, FPS: {media_info.fps}, Thời lượng: {round(media_info.duration, 2)}s, Âm thanh: {media_info.has_audio}")
                emit_progress(20, "Phân tích video hoàn tất.")
                self.check_cancelled()

            # -------------------------------------------------------------
            # Stage 3: TRANSCRIBE (Speech-to-text)
            # -------------------------------------------------------------
            if start_from_stage in ("acquire", "inspect", "transcribe", "start"):
                emit_stage("transcribing", "Đang nhận dạng lời thoại tiếng Trung...")
                self.check_cancelled()

                if not task.has_audio:
                    emit_log("Video không có âm thanh. Bỏ qua nhận dạng giọng nói.")
                    zh_segments = []
                else:
                    zh_segments = self.stt_engine.transcribe(
                        input_video_path,
                        total_duration=task.duration,
                        progress_callback=lambda p, m: emit_progress(int(20 + p * 0.4), m),
                        is_cancelled=lambda: self._is_cancelled,
                    )

                # Fallback to OCR text detection if no speech found
                if len(zh_segments) == 0:
                    emit_log("Không tìm thấy lời thoại qua giọng nói. Tự động nhận diện chữ chạy/tiêu đề tiếng Trung (OCR)...")
                    try:
                        ocr_segments = self.ocr_extractor.extract_subtitles_from_video(
                            input_video_path,
                            sample_step_sec=2.5,
                            progress_callback=lambda p, m: emit_progress(int(25 + p * 0.35), m),
                            is_cancelled=lambda: self._is_cancelled,
                        )
                        if ocr_segments:
                            emit_log(f"Đã nhận diện thành công {len(ocr_segments)} đoạn phụ đề chữ từ video!")
                            zh_segments = ocr_segments
                        else:
                            emit_log("Video không có phụ đề chữ hoặc giọng nói tiếng Trung.")
                    except Exception as ocr_err:
                        emit_log(f"Quét OCR gặp sự cố ({ocr_err}). Bỏ qua OCR để tiếp tục quy trình.")
                        zh_segments = []

                with open(zh_json_path, "w", encoding="utf-8") as f:
                    json.dump(zh_segments, f, ensure_ascii=False, indent=2)
                export_srt(zh_segments, zh_srt_path, text_key="text")

                emit_progress(60, f"Đã nhận dạng {len(zh_segments)} đoạn phụ đề/hội thoại tiếng Trung.")
                self.check_cancelled()
            else:
                if zh_json_path.exists():
                    with open(zh_json_path, "r", encoding="utf-8") as f:
                        zh_segments = json.load(f)
                else:
                    zh_segments = []

            # -------------------------------------------------------------
            # Stage 4: TRANSLATE (Chinese to Vietnamese)
            # -------------------------------------------------------------
            if start_from_stage in ("acquire", "inspect", "transcribe", "translate", "start"):
                emit_stage("translating", "Đang dịch phụ đề tiếng Trung sang tiếng Việt...")
                self.check_cancelled()

                vi_segments = self.translator.translate_segments(
                    zh_segments,
                    progress_callback=lambda p, m: emit_progress(int(60 + p * 0.15), m),
                    is_cancelled=lambda: self._is_cancelled,
                )

                with open(vi_json_path, "w", encoding="utf-8") as f:
                    json.dump(vi_segments, f, ensure_ascii=False, indent=2)
                export_srt(vi_segments, vi_srt_path, text_key="text_vi")

                # Update task model with bilingual subtitles
                task.subtitles = [SubtitleItem(**item) for item in vi_segments]
                self.repository.update_subtitles(task.id, task.subtitles)

                emit_progress(75, f"Đã dịch hoàn tất {len(vi_segments)} câu sang tiếng Việt.")
                self.check_cancelled()

            # -------------------------------------------------------------
            # Stage 5: REVIEW (Interactive user check / edit)
            # -------------------------------------------------------------
            if not self.settings.auto_pipeline and start_from_stage not in ("render_only", "resume_render"):
                emit_stage("review_ready", "Đã sẵn sàng cho người dùng kiểm tra và chỉnh sửa phụ đề.")
                task.progress = 75
                self.repository.update_progress(task.id, "review_ready", 75, "Chờ người dùng xác nhận bản dịch.")
                return task
            else:
                emit_log(f"Chế độ Tự động hoàn toàn: Tự động xóa phụ đề Trung ({self.settings.subtitle_remove_mode}) và xuất video thành phẩm...")

            # -------------------------------------------------------------
            # Stage 6: REMOVE SUBTITLES (VSR or bypass)
            # -------------------------------------------------------------
            if start_from_stage in ("acquire", "inspect", "transcribe", "translate", "start", "remove_subtitles", "render_only", "resume_render"):
                mode_name = {
                    "ffmpeg_delogo": "FFmpeg Delogo",
                    "ffmpeg_blur": "FFmpeg Boxblur",
                    "vsr": "VSR AI",
                    "skip": "Bỏ qua"
                }.get(self.settings.subtitle_remove_mode, self.settings.subtitle_remove_mode)
                emit_stage("removing_subtitles", f"Đang xóa phụ đề tiếng Trung ({mode_name})...")
                self.check_cancelled()

                # Refresh latest subtitles from repository (in case user edited them)
                db_task = self.repository.get(task.id)
                if db_task and db_task.subtitles:
                    task.subtitles = db_task.subtitles
                    # Re-export SRT with verified edits
                    export_srt([s.model_dump() for s in task.subtitles], vi_srt_path, text_key="text_vi")

                self.subtitle_remover.remove_subtitles(
                    input_video=input_video_path,
                    output_video=clean_video_path,
                    mode=self.settings.subtitle_remove_mode,
                    zone_mode=self.settings.subtitle_zone_mode,
                    area_ratio=self.settings.subtitle_area_ratio,
                    progress_callback=lambda p, m: emit_progress(int(75 + p * 0.1), m),
                    is_cancelled=lambda: self._is_cancelled,
                )

                emit_progress(85, "Chuẩn bị xong khung hình video sạch.")
                self.check_cancelled()

            # -------------------------------------------------------------
            # Stage 7: RENDER (Burn Vietnamese Subtitles with FFmpeg)
            # -------------------------------------------------------------
            emit_stage("rendering", "Đang ghi đè phụ đề tiếng Việt lên video...")
            self.check_cancelled()

            # Input video for rendering is clean_video if exists, else input_video
            render_input = clean_video_path if clean_video_path.exists() else input_video_path

            self.subtitle_renderer.render(
                video_input=render_input,
                srt_input=vi_srt_path,
                video_output=final_video_path,
                style=self.settings.subtitle_style,
                crf=self.settings.crf,
                preset=self.settings.preset,
                progress_callback=lambda p, m: emit_progress(int(85 + p * 0.13), m),
                is_cancelled=lambda: self._is_cancelled,
            )

            # Copy SRT to output folder
            shutil.copy2(vi_srt_path, srt_output_path)
            emit_progress(98, "Đã tạo video hoàn chỉnh.")
            self.check_cancelled()

            # -------------------------------------------------------------
            # Stage 8: VALIDATE
            # -------------------------------------------------------------
            emit_stage("validating", "Đang kiểm tra tính toàn vẹn của video thành phẩm...")
            if not final_video_path.exists() or final_video_path.stat().st_size == 0:
                raise RuntimeError("File video đầu ra không tồn tại hoặc bị rỗng.")

            final_probe = self.media_probe.probe(final_video_path)
            if not final_probe.has_video:
                raise RuntimeError("Video đầu ra bị hỏng luồng hiển thị.")

            emit_log(f"Kiểm tra thành công: Kích thước {final_video_path.stat().st_size // 1024} KB, Thời lượng: {final_probe.duration}s")

            task.output_video_path = str(final_video_path)
            task.output_srt_path = str(srt_output_path)
            task.status = "completed"
            task.progress = 100
            task.current_step = "Đã hoàn thành xuất sắc toàn bộ quy trình!"

            self.repository.update_outputs(task.id, str(final_video_path), str(srt_output_path))
            self.repository.update_progress(task.id, "completed", 100, task.current_step)
            emit_stage("completed", "Đã hoàn thành xuất sắc toàn bộ quy trình!")

            return task

        except PipelineCancelledException as e:
            emit_log(f"Tác vụ bị hủy: {e}")
            task.status = "cancelled"
            task.current_step = "Đã hủy bởi người dùng."
            self.repository.update_progress(task.id, "cancelled", task.progress, "Đã hủy.")
            return task
        except Exception as e:
            emit_log(f"Lỗi pipeline: {e}")
            task.status = "failed"
            task.error_message = str(e)
            self.repository.update_progress(task.id, "failed", task.progress, f"Lỗi: {e}", error_message=str(e))
            raise
