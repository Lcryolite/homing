import sys
from pathlib import Path

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QGuiApplication
from PyQt6.QtWidgets import QApplication

from openemail.config import settings
from openemail.storage.database import db
from openemail.utils.exceptions import (
    install_global_handler,
    detect_last_crash,
    clear_crash_flag,
)


def _ensure_async_deps():
    """确保异步依赖可用，缺失时注入轻量模拟"""
    _mocks = {
        "aiohttp": lambda: type(
            "aiohttp",
            (),
            {
                "__version__": "0.0.0-mock",
                "ClientSession": type(
                    "ClientSession",
                    (),
                    {
                        "__init__": lambda self, *a, **k: None,
                    },
                ),
            },
        )(),
        "aiohttp.client": lambda: type("client", (), {})(),
        "aiosmtplib": lambda: type(
            "aiosmtplib",
            (),
            {
                "SMTP": type(
                    "SMTP",
                    (),
                    {
                        "__init__": lambda self, *a, **k: None,
                    },
                ),
            },
        )(),
        "aioimaplib": lambda: type(
            "aioimaplib",
            (),
            {
                "AioImap": type(
                    "AioImap",
                    (),
                    {
                        "__init__": lambda self, *a, **k: None,
                    },
                ),
            },
        )(),
    }
    for name, factory in _mocks.items():
        if name not in sys.modules:
            try:
                __import__(name)
            except ImportError:
                sys.modules[name] = factory()


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

    # 确保异步依赖可用
    _ensure_async_deps()

    # 安装全局异常处理器
    install_global_handler()

    # 检测上次是否异常退出
    if detect_last_crash():
        print("警告：检测到应用程序上次可能异常退出，详情请查看 ~/.openemail/crash.log")

    _app = QApplication(sys.argv)
    _app.setApplicationName("OpenEmail")
    _app.setOrganizationName("openemail")
    _app.setDesktopFileName("openemail")

    db.connect()

    # 启动后台任务管理器（日历提醒等）
    from openemail.background.background_manager import background_task_manager

    background_task_manager.start()

    # 初始化语义搜索系统
    from openemail.search.semantic_search import init_semantic_search

    init_semantic_search()

    from openemail.ui.main_window import MainWindow

    _main_window = MainWindow()

    apply_theme()

    # 清除崩溃标志
    clear_crash_flag()

    return _app, _main_window


def get_app() -> QApplication | None:
    return _app


def get_main_window():
    return _main_window
