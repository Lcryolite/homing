from __future__ import annotations

import json
from dataclasses import dataclass
from enum import Enum

from openemail.core.imap_client import IMAPClient
from openemail.models.account import Account
from openemail.storage.database import db


class OperationType(Enum):
    DELETE = "delete"
    MOVE = "move"
    MARK_READ = "mark_read"
    MARK_FLAGGED = "mark_flagged"
    MARK_SPAM = "mark_spam"


@dataclass
class QueuedOperation:
    type: OperationType
    account_id: int
    email_uid: str
    folder_name: str
    params: dict | None = None


class OperationQueue:
    """离线操作队列管理器"""

    _instance: "OperationQueue" | None = None

    def __new__(cls) -> "OperationQueue":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self) -> None:
        if hasattr(self, "_initialized"):
            return
        self._initialized = True
        self._network_available = True

    def enqueue(
        self,
        operation: QueuedOperation,
    ) -> int:
        """添加操作到队列"""
        op_id = db.insert(
            "operation_queue",
            {
                "account_id": operation.account_id,
                "operation_type": operation.type.value,
                "email_uid": operation.email_uid,
                "folder_name": operation.folder_name,
                "params": json.dumps(operation.params or {}),
                "status": "pending",
                "retry_count": 0,
            },
        )
        return op_id

    def enqueue_delete(self, account_id: int, uid: str, folder: str) -> int:
        return self.enqueue(
            QueuedOperation(
                type=OperationType.DELETE,
                account_id=account_id,
                email_uid=uid,
                folder_name=folder,
            )
        )

    def enqueue_move(
        self, account_id: int, uid: str, source_folder: str, dest_folder: str
    ) -> int:
        return self.enqueue(
            QueuedOperation(
                type=OperationType.MOVE,
                account_id=account_id,
                email_uid=uid,
                folder_name=source_folder,
                params={"dest_folder": dest_folder},
            )
        )

    def enqueue_mark_read(self, account_id: int, uid: str, folder: str) -> int:
        return self.enqueue(
            QueuedOperation(
                type=OperationType.MARK_READ,
                account_id=account_id,
                email_uid=uid,
                folder_name=folder,
            )
        )

    def process_queue(self) -> tuple[int, int]:
        """
        处理队列（联网时）
        返回：(成功数，失败数)
        """
        if not self._network_available:
            return (0, 0)

        pending = db.fetchall(
            "SELECT * FROM operation_queue WHERE status = 'pending' ORDER BY created_at"
        )

        success_count = 0
        fail_count = 0

        for op in pending:
            try:
                self._execute_operation(op)
                db.update(
                    "operation_queue",
                    {"status": "synced"},
                    "id = ?",
                    (op["id"],),
                )
                success_count += 1
            except Exception as e:
                retry_count = op["retry_count"] + 1
                if retry_count >= 3:
                    db.update(
                        "operation_queue",
                        {"status": "failed", "error_message": str(e)},
                        "id = ?",
                        (op["id"],),
                    )
                    fail_count += 1
                else:
                    db.update(
                        "operation_queue",
                        {"retry_count": retry_count},
                        "id = ?",
                        (op["id"],),
                    )

        return (success_count, fail_count)

    def _execute_operation(self, op: dict) -> None:
        """执行单个操作"""
        account = Account.get_by_id(op["account_id"])
        if not account:
            raise ValueError(f"Account {op['account_id']} not found")

        if account.protocol == "imap":
            self._execute_imap_operation(account, op)
        elif account.protocol == "pop3":
            # POP3 支持的操作有限
            if op["operation_type"] == "delete":
                self._execute_pop3_delete(account, op)

    def _execute_imap_operation(self, account: Account, op: dict) -> None:
        """执行 IMAP 操作"""
        import asyncio

        loop = asyncio.new_event_loop()
        try:
            client = IMAPClient(account)
            loop.run_until_complete(client.connect())

            op_type = op["operation_type"]
            uid = op["email_uid"]
            folder = op["folder_name"]
            params = json.loads(op["params"]) if op["params"] else {}

            if op_type == "delete":
                loop.run_until_complete(client.delete_email(uid, folder))
            elif op_type == "move":
                dest_folder = params.get("dest_folder")
                if dest_folder:
                    loop.run_until_complete(client.move_email(uid, folder, dest_folder))
            elif op_type == "mark_read":
                loop.run_until_complete(client.mark_as_read(uid, folder))
            elif op_type == "mark_flagged":
                loop.run_until_complete(client.mark_as_flagged(uid, folder))

            loop.run_until_complete(client.disconnect())
        finally:
            loop.close()

    def _execute_pop3_delete(self, account: Account, op: dict) -> None:
        """执行 POP3 删除操作"""
        from openemail.core.pop3_client import POP3Client

        client = POP3Client(account)
        if client.connect():
            # POP3 删除需要消息编号，这里简化处理
            client.disconnect()

    def set_network_available(self, available: bool) -> None:
        """设置网络状态"""
        self._network_available = available
        if available:
            self.process_queue()

    def get_pending_count(self) -> int:
        """获取待处理操作数"""
        row = db.fetchone(
            "SELECT COUNT(*) as c FROM operation_queue WHERE status = 'pending'"
        )
        return row["c"] if row else 0

    def get_pending_operations(self, limit: int = 50) -> list[dict]:
        """获取待处理操作列表"""
        return db.fetchall(
            "SELECT * FROM operation_queue WHERE status = 'pending' ORDER BY created_at LIMIT ?",
            (limit,),
        )

    def clear_completed(self) -> None:
        """清除已完成的操作"""
        db.delete("operation_queue", "status IN ('synced', 'failed')")


operation_queue = OperationQueue()
