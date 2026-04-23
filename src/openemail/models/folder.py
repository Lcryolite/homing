from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Optional

from openemail.storage.database import db

logger = logging.getLogger(__name__)

SYSTEM_FOLDERS: list[str] = [
    "INBOX",
    "Sent",
    "Drafts",
    "Spam",
    "Trash",
]

RFC6154_SPECIAL_USE_MAP: dict[str, str] = {
    "\\Inbox": "inbox",
    "\\Sent": "sent",
    "\\Drafts": "drafts",
    "\\Spam": "spam",
    "\\Junk": "spam",
    "\\Trash": "trash",
    "\\Archive": "archive",
    "\\Flagged": "flagged",
    "\\Important": "important",
}

FALLBACK_NAME_MAP: dict[str, str] = {
    "inbox": "inbox",
    "sent": "sent",
    "sent items": "sent",
    "sent mail": "sent",
    "drafts": "drafts",
    "draft": "drafts",
    "spam": "spam",
    "junk": "spam",
    "junk email": "spam",
    "trash": "trash",
    "deleted items": "trash",
    "deleted messages": "trash",
    "archive": "archive",
    "archived": "archive",
    "flagged": "flagged",
    "starred": "flagged",
    "important": "important",
}


@dataclass
class Folder:
    id: int = 0
    account_id: int = 0
    name: str = ""
    path: str = ""
    unread_count: int = 0
    is_system: bool = False
    special_use: str = ""
    uid_validity: str = ""
    last_uid: str = ""
    is_deleted: bool = False

    def save(self) -> int:
        data = {
            "account_id": self.account_id,
            "name": self.name,
            "path": self.path,
            "unread_count": self.unread_count,
            "is_system": int(self.is_system),
            "special_use": self.special_use,
            "uid_validity": self.uid_validity,
            "last_uid": self.last_uid,
            "is_deleted": int(self.is_deleted),
        }
        if self.id == 0:
            self.id = db.insert("folders", data)
        else:
            db.update("folders", data, "id = ?", (self.id,))
        return self.id

    def delete(self) -> None:
        if self.id:
            # Soft delete: mark folder and its emails as deleted
            db.update("folders", {"is_deleted": 1}, "id = ?", (self.id,))
            db.update("emails", {"is_deleted": 1}, "folder_id = ?", (self.id,))
            self.is_deleted = True

    def hard_delete(self) -> None:
        """Permanently remove folder and all associated emails from DB."""
        if self.id:
            db.delete("emails", "folder_id = ?", (self.id,))
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
        row = db.fetchone("SELECT * FROM folders WHERE id = ? AND is_deleted = 0", (folder_id,))
        if row is None:
            return None
        return cls._from_row(row)

    @classmethod
    def get_by_name(cls, account_id: int, name: str) -> Folder | None:
        row = db.fetchone(
            "SELECT * FROM folders WHERE account_id = ? AND name = ? AND is_deleted = 0",
            (account_id, name),
        )
        if row is None:
            return None
        return cls._from_row(row)

    @classmethod
    def get_by_special_use(cls, account_id: int, special_use: str) -> Folder | None:
        row = db.fetchone(
            "SELECT * FROM folders WHERE account_id = ? AND special_use = ? AND is_deleted = 0",
            (account_id, special_use),
        )
        if row is None:
            return None
        return cls._from_row(row)

    @classmethod
    def get_by_account(cls, account_id: int) -> list[Folder]:
        rows = db.fetchall(
            "SELECT * FROM folders WHERE account_id = ? AND is_deleted = 0 ORDER BY name", (account_id,)
        )
        return [cls._from_row(r) for r in rows]

    @classmethod
    def get_deleted(cls, account_id: int) -> list[Folder]:
        rows = db.fetchall(
            "SELECT * FROM folders WHERE account_id = ? AND is_deleted = 1 ORDER BY name", (account_id,)
        )
        return [cls._from_row(r) for r in rows]

    @classmethod
    def restore_deleted(cls, account_id: int, name: str) -> Folder | None:
        row = db.fetchone(
            "SELECT * FROM folders WHERE account_id = ? AND name = ? AND is_deleted = 1",
            (account_id, name),
        )
        if row is None:
            return None
        folder = cls._from_row(row)
        folder.is_deleted = False
        folder.save()
        # Also restore emails in this folder
        db.update("emails", {"is_deleted": 0}, "folder_id = ?", (folder.id,))
        return folder

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
    def discover_system_folders(
        cls, account_id: int, remote_folders: list[dict[str, Any]]
    ) -> list[Folder]:
        """
        基于 RFC 6154 SPECIAL-USE 属性自动发现系统文件夹。

        优先使用服务器返回的 SPECIAL-USE 属性，回退到名称匹配。

        Args:
            account_id: 账户ID
            remote_folders: IMAP LIST 返回的文件夹列表，
                每项包含 name, path, 可选 flags/attributes

        Returns:
            发现的系统文件夹列表
        """
        discovered: list[Folder] = []
        used_special_uses: set[str] = set()

        for rf in remote_folders:
            name = rf.get("name", "")
            path = rf.get("path", name)
            flags = rf.get("flags", rf.get("attributes", []))

            special_use = cls._resolve_special_use(name, flags)
            if not special_use:
                continue

            if special_use in used_special_uses:
                continue

            existing = cls.get_by_name(account_id, name)
            if existing:
                if not existing.special_use:
                    existing.special_use = special_use
                    existing.is_system = True
                    existing.save()
                discovered.append(existing)
            else:
                folder = cls(
                    account_id=account_id,
                    name=name,
                    path=path,
                    is_system=True,
                    special_use=special_use,
                )
                folder.save()
                discovered.append(folder)

            used_special_uses.add(special_use)

        return discovered

    @classmethod
    def reconcile_folders(
        cls, account_id: int, remote_folders: list[dict[str, Any]]
    ) -> list[Folder]:
        """Reconcile local folder list with server folder list.

        Handles:
        - New folders → create
        - Renamed folders → update path (match by special_use or fuzzy)
        - Deleted folders → soft-delete (mark is_deleted=1)
        - Re-appeared folders → restore from soft-delete
        - Existing unchanged → keep

        Returns the full list of current active folders after reconciliation.
        """
        remote_by_name: dict[str, dict[str, Any]] = {}
        for rf in remote_folders:
            name = rf.get("name", "")
            remote_by_name[name] = rf

        remote_names = set(remote_by_name.keys())
        local_folders = cls.get_by_account(account_id)
        local_by_name = {f.name: f for f in local_folders}
        local_names = set(local_by_name.keys())

        # Include soft-deleted folders for potential restoration
        deleted_folders = cls.get_deleted(account_id)
        deleted_by_name = {f.name: f for f in deleted_folders}

        # 1. Deleted folders: in local but not remote → soft-delete
        removed = local_names - remote_names
        for name in removed:
            folder = local_by_name[name]
            logger.info(
                "Folder '%s' no longer on server, soft-deleting local (id=%d)", name, folder.id
            )
            folder.delete()

        # 2. New folders: in remote but not local → create (or restore if previously deleted)
        added = remote_names - local_names
        result: list[Folder] = []
        for name in added:
            rf = remote_by_name[name]
            flags = rf.get("flags", [])
            special_use = cls._resolve_special_use(name, flags) or ""

            # Check if this folder was previously soft-deleted → restore it
            if name in deleted_by_name:
                restored = cls.restore_deleted(account_id, name)
                if restored:
                    # Update path/special_use if changed while deleted
                    remote_path = rf.get("path", name)
                    if remote_path and restored.path != remote_path:
                        restored.path = remote_path
                    if special_use and not restored.special_use:
                        restored.special_use = special_use
                        restored.is_system = True
                    if restored.path != rf.get("path", name) or (special_use and not restored.special_use):
                        restored.save()
                    result.append(restored)
                    continue

            folder = cls(
                account_id=account_id,
                name=name,
                path=rf.get("path", name),
                is_system=bool(special_use),
                special_use=special_use,
            )
            folder.save()
            result.append(folder)

        # 3. Existing folders: update path if changed, re-resolve special_use
        unchanged = remote_names & local_names
        for name in unchanged:
            folder = local_by_name[name]
            rf = remote_by_name[name]
            flags = rf.get("flags", [])
            new_special_use = cls._resolve_special_use(name, flags) or ""
            remote_path = rf.get("path", name)

            changed = False
            if remote_path and folder.path != remote_path:
                folder.path = remote_path
                changed = True
            if new_special_use and not folder.special_use:
                folder.special_use = new_special_use
                folder.is_system = True
                changed = True
            if changed:
                folder.save()
            result.append(folder)

        # 4. Also run discover_system_folders for dedup marking
        cls.discover_system_folders(account_id, remote_folders)

        return result

    @classmethod
    def get_by_path(cls, account_id: int, path: str) -> Folder | None:
        row = db.fetchone(
            "SELECT * FROM folders WHERE account_id = ? AND path = ? AND is_deleted = 0",
            (account_id, path),
        )
        if row is None:
            return None
        return cls._from_row(row)

    @classmethod
    def _resolve_special_use(cls, name: str, flags: list[Any]) -> Optional[str]:
        """
        解析文件夹的 SPECIAL-USE 属性。

        优先从 flags 中提取 RFC 6154 属性，回退到名称匹配。

        Args:
            name: 文件夹名称
            flags: IMAP LIST 返回的 flags/attributes

        Returns:
            special_use 标识（如 'inbox', 'sent', 'drafts' 等），或 None
        """
        for flag in flags:
            flag_str = str(flag)
            if flag_str in RFC6154_SPECIAL_USE_MAP:
                return RFC6154_SPECIAL_USE_MAP[flag_str]

        name_lower = name.lower().strip()
        if name_lower in FALLBACK_NAME_MAP:
            return FALLBACK_NAME_MAP[name_lower]

        return None

    @classmethod
    def _from_row(cls, row: dict) -> Folder:
        return cls(
            id=row["id"],
            account_id=row["account_id"],
            name=row["name"],
            path=row["path"] or "",
            unread_count=row["unread_count"] or 0,
            is_system=bool(row["is_system"]),
            special_use=row["special_use"] if "special_use" in row.keys() else "",
            uid_validity=row["uid_validity"] if "uid_validity" in row.keys() else "",
            last_uid=row["last_uid"] if "last_uid" in row.keys() else "",
            is_deleted=bool(row.get("is_deleted", 0)),
        )
