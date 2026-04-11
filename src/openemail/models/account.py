from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any

from openemail.storage.database import db
from openemail.utils.crypto import decrypt_password, encrypt_password


PROVIDER_PRESETS: dict[str, dict[str, Any]] = {
    "qq": {
        "name": "QQ邮箱",
        "protocol": "imap",
        "imap_host": "imap.qq.com",
        "imap_port": 993,
        "smtp_host": "smtp.qq.com",
        "smtp_port": 465,
        "ssl_mode": "ssl",
        "auth_type": "app_password",
    },
    "gmail": {
        "name": "Gmail",
        "protocol": "imap",
        "imap_host": "imap.gmail.com",
        "imap_port": 993,
        "smtp_host": "smtp.gmail.com",
        "smtp_port": 465,
        "ssl_mode": "ssl",
        "auth_type": "oauth2",
        "oauth_provider": "google",
    },
    "outlook": {
        "name": "Outlook",
        "protocol": "imap",
        "imap_host": "outlook.office365.com",
        "imap_port": 993,
        "smtp_host": "smtp.office365.com",
        "smtp_port": 587,
        "ssl_mode": "starttls",
        "auth_type": "oauth2",
        "oauth_provider": "microsoft",
    },
    "yahoo": {
        "name": "Yahoo",
        "protocol": "imap",
        "imap_host": "imap.mail.yahoo.com",
        "imap_port": 993,
        "smtp_host": "smtp.mail.yahoo.com",
        "smtp_port": 465,
        "ssl_mode": "ssl",
        "auth_type": "app_password",
    },
    "163": {
        "name": "163邮箱",
        "protocol": "imap",
        "imap_host": "imap.163.com",
        "imap_port": 993,
        "smtp_host": "smtp.163.com",
        "smtp_port": 465,
        "ssl_mode": "ssl",
        "auth_type": "app_password",
    },
    "126": {
        "name": "126邮箱",
        "protocol": "imap",
        "imap_host": "imap.126.com",
        "imap_port": 993,
        "smtp_host": "smtp.126.com",
        "smtp_port": 465,
        "ssl_mode": "ssl",
        "auth_type": "app_password",
    },
}


@dataclass
class Account:
    id: int = 0
    name: str = ""
    email: str = ""
    protocol: str = "imap"
    imap_host: str = ""
    imap_port: int = 993
    pop3_host: str = ""
    pop3_port: int = 995
    smtp_host: str = ""
    smtp_port: int = 465
    ssl_mode: str = "ssl"
    auth_type: str = "password"
    oauth_provider: str = ""
    _password: str = field(default="", repr=False)
    _oauth_token: str = field(default="", repr=False)
    _oauth_refresh: str = field(default="", repr=False)
    is_active: bool = True
    last_sync_at: str = ""

    @property
    def password(self) -> str:
        if self._password.startswith("gAAAA"):
            try:
                return decrypt_password(self._password)
            except Exception:
                return self._password
        return self._password

    @password.setter
    def password(self, value: str) -> None:
        self._password = encrypt_password(value) if value else ""

    @property
    def oauth_token(self) -> str:
        if self._oauth_token and self._oauth_token.startswith("gAAAA"):
            try:
                return decrypt_password(self._oauth_token)
            except Exception:
                return self._oauth_token
        return self._oauth_token

    @oauth_token.setter
    def oauth_token(self, value: str) -> None:
        self._oauth_token = encrypt_password(value) if value else ""

    @property
    def oauth_refresh(self) -> str:
        if self._oauth_refresh and self._oauth_refresh.startswith("gAAAA"):
            try:
                return decrypt_password(self._oauth_refresh)
            except Exception:
                return self._oauth_refresh
        return self._oauth_refresh

    @oauth_refresh.setter
    def oauth_refresh(self, value: str) -> None:
        self._oauth_refresh = encrypt_password(value) if value else ""

    def save(self) -> int:
        data = {
            "name": self.name,
            "email": self.email,
            "protocol": self.protocol,
            "imap_host": self.imap_host,
            "imap_port": self.imap_port,
            "pop3_host": self.pop3_host,
            "pop3_port": self.pop3_port,
            "smtp_host": self.smtp_host,
            "smtp_port": self.smtp_port,
            "ssl_mode": self.ssl_mode,
            "auth_type": self.auth_type,
            "oauth_provider": self.oauth_provider,
            "is_active": int(self.is_active),
            "last_sync_at": self.last_sync_at,
            "password_enc": self._password,
            "oauth_token_enc": self._oauth_token,
            "oauth_refresh_enc": self._oauth_refresh,
        }
        if self.id == 0:
            self.id = db.insert("accounts", data)
        else:
            db.update("accounts", data, "id = ?", (self.id,))
        return self.id

    def delete(self) -> None:
        if self.id:
            db.delete("accounts", "id = ?", (self.id,))
            self.id = 0

    @classmethod
    def get_by_id(cls, account_id: int) -> Account | None:
        row = db.fetchone("SELECT * FROM accounts WHERE id = ?", (account_id,))
        if row is None:
            return None
        return cls._from_row(row)

    @classmethod
    def get_by_email(cls, email: str) -> Account | None:
        row = db.fetchone("SELECT * FROM accounts WHERE email = ?", (email,))
        if row is None:
            return None
        return cls._from_row(row)

    @classmethod
    def get_all_active(cls) -> list[Account]:
        rows = db.fetchall("SELECT * FROM accounts WHERE is_active = 1 ORDER BY id")
        return [cls._from_row(r) for r in rows]

    @classmethod
    def get_all(cls) -> list[Account]:
        rows = db.fetchall("SELECT * FROM accounts ORDER BY id")
        return [cls._from_row(r) for r in rows]

    @classmethod
    def _from_row(cls, row: dict) -> Account:
        return cls(
            id=row["id"],
            name=row["name"],
            email=row["email"],
            protocol=row["protocol"],
            imap_host=row["imap_host"] or "",
            imap_port=row["imap_port"] or 993,
            pop3_host=row["pop3_host"] or "",
            pop3_port=row["pop3_port"] or 995,
            smtp_host=row["smtp_host"] or "",
            smtp_port=row["smtp_port"] or 465,
            ssl_mode=row["ssl_mode"] or "ssl",
            auth_type=row["auth_type"] or "password",
            oauth_provider=row["oauth_provider"] or "",
            _password=row["password_enc"] if "password_enc" in row.keys() else "",
            _oauth_token=row["oauth_token_enc"]
            if "oauth_token_enc" in row.keys()
            else "",
            _oauth_refresh=row["oauth_refresh_enc"]
            if "oauth_refresh_enc" in row.keys()
            else "",
            is_active=bool(row["is_active"]),
            last_sync_at=row["last_sync_at"] or "",
        )

    @classmethod
    def create_from_preset(
        cls, provider: str, email: str, name: str = "", password: str = ""
    ) -> Account:
        preset = PROVIDER_PRESETS.get(provider, {})
        account = cls(
            name=name or preset.get("name", email),
            email=email,
            protocol=preset.get("protocol", "imap"),
            imap_host=preset.get("imap_host", ""),
            imap_port=preset.get("imap_port", 993),
            smtp_host=preset.get("smtp_host", ""),
            smtp_port=preset.get("smtp_port", 465),
            ssl_mode=preset.get("ssl_mode", "ssl"),
            auth_type=preset.get("auth_type", "password"),
            oauth_provider=preset.get("oauth_provider", ""),
        )
        if password:
            account.password = password
        return account
