from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime
from typing import Optional

from openemail.storage.database import db

logger = logging.getLogger(__name__)


@dataclass
class EmailThread:
    id: int = 0
    account_id: int = 0
    subject: str = ""
    message_count: int = 1
    last_date: Optional[str] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None

    def save(self) -> int:
        now = datetime.now().isoformat()
        data = {
            "account_id": self.account_id,
            "subject": self.subject,
            "message_count": self.message_count,
            "last_date": self.last_date,
            "updated_at": now,
        }
        if self.id == 0:
            data["created_at"] = now
            self.id = db.insert("email_threads", data)
        else:
            db.update("email_threads", data, "id = ?", (self.id,))
        return self.id

    def delete(self) -> None:
        if self.id:
            db.delete("email_thread_members", "thread_id = ?", (self.id,))
            db.delete("email_threads", "id = ?", (self.id,))
            self.id = 0

    def add_email(self, email_id: int) -> None:
        if not self.id:
            return
        existing = db.fetchone(
            "SELECT id FROM email_thread_members WHERE thread_id = ? AND email_id = ?",
            (self.id, email_id),
        )
        if not existing:
            db.insert(
                "email_thread_members", {"thread_id": self.id, "email_id": email_id}
            )
            self.message_count += 1
            self.save()

    def get_email_ids(self) -> list[int]:
        if not self.id:
            return []
        rows = db.fetchall(
            "SELECT email_id FROM email_thread_members WHERE thread_id = ? ORDER BY email_id",
            (self.id,),
        )
        return [r["email_id"] for r in rows]

    @classmethod
    def get_by_id(cls, thread_id: int) -> EmailThread | None:
        row = db.fetchone("SELECT * FROM email_threads WHERE id = ?", (thread_id,))
        return cls._from_row(row) if row else None

    @classmethod
    def get_by_account(cls, account_id: int) -> list[EmailThread]:
        rows = db.fetchall(
            "SELECT * FROM email_threads WHERE account_id = ? ORDER BY last_date DESC",
            (account_id,),
        )
        return [cls._from_row(r) for r in rows]

    @classmethod
    def find_by_email_id(cls, email_id: int) -> EmailThread | None:
        row = db.fetchone(
            """SELECT t.* FROM email_threads t
               JOIN email_thread_members m ON t.id = m.thread_id
               WHERE m.email_id = ?""",
            (email_id,),
        )
        return cls._from_row(row) if row else None

    @classmethod
    def _from_row(cls, row) -> EmailThread:
        r = dict(row)  # sqlite3.Row -> dict
        return cls(
            id=r["id"],
            account_id=r["account_id"],
            subject=r.get("subject") or "",
            message_count=r.get("message_count", 1),
            last_date=r.get("last_date"),
            created_at=r.get("created_at"),
            updated_at=r.get("updated_at"),
        )
