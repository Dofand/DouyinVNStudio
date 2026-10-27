"""Interactive video preview component with transport controls and visual subtitle region selector."""

from __future__ import annotations

from pathlib import Path
from typing import Optional, Tuple

from PySide6.QtCore import QPoint, QRect, QRectF, Qt, QUrl, Signal
from PySide6.QtGui import QBrush, QColor, QFont, QMouseEvent, QPainter, QPaintEvent, QPen
from PySide6.QtMultimedia import QAudioOutput, QMediaPlayer
from PySide6.QtMultimediaWidgets import QVideoWidget
from PySide6.QtWidgets import (
    QComboBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSlider,
    QStyle,
    QVBoxLayout,
    QWidget,
)


class SubtitleAreaOverlay(QWidget):
    """Transparent overlay allowing user to drag and resize subtitle removal box."""
    areaChanged = Signal(tuple)  # (ymin_ratio, ymax_ratio, xmin_ratio, xmax_ratio)

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.setAttribute(Qt.WA_TransparentForMouseEvents, False)
        # Default ratio (ymin, ymax, xmin, xmax)
        self.ymin_r = 0.75
        self.ymax_r = 0.94
        self.xmin_r = 0.05
        self.xmax_r = 0.95

        self._dragging = False
        self._drag_start = QPoint()

    def set_ratios(self, ymin: float, ymax: float, xmin: float, xmax: float):
        self.ymin_r = max(0.0, min(1.0, ymin))
        self.ymax_r = max(0.0, min(1.0, ymax))
        self.xmin_r = max(0.0, min(1.0, xmin))
        self.xmax_r = max(0.0, min(1.0, xmax))
        self.update()
        self.areaChanged.emit((self.ymin_r, self.ymax_r, self.xmin_r, self.xmax_r))

    def get_pixel_rect(self) -> QRect:
        w = self.width()
        h = self.height()
        x = int(self.xmin_r * w)
        y = int(self.ymin_r * h)
        box_w = max(10, int((self.xmax_r - self.xmin_r) * w))
        box_h = max(10, int((self.ymax_r - self.ymin_r) * h))
        return QRect(x, y, box_w, box_h)

    def paintEvent(self, event: QPaintEvent):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        rect = self.get_pixel_rect()

        # Dim areas outside the box slightly
        dim_color = QColor(0, 0, 0, 80)
        # Top
        painter.fillRect(0, 0, self.width(), rect.top(), dim_color)
        # Bottom
        painter.fillRect(0, rect.bottom(), self.width(), self.height() - rect.bottom(), dim_color)
        # Left
        painter.fillRect(0, rect.top(), rect.left(), rect.height(), dim_color)
        # Right
        painter.fillRect(rect.right(), rect.top(), self.width() - rect.right(), rect.height(), dim_color)

        # Highlight subtitle box
        pen = QPen(QColor(255, 69, 58, 220), 2, Qt.DashLine)
        painter.setPen(pen)
        painter.setBrush(QBrush(QColor(255, 69, 58, 40)))
        painter.drawRect(rect)

        # Draw label
        painter.setPen(QColor(255, 255, 255, 240))
        font = QFont("Segoe UI", 9, QFont.Bold)
        painter.setFont(font)
        painter.drawText(rect.adjusted(8, 8, -8, -8), Qt.AlignTop | Qt.AlignLeft, "VÙNG XÓA PHỤ ĐỀ TRUNG")

    def mousePressEvent(self, event: QMouseEvent):
        if event.button() == Qt.LeftButton:
            self._dragging = True
            self._drag_start = event.pos()
            # Set top-left
            self.xmin_r = max(0.0, min(1.0, event.pos().x() / max(1, self.width())))
            self.ymin_r = max(0.0, min(1.0, event.pos().y() / max(1, self.height())))
            self.xmax_r = self.xmin_r
            self.ymax_r = self.ymin_r
            self.update()

    def mouseMoveEvent(self, event: QMouseEvent):
        if self._dragging:
            cur_x_r = max(0.0, min(1.0, event.pos().x() / max(1, self.width())))
            cur_y_r = max(0.0, min(1.0, event.pos().y() / max(1, self.height())))

            self.xmin_r = min(self._drag_start.x() / max(1, self.width()), cur_x_r)
            self.xmax_r = max(self._drag_start.x() / max(1, self.width()), cur_x_r)
            self.ymin_r = min(self._drag_start.y() / max(1, self.height()), cur_y_r)
            self.ymax_r = max(self._drag_start.y() / max(1, self.height()), cur_y_r)
            self.update()

    def mouseReleaseEvent(self, event: QMouseEvent):
        if event.button() == Qt.LeftButton and self._dragging:
            self._dragging = False
            # Ensure minimum size
            if (self.xmax_r - self.xmin_r) < 0.05:
                self.xmax_r = min(1.0, self.xmin_r + 0.1)
            if (self.ymax_r - self.ymin_r) < 0.05:
                self.ymax_r = min(1.0, self.ymin_r + 0.08)
            self.update()
            self.areaChanged.emit((self.ymin_r, self.ymax_r, self.xmin_r, self.xmax_r))


class VideoPreviewWidget(QWidget):
    """Full-featured video preview player with transport controls and metadata header."""

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self._current_path: Optional[str] = None
        self._duration_ms: int = 0

        self._setup_ui()
        self._setup_player()

    def _setup_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(6)

        # Video container
        self.video_container = QWidget(self)
        self.video_container.setStyleSheet("background-color: #0b0f19; border-radius: 8px;")
        video_stack = QVBoxLayout(self.video_container)
        video_stack.setContentsMargins(0, 0, 0, 0)

        self.video_widget = QVideoWidget(self.video_container)
        video_stack.addWidget(self.video_widget)

        # Overlay for region selection
        self.overlay = SubtitleAreaOverlay(self.video_widget)
        self.overlay.hide()

        main_layout.addWidget(self.video_container, stretch=1)

        # Info bar
        self.info_label = QLabel("Chưa mở video nào.", self)
        self.info_label.setStyleSheet("color: #94a3b8; font-size: 11px; padding: 2px 4px;")
        main_layout.addWidget(self.info_label)

        # Progress slider & Time
        slider_row = QHBoxLayout()
        slider_row.setContentsMargins(4, 0, 4, 0)

        self.slider = QSlider(Qt.Horizontal, self)
        self.slider.setRange(0, 1000)
        self.slider.sliderMoved.connect(self._on_seek)
        slider_row.addWidget(self.slider, stretch=1)

        self.time_label = QLabel("00:00 / 00:00", self)
        self.time_label.setStyleSheet("color: #e2e8f0; font-family: Consolas, monospace; font-size: 11px;")
        slider_row.addWidget(self.time_label)

        main_layout.addLayout(slider_row)

        # Controls row
        ctrl_row = QHBoxLayout()
        ctrl_row.setContentsMargins(4, 0, 4, 0)

        self.btn_play = QPushButton("▶ Phát", self)
        self.btn_play.setStyleSheet(
            "QPushButton { background: #2563eb; color: white; border-radius: 5px; padding: 5px 12px; font-weight: bold; } "
            "QPushButton:hover { background: #1d4ed8; }"
        )
        self.btn_play.clicked.connect(self.toggle_play)
        ctrl_row.addWidget(self.btn_play)

        # Subtitle region selector toggle
        self.btn_toggle_mask = QPushButton("🎯 Chọn vùng xóa chữ", self)
        self.btn_toggle_mask.setCheckable(True)
        self.btn_toggle_mask.toggled.connect(self._toggle_mask_overlay)
        self.btn_toggle_mask.setStyleSheet(
            "QPushButton { background: #334155; color: #f1f5f9; border-radius: 5px; padding: 5px 10px; } "
            "QPushButton:checked { background: #ef4444; color: white; }"
        )
        ctrl_row.addWidget(self.btn_toggle_mask)

        # Preset regions
        self.preset_combo = QComboBox(self)
        self.preset_combo.addItems([
            "Vùng: Dưới đáy (75% - 95%)",
            "Vùng: Nửa dưới (50% - 95%)",
            "Vùng: Tiêu đề trên (5% - 25%)",
            "Vùng: Tự do bằng chuột"
        ])
        self.preset_combo.currentIndexChanged.connect(self._on_preset_changed)
        self.preset_combo.setStyleSheet("background: #1e293b; color: #f8fafc; border-radius: 5px; padding: 4px;")
        ctrl_row.addWidget(self.preset_combo)

        ctrl_row.addStretch()

        # Volume
        vol_label = QLabel("🔊", self)
        ctrl_row.addWidget(vol_label)
        self.vol_slider = QSlider(Qt.Horizontal, self)
        self.vol_slider.setRange(0, 100)
        self.vol_slider.setValue(80)
        self.vol_slider.setMaximumWidth(90)
        self.vol_slider.valueChanged.connect(self._on_volume_changed)
        ctrl_row.addWidget(self.vol_slider)

        main_layout.addLayout(ctrl_row)

    def _setup_player(self):
        self.player = QMediaPlayer(self)
        self.audio_output = QAudioOutput(self)
        self.player.setAudioOutput(self.audio_output)
        self.player.setVideoOutput(self.video_widget)
        self.audio_output.setVolume(0.8)

        self.player.positionChanged.connect(self._on_position_changed)
        self.player.durationChanged.connect(self._on_duration_changed)
        self.player.playbackStateChanged.connect(self._on_state_changed)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.overlay.setGeometry(0, 0, self.video_widget.width(), self.video_widget.height())

    def load_video(self, video_path: str | Path, info_text: str = ""):
        """Load video file into player."""
        p = Path(video_path).resolve()
        if not p.exists():
            return
        self._current_path = str(p)
        self.player.setSource(QUrl.fromLocalFile(str(p)))
        if info_text:
            self.info_label.setText(info_text)
        else:
            self.info_label.setText(f"File: {p.name}")
        self.overlay.setGeometry(0, 0, self.video_widget.width(), self.video_widget.height())

    def toggle_play(self):
        if self.player.playbackState() == QMediaPlayer.PlayingState:
            self.player.pause()
        else:
            self.player.play()

    def _on_state_changed(self, state):
        if state == QMediaPlayer.PlayingState:
            self.btn_play.setText("⏸ Tạm dừng")
        else:
            self.btn_play.setText("▶ Phát")

    def _on_duration_changed(self, duration_ms: int):
        self._duration_ms = duration_ms
        self._update_time_label(self.player.position(), duration_ms)

    def _on_position_changed(self, pos_ms: int):
        if self._duration_ms > 0:
            val = int(pos_ms / self._duration_ms * 1000)
            self.slider.blockSignals(True)
            self.slider.setValue(val)
            self.slider.blockSignals(False)
        self._update_time_label(pos_ms, self._duration_ms)

    def _on_seek(self, value: int):
        if self._duration_ms > 0:
            target_ms = int(value / 1000.0 * self._duration_ms)
            self.player.setPosition(target_ms)

    def _on_volume_changed(self, value: int):
        self.audio_output.setVolume(value / 100.0)

    def _update_time_label(self, pos_ms: int, dur_ms: int):
        def fmt(ms: int) -> str:
            secs = ms // 1000
            m = secs // 60
            s = secs % 60
            return f"{m:02d}:{s:02d}"
        self.time_label.setText(f"{fmt(pos_ms)} / {fmt(dur_ms)}")

    def _toggle_mask_overlay(self, checked: bool):
        if checked:
            self.overlay.setGeometry(0, 0, self.video_widget.width(), self.video_widget.height())
            self.overlay.show()
            self.overlay.raise_()
        else:
            self.overlay.hide()

    def _on_preset_changed(self, index: int):
        if index == 0:  # Bottom 75-95%
            self.overlay.set_ratios(0.75, 0.95, 0.05, 0.95)
        elif index == 1:  # Lower half 50-95%
            self.overlay.set_ratios(0.50, 0.95, 0.05, 0.95)
        elif index == 2:  # Top 5-25%
            self.overlay.set_ratios(0.05, 0.25, 0.05, 0.95)
        self.btn_toggle_mask.setChecked(True)

    def get_subtitle_area_ratio(self) -> Tuple[float, float, float, float]:
        """Return (ymin, ymax, xmin, xmax) ratio."""
        return (self.overlay.ymin_r, self.overlay.ymax_r, self.overlay.xmin_r, self.overlay.xmax_r)
