from __future__ import annotations

from dataclasses import dataclass

from openemail.storage.database import db


@dataclass
class Tag:
    id: int = 0
    name: str = ""
    color: str = "#89b4fa"
    icon: str = "🏷️"

    def save(self) -> int:
        data = {
            "name": self.name,
            "color": self.color,
            "icon": self.icon,
        }
        if self.id == 0:
            self.id = db.insert("tags", data)
        else:
            db.update("tags", data, "id = ?", (self.id,))
        return self.id

    def delete(self) -> None:
        if self.id:
            db.delete("tags", "id = ?", (self.id,))
            self.id = 0

    @classmethod
    def get_by_id(cls, tag_id: int) -> Tag | None:
        row = db.fetchone("SELECT * FROM tags WHERE id = ?", (tag_id,))
        if row is None:
            return None
        return cls._from_row(row)

    @classmethod
    def get_by_name(cls, name: str) -> Tag | None:
        row = db.fetchone("SELECT * FROM tags WHERE name = ?", (name,))
        if row is None:
            return None
        return cls._from_row(row)

    @classmethod
    def get_all(cls) -> list[Tag]:
        rows = db.fetchall("SELECT * FROM tags ORDER BY name")
        return [cls._from_row(r) for r in rows]

    @classmethod
    def _from_row(cls, row: dict) -> Tag:
        return cls(
            id=row["id"],
            name=row["name"],
            color=row["color"] or "#89b4fa",
            icon=row["icon"] or "🏷️",
        )
