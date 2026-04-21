import logging
import sys
from pathlib import Path
from typing import TYPE_CHECKING

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QGuiApplication
from PyQt6.QtWidgets import QApplication

from openemail.config import settings
from openemail.storage.database import db
from openemail.utils.logging_config import setup_logging
from openemail.utils.exceptions import (
    install_global_handler,
    detect_last_crash,
    clear_crash_flag,
)

if TYPE_CHECKING:
    from openemail.ui.main_window import MainWindow

logger = logging.getLogger(__name__)


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


def _recover_interrupted_queue() -> None:
    """Reset 'processing' operations back to 'pending' after a crash.

    Operations stuck in 'processing' were interrupted mid-execution and
    must be re-queued.  'success' operations are never touched.
    """
    try:
        from openemail.storage.database import db

        cur = db.execute(
            """
            UPDATE offline_operations
            SET status = 'pending', updated_at = datetime('now')
            WHERE status IN ('processing', 'retrying')
            """
        )
        reset_count = cur.rowcount
        if reset_count > 0:
            db.commit()
            logger.info("崩溃恢复：已将 %d 个中断操作重置为 pending", reset_count)
        else:
            logger.debug("崩溃恢复：无中断的离线操作")
    except Exception:
        logger.exception("崩溃恢复：重置离线队列失败")


def _show_crash_recovery_dialog() -> None:
    """Show a non-blocking notification about the previous crash."""
    try:
        from PyQt6.QtWidgets import QMessageBox

        box = QMessageBox()
        box.setIcon(QMessageBox.Icon.Warning)
        box.setWindowTitle("OpenEmail — 上次异常退出")
        box.setText(
            "检测到 OpenEmail 上次异常退出。\n\n"
            "已自动恢复中断的离线队列操作。\n"
            "详细诊断信息请查看 ~/.openemail/crash.log"
        )
        box.setStandardButtons(QMessageBox.StandardButton.Ok)
        box.exec()
    except Exception:
        logger.exception("显示崩溃恢复对话框失败")


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

    # 初始化统一日志系统（最先执行）
    setup_logging()

    # 确保异步依赖可用
    _ensure_async_deps()

    # 安装全局异常处理器
    install_global_handler()

    # 检测上次是否异常退出
    _crashed = detect_last_crash()
    if _crashed:
        logger.warning(
            "检测到应用程序上次可能异常退出，详情请查看 ~/.openemail/crash.log"
        )

    _app = QApplication(sys.argv)
    _app.setApplicationName("OpenEmail")
    _app.setOrganizationName("openemail")
    _app.setDesktopFileName("openemail")

    db.connect()

    # 崩溃恢复：重置中断的离线队列操作
    if _crashed:
        _recover_interrupted_queue()

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

    # 显示崩溃恢复通知（非阻塞，在 main_window 创建之后）
    if _crashed:
        _show_crash_recovery_dialog()

    return _app, _main_window


def get_app() -> QApplication | None:
    return _app


def get_main_window():
    return _main_window
