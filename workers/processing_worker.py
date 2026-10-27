"""Background processing worker using QThread for non-blocking UI execution."""

from __future__ import annotations

import logging
from typing import List, Optional

from PySide6.QtCore import QObject, QThread, Signal

from config.settings import AppSettings
from core.pipeline import PipelineCancelledException, VideoProcessingPipeline
from storage.task_repository import SubtitleItem, TaskModel, TaskRepository

logger = logging.getLogger(__name__)


class PipelineWorkerSignals(QObject):
    """Signals emitted by the processing pipeline worker."""
    sig_progress = Signal(int, str)             # (percentage, message)
    sig_stage_changed = Signal(str, str)        # (stage, message)
    sig_log = Signal(str)                       # (log_line)
    sig_review_ready = Signal(str, list)        # (task_id, subtitles)
    sig_completed = Signal(str, str, str)       # (task_id, video_path, srt_path)
    sig_failed = Signal(str, str)               # (task_id, error_message)
    sig_cancelled = Signal(str)                 # (task_id)


class ProcessingWorker(QThread):
    """QThread running the video processing pipeline in the background."""

    def __init__(
        self,
        task: TaskModel,
        start_from_stage: str = "acquire",
        settings: Optional[AppSettings] = None,
        repository: Optional[TaskRepository] = None,
        parent: Optional[QObject] = None,
    ):
        super().__init__(parent)
        self.task = task
        self.start_from_stage = start_from_stage
        self.settings = settings or AppSettings.load()
        self.repository = repository or TaskRepository()
        self.signals = PipelineWorkerSignals()
        self.pipeline: Optional[VideoProcessingPipeline] = None
        self._is_cancelled = False

    def cancel(self) -> None:
        """Request the worker and pipeline to cancel gracefully."""
        self._is_cancelled = True
        if self.pipeline:
            self.pipeline.cancel()

    def run(self) -> None:
        """Worker main loop."""
        try:
            self.pipeline = VideoProcessingPipeline(
                settings=self.settings,
                repository=self.repository,
            )

            res_task = self.pipeline.run_pipeline(
                task=self.task,
                start_from_stage=self.start_from_stage,
                progress_callback=self.signals.sig_progress.emit,
                stage_callback=self.signals.sig_stage_changed.emit,
                log_callback=self.signals.sig_log.emit,
            )

            if res_task.status == "review_ready":
                self.signals.sig_review_ready.emit(res_task.id, res_task.subtitles)
            elif res_task.status == "completed":
                self.signals.sig_completed.emit(
                    res_task.id, res_task.output_video_path, res_task.output_srt_path
                )
            elif res_task.status == "cancelled":
                self.signals.sig_cancelled.emit(res_task.id)

        except PipelineCancelledException:
            logger.info(f"Task {self.task.id} cancelled.")
            self.signals.sig_cancelled.emit(self.task.id)
        except Exception as e:
            logger.exception(f"Task {self.task.id} failed: {e}")
            self.signals.sig_failed.emit(self.task.id, str(e))
