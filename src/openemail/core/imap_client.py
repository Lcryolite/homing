from __future__ import annotations

import asyncio
import email
from email import policy
from email.header import decode_header
from email.utils import parseaddr, parsedate_to_datetime
from typing import Any

import aioimaplib

from openemail.core.oauth2 import OAuth2Authenticator
from openemail.models.account import Account
from openemail.models.email import Email
from openemail.models.folder import Folder
from openemail.storage.database import db
from openemail.storage.mail_store import mail_store


def _decode_header_value(value: str | None) -> str:
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


def _parse_address_list(raw: str | None) -> list[str]:
    if not raw:
        return []
    addresses = []
    for addr in raw.split(","):
        _, email_addr = parseaddr(addr.strip())
        if email_addr:
            addresses.append(email_addr)
    return addresses


def _extract_preview(text: str, max_len: int = 100) -> str:
    text = text.replace("\r", "").replace("\n", " ").strip()
    while "  " in text:
        text = text.replace("  ", " ")
    return text[:max_len] + ("..." if len(text) > max_len else "")


class IMAPClient:
    def __init__(self, account: Account) -> None:
        self._account = account
        self._client: aioimaplib.IMAP4 | aioimaplib.IMAP4_SSL | None = None
        self._idle_event = asyncio.Event()

    async def connect(self) -> bool:
        try:
            if self._account.ssl_mode == "ssl":
                self._client = aioimaplib.IMAP4_SSL(
                    host=self._account.imap_host,
                    port=self._account.imap_port,
                )
            else:
                self._client = aioimaplib.IMAP4(
                    host=self._account.imap_host,
                    port=self._account.imap_port,
                )

            if self._account.auth_type == "oauth2":
                auth_string = OAuth2Authenticator.build_xoauth2_string(
                    self._account.email, self._account.oauth_token
                )
                await self._client.authenticate(
                    "XOAUTH2", lambda x: auth_string.encode()
                )
            else:
                await self._client.login(self._account.email, self._account.password)

            return True
        except Exception as e:
            print(f"IMAP connect error for {self._account.email}: {e}")
            return False

    async def disconnect(self) -> None:
        if self._client:
            try:
                await self._client.logout()
            except Exception:
                pass
            self._client = None

    async def list_folders(self) -> list[dict[str, str]]:
        if not self._client:
            return []
        _, data = await self._client.list()
        folders = []
        for item in data:
            if isinstance(item, bytes):
                item = item.decode("utf-8", errors="replace")
            if not item or item == b")":
                continue
            parts = item.split('"/"')
            if len(parts) >= 2:
                name = parts[-1].strip().strip('"')
                path = name
                folders.append({"name": name, "path": path})
        return folders

    async def sync_folder(self, folder_name: str, folder_id: int) -> int:
        if not self._client:
            return 0

        await self._client.select(folder_name)
        _, data = await self._client.search("ALL")
        if not data or not data[0]:
            return 0

        uids = data[0].split()
        if isinstance(uids[0], bytes):
            uids = [u.decode() for u in uids]

        existing_uids = {
            r["uid"]
            for r in db.fetchall(
                "SELECT uid FROM emails WHERE account_id = ? AND folder_id = ?",
                (self._account.id, folder_id),
            )
        }

        new_uids = [u for u in uids if u not in existing_uids]
        synced = 0

        for uid in new_uids:
            _, msg_data = await self._client.fetch(uid, "(RFC822)")
            if not msg_data:
                continue

            raw = None
            for item in msg_data:
                if isinstance(item, tuple) and len(item) >= 2:
                    raw = item[1]
                    break
            if raw is None:
                continue

            if isinstance(raw, str):
                raw = raw.encode("utf-8", errors="replace")

            email_obj = self._parse_message(uid, raw, folder_id)
            if email_obj:
                file_path = mail_store.save_raw(self._account.id, folder_name, uid, raw)
                email_obj.file_path = str(file_path)
                email_obj.save()
                synced += 1

        return synced

    async def fetch_new_emails(self, folder_name: str, folder_id: int) -> list[Email]:
        if not self._client:
            return []

        await self._client.select(folder_name)
        _, data = await self._client.search("ALL")
        if not data or not data[0]:
            return []

        uids = data[0].split()
        if isinstance(uids[0], bytes):
            uids = [u.decode() for u in uids]

        existing_uids = {
            r["uid"]
            for r in db.fetchall(
                "SELECT uid FROM emails WHERE account_id = ? AND folder_id = ?",
                (self._account.id, folder_id),
            )
        }

        new_emails = []
        for uid in uids:
            if uid in existing_uids:
                continue
            _, msg_data = await self._client.fetch(uid, "(RFC822)")
            if not msg_data:
                continue
            raw = None
            for item in msg_data:
                if isinstance(item, tuple) and len(item) >= 2:
                    raw = item[1]
                    break
            if raw is None:
                continue
            if isinstance(raw, str):
                raw = raw.encode("utf-8", errors="replace")

            email_obj = self._parse_message(uid, raw, folder_id)
            if email_obj:
                file_path = mail_store.save_raw(self._account.id, folder_name, uid, raw)
                email_obj.file_path = str(file_path)
                email_obj.save()
                new_emails.append(email_obj)

        return new_emails

    async def move_email(self, uid: str, source_folder: str, dest_folder: str) -> bool:
        if not self._client:
            return False
        try:
            await self._client.select(source_folder)
            await self._client.copy(uid, dest_folder)
            await self._client.store(uid, "+FLAGS", "\\Deleted")
            await self._client.expunge()
            return True
        except Exception:
            return False

    async def delete_email(self, uid: str, folder_name: str) -> bool:
        if not self._client:
            return False
        try:
            await self._client.select(folder_name)
            await self._client.store(uid, "+FLAGS", "\\Deleted")
            await self._client.expunge()
            return True
        except Exception:
            return False

    async def mark_as_read(self, uid: str, folder_name: str) -> bool:
        if not self._client:
            return False
        try:
            await self._client.select(folder_name)
            await self._client.store(uid, "+FLAGS", "\\Seen")
            return True
        except Exception:
            return False

    async def mark_as_flagged(
        self, uid: str, folder_name: str, flagged: bool = True
    ) -> bool:
        if not self._client:
            return False
        try:
            await self._client.select(folder_name)
            flag = "+FLAGS" if flagged else "-FLAGS"
            await self._client.store(uid, f"{flag}", "\\Flagged")
            return True
        except Exception:
            return False

    async def idle(self, folder_name: str, timeout: int = 300) -> list[str]:
        if not self._client:
            return []
        try:
            await self._client.select(folder_name)
            await self._client.idle_start()
            idle_result = await self._client.idle_check(timeout=timeout)
            await self._client.idle_done()
            return idle_result if idle_result else []
        except Exception:
            return []

    def _parse_message(self, uid: str, raw: bytes, folder_id: int) -> Email | None:
        try:
            msg = email.message_from_bytes(raw, policy=policy.default)

            subject = _decode_header_value(msg.get("Subject", ""))
            from_header = msg.get("From", "")
            sender_name, sender_addr = parseaddr(from_header)
            sender_name = _decode_header_value(sender_name)

            to_list = _parse_address_list(msg.get("To", ""))
            cc_list = _parse_address_list(msg.get("Cc", ""))
            bcc_list = _parse_address_list(msg.get("Bcc", ""))

            date_str = ""
            try:
                dt = parsedate_to_datetime(msg.get("Date", ""))
                date_str = dt.isoformat()
            except Exception:
                date_str = msg.get("Date", "")

            message_id = msg.get("Message-ID", "")

            has_attachment = any(
                part.get_content_disposition() in ("attachment", "inline")
                and part.get_filename()
                for part in msg.walk()
                if not part.is_multipart()
            )

            preview_text = ""
            if msg.is_multipart():
                for part in msg.walk():
                    if part.get_content_type() == "text/plain":
                        try:
                            charset = part.get_content_charset() or "utf-8"
                            preview_text = part.get_payload(decode=True).decode(
                                charset, errors="replace"
                            )
                        except Exception:
                            pass
                        break
            else:
                if msg.get_content_type() == "text/plain":
                    try:
                        charset = msg.get_content_charset() or "utf-8"
                        preview_text = msg.get_payload(decode=True).decode(
                            charset, errors="replace"
                        )
                    except Exception:
                        pass

            import json

            return Email(
                account_id=self._account.id,
                folder_id=folder_id,
                uid=uid,
                message_id=message_id,
                subject=subject,
                sender_name=sender_name,
                sender_addr=sender_addr,
                to_addrs=json.dumps(to_list, ensure_ascii=False),
                cc_addrs=json.dumps(cc_list, ensure_ascii=False),
                bcc_addrs=json.dumps(bcc_list, ensure_ascii=False),
                date=date_str,
                size=len(raw),
                is_read=False,
                has_attachment=has_attachment,
                preview_text=_extract_preview(preview_text),
            )
        except Exception as e:
            print(f"Error parsing email uid={uid}: {e}")
            return None
