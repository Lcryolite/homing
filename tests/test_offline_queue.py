"""Tests for offline queue idempotency, retry policy, and crash recovery."""

from __future__ import annotations

import pytest

from openemail.queue.offline_queue import (
    OfflineOperation,
    OfflineQueue,
    OperationStatus,
    OperationType,
    PriorityLevel,
)
from openemail.storage.database import Database


@pytest.fixture
def queue(temp_db: Database) -> OfflineQueue:
    """Fresh OfflineQueue instance bound to the temp database."""
    # The queue auto-creates its table on init.
    q = OfflineQueue()
    # Stop any background workers so they don't interfere with tests.
    q._running = False
    return q


class TestIdempotency:
    def test_duplicate_key_skipped(self, queue: OfflineQueue) -> None:
        op1 = OfflineOperation(
            operation_type=OperationType.MARK_READ.value,
            account_id=1,
            data={"email_ids": [1]},
            idempotency_key="mark-read-1",
            priority=PriorityLevel.LOW.value,
        )
        id1 = queue.add_operation(op1)
        assert id1 > 0

        op2 = OfflineOperation(
            operation_type=OperationType.MARK_READ.value,
            account_id=1,
            data={"email_ids": [2]},
            idempotency_key="mark-read-1",
            priority=PriorityLevel.LOW.value,
        )
        id2 = queue.add_operation(op2)
        assert id2 == id1  # skipped

    def test_new_key_allowed(self, queue: OfflineQueue) -> None:
        op1 = OfflineOperation(
            operation_type=OperationType.MARK_READ.value,
            account_id=1,
            data={"email_ids": [1]},
            idempotency_key="key-a",
        )
        id1 = queue.add_operation(op1)

        op2 = OfflineOperation(
            operation_type=OperationType.MARK_READ.value,
            account_id=1,
            data={"email_ids": [1]},
            idempotency_key="key-b",
        )
        id2 = queue.add_operation(op2)
        assert id2 != id1

    def test_empty_key_no_dedup(self, queue: OfflineQueue) -> None:
        op1 = OfflineOperation(
            operation_type=OperationType.MARK_READ.value,
            account_id=1,
            data={"email_ids": [1]},
            idempotency_key="",
        )
        id1 = queue.add_operation(op1)
        id2 = queue.add_operation(op1)
        assert id2 != id1


class TestRetryPolicy:
    def test_retryable_error_increments_retry_count(self, queue: OfflineQueue) -> None:
        op = OfflineOperation(
            operation_type=OperationType.MARK_READ.value,
            account_id=1,
            data={"email_ids": [1]},
            max_retries=3,
        )
        op_id = queue.add_operation(op)
        op.id = op_id

        # Simulate a retryable failure
        success = queue._process_operation(op)
        assert success is False

        updated = queue.get_by_id(op_id)
        assert updated is not None
        assert updated.status in (OperationStatus.RETRY_ING.value, OperationStatus.FAILED.value)
        assert updated.retry_count > 0

    def test_non_retryable_error_fails_immediately(self, queue: OfflineQueue) -> None:
        op = OfflineOperation(
            operation_type=OperationType.SEND_EMAIL.value,
            account_id=1,
            data={"draft": {}},
            max_retries=5,
        )
        op_id = queue.add_operation(op)
        op.id = op_id

        # Patch handler to raise an auth error (non-retryable)
        queue.register_operation_handler(
            OperationType.SEND_EMAIL.value,
            lambda data, account_id: (_ for _ in ()).throw(
                Exception("Authentication failed: invalid credentials")
            ),
        )

        success = queue._process_operation(op)
        assert success is False

        updated = queue.get_by_id(op_id)
        assert updated is not None
        assert updated.status == OperationStatus.FAILED.value
        assert updated.retry_count == 1  # incremented once, then stopped


class TestCrashRecovery:
    def test_processing_reset_to_pending(self, queue: OfflineQueue) -> None:
        # Insert a row directly with processing status
        from openemail.storage.database import db

        db.execute(
            """
            INSERT INTO offline_operations (operation_type, account_id, data, status, priority)
            VALUES (?, ?, ?, ?, ?)
            """,
            (OperationType.MOVE_TO_FOLDER.value, 1, "{}", OperationStatus.PROCESSING.value, 1),
        )

        count = queue.recover_interrupted_operations()
        assert count > 0

        rows = db.fetchall(
            "SELECT status FROM offline_operations WHERE status = ?",
            (OperationStatus.PENDING.value,),
        )
        assert len(rows) == count

    def test_success_not_modified(self, queue: OfflineQueue) -> None:
        from openemail.storage.database import db

        db.execute(
            """
            INSERT INTO offline_operations (operation_type, account_id, data, status, priority)
            VALUES (?, ?, ?, ?, ?)
            """,
            (OperationType.MARK_READ.value, 1, "{}", OperationStatus.SUCCESS.value, 1),
        )

        count = queue.recover_interrupted_operations()
        assert count == 0


class TestIsRetryableError:
    def test_network_errors_are_retryable(self) -> None:
        assert OfflineQueue._is_retryable_error("Connection timeout") is True
        assert OfflineQueue._is_retryable_error("DNS resolution failed") is True

    def test_auth_errors_are_not_retryable(self) -> None:
        assert OfflineQueue._is_retryable_error("Authentication failed") is False
        assert OfflineQueue._is_retryable_error("Invalid credentials") is False
        assert OfflineQueue._is_retryable_error("Permission denied") is False

    def test_empty_error_is_retryable(self) -> None:
        assert OfflineQueue._is_retryable_error("") is True
