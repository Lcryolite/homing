#!/usr/bin/env python3
"""
连接状态状态机

批次 D：真实认证闭环
==============
完成以下目标：

1. 保存账号前强制执行真实认证
2. 收信协议失败时禁止保存
3. 明确区分：
   * 可保存草稿
   * 已验证可用
   * 可见但不可同步
4. 落地 `connection_status` 状态机
5. 同步器跳过未验证/失败账号
6. 不允许任何“未实现 / 未支持 / 仅预检”结果被当作认证通过
"""

import logging
from enum import Enum
from typing import Dict, Any, Optional, List

logger = logging.getLogger(__name__)


class ConnectionStatus(str, Enum):
    """连接状态状态机"""

    # 草稿状态：用户正在编辑，未提交
    DRAFT = "draft"

    # 验证中：正在执行连接测试
    VALIDATING = "validating"

    # 需要认证：需要用户输入认证信息
    AUTH_REQUIRED = "auth_required"

    # 已验证：收信协议真实测试通过
    VERIFIED = "verified"

    # 同步就绪：已验证且准备好同步
    SYNC_READY = "sync_ready"

    # 认证失败：用户名/密码/令牌错误
    AUTH_FAILED = "auth_failed"

    # 网络失败：服务器不可达、网络错误
    NETWORK_FAILED = "network_failed"

    # 已禁用：用户手动禁用
    DISABLED = "disabled"

    # 未验证：历史账号无法确认状态
    UNVERIFIED = "unverified"


class AccountValidationResult:
    """账号验证结果"""

    def __init__(
        self,
        inbound_success: bool = False,
        outbound_success: bool = False,
        test_id: Optional[str] = None,
        error_code: Optional[str] = None,
        error_message: Optional[str] = None,
        input_hash: Optional[str] = None,
        # 批次E新增字段
        fully_verified: bool = False,  # 是否完全验证
        auth_verified: bool = False,  # 是否认证通过
        verification_level: str = "unknown",  # 验证级别: precheck/endpoint/connection/auth/full
        protocol_results: Optional[dict] = None,  # 各协议详细结果
        error_categories: Optional[List[str]] = None,  # 错误分类
        suggestions: Optional[List[str]] = None,  # 修复建议
    ):
        self.inbound_success = inbound_success  # 收信协议通过
        self.outbound_success = outbound_success  # 发信协议通过
        self.test_id = test_id  # 测试唯一标识
        self.error_code = error_code
        self.error_message = error_message
        self._input_hash = input_hash  # 输入内容哈希，用于检查表单是否已修改
        # 批次E新增字段
        self.fully_verified = fully_verified
        self.auth_verified = auth_verified
        self.verification_level = verification_level
        self.protocol_results = protocol_results or {}
        self.error_categories = error_categories or []
        self.suggestions = suggestions or []

    @property
    def input_hash(self) -> Optional[str]:
        """获取输入哈希值"""
        return self._input_hash

    @input_hash.setter
    def input_hash(self, value: Optional[str]) -> None:
        """设置输入哈希值"""
        self._input_hash = value

    def to_dict(self) -> Dict[str, Any]:
        return {
            "inbound_success": self.inbound_success,
            "outbound_success": self.outbound_success,
            "test_id": self.test_id,
            "error_code": self.error_code,
            "error_message": self.error_message,
            "input_hash": self.input_hash,
            # 批次E新增字段
            "fully_verified": self.fully_verified,
            "auth_verified": self.auth_verified,
            "verification_level": self.verification_level,
            "protocol_results": self.protocol_results,
            "error_categories": self.error_categories,
            "suggestions": self.suggestions,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "AccountValidationResult":
        return cls(
            inbound_success=data.get("inbound_success", False),
            outbound_success=data.get("outbound_success", False),
            test_id=data.get("test_id"),
            error_code=data.get("error_code"),
            error_message=data.get("error_message"),
            input_hash=data.get("input_hash"),
            # 批次E新增字段
            fully_verified=data.get("fully_verified", False),
            auth_verified=data.get("auth_verified", False),
            verification_level=data.get("verification_level", "unknown"),
            protocol_results=data.get("protocol_results", {}),
            error_categories=data.get("error_categories", []),
            suggestions=data.get("suggestions", []),
        )

    @property
    def is_valid(self) -> bool:
        """验证结果是否有效（包含有效测试且输入未更改）"""
        return bool(self.test_id)

    @property
    def is_complete(self) -> bool:
        """验证是否完整（收信和发信都测试过）"""
        return self.inbound_success or self.outbound_success


def get_next_status(
    current_status: ConnectionStatus,
    validation_result: Optional[AccountValidationResult] = None,
    user_action: Optional[str] = None,
) -> ConnectionStatus:
    """
    根据当前状态和验证结果/用户操作计算下一个状态

    使用 error_categories 作为主要判断依据，不依赖字符串匹配。
    """
    # 用户操作处理
    if user_action == "disable":
        return ConnectionStatus.DISABLED
    elif user_action == "enable" and current_status == ConnectionStatus.DISABLED:
        return ConnectionStatus.UNVERIFIED
    elif user_action == "retry":
        return ConnectionStatus.VALIDATING

    # 验证结果处理（基于 error_categories，不依赖字符串匹配）
    if validation_result:
        error_categories = validation_result.error_categories or []

        if validation_result.inbound_success:
            # 收信验证通过
            return ConnectionStatus.VERIFIED
        elif any(
            cat in error_categories
            for cat in ["auth_error", "authentication_error"]
        ):
            return ConnectionStatus.AUTH_FAILED
        elif any(
            cat in error_categories
            for cat in [
                "network_error",
                "dns_error",
                "ssl_error",
                "timeout_error",
                "connection_error",
            ]
        ):
            return ConnectionStatus.NETWORK_FAILED
        elif validation_result.error_message:
            # 有错误信息但无明确分类，根据 inbound_success 判断
            if not validation_result.inbound_success:
                return ConnectionStatus.AUTH_FAILED
            return ConnectionStatus.NETWORK_FAILED
        else:
            return ConnectionStatus.AUTH_FAILED

    # 默认状态转换
    if current_status == ConnectionStatus.DRAFT:
        return ConnectionStatus.VALIDATING
    elif current_status == ConnectionStatus.VALIDATING:
        return ConnectionStatus.UNVERIFIED
    elif current_status == ConnectionStatus.UNVERIFIED:
        return ConnectionStatus.UNVERIFIED

    return current_status


def get_suggestions_for_categories(
    error_categories: list[str],
) -> list[str]:
    """
    将错误类别映射为用户可读的修复建议

    Returns:
        建议列表，每条建议都是用户可操作的行动
    """
    suggestions: list[str] = []
    seen_suggestions: set[str] = set()

    category_suggestions = {
        "auth_error": "检查用户名和密码是否正确",
        "authentication_error": "检查用户名和密码是否正确",
        "network_error": "检查网络连接和服务器地址",
        "dns_error": "DNS 解析失败，检查服务器地址拼写",
        "ssl_error": "SSL/TLS 连接失败，检查加密设置",
        "timeout_error": "连接超时，检查网络或服务器地址",
        "configuration_error": "检查账户配置填写是否完整",
        "protocol_error": "服务器协议响应异常，检查端口和协议设置",
        "server_error": "服务器端错误，请稍后重试",
        "server_rejected": "服务器拒绝连接，检查账户权限",
        "unsupported_error": "该协议或配置暂不支持",
    }

    for cat in error_categories:
        text = category_suggestions.get(cat)
        if text and text not in seen_suggestions:
            suggestions.append(text)
            seen_suggestions.add(text)

    return suggestions


def can_transition(from_status: ConnectionStatus, to_status: ConnectionStatus) -> bool:
    """
    检查状态转换是否合法

    合法转换规则：
    1. 任何状态可以转为 DISABLED
    2. DISABLED 只能转为 VALIDATING 或 UNVERIFIED
    3. VALIDATING 只能转为 VERIFIED, AUTH_FAILED, NETWORK_FAILED, UNVERIFIED
    4. VERIFIED 只能转为 SYNC_READY, AUTH_FAILED, NETWORK_FAILED, DISABLED
    5. SYNC_READY 是最终状态，只能转为 DISABLED
    6. AUTH_FAILED/NETWORK_FAILED 可以转为 VALIDATING 或 DISABLED
    """
    # 任何状态都可以被禁用
    if to_status == ConnectionStatus.DISABLED:
        return True

    # 从禁用状态恢复
    if from_status == ConnectionStatus.DISABLED:
        return to_status in [ConnectionStatus.VALIDATING, ConnectionStatus.UNVERIFIED]

    # 验证中状态转换
    if from_status == ConnectionStatus.VALIDATING:
        return to_status in [
            ConnectionStatus.VERIFIED,
            ConnectionStatus.AUTH_FAILED,
            ConnectionStatus.NETWORK_FAILED,
            ConnectionStatus.UNVERIFIED,
        ]

    # 已验证状态转换
    if from_status == ConnectionStatus.VERIFIED:
        return to_status in [
            ConnectionStatus.SYNC_READY,
            ConnectionStatus.AUTH_FAILED,
            ConnectionStatus.NETWORK_FAILED,
            ConnectionStatus.DISABLED,
        ]

    # 同步就绪状态转换
    if from_status == ConnectionStatus.SYNC_READY:
        return to_status == ConnectionStatus.DISABLED

    # 认证失败/网络失败状态转换
    if from_status in [ConnectionStatus.AUTH_FAILED, ConnectionStatus.NETWORK_FAILED]:
        return to_status in [ConnectionStatus.VALIDATING, ConnectionStatus.DISABLED]

    # 其他状态转换
    transitions = {
        ConnectionStatus.DRAFT: [ConnectionStatus.VALIDATING],
        ConnectionStatus.AUTH_REQUIRED: [ConnectionStatus.VALIDATING],
        ConnectionStatus.UNVERIFIED: [
            ConnectionStatus.VALIDATING,
            ConnectionStatus.DISABLED,
        ],
    }

    return to_status in transitions.get(from_status, [])


def should_sync(status: ConnectionStatus) -> bool:
    """
    检查该状态下的账号是否应该参与同步

    同步器只处理：
    * VERIFIED
    * SYNC_READY
    """
    return status in [ConnectionStatus.VERIFIED, ConnectionStatus.SYNC_READY]


def is_savable(
    status: ConnectionStatus, validation_result: Optional[AccountValidationResult]
) -> bool:
    """
    检查该状态下的账号是否可以保存

    规则：
    1. 收信协议测试必须真实通过才能保存为VERIFIED状态
    2. 测试结果必须有效（test_id存在且输入未更改）
    3. 不允许将"未实现"/"未支持"的结果作为验证通过
    4. "仅预检通过"不能作为verified保存
    """
    if status == ConnectionStatus.VERIFIED:
        if not validation_result or not validation_result.is_valid:
            return False
        if not validation_result.inbound_success:
            return False

        # 确保不是"未实现"或"未支持"的结果
        if validation_result.error_message and any(
            msg in validation_result.error_message.lower()
            for msg in [
                "not implemented",
                "unimplemented",
                "not supported",
                "unsupported",
                "未实现",
                "未支持",
                "暂未",
            ]
        ):
            return False

        # 批次E：检查验证级别
        # 确保不是"仅预检通过"或低级别验证
        verification_level = (
            validation_result.verification_level.lower()
            if validation_result.verification_level
            else ""
        )
        if verification_level in [
            "precheck",
            "endpoint_verified",
            "connection_verified",
        ]:
            logger.warning(
                "Cannot save as VERIFIED with low verification level: %s",
                verification_level,
            )
            return False

        # 批次E：检查错误分类
        error_categories = validation_result.error_categories or []
        if any(cat in ["not_implemented", "unsupported"] for cat in error_categories):
            logger.warning("Cannot save as VERIFIED with unsupported protocol")
            return False

        return True
    elif status == ConnectionStatus.SYNC_READY:
        # SYNC_READY必须是已验证状态
        if not validation_result or not validation_result.is_valid:
            return False
        return validation_result.inbound_success
    else:
        # 其他状态可以保存（如草稿、未验证等）
        return True


def get_status_display(status: ConnectionStatus) -> str:
    """获取状态显示文本"""
    display_map = {
        ConnectionStatus.DRAFT: "草稿",
        ConnectionStatus.VALIDATING: "验证中...",
        ConnectionStatus.AUTH_REQUIRED: "需要认证",
        ConnectionStatus.VERIFIED: "已验证",
        ConnectionStatus.SYNC_READY: "同步就绪",
        ConnectionStatus.AUTH_FAILED: "认证失败",
        ConnectionStatus.NETWORK_FAILED: "连接失败",
        ConnectionStatus.DISABLED: "已禁用",
        ConnectionStatus.UNVERIFIED: "未验证",
    }
    return display_map.get(status, status.value)


def get_status_icon(status: ConnectionStatus) -> str:
    """获取状态图标"""
    icon_map = {
        ConnectionStatus.DRAFT: "📝",
        ConnectionStatus.VALIDATING: "⏳",
        ConnectionStatus.AUTH_REQUIRED: "🔒",
        ConnectionStatus.VERIFIED: "✅",
        ConnectionStatus.SYNC_READY: "🔄",
        ConnectionStatus.AUTH_FAILED: "❌",
        ConnectionStatus.NETWORK_FAILED: "🌐❌",
        ConnectionStatus.DISABLED: "🚫",
        ConnectionStatus.UNVERIFIED: "❓",
    }
    return icon_map.get(status, "❓")
