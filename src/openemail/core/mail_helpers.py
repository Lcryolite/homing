"""Shared mail parsing helpers used across IMAP, POP3, and mail parser modules."""

from __future__ import annotations

from email.header import decode_header
from email.utils import parseaddr


def decode_header_value(value: str | None) -> str:
    """Decode an email header value that may use RFC 2047 encoding."""
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


def parse_address_list(raw: str | None) -> list[str]:
    """Parse a comma-separated email address string into a list of email addresses."""
    if not raw:
        return []
    addresses = []
    for addr in raw.split(","):
        _, email_addr = parseaddr(addr.strip())
        if email_addr:
            addresses.append(email_addr)
    return addresses


def extract_preview(text: str, max_len: int = 100) -> str:
    """Extract a single-line preview from email body text."""
    text = text.replace("\r", "").replace("\n", " ").strip()
    while "  " in text:
        text = text.replace("  ", " ")
    return text[:max_len] + ("..." if len(text) > max_len else "")
