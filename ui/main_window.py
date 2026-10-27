"""Main application window for DouyinVN Studio desktop app."""

from __future__ import annotations

import os
import shutil
import subprocess
import uuid
from pathlib import Path
from typing import Optional

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QDragEnterEvent, QDropEvent, QIcon
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QFileDialog,
    QFrame,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPlainTextEdit,
    QProgressBar,
    QPushButton,
    QSplitter,
    QStackedWidget,
    QStyle,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from config.settings import AppSettings
from core.media_probe import MediaProbe
from storage.task_repository import SubtitleItem, TaskModel, TaskRepository
from ui.settings_dialog import SettingsDialog
from ui.subtitle_editor import SubtitleEditorWidget
from ui.task_queue import TaskQueueWidget
from workers.processing_worker import ProcessingWorker


class DropAreaWidget(QFrame):
    """Visual drop area for video files."""

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.setAcceptDrops(True)
        self.setStyleSheet("""
            QFrame {
                border: 2px dashed #3b82f6;
                border-radius: 8px;
                background-color: #1e293b;
                padding: 20px;
            }
            QFrame:hover {
                background-color: #24344d;
                border-color: #60a5fa;
            }
        """)
        layout = QVBoxLayout(self)
        self.label = QLabel("📥 KÉO & THẢ VIDEO MP4 VÀO ĐÂY HOẶC NHẤP ĐỂ CHỌN FILE", self)
        self.label.setAlignment(Qt.AlignCenter)
        self.label.setStyleSheet("color: #93c5fd; font-weight: bold; font-size: 13px; border: none;")
        layout.addWidget(self.label)


class MainWindow(QMainWindow):
    """DouyinVN Studio primary desktop window."""

    def __init__(self):
        super().__init__()
        self.settings = AppSettings.load()
        self.repository = TaskRepository()
        self.media_probe = MediaProbe(self.settings.ffprobe_path, self.settings.ffmpeg_path)

        self.current_task: Optional[TaskModel] = None
        self.worker: Optional[ProcessingWorker] = None

        self.setWindowTitle("DouyinVN Studio - Xóa Phụ Đề Trung & Tạo Phụ Đề Việt Tự Động")
        self.resize(1150, 780)
        self.setMinimumSize(950, 650)
        self.setAcceptDrops(True)

        self._apply_dark_theme()
        self._setup_ui()
        self._check_system_health()

    def _apply_dark_theme(self):
        self.setStyleSheet("""
            QMainWindow { background-color: #0b0f19; }
            QWidget { font-family: 'Segoe UI', 'Roboto', sans-serif; color: #f8fafc; }
            QTabWidget::pane { border: 1px solid #1e293b; background-color: #0f172a; border-radius: 6px; }
            QTabBar::tab {
                background-color: #1e293b;
                color: #94a3b8;
                padding: 10px 20px;
                font-size: 12px;
                font-weight: bold;
                border-top-left-radius: 6px;
                border-top-right-radius: 6px;
                margin-right: 3px;
            }
            QTabBar::tab:selected {
                background-color: #0284c7;
                color: white;
            }
            QLineEdit {
                background-color: #1e293b;
                border: 1px solid #334155;
                border-radius: 5px;
                padding: 6px 10px;
                color: white;
                font-size: 12px;
            }
            QLineEdit:focus {
                border-color: #38bdf8;
            }
            QPushButton {
                background-color: #1e293b;
                border: 1px solid #334155;
                border-radius: 5px;
                padding: 6px 14px;
                font-weight: bold;
                color: white;
            }
            QPushButton:hover {
                background-color: #334155;
            }
            QProgressBar {
                background-color: #1e293b;
                border: 1px solid #334155;
                border-radius: 5px;
                text-align: center;
                color: white;
                font-weight: bold;
                height: 20px;
            }
            QProgressBar::chunk {
                background-color: #0284c7;
                border-radius: 4px;
            }
            QPlainTextEdit {
                background-color: #020617;
                color: #a7f3d0;
                font-family: Consolas, monospace;
                font-size: 11px;
                border: 1px solid #1e293b;
                border-radius: 5px;
            }
        """)

    def _setup_ui(self):
        central_widget = QWidget(self)
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)
        main_layout.setContentsMargins(10, 8, 10, 8)
        main_layout.setSpacing(8)

        # Header bar
        header_row = QHBoxLayout()
        logo_label = QLabel("🎬 DOUYINVN STUDIO", self)
        logo_label.setStyleSheet("font-size: 16px; font-weight: 900; color: #38bdf8; letter-spacing: 1px;")
        header_row.addWidget(logo_label)

        sub_title = QLabel("v1.0.0 | AI Local Video Processing", self)
        sub_title.setStyleSheet("color: #64748b; font-size: 11px;")
        header_row.addWidget(sub_title)

        header_row.addStretch()

        self.lbl_health = QLabel("Kiểm tra công cụ...", self)
        self.lbl_health.setStyleSheet("color: #10b981; font-size: 11px; padding: 2px 8px; background: #064e3b; border-radius: 4px;")
        header_row.addWidget(self.lbl_health)

        btn_settings = QPushButton("⚙️ Cài đặt", self)
        btn_settings.clicked.connect(self._open_settings)
        header_row.addWidget(btn_settings)

        main_layout.addLayout(header_row)

        # Tabs
        self.tabs = QTabWidget(self)

        # -------------------------------------------------------------
        # Tab 1: Xử lý chính (Dashboard)
        # -------------------------------------------------------------
        tab_dashboard = QWidget()
        dash_layout = QVBoxLayout(tab_dashboard)
        dash_layout.setSpacing(10)

        # Input Group
        input_group = QGroupBox("1. TIẾP NHẬN VIDEO TỪ DOUYIN HOẶC FILE CỤC BỘ", tab_dashboard)
        input_group.setStyleSheet("QGroupBox { font-weight: bold; color: #38bdf8; border: 1px solid #1e293b; margin-top: 6px; padding-top: 14px; }")
        input_layout = QVBoxLayout(input_group)

        # URL row
        url_row = QHBoxLayout()
        self.txt_url = QLineEdit(self)
        self.txt_url.setPlaceholderText("Dán liên kết Douyin vào đây (ví dụ: https://v.douyin.com/xyz hoặc toàn bộ văn bản chia sẻ)...")
        btn_fetch_url = QPushButton("⚡ Phân tích URL", self)
        btn_fetch_url.setStyleSheet("background: #0284c7; color: white;")
        btn_fetch_url.clicked.connect(self._on_fetch_url)

        url_row.addWidget(self.txt_url, stretch=1)
        url_row.addWidget(btn_fetch_url)
        input_layout.addLayout(url_row)

        # Drop / browse row
        file_row = QHBoxLayout()
        self.drop_area = DropAreaWidget(self)
        self.drop_area.mousePressEvent = lambda e: self._on_browse_file()
        file_row.addWidget(self.drop_area, stretch=1)

        btn_browse = QPushButton("📂 Chọn File MP4...", self)
        btn_browse.setStyleSheet("background: #3b82f6; color: white; padding: 12px 18px; font-size: 12px;")
        btn_browse.clicked.connect(self._on_browse_file)
        file_row.addWidget(btn_browse)

        input_layout.addLayout(file_row)
        dash_layout.addWidget(input_group)

        # Task Status & Media Info Card
        self.card_info = QFrame(tab_dashboard)
        self.card_info.setStyleSheet("background: #0f172a; border: 1px solid #1e293b; border-radius: 6px; padding: 6px;")
        card_layout = QHBoxLayout(self.card_info)

        self.lbl_file_name = QLabel("Chưa chọn video", self.card_info)
        self.lbl_file_name.setStyleSheet("font-weight: bold; color: #f8fafc;")
        card_layout.addWidget(self.lbl_file_name)

        self.lbl_media_specs = QLabel("Độ phân giải: -- | Thời lượng: -- | Âm thanh: --", self.card_info)
        self.lbl_media_specs.setStyleSheet("color: #94a3b8; font-size: 11px;")
        card_layout.addWidget(self.lbl_media_specs)
        card_layout.addStretch()

        dash_layout.addWidget(self.card_info)

        # Progress Section
        prog_group = QGroupBox("2. TIẾN TRÌNH THỰC HIỆN PIPELINE", tab_dashboard)
        prog_group.setStyleSheet("QGroupBox { font-weight: bold; color: #38bdf8; border: 1px solid #1e293b; margin-top: 6px; padding-top: 14px; }")
        prog_layout = QVBoxLayout(prog_group)

        self.lbl_stage = QLabel("Trạng thái: Sẵn sàng.", self)
        self.lbl_stage.setStyleSheet("color: #38bdf8; font-weight: bold;")
        prog_layout.addWidget(self.lbl_stage)

        self.progress_bar = QProgressBar(self)
        self.progress_bar.setValue(0)
        prog_layout.addWidget(self.progress_bar)

        # Quick Mode & Subtitle Removal Configuration Strip
        cfg_strip = QHBoxLayout()
        cfg_strip.setContentsMargins(0, 4, 0, 4)

        self.chk_auto_pipeline = QCheckBox("⚡ Tự động chạy toàn bộ (Nhận dạng, dịch & xóa phụ đề không cần dừng chờ duyệt)", self)
        self.chk_auto_pipeline.setChecked(self.settings.auto_pipeline)
        self.chk_auto_pipeline.setStyleSheet("color: #38bdf8; font-weight: bold; font-size: 11px;")
        self.chk_auto_pipeline.toggled.connect(self._on_quick_auto_toggled)
        cfg_strip.addWidget(self.chk_auto_pipeline)

        cfg_strip.addStretch()

        lbl_mode = QLabel("Chế độ xóa phụ đề:", self)
        lbl_mode.setStyleSheet("color: #94a3b8; font-size: 11px;")
        cfg_strip.addWidget(lbl_mode)

        self.combo_quick_remove_mode = QComboBox(self)
        self.combo_quick_remove_mode.addItem("🎯 Tự động phát hiện & Xóa siêu nét (Khuyên dùng)", "ffmpeg_delogo")
        self.combo_quick_remove_mode.addItem("🌫️ Làm mờ thông minh (FFmpeg Blur)", "ffmpeg_blur")
        self.combo_quick_remove_mode.addItem("⏩ Bỏ qua xóa (Ghi đè trực tiếp)", "skip")
        self.combo_quick_remove_mode.addItem("🤖 Phục hồi AI bằng VSR", "vsr")
        idx = self.combo_quick_remove_mode.findData(self.settings.subtitle_remove_mode)
        if idx >= 0:
            self.combo_quick_remove_mode.setCurrentIndex(idx)
        self.combo_quick_remove_mode.currentIndexChanged.connect(self._on_quick_remove_mode_changed)
        self.combo_quick_remove_mode.setStyleSheet("background: #1e293b; color: #f8fafc; border-radius: 4px; padding: 3px 6px; font-size: 11px;")
        cfg_strip.addWidget(self.combo_quick_remove_mode)

        prog_layout.addLayout(cfg_strip)

        # Action Buttons Row
        act_row = QHBoxLayout()
        self.btn_start = QPushButton("▶ BẮT ĐẦU XỬ LÝ", self)
        self.btn_start.setStyleSheet(
            "QPushButton { background: #059669; color: white; font-size: 13px; padding: 8px 18px; } "
            "QPushButton:hover { background: #10b981; }"
        )
        self.btn_start.clicked.connect(self._on_start_pipeline)
        act_row.addWidget(self.btn_start)

        self.btn_cancel = QPushButton("⏹ Hủy tác vụ", self)
        self.btn_cancel.setStyleSheet("background: #dc2626; color: white; padding: 8px 14px;")
        self.btn_cancel.setEnabled(False)
        self.btn_cancel.clicked.connect(self._on_cancel_pipeline)
        act_row.addWidget(self.btn_cancel)

        act_row.addStretch()

        self.btn_open_editor = QPushButton("✏️ Xem & Sửa phụ đề", self)
        self.btn_open_editor.setStyleSheet("background: #0284c7; color: white; padding: 8px 14px;")
        self.btn_open_editor.clicked.connect(lambda: self.tabs.setCurrentIndex(1))
        act_row.addWidget(self.btn_open_editor)

        self.btn_play_output = QPushButton("🎬 Xem video thành phẩm", self)
        self.btn_play_output.setStyleSheet("background: #10b981; color: white; padding: 8px 14px; font-weight: bold;")
        self.btn_play_output.setEnabled(False)
        self.btn_play_output.clicked.connect(self._on_play_current_output)
        act_row.addWidget(self.btn_play_output)

        self.btn_open_output = QPushButton("📁 Mở thư mục kết quả", self)
        self.btn_open_output.setStyleSheet("background: #334155; color: white; padding: 8px 14px;")
        self.btn_open_output.clicked.connect(self._on_open_output_dir)
        act_row.addWidget(self.btn_open_output)

        prog_layout.addLayout(act_row)
        dash_layout.addWidget(prog_group)

        # Log Console
        log_group = QGroupBox("3. NHẬT KÝ XỬ LÝ HỆ THỐNG", tab_dashboard)
        log_group.setStyleSheet("QGroupBox { font-weight: bold; color: #38bdf8; border: 1px solid #1e293b; margin-top: 6px; padding-top: 14px; }")
        log_layout = QVBoxLayout(log_group)

        self.txt_log = QPlainTextEdit(self)
        self.txt_log.setReadOnly(True)
        self.txt_log.setMaximumHeight(150)
        log_layout.addWidget(self.txt_log)

        dash_layout.addWidget(log_group)
        self.tabs.addTab(tab_dashboard, "🚀 Xử lý Video")

        # -------------------------------------------------------------
        # Tab 2: Chỉnh sửa phụ đề
        # -------------------------------------------------------------
        self.editor_widget = SubtitleEditorWidget(self)
        self.editor_widget.subtitles_changed.connect(self._on_subtitles_saved_from_editor)
        self.editor_widget.proceed_to_render.connect(self._on_proceed_from_editor)
        self.tabs.addTab(self.editor_widget, "✍️ Chỉnh sửa phụ đề")

        # -------------------------------------------------------------
        # Tab 3: Hàng đợi tác vụ & Lịch sử
        # -------------------------------------------------------------
        self.queue_widget = TaskQueueWidget(repository=self.repository, parent=self)
        self.queue_widget.task_selected.connect(self._load_task_into_ui)
        self.queue_widget.resume_task.connect(self._resume_task_from_id)
        self.tabs.addTab(self.queue_widget, "📋 Hàng đợi tác vụ")

        main_layout.addWidget(self.tabs)

    def _check_system_health(self):
        """Check availability of FFmpeg, VSR, and AI models."""
        ffmpeg_ok = Path(self.settings.ffmpeg_path).exists() if self.settings.ffmpeg_path else False
        vsr_ok = Path(self.settings.vsr_path).exists() if self.settings.vsr_path else False

        status_parts = []
        if ffmpeg_ok:
            status_parts.append("FFmpeg: Sẵn sàng")
        else:
            status_parts.append("FFmpeg: Chưa cấu hình")

        if vsr_ok:
            status_parts.append("Xóa chữ: VSR Inpaint AI")
        else:
            mode_map = {
                "ffmpeg_delogo": "Xóa chữ: Delogo + Tái tạo nét (Tự động)",
                "ffmpeg_blur": "Xóa chữ: Làm mờ FFmpeg",
                "skip": "Xóa chữ: Bỏ qua",
            }
            status_parts.append(mode_map.get(self.settings.subtitle_remove_mode, "Xóa chữ: Tự động"))

        self.lbl_health.setText(" | ".join(status_parts))

    def dragEnterEvent(self, event: QDragEnterEvent):
        if event.mimeData().hasUrls():
            for url in event.mimeData().urls():
                if url.toLocalFile().lower().endswith((".mp4", ".mov", ".mkv", ".flv", ".webm")):
                    event.acceptProposedAction()
                    return
        event.ignore()

    def dropEvent(self, event: QDropEvent):
        for url in event.mimeData().urls():
            file_path = url.toLocalFile()
            if file_path.lower().endswith((".mp4", ".mov", ".mkv", ".flv", ".webm")):
                self._create_task_from_file(file_path)
                break

    def _on_browse_file(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Chọn file video MP4 Douyin",
            "",
            "Video Files (*.mp4 *.mov *.mkv *.webm);;All Files (*)"
        )
        if file_path:
            self._create_task_from_file(file_path)

    def _on_fetch_url(self):
        text = self.txt_url.text().strip()
        if not text:
            QMessageBox.warning(self, "Cảnh báo", "Vui lòng nhập hoặc dán liên kết Douyin.")
            return

        task_id = str(uuid.uuid4())
        task = TaskModel(
            id=task_id,
            title=f"Douyin_URL_{task_id[:6]}",
            source_type="url",
            source_path=text,
            status="pending",
        )
        self.repository.create(task)
        self.current_task = task
        self.lbl_file_name.setText(f"URL: {text[:50]}...")
        self.lbl_media_specs.setText("Nguồn: Douyin URL | Đang chờ bắt đầu xử lý")
        self.queue_widget.refresh_tasks()
        self._append_log(f"Đã tiếp nhận URL Douyin: {text}")

    def _create_task_from_file(self, file_path: str):
        p = Path(file_path).resolve()
        task_id = str(uuid.uuid4())
        task = TaskModel(
            id=task_id,
            title=p.stem,
            source_type="file",
            source_path=str(p),
            status="pending",
        )
        self.repository.create(task)
        self.current_task = task
        self.lbl_file_name.setText(f"File: {p.name}")

        try:
            info = self.media_probe.probe(p)
            task.video_width = info.width
            task.video_height = info.height
            task.duration = info.duration
            task.fps = info.fps
            task.has_audio = info.has_audio
            self.repository.update_media_info(task.id, info.width, info.height, info.duration, info.fps, info.has_audio)
            self.lbl_media_specs.setText(
                f"Kích thước: {info.width}x{info.height} ({'Dọc 9:16' if info.is_vertical else 'Ngang'}) | "
                f"Thời lượng: {round(info.duration, 1)}s | FPS: {info.fps} | Âm thanh: {'Có' if info.has_audio else 'Không'}"
            )
        except Exception as e:
            self.lbl_media_specs.setText(f"Chưa phân tích được thông số: {e}")

        self.queue_widget.refresh_tasks()
        self._append_log(f"Đã nạp file video cục bộ: {p}")

    def _on_start_pipeline(self):
        if not self.current_task:
            QMessageBox.warning(self, "Thông báo", "Vui lòng chọn file MP4 hoặc nhập liên kết Douyin trước.")
            return

        self._run_worker_on_task(self.current_task, start_from_stage="acquire")

    def _run_worker_on_task(self, task: TaskModel, start_from_stage: str = "acquire"):
        if self.worker and self.worker.isRunning():
            QMessageBox.warning(self, "Cảnh báo", "Đang có một tác vụ khác đang chạy.")
            return

        self.btn_start.setEnabled(False)
        self.btn_cancel.setEnabled(True)

        self.worker = ProcessingWorker(
            task=task,
            start_from_stage=start_from_stage,
            settings=self.settings,
            repository=self.repository,
            parent=self,
        )

        self.worker.signals.sig_progress.connect(self._on_worker_progress)
        self.worker.signals.sig_stage_changed.connect(self._on_worker_stage)
        self.worker.signals.sig_log.connect(self._append_log)
        self.worker.signals.sig_review_ready.connect(self._on_worker_review_ready)
        self.worker.signals.sig_completed.connect(self._on_worker_completed)
        self.worker.signals.sig_failed.connect(self._on_worker_failed)
        self.worker.signals.sig_cancelled.connect(self._on_worker_cancelled)

        self.worker.start()

    def _on_worker_progress(self, pct: int, msg: str):
        self.progress_bar.setValue(pct)
        self.lbl_stage.setText(f"Tiến trình ({pct}%): {msg}")

    def _on_worker_stage(self, stage: str, msg: str):
        self.lbl_stage.setText(f"Giai đoạn [{stage}]: {msg}")
        self.queue_widget.refresh_tasks()

    def _on_worker_review_ready(self, task_id: str, subtitles: list):
        self.btn_start.setEnabled(True)
        self.btn_cancel.setEnabled(False)
        self.progress_bar.setValue(65)
        self.lbl_stage.setText("Đã nhận dạng và dịch xong! Vui lòng duyệt phụ đề trước khi xuất.")

        # Load subtitles into editor
        self.editor_widget.load_subtitles(subtitles)
        self.tabs.setCurrentIndex(1)  # Switch to Subtitle Editor tab

        QMessageBox.information(
            self,
            "Sẵn sàng kiểm tra phụ đề",
            f"Đã dịch thành công {len(subtitles)} câu thoại.\n"
            f"Hệ thống đã chuyển sang tab 'Chỉnh sửa phụ đề' để bạn kiểm tra, chỉnh sửa từ ngữ trước khi ghi lên video."
        )

    def _on_worker_completed(self, task_id: str, output_video: str, output_srt: str):
        self.btn_start.setEnabled(True)
        self.btn_cancel.setEnabled(False)
        self.progress_bar.setValue(100)
        self.lbl_stage.setText("🎉 ĐÃ HOÀN THÀNH XUẤT SẮC TOÀN BỘ QUY TRÌNH!")
        self.btn_play_output.setEnabled(True)
        self.queue_widget.refresh_tasks()

        reply = QMessageBox.information(
            self,
            "Hoàn tất xử lý video",
            f"Đã tạo video MP4 có phụ đề tiếng Việt thành công!\n\n"
            f"File: {Path(output_video).name}\n\n"
            f"Bạn có muốn phát video này ngay bây giờ?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.Yes
        )
        if reply == QMessageBox.Yes and Path(output_video).exists():
            self._open_media_file(output_video)

    def _on_worker_failed(self, task_id: str, error_msg: str):
        self.btn_start.setEnabled(True)
        self.btn_cancel.setEnabled(False)
        self.lbl_stage.setText(f"❌ Xử lý thất bại: {error_msg}")
        self.queue_widget.refresh_tasks()
        QMessageBox.critical(self, "Lỗi xử lý", f"Tác vụ gặp sự cố:\n{error_msg}")

    def _on_worker_cancelled(self, task_id: str):
        self.btn_start.setEnabled(True)
        self.btn_cancel.setEnabled(False)
        self.lbl_stage.setText("Tác vụ đã bị hủy.")
        self.queue_widget.refresh_tasks()

    def _on_cancel_pipeline(self):
        if self.worker and self.worker.isRunning():
            self.lbl_stage.setText("Đang yêu cầu hủy tác vụ...")
            self.worker.cancel()

    def _on_subtitles_saved_from_editor(self, subtitles: list):
        if self.current_task:
            self.current_task.subtitles = subtitles
            self.repository.update_subtitles(self.current_task.id, subtitles)
            self._append_log("Đã cập nhật phụ đề sửa đổi vào cơ sở dữ liệu.")

    def _on_proceed_from_editor(self, subtitles: list):
        """User approved subtitles, resume pipeline from subtitle removal / render stage."""
        if not self.current_task:
            return

        self._on_subtitles_saved_from_editor(subtitles)
        self.tabs.setCurrentIndex(0)  # Return to Dashboard
        self._run_worker_on_task(self.current_task, start_from_stage="render_only")

    def _load_task_into_ui(self, task_id: str):
        task = self.repository.get(task_id)
        if not task:
            return
        self.current_task = task
        self.lbl_file_name.setText(f"Tác vụ: {task.title}")
        self.lbl_media_specs.setText(f"{task.video_width}x{task.video_height} | {round(task.duration, 1)}s | Trạng thái: {task.status}")

        has_output = bool(task.output_video_path and Path(task.output_video_path).exists())
        self.btn_play_output.setEnabled(has_output)

        if task.subtitles:
            self.editor_widget.load_subtitles(task.subtitles)

        if task.status == "review_ready":
            self.tabs.setCurrentIndex(1)
        else:
            self.tabs.setCurrentIndex(0)

    def _on_play_current_output(self):
        if not self.current_task or not self.current_task.output_video_path:
            return
        self._open_media_file(self.current_task.output_video_path)

    def _open_media_file(self, file_path: str):
        """Open video file in dedicated media player and reveal in Explorer."""
        p = Path(file_path).resolve()
        if not p.exists():
            QMessageBox.warning(self, "Lỗi", f"Không tìm thấy file: {p}")
            return

        # If filename contains '#' (hashtags), create clean alias so Windows Media Player never throws DCOM error
        if "#" in p.name:
            import re
            safe_name = re.sub(r'#\S+', '', p.stem).strip()
            safe_name = re.sub(r'[#%?*:"<>|/\\\t\r\n]+', '_', safe_name).strip(' ._') + p.suffix
            safe_p = p.parent / safe_name
            if not safe_p.exists():
                try:
                    shutil.copy2(p, safe_p)
                except Exception:
                    safe_p = p
            p = safe_p

        # 1. Launch in dedicated media player (wmplayer/vlc) to prevent Windows 10/11 Photos DCOM error
        opened = False
        candidates = [
            Path(os.environ.get("ProgramFiles", r"C:\Program Files")) / "Windows Media Player" / "wmplayer.exe",
            Path(os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)")) / "Windows Media Player" / "wmplayer.exe",
            Path(os.environ.get("ProgramFiles", r"C:\Program Files")) / "VideoLAN" / "VLC" / "vlc.exe",
            Path(os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)")) / "VideoLAN" / "VLC" / "vlc.exe",
        ]
        for exe in candidates:
            if exe.exists():
                try:
                    subprocess.Popen([str(exe), str(p)])
                    opened = True
                    break
                except Exception:
                    pass

        if not opened:
            try:
                os.startfile(str(p))
            except Exception:
                try:
                    subprocess.Popen(["cmd.exe", "/c", "start", "", str(p)], shell=False)
                except Exception as e:
                    logger.warning(f"Không thể mở trình phát hệ thống: {e}")

        # 3. Reveal and highlight file in Windows File Explorer
        try:
            subprocess.Popen(["explorer.exe", f"/select,{str(p)}"])
        except Exception:
            pass

    def _resume_task_from_id(self, task_id: str):
        task = self.repository.get(task_id)
        if not task:
            return
        self.current_task = task
        start_stage = "render_only" if task.status == "review_ready" else "acquire"
        self._run_worker_on_task(task, start_from_stage=start_stage)

    def _open_settings(self):
        dialog = SettingsDialog(settings=self.settings, parent=self)
        dialog.settings_saved.connect(self._on_settings_saved)
        dialog.exec()

    def _on_settings_saved(self, new_settings: AppSettings):
        self.settings = new_settings
        self.chk_auto_pipeline.setChecked(new_settings.auto_pipeline)
        idx = self.combo_quick_remove_mode.findData(new_settings.subtitle_remove_mode)
        if idx >= 0:
            self.combo_quick_remove_mode.setCurrentIndex(idx)
        self._check_system_health()
        self._append_log("Đã áp dụng cấu hình hệ thống mới.")

    def _on_quick_auto_toggled(self, checked: bool):
        self.settings.auto_pipeline = checked
        self.settings.to_file()
        status = "BẬT (Tự động nhận dạng, dịch và xóa phụ đề xuất video luôn)" if checked else "TẮT (Dừng lại tại bước dịch để kiểm tra)"
        self._append_log(f"Chế độ tự động: {status}")

    def _on_quick_remove_mode_changed(self, index: int):
        mode = self.combo_quick_remove_mode.currentData()
        if mode:
            self.settings.subtitle_remove_mode = mode
            self.settings.to_file()
            self._append_log(f"Phương pháp xóa phụ đề tiếng Trung: {mode}")

    def _on_open_output_dir(self):
        out_p = Path(self.settings.output_dir).resolve()
        out_p.mkdir(parents=True, exist_ok=True)
        subprocess.run(["explorer", str(out_p)])

    def _append_log(self, text: str):
        self.txt_log.appendPlainText(text)
