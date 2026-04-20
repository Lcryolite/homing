from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from openemail.storage.database import db


@dataclass
class CalendarEvent:
    id: int = 0
    account_id: int = 0
    title: str = ""
    description: str = ""
    location: str = ""
    start_time: str = ""
    end_time: str = ""
    is_all_day: bool = False
    recurrence: str = ""
    reminder: int = 0
    color: str = ""
    email_uid: str = ""
    sync_enabled: bool = False
    sync_provider: str = ""
    sync_url: str = ""
    sync_etag: str = ""
    last_synced_at: str = ""
    created_at: str = ""

    @property
    def display_time(self) -> str:
        if not self.start_time:
            return ""
        try:
            dt = datetime.fromisoformat(self.start_time.replace("Z", "+00:00"))
            if self.is_all_day:
                return dt.strftime("%Y-%m-%d")
            if self.end_time:
                end_dt = datetime.fromisoformat(self.end_time.replace("Z", "+00:00"))
                if dt.date() == end_dt.date():
                    return (
                        f"{dt.strftime('%Y-%m-%d %H:%M')} - {end_dt.strftime('%H:%M')}"
                    )
                return f"{dt.strftime('%Y-%m-%d %H:%M')} - {end_dt.strftime('%Y-%m-%d %H:%M')}"
            return dt.strftime("%Y-%m-%d %H:%M")
        except (ValueError, TypeError):
            return self.start_time

    def save(self) -> int:
        data = {
            "account_id": self.account_id,
            "title": self.title,
            "description": self.description,
            "location": self.location,
            "start_time": self.start_time,
            "end_time": self.end_time,
            "is_all_day": int(self.is_all_day),
            "recurrence": self.recurrence,
            "reminder": self.reminder,
            "color": self.color,
            "email_uid": self.email_uid,
            "sync_enabled": int(self.sync_enabled),
            "sync_provider": self.sync_provider,
            "sync_url": self.sync_url,
            "sync_etag": self.sync_etag,
            "last_synced_at": self.last_synced_at,
        }
        if self.id == 0:
            self.id = db.insert("calendar_events", data)
        else:
            db.update("calendar_events", data, "id = ?", (self.id,))
        return self.id

    def delete(self) -> None:
        if self.id:
            db.delete("calendar_events", "id = ?", (self.id,))
            self.id = 0

    @classmethod
    def get_by_id(cls, event_id: int) -> CalendarEvent | None:
        row = db.fetchone("SELECT * FROM calendar_events WHERE id = ?", (event_id,))
        if row is None:
            return None
        return cls._from_row(row)

    @classmethod
    def get_all(cls, limit: int = 100, offset: int = 0) -> list[CalendarEvent]:
        rows = db.fetchall(
            "SELECT * FROM calendar_events ORDER BY start_time ASC LIMIT ? OFFSET ?",
            (limit, offset),
        )
        return [cls._from_row(r) for r in rows]

    @classmethod
    def get_by_account(
        cls, account_id: int, limit: int = 100, offset: int = 0
    ) -> list[CalendarEvent]:
        rows = db.fetchall(
            "SELECT * FROM calendar_events WHERE account_id = ? ORDER BY start_time ASC LIMIT ? OFFSET ?",
            (account_id, limit, offset),
        )
        return [cls._from_row(r) for r in rows]

    @classmethod
    def get_by_date_range(
        cls, start: str, end: str, account_id: int | None = None
    ) -> list[CalendarEvent]:
        if account_id is not None:
            rows = db.fetchall(
                "SELECT * FROM calendar_events WHERE account_id = ? AND start_time >= ? AND start_time <= ? ORDER BY start_time ASC",
                (account_id, start, end),
            )
        else:
            rows = db.fetchall(
                "SELECT * FROM calendar_events WHERE start_time >= ? AND start_time <= ? ORDER BY start_time ASC",
                (start, end),
            )
        return [cls._from_row(r) for r in rows]

    @classmethod
    def get_by_email_uid(cls, account_id: int, email_uid: str) -> CalendarEvent | None:
        row = db.fetchone(
            "SELECT * FROM calendar_events WHERE account_id = ? AND email_uid = ?",
            (account_id, email_uid),
        )
        if row is None:
            return None
        return cls._from_row(row)

    @classmethod
    def get_synced(cls, account_id: int) -> list[CalendarEvent]:
        rows = db.fetchall(
            "SELECT * FROM calendar_events WHERE account_id = ? AND sync_enabled = 1 ORDER BY start_time ASC",
            (account_id,),
        )
        return [cls._from_row(r) for r in rows]

    @classmethod
    def _from_row(cls, row: dict) -> CalendarEvent:
        return cls(
            id=row["id"],
            account_id=row["account_id"] or 0,
            title=row["title"] or "",
            description=row["description"] or "",
            location=row["location"] or "",
            start_time=row["start_time"] or "",
            end_time=row["end_time"] or "",
            is_all_day=bool(row["is_all_day"]),
            recurrence=row["recurrence"] or "",
            reminder=row["reminder"] or 0,
            color=row["color"] or "",
            email_uid=row["email_uid"] or "",
            sync_enabled=bool(row["sync_enabled"]),
            sync_provider=row["sync_provider"] or "",
            sync_url=row["sync_url"] or "",
            sync_etag=row["sync_etag"] or "",
            last_synced_at=row["last_synced_at"] or "",
            created_at=row["created_at"] or "",
        )
