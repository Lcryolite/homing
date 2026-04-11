from __future__ import annotations

import base64
import mimetypes
import os
from email import encoders
from email.mime.base import MIMEBase
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.utils import formataddr, make_msgid, formatdate
from typing import Any


class MailBuilder:
    def __init__(self) -> None:
        self._from_addr: str = ""
        self._from_name: str = ""
        self._to: list[str] = []
        self._cc: list[str] = []
        self._bcc: list[str] = []
        self._subject: str = ""
        self._text_body: str = ""
        self._html_body: str = ""
        self._reply_to: str = ""
        self._in_reply_to: str = ""
        self._references: str = ""
        self._attachments: list[dict[str, Any]] = []
        self._custom_headers: dict[str, str] = {}

    def set_from(self, email_addr: str, name: str = "") -> MailBuilder:
        self._from_addr = email_addr
        self._from_name = name
        return self

    def set_to(self, addresses: list[str]) -> MailBuilder:
        self._to = addresses
        return self

    def add_to(self, address: str) -> MailBuilder:
        self._to.append(address)
        return self

    def set_cc(self, addresses: list[str]) -> MailBuilder:
        self._cc = addresses
        return self

    def add_cc(self, address: str) -> MailBuilder:
        self._cc.append(address)
        return self

    def set_bcc(self, addresses: list[str]) -> MailBuilder:
        self._bcc = addresses
        return self

    def set_subject(self, subject: str) -> MailBuilder:
        self._subject = subject
        return self

    def set_text_body(self, body: str) -> MailBuilder:
        self._text_body = body
        return self

    def set_html_body(self, body: str) -> MailBuilder:
        self._html_body = body
        return self

    def set_reply_to(self, address: str) -> MailBuilder:
        self._reply_to = address
        return self

    def set_in_reply_to(self, message_id: str) -> MailBuilder:
        self._in_reply_to = message_id
        return self

    def set_references(self, references: str) -> MailBuilder:
        self._references = references
        return self

    def add_attachment(
        self, filename: str, data: bytes, mime_type: str = "application/octet-stream"
    ) -> MailBuilder:
        self._attachments.append(
            {"filename": filename, "data": data, "mime_type": mime_type}
        )
        return self

    def add_file_attachment(self, file_path: str) -> MailBuilder:
        path = os.path.expanduser(file_path)
        if not os.path.isfile(path):
            return self
        mime_type, _ = mimetypes.guess_type(path)
        if mime_type is None:
            mime_type = "application/octet-stream"
        filename = os.path.basename(path)
        with open(path, "rb") as f:
            data = f.read()
        return self.add_attachment(filename, data, mime_type)

    def add_header(self, name: str, value: str) -> MailBuilder:
        self._custom_headers[name] = value
        return self

    def build(self) -> MIMEMultipart:
        has_html = bool(self._html_body)
        has_attachments = bool(self._attachments)

        if has_attachments:
            msg = MIMEMultipart("mixed")
        else:
            msg = MIMEMultipart("alternative") if has_html else MIMEMultipart()

        if self._from_name:
            msg["From"] = formataddr((self._from_name, self._from_addr))
        else:
            msg["From"] = self._from_addr

        if self._to:
            msg["To"] = ", ".join(self._to)
        if self._cc:
            msg["Cc"] = ", ".join(self._cc)

        msg["Subject"] = self._subject
        msg["Date"] = formatdate(localtime=True)
        msg["Message-ID"] = make_msgid(
            domain=self._from_addr.split("@")[1]
            if "@" in self._from_addr
            else "localhost"
        )

        if self._reply_to:
            msg["Reply-To"] = self._reply_to
        if self._in_reply_to:
            msg["In-Reply-To"] = self._in_reply_to
        if self._references:
            msg["References"] = self._references

        for name, value in self._custom_headers.items():
            msg[name] = value

        if has_attachments:
            if has_html:
                text_part = MIMEMultipart("alternative")
                if self._text_body:
                    text_part.attach(MIMEText(self._text_body, "plain", "utf-8"))
                text_part.attach(MIMEText(self._html_body, "html", "utf-8"))
                msg.attach(text_part)
            elif self._text_body:
                msg.attach(MIMEText(self._text_body, "plain", "utf-8"))

            for att in self._attachments:
                att_part = MIMEBase(*att["mime_type"].split("/", 1))
                att_part.set_payload(att["data"])
                encoders.encode_base64(att_part)
                safe_name = att["filename"]
                att_part.add_header(
                    "Content-Disposition", "attachment", filename=safe_name
                )
                msg.attach(att_part)
        else:
            if has_html:
                if self._text_body:
                    msg.attach(MIMEText(self._text_body, "plain", "utf-8"))
                msg.attach(MIMEText(self._html_body, "html", "utf-8"))
            elif self._text_body:
                msg.attach(MIMEText(self._text_body, "plain", "utf-8"))

        return msg

    def build_forward(self, original_text: str, original_headers: str) -> MIMEMultipart:
        forward_body = f"\n\n---------- 转发的邮件 ----------\n{original_headers}\n\n{original_text}"
        self._text_body = (self._text_body or "") + forward_body
        return self.build()

    def build_reply(self, original_text: str, original_headers: str) -> MIMEMultipart:
        reply_body = f"\n\n于 {original_headers} 写道:\n"
        for line in original_text.splitlines():
            reply_body += f"> {line}\n"
        self._text_body = (self._text_body or "") + reply_body
        return self.build()
