"""Settings dialog for configuring DouyinVN Studio parameters, paths, models, and styling."""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from config.settings import AppSettings, SubtitleStyle


class SettingsDialog(QDialog):
    """Configuration dialog for system paths, AI models, subtitle styling, and pipeline modes."""
    settings_saved = Signal(AppSettings)

    def __init__(self, settings: Optional[AppSettings] = None, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.settings = settings or AppSettings.load()
        self.setWindowTitle("⚙️ Cài đặt hệ thống - DouyinVN Studio")
        self.resize(650, 520)
        self.setStyleSheet("""
            QDialog { background-color: #0f172a; color: #f8fafc; }
            QLabel { color: #e2e8f0; font-size: 12px; }
            QLineEdit, QComboBox, QSpinBox { background-color: #1e293b; color: white; border: 1px solid #334155; border-radius: 4px; padding: 4px 8px; }
            QGroupBox { border: 1px solid #334155; border-radius: 6px; margin-top: 10px; font-weight: bold; color: #38bdf8; padding-top: 15px; }
            QGroupBox::title { subcontrol-origin: margin; left: 10px; padding: 0 4px; }
            QPushButton { background-color: #334155; color: white; border-radius: 4px; padding: 5px 12px; }
            QPushButton:hover { background-color: #475569; }
            QTabBar::tab { background: #1e293b; color: #94a3b8; padding: 8px 16px; border-top-left-radius: 4px; border-top-right-radius: 4px; }
            QTabBar::tab:selected { background: #0284c7; color: white; font-weight: bold; }
        """)

        self._setup_ui()
        self._load_values()

    def _setup_ui(self):
        main_layout = QVBoxLayout(self)

        tabs = QTabWidget(self)

        # Tab 1: Công cụ & Đường dẫn
        tab_paths = QWidget()
        layout_paths = QVBoxLayout(tab_paths)

        gb_tools = QGroupBox("Đường dẫn thực thi (Executables)", tab_paths)
        form_tools = QFormLayout(gb_tools)

        # FFmpeg
        row_ffmpeg = QHBoxLayout()
        self.txt_ffmpeg = QLineEdit(self)
        btn_browse_ffmpeg = QPushButton("Chọn...", self)
        btn_browse_ffmpeg.clicked.connect(lambda: self._browse_file(self.txt_ffmpeg, "Chọn ffmpeg.exe", "ffmpeg.exe (*.exe)"))
        row_ffmpeg.addWidget(self.txt_ffmpeg)
        row_ffmpeg.addWidget(btn_browse_ffmpeg)
        form_tools.addRow("FFmpeg Path:", row_ffmpeg)

        # FFprobe
        row_ffprobe = QHBoxLayout()
        self.txt_ffprobe = QLineEdit(self)
        btn_browse_ffprobe = QPushButton("Chọn...", self)
        btn_browse_ffprobe.clicked.connect(lambda: self._browse_file(self.txt_ffprobe, "Chọn ffprobe.exe", "ffprobe.exe (*.exe)"))
        row_ffprobe.addWidget(self.txt_ffprobe)
        row_ffprobe.addWidget(btn_browse_ffprobe)
        form_tools.addRow("FFprobe Path:", row_ffprobe)

        # VSR Path
        row_vsr = QHBoxLayout()
        self.txt_vsr = QLineEdit(self)
        self.txt_vsr.setPlaceholderText("Để trống nếu chưa cài hoặc dùng xóa làm mờ FFmpeg")
        btn_browse_vsr = QPushButton("Chọn thư mục / file...", self)
        btn_browse_vsr.clicked.connect(lambda: self._browse_dir_or_file(self.txt_vsr))
        row_vsr.addWidget(self.txt_vsr)
        row_vsr.addWidget(btn_browse_vsr)
        form_tools.addRow("VSR (Video-Subtitle-Remover):", row_vsr)

        layout_paths.addWidget(gb_tools)

        # Output / Workspace dirs
        gb_dirs = QGroupBox("Thư mục lưu trữ", tab_paths)
        form_dirs = QFormLayout(gb_dirs)

        row_out = QHBoxLayout()
        self.txt_out = QLineEdit(self)
        btn_browse_out = QPushButton("Chọn...", self)
        btn_browse_out.clicked.connect(lambda: self._browse_dir(self.txt_out, "Chọn thư mục xuất video"))
        row_out.addWidget(self.txt_out)
        row_out.addWidget(btn_browse_out)
        form_dirs.addRow("Thư mục video thành phẩm:", row_out)

        row_models = QHBoxLayout()
        self.txt_models = QLineEdit(self)
        btn_browse_models = QPushButton("Chọn...", self)
        btn_browse_models.clicked.connect(lambda: self._browse_dir(self.txt_models, "Chọn thư mục Cache Model"))
        row_models.addWidget(self.txt_models)
        row_models.addWidget(btn_browse_models)
        form_dirs.addRow("Thư mục Cache Model:", row_models)

        layout_paths.addWidget(gb_dirs)
        layout_paths.addStretch()
        tabs.addTab(tab_paths, "📁 Đường dẫn & Công cụ")

        # Tab 2: Cấu hình AI & Xử lý
        tab_ai = QWidget()
        layout_ai = QVBoxLayout(tab_ai)

        gb_whisper = QGroupBox("Nhận dạng tiếng Trung (Faster-Whisper)", tab_ai)
        form_whisper = QFormLayout(gb_whisper)

        self.combo_whisper_model = QComboBox(self)
        self.combo_whisper_model.addItems(["tiny", "base", "small", "medium"])
        form_whisper.addRow("Kích thước Model:", self.combo_whisper_model)

        self.combo_whisper_device = QComboBox(self)
        self.combo_whisper_device.addItems(["cpu", "cuda", "auto"])
        form_whisper.addRow("Thiết bị xử lý:", self.combo_whisper_device)

        self.combo_whisper_compute = QComboBox(self)
        self.combo_whisper_compute.addItems(["int8", "float16", "float32"])
        form_whisper.addRow("Kiểu tính toán (Compute):", self.combo_whisper_compute)

        layout_ai.addWidget(gb_whisper)

        gb_sub_remove = QGroupBox("Phương pháp xóa phụ đề tiếng Trung", tab_ai)
        form_sub_remove = QFormLayout(gb_sub_remove)

        self.combo_zone_mode = QComboBox(self)
        self.combo_zone_mode.addItem("Tự động nhận diện vùng chữ (Auto Detect)", "auto")
        self.combo_zone_mode.addItem("Tiêu đề trên màn hình (Top: 6%-16%)", "top")
        self.combo_zone_mode.addItem("Phụ đề dưới màn hình (Bottom: 70%-92%)", "bottom")
        self.combo_zone_mode.addItem("Cả hai vùng (Top & Bottom)", "both")
        self.combo_zone_mode.addItem("Vùng chuột tùy chọn (Custom Drag)", "custom")
        form_sub_remove.addRow("Vị trí chữ cần xóa:", self.combo_zone_mode)

        self.combo_remove_mode = QComboBox(self)
        self.combo_remove_mode.addItem("Bỏ qua xóa (Ghi đè phụ đề mới trực tiếp)", "skip")
        self.combo_remove_mode.addItem("Làm mờ vùng chữ bằng FFmpeg (Boxblur)", "ffmpeg_blur")
        self.combo_remove_mode.addItem("Xóa vùng chữ bằng FFmpeg (Delogo)", "ffmpeg_delogo")
        self.combo_remove_mode.addItem("Phục hồi AI nâng cao bằng VSR", "vsr")
        form_sub_remove.addRow("Phương pháp xóa chữ:", self.combo_remove_mode)

        self.combo_vsr_inpaint = QComboBox(self)
        self.combo_vsr_inpaint.addItems(["sttn-auto", "sttn-det", "lama", "propainter", "opencv"])
        form_sub_remove.addRow("Thuật toán VSR Inpaint:", self.combo_vsr_inpaint)

        layout_ai.addWidget(gb_sub_remove)

        gb_pipe = QGroupBox("Quy trình tự động", tab_ai)
        form_pipe = QFormLayout(gb_pipe)

        self.chk_auto = QCheckBox("Tự động xử lý toàn bộ (Không dừng lại để duyệt bản dịch)", self)
        form_pipe.addRow(self.chk_auto)

        self.chk_mock = QCheckBox("Chế độ Mock (Kiểm thử nhanh không tải model AI)", self)
        form_pipe.addRow(self.chk_mock)

        layout_ai.addWidget(gb_pipe)
        layout_ai.addStretch()
        tabs.addTab(tab_ai, "🤖 Trí tuệ nhân tạo (AI)")

        # Tab 3: Kiểu dáng phụ đề (Styling)
        tab_style = QWidget()
        layout_style = QVBoxLayout(tab_style)

        gb_style = QGroupBox("Định dạng phụ đề tiếng Việt xuất ra", tab_style)
        form_style = QFormLayout(gb_style)

        self.combo_font = QComboBox(self)
        self.combo_font.addItems(["Segoe UI", "Arial", "Tahoma", "Verdana", "Roboto"])
        form_style.addRow("Font chữ:", self.combo_font)

        self.spin_font_size = QSpinBox(self)
        self.spin_font_size.setRange(12, 72)
        form_style.addRow("Cỡ chữ (Font Size):", self.spin_font_size)

        self.txt_primary_color = QLineEdit(self)
        form_style.addRow("Màu chữ chính (ASS format):", self.txt_primary_color)

        self.txt_outline_color = QLineEdit(self)
        form_style.addRow("Màu viền (Outline):", self.txt_outline_color)

        self.spin_margin_v = QSpinBox(self)
        self.spin_margin_v.setRange(5, 300)
        form_style.addRow("Lề dưới (MarginV):", self.spin_margin_v)

        self.chk_bold = QCheckBox("In đậm (Bold)", self)
        form_style.addRow(self.chk_bold)

        layout_style.addWidget(gb_style)
        layout_style.addStretch()
        tabs.addTab(tab_style, "🎨 Kiểu dáng phụ đề")

        main_layout.addWidget(tabs)

        # Buttons
        btn_box = QHBoxLayout()
        btn_box.addStretch()

        btn_cancel = QPushButton("Hủy bỏ", self)
        btn_cancel.clicked.connect(self.reject)
        btn_box.addWidget(btn_cancel)

        btn_save = QPushButton("💾 Lưu cài đặt", self)
        btn_save.setStyleSheet("background: #0284c7; color: white; font-weight: bold; padding: 6px 18px;")
        btn_save.clicked.connect(self._save_values)
        btn_box.addWidget(btn_save)

        main_layout.addLayout(btn_box)

    def _browse_file(self, target_line_edit: QLineEdit, title: str, filter_str: str):
        path, _ = QFileDialog.getOpenFileName(self, title, "", filter_str)
        if path:
            target_line_edit.setText(path)

    def _browse_dir(self, target_line_edit: QLineEdit, title: str):
        path = QFileDialog.getExistingDirectory(self, title)
        if path:
            target_line_edit.setText(path)

    def _browse_dir_or_file(self, target_line_edit: QLineEdit):
        path = QFileDialog.getExistingDirectory(self, "Chọn thư mục VSR chứa backend/main.py")
        if path:
            target_line_edit.setText(path)

    def _load_values(self):
        s = self.settings
        self.txt_ffmpeg.setText(s.ffmpeg_path)
        self.txt_ffprobe.setText(s.ffprobe_path)
        self.txt_vsr.setText(s.vsr_path)
        self.txt_out.setText(s.output_dir)
        self.txt_models.setText(s.models_cache_dir)

        # Whisper
        self.combo_whisper_model.setCurrentText(s.whisper_model)
        self.combo_whisper_device.setCurrentText(s.whisper_device)
        self.combo_whisper_compute.setCurrentText(s.whisper_compute_type)

        # Remove mode & zone
        z_idx = self.combo_zone_mode.findData(s.subtitle_zone_mode)
        if z_idx >= 0:
            self.combo_zone_mode.setCurrentIndex(z_idx)
        idx = self.combo_remove_mode.findData(s.subtitle_remove_mode)
        if idx >= 0:
            self.combo_remove_mode.setCurrentIndex(idx)
        self.combo_vsr_inpaint.setCurrentText(s.vsr_inpaint_mode)

        self.chk_auto.setChecked(s.auto_pipeline)
        self.chk_mock.setChecked(s.mock_mode)

        # Subtitle styling
        st = s.subtitle_style
        self.combo_font.setCurrentText(st.font_name)
        self.spin_font_size.setValue(st.font_size)
        self.txt_primary_color.setText(st.primary_color)
        self.txt_outline_color.setText(st.outline_color)
        self.spin_margin_v.setValue(st.margin_v)
        self.chk_bold.setChecked(st.bold)

    def _save_values(self):
        s = self.settings
        s.ffmpeg_path = self.txt_ffmpeg.text().strip()
        s.ffprobe_path = self.txt_ffprobe.text().strip()
        s.vsr_path = self.txt_vsr.text().strip()
        s.output_dir = self.txt_out.text().strip()
        s.models_cache_dir = self.txt_models.text().strip()

        s.whisper_model = self.combo_whisper_model.currentText()
        s.whisper_device = self.combo_whisper_device.currentText()
        s.whisper_compute_type = self.combo_whisper_compute.currentText()

        s.subtitle_zone_mode = self.combo_zone_mode.currentData() or "auto"
        s.subtitle_remove_mode = self.combo_remove_mode.currentData()
        s.vsr_inpaint_mode = self.combo_vsr_inpaint.currentText()

        s.auto_pipeline = self.chk_auto.isChecked()
        s.mock_mode = self.chk_mock.isChecked()

        # Styling
        s.subtitle_style.font_name = self.combo_font.currentText()
        s.subtitle_style.font_size = self.spin_font_size.value()
        s.subtitle_style.primary_color = self.txt_primary_color.text().strip() or "&H00FFFFFF"
        s.subtitle_style.outline_color = self.txt_outline_color.text().strip() or "&H00000000"
        s.subtitle_style.margin_v = self.spin_margin_v.value()
        s.subtitle_style.bold = self.chk_bold.isChecked()

        s.ensure_directories()
        s.to_file()
        self.settings_saved.emit(s)
        QMessageBox.information(self, "Thành công", "Đã lưu cài đặt thành công!")
        self.accept()
