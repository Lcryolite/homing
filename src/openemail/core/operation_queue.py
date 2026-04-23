from __future__ import annotations

import json
import logging
import threading
import time
from dataclasses import dataclass
from enum import Enum

from openemail.models.account import Account
from openemail.storage.database import db

logger = logging.getLogger(__name__)


class OperationType(Enum):
    DELETE = "delete"
    MOVE = "move"
    MARK_READ = "mark_read"
    MARK_FLAGGED = "mark_flagged"
    MARK_SPAM = "mark_spam"


# Operations that are naturally idempotent — duplicate enqueues can be collapsed.
_IDEMPOTENT_OPS = {OperationType.MARK_READ, OperationType.MARK_FLAGGED, OperationType.MARK_SPAM}


@dataclass
class QueuedOperation:
    type: OperationType
    account_id: int
    email_uid: str
    folder_name: str
    params: dict | None = None


class OperationQueue:
    """Offline operation queue with deduplication, exponential backoff, and crash recovery."""

    _instance: "OperationQueue" | None = None
    _lock: threading.Lock = threading.Lock()

    MAX_RETRY = 5
    BASE_DELAY_SEC = 5

    def __new__(cls) -> "OperationQueue":
        with cls._lock:
            if cls._instance is None:
                cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self) -> None:
        if hasattr(self, "_initialized"):
            return
        self._initialized = True
        self._network_available = True
        self._recover_interrupted()

    # ------------------------------------------------------------------
    # Crash recovery
    # ------------------------------------------------------------------
    def _recover_interrupted(self) -> None:
        """On startup, reset 'processing' ops back to 'pending' so they are retried."""
        db.execute(
            "UPDATE operation_queue SET status = 'pending' WHERE status = 'processing'"
        )
        affected = db.conn.total_changes  # approximate; good enough for logging
        if affected:
            logger.info("Recovered %d interrupted operations to pending", affected)

    # ------------------------------------------------------------------
    # Deduplication helpers
    # ------------------------------------------------------------------
    @staticmethod
    def _operation_fingerprint(op: QueuedOperation) -> tuple:
        """Return a hashable key for deduplication."""
        params_key = json.dumps(op.params or {}, sort_keys=True)
        return (op.account_id, op.type.value, op.email_uid, op.folder_name, params_key)

    def _has_pending_duplicate(self, op: QueuedOperation) -> bool:
        """Check if an identical pending operation already exists."""
        if op.type not in _IDEMPOTENT_OPS:
            return False
        row = db.fetchone(
            "SELECT 1 FROM operation_queue WHERE account_id = ? AND operation_type = ? "
            "AND email_uid = ? AND folder_name = ? AND status = 'pending' LIMIT 1",
            (op.account_id, op.type.value, op.email_uid, op.folder_name),
        )
        return row is not None

    # ------------------------------------------------------------------
    # Public enqueue API
    # ------------------------------------------------------------------
    def enqueue(self, operation: QueuedOperation) -> int | None:
        """Add an operation to the queue. Returns op_id or None if deduplicated."""
        if self._has_pending_duplicate(operation):
            logger.debug("Deduplicated %s for uid=%s", operation.type.value, operation.email_uid)
            return None

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

    def enqueue_delete(self, account_id: int, uid: str, folder: str) -> int | None:
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
    ) -> int | None:
        return self.enqueue(
            QueuedOperation(
                type=OperationType.MOVE,
                account_id=account_id,
                email_uid=uid,
                folder_name=source_folder,
                params={"dest_folder": dest_folder},
            )
        )

    def enqueue_mark_read(self, account_id: int, uid: str, folder: str) -> int | None:
        return self.enqueue(
            QueuedOperation(
                type=OperationType.MARK_READ,
                account_id=account_id,
                email_uid=uid,
                folder_name=folder,
            )
        )

    # ------------------------------------------------------------------
    # Retry backoff
    # ------------------------------------------------------------------
    @classmethod
    def _next_retry_delay(cls, retry_count: int) -> int:
        """Exponential backoff capped at ~5 minutes."""
        delay = cls.BASE_DELAY_SEC * (2 ** retry_count)
        return min(delay, 300)

    @classmethod
    def _compute_next_retry_at(cls, retry_count: int) -> str:
        delay = cls._next_retry_delay(retry_count)
        ts = time.time() + delay
        return time.strftime("%Y-%m-%dT%H:%M:%S", time.localtime(ts))

    # ------------------------------------------------------------------
    # Error categorisation
    # ------------------------------------------------------------------
    @staticmethod
    def _classify_error(exc: Exception) -> str:
        msg = str(exc).lower()
        if any(k in msg for k in ("auth", "credential", "password", "login")):
            return "auth_error"
        if any(k in msg for k in ("timeout", "timed out")):
            return "timeout_error"
        if any(k in msg for k in ("network", "unreachable", "connection refused", "dns")):
            return "network_error"
        if any(k in msg for k in ("ssl", "tls", "certificate")):
            return "ssl_error"
        return "unknown_error"

    # ------------------------------------------------------------------
    # Queue processing
    # ------------------------------------------------------------------
    def process_queue(self) -> tuple[int, int]:
        """
        Process pending operations that are due for retry.
        Returns: (success_count, fail_count)
        """
        if not self._network_available:
            return (0, 0)

        now = time.strftime("%Y-%m-%dT%H:%M:%S", time.localtime())
        pending = db.fetchall(
            "SELECT * FROM operation_queue WHERE status = 'pending' "
            "AND (next_retry_at IS NULL OR next_retry_at <= ?) "
            "ORDER BY created_at LIMIT 100",
            (now,),
        )

        success_count = 0
        fail_count = 0

        for op in pending:
            try:
                # Mark as processing
                db.update(
                    "operation_queue",
                    {"status": "processing", "last_attempt_at": now},
                    "id = ?",
                    (op["id"],),
                )

                self._execute_operation(op)

                # Success
                db.update(
                    "operation_queue",
                    {"status": "synced", "error_message": None, "error_category": None},
                    "id = ?",
                    (op["id"],),
                )
                success_count += 1
            except Exception as e:
                retry_count = (op.get("retry_count") or 0) + 1
                category = self._classify_error(e)

                if retry_count >= self.MAX_RETRY:
                    db.update(
                        "operation_queue",
                        {
                            "status": "failed",
                            "retry_count": retry_count,
                            "error_message": str(e)[:500],
                            "error_category": category,
                            "last_attempt_at": now,
                        },
                        "id = ?",
                        (op["id"],),
                    )
                    fail_count += 1
                    logger.warning(
                        "Operation %s permanently failed after %d retries: %s",
                        op["id"], retry_count, e,
                    )
                else:
                    next_retry = self._compute_next_retry_at(retry_count)
                    db.update(
                        "operation_queue",
                        {
                            "status": "pending",
                            "retry_count": retry_count,
                            "error_message": str(e)[:500],
                            "error_category": category,
                            "last_attempt_at": now,
                            "next_retry_at": next_retry,
                        },
                        "id = ?",
                        (op["id"],),
                    )

        return (success_count, fail_count)

    def _execute_operation(self, op: dict) -> None:
        """Execute a single operation."""
        account = Account.get_by_id(op["account_id"])
        if not account:
            raise ValueError(f"Account {op['account_id']} not found")

        if account.protocol == "imap":
            self._execute_imap_operation(account, op)
        elif account.protocol == "pop3":
            if op["operation_type"] == "delete":
                self._execute_pop3_delete(account, op)

    def _execute_imap_operation(self, account: Account, op: dict) -> None:
        """Execute IMAP operation, reusing the thread-local event loop."""
        import asyncio

        from openemail.core.connection_manager import connection_manager

        async def _do():
            client = await connection_manager.get_imap(account)

            op_type = op["operation_type"]
            uid = op["email_uid"]
            folder = op["folder_name"]
            params = json.loads(op["params"]) if op["params"] else {}

            if op_type == "delete":
                await client.delete_email(uid, folder)
            elif op_type == "move":
                dest_folder = params.get("dest_folder")
                if dest_folder:
                    await client.move_email(uid, folder, dest_folder)
            elif op_type == "mark_read":
                await client.mark_as_read(uid, folder)
            elif op_type == "mark_flagged":
                await client.mark_as_flagged(uid, folder)

        try:
            loop = asyncio.get_event_loop()
            if loop.is_closed():
                raise RuntimeError("closed")
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

        loop.run_until_complete(_do())

    def _execute_pop3_delete(self, account: Account, op: dict) -> None:
        """Execute POP3 delete operation."""
        from openemail.core.pop3_client import POP3Client

        client = POP3Client(account)
        if client.connect():
            # POP3 删除需要消息编号，这里简化处理
            client.disconnect()

    def set_network_available(self, available: bool) -> None:
        """Update network state and trigger processing if now online."""
        was_offline = not self._network_available
        self._network_available = available
        if available and was_offline:
            self.process_queue()

    def get_pending_count(self) -> int:
        """Return the number of pending operations (excluding future retries)."""
        now = time.strftime("%Y-%m-%dT%H:%M:%S", time.localtime())
        row = db.fetchone(
            "SELECT COUNT(*) as c FROM operation_queue WHERE status = 'pending' "
            "AND (next_retry_at IS NULL OR next_retry_at <= ?)",
            (now,),
        )
        return row["c"] if row else 0

    def get_pending_operations(self, limit: int = 50) -> list[dict]:
        """Return pending operations that are due for retry."""
        now = time.strftime("%Y-%m-%dT%H:%M:%S", time.localtime())
        return db.fetchall(
            "SELECT * FROM operation_queue WHERE status = 'pending' "
            "AND (next_retry_at IS NULL OR next_retry_at <= ?) "
            "ORDER BY created_at LIMIT ?",
            (now, limit),
        )

    def clear_completed(self) -> None:
        """Remove synced and failed operations older than 7 days."""
        db.execute(
            "DELETE FROM operation_queue WHERE status IN ('synced', 'failed') "
            "AND created_at < datetime('now', '-7 days')"
        )


operation_queue = OperationQueue()
