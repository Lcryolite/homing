from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from typing import Any
from datetime import datetime, timedelta
from openemail.storage.database import db
from openemail.utils.crypto import decrypt_password, encrypt_password
from openemail.core.connection_status import (
    ConnectionStatus,
    AccountValidationResult,
    can_transition,
    should_sync,
    is_savable,
    get_status_display,
)
from openemail.core.oauth2_new import (
    OAuthManager,
)

logger = logging.getLogger(__name__)


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
        "auth_type": "app_password",  # 默认使用应用专用密码，更稳定
        "oauth_provider": "google",
        "folder_prefix": "[Gmail]/",
    },
    "gmail_oauth": {
        "name": "Gmail (OAuth2)",
        "protocol": "imap",
        "imap_host": "imap.gmail.com",
        "imap_port": 993,
        "smtp_host": "smtp.gmail.com",
        "smtp_port": 465,
        "ssl_mode": "ssl",
        "auth_type": "oauth2",
        "oauth_provider": "google",
        "folder_prefix": "[Gmail]/",
    },
    "outlook": {
        "name": "Outlook (IMAP)",
        "protocol": "imap",
        "imap_host": "outlook.office365.com",
        "imap_port": 993,
        "smtp_host": "smtp.office365.com",
        "smtp_port": 587,
        "ssl_mode": "starttls",
        "auth_type": "oauth2",
        "oauth_provider": "microsoft",
    },
    "outlook_activesync": {
        "name": "Outlook/Exchange ActiveSync",
        "protocol": "activesync",
        "eas_host": "outlook.office365.com",
        "eas_path": "/Microsoft-Server-ActiveSync",
        "auth_type": "basic",  # ActiveSync通常使用基本认证
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
    eas_host: str = ""  # ActiveSync主机
    eas_path: str = "/Microsoft-Server-ActiveSync"  # ActiveSync路径
    ssl_mode: str = "ssl"
    auth_type: str = "password"
    oauth_provider: str = ""
    connection_status: ConnectionStatus = ConnectionStatus.UNVERIFIED
    _password: str = field(default="", repr=False)
    _oauth_token: str = field(default="", repr=False)
    _oauth_refresh: str = field(default="", repr=False)
    _validation_result: str = field(default="", repr=False)  # JSON序列化的验证结果
    token_expires_at: str = ""
    last_error_code: str = ""
    last_error_at: str = ""
    sync_fail_count: int = 0
    last_verified_at: str = ""
    is_default: bool = False  # 是否为默认账号
    is_active: bool = True
    last_sync_at: str = ""
    metadata: str = ""  # JSON序列化的元数据，用于存储风险信息等

    @property
    def metadata_dict(self) -> dict:
        """获取反序列化的元数据"""
        if not self.metadata:
            return {}
        try:
            return json.loads(self.metadata)
        except Exception:
            return {}

    @metadata_dict.setter
    def metadata_dict(self, value: dict) -> None:
        """设置元数据"""
        self.metadata = json.dumps(value) if value else ""

    @property
    def password(self) -> str:
        if self._password and self._password.startswith("gAAAA"):
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

    @property
    def validation_result(self) -> AccountValidationResult | None:
        """获取反序列化的验证结果"""
        if not self._validation_result:
            return None
        try:
            data = json.loads(self._validation_result)
            return AccountValidationResult.from_dict(data)
        except Exception:
            return None

    @validation_result.setter
    def validation_result(self, value: AccountValidationResult | None) -> None:
        """设置验证结果"""
        if value is None:
            self._validation_result = ""
        else:
            self._validation_result = json.dumps(value.to_dict())

    @property
    def status_display(self) -> str:
        """获取状态显示文本"""
        return get_status_display(self.connection_status)

    @property
    def can_sync(self) -> bool:
        """检查是否可以同步"""
        return should_sync(self.connection_status)

    @property
    def can_save(self) -> bool:
        """检查是否可以保存"""
        return is_savable(self.connection_status, self.validation_result)

    def update_status(self, new_status: ConnectionStatus, force: bool = False) -> bool:
        """更新连接状态"""
        if not force and not can_transition(self.connection_status, new_status):
            return False
        self.connection_status = new_status

        # 记录状态变化时间
        if new_status == ConnectionStatus.VERIFIED:
            self.last_verified_at = datetime.now().isoformat()
        elif new_status in [
            ConnectionStatus.AUTH_FAILED,
            ConnectionStatus.NETWORK_FAILED,
        ]:
            self.last_error_at = datetime.now().isoformat()

        return True

    def record_validation_result(self, result: AccountValidationResult) -> None:
        """记录验证结果并更新状态（批次E升级）"""
        self.validation_result = result

        # 批次E：基于验证级别更新状态
        verification_level = (
            result.verification_level.lower()
            if hasattr(result, "verification_level")
            else "unknown"
        )

        if result.error_message:
            # 明确错误，使用批次E的错误分类
            if any(
                msg in result.error_message.lower()
                for msg in ["auth", "认证", "password", "密码", "invalid", "incorrect"]
            ):
                self.update_status(ConnectionStatus.AUTH_FAILED)
            elif any(
                msg in result.error_message.lower()
                for msg in ["network", "连接", "timeout", "time out", "dns"]
            ):
                self.update_status(ConnectionStatus.NETWORK_FAILED)
            else:
                self.update_status(ConnectionStatus.NETWORK_FAILED)
        elif verification_level == "full_protocol_verified" and result.fully_verified:
            # 完整协议验证通过
            self.update_status(ConnectionStatus.VERIFIED)
        elif verification_level == "auth_verified" and result.auth_verified:
            # 认证通过但未完全验证
            self.update_status(ConnectionStatus.VERIFIED)
        elif verification_level == "connection_verified":
            # 连接成功但认证失败或未认证
            self.update_status(ConnectionStatus.NETWORK_FAILED)
        elif verification_level == "endpoint_verified":
            # 仅端点可达
            self.update_status(ConnectionStatus.NETWORK_FAILED)
        elif verification_level == "precheck":
            # 预检查失败
            self.update_status(ConnectionStatus.NETWORK_FAILED)
        elif verification_level == "unsupported":
            # 协议不支持
            self.update_status(ConnectionStatus.DISABLED)
        elif result.inbound_success:
            # 旧逻辑兼容：收信验证通过
            self.update_status(ConnectionStatus.VERIFIED)
        else:
            # 验证失败，但不知道具体原因
            self.update_status(ConnectionStatus.AUTH_FAILED)

    def mark_for_sync(self) -> bool:
        """标记账号为同步就绪"""
        if self.connection_status != ConnectionStatus.VERIFIED:
            return False
        return self.update_status(ConnectionStatus.SYNC_READY)

    def should_sync(self) -> bool:
        """检查是否应该同步（迁移兼容性方法）"""
        return self.can_sync

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
            "eas_host": self.eas_host,
            "eas_path": self.eas_path,
            "ssl_mode": self.ssl_mode,
            "auth_type": self.auth_type,
            "oauth_provider": self.oauth_provider,
            "connection_status": self.connection_status.value,
            "token_expires_at": self.token_expires_at,
            "last_error_code": self.last_error_code,
            "last_error_at": self.last_error_at,
            "sync_fail_count": self.sync_fail_count,
            "last_verified_at": self.last_verified_at,
            "validation_result": self._validation_result,
            "is_default": int(self.is_default),
            "is_active": int(self.is_active),
            "last_sync_at": self.last_sync_at,
            "password_enc": self._password,
            "oauth_token_enc": self._oauth_token,
            "oauth_refresh_enc": self._oauth_refresh,
            "metadata": self.metadata,
        }
        if self.id == 0:
            # 检查是否已存在同email的账户，如果有则更新
            existing = db.fetchone(
                "SELECT id FROM accounts WHERE email = ?", (self.email,)
            )
            if existing:
                self.id = existing["id"] if isinstance(existing, dict) else existing[0]
                db.update("accounts", data, "id = ?", (self.id,))
            else:
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
    def get_syncable(cls) -> list[Account]:
        """获取所有可以同步的账号"""
        rows = db.fetchall("""
            SELECT * FROM accounts 
            WHERE is_active = 1 
            AND connection_status IN ('verified', 'sync_ready')
            ORDER BY id
        """)

        result = [cls._from_row(r) for r in rows]

        # 记录可同步账号数量，如果启用调试日志
        import logging

        logger = logging.getLogger(__name__)
        if logger.isEnabledFor(logging.INFO):
            all_active = cls.get_all_active()
            skipped = [acc for acc in all_active if acc not in result]
            logger.info(
                "可同步账号: %d/%d, 跳过账号: %d",
                len(result),
                len(all_active),
                len(skipped),
            )
            for acc in skipped:
                logger.debug(
                    "跳过账号 %s (状态: %s)", acc.email, acc.connection_status.value
                )

        return result

    @classmethod
    def get_valid_for_display(cls) -> list[Account]:
        """
        获取主界面可显示的账号

        根据批次D2规则：
        1. 只显示 sync_ready 和 verified 状态的账号
        2. 不显示未验证、草稿、失败等状态的账号
        3. 按状态优先级排序: sync_ready > verified
        """
        rows = db.fetchall("""
            SELECT * FROM accounts 
            WHERE is_active = 1 
            AND connection_status IN ('sync_ready', 'verified')
            ORDER BY CASE 
                WHEN connection_status = 'sync_ready' THEN 1
                WHEN connection_status = 'verified' THEN 2
                ELSE 3
            END, id
        """)
        return [cls._from_row(r) for r in rows]

    @classmethod
    def get_default_for_display(cls) -> Account | None:
        """获取默认显示账号（主界面当前邮箱）"""

        # 首先尝试默认且可用的账号
        rows = db.fetchall("""
            SELECT * FROM accounts 
            WHERE is_active = 1 
            AND is_default = 1
            AND connection_status IN ('sync_ready', 'verified')
            ORDER BY 
                CASE 
                    WHEN connection_status = 'sync_ready' THEN 1
                    WHEN connection_status = 'verified' THEN 2
                    ELSE 3
                END,
                id
            LIMIT 1
        """)
        if rows:
            return cls._from_row(rows[0])

        # 其次尝试 sync_ready 状态的账号
        rows = db.fetchall("""
            SELECT * FROM accounts 
            WHERE is_active = 1 
            AND connection_status = 'sync_ready'
            ORDER BY id
            LIMIT 1
        """)
        if rows:
            return cls._from_row(rows[0])

        # 最后尝试 verified 状态的账号
        rows = db.fetchall("""
            SELECT * FROM accounts 
            WHERE is_active = 1 
            AND connection_status = 'verified'
            ORDER BY id
            LIMIT 1
        """)
        if rows:
            return cls._from_row(rows[0])

        # 没有可用账号
        return None

    @classmethod
    def get_ouath_provider_for_email(cls, email: str) -> str:
        """
        根据邮箱地址推断OAuth服务商

        Returns:
            "google", "microsoft", 或空字符串
        """
        email_lower = email.lower()
        if email_lower.endswith("@gmail.com") or email_lower.endswith(
            "@googlemail.com"
        ):
            return "google"
        elif (
            "@outlook." in email_lower
            or "@hotmail." in email_lower
            or "@live." in email_lower
            or "@msn.com" in email_lower
            or (
                "@office365.com" in email_lower
                or email_lower.endswith("@microsoft.com")
            )
        ):
            return "microsoft"
        return ""

    @classmethod
    def get_need_action_accounts(cls) -> list[Account]:
        """获取需要用户操作的账号（未验证、失败等）"""
        rows = db.fetchall("""
            SELECT * FROM accounts 
            WHERE is_active = 1 
            AND connection_status IN (
                'unverified', 'draft', 'auth_failed', 
                'network_failed', 'auth_required', 'validating'
            )
            ORDER BY 
                CASE 
                    WHEN connection_status = 'auth_failed' THEN 1
                    WHEN connection_status = 'network_failed' THEN 2
                    WHEN connection_status = 'auth_required' THEN 3
                    WHEN connection_status = 'validating' THEN 4
                    WHEN connection_status = 'unverified' THEN 5
                    WHEN connection_status = 'draft' THEN 6
                    ELSE 7
                END,
                id
        """)
        return [cls._from_row(r) for r in rows]

    @classmethod
    def get_all(cls) -> list[Account]:
        rows = db.fetchall("SELECT * FROM accounts ORDER BY id")
        return [cls._from_row(r) for r in rows]

    @classmethod
    def _from_row(cls, row: dict) -> Account:
        # Helper function to mimic dict.get() behavior with sqlite3.Row
        def row_get(key, default=None):
            if key in row.keys():
                value = row[key]
                return default if value is None else value
            return default

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
            eas_host=row_get("eas_host", "") or "",
            eas_path=row_get("eas_path", "/Microsoft-Server-ActiveSync")
            or "/Microsoft-Server-ActiveSync",
            ssl_mode=row["ssl_mode"] or "ssl",
            auth_type=row["auth_type"] or "password",
            oauth_provider=row["oauth_provider"] or "",
            connection_status=ConnectionStatus(
                row_get("connection_status", "unverified")
            ),
            _password=row_get("password_enc", ""),
            _oauth_token=row_get("oauth_token_enc", ""),
            _oauth_refresh=row_get("oauth_refresh_enc", ""),
            _validation_result=row_get("validation_result", ""),
            token_expires_at=row_get("token_expires_at", ""),
            last_error_code=row_get("last_error_code", ""),
            last_error_at=row_get("last_error_at", ""),
            sync_fail_count=row_get("sync_fail_count", 0),
            last_verified_at=row_get("last_verified_at", ""),
            is_default=bool(row_get("is_default", 0)),
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
            eas_host=preset.get("eas_host", ""),
            eas_path=preset.get("eas_path", "/Microsoft-Server-ActiveSync"),
            ssl_mode=preset.get("ssl_mode", "ssl"),
            auth_type=preset.get("auth_type", "password"),
            oauth_provider=preset.get("oauth_provider", ""),
        )
        if password:
            account.password = password
        return account

    # ===== OAuth相关方法 =====

    def is_oauth_enabled(self) -> bool:
        """检查是否启用了OAuth认证"""
        return self.auth_type == "oauth2" and bool(self.oauth_provider)

    def oauth_configured(self) -> bool:
        """检查OAuth服务商是否已配置"""
        if not self.is_oauth_enabled():
            return False


        oauth_mgr = OAuthManager()
        return oauth_mgr.is_provider_available(self.oauth_provider)

    def get_oauth_authenticator(self):
        """获取OAuth认证器实例"""
        if not self.is_oauth_enabled():
            return None


        oauth_mgr = OAuthManager()
        return oauth_mgr.get_authenticator(self.oauth_provider)

    def check_and_refresh_token(self) -> bool:
        """
        检查并刷新OAuth令牌

        Returns:
            True - token有效或刷新成功
            False - 需要重新授权
        """
        if not self.is_oauth_enabled():
            return False

        authenticator = self.get_oauth_authenticator()
        if not authenticator:
            logger.warning("无法获取OAuth认证器: %s", self.oauth_provider)
            return False

        try:
            success = authenticator.check_and_refresh(self)
            if not success:
                # 刷新失败，需要重新授权
                self.update_status(ConnectionStatus.AUTH_REQUIRED)
                self.save()
                logger.info("账户 %s OAuth令牌需要重新授权", self.email)
            return success
        except Exception as e:
            logger.error("检查刷新令牌失败: %s", str(e))
            self.update_status(ConnectionStatus.AUTH_REQUIRED)
            self.save()
            return False

    def needs_token_refresh(self) -> bool:
        """检查令牌是否需要刷新"""
        if not self.is_oauth_enabled() or not self.token_expires_at:
            return False

        try:
            expires_at = datetime.fromisoformat(self.token_expires_at)
            buffer_time = timedelta(minutes=5)  # 5分钟缓冲
            return datetime.now() > (expires_at - buffer_time)
        except (ValueError, TypeError):
            return True  # 如果解析失败，认为需要刷新

    def oauth_status_display(self) -> str:
        """获取OAuth状态显示文本"""
        if not self.is_oauth_enabled():
            return "未启用OAuth"

        if not self.oauth_refresh:
            return "未授权"

        if self.connection_status == ConnectionStatus.AUTH_REQUIRED:
            return "需要重新授权"

        if self.needs_token_refresh():
            return "令牌即将过期"

        if self.oauth_token:
            return "已授权"

        return "状态未知"
