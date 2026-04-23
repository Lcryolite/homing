from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from openemail.models.tag import Tag

from openemail.storage.database import db


@dataclass
class Email:
    id: int = 0
    account_id: int = 0
    folder_id: int = 0
    uid: str = ""
    message_id: str = ""
    subject: str = ""
    sender_name: str = ""
    sender_addr: str = ""
    to_addrs: str = "[]"
    cc_addrs: str = "[]"
    bcc_addrs: str = "[]"
    date: str = ""
    size: int = 0
    is_read: bool = False
    is_flagged: bool = False
    is_deleted: bool = False
    is_spam: bool = False
    spam_reason: str = ""
    has_attachment: bool = False
    preview_text: str = ""
    file_path: str = ""
    in_reply_to: str = ""
    references: str = ""
    created_at: str = ""
    _search_snippet: str = ""
    _search_highlight: str = ""

    @property
    def to_list(self) -> list[str]:
        try:
            return json.loads(self.to_addrs)
        except (json.JSONDecodeError, TypeError):
            return []

    @to_list.setter
    def to_list(self, value: list[str]) -> None:
        self.to_addrs = json.dumps(value, ensure_ascii=False)

    @property
    def cc_list(self) -> list[str]:
        try:
            return json.loads(self.cc_addrs)
        except (json.JSONDecodeError, TypeError):
            return []

    @cc_list.setter
    def cc_list(self, value: list[str]) -> None:
        self.cc_addrs = json.dumps(value, ensure_ascii=False)

    @property
    def bcc_list(self) -> list[str]:
        try:
            return json.loads(self.bcc_addrs)
        except (json.JSONDecodeError, TypeError):
            return []

    @bcc_list.setter
    def bcc_list(self, value: list[str]) -> None:
        self.bcc_addrs = json.dumps(value, ensure_ascii=False)

    @property
    def display_sender(self) -> str:
        if self.sender_name:
            return f"{self.sender_name} <{self.sender_addr}>"
        return self.sender_addr

    @property
    def display_date(self) -> str:
        if not self.date:
            return ""
        try:
            dt = datetime.fromisoformat(self.date.replace("Z", "+00:00"))
            now = datetime.now(dt.tzinfo)
            diff = now - dt
            if diff.days == 0:
                return dt.strftime("%H:%M")
            elif diff.days < 7:
                return dt.strftime("%a %H:%M")
            elif dt.year == now.year:
                return dt.strftime("%m-%d %H:%M")
            return dt.strftime("%Y-%m-%d")
        except (ValueError, TypeError):
            return self.date

    def save(self) -> int:
        data = {
            "account_id": self.account_id,
            "folder_id": self.folder_id,
            "uid": self.uid,
            "message_id": self.message_id,
            "subject": self.subject,
            "sender_name": self.sender_name,
            "sender_addr": self.sender_addr,
            "to_addrs": self.to_addrs,
            "cc_addrs": self.cc_addrs,
            "bcc_addrs": self.bcc_addrs,
            "date": self.date,
            "size": self.size,
            "is_read": int(self.is_read),
            "is_flagged": int(self.is_flagged),
            "is_deleted": int(self.is_deleted),
            "is_spam": int(self.is_spam),
            "spam_reason": self.spam_reason,
            "has_attachment": int(self.has_attachment),
            "preview_text": self.preview_text,
            "file_path": self.file_path,
            "in_reply_to": self.in_reply_to,
            "references": self.references,
        }
        if self.id == 0:
            self.id = db.insert("emails", data)
        else:
            db.update("emails", data, "id = ?", (self.id,))
        return self.id

    def delete(self) -> None:
        if self.id:
            # Clean up disk files before removing DB record
            from openemail.storage.mail_store import mail_store

            if self.file_path:
                mail_store.delete_raw(self.file_path)
            if self.has_attachment:
                mail_store.delete_attachments(self.id)
            db.delete("emails", "id = ?", (self.id,))
            self.id = 0

    def mark_read(self) -> None:
        self.is_read = True
        db.update("emails", {"is_read": 1}, "id = ?", (self.id,))

    def mark_flagged(self, flagged: bool = True) -> None:
        self.is_flagged = flagged
        db.update("emails", {"is_flagged": int(flagged)}, "id = ?", (self.id,))

    def mark_spam(self, reason: str = "") -> None:
        self.is_spam = True
        self.spam_reason = reason
        db.update("emails", {"is_spam": 1, "spam_reason": reason}, "id = ?", (self.id,))

    def mark_not_spam(self) -> None:
        self.is_spam = False
        self.spam_reason = ""
        db.update("emails", {"is_spam": 0, "spam_reason": ""}, "id = ?", (self.id,))

    def move_to_folder(self, folder_id: int) -> None:
        self.folder_id = folder_id
        db.update("emails", {"folder_id": folder_id}, "id = ?", (self.id,))

    @classmethod
    def get_by_id(cls, email_id: int) -> Email | None:
        row = db.fetchone("SELECT * FROM emails WHERE id = ?", (email_id,))
        if row is None:
            return None
        return cls._from_row(row)

    @classmethod
    def get_by_uid(cls, account_id: int, uid: str) -> Email | None:
        row = db.fetchone(
            "SELECT * FROM emails WHERE account_id = ? AND uid = ?", (account_id, uid)
        )
        if row is None:
            return None
        return cls._from_row(row)

    @classmethod
    def get_by_folder(
        cls, folder_id: int, limit: int = 100, offset: int = 0
    ) -> list[Email]:
        rows = db.fetchall(
            "SELECT * FROM emails WHERE folder_id = ? AND is_deleted = 0 ORDER BY date DESC LIMIT ? OFFSET ?",
            (folder_id, limit, offset),
        )
        return [cls._from_row(r) for r in rows]

    @classmethod
    def search(cls, account_id: int, query: str, limit: int = 50) -> list[Email]:
        like = f"%{query}%"
        rows = db.fetchall(
            """SELECT * FROM emails
               WHERE account_id = ? AND is_deleted = 0
               AND (subject LIKE ? OR sender_addr LIKE ? OR sender_name LIKE ? OR preview_text LIKE ?)
               ORDER BY date DESC LIMIT ?""",
            (account_id, like, like, like, like, limit),
        )
        return [cls._from_row(r) for r in rows]

    @classmethod
    def get_spam(cls, account_id: int, limit: int = 100) -> list[Email]:
        rows = db.fetchall(
            "SELECT * FROM emails WHERE account_id = ? AND is_spam = 1 AND is_deleted = 0 ORDER BY date DESC LIMIT ?",
            (account_id, limit),
        )
        return [cls._from_row(r) for r in rows]

    @classmethod
    def get_unread_count(cls, folder_id: int) -> int:
        row = db.fetchone(
            "SELECT COUNT(*) as c FROM emails WHERE folder_id = ? AND is_read = 0 AND is_deleted = 0",
            (folder_id,),
        )
        return row["c"] if row else 0

    @classmethod
    def _from_row(cls, row) -> Email:
        r = dict(row)  # sqlite3.Row -> dict, 支持 .get()
        return cls(
            id=r["id"],
            account_id=r["account_id"],
            folder_id=r["folder_id"],
            uid=r.get("uid") or "",
            message_id=r.get("message_id") or "",
            subject=r.get("subject") or "",
            sender_name=r.get("sender_name") or "",
            sender_addr=r.get("sender_addr") or "",
            to_addrs=r.get("to_addrs") or "[]",
            cc_addrs=r.get("cc_addrs") or "[]",
            bcc_addrs=r.get("bcc_addrs") or "[]",
            date=r.get("date") or "",
            size=r.get("size") or 0,
            is_read=bool(r.get("is_read")),
            is_flagged=bool(r.get("is_flagged")),
            is_deleted=bool(r.get("is_deleted")),
            is_spam=bool(r.get("is_spam")),
            spam_reason=r.get("spam_reason") or "",
            has_attachment=bool(r.get("has_attachment")),
            preview_text=r.get("preview_text") or "",
            file_path=r.get("file_path") or "",
            in_reply_to=r.get("in_reply_to") or "",
            references=r.get("references") or "",
            created_at=r.get("created_at") or "",
        )

    def get_tags(self) -> list[Tag]:
        from openemail.models.tag import Tag

        rows = db.fetchall(
            "SELECT t.* FROM tags t JOIN email_tags et ON t.id = et.tag_id WHERE et.email_id = ?",
            (self.id,),
        )
        return [Tag._from_row(r) for r in rows]

    def add_tag(self, tag: Tag) -> None:
        db.execute(
            "INSERT OR IGNORE INTO email_tags (email_id, tag_id) VALUES (?, ?)",
            (self.id, tag.id),
        )

    def remove_tag(self, tag: Tag) -> None:
        db.execute(
            "DELETE FROM email_tags WHERE email_id = ? AND tag_id = ?",
            (self.id, tag.id),
        )
