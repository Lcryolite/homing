from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any

from openemail.storage.database import db

VALID_STATUSES = ("pending", "in_progress", "completed", "cancelled")
VALID_PRIORITIES = ("low", "normal", "high", "urgent")


@dataclass
class Todo:
    id: int = 0
    account_id: int | None = None
    title: str = ""
    description: str = ""
    status: str = "pending"
    priority: str = "normal"
    due_date: str = ""
    reminder: int | None = None
    tags: str = ""
    email_uid: str = ""
    sync_enabled: bool = False
    sync_provider: str = ""
    sync_url: str = ""
    sync_etag: str = ""
    last_synced_at: str = ""
    created_at: str = ""
    updated_at: str = ""

    @property
    def is_overdue(self) -> bool:
        if not self.due_date or self.status in ("completed", "cancelled"):
            return False
        try:
            due = datetime.fromisoformat(self.due_date.replace("Z", "+00:00"))
            now = datetime.now(due.tzinfo)
            return due < now
        except (ValueError, TypeError):
            return False

    @property
    def is_due_today(self) -> bool:
        if not self.due_date:
            return False
        try:
            due = datetime.fromisoformat(self.due_date.replace("Z", "+00:00"))
            now = datetime.now(due.tzinfo)
            return due.date() == now.date()
        except (ValueError, TypeError):
            return False

    @property
    def display_priority(self) -> str:
        labels = {"low": "Low", "normal": "Normal", "high": "High", "urgent": "Urgent"}
        return labels.get(self.priority, self.priority)

    @property
    def display_status(self) -> str:
        labels = {
            "pending": "Pending",
            "in_progress": "In Progress",
            "completed": "Completed",
            "cancelled": "Cancelled",
        }
        return labels.get(self.status, self.status)

    def save(self) -> int:
        if self.status not in VALID_STATUSES:
            raise ValueError(f"Invalid status: {self.status}")
        if self.priority not in VALID_PRIORITIES:
            raise ValueError(f"Invalid priority: {self.priority}")
        data = {
            "account_id": self.account_id,
            "title": self.title,
            "description": self.description,
            "status": self.status,
            "priority": self.priority,
            "due_date": self.due_date,
            "reminder": self.reminder,
            "tags": self.tags,
            "email_uid": self.email_uid,
            "sync_enabled": int(self.sync_enabled),
            "sync_provider": self.sync_provider,
            "sync_url": self.sync_url,
            "sync_etag": self.sync_etag,
            "last_synced_at": self.last_synced_at,
            "updated_at": datetime.now().isoformat(),
        }
        if self.id == 0:
            self.id = db.insert("todos", data)
        else:
            db.update("todos", data, "id = ?", (self.id,))
        return self.id

    def delete(self) -> None:
        if self.id:
            db.delete("todos", "id = ?", (self.id,))
            self.id = 0

    def toggle_complete(self) -> None:
        if self.status == "completed":
            self.status = "pending"
        else:
            self.status = "completed"
        db.update(
            "todos",
            {"status": self.status, "updated_at": datetime.now().isoformat()},
            "id = ?",
            (self.id,),
        )

    @classmethod
    def get_by_id(cls, todo_id: int) -> Todo | None:
        row = db.fetchone("SELECT * FROM todos WHERE id = ?", (todo_id,))
        if row is None:
            return None
        return cls._from_row(row)

    @classmethod
    def get_all(
        cls, account_id: int | None = None, limit: int = 100, offset: int = 0
    ) -> list[Todo]:
        if account_id is not None:
            rows = db.fetchall(
                "SELECT * FROM todos WHERE account_id = ? ORDER BY created_at DESC LIMIT ? OFFSET ?",
                (account_id, limit, offset),
            )
        else:
            rows = db.fetchall(
                "SELECT * FROM todos ORDER BY created_at DESC LIMIT ? OFFSET ?",
                (limit, offset),
            )
        return [cls._from_row(r) for r in rows]

    @classmethod
    def get_by_status(cls, status: str, account_id: int | None = None) -> list[Todo]:
        if status not in VALID_STATUSES:
            raise ValueError(f"Invalid status: {status}")
        if account_id is not None:
            rows = db.fetchall(
                "SELECT * FROM todos WHERE status = ? AND account_id = ? ORDER BY created_at DESC",
                (status, account_id),
            )
        else:
            rows = db.fetchall(
                "SELECT * FROM todos WHERE status = ? ORDER BY created_at DESC",
                (status,),
            )
        return [cls._from_row(r) for r in rows]

    @classmethod
    def get_by_priority(
        cls, priority: str, account_id: int | None = None
    ) -> list[Todo]:
        if priority not in VALID_PRIORITIES:
            raise ValueError(f"Invalid priority: {priority}")
        if account_id is not None:
            rows = db.fetchall(
                "SELECT * FROM todos WHERE priority = ? AND account_id = ? ORDER BY created_at DESC",
                (priority, account_id),
            )
        else:
            rows = db.fetchall(
                "SELECT * FROM todos WHERE priority = ? ORDER BY created_at DESC",
                (priority,),
            )
        return [cls._from_row(r) for r in rows]

    @classmethod
    def get_overdue(cls, account_id: int | None = None) -> list[Todo]:
        now = datetime.now().isoformat()
        if account_id is not None:
            rows = db.fetchall(
                "SELECT * FROM todos WHERE due_date < ? AND due_date != '' AND status NOT IN ('completed', 'cancelled') AND account_id = ? ORDER BY due_date ASC",
                (now, account_id),
            )
        else:
            rows = db.fetchall(
                "SELECT * FROM todos WHERE due_date < ? AND due_date != '' AND status NOT IN ('completed', 'cancelled') ORDER BY due_date ASC",
                (now,),
            )
        return [cls._from_row(r) for r in rows]

    @classmethod
    def get_due_today(cls, account_id: int | None = None) -> list[Todo]:
        today = datetime.now().date()
        start = datetime.combine(today, datetime.min.time()).isoformat()
        end = datetime.combine(today, datetime.max.time()).isoformat()
        if account_id is not None:
            rows = db.fetchall(
                "SELECT * FROM todos WHERE due_date >= ? AND due_date <= ? AND status NOT IN ('completed', 'cancelled') AND account_id = ? ORDER BY due_date ASC",
                (start, end, account_id),
            )
        else:
            rows = db.fetchall(
                "SELECT * FROM todos WHERE due_date >= ? AND due_date <= ? AND status NOT IN ('completed', 'cancelled') ORDER BY due_date ASC",
                (start, end),
            )
        return [cls._from_row(r) for r in rows]

    @classmethod
    def get_due_this_week(cls, account_id: int | None = None) -> list[Todo]:
        today = datetime.now().date()
        start = datetime.combine(today, datetime.min.time()).isoformat()
        end_of_week = datetime.combine(
            today + timedelta(days=(6 - today.weekday())), datetime.max.time()
        ).isoformat()
        if account_id is not None:
            rows = db.fetchall(
                "SELECT * FROM todos WHERE due_date >= ? AND due_date <= ? AND status NOT IN ('completed', 'cancelled') AND account_id = ? ORDER BY due_date ASC",
                (start, end_of_week, account_id),
            )
        else:
            rows = db.fetchall(
                "SELECT * FROM todos WHERE due_date >= ? AND due_date <= ? AND status NOT IN ('completed', 'cancelled') ORDER BY due_date ASC",
                (start, end_of_week),
            )
        return [cls._from_row(r) for r in rows]

    @classmethod
    def _from_row(cls, row: dict) -> Todo:
        return cls(
            id=row["id"],
            account_id=row["account_id"],
            title=row["title"] or "",
            description=row["description"] or "",
            status=row["status"] or "pending",
            priority=row["priority"] or "normal",
            due_date=row["due_date"] or "",
            reminder=row["reminder"],
            tags=row["tags"] or "",
            email_uid=row["email_uid"] or "",
            sync_enabled=bool(row["sync_enabled"]),
            sync_provider=row["sync_provider"] or "",
            sync_url=row["sync_url"] or "",
            sync_etag=row["sync_etag"] or "",
            last_synced_at=row["last_synced_at"] or "",
            created_at=row["created_at"] or "",
            updated_at=row["updated_at"] or "",
        )
