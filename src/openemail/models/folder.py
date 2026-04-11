from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from openemail.storage.database import db

SYSTEM_FOLDERS: list[str] = [
    "INBOX",
    "Sent",
    "Drafts",
    "Spam",
    "Trash",
]


@dataclass
class Folder:
    id: int = 0
    account_id: int = 0
    name: str = ""
    path: str = ""
    unread_count: int = 0
    is_system: bool = False

    def save(self) -> int:
        data = {
            "account_id": self.account_id,
            "name": self.name,
            "path": self.path,
            "unread_count": self.unread_count,
            "is_system": int(self.is_system),
        }
        if self.id == 0:
            self.id = db.insert("folders", data)
        else:
            db.update("folders", data, "id = ?", (self.id,))
        return self.id

    def delete(self) -> None:
        if self.id:
            db.delete("folders", "id = ?", (self.id,))
            self.id = 0

    def update_unread(self) -> None:
        count = db.fetchone(
            "SELECT COUNT(*) as c FROM emails WHERE folder_id = ? AND is_read = 0 AND is_deleted = 0",
            (self.id,),
        )
        self.unread_count = count["c"] if count else 0
        db.update("folders", {"unread_count": self.unread_count}, "id = ?", (self.id,))

    @classmethod
    def get_by_id(cls, folder_id: int) -> Folder | None:
        row = db.fetchone("SELECT * FROM folders WHERE id = ?", (folder_id,))
        if row is None:
            return None
        return cls._from_row(row)

    @classmethod
    def get_by_name(cls, account_id: int, name: str) -> Folder | None:
        row = db.fetchone(
            "SELECT * FROM folders WHERE account_id = ? AND name = ?",
            (account_id, name),
        )
        if row is None:
            return None
        return cls._from_row(row)

    @classmethod
    def get_by_account(cls, account_id: int) -> list[Folder]:
        rows = db.fetchall(
            "SELECT * FROM folders WHERE account_id = ? ORDER BY name", (account_id,)
        )
        return [cls._from_row(r) for r in rows]

    @classmethod
    def ensure_system_folders(cls, account_id: int) -> list[Folder]:
        folders = []
        for name in SYSTEM_FOLDERS:
            existing = cls.get_by_name(account_id, name)
            if existing:
                folders.append(existing)
            else:
                folder = cls(
                    account_id=account_id, name=name, path=name, is_system=True
                )
                folder.save()
                folders.append(folder)
        return folders

    @classmethod
    def _from_row(cls, row: dict) -> Folder:
        return cls(
            id=row["id"],
            account_id=row["account_id"],
            name=row["name"],
            path=row["path"] or "",
            unread_count=row["unread_count"] or 0,
            is_system=bool(row["is_system"]),
        )
