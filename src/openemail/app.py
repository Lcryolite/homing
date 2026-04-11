import sys
from pathlib import Path

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QGuiApplication
from PyQt6.QtWidgets import QApplication

from openemail.config import settings
from openemail.storage.database import db

_app: QApplication | None = None
_main_window = None


def _styles_dir() -> Path:
    return Path(__file__).parent / "ui" / "resources" / "styles"


def _resolve_theme() -> str:
    theme = settings.theme
    if theme == "system":
        color_scheme = QGuiApplication.styleHints().colorScheme()
        if color_scheme == Qt.ColorScheme.Dark:
            return "dark"
        return "light"
    return theme


def apply_theme() -> None:
    if _app is None:
        return
    theme = _resolve_theme()
    qss_file = _styles_dir() / f"{theme}.qss"
    if qss_file.exists():
        stylesheet = qss_file.read_text(encoding="utf-8")
        _app.setStyleSheet(stylesheet)


def create_app() -> tuple[QApplication, "MainWindow"]:
    global _app, _main_window

    _app = QApplication(sys.argv)
    _app.setApplicationName("OpenEmail")
    _app.setOrganizationName("openemail")
    _app.setDesktopFileName("openemail")

    db.connect()

    from openemail.ui.main_window import MainWindow

    _main_window = MainWindow()

    apply_theme()

    return _app, _main_window


def get_app() -> QApplication | None:
    return _app


def get_main_window():
    return _main_window
