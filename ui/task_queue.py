"""Task queue and history viewer component."""

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path
from typing import List, Optional

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QAbstractItemView,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from storage.task_repository import TaskModel, TaskRepository


class TaskQueueWidget(QWidget):
    """View and manage pipeline tasks, past history, and resume capabilities."""
    task_selected = Signal(str)
    resume_task = Signal(str)

    def __init__(self, repository: Optional[TaskRepository] = None, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.repository = repository or TaskRepository()
        self._setup_ui()
        self.refresh_tasks()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(8)

        # Header
        header = QHBoxLayout()
        title = QLabel("📋 HÀNG ĐỢI & LỊCH SỬ XỬ LÝ VIDEO", self)
        title.setStyleSheet("font-weight: bold; font-size: 14px; color: #38bdf8;")
        header.addWidget(title)
        header.addStretch()

        self.btn_refresh = QPushButton("🔄 Làm mới", self)
        self.btn_refresh.setStyleSheet("background: #334155; color: white; padding: 5px 12px; border-radius: 4px;")
        self.btn_refresh.clicked.connect(self.refresh_tasks)
        header.addWidget(self.btn_refresh)
        layout.addLayout(header)

        # Table
        self.table = QTableWidget(self)
        self.table.setColumnCount(6)
        self.table.setHorizontalHeaderLabels([
            "Tiêu đề", "Nguồn đầu vào", "Trạng thái", "Tiến trình", "Thời gian", "Thao tác"
        ])
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(5, QHeaderView.ResizeToContents)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setStyleSheet(
            "QTableWidget { background-color: #0f172a; color: #f8fafc; gridline-color: #334155; }"
            "QHeaderView::section { background-color: #1e293b; color: #e2e8f0; font-weight: bold; padding: 4px; }"
            "QTableWidget::item:selected { background-color: #2563eb; }"
        )
        layout.addWidget(self.table, stretch=1)

    def refresh_tasks(self):
        """Reload all tasks from database."""
        tasks = self.repository.list_all(limit=50)
        self.table.setRowCount(len(tasks))

        status_names = {
            "pending": "Chờ xử lý",
            "acquiring": "Đang tải video",
            "inspecting": "Đang phân tích",
            "transcribing": "Nhận dạng giọng",
            "translating": "Đang dịch thuật",
            "review_ready": "Chờ duyệt phụ đề",
            "removing_subtitles": "Đang xóa chữ cũ",
            "rendering": "Đang ghi phụ đề",
            "validating": "Đang kiểm tra",
            "completed": "Hoàn thành",
            "failed": "Thất bại",
            "cancelled": "Đã hủy",
        }

        status_colors = {
            "completed": "#10b981",
            "failed": "#ef4444",
            "review_ready": "#f59e0b",
            "cancelled": "#64748b",
        }

        for row_idx, task in enumerate(tasks):
            # Title
            title_item = QTableWidgetItem(task.title)
            self.table.setItem(row_idx, 0, title_item)

            # Source
            src_text = task.source_path if len(task.source_path) < 40 else f"{task.source_path[:37]}..."
            src_item = QTableWidgetItem(src_text)
            src_item.setToolTip(task.source_path)
            self.table.setItem(row_idx, 1, src_item)

            # Status
            st_text = status_names.get(task.status, task.status)
            st_item = QTableWidgetItem(st_text)
            color = status_colors.get(task.status, "#38bdf8")
            st_item.setForeground(Qt.GlobalColor.white)
            st_item.setBackground(Qt.GlobalColor.transparent)
            st_item.setTextAlignment(Qt.AlignCenter)
            self.table.setItem(row_idx, 2, st_item)

            # Progress
            pbar = QProgressBar(self)
            pbar.setValue(task.progress)
            pbar.setStyleSheet("QProgressBar { text-align: center; font-size: 10px; max-width: 100px; height: 16px; }")
            self.table.setCellWidget(row_idx, 3, pbar)

            # Created Time
            time_str = task.created_at[:16].replace("T", " ")
            time_item = QTableWidgetItem(time_str)
            time_item.setTextAlignment(Qt.AlignCenter)
            self.table.setItem(row_idx, 4, time_item)

            # Actions Widget
            actions_widget = QWidget(self)
            act_layout = QHBoxLayout(actions_widget)
            act_layout.setContentsMargins(2, 2, 2, 2)
            act_layout.setSpacing(4)

            # View button
            if task.status == "completed" and task.output_video_path and Path(task.output_video_path).exists():
                btn_play = QPushButton("▶ Mở", actions_widget)
                btn_play.setStyleSheet("background: #2563eb; color: white; padding: 2px 6px; font-size: 11px;")
                btn_play.clicked.connect(lambda _, p=task.output_video_path: self._open_file(p))
                act_layout.addWidget(btn_play)

            # Review / Edit Subtitles
            if task.subtitles:
                btn_edit = QPushButton("✏️ Sửa", actions_widget)
                btn_edit.setStyleSheet("background: #0284c7; color: white; padding: 2px 6px; font-size: 11px;")
                btn_edit.clicked.connect(lambda _, tid=task.id: self.task_selected.emit(tid))
                act_layout.addWidget(btn_edit)

            # Resume button
            if task.status in ("review_ready", "failed"):
                btn_resume = QPushButton("▶ Tiếp tục", actions_widget)
                btn_resume.setStyleSheet("background: #10b981; color: white; padding: 2px 6px; font-size: 11px;")
                btn_resume.clicked.connect(lambda _, tid=task.id: self.resume_task.emit(tid))
                act_layout.addWidget(btn_resume)

            # Folder button
            btn_folder = QPushButton("📁", actions_widget)
            btn_folder.setToolTip("Mở thư mục")
            btn_folder.setStyleSheet("background: #334155; color: white; padding: 2px 6px; font-size: 11px;")
            btn_folder.clicked.connect(lambda _, t=task: self._open_task_folder(t))
            act_layout.addWidget(btn_folder)

            # Delete button
            btn_del = QPushButton("❌", actions_widget)
            btn_del.setToolTip("Xóa tác vụ")
            btn_del.setStyleSheet("background: #dc2626; color: white; padding: 2px 6px; font-size: 11px;")
            btn_del.clicked.connect(lambda _, tid=task.id: self._delete_task(tid))
            act_layout.addWidget(btn_del)

            self.table.setCellWidget(row_idx, 5, actions_widget)

    def _open_file(self, file_path: str):
        p = Path(file_path).resolve()
        if not p.exists():
            return

        # Handle filename with '#' by resolving to safe name if needed
        if "#" in p.name:
            import re, shutil
            safe_name = re.sub(r'#\S+', '', p.stem).strip()
            safe_name = re.sub(r'[#%?*:"<>|/\\\t\r\n]+', '_', safe_name).strip(' ._') + p.suffix
            safe_p = p.parent / safe_name
            if not safe_p.exists():
                try:
                    shutil.copy2(p, safe_p)
                except Exception:
                    safe_p = p
            p = safe_p

        # 1. Launch in dedicated media player (wmplayer/vlc) to prevent Windows Photos DCOM error
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
                except Exception:
                    pass

        # 2. Reveal in File Explorer with the video selected
        try:
            subprocess.Popen(["explorer.exe", f"/select,{str(p)}"])
        except Exception:
            pass

    def _open_task_folder(self, task: TaskModel):
        target = task.workspace_dir or (Path.cwd() / "output")
        if Path(target).exists():
            subprocess.run(["explorer", str(Path(target).resolve())])

    def _delete_task(self, task_id: str):
        reply = QMessageBox.question(
            self,
            "Xác nhận xóa",
            "Bạn có chắc chắn muốn xóa tác vụ này khỏi lịch sử?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )
        if reply == QMessageBox.Yes:
            self.repository.delete(task_id)
            self.refresh_tasks()
