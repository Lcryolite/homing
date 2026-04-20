from __future__ import annotations

import asyncio
import email
import poplib
import socket
import ssl
from email import policy
from email.utils import parsedate_to_datetime
from openemail.core.mail_helpers import decode_header_value, parse_address_list, extract_preview
from typing import Any

from openemail.models.account import Account
from openemail.models.email import Email
from openemail.models.folder import Folder
from openemail.storage.mail_store import mail_store


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


def parse_address_list(raw: str | None) -> list[str]:
    if not raw:
        return []
    addresses = []
    for addr in raw.split(","):
        _, email_addr = parseaddr(addr.strip())
        if email_addr:
            addresses.append(email_addr)
    return addresses


def extract_preview(text: str, max_len: int = 100) -> str:
    text = text.replace("\r", "").replace("\n", " ").strip()
    while "  " in text:
        text = text.replace("  ", " ")
    return text[:max_len] + ("..." if len(text) > max_len else "")


class POP3Client:
    def __init__(self, account: Account) -> None:
        self._account = account
        self._client: poplib.POP3 | poplib.POP3_SSL | None = None

    def connect(self) -> bool:
        """连接到POP3服务器并进行认证

        返回:
            bool: 连接和认证是否成功

        异常:
            会抛出具体异常以便调用方进行错误分类
        """
        try:
            if self._account.ssl_mode == "ssl":
                self._client = poplib.POP3_SSL(
                    host=self._account.pop3_host,
                    port=self._account.pop3_port,
                    timeout=30,
                )
            else:
                self._client = poplib.POP3(
                    host=self._account.pop3_host,
                    port=self._account.pop3_port,
                    timeout=30,
                )

            # 测试欢迎消息
            welcome_msg = self._client.getwelcome().decode("utf-8", errors="ignore")
            if not welcome_msg.startswith("+OK"):
                raise ConnectionError(f"服务器欢迎消息异常: {welcome_msg[:100]}")

            # 用户认证
            user_response = self._client.user(self._account.email)
            if not user_response.startswith(b"+OK"):
                raise PermissionError(
                    f"用户认证失败: {user_response.decode('utf-8', errors='ignore')}"
                )

            # 密码认证
            pass_response = self._client.pass_(self._account.password)
            if not pass_response.startswith(b"+OK"):
                raise PermissionError(
                    f"密码认证失败: {pass_response.decode('utf-8', errors='ignore')}"
                )

            return True
        except socket.timeout:
            raise TimeoutError(
                f"POP3连接超时: {self._account.pop3_host}:{self._account.pop3_port}"
            )
        except ConnectionRefusedError:
            raise ConnectionRefusedError(
                f"POP3连接被拒绝: {self._account.pop3_host}:{self._account.pop3_port}"
            )
        except ssl.SSLError as ssl_error:
            raise ssl_error
        except Exception as e:
            # 重新抛出原始异常
            raise e

    def disconnect(self) -> None:
        if self._client:
            try:
                self._client.quit()
            except Exception:
                pass
            self._client = None

    def get_message_count(self) -> int:
        if not self._client:
            return 0
        count, _ = self._client.stat()
        return count

    def get_message_uidl_list(self) -> list[str]:
        if not self._client:
            return []
        _, uidl_list, _ = self._client.uidl()
        return [
            uidl.decode() if isinstance(uidl, bytes) else uidl for uidl in uidl_list
        ]

    def fetch_message(self, msg_num: int) -> bytes | None:
        if not self._client:
            return None
        try:
            _, lines, _ = self._client.retr(msg_num)
            return b"\r\n".join(lines)
        except Exception as e:
            print(f"POP3 fetch error for msg {msg_num}: {e}")
            return None

    def delete_message(self, msg_num: int) -> bool:
        if not self._client:
            return False
        try:
            self._client.dele(msg_num)
            return True
        except Exception:
            return False

    def sync_emails(self, folder_id: int) -> int:
        if not self._client:
            return 0

        from openemail.storage.database import db
        import json

        uidl_list = self.get_message_uidl_list()
        existing_uids = {
            r["uid"]
            for r in db.fetchall(
                "SELECT uid FROM emails WHERE account_id = ? AND folder_id = ?",
                (self._account.id, folder_id),
            )
        }

        synced = 0
        for i, uidl_entry in enumerate(uidl_list):
            parts = uidl_entry.split()
            if len(parts) < 2:
                continue
            msg_num_str, uid = parts[0], parts[1]

            if uid in existing_uids:
                continue

            raw = self.fetch_message(int(msg_num_str))
            if raw is None:
                continue

            email_obj = self._parse_message(uid, raw, folder_id)
            if email_obj:
                file_path = mail_store.save_raw(self._account.id, "INBOX", uid, raw)
                email_obj.file_path = str(file_path)
                email_obj.save()
                synced += 1

        return synced

    def _parse_message(self, uid: str, raw: bytes, folder_id: int) -> Email | None:
        try:
            msg = email.message_from_bytes(raw, policy=policy.default)

            subject = decode_header_value(msg.get("Subject", ""))
            from_header = msg.get("From", "")
            sender_name, sender_addr = parseaddr(from_header)
            sender_name = decode_header_value(sender_name)

            to_list = parse_address_list(msg.get("To", ""))
            cc_list = parse_address_list(msg.get("Cc", ""))
            bcc_list = parse_address_list(msg.get("Bcc", ""))

            date_str = ""
            try:
                dt = parsedate_to_datetime(msg.get("Date", ""))
                date_str = dt.isoformat()
            except Exception:
                date_str = msg.get("Date", "")

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

            return Email(
                account_id=self._account.id,
                folder_id=folder_id,
                uid=uid,
                message_id=msg.get("Message-ID", ""),
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
                preview_text=extract_preview(preview_text),
            )
        except Exception as e:
            print(f"Error parsing POP3 email uid={uid}: {e}")
            return None
