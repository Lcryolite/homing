from __future__ import annotations

from enum import IntEnum

from PyQt6.QtCore import Qt, pyqtSignal
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
from openemail.models.email import Email
from openemail.models.folder import Folder


class Page(IntEnum):
    MAIL_INBOX = 0
    MAIL_SENT = 1
    MAIL_DRAFTS = 2
    MAIL_SPAM = 3
    MAIL_TRASH = 4
    LABELS = 5
    CONTACTS = 6
    CALENDAR = 7
    TODO_TODAY = 8
    TODO_WEEK = 9
    TODO_ALL = 10
    PROJECTS = 11
    SETTINGS = 12


PAGE_ICONS: dict[Page, str] = {
    Page.MAIL_INBOX: "📥",
    Page.MAIL_SENT: "📤",
    Page.MAIL_DRAFTS: "📝",
    Page.MAIL_SPAM: "🚫",
    Page.MAIL_TRASH: "🗑",
    Page.LABELS: "🏷",
    Page.CONTACTS: "👤",
    Page.CALENDAR: "📅",
    Page.TODO_TODAY: "⭐",
    Page.TODO_WEEK: "📋",
    Page.TODO_ALL: "✅",
    Page.PROJECTS: "📊",
    Page.SETTINGS: "⚙",
}

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
    def __init__(
        self, text: str, page: Page | None = None, icon: str = "", badge: int = 0
    ) -> None:
        self._icon_text = icon
        self._base_text = text
        display = f"  {icon}  {text}" if icon else text
        super().__init__(display)
        self._page = page
        self._badge_count = badge
        self.setCheckable(True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setMinimumHeight(38)
        self.setStyleSheet("""
            QPushButton {
                text-align: left;
                padding: 8px 12px;
                border: none;
                border-radius: 8px;
                font-size: 13px;
            }
            QPushButton:checked {
                font-weight: bold;
            }
        """)

    def set_badge(self, count: int) -> None:
        self._badge_count = count
        icon_part = f"  {self._icon_text}" if self._icon_text else ""
        if count > 0:
            self.setText(f"{icon_part}  {self._base_text} ({count})")
        else:
            self.setText(f"{icon_part}  {self._base_text}")


class ComposeButton(QPushButton):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__("✏  写邮件", parent)
        self.setProperty("class", "primary")
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setMinimumHeight(40)
        self.setStyleSheet("""
            QPushButton {
                padding: 10px 16px;
                border-radius: 10px;
                font-size: 14px;
                font-weight: bold;
            }
            QPushButton:hover {
                opacity: 0.9;
            }
        """)


class SectionHeader(QLabel):
    def __init__(self, text: str) -> None:
        super().__init__(text)
        self.setStyleSheet("""
            QLabel {
                font-size: 11px;
                font-weight: bold;
                padding: 14px 12px 4px 12px;
                letter-spacing: 1px;
            }
        """)


class Sidebar(QWidget):
    page_changed = pyqtSignal(Page)
    compose_requested = pyqtSignal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setProperty("class", "sidebar")
        self._buttons: list[SidebarButton] = []
        self._folder_buttons: dict[str, SidebarButton] = {}
        self._setup_ui()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(0)

        header_layout = QHBoxLayout()
        header_layout.setContentsMargins(4, 0, 4, 0)

        app_label = QLabel("✉  OpenEmail")
        app_label.setStyleSheet("""
            QLabel {
                font-size: 18px;
                font-weight: bold;
                padding: 4px 0 12px 0;
            }
        """)
        header_layout.addWidget(app_label)
        header_layout.addStretch()
        layout.addLayout(header_layout)

        self._compose_btn = ComposeButton()
        self._compose_btn.clicked.connect(self.compose_requested.emit)
        layout.addWidget(self._compose_btn)

        layout.addSpacing(8)

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

        self._scroll_layout.addWidget(SectionHeader("通讯"))
        self._add_button(
            self._scroll_layout,
            "联系人",
            Page.CONTACTS,
            PAGE_ICONS.get(Page.CONTACTS, ""),
        )

        self._scroll_layout.addWidget(SectionHeader("日历与待办"))
        self._add_button(
            self._scroll_layout,
            "日历",
            Page.CALENDAR,
            PAGE_ICONS.get(Page.CALENDAR, ""),
        )
        self._add_button(
            self._scroll_layout,
            "今天",
            Page.TODO_TODAY,
            PAGE_ICONS.get(Page.TODO_TODAY, ""),
        )
        self._add_button(
            self._scroll_layout,
            "本周",
            Page.TODO_WEEK,
            PAGE_ICONS.get(Page.TODO_WEEK, ""),
        )
        self._add_button(
            self._scroll_layout,
            "全部待办",
            Page.TODO_ALL,
            PAGE_ICONS.get(Page.TODO_ALL, ""),
        )

        self._scroll_layout.addWidget(SectionHeader("项目"))
        self._add_button(
            self._scroll_layout,
            "项目板",
            Page.PROJECTS,
            PAGE_ICONS.get(Page.PROJECTS, ""),
        )

        self._scroll_layout.addStretch()

        scroll.setWidget(scroll_content)
        layout.addWidget(scroll)

        separator = QFrame()
        separator.setFrameShape(QFrame.Shape.HLine)
        separator.setFixedHeight(1)
        layout.addWidget(separator)

        self._add_button(
            layout, "设置", Page.SETTINGS, PAGE_ICONS.get(Page.SETTINGS, "")
        )

        if self._buttons:
            self._buttons[0].setChecked(True)

    def _add_mail_buttons(self, layout: QVBoxLayout) -> None:
        mail_items = [
            ("收件箱", Page.MAIL_INBOX),
            ("标签", Page.LABELS),
            ("已发送", Page.MAIL_SENT),
            ("草稿", Page.MAIL_DRAFTS),
            ("垃圾邮件", Page.MAIL_SPAM),
            ("已删除", Page.MAIL_TRASH),
        ]
        for text, page in mail_items:
            icon = PAGE_ICONS.get(page, "")
            btn = self._add_button(layout, text, page, icon)
            folder_key = [k for k, v in FOLDER_PAGES.items() if v == page]
            if folder_key:
                self._folder_buttons[folder_key[0]] = btn

    def _add_button(
        self, layout: QVBoxLayout, text: str, page: Page, icon: str = ""
    ) -> SidebarButton:
        btn = SidebarButton(text, page=page, icon=icon)
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

        accounts = Account.get_valid_for_display()
        if not accounts:
            need_action = Account.get_need_action_accounts()
            if need_action:
                self._account_section.setVisible(True)
                header = SectionHeader("账户（需修复）")
                self._account_layout.addWidget(header)

                for account in need_action[:2]:
                    from openemail.core.connection_status import get_status_display

                    status_display = get_status_display(account.connection_status)
                    label = QLabel(f"  ⚠ {account.email}（{status_display}）")
                    label.setStyleSheet(
                        "font-size: 11px; padding: 2px 12px; color: #ff6b6b;"
                    )
                    label.setToolTip(
                        f"账号状态: {status_display}\n需要用户操作修复该账号"
                    )
                    self._account_layout.addWidget(label)

                if len(need_action) > 2:
                    more_label = QLabel(
                        f"  … 还有 {len(need_action) - 2} 个账号需要修复"
                    )
                    more_label.setStyleSheet(
                        "font-size: 10px; padding: 2px 12px; color: #999;"
                    )
                    self._account_layout.addWidget(more_label)
            else:
                self._account_section.setVisible(False)
            return

        self._account_section.setVisible(True)
        header = SectionHeader("账户")
        self._account_layout.addWidget(header)

        for account in accounts:
            from openemail.core.connection_status import get_status_display

            status_icon = (
                "🟢" if account.connection_status.value == "sync_ready" else "🟡"
            )
            status_text = get_status_display(account.connection_status)
            label = QLabel(f"  {status_icon} {account.name or account.email}")
            label.setStyleSheet("font-size: 12px; padding: 2px 12px;")
            label.setToolTip(f"账号状态: {status_text}")
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
