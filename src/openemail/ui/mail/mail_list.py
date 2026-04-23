from __future__ import annotations

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QAction
from PyQt6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QMenu,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from openemail.models.email import Email


class MailItemWidget(QWidget):
    clicked = pyqtSignal(int)

    def __init__(self, email: Email, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._email_id = email.id
        self._setup_ui(email)

    def _setup_ui(self, email: Email) -> None:
        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 4, 8, 4)
        layout.setSpacing(8)

        left = QVBoxLayout()
        left.setSpacing(2)

        top_row = QHBoxLayout()
        top_row.setSpacing(8)

        # 标签圆点显示
        tags = email.get_tags()
        if tags:
            for tag in tags[:3]:  # 最多显示 3 个标签
                tag_label = QLabel(tag.icon)
                tag_label.setToolTip(tag.name)
                tag_label.setStyleSheet(f"font-size: 12px; color: {tag.color};")
                top_row.addWidget(tag_label)

        sender_label = QLabel(email.sender_name or email.sender_addr)
        sender_label.setStyleSheet("font-weight: bold; font-size: 13px;")
        if not email.is_read:
            sender_label.setStyleSheet("font-weight: bold; font-size: 13px;")
        top_row.addWidget(sender_label)
        top_row.addStretch()

        date_label = QLabel(email.display_date)
        date_label.setStyleSheet("font-size: 11px;")
        top_row.addWidget(date_label)

        if email.is_flagged:
            flag_label = QLabel("★")
            flag_label.setStyleSheet("color: #C97850; font-size: 12px;")
            top_row.addWidget(flag_label)

        if email.has_attachment:
            att_label = QLabel("📎")
            att_label.setStyleSheet("font-size: 12px;")
            top_row.addWidget(att_label)

        left.addLayout(top_row)

        subject_label = QLabel(email.subject or "(无主题)")
        subject_label.setStyleSheet("font-size: 12px;")
        if not email.is_read:
            subject_label.setStyleSheet("font-size: 12px; font-weight: bold;")
        left.addWidget(subject_label)

        preview_label = QLabel(email.preview_text)
        preview_label.setStyleSheet("font-size: 11px;")
        preview_label.setWordWrap(False)
        left.addWidget(preview_label)

        layout.addLayout(left)

    @property
    def email_id(self) -> int:
        return self._email_id


class MailListWidget(QWidget):
    email_selected = pyqtSignal(int)
    email_double_clicked = pyqtSignal(int)
    mark_read_requested = pyqtSignal(int)
    mark_flagged_requested = pyqtSignal(int, bool)
    delete_requested = pyqtSignal(int)
    mark_spam_requested = pyqtSignal(int)
    mark_not_spam_requested = pyqtSignal(int)

    PAGE_SIZE = 100

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._emails: list[Email] = []
        self._folder_id: int = 0
        self._offset: int = 0
        self._has_more: bool = True
        self._loading: bool = False
        self._setup_ui()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self._header = QLabel("收件箱")
        self._header.setStyleSheet(
            "font-size: 16px; font-weight: bold; padding: 12px 16px;"
        )
        layout.addWidget(self._header)

        self._list = QTreeWidget()
        self._list.setHeaderHidden(True)
        self._list.setRootIsDecorated(False)
        self._list.setIndentation(0)
        self._list.setSelectionMode(QTreeWidget.SelectionMode.SingleSelection)
        self._list.itemClicked.connect(self._on_item_clicked)
        self._list.itemDoubleClicked.connect(self._on_item_double_clicked)
        self._list.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self._list.customContextMenuRequested.connect(self._show_context_menu)
        # Lazy load on scroll
        self._list.verticalScrollBar().valueChanged.connect(self._on_scroll)
        layout.addWidget(self._list)

        self._loading_label = QLabel("加载中...")
        self._loading_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._loading_label.hide()
        layout.addWidget(self._loading_label)

    def set_title(self, title: str) -> None:
        self._header.setText(title)

    def load_emails(self, emails: list[Email], folder_id: int = 0, append: bool = False) -> None:
        if not append:
            self._emails = emails
            self._list.clear()
            self._offset = len(emails)
            self._folder_id = folder_id
            self._has_more = len(emails) >= self.PAGE_SIZE
        else:
            self._emails.extend(emails)
            self._offset += len(emails)
            self._has_more = len(emails) >= self.PAGE_SIZE

        for email_obj in emails:
            item = QTreeWidgetItem(self._list)
            widget = MailItemWidget(email_obj)
            item.setData(0, Qt.ItemDataRole.UserRole, email_obj.id)
            self._list.setItemWidget(item, 0, widget)

        self._loading = False
        self._loading_label.hide()

    def _on_scroll(self, value: int) -> None:
        if self._loading or not self._has_more or not self._folder_id:
            return
        scrollbar = self._list.verticalScrollBar()
        if value >= scrollbar.maximum() - 20:
            self._load_next_page()

    def _load_next_page(self) -> None:
        self._loading = True
        self._loading_label.show()
        from openemail.models.email import Email
        more = Email.get_by_folder(self._folder_id, limit=self.PAGE_SIZE, offset=self._offset)
        self.load_emails(more, self._folder_id, append=True)

    def add_email(self, email: Email) -> None:
        self._emails.insert(0, email)
        item = QTreeWidgetItem(self._list)
        widget = MailItemWidget(email)
        item.setData(0, Qt.ItemDataRole.UserRole, email.id)
        self._list.setItemWidget(item, 0, widget)
        self._list.insertTopLevelItem(0, item)

    def remove_email(self, email_id: int) -> None:
        self._emails = [e for e in self._emails if e.id != email_id]
        for i in range(self._list.topLevelItemCount()):
            item = self._list.topLevelItem(i)
            if item.data(0, Qt.ItemDataRole.UserRole) == email_id:
                self._list.takeTopLevelItem(i)
                break

    def refresh_email(self, email: Email) -> None:
        for i in range(self._list.topLevelItemCount()):
            item = self._list.topLevelItem(i)
            if item.data(0, Qt.ItemDataRole.UserRole) == email.id:
                widget = MailItemWidget(email)
                self._list.setItemWidget(item, 0, widget)
                break

    def get_selected_email_id(self) -> int | None:
        items = self._list.selectedItems()
        if items:
            return items[0].data(0, Qt.ItemDataRole.UserRole)
        return None

    def _on_item_clicked(self, item: QTreeWidgetItem) -> None:
        email_id = item.data(0, Qt.ItemDataRole.UserRole)
        if email_id is not None:
            self.email_selected.emit(email_id)

    def _on_item_double_clicked(self, item: QTreeWidgetItem) -> None:
        email_id = item.data(0, Qt.ItemDataRole.UserRole)
        if email_id is not None:
            self.email_double_clicked.emit(email_id)

    def _show_context_menu(self, pos) -> None:
        item = self._list.itemAt(pos)
        if not item:
            return
        email_id = item.data(0, Qt.ItemDataRole.UserRole)
        if email_id is None:
            return

        email = Email.get_by_id(email_id)
        if email is None:
            return

        menu = QMenu(self)

        mark_read_action = QAction(
            "标记为已读" if not email.is_read else "标记为未读", self
        )
        mark_read_action.triggered.connect(
            lambda: self.mark_read_requested.emit(email_id)
        )
        menu.addAction(mark_read_action)

        flag_action = QAction("取消星标" if email.is_flagged else "添加星标", self)
        flag_action.triggered.connect(
            lambda: self.mark_flagged_requested.emit(email_id, not email.is_flagged)
        )
        menu.addAction(flag_action)

        menu.addSeparator()

        if not email.is_spam:
            spam_action = QAction("标记为垃圾邮件", self)
            spam_action.triggered.connect(
                lambda: self.mark_spam_requested.emit(email_id)
            )
            menu.addAction(spam_action)
        else:
            not_spam_action = QAction("这不是垃圾邮件", self)
            not_spam_action.triggered.connect(
                lambda: self.mark_not_spam_requested.emit(email_id)
            )
            menu.addAction(not_spam_action)

        menu.addSeparator()

        delete_action = QAction("删除", self)
        delete_action.triggered.connect(lambda: self.delete_requested.emit(email_id))
        menu.addAction(delete_action)

        menu.exec(self._list.mapToGlobal(pos))
