#!/usr/bin/env python3
"""
账号验证快照

批次 D：保存前强校验接入点
=====================
检查并封住所有保存路径，至少包括：

1. `AccountDialog._save()`
2. `WelcomeDialogEnhanced._add_account()`
3. 任何可能绕过 UI 测试按钮直接保存账号的路径

要求：
* 不能只依赖“用户先点了测试连接”
* 保存时必须自行确认测试结果是否有效
* 若没有有效测试结果，保存时自动触发测试或阻止保存
* 测试结果必须与当前表单内容绑定；如果用户改了 host / email / password / auth_type，旧结果立即失效
"""

import hashlib
import hmac
import json
import logging
from dataclasses import dataclass
from typing import TYPE_CHECKING, Dict, Any, Optional

if TYPE_CHECKING:
    from openemail.core.connection_status import AccountValidationResult

logger = logging.getLogger(__name__)

# Pepper for HMAC-based password hashing in validation snapshots.
# This is NOT for secure password storage - only for change detection.
# Deterministic (same input = same output) for snapshot comparison.
_PASSWORD_PEPPER = b"openemail-validation-v1"

@dataclass
class AccountValidationSnapshot:
    """
    账号验证快照

    记录本次测试对应的关键输入摘要，用于验证测试结果是否仍然有效
    """

    email: str = ""
    protocol: str = ""
    auth_type: str = ""
    imap_host: str = ""
    imap_port: int = 0
    smtp_host: str = ""
    smtp_port: int = 0
    pop3_host: str = ""
    pop3_port: int = 0
    eas_host: str = ""
    eas_path: str = ""
    ssl_mode: str = ""
    oauth_provider: str = ""
    password_hash: str = ""  # 密码哈希，不存储明文

    def __post_init__(self):
        """初始化后计算哈希"""
        self._input_hash = self._calculate_hash()

    def _calculate_hash(self) -> str:
        """计算输入内容的哈希值"""
        data = {
            "email": self.email,
            "protocol": self.protocol,
            "auth_type": self.auth_type,
            "imap_host": self.imap_host,
            "imap_port": self.imap_port,
            "smtp_host": self.smtp_host,
            "smtp_port": self.smtp_port,
            "pop3_host": self.pop3_host,
            "pop3_port": self.pop3_port,
            "eas_host": self.eas_host,
            "eas_path": self.eas_path,
            "ssl_mode": self.ssl_mode,
            "oauth_provider": self.oauth_provider,
            "password_hash": self.password_hash,
        }

        json_str = json.dumps(data, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(json_str.encode()).hexdigest()

    @property
    def input_hash(self) -> str:
        """获取输入哈希值"""
        return self._input_hash

    def matches(self, other: "AccountValidationSnapshot") -> bool:
        """检查两个快照是否匹配"""
        return self.input_hash == other.input_hash

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "email": self.email,
            "protocol": self.protocol,
            "auth_type": self.auth_type,
            "imap_host": self.imap_host,
            "imap_port": self.imap_port,
            "smtp_host": self.smtp_host,
            "smtp_port": self.smtp_port,
            "pop3_host": self.pop3_host,
            "pop3_port": self.pop3_port,
            "eas_host": self.eas_host,
            "eas_path": self.eas_path,
            "ssl_mode": self.ssl_mode,
            "oauth_provider": self.oauth_provider,
            "password_hash": self.password_hash,
            "input_hash": self.input_hash,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "AccountValidationSnapshot":
        """从字典创建快照"""
        snapshot = cls(
            email=data.get("email", ""),
            protocol=data.get("protocol", ""),
            auth_type=data.get("auth_type", ""),
            imap_host=data.get("imap_host", ""),
            imap_port=data.get("imap_port", 0),
            smtp_host=data.get("smtp_host", ""),
            smtp_port=data.get("smtp_port", 0),
            pop3_host=data.get("pop3_host", ""),
            pop3_port=data.get("pop3_port", 0),
            eas_host=data.get("eas_host", ""),
            eas_path=data.get("eas_path", ""),
            ssl_mode=data.get("ssl_mode", ""),
            oauth_provider=data.get("oauth_provider", ""),
            password_hash=data.get("password_hash", ""),
        )
        # 手动设置哈希值，确保一致
        snapshot._input_hash = data.get("input_hash", snapshot.input_hash)
        return snapshot

    @classmethod
    def from_form_data(cls, form_data: Dict[str, Any]) -> "AccountValidationSnapshot":
        """从表单数据创建快照"""
        # 计算密码哈希
        password = form_data.get("password", "")
        password_hash = (
            hmac.new(_PASSWORD_PEPPER, password.encode(), hashlib.sha256).hexdigest() if password else ""
        )

        return cls(
            email=form_data.get("email", ""),
            protocol=form_data.get("protocol", ""),
            auth_type=form_data.get("auth_type", ""),
            imap_host=form_data.get("imap_host", ""),
            imap_port=form_data.get("imap_port", 0),
            smtp_host=form_data.get("smtp_host", ""),
            smtp_port=form_data.get("smtp_port", 0),
            pop3_host=form_data.get("pop3_host", ""),
            pop3_port=form_data.get("pop3_port", 0),
            eas_host=form_data.get("eas_host", ""),
            eas_path=form_data.get("eas_path", ""),
            ssl_mode=form_data.get("ssl_mode", ""),
            oauth_provider=form_data.get("oauth_provider", ""),
            password_hash=password_hash,
        )

    @classmethod
    def from_account(cls, account) -> "AccountValidationSnapshot":
        """从Account对象创建快照"""
        return cls(
            email=account.email,
            protocol=account.protocol,
            auth_type=account.auth_type,
            imap_host=account.imap_host,
            imap_port=account.imap_port,
            smtp_host=account.smtp_host,
            smtp_port=account.smtp_port,
            pop3_host=account.pop3_host,
            pop3_port=account.pop3_port,
            eas_host=account.eas_host,
            eas_path=account.eas_path,
            ssl_mode=account.ssl_mode,
            oauth_provider=account.oauth_provider,
            password_hash=hmac.new(_PASSWORD_PEPPER, account.password.encode(), hashlib.sha256).hexdigest()
            if account.password
            else "",
        )


class ValidationManager:
    """
    验证管理器

    管理账号验证状态和测试结果
    """

    def __init__(self):
        self._validation_results: Dict[
            str, AccountValidationResult
        ] = {}  # test_id -> result
        self._validation_snapshots: Dict[
            str, AccountValidationSnapshot
        ] = {}  # test_id -> snapshot

    def register_validation_result(
        self,
        test_id: str,
        snapshot: AccountValidationSnapshot,
        validation_result: "AccountValidationResult",  # 需要从connection_status导入
    ) -> None:
        """
        注册验证结果

        Args:
            test_id: 测试唯一标识
            snapshot: 验证时的输入快照
            validation_result: 验证结果
        """

        self._validation_snapshots[test_id] = snapshot
        self._validation_results[test_id] = validation_result

        # 为验证结果设置输入哈希
        validation_result.input_hash = snapshot.input_hash
        logger.info("Registered validation result for test_id: %s", test_id)

    def get_validation_result(
        self, test_id: str, current_snapshot: Optional[AccountValidationSnapshot] = None
    ) -> Optional["AccountValidationResult"]:
        """
        获取验证结果

        Args:
            test_id: 测试唯一标识
            current_snapshot: 当前输入快照，用于检查结果是否仍然有效

        Returns:
            如果test_id存在且结果仍然有效，返回验证结果；否则返回None
        """

        if test_id not in self._validation_results:
            return None

        result = self._validation_results[test_id]
        snapshot = self._validation_snapshots.get(test_id)

        # 如果没有提供当前快照，直接返回结果
        if current_snapshot is None:
            return result

        # 检查结果是否仍然有效（输入未更改）
        if snapshot and snapshot.matches(current_snapshot):
            return result

        # 输入已更改，结果失效
        logger.warning("Validation result expired for test_id: %s", test_id)
        return None

    def is_result_valid(
        self, test_id: str, current_snapshot: AccountValidationSnapshot
    ) -> bool:
        """
        检查验证结果是否仍然有效

        Args:
            test_id: 测试唯一标识
            current_snapshot: 当前输入快照

        Returns:
            如果结果存在且有效返回True，否则返回False
        """
        result = self.get_validation_result(test_id, current_snapshot)
        return result is not None and result.is_valid

    def can_save_account(
        self,
        account_snapshot: AccountValidationSnapshot,
        validation_result: Optional["AccountValidationResult"] = None,
        target_status: str = "verified",
    ) -> bool:
        """
        检查是否可以保存账号

        Args:
            account_snapshot: 账号输入快照
            validation_result: 验证结果（可选）
            target_status: 目标状态

        Returns:
            如果可以保存返回True，否则返回False
        """
        from openemail.core.connection_status import (
            ConnectionStatus,
            is_savable,
        )

        if target_status == "verified":
            status = ConnectionStatus.VERIFIED
        elif target_status == "sync_ready":
            status = ConnectionStatus.SYNC_READY
        else:
            # 其他状态默认允许保存
            return True

        if validation_result:
            # 检查验证结果的有效性
            if validation_result.input_hash and account_snapshot.input_hash:
                if validation_result.input_hash != account_snapshot.input_hash:
                    logger.warning("Input hash mismatch, validation result expired")
                    return False

            # 检查是否可以通过状态验证
            if not is_savable(status, validation_result):
                return False

        return True

    def clear_expired_results(self, max_age_hours: int = 24) -> None:
        """清理过期验证结果"""
        # TODO: 实现基于时间的清理
        pass


# 全局单例
_validation_manager: Optional[ValidationManager] = None


def get_validation_manager() -> ValidationManager:
    """获取全局验证管理器单例"""
    global _validation_manager
    if _validation_manager is None:
        _validation_manager = ValidationManager()
    return _validation_manager
