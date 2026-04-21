from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from datetime import datetime
from email.utils import make_msgid
from typing import Any, Optional

from openemail.storage.database import db

logger = logging.getLogger(__name__)


@dataclass
class Draft:
    id: int = 0
    account_id: int = 0
    folder_id: Optional[int] = None
    message_id: str = ""
    uid: str = ""
    from_addr: str = ""
    to_addrs: str = ""
    cc_addrs: str = ""
    bcc_addrs: str = ""
    subject: str = ""
    body_text: str = ""
    body_html: str = ""
    attachments: str = "{}"
    in_reply_to: str = ""
    references: str = ""
    is_local_only: bool = True
    is_syncing: bool = False
    created_at: Optional[str] = None
    updated_at: Optional[str] = None
    synced_at: Optional[str] = None

    def save(self) -> int:
        now = datetime.now().isoformat()
        if not self.message_id:
            domain = (
                self.from_addr.split("@")[1] if "@" in self.from_addr else "localhost"
            )
            self.message_id = make_msgid(domain=domain)

        data = {
            "account_id": self.account_id,
            "folder_id": self.folder_id,
            "message_id": self.message_id,
            "uid": self.uid,
            "from_addr": self.from_addr,
            "to_addrs": self.to_addrs,
            "cc_addrs": self.cc_addrs,
            "bcc_addrs": self.bcc_addrs,
            "subject": self.subject,
            "body_text": self.body_text,
            "body_html": self.body_html,
            "attachments": self.attachments,
            "in_reply_to": self.in_reply_to,
            "references": self.references,
            "is_local_only": int(self.is_local_only),
            "is_syncing": int(self.is_syncing),
            "updated_at": now,
        }

        if self.id == 0:
            data["created_at"] = now
            self.id = db.insert("drafts", data)
        else:
            db.update("drafts", data, "id = ?", (self.id,))
        return self.id

    def delete(self) -> None:
        if self.id:
            db.delete("drafts", "id = ?", (self.id,))
            self.id = 0

    def mark_synced(self, uid: str = "") -> None:
        now = datetime.now().isoformat()
        self.uid = uid
        self.is_local_only = False
        self.is_syncing = False
        self.synced_at = now
        db.update(
            "drafts",
            {
                "uid": uid,
                "is_local_only": 0,
                "is_syncing": 0,
                "synced_at": now,
                "updated_at": now,
            },
            "id = ?",
            (self.id,),
        )

    def get_to_list(self) -> list[str]:
        if not self.to_addrs:
            return []
        return [a.strip() for a in self.to_addrs.split(",") if a.strip()]

    def get_cc_list(self) -> list[str]:
        if not self.cc_addrs:
            return []
        return [a.strip() for a in self.cc_addrs.split(",") if a.strip()]

    def get_attachments_list(self) -> list[dict[str, Any]]:
        if not self.attachments:
            return []
        try:
            return json.loads(self.attachments)
        except (json.JSONDecodeError, TypeError):
            return []

    def set_attachments_list(self, atts: list[dict[str, Any]]) -> None:
        self.attachments = json.dumps(atts, ensure_ascii=False)

    @classmethod
    def get_by_id(cls, draft_id: int) -> Draft | None:
        row = db.fetchone("SELECT * FROM drafts WHERE id = ?", (draft_id,))
        return cls._from_row(row) if row else None

    @classmethod
    def get_by_message_id(cls, account_id: int, message_id: str) -> Draft | None:
        row = db.fetchone(
            "SELECT * FROM drafts WHERE account_id = ? AND message_id = ?",
            (account_id, message_id),
        )
        return cls._from_row(row) if row else None

    @classmethod
    def get_by_account(cls, account_id: int) -> list[Draft]:
        rows = db.fetchall(
            "SELECT * FROM drafts WHERE account_id = ? ORDER BY updated_at DESC",
            (account_id,),
        )
        return [cls._from_row(r) for r in rows]

    @classmethod
    def get_unsynced(cls, account_id: int) -> list[Draft]:
        rows = db.fetchall(
            "SELECT * FROM drafts WHERE account_id = ? AND is_local_only = 1 AND is_syncing = 0",
            (account_id,),
        )
        return [cls._from_row(r) for r in rows]

    @classmethod
    def _from_row(cls, row) -> Draft:
        r = dict(row)  # sqlite3.Row -> dict
        return cls(
            id=r["id"],
            account_id=r["account_id"],
            folder_id=r.get("folder_id"),
            message_id=r.get("message_id") or "",
            uid=r.get("uid") or "",
            from_addr=r.get("from_addr") or "",
            to_addrs=r.get("to_addrs") or "",
            cc_addrs=r.get("cc_addrs") or "",
            bcc_addrs=r.get("bcc_addrs") or "",
            subject=r.get("subject") or "",
            body_text=r.get("body_text") or "",
            body_html=r.get("body_html") or "",
            attachments=r.get("attachments") or "{}",
            in_reply_to=r.get("in_reply_to") or "",
            references=r.get("references") or "",
            is_local_only=bool(r.get("is_local_only", 1)),
            is_syncing=bool(r.get("is_syncing", 0)),
            created_at=r.get("created_at"),
            updated_at=r.get("updated_at"),
            synced_at=r.get("synced_at"),
        )
