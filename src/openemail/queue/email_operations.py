from __future__ import annotations

import logging
from typing import List, Dict, Any, Optional

from openemail.queue.offline_queue import (
    get_offline_queue,
    OfflineOperation,
    OperationType,
    PriorityLevel,
)
from openemail.models.folder import Folder


class EmailOperationsManager:
    """邮件操作管理器，集成离线队列"""

    def __init__(self):
        self.queue = get_offline_queue()
        self._register_handlers()

    def _register_handlers(self):
        """注册操作处理器"""
        # 注册邮件相关操作的处理器
        self.queue.register_operation_handler(
            OperationType.MARK_READ.value, self._handle_mark_read
        )
        self.queue.register_operation_handler(
            OperationType.MARK_UNREAD.value, self._handle_mark_unread
        )
        self.queue.register_operation_handler(
            OperationType.MOVE_TO_FOLDER.value, self._handle_move_to_folder
        )
        self.queue.register_operation_handler(
            OperationType.DELETE_EMAIL.value, self._handle_delete_email
        )
        self.queue.register_operation_handler(
            OperationType.MARK_FLAGGED.value, self._handle_mark_flagged
        )
        self.queue.register_operation_handler(
            OperationType.MARK_UNFLAGGED.value, self._handle_mark_unflagged
        )
        logging.info("邮件操作处理器已注册")

    def mark_emails_read(
        self, email_ids: List[int], account_id: int, immediate: bool = False
    ) -> bool:
        """
        标记邮件为已读

        Args:
            email_ids: 邮件ID列表
            account_id: 账户ID
            immediate: 是否立即执行（True）或加入队列（False）
        """
        if not email_ids:
            return True

        if immediate:
            # 立即执行
            return self._handle_mark_read({"email_ids": email_ids}, account_id)
        else:
            # 加入队列
            operation_id = self.queue.create_mark_read_operation(email_ids, account_id)
            return operation_id > 0

    def mark_emails_unread(
        self, email_ids: List[int], account_id: int, immediate: bool = False
    ) -> bool:
        """
        标记邮件为未读

        Args:
            email_ids: 邮件ID列表
            account_id: 账户ID
            immediate: 是否立即执行（True）或加入队列（False）
        """
        if not email_ids:
            return True

        if immediate:
            # 立即执行
            return self._handle_mark_unread({"email_ids": email_ids}, account_id)
        else:
            # 加入队列
            operation_id = self.queue.create_mark_unread_operation(
                email_ids, account_id
            )
            return operation_id > 0

    def mark_emails_flagged(
        self,
        email_ids: List[int],
        flagged: bool,
        account_id: int,
        immediate: bool = False,
    ) -> bool:
        """
        标记或取消标记邮件星标

        Args:
            email_ids: 邮件ID列表
            flagged: True为标记星标，False为取消星标
            account_id: 账户ID
            immediate: 是否立即执行（True）或加入队列（False）
        """
        if not email_ids:
            return True

        if immediate:
            # 立即执行
            if flagged:
                return self._handle_mark_flagged({"email_ids": email_ids}, account_id)
            else:
                return self._handle_mark_unflagged({"email_ids": email_ids}, account_id)
        else:
            # 创建操作
            operation = OfflineOperation(
                operation_type=(
                    OperationType.MARK_FLAGGED.value
                    if flagged
                    else OperationType.MARK_UNFLAGGED.value
                ),
                account_id=account_id,
                data={"email_ids": email_ids},
                priority=PriorityLevel.LOW.value,
            )

            operation_id = self.queue.add_operation(operation)
            return operation_id > 0

    def move_emails_to_folder(
        self,
        email_ids: List[int],
        target_folder_id: int,
        account_id: int,
        immediate: bool = False,
    ) -> bool:
        """
        移动邮件到指定文件夹

        Args:
            email_ids: 邮件ID列表
            target_folder_id: 目标文件夹ID
            account_id: 账户ID
            immediate: 是否立即执行（True）或加入队列（False）
        """
        if not email_ids or not target_folder_id:
            return False

        if immediate:
            # 立即执行
            return self._handle_move_to_folder(
                {"email_ids": email_ids, "target_folder_id": target_folder_id},
                account_id,
            )
        else:
            # 加入队列
            operation_id = self.queue.create_move_operation(
                email_ids, target_folder_id, account_id
            )
            return operation_id > 0

    def delete_emails(
        self,
        email_ids: List[int],
        account_id: int,
        permanent: bool = False,
        immediate: bool = False,
    ) -> bool:
        """
        删除邮件

        Args:
            email_ids: 邮件ID列表
            account_id: 账户ID
            permanent: 是否永久删除（True）或移到垃圾箱（False）
            immediate: 是否立即执行（True）或加入队列（False）
        """
        if not email_ids:
            return True

        if immediate:
            # 立即执行
            return self._handle_delete_email(
                {"email_ids": email_ids, "permanent": permanent}, account_id
            )
        else:
            # 加入队列
            operation_id = self.queue.create_delete_operation(
                email_ids, account_id, permanent
            )
            return operation_id > 0

    def send_email_immediately(
        self, draft_data: Dict[str, Any], account_id: int
    ) -> bool:
        """
        立即发送邮件（不使用队列，直接发送）

        Args:
            draft_data: 草稿数据
            account_id: 账户ID
        """
        try:
            # TODO: 实现即时发送邮件逻辑
            # 这里需要调用实际的邮件发送功能
            logging.info(f"立即发送邮件，账户ID: {account_id}")

            # 模拟发送成功
            return True

        except Exception as e:
            logging.error(f"发送邮件失败: {e}")
            return False

    def send_email_via_queue(self, draft_data: Dict[str, Any], account_id: int) -> int:
        """
        通过队列发送邮件

        Args:
            draft_data: 草稿数据
            account_id: 账户ID

        Returns:
            操作ID，0表示失败
        """
        operation_id = self.queue.create_send_email_operation(draft_data, account_id)
        if operation_id > 0:
            logging.info(f"邮件已加入发送队列，操作ID: {operation_id}")
        else:
            logging.error("邮件加入发送队列失败")

        return operation_id

    def _handle_mark_read(self, data: Dict[str, Any], account_id: int) -> bool:
        """处理标记已读操作"""
        try:
            from openemail.storage.database import db

            email_ids = data.get("email_ids", [])
            if not email_ids:
                return True

            db.update_safe("emails", {"is_read": 1}, {"id": email_ids})
            logging.info(f"批量标记 {len(email_ids)} 封邮件为已读")
            return True

        except Exception as e:
            logging.error(f"标记已读失败: {e}")
            return False

    def _handle_mark_unread(self, data: Dict[str, Any], account_id: int) -> bool:
        """处理标记未读操作"""
        try:
            from openemail.storage.database import db

            email_ids = data.get("email_ids", [])
            if not email_ids:
                return True

            db.update_safe("emails", {"is_read": 0}, {"id": email_ids})
            logging.info(f"批量标记 {len(email_ids)} 封邮件为未读")
            return True

        except Exception as e:
            logging.error(f"标记未读失败: {e}")
            return False

    def _handle_mark_flagged(self, data: Dict[str, Any], account_id: int) -> bool:
        """处理标记星标操作"""
        try:
            from openemail.storage.database import db

            email_ids = data.get("email_ids", [])
            if not email_ids:
                return True

            db.update_safe("emails", {"is_flagged": 1}, {"id": email_ids})
            logging.info(f"批量标记 {len(email_ids)} 封邮件为星标")
            return True

        except Exception as e:
            logging.error(f"标记星标失败: {e}")
            return False

    def _handle_mark_unflagged(self, data: Dict[str, Any], account_id: int) -> bool:
        """处理取消标记星标操作"""
        try:
            from openemail.storage.database import db

            email_ids = data.get("email_ids", [])
            if not email_ids:
                return True

            db.update_safe("emails", {"is_flagged": 0}, {"id": email_ids})
            logging.info(f"批量取消 {len(email_ids)} 封邮件的星标")
            return True

        except Exception as e:
            logging.error(f"取消星标失败: {e}")
            return False

    def _handle_move_to_folder(self, data: Dict[str, Any], account_id: int) -> bool:
        """处理移动邮件操作"""
        try:
            from openemail.storage.database import db

            email_ids = data.get("email_ids", [])
            target_folder_id = data.get("target_folder_id")

            if not email_ids or not target_folder_id:
                return False

            folder = Folder.get_by_id(target_folder_id)
            if not folder:
                logging.error(f"目标文件夹不存在: ID={target_folder_id}")
                return False

            db.update_safe("emails", {"folder_id": target_folder_id}, {"id": email_ids})
            logging.info(f"批量移动 {len(email_ids)} 封邮件到文件夹 {folder.name}")
            return True

        except Exception as e:
            logging.error(f"移动邮件失败: {e}")
            return False

    def _handle_delete_email(self, data: Dict[str, Any], account_id: int) -> bool:
        """处理删除邮件操作"""
        try:
            from openemail.storage.database import db

            email_ids = data.get("email_ids", [])
            permanent = data.get("permanent", False)

            if not email_ids:
                return True

            if permanent:
                db.delete_safe("emails", {"id": email_ids})
                logging.info(f"永久删除了 {len(email_ids)} 封邮件")
            else:
                trash_folder = Folder.get_by_name(account_id, "Trash")
                if trash_folder:
                    db.update_safe(
                        "emails", {"folder_id": trash_folder.id}, {"id": email_ids}
                    )
                    logging.info(f"移动 {len(email_ids)} 封邮件到垃圾箱")
                else:
                    logging.error("找不到垃圾箱文件夹")
                    return False

            return True

        except Exception as e:
            logging.error(f"删除邮件失败: {e}")
            return False

    def get_queue_statistics(self) -> Dict[str, Any]:
        """获取队列统计信息"""
        stats = self.queue.get_queue_stats()
        return stats.to_dict()

    def get_pending_operations(self) -> List[Dict[str, Any]]:
        """获取待处理操作"""
        operations = self.queue.get_pending_operations(limit=50)
        return [self._operation_to_dict(op) for op in operations]

    def get_failed_operations(self) -> List[Dict[str, Any]]:
        """获取失败操作"""
        operations = self.queue.get_failed_operations(limit=50)
        return [self._operation_to_dict(op) for op in operations]

    def retry_operation(self, operation_id: int) -> bool:
        """重试失败操作"""
        return self.queue.retry_failed_operation(operation_id)

    def cancel_operation(self, operation_id: int) -> bool:
        """取消操作"""
        return self.queue.cancel_operation(operation_id)

    def _operation_to_dict(self, operation: OfflineOperation) -> Dict[str, Any]:
        """将操作对象转换为字典"""
        return {
            "id": operation.id,
            "type": operation.operation_type,
            "status": operation.status,
            "priority": operation.priority,
            "retry_count": operation.retry_count,
            "max_retries": operation.max_retries,
            "created_at": operation.created_at.isoformat()
            if operation.created_at
            else None,
            "last_attempt": operation.last_attempt.isoformat()
            if operation.last_attempt
            else None,
            "error_message": operation.error_message,
            "account_id": operation.account_id,
        }

    def start_workers(self, num_workers: int = 3) -> None:
        """启动工作线程"""
        self.queue.start_workers(num_workers)

    def stop_workers(self) -> None:
        """停止工作线程"""
        self.queue.stop_workers()

    def clear_old_operations(self, days: int = 7) -> int:
        """清理旧的操作记录"""
        return self.queue.clear_completed_operations(days)


# 单例实例
_email_operations_manager: Optional[EmailOperationsManager] = None


def get_email_operations_manager() -> EmailOperationsManager:
    """获取邮件操作管理器实例"""
    global _email_operations_manager

    if _email_operations_manager is None:
        _email_operations_manager = EmailOperationsManager()

    return _email_operations_manager


def init_email_operations() -> None:
    """初始化邮件操作管理器（需要手动调用）"""
    # 配置日志
    logging.basicConfig(level=logging.INFO)

    # 创建管理器实例并启动工作线程
    manager = get_email_operations_manager()

    # 默认启动2个工作线程
    manager.start_workers(2)

    logging.info("邮件操作管理器初始化完成")
