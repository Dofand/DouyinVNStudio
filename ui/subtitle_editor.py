"""Interactive Subtitle Editor allowing editing, time shifting, adding/removing lines, and approval."""

from __future__ import annotations

from typing import List, Optional

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QDoubleSpinBox,
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from core.speech_to_text import seconds_to_srt_time, srt_time_to_seconds
from storage.task_repository import SubtitleItem


class SubtitleEditorWidget(QWidget):
    """Subtitle table editor with timeline controls and bilingual editing."""
    subtitles_changed = Signal(list)
    proceed_to_render = Signal(list)

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.subtitles: List[SubtitleItem] = []
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(8)

        # Header bar
        header_row = QHBoxLayout()
        title_label = QLabel("✍️ BẢNG CHỈNH SỬA PHỤ ĐỀ SONG NGỮ (TRUNG - VIỆT)", self)
        title_label.setStyleSheet("font-weight: bold; font-size: 14px; color: #38bdf8;")
        header_row.addWidget(title_label)
        header_row.addStretch()

        self.count_label = QLabel("0 câu", self)
        self.count_label.setStyleSheet("color: #94a3b8; font-size: 12px;")
        header_row.addWidget(self.count_label)
        layout.addLayout(header_row)

        # Toolbar: Search, Add, Delete, Shift
        toolbar = QHBoxLayout()
        toolbar.setSpacing(6)

        self.search_input = QLineEdit(self)
        self.search_input.setPlaceholderText("🔍 Tìm kiếm nội dung tiếng Trung hoặc tiếng Việt...")
        self.search_input.textChanged.connect(self._filter_table)
        self.search_input.setStyleSheet("background: #1e293b; color: white; padding: 5px; border-radius: 4px;")
        toolbar.addWidget(self.search_input, stretch=2)

        self.btn_add = QPushButton("➕ Thêm dòng", self)
        self.btn_add.setStyleSheet("background: #059669; color: white; padding: 5px 10px; border-radius: 4px; font-weight: bold;")
        self.btn_add.clicked.connect(self._add_row)
        toolbar.addWidget(self.btn_add)

        self.btn_del = QPushButton("🗑️ Xóa dòng", self)
        self.btn_del.setStyleSheet("background: #dc2626; color: white; padding: 5px 10px; border-radius: 4px;")
        self.btn_del.clicked.connect(self._delete_selected_rows)
        toolbar.addWidget(self.btn_del)

        # Shift time controls
        shift_label = QLabel("Lệch thời gian (s):", self)
        shift_label.setStyleSheet("color: #cbd5e1;")
        toolbar.addWidget(shift_label)

        self.spin_shift = QDoubleSpinBox(self)
        self.spin_shift.setRange(-60.0, 60.0)
        self.spin_shift.setSingleStep(0.2)
        self.spin_shift.setValue(0.0)
        self.spin_shift.setStyleSheet("background: #1e293b; color: white; padding: 4px;")
        toolbar.addWidget(self.spin_shift)

        self.btn_apply_shift = QPushButton("Áp dụng dịch", self)
        self.btn_apply_shift.setStyleSheet("background: #475569; color: white; padding: 5px 8px; border-radius: 4px;")
        self.btn_apply_shift.clicked.connect(self._apply_time_shift)
        toolbar.addWidget(self.btn_apply_shift)

        layout.addLayout(toolbar)

        # Table
        self.table = QTableWidget(self)
        self.table.setColumnCount(6)
        self.table.setHorizontalHeaderLabels([
            "STT", "Bắt đầu", "Kết thúc", "Tiếng Trung (Gốc)", "Tiếng Việt (Bản dịch)", "Đã duyệt"
        ])
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(3, QHeaderView.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(4, QHeaderView.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(5, QHeaderView.ResizeToContents)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setStyleSheet(
            "QTableWidget { background-color: #0f172a; color: #f8fafc; gridline-color: #334155; }"
            "QHeaderView::section { background-color: #1e293b; color: #e2e8f0; font-weight: bold; padding: 4px; }"
            "QTableWidget::item:selected { background-color: #2563eb; }"
        )
        self.table.cellChanged.connect(self._on_cell_changed)
        layout.addWidget(self.table, stretch=1)

        # Footer Actions
        footer = QHBoxLayout()
        self.btn_save = QPushButton("💾 Lưu thay đổi", self)
        self.btn_save.setStyleSheet("background: #3b82f6; color: white; font-weight: bold; padding: 8px 16px; border-radius: 6px;")
        self.btn_save.clicked.connect(self._save_changes)
        footer.addWidget(self.btn_save)

        footer.addStretch()

        self.btn_confirm_render = QPushButton("🚀 Xác nhận bản dịch & Xuất Video", self)
        self.btn_confirm_render.setStyleSheet(
            "QPushButton { background: #10b981; color: white; font-weight: bold; font-size: 13px; padding: 8px 20px; border-radius: 6px; } "
            "QPushButton:hover { background: #059669; }"
        )
        self.btn_confirm_render.clicked.connect(self._on_confirm_render)
        footer.addWidget(self.btn_confirm_render)

        layout.addLayout(footer)

    def load_subtitles(self, subtitles: List[SubtitleItem]):
        """Populate table with SubtitleItems."""
        self.subtitles = list(subtitles)
        self._populate_table()

    def _populate_table(self):
        self.table.blockSignals(True)
        self.table.setRowCount(len(self.subtitles))

        for row_idx, item in enumerate(self.subtitles):
            # STT
            stt_item = QTableWidgetItem(str(item.id))
            stt_item.setTextAlignment(Qt.AlignCenter)
            stt_item.setFlags(stt_item.flags() & ~Qt.ItemIsEditable)
            self.table.setItem(row_idx, 0, stt_item)

            # Start
            start_item = QTableWidgetItem(seconds_to_srt_time(item.start))
            start_item.setTextAlignment(Qt.AlignCenter)
            self.table.setItem(row_idx, 1, start_item)

            # End
            end_item = QTableWidgetItem(seconds_to_srt_time(item.end))
            end_item.setTextAlignment(Qt.AlignCenter)
            self.table.setItem(row_idx, 2, end_item)

            # Text ZH
            zh_item = QTableWidgetItem(item.text_zh)
            self.table.setItem(row_idx, 3, zh_item)

            # Text VI
            vi_item = QTableWidgetItem(item.text_vi)
            self.table.setItem(row_idx, 4, vi_item)

            # Verified checkbox
            chk_item = QTableWidgetItem()
            chk_item.setFlags(Qt.ItemIsUserCheckable | Qt.ItemIsEnabled)
            chk_item.setCheckState(Qt.Checked if item.verified else Qt.Unchecked)
            chk_item.setTextAlignment(Qt.AlignCenter)
            self.table.setItem(row_idx, 5, chk_item)

        self.table.blockSignals(False)
        self.count_label.setText(f"{len(self.subtitles)} câu")

    def _on_cell_changed(self, row: int, col: int):
        if row >= len(self.subtitles):
            return

        item = self.subtitles[row]
        if col == 1:  # Start
            text = self.table.item(row, col).text()
            item.start = srt_time_to_seconds(text)
        elif col == 2:  # End
            text = self.table.item(row, col).text()
            item.end = srt_time_to_seconds(text)
        elif col == 3:  # ZH
            item.text_zh = self.table.item(row, col).text()
        elif col == 4:  # VI
            item.text_vi = self.table.item(row, col).text()
        elif col == 5:  # Verified
            item.verified = (self.table.item(row, col).checkState() == Qt.Checked)

    def _add_row(self):
        new_id = len(self.subtitles) + 1
        last_end = self.subtitles[-1].end if self.subtitles else 0.0
        new_item = SubtitleItem(
            id=new_id,
            start=round(last_end, 2),
            end=round(last_end + 2.0, 2),
            text_zh="新字幕",
            text_vi="Phụ đề mới",
            verified=False,
        )
        self.subtitles.append(new_item)
        self._populate_table()
        self.table.scrollToBottom()

    def _delete_selected_rows(self):
        selected_indexes = sorted(set(idx.row() for idx in self.table.selectedIndexes()), reverse=True)
        if not selected_indexes:
            return

        for row in selected_indexes:
            if row < len(self.subtitles):
                del self.subtitles[row]

        # Re-index
        for idx, item in enumerate(self.subtitles, start=1):
            item.id = idx

        self._populate_table()

    def _apply_time_shift(self):
        shift = self.spin_shift.value()
        if shift == 0.0:
            return

        for item in self.subtitles:
            item.start = max(0.0, round(item.start + shift, 3))
            item.end = max(item.start + 0.1, round(item.end + shift, 3))

        self._populate_table()
        QMessageBox.information(self, "Thông báo", f"Đã dịch chuyển thời gian {shift:+.2f}s cho toàn bộ phụ đề.")

    def _filter_table(self, query: str):
        query = query.strip().lower()
        for row in range(self.table.rowCount()):
            zh = self.table.item(row, 3).text().lower() if self.table.item(row, 3) else ""
            vi = self.table.item(row, 4).text().lower() if self.table.item(row, 4) else ""
            matches = (query in zh) or (query in vi)
            self.table.setRowHidden(row, not matches)

    def _save_changes(self):
        self.subtitles_changed.emit(self.subtitles)
        QMessageBox.information(self, "Thành công", "Đã lưu toàn bộ thay đổi phụ đề vào cơ sở dữ liệu.")

    def _on_confirm_render(self):
        if not self.subtitles:
            QMessageBox.warning(self, "Cảnh báo", "Danh sách phụ đề đang rỗng.")
            return

        reply = QMessageBox.question(
            self,
            "Xác nhận xuất video",
            f"Bạn có chắc chắn muốn xuất video với {len(self.subtitles)} câu phụ đề tiếng Việt?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.Yes
        )
        if reply == QMessageBox.Yes:
            self.proceed_to_render.emit(self.subtitles)
