from __future__ import annotations

import asyncio
import json

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QSplitter,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from openemail.core.mail_builder import MailBuilder
from openemail.core.smtp_client import SMTPClient
from openemail.models.account import Account
from openemail.models.email import Email
from openemail.core.mail_parser import MailParser
from openemail.storage.mail_store import mail_store


class ComposeWindow(QDialog):
    sent = pyqtSignal()

    def __init__(self, account: Account, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._account = account
        self._reply_to_email: Email | None = None
        self._forward_email: Email | None = None
        self._setup_ui()

    def _setup_ui(self) -> None:
        self.setWindowTitle("写邮件")
        self.setMinimumSize(700, 500)
        self.resize(800, 600)

        layout = QVBoxLayout(self)
        layout.setSpacing(8)

        from_row = QHBoxLayout()
        from_label = QLabel("发件人:")
        from_label.setFixedWidth(60)
        self._from_field = QLineEdit(self._account.email)
        self._from_field.setReadOnly(True)
        from_row.addWidget(from_label)
        from_row.addWidget(self._from_field)
        layout.addLayout(from_row)

        to_row = QHBoxLayout()
        to_label = QLabel("收件人:")
        to_label.setFixedWidth(60)
        self._to_field = QLineEdit()
        self._to_field.setPlaceholderText("输入收件人地址，多个用逗号分隔")
        to_row.addWidget(to_label)
        to_row.addWidget(to_label)
        to_row.addWidget(self._to_field)
        layout.addLayout(to_row)

        cc_row = QHBoxLayout()
        cc_label = QLabel("抄送:")
        cc_label.setFixedWidth(60)
        self._cc_field = QLineEdit()
        self._cc_field.setPlaceholderText("抄送地址，多个用逗号分隔")
        cc_row.addWidget(cc_label)
        cc_row.addWidget(self._cc_field)
        layout.addLayout(cc_row)

        subject_row = QHBoxLayout()
        subject_label = QLabel("主题:")
        subject_label.setFixedWidth(60)
        self._subject_field = QLineEdit()
        subject_row.addWidget(subject_label)
        subject_row.addWidget(self._subject_field)
        layout.addLayout(subject_row)

        self._body_edit = QTextEdit()
        self._body_edit.setPlaceholderText("在此输入邮件正文...")
        self._body_edit.setMinimumHeight(200)
        layout.addWidget(self._body_edit)

        btn_row = QHBoxLayout()
        btn_row.addStretch()

        self._send_btn = QPushButton("发送")
        self._send_btn.setProperty("class", "primary")
        self._send_btn.clicked.connect(self._on_send)
        btn_row.addWidget(self._send_btn)

        cancel_btn = QPushButton("取消")
        cancel_btn.clicked.connect(self.reject)
        btn_row.addWidget(cancel_btn)

        layout.addLayout(btn_row)

    def set_reply(self, email_obj: Email, reply_all: bool = False) -> None:
        self._reply_to_email = email_obj
        self.setWindowTitle("回复邮件")

        to_addrs = []
        if reply_all:
            to_addrs = email_obj.to_list + email_obj.cc_list
            to_addrs = [a for a in to_addrs if a != self._account.email]
            if email_obj.sender_addr != self._account.email:
                to_addrs.insert(0, email_obj.sender_addr)
        else:
            to_addrs = [email_obj.sender_addr]

        self._to_field.setText(", ".join(to_addrs))
        self._subject_field.setText(f"Re: {email_obj.subject}")

        self._body_edit.setPlainText(
            f"\n\n--- 原始邮件 ---\n发件人: {email_obj.display_sender}\n日期: {email_obj.date}\n主题: {email_obj.subject}\n"
        )

        if email_obj.file_path:
            raw = mail_store.read_raw(email_obj.file_path)
            if raw:
                parsed = MailParser.parse_raw(raw)
                self._body_edit.append(parsed.text_body or "(HTML邮件，请查看原邮件)")

    def set_forward(self, email_obj: Email) -> None:
        self._forward_email = email_obj
        self.setWindowTitle("转发邮件")

        self._subject_field.setText(f"Fwd: {email_obj.subject}")

        self._body_edit.setPlainText(
            f"\n\n--- 转发邮件 ---\n发件人: {email_obj.display_sender}\n日期: {email_obj.date}\n主题: {email_obj.subject}\n"
        )

        if email_obj.file_path:
            raw = mail_store.read_raw(email_obj.file_path)
            if raw:
                parsed = MailParser.parse_raw(raw)
                self._body_edit.append(parsed.text_body or "(HTML邮件，请查看原邮件)")

    def _on_send(self) -> None:
        to_text = self._to_field.text().strip()
        if not to_text:
            return

        to_addrs = [a.strip() for a in to_text.split(",") if a.strip()]
        cc_text = self._cc_field.text().strip()
        cc_addrs = (
            [a.strip() for a in cc_text.split(",") if a.strip()] if cc_text else []
        )

        subject = self._subject_field.text().strip()
        body = self._body_edit.toPlainText()

        self._send_btn.setEnabled(False)
        self._send_btn.setText("发送中...")

        builder = MailBuilder()
        builder.set_from(self._account.email, self._account.name)
        builder.set_to(to_addrs)
        if cc_addrs:
            builder.set_cc(cc_addrs)
        builder.set_subject(subject)
        builder.set_text_body(body)

        if self._reply_to_email and self._reply_to_email.message_id:
            builder.set_in_reply_to(self._reply_to_email.message_id)
            refs = self._reply_to_email.message_id
            builder.set_references(refs)

        if self._forward_email and self._forward_email.file_path:
            raw = mail_store.read_raw(self._forward_email.file_path)
            if raw:
                parsed = MailParser.parse_raw(raw)
                for att in parsed.attachments:
                    builder.add_attachment(
                        att["filename"], att["data"], att["mime_type"]
                    )

        message = builder.build()

        import asyncio

        loop = asyncio.new_event_loop()
        try:
            client = SMTPClient(self._account)
            success = loop.run_until_complete(
                client.send(
                    to=to_addrs,
                    subject=subject,
                    body_text=body,
                    cc=cc_addrs,
                    in_reply_to=self._reply_to_email.message_id
                    if self._reply_to_email
                    else None,
                    references=self._reply_to_email.message_id
                    if self._reply_to_email
                    else None,
                )
            )
        finally:
            loop.close()

        if success:
            self.sent.emit()
            self.accept()
        else:
            self._send_btn.setEnabled(True)
            self._send_btn.setText("发送")
