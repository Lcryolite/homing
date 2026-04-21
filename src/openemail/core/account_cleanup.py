#!/usr/bin/env python3
"""
账号清理和修复工具

批次 D2：处理历史脏账号
"""

import logging
import re
from typing import List

from openemail.models.account import Account
from openemail.core.connection_status import ConnectionStatus

logger = logging.getLogger(__name__)


def is_dirty_email(email: str) -> bool:
    """
    检查是否为可疑邮箱地址（风险提示，不直接判死）

    批次 E：收紧检测算法，不再用邮箱模式作为主验证依据

    规则：
    1. 明显测试邮箱：test@test.com, example@example.com
    2. 过于简易的格式：xx@xx.com, aa@bb.com
    3. 空邮箱或不完整格式

    重要：此方法仅用于风险提示，不应用作账号有效性主依据
    """
    if not email:
        return True

    email = email.strip().lower()

    # 空邮箱
    if not email:
        return True

    # 明显测试邮箱（宽松匹配，仅提示）
    suspicious_patterns = [
        r"^test@test\.com$",
        r"^example@example\.com$",
        r"^demo@demo\.com$",
        r"^temp@temp\.com$",
    ]

    for pattern in suspicious_patterns:
        if re.match(pattern, email):
            logger.debug("检测到明显测试邮箱（风险提示）: %s", email)
            return True

    # 过于简易的重复模式：xx@xx.com
    if "@" in email:
        local_part, domain = email.split("@", 1)
        domain_base = domain.split(".")[0] if "." in domain else ""

        # 仅检查长度极短且完全相同的重复模式
        if (
            len(local_part) == 2
            and local_part == domain_base
            and domain.endswith(".com")
            and len(domain_base) == 2
        ):
            logger.debug("检测到极简重复模式邮箱（风险提示）: %s", email)
            return True

    return False


def check_email_risk(email: str) -> dict:
    """
    检查邮箱风险等级（提供更细粒度的风险提示）

    返回：
        {
            "needs_review": bool,  # 是否需要人工审查
            "risk_level": "low" | "medium" | "high",  # 风险级别
            "reason": str,          # 风险原因说明
            "suggestion": str       # 建议措施
        }
    """
    if not email:
        return {
            "needs_review": True,
            "risk_level": "high",
            "reason": "邮箱地址为空",
            "suggestion": "请输入有效的邮箱地址",
        }

    email = email.strip().lower()

    # 明显测试邮箱
    if any(pattern in email for pattern in ["test@test.com", "example@example.com"]):
        return {
            "needs_review": True,
            "risk_level": "high",
            "reason": "使用了常见的测试邮箱地址",
            "suggestion": "建议使用真实邮箱地址进行验证",
        }

    # 过于简单的重复模式
    if "@" in email:
        local_part, domain = email.split("@", 1)
        if len(local_part) <= 2 and "@" in email and "." not in email:
            return {
                "needs_review": True,
                "risk_level": "medium",
                "reason": "邮箱格式过于简单",
                "suggestion": "请确认邮箱地址格式是否正确",
            }

    # localhost或本地地址（开发环境允许）
    if "localhost" in email or "127.0.0.1" in email:
        return {
            "needs_review": False,
            "risk_level": "low",
            "reason": "使用了本地地址（开发环境）",
            "suggestion": "开发环境下可以正常使用",
        }

    return {
        "needs_review": False,
        "risk_level": "low",
        "reason": "邮箱格式正常",
        "suggestion": "可以正常使用",
    }


def mark_suspicious_accounts_as_needs_review() -> int:
    """
    标记可疑账号为需要审查（不再直接降级）

    批次 E：收紧策略，不再直接判死可疑邮箱
    改为风险提示，保留账号的已验证状态（如果确实已验证）
    """
    all_accounts = Account.get_all()
    marked_count = 0

    for account in all_accounts:
        # 只处理活跃账号
        if not account.is_active:
            continue

        # 检查邮箱风险
        risk_info = check_email_risk(account.email)

        # 如果是高风险且需要审查，设置风险标记
        if risk_info["needs_review"] and risk_info["risk_level"] == "high":
            logger.warning(
                "发现高风险邮箱账号（风险提示，不降级）: %s (状态: %s, 原因: %s)",
                account.email,
                account.connection_status.value,
                risk_info["reason"],
            )

            # 保存风险信息到账号元数据
            metadata = account.metadata_dict
            metadata["risk_info"] = risk_info
            account.metadata_dict = metadata
            account.save()
            marked_count += 1
            logger.info("已标记高风险账号风险信息: %s", account.email)

    return marked_count


def mark_dirty_accounts_as_unverified() -> int:
    """
    （兼容函数）标记可疑账号为需要审查
    """
    return mark_suspicious_accounts_as_needs_review()


def cleanup_disabled_accounts(days_threshold: int = 30) -> int:
    """
    清理长期禁用的账号

    Args:
        days_threshold: 禁用超过多少天的账号将被清理
    """
    # TODO: 实现基于时间的清理
    return 0


def validate_account_statuses() -> List[str]:
    """
    验证所有账号状态的一致性

    返回：
        包含问题的描述列表
    """
    issues = []
    all_accounts = Account.get_all()

    for account in all_accounts:
        # 检查状态是否有效
        try:
            status = ConnectionStatus(account.connection_status.value)
        except ValueError:
            issues.append(
                f"账号 {account.email} 有无效状态: {account.connection_status.value}"
            )
            continue

        # 检查高风险邮箱并提供警告提示（不再直接判错）
        risk_info = check_email_risk(account.email)
        if risk_info["needs_review"] and risk_info["risk_level"] == "high":
            issues.append(
                f"高风险邮箱 {account.email} 需要人工审查（原因为: {risk_info['reason']}）"
            )

        # 检查已禁用的账号是否被标记为已验证
        if not account.is_active and status in [
            ConnectionStatus.VERIFIED,
            ConnectionStatus.SYNC_READY,
        ]:
            issues.append(f"已禁用的账号 {account.email} 被错误标记为 {status.value}")

    return issues


def fix_inconsistent_accounts() -> dict:
    """
    修复不一致的账号状态

    返回：
        修复统计信息
    """
    stats = {
        "dirty_marked": 0,
        "disabled_fixed": 0,
        "invalid_status_fixed": 0,
        "total_accounts": 0,
    }

    all_accounts = Account.get_all()
    stats["total_accounts"] = len(all_accounts)

    for account in all_accounts:
        # 检查高风险邮箱（仅记录风险信息，不自动降级）
        risk_info = check_email_risk(account.email)
        if risk_info["needs_review"] and risk_info["risk_level"] == "high":
            # 保存风险信息但不修改状态
            metadata = account.metadata_dict
            metadata["risk_info"] = risk_info
            account.metadata_dict = metadata
            account.save()
            stats["dirty_marked"] += 1
            logger.info(
                "标记高风险邮箱 %s（保持原状态: %s，原因: %s）",
                account.email,
                account.connection_status.value,
                risk_info["reason"],
            )

        # 修复已禁用但状态为已验证的账号
        if not account.is_active and account.connection_status in [
            ConnectionStatus.VERIFIED,
            ConnectionStatus.SYNC_READY,
        ]:
            old_status = account.connection_status.value
            account.update_status(ConnectionStatus.DISABLED)
            account.save()
            stats["disabled_fixed"] += 1
            logger.warning(
                "修复禁用账号 %s: %s -> %s",
                account.email,
                old_status,
                account.connection_status.value,
            )

    return stats


def run_account_cleanup() -> None:
    """运行账号清理（通常在应用启动时调用）"""
    logger.info("开始账号清理检查...")

    # 修复不一致的账号
    stats = fix_inconsistent_accounts()

    # 验证状态
    issues = validate_account_statuses()

    # 记录结果
    if stats["dirty_marked"] > 0 or stats["disabled_fixed"] > 0 or issues:
        logger.info("账号检查完成，发现以下情况:")
        if stats["dirty_marked"] > 0:
            logger.info("  - 标记高风险邮箱（风险提醒）: %d", stats["dirty_marked"])
        if stats["disabled_fixed"] > 0:
            logger.info("  - 修复禁用账号状态: %d", stats["disabled_fixed"])
    else:
        logger.info("账号状态正常，无需修复")

    if issues:
        logger.info("发现以下需要关注的情况:")
        for issue in issues:
            logger.info("  - %s", issue)

    logger.info("账号检查完成，总计账号: %d", stats["total_accounts"])


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )

    # 运行清理
    run_account_cleanup()
