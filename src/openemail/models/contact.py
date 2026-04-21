from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, List, Dict, Any

from openemail.storage.database import db

logger = logging.getLogger(__name__)


@dataclass
class Contact:
    """联系人数据模型"""

    id: int = 0
    account_id: Optional[int] = None
    name: str = ""
    email: str = ""
    phone: str = ""
    mobile: str = ""
    company: str = ""
    job_title: str = ""
    address: str = ""
    notes: str = ""
    avatar_path: str = ""
    is_favorite: bool = False
    frequency: int = 0  # 联系频率
    last_contacted: Optional[str] = None
    created_at: str = ""
    updated_at: str = ""
    tags: List[str] = field(default_factory=list)

    @property
    def display_name(self) -> str:
        """显示名称"""
        return self.name if self.name else self.email.split("@")[0]

    @property
    def initials(self) -> str:
        """获取姓名首字母"""
        if not self.name:
            if self.email:
                return self.email[0].upper()
            return "?"

        # 获取中文字符的首字
        if any("\u4e00" <= c <= "\u9fff" for c in self.name):
            return self.name[0]

        # 英文名字：获取首字母
        parts = self.name.split()
        if len(parts) >= 2:
            return (parts[0][0] + parts[-1][0]).upper()
        elif len(parts) == 1:
            return parts[0][0].upper()

        return "?"

    def save(self) -> int:
        """保存联系人"""
        data = {
            "account_id": self.account_id,
            "name": self.name,
            "email": self.email,
            "phone": self.phone,
            "mobile": self.mobile,
            "company": self.company,
            "job_title": self.job_title,
            "address": self.address,
            "notes": self.notes,
            "avatar_path": self.avatar_path,
            "is_favorite": 1 if self.is_favorite else 0,
            "frequency": self.frequency,
            "last_contacted": self.last_contacted,
            "updated_at": datetime.now().isoformat(),
        }

        if self.id:
            # 更新现有联系人
            db.update("contacts", data, "id = ?", (self.id,))
            return self.id
        else:
            # 创建新联系人
            data["created_at"] = datetime.now().isoformat()
            self.id = db.insert("contacts", data)

            # 保存标签关联
            self._save_tags()

            return self.id

    def delete(self) -> bool:
        """删除联系人"""
        if self.id:
            # 删除标签关联
            db.delete("contact_tags", "contact_id = ?", (self.id,))

            # 删除联系人
            db.delete("contacts", "id = ?", (self.id,))
            return True
        return False

    def increment_frequency(self) -> None:
        """增加联系频率"""
        self.frequency += 1
        self.last_contacted = datetime.now().isoformat()
        self.save()

    def _save_tags(self) -> None:
        """保存标签关联"""
        if not self.id:
            return

        # 清除旧标签
        db.delete("contact_tags", "contact_id = ?", (self.id,))

        # 保存新标签
        for tag_name in self.tags:
            tag_id = ContactTag.get_or_create(tag_name)
            db.insert("contact_tags", {"contact_id": self.id, "tag_id": tag_id})

    def get_related_emails(self, limit: int = 20) -> List[Dict[str, Any]]:
        """获取相关邮件"""
        from openemail.models.email import Email

        emails = Email.get_by_sender(self.email, limit=limit)

        result = []
        for email in emails:
            result.append(
                {
                    "id": email.id,
                    "subject": email.subject,
                    "date": email.date,
                    "preview": email.preview_text[:100] if email.preview_text else "",
                    "is_read": email.is_read,
                    "has_attachment": email.has_attachment,
                }
            )

        return result

    @classmethod
    def from_row(cls, row: Dict[str, Any]) -> Contact:
        """从数据库行创建实例"""
        contact = cls()

        for key, value in row.items():
            if hasattr(contact, key):
                if key == "is_favorite":
                    setattr(contact, key, bool(value))
                else:
                    setattr(contact, key, value)

        # 加载标签
        contact.tags = ContactTag.get_by_contact(contact.id)

        return contact

    @classmethod
    def get_by_id(cls, contact_id: int) -> Optional[Contact]:
        """根据ID获取联系人"""
        row = db.fetchone("SELECT * FROM contacts WHERE id = ?", (contact_id,))
        if row:
            return cls.from_row(row)
        return None

    @classmethod
    def get_by_email(
        cls, email: str, account_id: Optional[int] = None
    ) -> Optional[Contact]:
        """根据邮箱获取联系人"""
        query = "SELECT * FROM contacts WHERE email = ?"
        params = [email]

        if account_id is not None:
            query += " AND (account_id = ? OR account_id IS NULL)"
            params.append(account_id)

        row = db.fetchone(query, params)
        if row:
            return cls.from_row(row)
        return None

    @classmethod
    def search(
        cls, query: str, account_id: Optional[int] = None, limit: int = 50
    ) -> List[Contact]:
        """搜索联系人"""
        where_clauses = []
        params = []

        # 构建搜索条件
        search_terms = query.split()
        for term in search_terms:
            where_clauses.append("(")
            where_clauses.append("name LIKE ?")
            where_clauses.append("OR email LIKE ?")
            where_clauses.append("OR company LIKE ?")
            where_clauses.append("OR phone LIKE ?")
            where_clauses.append("OR notes LIKE ?")
            where_clauses.append(")")

            like_term = f"%{term}%"
            params.extend([like_term] * 5)

        if where_clauses:
            where_clause = " AND ".join(
                [
                    "(" + " OR ".join(where_clauses[i : i + 6]) + ")"
                    for i in range(0, len(where_clauses), 6)
                ]
            )
        else:
            where_clause = "1=1"

        if account_id is not None:
            where_clause += " AND (account_id = ? OR account_id IS NULL)"
            params.append(account_id)

        sql = f"""
            SELECT * FROM contacts 
            WHERE {where_clause}
            ORDER BY is_favorite DESC, frequency DESC, name
            LIMIT ?
        """
        params.append(limit)

        rows = db.fetchall(sql, params)
        return [cls.from_row(row) for row in rows]

    @classmethod
    def get_all(
        cls, account_id: Optional[int] = None, favorites_only: bool = False
    ) -> List[Contact]:
        """获取所有联系人"""
        where_clauses = []
        params = []

        if account_id is not None:
            where_clauses.append("(account_id = ? OR account_id IS NULL)")
            params.append(account_id)

        if favorites_only:
            where_clauses.append("is_favorite = 1")

        where_clause = " AND ".join(where_clauses) if where_clauses else "1=1"

        sql = f"""
            SELECT * FROM contacts 
            WHERE {where_clause}
            ORDER BY is_favorite DESC, name
        """

        rows = db.fetchall(sql, params)
        return [cls.from_row(row) for row in rows]

    @classmethod
    def create_from_email(
        cls,
        email_address: str,
        name: Optional[str] = None,
        account_id: Optional[int] = None,
    ) -> Contact:
        """从邮件地址创建联系人"""
        contact = cls(
            account_id=account_id,
            email=email_address,
            name=name or email_address.split("@")[0],
        )
        contact.save()
        return contact

    @classmethod
    def import_from_vcard(
        cls, vcard_content: str, account_id: Optional[int] = None
    ) -> List[Contact]:
        """从VCard导入联系人"""
        try:
            import vobject
        except ImportError:
            logger.warning("VCard导入需要vobject库: pip install vobject")
            return []

        contacts = []
        for vcard in vobject.readComponents(vcard_content):
            contact = cls(account_id=account_id)

            if hasattr(vcard, "n"):
                contact.name = str(vcard.n.value)

            if hasattr(vcard, "fn"):
                contact.name = str(vcard.fn.value)

            if hasattr(vcard, "email"):
                contact.email = str(vcard.email.value)

            if hasattr(vcard, "tel"):
                for tel in vcard.tel_list:
                    if hasattr(tel, "type_param"):
                        if "cell" in str(tel.type_param):
                            contact.mobile = str(tel.value)
                        else:
                            contact.phone = str(tel.value)
                    else:
                        contact.phone = str(tel.value)

            if hasattr(vcard, "org"):
                contact.company = str(vcard.org.value)

            if hasattr(vcard, "title"):
                contact.job_title = str(vcard.title.value)

            if hasattr(vcard, "adr"):
                address_parts = vcard.adr.value
                contact.address = ", ".join(str(part) for part in address_parts if part)

            if hasattr(vcard, "note"):
                contact.notes = str(vcard.note.value)

            contact.save()
            contacts.append(contact)

        return contacts

    def export_to_vcard(self) -> str:
        """导出为VCard格式"""
        try:
            import vobject
        except ImportError:
            return ""

        vcard = vobject.vCard()
        vcard.add("fn").value = self.display_name
        vcard.add("n").value = vobject.vcard.Name(
            family=self.name or "", given=self.name or ""
        )

        if self.email:
            email = vcard.add("email")
            email.value = self.email
            email.type_param = "INTERNET"

        if self.phone:
            tel = vcard.add("tel")
            tel.value = self.phone
            tel.type_param = "WORK"

        if self.mobile:
            mobile = vcard.add("tel")
            mobile.value = self.mobile
            mobile.type_param = "CELL"

        if self.company:
            vcard.add("org").value = [self.company]

        if self.job_title:
            vcard.add("title").value = self.job_title

        if self.address:
            vcard.add("adr").value = vobject.vcard.Address(
                street=self.address, city="", region="", code="", country=""
            )

        if self.notes:
            vcard.add("note").value = self.notes

        return vcard.serialize()


class ContactTag:
    """联系人标签类"""

    @staticmethod
    def create(name: str, color: str = "#89b4fa") -> int:
        """创建标签"""
        return db.insert(
            "contact_tags_meta",
            {"name": name, "color": color, "created_at": datetime.now().isoformat()},
        )

    @staticmethod
    def get_or_create(name: str, color: str = "#89b4fa") -> int:
        """获取或创建标签"""
        row = db.fetchone("SELECT id FROM contact_tags_meta WHERE name = ?", (name,))
        if row:
            return row["id"]
        return ContactTag.create(name, color)

    @staticmethod
    def get_by_contact(contact_id: int) -> List[str]:
        """获取联系人的标签"""
        rows = db.fetchall(
            """
            SELECT tm.name FROM contact_tags_meta tm
            JOIN contact_tags ct ON tm.id = ct.tag_id
            WHERE ct.contact_id = ?
            ORDER BY tm.name
        """,
            (contact_id,),
        )

        return [row["name"] for row in rows]

    @staticmethod
    def get_all() -> List[Dict[str, Any]]:
        """获取所有标签"""
        rows = db.fetchall("SELECT * FROM contact_tags_meta ORDER BY name")
        return [dict(row) for row in rows]

    @staticmethod
    def delete(tag_id: int) -> bool:
        """删除标签"""
        # 删除关联
        db.delete("contact_tags", "tag_id = ?", (tag_id,))

        # 删除标签
        db.delete("contact_tags_meta", "id = ?", (tag_id,))
        return True


def ensure_contact_tables():
    """确保联系人相关表存在"""
    # 联系人标签元数据表
    db.execute("""
        CREATE TABLE IF NOT EXISTS contact_tags_meta (
            id          INTEGER PRIMARY KEY,
            name        TEXT NOT NULL UNIQUE,
            color       TEXT DEFAULT '#89b4fa',
            created_at  TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # 联系人标签关联表
    db.execute("""
        CREATE TABLE IF NOT EXISTS contact_tags (
            contact_id  INTEGER REFERENCES contacts(id) ON DELETE CASCADE,
            tag_id      INTEGER REFERENCES contact_tags_meta(id) ON DELETE CASCADE,
            PRIMARY KEY (contact_id, tag_id)
        )
    """)

    # 首先确保contacts表存在（由migrations.py创建）
    # 检查contacts表是否存在以及是否有is_favorite列
    try:
        # 尝试查询contacts表结构
        _check_result = db.fetchone("SELECT * FROM contacts LIMIT 0")
        # 如果表存在，继续创建索引
        db.execute("CREATE INDEX IF NOT EXISTS idx_contacts_email ON contacts(email)")
        db.execute(
            "CREATE INDEX IF NOT EXISTS idx_contacts_account ON contacts(account_id)"
        )
        # 只在is_favorite列存在时创建索引
        try:
            # 检查is_favorite列是否存在
            db.execute("SELECT is_favorite FROM contacts LIMIT 1")
            db.execute(
                "CREATE INDEX IF NOT EXISTS idx_contacts_favorite ON contacts(is_favorite)"
            )
        except Exception:
            # 列不存在，跳过这个索引
            pass
        db.execute("CREATE INDEX IF NOT EXISTS idx_contacts_name ON contacts(name)")
    except Exception:
        # contacts表可能还不存在，跳过索引创建
        # 表会在migrations.py中创建
        pass


# 第一次导入时创建表
ensure_contact_tables()
