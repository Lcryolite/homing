from __future__ import annotations

import asyncio
import email
import logging

logger = logging.getLogger(__name__)
from email import policy
from email.utils import parsedate_to_datetime
from openemail.core.mail_helpers import decode_header_value, parse_address_list, extract_preview
from typing import Any

# 条件导入aioimaplib
try:
    import aioimaplib

    AIOIMAPLIB_AVAILABLE = True
    from aioimaplib import AioImap
except ImportError:
    AIOIMAPLIB_AVAILABLE = False

    # 使用Python标准库imaplib包装成异步接口
    import imaplib
    import ssl as _ssl

    class _SyncImapWrapper:
        """将同步imaplib包装为异步接口，兼容aioimaplib的API"""

        def __init__(self, host, port=993, ssl_mode=None, timeout=30):
            self._host = host
            self._port = port
            self._ssl_mode = ssl_mode
            self._timeout = timeout
            self._conn = None

        async def wait_hello_from_server(self):
            if self._ssl_mode == "ssl" or self._port == 993:
                ctx = _ssl.create_default_context()
                self._conn = imaplib.IMAP4_SSL(
                    self._host, self._port, ssl_context=ctx, timeout=self._timeout
                )
            else:
                self._conn = imaplib.IMAP4(
                    self._host, self._port, timeout=self._timeout
                )
                if self._ssl_mode == "starttls":
                    ctx = _ssl.create_default_context()
                    self._conn.starttls(ssl_context=ctx)

        async def login(self, username, password):
            if not self._conn:
                await self.wait_hello_from_server()
            return self._conn.login(username, password)

        async def xoauth2(self, user, token):
            if not self._conn:
                await self.wait_hello_from_server()
            auth_string = f"user={user}\x01auth=Bearer {token}\x01\x01"
            return self._conn.authenticate("XOAUTH2", lambda x: auth_string.encode())

        async def select(self, mailbox="INBOX"):
            return self._conn.select(mailbox)

        async def list(self, reference='""', pattern="*"):
            return self._conn.list(reference, pattern)

        async def search(self, *criteria, charset=None, by_uid=False):
            if charset:
                return self._conn.search(charset, *criteria)
            return self._conn.search(None, *criteria)

        async def fetch(self, message_set, *args):
            return self._conn.fetch(message_set, *args)

        async def store(self, message_set, flags_str, flags):
            return self._conn.store(message_set, flags_str, flags)

        async def copy(self, message_set, mailbox):
            return self._conn.copy(message_set, mailbox)

        async def expunge(self):
            return self._conn.expunge()

        async def logout(self):
            if self._conn:
                try:
                    return self._conn.logout()
                except Exception as e:
                    logger.debug("Suppressed exception in %s: %s", __name__, e)
            return ("OK", [b"Logout"])

        async def idle(self, timeout=300):
            # 标准imaplib不支持IDLE，直接返回
            await asyncio.sleep(min(timeout, 30))

        async def noop(self):
            if self._conn:
                return self._conn.noop()
            return ("OK", [b"Noop"])

    AioImap = _SyncImapWrapper

    # 创建兼容的模块对象
    class _MockAioimaplib:
        IMAP4 = imaplib.IMAP4
        IMAP4_SSL = imaplib.IMAP4_SSL
        AioImap = _SyncImapWrapper

    aioimaplib = _MockAioimaplib()

from openemail.models.account import Account
from openemail.models.email import Email
from openemail.models.folder import Folder
from openemail.storage.database import db
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


class IMAPClient:
    def __init__(self, account: Account) -> None:
        self._account = account
        self._client = None
        self._idle_event = asyncio.Event()

    async def connect(self) -> bool:
        try:
            if AIOIMAPLIB_AVAILABLE:
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
                await self._client.wait_hello_from_server()
            else:
                self._client = _SyncImapWrapper(
                    host=self._account.imap_host,
                    port=self._account.imap_port,
                    ssl_mode=self._account.ssl_mode,
                )
                await self._client.wait_hello_from_server()

            if self._account.auth_type == "oauth2":
                # 对于XOAUTH2，使用专门的xoauth2方法
                # aioimaplib的xoauth2方法接受user和token参数
                await self._client.xoauth2(
                    self._account.email, self._account.oauth_token
                )
            else:
                # 标准用户名密码登录
                await self._client.login(self._account.email, self._account.password)

            # 测试连接是否真的成功
            if self._client:
                # 尝试选择INBOX验证连接
                try:
                    await self._client.select("INBOX")
                except Exception as e:
                    # 记录连接测试失败，但连接已建立
                    logging.debug(
                        f"IMAP connection INBOX select test failed (connection still established): {e}"
                    )
            return True
        except Exception as e:
            error_msg = str(e)
            logger.error("IMAP connect error for %s: %s", self._account.email, error_msg)

            # 提供更好的错误提示
            if (
                "username and password not accepted" in error_msg.lower()
                or "invalid credentials" in error_msg.lower()
            ):
                print(f"认证失败！请检查用户名和密码是否正确。")
                print(f"对于Gmail用户：请使用应用专用密码而不是普通密码。")
                print(f"如何获取应用专用密码：")
                print(f"1. 登录Gmail账户")
                print(f"2. 转到账户安全设置")
                print(f"3. 开启两步验证（如未开启）")
                print(f"4. 在'应用专用密码'部分生成新密码")
                print(f"5. 在OpenEmail中使用此密码而非账户密码")
            elif "xoauth2" in error_msg.lower():
                print(f"OAuth2认证失败！Token可能已过期。")
            elif (
                "network is unreachable" in error_msg.lower()
                or "connection refused" in error_msg.lower()
            ):
                print(f"网络连接失败！请检查网络设置和主机名/端口。")

            return False

    async def disconnect(self) -> None:
        if self._client:
            try:
                await self._client.logout()
            except Exception as e:
                logger.debug("Suppressed exception in %s: %s", __name__, e)
            self._client = None

    async def list_folders(self) -> list[dict[str, Any]]:
        if not self._client:
            return []
        _, data = await self._client.list()
        folders = []
        for item in data:
            if isinstance(item, bytes):
                item = item.decode("utf-8", errors="replace")
            if not item or item == b")":
                continue

            flags: list[str] = []
            name = ""

            paren_start = item.find("(")
            if paren_start != -1:
                paren_end = item.find(")", paren_start)
                if paren_end != -1:
                    flags = item[paren_start + 1 : paren_end].split()
                    rest = item[paren_end + 1 :].strip()
                else:
                    rest = item
            else:
                rest = item

            parts = rest.split('"/"')
            if len(parts) >= 2:
                name = parts[-1].strip().strip('"')
            elif parts:
                name = parts[0].strip().strip('"')

            if name:
                folders.append({"name": name, "path": name, "flags": flags})
        return folders

    async def sync_folder(
        self, folder_name: str, folder_id: int, limit: int = 100
    ) -> int:
        if not self._client:
            return 0

        actual_name = await self._resolve_folder_name(folder_name)
        await self._client.select(actual_name)
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
        if len(new_uids) > limit:
            new_uids = new_uids[-limit:]
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

    async def _resolve_folder_name(self, folder_name: str) -> str:
        """将标准文件夹名映射到服务器实际路径，优先使用 PROVIDERS 配置。"""
        from openemail.models.account import PROVIDERS

        # 标准名称 → 服务器文件夹名（不含前缀）
        standard_map = {
            "INBOX": "INBOX",
            "Sent": "Sent Mail",
            "Drafts": "Drafts",
            "Spam": "Spam",
            "Trash": "Trash",
        }

        # 通过 imap_host 匹配 provider，取 folder_prefix
        prefix = ""
        if self._account.imap_host:
            host_lower = self._account.imap_host.lower()
            for _key, cfg in PROVIDERS.items():
                if cfg.get("imap_host", "").lower() == host_lower:
                    prefix = cfg.get("folder_prefix", "")
                    break

        mapped = standard_map.get(folder_name, folder_name)
        if prefix and mapped != "INBOX":
            return f'"{prefix}{mapped}"'
        return mapped

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
                        except Exception as e:
                            logger.debug("Suppressed exception in %s: %s", __name__, e)
                        break
            else:
                if msg.get_content_type() == "text/plain":
                    try:
                        charset = msg.get_content_charset() or "utf-8"
                        preview_text = msg.get_payload(decode=True).decode(
                            charset, errors="replace"
                        )
                    except Exception as e:
                        logger.debug("Suppressed exception in %s: %s", __name__, e)

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
                preview_text=extract_preview(preview_text),
            )
        except Exception as e:
            logger.error("Error parsing email uid={uid}: {e}")
            return None
