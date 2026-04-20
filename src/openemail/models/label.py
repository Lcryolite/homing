from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import List, Optional, Dict, Any, Set
import sqlite3

from openemail.storage.database import db

logger = logging.getLogger(__name__)


class LabelType(Enum):
    """标签类型"""

    USER = "user"  # 用户创建的标签
    SYSTEM = "system"  # 系统标签（如重要、星标等）
    SMART = "smart"  # 智能标签（基于规则）
    CATEGORY = "category"  # 分类标签（如社交、促销等）


class LabelVisibility(Enum):
    """标签可见性"""

    VISIBLE = "visible"  # 始终显示
    HIDDEN = "hidden"  # 仅在过滤器中显示
    ARCHIVE = "archive"  # 归档标签，不显示在侧边栏


@dataclass
class Label:
    """邮件标签"""

    id: int = 0
    name: str = ""
    display_name: Optional[str] = None
    color: str = "#89b4fa"  # 默认蓝色
    type: str = LabelType.USER.value
    visibility: str = LabelVisibility.VISIBLE.value
    parent_id: Optional[int] = None  # 父标签ID，用于嵌套
    account_id: Optional[int] = None  # 账户特定标签，None表示全局标签
    description: str = ""
    email_count: int = 0  # 缓存邮件数量
    unread_count: int = 0  # 缓存未读邮件数量
    is_synced: bool = True  # 是否与服务器同步
    sync_state: str = "synced"  # 同步状态：synced, pending, error
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    def __post_init__(self):
        if self.display_name is None:
            self.display_name = self.name
        if self.created_at is None:
            self.created_at = datetime.now()
        if self.updated_at is None:
            self.updated_at = datetime.now()

    def save(self) -> int:
        """保存标签"""
        data = {
            "name": self.name,
            "display_name": self.display_name,
            "color": self.color,
            "type": self.type,
            "visibility": self.visibility,
            "parent_id": self.parent_id,
            "account_id": self.account_id,
            "description": self.description,
            "email_count": self.email_count,
            "unread_count": self.unread_count,
            "is_synced": int(self.is_synced),
            "sync_state": self.sync_state,
            "created_at": self.created_at.isoformat(),
            "updated_at": datetime.now().isoformat(),
        }

        if self.id == 0:
            self.id = db.insert("labels", data)
        else:
            db.update("labels", data, "id = ?", (self.id,))
            self.updated_at = datetime.now()

        return self.id

    def delete(self) -> bool:
        """删除标签（及其与邮件的关联）"""
        if not self.id:
            return False

        try:
            # 删除标签与邮件的关联
            db.delete("email_labels", "label_id = ?", (self.id,))

            # 删除标签本身
            db.delete("labels", "id = ?", (self.id,))

            # 更新子标签的parent_id
            db.update("labels", {"parent_id": None}, "parent_id = ?", (self.id,))

            self.id = 0
            return True
        except sqlite3.Error:
            return False

    def update_counts(self) -> None:
        """更新邮件计数"""
        try:
            # 计算邮件总数
            count_sql = """
                SELECT 
                    COUNT(*) as total,
                    SUM(CASE WHEN emails.is_read = 0 THEN 1 ELSE 0 END) as unread
                FROM emails
                JOIN email_labels ON emails.id = email_labels.email_id
                WHERE email_labels.label_id = ?
            """
            result = db.fetchone(count_sql, (self.id,))

            if result:
                self.email_count = result["total"] or 0
                self.unread_count = result["unread"] or 0

                db.update(
                    "labels",
                    {
                        "email_count": self.email_count,
                        "unread_count": self.unread_count,
                        "updated_at": datetime.now().isoformat(),
                    },
                    "id = ?",
                    (self.id,),
                )
        except Exception:
            pass

    def add_to_email(self, email_id: int) -> bool:
        """将标签添加到邮件"""
        try:
            # 检查是否已存在
            existing = db.fetchone(
                "SELECT 1 FROM email_labels WHERE email_id = ? AND label_id = ?",
                (email_id, self.id),
            )

            if existing:
                return True  # 已存在

            # 创建关联
            db.insert(
                "email_labels",
                {
                    "email_id": email_id,
                    "label_id": self.id,
                    "created_at": datetime.now().isoformat(),
                },
            )

            # 更新计数
            self.email_count += 1
            # 检查邮件是否未读
            email = db.fetchone("SELECT is_read FROM emails WHERE id = ?", (email_id,))
            if email and email.get("is_read") == 0:
                self.unread_count += 1

            db.update(
                "labels",
                {
                    "email_count": self.email_count,
                    "unread_count": self.unread_count,
                    "updated_at": datetime.now().isoformat(),
                },
                "id = ?",
                (self.id,),
            )

            return True
        except sqlite3.Error as e:
            logger.error("添加标签到邮件失败: %s", e)
            return False

    def remove_from_email(self, email_id: int) -> bool:
        """从邮件移除标签"""
        try:
            # 删除关联
            db.delete(
                "email_labels", "email_id = ? AND label_id = ?", (email_id, self.id)
            )

            # 更新计数
            if self.email_count > 0:
                self.email_count -= 1

            # 检查邮件是否未读
            email = db.fetchone("SELECT is_read FROM emails WHERE id = ?", (email_id,))
            if email and email.get("is_read") == 0 and self.unread_count > 0:
                self.unread_count -= 1

            db.update(
                "labels",
                {
                    "email_count": self.email_count,
                    "unread_count": self.unread_count,
                    "updated_at": datetime.now().isoformat(),
                },
                "id = ?",
                (self.id,),
            )

            return True
        except sqlite3.Error:
            return False

    def merge_with(self, other_label_id: int) -> bool:
        """合并标签（将当前标签的所有邮件移到另一个标签）"""
        try:
            # 将当前标签的邮件关联转移到另一个标签
            update_sql = """
                INSERT OR IGNORE INTO email_labels (email_id, label_id, created_at)
                SELECT email_id, ?, created_at 
                FROM email_labels 
                WHERE label_id = ?
                ON CONFLICT(email_id, label_id) DO NOTHING
            """
            db.execute(update_sql, (other_label_id, self.id))

            # 删除旧的关联
            db.delete("email_labels", "label_id = ?", (self.id,))

            # 删除当前标签
            self.delete()

            # 更新目标标签的计数
            other_label = Label.get_by_id(other_label_id)
            if other_label:
                other_label.update_counts()

            return True
        except sqlite3.Error:
            return False

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "id": self.id,
            "name": self.name,
            "display_name": self.display_name,
            "color": self.color,
            "type": self.type,
            "visibility": self.visibility,
            "parent_id": self.parent_id,
            "account_id": self.account_id,
            "description": self.description,
            "email_count": self.email_count,
            "unread_count": self.unread_count,
            "is_synced": self.is_synced,
            "sync_state": self.sync_state,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }

    @classmethod
    def get_by_id(cls, label_id: int) -> Optional[Label]:
        """根据ID获取标签"""
        row = db.fetchone("SELECT * FROM labels WHERE id = ?", (label_id,))
        if row is None:
            return None
        return cls._from_row(row)

    @classmethod
    def get_by_name(
        cls, name: str, account_id: Optional[int] = None
    ) -> Optional[Label]:
        """根据名称获取标签"""
        if account_id is None:
            sql = "SELECT * FROM labels WHERE name = ? AND account_id IS NULL"
            params = (name,)
        else:
            sql = "SELECT * FROM labels WHERE name = ? AND (account_id = ? OR account_id IS NULL)"
            params = (name, account_id)

        row = db.fetchone(sql, params)
        if row is None:
            return None
        return cls._from_row(row)

    @classmethod
    def get_all(
        cls, account_id: Optional[int] = None, include_hidden: bool = False
    ) -> List[Label]:
        """获取所有标签"""
        if account_id is None:
            sql = "SELECT * FROM labels WHERE 1=1"
            params = []
        else:
            sql = "SELECT * FROM labels WHERE account_id = ? OR account_id IS NULL"
            params = [account_id]

        if not include_hidden:
            sql += " AND visibility != 'hidden'"

        sql += " ORDER BY type, name"

        rows = db.fetchall(sql, params)
        return [cls._from_row(r) for r in rows]

    @classmethod
    def get_for_email(cls, email_id: int) -> List[Label]:
        """获取邮件的所有标签"""
        sql = """
            SELECT l.* FROM labels l
            JOIN email_labels el ON l.id = el.label_id
            WHERE el.email_id = ?
            ORDER BY l.type, l.name
        """
        rows = db.fetchall(sql, (email_id,))
        return [cls._from_row(r) for r in rows]

    @classmethod
    def search(
        cls, query: str, account_id: Optional[int] = None, limit: int = 50
    ) -> List[Label]:
        """搜索标签"""
        if account_id is None:
            sql = """
                SELECT * FROM labels 
                WHERE (name LIKE ? OR display_name LIKE ? OR description LIKE ?)
                AND visibility != 'hidden'
                ORDER BY email_count DESC
                LIMIT ?
            """
            params = (f"%{query}%", f"%{query}%", f"%{query}%", limit)
        else:
            sql = """
                SELECT * FROM labels 
                WHERE (account_id = ? OR account_id IS NULL)
                AND (name LIKE ? OR display_name LIKE ? OR description LIKE ?)
                AND visibility != 'hidden'
                ORDER BY email_count DESC
                LIMIT ?
            """
            params = (account_id, f"%{query}%", f"%{query}%", f"%{query}%", limit)

        rows = db.fetchall(sql, params)
        return [cls._from_row(r) for r in rows]

    @classmethod
    def get_system_labels(cls, account_id: Optional[int] = None) -> List[Label]:
        """获取系统标签"""
        if account_id is None:
            sql = "SELECT * FROM labels WHERE type = 'system' ORDER BY name"
            params = []
        else:
            sql = """
                SELECT * FROM labels 
                WHERE type = 'system' AND (account_id = ? OR account_id IS NULL)
                ORDER BY name
            """
            params = [account_id]

        rows = db.fetchall(sql, params)
        return [cls._from_row(r) for r in rows]

    @classmethod
    def get_smart_labels(cls, account_id: Optional[int] = None) -> List[Label]:
        """获取智能标签"""
        if account_id is None:
            sql = "SELECT * FROM labels WHERE type = 'smart' ORDER BY name"
            params = []
        else:
            sql = """
                SELECT * FROM labels 
                WHERE type = 'smart' AND (account_id = ? OR account_id IS NULL)
                ORDER BY name
            """
            params = [account_id]

        rows = db.fetchall(sql, params)
        return [cls._from_row(r) for r in rows]

    @classmethod
    def get_child_labels(cls, parent_id: int) -> List[Label]:
        """获取子标签"""
        sql = "SELECT * FROM labels WHERE parent_id = ? ORDER BY name"
        rows = db.fetchall(sql, (parent_id,))
        return [cls._from_row(r) for r in rows]

    @classmethod
    def create_system_label(
        cls,
        name: str,
        display_name: str,
        color: str = "#89b4fa",
        account_id: Optional[int] = None,
    ) -> Label:
        """创建系统标签"""
        label = cls(
            name=name,
            display_name=display_name,
            color=color,
            type=LabelType.SYSTEM.value,
            visibility=LabelVisibility.VISIBLE.value,
            account_id=account_id,
        )
        label.save()
        return label

    @classmethod
    def create_smart_label(
        cls,
        name: str,
        display_name: str,
        rule: Dict[str, Any],
        color: str = "#cba6f7",
        account_id: Optional[int] = None,
    ) -> Label:
        """创建智能标签（基于规则）"""
        label = cls(
            name=name,
            display_name=display_name,
            color=color,
            type=LabelType.SMART.value,
            visibility=LabelVisibility.VISIBLE.value,
            account_id=account_id,
            description=json.dumps(rule, ensure_ascii=False),
        )
        label.save()
        return label

    @classmethod
    def _from_row(cls, row: Dict[str, Any]) -> Label:
        """从数据库行创建标签对象"""

        def parse_date(date_str):
            if date_str:
                try:
                    return datetime.fromisoformat(date_str)
                except (ValueError, TypeError):
                    return None
            return None

        # Helper function to mimic dict.get() behavior with sqlite3.Row
        def row_get(key, default=None):
            if key in row.keys():
                value = row[key]
                return default if value is None else value
            return default

        return cls(
            id=row["id"],
            name=row["name"],
            display_name=row_get("display_name") or row["name"],
            color=row_get("color", "#89b4fa"),
            type=row_get("type", "user"),
            visibility=row_get("visibility", "visible"),
            parent_id=row_get("parent_id"),
            account_id=row_get("account_id"),
            description=row_get("description", ""),
            email_count=row_get("email_count", 0) or 0,
            unread_count=row_get("unread_count", 0) or 0,
            is_synced=bool(row_get("is_synced", 1)),
            sync_state=row_get("sync_state", "synced"),
            created_at=parse_date(row_get("created_at")),
            updated_at=parse_date(row_get("updated_at")),
        )


@dataclass
class LabelEmailRel:
    """邮件标签关联关系"""

    email_id: int = 0
    label_id: int = 0
    created_at: Optional[datetime] = None

    @classmethod
    def create(cls, email_id: int, label_id: int) -> bool:
        """创建邮件标签关联"""
        try:
            db.execute(
                "INSERT OR IGNORE INTO email_labels (email_id, label_id) VALUES (?, ?)",
                (email_id, label_id),
            )
            return True
        except sqlite3.Error as e:
            logger.error("创建邮件标签关联失败: %s", e)
            return False

    @classmethod
    def delete_by_email_and_label(cls, email_id: int, label_id: int) -> bool:
        """删除邮件标签关联"""
        try:
            db.execute(
                "DELETE FROM email_labels WHERE email_id = ? AND label_id = ?",
                (email_id, label_id),
            )
            return True
        except sqlite3.Error as e:
            logger.error("删除邮件标签关联失败: %s", e)
            return False

    @classmethod
    def exists(cls, email_id: int, label_id: int) -> bool:
        """检查关联是否存在"""
        row = db.fetchone(
            "SELECT 1 FROM email_labels WHERE email_id = ? AND label_id = ?",
            (email_id, label_id),
        )
        return row is not None

    @classmethod
    def get_label_ids_for_email(cls, email_id: int) -> List[int]:
        """获取邮件的所有标签ID"""
        rows = db.fetchall(
            "SELECT label_id FROM email_labels WHERE email_id = ?", (email_id,)
        )
        return [row["label_id"] for row in rows]

    @classmethod
    def get_email_ids_for_label(cls, label_id: int) -> List[int]:
        """获取标签的所有邮件ID"""
        rows = db.fetchall(
            "SELECT email_id FROM email_labels WHERE label_id = ?", (label_id,)
        )
        return [row["email_id"] for row in rows]

    @classmethod
    def delete_by_email(cls, email_id: int) -> bool:
        """删除邮件的所有标签"""
        try:
            db.execute("DELETE FROM email_labels WHERE email_id = ?", (email_id,))
            return True
        except sqlite3.Error as e:
            logger.error("删除邮件标签失败: %s", e)
            return False

    @classmethod
    def delete_by_label(cls, label_id: int) -> bool:
        """删除标签的所有邮件关联"""
        try:
            db.execute("DELETE FROM email_labels WHERE label_id = ?", (label_id,))
            return True
        except sqlite3.Error as e:
            logger.error("删除标签邮件关联失败: %s", e)
            return False


def ensure_label_tables():
    """确保标签相关表存在"""
    # 创建标签表
    db.execute("""
        CREATE TABLE IF NOT EXISTS labels (
            id            INTEGER PRIMARY KEY,
            name          TEXT NOT NULL,
            display_name  TEXT,
            color         TEXT DEFAULT '#89b4fa',
            type          TEXT DEFAULT 'user',
            visibility    TEXT DEFAULT 'visible',
            parent_id     INTEGER REFERENCES labels(id) ON DELETE SET NULL,
            account_id    INTEGER REFERENCES accounts(id) ON DELETE CASCADE,
            description   TEXT DEFAULT '',
            email_count   INTEGER DEFAULT 0,
            unread_count  INTEGER DEFAULT 0,
            is_synced     INTEGER DEFAULT 1,
            sync_state    TEXT DEFAULT 'synced',
            created_at    TEXT DEFAULT CURRENT_TIMESTAMP,
            updated_at    TEXT DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(name, account_id)
        )
    """)

    # 创建邮件标签关联表
    db.execute("""
        CREATE TABLE IF NOT EXISTS email_labels (
            email_id    INTEGER REFERENCES emails(id) ON DELETE CASCADE,
            label_id    INTEGER REFERENCES labels(id) ON DELETE CASCADE,
            created_at  TEXT DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (email_id, label_id)
        )
    """)

    # 创建索引
    db.execute("CREATE INDEX IF NOT EXISTS idx_labels_name ON labels(name)")
    db.execute("CREATE INDEX IF NOT EXISTS idx_labels_account ON labels(account_id)")
    db.execute("CREATE INDEX IF NOT EXISTS idx_labels_type ON labels(type)")
    db.execute("CREATE INDEX IF NOT EXISTS idx_labels_parent ON labels(parent_id)")
    db.execute(
        "CREATE INDEX IF NOT EXISTS idx_email_labels_email ON email_labels(email_id)"
    )
    db.execute(
        "CREATE INDEX IF NOT EXISTS idx_email_labels_label ON email_labels(label_id)"
    )

    # 创建默认系统标签
    default_system_labels = [
        ("important", "重要", "#f38ba8"),
        ("starred", "星标", "#f9e2af"),
        ("unread", "未读", "#89b4fa"),
        ("sent", "已发送", "#94e2d5"),
        ("drafts", "草稿", "#cba6f7"),
        ("spam", "垃圾邮件", "#f2cdcd"),
        ("trash", "已删除", "#9399b2"),
    ]

    for name, display, color in default_system_labels:
        # 检查是否已存在
        existing = db.fetchone(
            "SELECT 1 FROM labels WHERE name = ? AND type = 'system'", (name,)
        )
        if not existing:
            db.insert(
                "labels",
                {
                    "name": name,
                    "display_name": display,
                    "color": color,
                    "type": LabelType.SYSTEM.value,
                    "visibility": LabelVisibility.VISIBLE.value,
                },
            )

    logger.info("标签系统表初始化完成")


# 自动初始化
ensure_label_tables()
