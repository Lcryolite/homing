from __future__ import annotations

import email
import logging
from email import policy
from email.header import decode_header
from email.utils import parseaddr, parsedate_to_datetime
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


def decode_header_value(value: str | None) -> str:
    if not value:
        return ""
    parts = decode_header(value)
    decoded = []
    for part, charset in parts:
        if isinstance(part, bytes):
            decoded.append(part.decode(charset or "utf-8", errors="replace"))
        else:
            decoded.append(part)
    return "".join(decoded)


class ParsedEmail:
    def __init__(self) -> None:
        self.subject: str = ""
        self.sender_name: str = ""
        self.sender_addr: str = ""
        self.to_addrs: list[str] = []
        self.cc_addrs: list[str] = []
        self.bcc_addrs: list[str] = []
        self.date: str = ""
        self.message_id: str = ""
        self.in_reply_to: str = ""
        self.references: str = ""
        self.text_body: str = ""
        self.html_body: str = ""
        self.attachments: list[dict[str, Any]] = []
        self.has_attachment: bool = False
        self.preview_text: str = ""

    @property
    def display_sender(self) -> str:
        if self.sender_name:
            return f"{self.sender_name} <{self.sender_addr}>"
        return self.sender_addr


class MailParser:
    @staticmethod
    def parse_raw(raw: bytes) -> ParsedEmail:
        msg = email.message_from_bytes(raw, policy=policy.default)
        parsed = ParsedEmail()

        parsed.subject = decode_header_value(msg.get("Subject", ""))
        from_header = msg.get("From", "")
        parsed.sender_name, parsed.sender_addr = parseaddr(from_header)
        parsed.sender_name = decode_header_value(parsed.sender_name)

        parsed.to_addrs = parse_address_list(msg.get("To", ""))
        parsed.cc_addrs = parse_address_list(msg.get("Cc", ""))
        parsed.bcc_addrs = parse_address_list(msg.get("Bcc", ""))

        try:
            dt = parsedate_to_datetime(msg.get("Date", ""))
            parsed.date = dt.isoformat()
        except Exception:
            parsed.date = msg.get("Date", "")

        parsed.message_id = msg.get("Message-ID", "")
        parsed.in_reply_to = msg.get("In-Reply-To", "")
        parsed.references = msg.get("References", "")

        MailParser._extract_bodies(msg, parsed)
        MailParser._extract_attachments(msg, parsed)

        if parsed.text_body:
            text = parsed.text_body.replace("\r", "").replace("\n", " ").strip()
            while "  " in text:
                text = text.replace("  ", " ")
            parsed.preview_text = text[:100] + ("..." if len(text) > 100 else "")

        return parsed

    @staticmethod
    def parse_file(file_path: str | Path) -> ParsedEmail | None:
        p = Path(file_path)
        if not p.exists():
            return None
        raw = p.read_bytes()
        return MailParser.parse_raw(raw)

    @staticmethod
    def _extract_bodies(msg: email.message.EmailMessage, parsed: ParsedEmail) -> None:
        if msg.is_multipart():
            for part in msg.walk():
                content_type = part.get_content_type()
                disposition = str(part.get("Content-Disposition", ""))

                if "attachment" in disposition:
                    continue

                if content_type == "text/plain" and not parsed.text_body:
                    try:
                        charset = part.get_content_charset() or "utf-8"
                        parsed.text_body = part.get_payload(decode=True).decode(
                            charset, errors="replace"
                        )
                    except Exception as e:
                        logger.debug("Suppressed exception in %s: %s", __name__, e)
                elif content_type == "text/html" and not parsed.html_body:
                    try:
                        charset = part.get_content_charset() or "utf-8"
                        parsed.html_body = part.get_payload(decode=True).decode(
                            charset, errors="replace"
                        )
                    except Exception as e:
                        logger.debug("Suppressed exception in %s: %s", __name__, e)
        else:
            content_type = msg.get_content_type()
            try:
                charset = msg.get_content_charset() or "utf-8"
                payload = msg.get_payload(decode=True)
                if payload:
                    body = payload.decode(charset, errors="replace")
                    if content_type == "text/html":
                        parsed.html_body = body
                    else:
                        parsed.text_body = body
            except Exception as e:
                logger.debug("Suppressed exception in %s: %s", __name__, e)

    @staticmethod
    def _extract_attachments(
        msg: email.message.EmailMessage, parsed: ParsedEmail
    ) -> None:
        for part in msg.walk():
            if part.is_multipart():
                continue
            disposition = part.get_content_disposition()
            if disposition in ("attachment", "inline"):
                filename = part.get_filename()
                if filename:
                    filename = decode_header_value(filename)
                    payload = part.get_payload(decode=True)
                    if payload:
                        parsed.attachments.append(
                            {
                                "filename": filename,
                                "data": payload,
                                "mime_type": part.get_content_type(),
                                "size": len(payload),
                                "disposition": disposition,
                            }
                        )
                        parsed.has_attachment = True


def parse_address_list(raw: str | None) -> list[str]:
    if not raw:
        return []
    addresses = []
    for addr in raw.split(","):
        _, email_addr = parseaddr(addr.strip())
        if email_addr:
            addresses.append(email_addr)
    return addresses
