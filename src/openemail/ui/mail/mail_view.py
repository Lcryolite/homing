from __future__ import annotations

import os
import tempfile

from PyQt6.QtCore import Qt, QUrl, pyqtSignal
from PyQt6.QtGui import QFont, QAction
from PyQt6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QMenu,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from openemail.core.mail_parser import MailParser
from openemail.models.email import Email
from openemail.storage.mail_store import mail_store


class AttachmentBar(QWidget):
    open_requested = pyqtSignal(str)
    save_requested = pyqtSignal(str, str)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._attachments: list[dict] = []
        self._setup_ui()

    def _setup_ui(self) -> None:
        layout = QHBoxLayout(self)
        layout.setContentsMargins(16, 4, 16, 4)
        layout.setSpacing(8)

        label = QLabel("附件:")
        label.setStyleSheet("font-weight: bold; font-size: 12px;")
        layout.addWidget(label)
        layout.addStretch()

    def load_attachments(self, attachments: list[dict]) -> None:
        self._attachments = attachments
        layout = self.layout()

        while layout.count() > 2:
            item = layout.takeAt(1)
            if item and item.widget():
                item.widget().deleteLater()

        for att in attachments:
            btn = QPushButton(f"📎 {att['filename']} ({att['size']} bytes)")
            btn.setStyleSheet("padding: 4px 8px; font-size: 11px;")
            btn.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
            btn.clicked.connect(lambda checked, f=att["filename"]: self._on_open(f))
            btn.customContextMenuRequested.connect(
                lambda pos, a=att: self._show_save_menu(a)
            )
            layout.insertWidget(layout.count() - 1, btn)

    def _on_open(self, filename: str) -> None:
        self.open_requested.emit(filename)

    def _show_save_menu(self, att: dict) -> None:
        self.save_requested.emit(att["filename"], "")


class MailViewWidget(QWidget):
    reply_requested = pyqtSignal(int)
    reply_all_requested = pyqtSignal(int)
    forward_requested = pyqtSignal(int)
    delete_requested = pyqtSignal(int)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._current_email: Email | None = None
        self._parsed = None
        self._setup_ui()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        toolbar = QHBoxLayout()
        toolbar.setContentsMargins(8, 4, 8, 4)
        toolbar.setSpacing(4)

        self._reply_btn = QPushButton("回复")
        self._reply_btn.setProperty("class", "primary")
        self._reply_btn.clicked.connect(
            lambda: self.reply_requested.emit(
                self._current_email.id if self._current_email else 0
            )
        )
        toolbar.addWidget(self._reply_btn)

        self._reply_all_btn = QPushButton("回复全部")
        self._reply_all_btn.clicked.connect(
            lambda: self.reply_all_requested.emit(
                self._current_email.id if self._current_email else 0
            )
        )
        toolbar.addWidget(self._reply_all_btn)

        self._forward_btn = QPushButton("转发")
        self._forward_btn.clicked.connect(
            lambda: self.forward_requested.emit(
                self._current_email.id if self._current_email else 0
            )
        )
        toolbar.addWidget(self._forward_btn)

        toolbar.addStretch()

        self._delete_btn = QPushButton("删除")
        self._delete_btn.setProperty("class", "danger")
        self._delete_btn.clicked.connect(
            lambda: self.delete_requested.emit(
                self._current_email.id if self._current_email else 0
            )
        )
        toolbar.addWidget(self._delete_btn)

        toolbar_widget = QWidget()
        toolbar_widget.setLayout(toolbar)
        layout.addWidget(toolbar_widget)

        self._header_area = QWidget()
        header_layout = QVBoxLayout(self._header_area)
        header_layout.setContentsMargins(16, 8, 16, 8)
        header_layout.setSpacing(4)

        self._subject_label = QLabel("")
        self._subject_label.setStyleSheet("font-size: 18px; font-weight: bold;")
        self._subject_label.setWordWrap(True)
        header_layout.addWidget(self._subject_label)

        self._from_label = QLabel("")
        self._from_label.setStyleSheet("font-size: 12px;")
        header_layout.addWidget(self._from_label)

        self._to_label = QLabel("")
        self._to_label.setStyleSheet("font-size: 11px; color: #888;")
        self._to_label.setWordWrap(True)
        header_layout.addWidget(self._to_label)

        self._date_label = QLabel("")
        self._date_label.setStyleSheet("font-size: 11px; color: #888;")
        header_layout.addWidget(self._date_label)

        self._spam_label = QLabel("")
        self._spam_label.setProperty("class", "badge-spam")
        self._spam_label.setVisible(False)
        header_layout.addWidget(self._spam_label)

        separator = QWidget()
        separator.setFixedHeight(1)
        separator.setStyleSheet("background-color: #45475a;")
        header_layout.addWidget(separator)

        self._attachment_bar = AttachmentBar()
        self._attachment_bar.setVisible(False)
        header_layout.addWidget(self._attachment_bar)

        layout.addWidget(self._header_area)

        try:
            from PyQt6.QtWebEngineWidgets import QWebEngineView

            self._use_webengine = True
            self._body_view = QWebEngineView()
            self._body_view.setContextMenuPolicy(Qt.ContextMenuPolicy.NoContextMenu)
        except ImportError:
            self._use_webengine = False
            self._body_view = QLabel("")
            self._body_view.setWordWrap(True)
            self._body_view.setTextFormat(Qt.TextFormat.PlainText)
            self._body_view.setStyleSheet("padding: 16px; font-size: 13px;")

        layout.addWidget(self._body_view, 1)

        self._placeholder = QLabel("选择一封邮件以查看内容")
        self._placeholder.setProperty("class", "placeholder-text")
        self._placeholder.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self._placeholder)
        self._placeholder.setVisible(True)
        self._header_area.setVisible(False)
        self._body_view.setVisible(False)

    def load_email(self, email_obj: Email) -> None:
        self._current_email = email_obj
        self._placeholder.setVisible(False)
        self._header_area.setVisible(True)
        self._body_view.setVisible(True)

        self._subject_label.setText(email_obj.subject or "(无主题)")
        self._from_label.setText(f"发件人: {email_obj.display_sender}")
        self._to_label.setText(f"收件人: {', '.join(email_obj.to_list)}")
        self._date_label.setText(email_obj.date)

        if email_obj.is_spam:
            self._spam_label.setText(f"垃圾邮件: {email_obj.spam_reason}")
            self._spam_label.setVisible(True)
        else:
            self._spam_label.setVisible(False)

        if email_obj.file_path:
            raw = mail_store.read_raw(email_obj.file_path)
            if raw:
                self._parsed = MailParser.parse_raw(raw)
                self._render_body()
                if self._parsed.has_attachment:
                    self._attachment_bar.load_attachments(self._parsed.attachments)
                    self._attachment_bar.setVisible(True)
                else:
                    self._attachment_bar.setVisible(False)
                return

        self._parsed = None
        if self._use_webengine:
            self._body_view.setHtml(f"<pre>{email_obj.preview_text}</pre>")
        else:
            self._body_view.setText(email_obj.preview_text)
        self._attachment_bar.setVisible(False)

    def _render_body(self) -> None:
        if not self._parsed:
            return

        if self._use_webengine:
            html = self._parsed.html_body or f"<pre>{self._parsed.text_body}</pre>"
            self._body_view.setHtml(html)
        else:
            text = self._parsed.text_body or self._parsed.html_body or ""
            self._body_view.setText(text)

    def clear(self) -> None:
        self._current_email = None
        self._parsed = None
        self._placeholder.setVisible(True)
        self._header_area.setVisible(False)
        self._body_view.setVisible(False)
        self._attachment_bar.setVisible(False)
        self._spam_label.setVisible(False)
