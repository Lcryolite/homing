from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from openemail.storage.database import db


class RuleType(Enum):
    KEYWORD = "keyword"
    REGEX = "regex"
    BLACKLIST_SENDER = "blacklist_sender"
    BLACKLIST_DOMAIN = "blacklist_domain"


class MatchField(Enum):
    SUBJECT = "subject"
    SENDER = "sender"
    BODY = "body"
    ALL = "all"


class FilterAction(Enum):
    MOVE = "move"
    TAG = "tag"
    MARK_READ = "mark_read"
    DELETE = "delete"
    SPAM = "spam"


@dataclass
class FilterRule:
    id: int = 0
    name: str = ""
    rule_type: str = "keyword"
    pattern: str = ""
    is_enabled: bool = True
    priority: int = 0
    action: str = "move_spam"
    match_field: str = "all"
    action_target: str = ""
    hit_count: int = 0

    def save(self) -> int:
        data = {
            "name": self.name,
            "rule_type": self.rule_type,
            "pattern": self.pattern,
            "is_enabled": int(self.is_enabled),
            "priority": self.priority,
            "action": self.action,
            "match_field": self.match_field,
            "action_target": self.action_target,
            "hit_count": self.hit_count,
        }
        if self.id == 0:
            self.id = db.insert("filter_rules", data)
        else:
            db.update("filter_rules", data, "id = ?", (self.id,))
        return self.id

    def delete(self) -> None:
        if self.id:
            db.delete("filter_rules", "id = ?", (self.id,))
            self.id = 0

    def increment_hit(self) -> None:
        self.hit_count += 1
        db.update("filter_rules", {"hit_count": self.hit_count}, "id = ?", (self.id,))

    @classmethod
    def get_by_id(cls, rule_id: int) -> FilterRule | None:
        row = db.fetchone("SELECT * FROM filter_rules WHERE id = ?", (rule_id,))
        if row is None:
            return None
        return cls._from_row(row)

    @classmethod
    def get_all_enabled(cls) -> list[FilterRule]:
        rows = db.fetchall(
            "SELECT * FROM filter_rules WHERE is_enabled = 1 ORDER BY priority"
        )
        return [cls._from_row(r) for r in rows]

    @classmethod
    def get_all(cls) -> list[FilterRule]:
        rows = db.fetchall("SELECT * FROM filter_rules ORDER BY priority")
        return [cls._from_row(r) for r in rows]

    @classmethod
    def _from_row(cls, row: dict) -> FilterRule:
        return cls(
            id=row["id"],
            name=row["name"],
            rule_type=row["rule_type"],
            pattern=row["pattern"] or "",
            is_enabled=bool(row["is_enabled"]),
            priority=row["priority"] or 0,
            action=row["action"] or "move_spam",
            match_field=row["match_field"] or "all",
            action_target=row["action_target"] or "",
            hit_count=row["hit_count"] or 0,
        )
