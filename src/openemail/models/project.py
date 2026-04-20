from __future__ import annotations

from dataclasses import dataclass

from openemail.storage.database import db


@dataclass
class Project:
    id: int = 0
    name: str = ""
    description: str = ""
    color: str = ""
    created_at: str = ""

    def save(self) -> int:
        data = {
            "name": self.name,
            "description": self.description,
            "color": self.color,
        }
        if self.id == 0:
            self.id = db.insert("projects", data)
        else:
            db.update("projects", data, "id = ?", (self.id,))
        return self.id

    def delete(self) -> None:
        if self.id:
            db.delete("projects", "id = ?", (self.id,))
            self.id = 0

    def get_columns(self) -> list[ProjectColumn]:
        rows = db.fetchall(
            "SELECT * FROM project_columns WHERE project_id = ? ORDER BY position",
            (self.id,),
        )
        return [ProjectColumn._from_row(r) for r in rows]

    def add_column(self, name: str) -> ProjectColumn:
        row = db.fetchone(
            "SELECT MAX(position) as max_pos FROM project_columns WHERE project_id = ?",
            (self.id,),
        )
        position = (
            (row["max_pos"] or 0) + 1 if row and row["max_pos"] is not None else 0
        )
        col = ProjectColumn(project_id=self.id, name=name, position=position)
        col.save()
        return col

    @classmethod
    def get_by_id(cls, project_id: int) -> Project | None:
        row = db.fetchone("SELECT * FROM projects WHERE id = ?", (project_id,))
        if row is None:
            return None
        return cls._from_row(row)

    @classmethod
    def get_all(cls) -> list[Project]:
        rows = db.fetchall("SELECT * FROM projects ORDER BY created_at")
        return [cls._from_row(r) for r in rows]

    @classmethod
    def _from_row(cls, row: dict) -> Project:
        return cls(
            id=row["id"],
            name=row["name"] or "",
            description=row["description"] or "",
            color=row["color"] or "",
            created_at=row["created_at"] or "",
        )


@dataclass
class ProjectColumn:
    id: int = 0
    project_id: int = 0
    name: str = ""
    position: int = 0

    def save(self) -> int:
        data = {
            "project_id": self.project_id,
            "name": self.name,
            "position": self.position,
        }
        if self.id == 0:
            self.id = db.insert("project_columns", data)
        else:
            db.update("project_columns", data, "id = ?", (self.id,))
        return self.id

    def delete(self) -> None:
        if self.id:
            db.delete("project_columns", "id = ?", (self.id,))
            self.id = 0

    def get_cards(self) -> list[ProjectCard]:
        rows = db.fetchall(
            "SELECT * FROM project_cards WHERE column_id = ? ORDER BY position",
            (self.id,),
        )
        return [ProjectCard._from_row(r) for r in rows]

    def add_card(self, title: str) -> ProjectCard:
        row = db.fetchone(
            "SELECT MAX(position) as max_pos FROM project_cards WHERE column_id = ?",
            (self.id,),
        )
        position = (
            (row["max_pos"] or 0) + 1 if row and row["max_pos"] is not None else 0
        )
        card = ProjectCard(column_id=self.id, title=title, position=position)
        card.save()
        return card

    def move_card(self, card_id: int, new_position: int) -> None:
        card = ProjectCard.get_by_id(card_id)
        if card is None or card.column_id != self.id:
            return
        old_position = card.position
        if new_position == old_position:
            return
        if new_position < old_position:
            db.execute(
                "UPDATE project_cards SET position = position + 1 WHERE column_id = ? AND position >= ? AND position < ?",
                (self.id, new_position, old_position),
            )
        else:
            db.execute(
                "UPDATE project_cards SET position = position - 1 WHERE column_id = ? AND position > ? AND position <= ?",
                (self.id, old_position, new_position),
            )
        card.position = new_position
        db.update("project_cards", {"position": new_position}, "id = ?", (card.id,))

    @classmethod
    def get_by_id(cls, column_id: int) -> ProjectColumn | None:
        row = db.fetchone("SELECT * FROM project_columns WHERE id = ?", (column_id,))
        if row is None:
            return None
        return cls._from_row(row)

    @classmethod
    def get_all(cls) -> list[ProjectColumn]:
        rows = db.fetchall(
            "SELECT * FROM project_columns ORDER BY project_id, position"
        )
        return [cls._from_row(r) for r in rows]

    @classmethod
    def _from_row(cls, row: dict) -> ProjectColumn:
        return cls(
            id=row["id"],
            project_id=row["project_id"],
            name=row["name"] or "",
            position=row["position"] or 0,
        )


@dataclass
class ProjectCard:
    id: int = 0
    column_id: int = 0
    title: str = ""
    description: str = ""
    position: int = 0
    priority: str = "normal"
    due_date: str = ""
    tags: str = ""
    assignee: str = ""
    email_uid: str = ""
    todo_id: int | None = None
    created_at: str = ""

    def save(self) -> int:
        data = {
            "column_id": self.column_id,
            "title": self.title,
            "description": self.description,
            "position": self.position,
            "priority": self.priority,
            "due_date": self.due_date,
            "tags": self.tags,
            "assignee": self.assignee,
            "email_uid": self.email_uid,
            "todo_id": self.todo_id,
        }
        if self.id == 0:
            self.id = db.insert("project_cards", data)
        else:
            db.update("project_cards", data, "id = ?", (self.id,))
        return self.id

    def delete(self) -> None:
        if self.id:
            db.delete("project_cards", "id = ?", (self.id,))
            self.id = 0

    def move_to_column(self, column_id: int) -> None:
        old_column_id = self.column_id
        self.column_id = column_id
        row = db.fetchone(
            "SELECT MAX(position) as max_pos FROM project_cards WHERE column_id = ?",
            (column_id,),
        )
        self.position = (
            (row["max_pos"] or 0) + 1 if row and row["max_pos"] is not None else 0
        )
        db.execute(
            "UPDATE project_cards SET position = position - 1 WHERE column_id = ? AND position > ?",
            (old_column_id, self.position),
        )
        db.update(
            "project_cards",
            {"column_id": self.column_id, "position": self.position},
            "id = ?",
            (self.id,),
        )

    def set_position(self, position: int) -> None:
        col = ProjectColumn.get_by_id(self.column_id)
        if col is None:
            return
        col.move_card(self.id, position)

    @classmethod
    def get_by_id(cls, card_id: int) -> ProjectCard | None:
        row = db.fetchone("SELECT * FROM project_cards WHERE id = ?", (card_id,))
        if row is None:
            return None
        return cls._from_row(row)

    @classmethod
    def get_all(cls) -> list[ProjectCard]:
        rows = db.fetchall("SELECT * FROM project_cards ORDER BY column_id, position")
        return [cls._from_row(r) for r in rows]

    @classmethod
    def _from_row(cls, row: dict) -> ProjectCard:
        return cls(
            id=row["id"],
            column_id=row["column_id"],
            title=row["title"] or "",
            description=row["description"] or "",
            position=row["position"] or 0,
            priority=row["priority"] or "normal",
            due_date=row["due_date"] or "",
            tags=row["tags"] or "",
            assignee=row["assignee"] or "",
            email_uid=row["email_uid"] or "",
            todo_id=row["todo_id"],
            created_at=row["created_at"] or "",
        )
