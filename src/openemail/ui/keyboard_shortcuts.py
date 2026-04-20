from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Callable, List, Optional

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QKeySequence, QShortcut
from PyQt6.QtWidgets import QWidget

logger = logging.getLogger(__name__)


@dataclass
class ShortcutConfig:
    id: str
    sequence: str
    description: str
    enabled_by_default: bool = True
    context: Qt.ShortcutContext = Qt.ShortcutContext.WidgetShortcut


class KeyboardShortcutManager:
    """
    Manage keyboard shortcuts for the application.
    Allows global shortcuts and per-widget shortcuts.
    """

    def __init__(self, parent: QWidget | None = None):
        self._parent = parent
        self._shortcuts: dict[str, QShortcut] = {}
        self._configs: list[ShortcutConfig] = [
            # Navigation
            ShortcutConfig("nav_inbox", "Alt+1", "切换到收件箱"),
            ShortcutConfig("nav_sent", "Alt+2", "切换到已发送"),
            ShortcutConfig("nav_drafts", "Alt+3", "切换到草稿箱"),
            ShortcutConfig("nav_trash", "Alt+4", "切换到垃圾箱"),
            ShortcutConfig("nav_search", "Ctrl+F", "聚焦搜索框"),
            ShortcutConfig("nav_next_item", "J", "下一个项目（邮件/联系人）"),
            ShortcutConfig("nav_prev_item", "K", "上一个项目（邮件/联系人）"),
            ShortcutConfig("nav_up_folder", "U", "返回上一级"),
            # Mail actions
            ShortcutConfig("mail_compose", "C", "撰写新邮件"),
            ShortcutConfig("mail_reply", "R", "回复邮件"),
            ShortcutConfig("mail_reply_all", "Shift+R", "全部回复"),
            ShortcutConfig("mail_forward", "F", "转发邮件"),
            ShortcutConfig("mail_delete", "Delete", "删除邮件"),
            ShortcutConfig("mail_archive", "E", "归档邮件"),
            ShortcutConfig("mail_mark_read", "Shift+I", "标记为已读"),
            ShortcutConfig("mail_mark_unread", "Shift+U", "标记为未读"),
            ShortcutConfig("mail_mark_flagged", "Shift+S", "切换星标/加旗"),
            ShortcutConfig("mail_mark_spam", "!", "标记为垃圾邮件"),
            ShortcutConfig("mail_refresh", "Shift+R", "刷新邮件列表"),
            # Selection
            ShortcutConfig("select_all", "Ctrl+A", "全选"),
            ShortcutConfig("select_none", "Esc", "取消选择"),
            ShortcutConfig("extend_selection_up", "Shift+K", "向上扩展选择"),
            ShortcutConfig("extend_selection_down", "Shift+J", "向下扩展选择"),
            # Application
            ShortcutConfig("app_quit", "Ctrl+Q", "退出应用"),
            ShortcutConfig("app_settings", "Ctrl+,", "打开设置"),
            ShortcutConfig("app_toggle_sidebar", "Ctrl+\\", "切换侧边栏"),
            ShortcutConfig("app_fullscreen", "F11", "切换全屏"),
            # Search
            ShortcutConfig("search_next", "Ctrl+G", "搜索下一个匹配"),
            ShortcutConfig("search_prev", "Ctrl+Shift+G", "搜索上一个匹配"),
            # Text editor (compose)
            ShortcutConfig("editor_bold", "Ctrl+B", "粗体"),
            ShortcutConfig("editor_italic", "Ctrl+I", "斜体"),
            ShortcutConfig("editor_underline", "Ctrl+U", "下划线"),
            ShortcutConfig("editor_send", "Ctrl+Enter", "发送邮件"),
            ShortcutConfig("editor_save_draft", "Ctrl+S", "保存草稿"),
            ShortcutConfig("editor_cancel", "Esc", "取消编辑"),
        ]

    def get_shortcut_descriptions(self) -> List[dict]:
        """Get all shortcuts for display in help dialog."""
        return [
            {
                "id": config.id,
                "sequence": config.sequence,
                "description": config.description,
                "enabled": config.id in self._shortcuts,
            }
            for config in self._configs
        ]

    def add_shortcut(
        self,
        parent: QWidget,
        key_sequence: str | QKeySequence,
        callback: Callable,
        context: Qt.ShortcutContext = Qt.ShortcutContext.WidgetShortcut,
        shortcut_id: str | None = None,
    ) -> QShortcut:
        """Add a shortcut to a widget."""
        shortcut = QShortcut(key_sequence, parent)
        shortcut.setContext(context)
        shortcut.activated.connect(callback)

        if shortcut_id:
            self._shortcuts[shortcut_id] = shortcut
            logger.debug(f"Registered shortcut {shortcut_id}: {key_sequence}")

        return shortcut

    def add_named_shortcut(
        self,
        parent: QWidget,
        shortcut_id: str,
        callback: Callable,
        context: Qt.ShortcutContext = Qt.ShortcutContext.WidgetShortcut,
    ) -> bool:
        """Add a shortcut from predefined configurations."""
        config = next((c for c in self._configs if c.id == shortcut_id), None)
        if not config:
            logger.warning(f"Unknown shortcut ID: {shortcut_id}")
            return False

        shortcut = self.add_shortcut(
            parent, config.sequence, callback, context, shortcut_id
        )
        return shortcut is not None

    def remove_shortcut(self, shortcut_id: str) -> bool:
        """Remove a shortcut by ID."""
        if shortcut_id in self._shortcuts:
            shortcut = self._shortcuts.pop(shortcut_id)
            shortcut.setEnabled(False)
            shortcut.deleteLater()
            logger.debug(f"Removed shortcut: {shortcut_id}")
            return True
        return False

    def set_shortcut_enabled(self, shortcut_id: str, enabled: bool) -> bool:
        """Enable or disable a shortcut."""
        if shortcut_id in self._shortcuts:
            self._shortcuts[shortcut_id].setEnabled(enabled)
            logger.debug(
                f"{'Enabled' if enabled else 'Disabled'} shortcut: {shortcut_id}"
            )
            return True
        return False

    def clear(self):
        """Clear all shortcuts."""
        for shortcut_id in list(self._shortcuts.keys()):
            self.remove_shortcut(shortcut_id)


# Global shortcut manager instance
_global_manager: Optional[KeyboardShortcutManager] = None


def get_global_manager() -> KeyboardShortcutManager:
    """Get the global shortcut manager instance."""
    global _global_manager
    if _global_manager is None:
        _global_manager = KeyboardShortcutManager()
    return _global_manager


def setup_application_shortcuts(main_window: QWidget) -> KeyboardShortcutManager:
    """
    Setup keyboard shortcuts for the main application window.
    This creates all global shortcuts that should be available throughout the app.
    """
    manager = get_global_manager()

    # Application-wide shortcuts
    manager.add_named_shortcut(main_window, "app_quit", main_window.close)
    manager.add_named_shortcut(
        main_window,
        "app_fullscreen",
        lambda: (
            main_window.showFullScreen()
            if not main_window.isFullScreen()
            else main_window.showNormal()
        ),
    )

    logger.info(f"Setup {len(manager._shortcuts)} keyboard shortcuts")
    return manager
