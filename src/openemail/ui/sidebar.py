from __future__ import annotations

from enum import IntEnum

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QIcon
from PyQt6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from openemail.models.account import Account
from openemail.models.folder import Folder, SYSTEM_FOLDERS


class Page(IntEnum):
    MAIL_INBOX = 0
    MAIL_SENT = 1
    MAIL_DRAFTS = 2
    MAIL_SPAM = 3
    MAIL_TRASH = 4
    CALENDAR = 5
    TODO_TODAY = 6
    TODO_WEEK = 7
    TODO_ALL = 8
    PROJECTS = 9
    SETTINGS = 10


FOLDER_LABELS: dict[str, str] = {
    "INBOX": "收件箱",
    "Sent": "已发送",
    "Drafts": "草稿",
    "Spam": "垃圾邮件",
    "Trash": "已删除",
}

FOLDER_PAGES: dict[str, Page] = {
    "INBOX": Page.MAIL_INBOX,
    "Sent": Page.MAIL_SENT,
    "Drafts": Page.MAIL_DRAFTS,
    "Spam": Page.MAIL_SPAM,
    "Trash": Page.MAIL_TRASH,
}


class SidebarButton(QPushButton):
    def __init__(self, text: str, page: Page | None = None, badge: int = 0) -> None:
        super().__init__(text)
        self._page = page
        self._badge_count = badge
        self.setCheckable(True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setMinimumHeight(36)
        self.setStyleSheet("""
            QPushButton {
                text-align: left;
                padding: 6px 12px;
                border: none;
                border-radius: 6px;
                font-size: 13px;
            }
            QPushButton:checked {
                font-weight: bold;
            }
            QPushButton:hover {
                opacity: 0.8;
            }
        """)

    def set_badge(self, count: int) -> None:
        self._badge_count = count
        base_text = self.text().split(" (")[0]
        if count > 0:
            self.setText(f"{base_text} ({count})")
        else:
            self.setText(base_text)


class SectionHeader(QLabel):
    def __init__(self, text: str) -> None:
        super().__init__(text)
        self.setStyleSheet("""
            QLabel {
                font-size: 11px;
                font-weight: bold;
                padding: 12px 12px 4px 12px;
                text-transform: uppercase;
                letter-spacing: 1px;
            }
        """)


class Sidebar(QWidget):
    page_changed = pyqtSignal(Page)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setProperty("class", "sidebar")
        self._buttons: list[SidebarButton] = []
        self._folder_buttons: dict[str, SidebarButton] = {}
        self._setup_ui()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(0)

        app_label = QLabel("OpenEmail")
        app_label.setStyleSheet("""
            QLabel {
                font-size: 20px;
                font-weight: bold;
                padding: 8px 12px 16px 12px;
            }
        """)
        layout.addWidget(app_label)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        scroll_content = QWidget()
        self._scroll_layout = QVBoxLayout(scroll_content)
        self._scroll_layout.setContentsMargins(0, 0, 0, 0)
        self._scroll_layout.setSpacing(2)

        self._scroll_layout.addWidget(SectionHeader("邮件"))
        self._add_mail_buttons(self._scroll_layout)

        self._account_section = QWidget()
        self._account_layout = QVBoxLayout(self._account_section)
        self._account_layout.setContentsMargins(0, 0, 0, 0)
        self._account_layout.setSpacing(2)
        self._account_section.setVisible(False)
        self._scroll_layout.addWidget(self._account_section)

        self._scroll_layout.addWidget(SectionHeader("日历"))
        self._add_button(self._scroll_layout, "日历", Page.CALENDAR)

        self._scroll_layout.addWidget(SectionHeader("待办"))
        self._add_button(self._scroll_layout, "今天", Page.TODO_TODAY)
        self._add_button(self._scroll_layout, "本周", Page.TODO_WEEK)
        self._add_button(self._scroll_layout, "全部", Page.TODO_ALL)

        self._scroll_layout.addWidget(SectionHeader("项目板"))
        self._add_button(self._scroll_layout, "项目", Page.PROJECTS)

        self._scroll_layout.addStretch()

        scroll.setWidget(scroll_content)
        layout.addWidget(scroll)

        separator = QFrame()
        separator.setFrameShape(QFrame.Shape.HLine)
        separator.setFixedHeight(1)
        layout.addWidget(separator)

        self._add_button(layout, "设置", Page.SETTINGS)

        if self._buttons:
            self._buttons[0].setChecked(True)

    def _add_mail_buttons(self, layout: QVBoxLayout) -> None:
        mail_items = [
            ("收件箱", Page.MAIL_INBOX),
            ("已发送", Page.MAIL_SENT),
            ("草稿", Page.MAIL_DRAFTS),
            ("垃圾邮件", Page.MAIL_SPAM),
            ("已删除", Page.MAIL_TRASH),
        ]
        for text, page in mail_items:
            btn = self._add_button(layout, text, page)
            folder_key = [k for k, v in FOLDER_PAGES.items() if v == page]
            if folder_key:
                self._folder_buttons[folder_key[0]] = btn

    def _add_button(self, layout: QVBoxLayout, text: str, page: Page) -> SidebarButton:
        btn = SidebarButton(text, page=page)
        btn.clicked.connect(lambda checked, p=page: self._on_button_clicked(p))
        self._buttons.append(btn)
        layout.addWidget(btn)
        return btn

    def _on_button_clicked(self, page: Page) -> None:
        for btn in self._buttons:
            btn.setChecked(btn._page == page)
        self.page_changed.emit(page)

    def set_active_page(self, page: Page) -> None:
        for btn in self._buttons:
            btn.setChecked(btn._page == page)

    def refresh_accounts(self) -> None:
        while self._account_layout.count():
            item = self._account_layout.takeAt(0)
            if item and item.widget():
                item.widget().deleteLater()

        accounts = Account.get_all_active()
        if not accounts:
            self._account_section.setVisible(False)
            return

        self._account_section.setVisible(True)
        header = SectionHeader("账户")
        self._account_layout.addWidget(header)

        for account in accounts:
            label = QLabel(f"  {account.name or account.email}")
            label.setStyleSheet("font-size: 12px; padding: 2px 12px;")
            self._account_layout.addWidget(label)

            folders = Folder.get_by_account(account.id)
            for folder in folders:
                folder_key = folder.name
                if folder_key in self._folder_buttons:
                    unread = (
                        Email.get_unread_count(folder.id)
                        if hasattr(Email, "get_unread_count")
                        else 0
                    )
                    btn = self._folder_buttons[folder_key]
                    btn.set_badge(unread)

    def update_folder_badge(self, folder_name: str, count: int) -> None:
        btn = self._folder_buttons.get(folder_name)
        if btn:
            btn.set_badge(count)
