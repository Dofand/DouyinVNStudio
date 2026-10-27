"""Main entry point for DouyinVN Studio desktop application."""

from __future__ import annotations

import logging
import os
import sys
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication, QMessageBox

from config.settings import AppSettings
from storage.database import init_db
from ui.main_window import MainWindow

# Configure global UTF-8 encoding for Windows console and loggers
os.environ["PYTHONIOENCODING"] = "utf-8"
os.environ["HF_HUB_DISABLE_SYMLINKS_WARNING"] = "1"

LOG_DIR = Path(__file__).resolve().parent / "logs"
LOG_DIR.mkdir(parents=True, exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] (%(name)s) %(message)s",
    handlers=[
        logging.FileHandler(LOG_DIR / "app.log", encoding="utf-8"),
        logging.StreamHandler(sys.stdout),
    ],
)
logger = logging.getLogger("DouyinVNStudio")


def setup_exception_hook():
    """Catch uncaught exceptions and display a user-friendly dialog."""
    def excepthook(exc_type, exc_value, exc_traceback):
        if issubclass(exc_type, KeyboardInterrupt):
            sys.__excepthook__(exc_type, exc_value, exc_traceback)
            return

        import traceback
        err_msg = "".join(traceback.format_exception(exc_type, exc_value, exc_traceback))
        logger.error(f"Uncaught exception:\n{err_msg}")

        # Show message box if QApplication exists
        if QApplication.instance():
            QMessageBox.critical(
                None,
                "Lỗi hệ thống không mong muốn",
                f"Đã xảy ra sự cố không xác định:\n\n{exc_value}\n\nXem chi tiết trong logs/app.log"
            )
    sys.excepthook = excepthook


def main():
    """Initialize environment, database, and launch application window."""
    setup_exception_hook()

    # Enable High DPI scaling
    QApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
    )

    app = QApplication(sys.argv)
    app.setApplicationName("DouyinVN Studio")
    app.setApplicationDisplayName("DouyinVN Studio")
    app.setOrganizationName("DouyinVN")

    # Initialize SQLite database
    init_db()

    # Load and ensure settings
    settings = AppSettings.load()
    settings.ensure_directories()

    window = MainWindow()
    window.show()

    logger.info("DouyinVN Studio started successfully.")
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
