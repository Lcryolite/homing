from __future__ import annotations

import json
import sqlite3
import time
import threading
import queue as threading_queue
from datetime import datetime, timedelta
from enum import Enum
from dataclasses import dataclass, asdict
from typing import List, Optional, Dict, Any, Callable, Union
import logging

from openemail.storage.database import db


class OperationType(Enum):
    """离线操作类型"""

    MARK_READ = "mark_read"
    MARK_UNREAD = "mark_unread"
    MARK_FLAGGED = "mark_flagged"
    MARK_UNFLAGGED = "mark_unflagged"
    MOVE_TO_FOLDER = "move_to_folder"
    DELETE_EMAIL = "delete_email"
    SEND_EMAIL = "send_email"
    CREATE_DRAFT = "create_draft"
    UPDATE_DRAFT = "update_draft"
    DELETE_DRAFT = "delete_draft"
    CREATE_FOLDER = "create_folder"
    DELETE_FOLDER = "delete_folder"
    CREATE_LABEL = "create_label"
    DELETE_LABEL = "delete_label"
    APPLY_LABEL = "apply_label"
    REMOVE_LABEL = "remove_label"


class OperationStatus(Enum):
    """操作状态"""

    PENDING = "pending"  # 等待处理
    QUEUED = "queued"  # 已加入队列
    PROCESSING = "processing"  # 处理中
    SUCCESS = "success"  # 成功完成
    FAILED = "failed"  # 处理失败
    RETRY_ING = "retrying"  # 重试中
    CANCELLED = "cancelled"  # 已取消


class PriorityLevel(Enum):
    """优先级级别"""

    LOW = 0  # 低优先级 - 如标记已读
    NORMAL = 1  # 正常优先级 - 如移动邮件
    HIGH = 2  # 高优先级 - 如发送邮件
    CRITICAL = 3  # 关键优先级 - 如删除垃圾邮件


@dataclass
class OfflineOperation:
    """离线操作实体"""

    id: int = 0
    operation_type: str = ""
    account_id: Optional[int] = None
    data: Dict[str, Any] = None
    status: str = "pending"
    priority: int = PriorityLevel.NORMAL.value
    retry_count: int = 0
    max_retries: int = 3
    last_attempt: Optional[datetime] = None
    next_attempt: Optional[datetime] = None
    error_message: str = ""
    idempotency_key: str = ""
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None

    def __post_init__(self):
        if self.data is None:
            self.data = {}
        if self.created_at is None:
            self.created_at = datetime.now()
        if self.updated_at is None:
            self.updated_at = datetime.now()

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        result = asdict(self)

        # Exclude id when it is 0 so SQLite auto-increment works
        if result.get("id") == 0:
            del result["id"]

        # 序列化日期时间
        for field in [
            "last_attempt",
            "next_attempt",
            "created_at",
            "updated_at",
            "completed_at",
        ]:
            if result[field] is not None:
                result[field] = result[field].isoformat()

        # 确保数据字段是JSON字符串
        if isinstance(result["data"], dict):
            result["data"] = json.dumps(result["data"], ensure_ascii=False)

        return result

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> OfflineOperation:
        """从字典创建操作"""
        # Normalize sqlite3.Row to plain dict
        if not isinstance(data, dict):
            data = dict(data)

        # 解析日期时间
        for field in [
            "last_attempt",
            "next_attempt",
            "created_at",
            "updated_at",
            "completed_at",
        ]:
            if data.get(field):
                try:
                    data[field] = datetime.fromisoformat(data[field])
                except (ValueError, TypeError):
                    data[field] = None

        # 解析JSON数据
        if isinstance(data.get("data"), str):
            try:
                data["data"] = json.loads(data["data"])
            except (json.JSONDecodeError, TypeError):
                data["data"] = {}

        return cls(**data)


class OfflineQueueStats:
    """离线队列统计信息"""

    def __init__(self):
        self.total_operations = 0
        self.pending_operations = 0
        self.queued_operations = 0
        self.processing_operations = 0
        self.successful_operations = 0
        self.failed_operations = 0
        self.retrying_operations = 0
        self.cancelled_operations = 0

        # 排队时间统计
        self.avg_queue_time_seconds = 0
        self.max_queue_time_seconds = 0

        # 处理时间统计
        self.avg_process_time_seconds = 0
        self.max_process_time_seconds = 0

        # 重试统计
        self.total_retries = 0
        self.max_retries_per_operation = 0

        # 按类型统计
        self.operations_by_type: Dict[str, int] = {}
        self.success_rate_by_type: Dict[str, float] = {}

        # 按账户统计
        self.operations_by_account: Dict[int, int] = {}
        self.success_rate_by_account: Dict[int, float] = {}

        # 按优先级统计
        self.operations_by_priority: Dict[int, int] = {}

        # 性能指标
        self.operations_per_minute = 0
        self.success_rate = 0.0
        self.error_rate = 0.0

    def update_from_database(self) -> None:
        """从数据库更新统计信息"""
        try:
            # 基本计数统计
            total_query = """
                SELECT 
                    COUNT(*) as total,
                    SUM(CASE WHEN status = 'pending' THEN 1 ELSE 0 END) as pending,
                    SUM(CASE WHEN status = 'queued' THEN 1 ELSE 0 END) as queued,
                    SUM(CASE WHEN status = 'processing' THEN 1 ELSE 0 END) as processing,
                    SUM(CASE WHEN status = 'success' THEN 1 ELSE 0 END) as success,
                    SUM(CASE WHEN status = 'failed' THEN 1 ELSE 0 END) as failed,
                    SUM(CASE WHEN status = 'retrying' THEN 1 ELSE 0 END) as retrying,
                    SUM(CASE WHEN status = 'cancelled' THEN 1 ELSE 0 END) as cancelled,
                    SUM(retry_count) as total_retries,
                    MAX(retry_count) as max_retries
                FROM offline_operations
            """

            row = db.fetchone(total_query)
            if row:
                self.total_operations = row["total"] or 0
                self.pending_operations = row["pending"] or 0
                self.queued_operations = row["queued"] or 0
                self.processing_operations = row["processing"] or 0
                self.successful_operations = row["success"] or 0
                self.failed_operations = row["failed"] or 0
                self.retrying_operations = row["retrying"] or 0
                self.cancelled_operations = row["cancelled"] or 0
                self.total_retries = row["total_retries"] or 0
                self.max_retries_per_operation = row["max_retries"] or 0

            # 成功率计算
            if self.total_operations > 0:
                self.success_rate = (
                    self.successful_operations / self.total_operations
                ) * 100
                self.error_rate = (
                    (self.failed_operations + self.cancelled_operations)
                    / self.total_operations
                ) * 100

            # 按类型统计
            type_query = """
                SELECT operation_type, 
                       COUNT(*) as count,
                       SUM(CASE WHEN status = 'success' THEN 1 ELSE 0 END) as success_count
                FROM offline_operations
                GROUP BY operation_type
            """

            rows = db.fetchall(type_query)
            self.operations_by_type.clear()
            self.success_rate_by_type.clear()

            for row in rows:
                op_type = row["operation_type"]
                count = row["count"]
                success_count = row["success_count"] or 0

                self.operations_by_type[op_type] = count
                if count > 0:
                    self.success_rate_by_type[op_type] = (success_count / count) * 100

            # 按账户统计
            account_query = """
                SELECT account_id,
                       COUNT(*) as count,
                       SUM(CASE WHEN status = 'success' THEN 1 ELSE 0 END) as success_count
                FROM offline_operations
                WHERE account_id IS NOT NULL
                GROUP BY account_id
            """

            rows = db.fetchall(account_query)
            self.operations_by_account.clear()
            self.success_rate_by_account.clear()

            for row in rows:
                account_id = int(row["account_id"])
                count = row["count"]
                success_count = row["success_count"] or 0

                self.operations_by_account[account_id] = count
                if count > 0:
                    self.success_rate_by_account[account_id] = (
                        success_count / count
                    ) * 100

            # 按优先级统计
            priority_query = """
                SELECT priority, COUNT(*) as count
                FROM offline_operations
                GROUP BY priority
                ORDER BY priority
            """

            rows = db.fetchall(priority_query)
            self.operations_by_priority.clear()

            for row in rows:
                priority = row["priority"]
                count = row["count"]
                self.operations_by_priority[priority] = count

            # 时间统计
            time_query = """
                SELECT 
                    AVG(julianday(completed_at) - julianday(created_at)) * 86400 as avg_queue_time,
                    MAX(julianday(completed_at) - julianday(created_at)) * 86400 as max_queue_time
                FROM offline_operations
                WHERE status = 'success' AND completed_at IS NOT NULL
            """

            row = db.fetchone(time_query)
            if row:
                self.avg_queue_time_seconds = row["avg_queue_time"] or 0
                self.max_queue_time_seconds = row["max_queue_time"] or 0

            # 最近性能统计（过去1小时）
            recent_query = """
                SELECT 
                    COUNT(*) as recent_count,
                    SUM(CASE WHEN status = 'success' THEN 1 ELSE 0 END) as recent_success
                FROM offline_operations
                WHERE created_at >= datetime('now', '-1 hour')
            """

            row = db.fetchone(recent_query)
            if row:
                recent_count = row["recent_count"] or 0
                self.operations_per_minute = recent_count / 60  # 转换为每分钟

        except Exception as e:
            logging.error(f"更新统计信息时出错: {e}")

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "total_operations": self.total_operations,
            "pending_operations": self.pending_operations,
            "queued_operations": self.queued_operations,
            "processing_operations": self.processing_operations,
            "successful_operations": self.successful_operations,
            "failed_operations": self.failed_operations,
            "retrying_operations": self.retrying_operations,
            "cancelled_operations": self.cancelled_operations,
            "avg_queue_time_seconds": self.avg_queue_time_seconds,
            "max_queue_time_seconds": self.max_queue_time_seconds,
            "total_retries": self.total_retries,
            "max_retries_per_operation": self.max_retries_per_operation,
            "operations_by_type": self.operations_by_type,
            "success_rate_by_type": self.success_rate_by_type,
            "operations_by_account": self.operations_by_account,
            "success_rate_by_account": self.success_rate_by_account,
            "operations_by_priority": self.operations_by_priority,
            "operations_per_minute": self.operations_per_minute,
            "success_rate": self.success_rate,
            "error_rate": self.error_rate,
        }

    def get_summary(self) -> str:
        """获取统计摘要"""
        return (
            f"离线队列统计:\n"
            f"  总计: {self.total_operations} 个操作\n"
            f"  待处理: {self.pending_operations}, 已排队: {self.queued_operations}, 处理中: {self.processing_operations}\n"
            f"  成功: {self.successful_operations}, 失败: {self.failed_operations}, 重试中: {self.retrying_operations}, 已取消: {self.cancelled_operations}\n"
            f"  成功率: {self.success_rate:.1f}%, 错误率: {self.error_rate:.1f}%\n"
            f"  平均排队时间: {self.avg_queue_time_seconds:.1f}秒\n"
            f"  每分钟处理: {self.operations_per_minute:.1f}个操作"
        )


class OfflineQueue:
    """离线操作队列管理器"""

    def __init__(self):
        self._queue: threading_queue.PriorityQueue = threading_queue.PriorityQueue()
        self._processing_lock = threading.Lock()
        self._stats = OfflineQueueStats()
        self._running = False
        self._worker_threads: List[threading.Thread] = []
        self._max_workers = 3
        self._retry_intervals = [60, 300, 900, 3600]  # 重试间隔（秒）

        # 回调函数
        self._operation_callbacks: Dict[str, Callable] = {}

        # 初始化数据库表
        self._init_database()

        # 加载待处理操作到内存队列
        self._load_pending_operations()

    def _init_database(self) -> None:
        """初始化数据库表"""
        try:
            db.execute("""
                CREATE TABLE IF NOT EXISTS offline_operations (
                    id              INTEGER PRIMARY KEY,
                    operation_type  TEXT NOT NULL,
                    account_id      INTEGER,
                    data            TEXT NOT NULL DEFAULT '{}',
                    status          TEXT NOT NULL DEFAULT 'pending',
                    priority        INTEGER NOT NULL DEFAULT 1,
                    retry_count     INTEGER NOT NULL DEFAULT 0,
                    max_retries     INTEGER NOT NULL DEFAULT 3,
                    last_attempt    TEXT,
                    next_attempt    TEXT,
                    error_message   TEXT DEFAULT '',
                    idempotency_key TEXT,
                    created_at      TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    updated_at      TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    completed_at    TEXT
                )
            """)

            # Migrate: add idempotency_key if missing (pre-v0.6.0 schema)
            try:
                db.execute("ALTER TABLE offline_operations ADD COLUMN idempotency_key TEXT")
            except sqlite3.OperationalError:
                pass  # Column already exists

            # Create unique index for idempotency
            db.execute("""
                CREATE UNIQUE INDEX IF NOT EXISTS idx_offline_ops_idempotency
                ON offline_operations(idempotency_key)
                WHERE idempotency_key IS NOT NULL
            """)

            # 创建索引
            db.execute("""
                CREATE INDEX IF NOT EXISTS idx_offline_ops_status
                ON offline_operations(status, priority)
            """)
            db.execute("""
                CREATE INDEX IF NOT EXISTS idx_offline_ops_account
                ON offline_operations(account_id, status)
            """)
            db.execute("""
                CREATE INDEX IF NOT EXISTS idx_offline_ops_retry
                ON offline_operations(next_attempt, retry_count)
            """)

            logging.info("离线队列数据库表初始化完成")

        except sqlite3.Error as e:
            logging.error(f"初始化离线队列数据库时出错: {e}")

    def _load_pending_operations(self) -> None:
        """加载待处理操作到内存队列"""
        try:
            # 获取所有待处理、排队和等待重试的操作
            now = datetime.now().isoformat()
            sql = """
                SELECT * FROM offline_operations
                WHERE status IN ('pending', 'queued', 'retrying')
                  AND (next_attempt IS NULL OR next_attempt <= ?)
                ORDER BY priority DESC, created_at ASC
                LIMIT 1000
            """

            rows = db.fetchall(sql, (now,))

            for row in rows:
                operation = OfflineOperation.from_dict(row)

                # 使用负优先级创建优先队列（Python优先队列是最小堆）
                priority_score = -operation.priority * 1000 + operation.id
                self._queue.put((priority_score, operation))

                # 更新状态为排队
                if operation.status != OperationStatus.QUEUED.value:
                    db.update(
                        "offline_operations",
                        {"status": OperationStatus.QUEUED.value, "updated_at": now},
                        "id = ?",
                        (operation.id,),
                    )

            logging.info(f"从数据库加载了 {len(rows)} 个操作到内存队列")

        except Exception as e:
            logging.error(f"加载待处理操作时出错: {e}")

    def register_operation_handler(
        self, operation_type: Union[str, OperationType], handler: Callable
    ) -> None:
        """注册操作处理器"""
        if isinstance(operation_type, OperationType):
            type_str = operation_type.value
        else:
            type_str = operation_type

        self._operation_callbacks[type_str] = handler
        logging.info(f"注册了 {type_str} 操作处理器")

    def add_operation(self, operation: OfflineOperation) -> int:
        """添加操作到队列"""
        try:
            # Idempotency check: skip if same key already pending/queued/processing
            if operation.idempotency_key:
                row = db.fetchone(
                    "SELECT id FROM offline_operations WHERE idempotency_key = ? AND status IN ('pending', 'queued', 'processing', 'retrying')",
                    (operation.idempotency_key,),
                )
                if row:
                    logging.info(
                        "Idempotent skip: %s already in queue (ID=%d)",
                        operation.idempotency_key,
                        row["id"],
                    )
                    return row["id"]

            # 保存到数据库
            operation_dict = operation.to_dict()
            operation_id = db.insert("offline_operations", operation_dict)

            if operation_id:
                operation.id = operation_id

                # 添加到内存队列
                priority_score = -operation.priority * 1000 + operation_id
                self._queue.put((priority_score, operation))

                # 更新状态
                db.update(
                    "offline_operations",
                    {
                        "status": OperationStatus.QUEUED.value,
                        "updated_at": datetime.now().isoformat(),
                    },
                    "id = ?",
                    (operation_id,),
                )

                logging.info(
                    f"添加操作到队列: {operation.operation_type} (ID: {operation_id})"
                )
                return operation_id

            return 0

        except Exception as e:
            logging.error(f"添加操作到队列时出错: {e}")
            return 0

    def create_mark_read_operation(self, email_ids: List[int], account_id: int) -> int:
        """创建标记已读操作"""
        operation = OfflineOperation(
            operation_type=OperationType.MARK_READ.value,
            account_id=account_id,
            data={"email_ids": email_ids},
            priority=PriorityLevel.LOW.value,
        )

        return self.add_operation(operation)

    def create_mark_unread_operation(
        self, email_ids: List[int], account_id: int
    ) -> int:
        """创建标记未读操作"""
        operation = OfflineOperation(
            operation_type=OperationType.MARK_UNREAD.value,
            account_id=account_id,
            data={"email_ids": email_ids},
            priority=PriorityLevel.LOW.value,
        )

        return self.add_operation(operation)

    def create_move_operation(
        self, email_ids: List[int], target_folder_id: int, account_id: int
    ) -> int:
        """创建移动邮件操作"""
        operation = OfflineOperation(
            operation_type=OperationType.MOVE_TO_FOLDER.value,
            account_id=account_id,
            data={"email_ids": email_ids, "target_folder_id": target_folder_id},
            priority=PriorityLevel.NORMAL.value,
        )

        return self.add_operation(operation)

    def create_delete_operation(
        self, email_ids: List[int], account_id: int, permanent: bool = False
    ) -> int:
        """创建删除邮件操作"""
        operation = OfflineOperation(
            operation_type=OperationType.DELETE_EMAIL.value,
            account_id=account_id,
            data={"email_ids": email_ids, "permanent": permanent},
            priority=PriorityLevel.HIGH.value,
        )

        return self.add_operation(operation)

    def create_send_email_operation(
        self, draft_data: Dict[str, Any], account_id: int
    ) -> int:
        """创建发送邮件操作"""
        operation = OfflineOperation(
            operation_type=OperationType.SEND_EMAIL.value,
            account_id=account_id,
            data={"draft": draft_data},
            priority=PriorityLevel.CRITICAL.value,
            max_retries=5,  # 发送邮件允许更多重试
        )

        return self.add_operation(operation)

    @staticmethod
    def _is_retryable_error(error_msg: str) -> bool:
        """判断错误是否值得重试。"""
        if not error_msg:
            return True
        non_retryable = [
            "auth failed",
            "authentication failed",
            "invalid credentials",
            "permission denied",
            "bad request",
            "validation error",
            "not found",
            "does not exist",
        ]
        lowered = error_msg.lower()
        return not any(nr in lowered for nr in non_retryable)

    def _process_operation(self, operation: OfflineOperation) -> bool:
        """处理单个操作"""
        operation_id = operation.id
        operation_type = operation.operation_type

        try:
            # 更新状态为处理中
            now = datetime.now().isoformat()
            db.update(
                "offline_operations",
                {
                    "status": OperationStatus.PROCESSING.value,
                    "last_attempt": now,
                    "updated_at": now,
                    "retry_count": operation.retry_count + 1,
                },
                "id = ?",
                (operation_id,),
            )

            # 查找处理器
            handler = self._operation_callbacks.get(operation_type)
            if not handler:
                raise ValueError(f"未找到 {operation_type} 操作的处理器")

            # 执行操作
            success = handler(operation.data, operation.account_id)

            if success:
                # 标记为成功
                db.update(
                    "offline_operations",
                    {
                        "status": OperationStatus.SUCCESS.value,
                        "completed_at": datetime.now().isoformat(),
                        "updated_at": datetime.now().isoformat(),
                    },
                    "id = ?",
                    (operation_id,),
                )
                logging.info(f"操作处理成功: {operation_type} (ID: {operation_id})")
                return True
            else:
                raise Exception("处理器返回失败")

        except Exception as e:
            error_msg = str(e)
            logging.error(
                f"处理操作失败: {operation_type} (ID: {operation_id}): {error_msg}"
            )

            # 处理失败，检查是否需要重试
            operation.retry_count += 1

            retryable = self._is_retryable_error(error_msg)
            if retryable and operation.retry_count < operation.max_retries:
                # 计算下次重试时间
                retry_index = min(
                    operation.retry_count - 1, len(self._retry_intervals) - 1
                )
                retry_seconds = self._retry_intervals[retry_index]
                next_attempt = datetime.now() + timedelta(seconds=retry_seconds)

                db.update(
                    "offline_operations",
                    {
                        "status": OperationStatus.RETRY_ING.value,
                        "next_attempt": next_attempt.isoformat(),
                        "error_message": error_msg,
                        "retry_count": operation.retry_count,
                        "updated_at": datetime.now().isoformat(),
                    },
                    "id = ?",
                    (operation_id,),
                )

                logging.info(
                    f"操作计划重试: {operation_type} (ID: {operation_id})，第 {operation.retry_count} 次重试"
                )

            else:
                # 重试次数用完或错误不可重试，标记为失败
                db.update(
                    "offline_operations",
                    {
                        "status": OperationStatus.FAILED.value,
                        "completed_at": datetime.now().isoformat(),
                        "error_message": error_msg,
                        "updated_at": datetime.now().isoformat(),
                    },
                    "id = ?",
                    (operation_id,),
                )

                if not retryable:
                    logging.error(
                        f"操作失败（不可重试错误）: {operation_type} (ID: {operation_id}): {error_msg}"
                    )
                else:
                    logging.error(
                        f"操作最终失败，重试次数用完: {operation_type} (ID: {operation_id})"
                    )

            return False

    def _worker_function(self, worker_id: int) -> None:
        """工作线程函数"""
        logging.info(f"离线队列工作线程 {worker_id} 启动")

        while self._running:
            try:
                # 从队列获取操作（带超时）
                priority_score, operation = self._queue.get(timeout=1)

                if operation:
                    # 处理操作
                    self._process_operation(operation)

                    # 标记任务完成
                    self._queue.task_done()

            except threading_queue.Empty:
                # 队列为空，继续循环
                continue
            except Exception as e:
                logging.error(f"工作线程 {worker_id} 出错: {e}")
                time.sleep(1)  # 出错时短暂休眠

    def start_workers(self, num_workers: Optional[int] = None) -> None:
        """启动工作线程"""
        if self._running:
            logging.warning("工作线程已经在运行")
            return

        self._running = True

        if num_workers is None:
            num_workers = self._max_workers
        else:
            num_workers = min(num_workers, 10)  # 限制最大线程数

        # 创建工作线程
        for i in range(num_workers):
            worker = threading.Thread(
                target=self._worker_function,
                args=(i,),
                daemon=True,
                name=f"OfflineQueueWorker-{i}",
            )
            worker.start()
            self._worker_threads.append(worker)

        logging.info(f"启动了 {num_workers} 个离线队列工作线程")

    def stop_workers(self) -> None:
        """停止工作线程"""
        self._running = False

        # 等待线程结束
        for worker in self._worker_threads:
            if worker.is_alive():
                worker.join(timeout=5)

        self._worker_threads.clear()
        logging.info("离线队列工作线程已停止")

    def get_queue_stats(self) -> OfflineQueueStats:
        """获取队列统计信息"""
        self._stats.update_from_database()
        return self._stats

    def get_pending_operations(self, limit: int = 100) -> List[OfflineOperation]:
        """获取待处理操作列表"""
        try:
            now = datetime.now().isoformat()
            sql = """
                SELECT * FROM offline_operations
                WHERE status IN ('pending', 'queued', 'retrying')
                  AND (next_attempt IS NULL OR next_attempt <= ?)
                ORDER BY priority DESC, created_at ASC
                LIMIT ?
            """

            rows = db.fetchall(sql, (now, limit))
            return [OfflineOperation.from_dict(r) for r in rows]

        except Exception as e:
            logging.error(f"获取待处理操作时出错: {e}")
            return []

    def recover_interrupted_operations(self) -> int:
        """Recover operations left in 'processing' state (e.g., after crash).

        Also resets 'retrying' operations whose next_attempt time has passed,
        as they may have been stuck by a crash.

        Returns:
            Number of operations reset to pending.
        """
        try:
            now = datetime.now().isoformat()
            # Reset processing (interrupted mid-flight)
            cur1 = db.execute(
                """
                UPDATE offline_operations
                SET status = ?, updated_at = ?, next_attempt = ?
                WHERE status = ?
                """,
                (OperationStatus.PENDING.value, now, now, OperationStatus.PROCESSING.value),
            )
            # Reset retrying that are past their scheduled time (clock may have changed / crash)
            cur2 = db.execute(
                """
                UPDATE offline_operations
                SET status = ?, updated_at = ?, next_attempt = ?
                WHERE status = ? AND next_attempt <= ?
                """,
                (OperationStatus.PENDING.value, now, now, OperationStatus.RETRY_ING.value, now),
            )
            rowcount = (cur1.rowcount or 0) + (cur2.rowcount or 0)
            if rowcount > 0:
                logging.info("Recovered %d interrupted operations to pending", rowcount)
            return rowcount
        except Exception as e:
            logging.error("Recover interrupted operations failed: %s", e)
            return 0

    def get_failed_operations(self, limit: int = 100) -> List[OfflineOperation]:
        """获取失败操作列表"""
        try:
            sql = """
                SELECT * FROM offline_operations
                WHERE status = 'failed'
                ORDER BY last_attempt DESC
                LIMIT ?
            """

            rows = db.fetchall(sql, (limit,))
            return [OfflineOperation.from_dict(r) for r in rows]

        except Exception as e:
            logging.error(f"获取失败操作时出错: {e}")
            return []

    def retry_failed_operation(self, operation_id: int) -> bool:
        """重试失败的操作"""
        try:
            operation = OfflineQueue.get_by_id(operation_id)
            if not operation:
                return False

            operation.status = OperationStatus.PENDING.value
            operation.next_attempt = None
            operation.error_message = ""
            operation.updated_at = datetime.now()

            now = datetime.now().isoformat()
            db.update(
                "offline_operations",
                {
                    "status": OperationStatus.PENDING.value,
                    "next_attempt": None,
                    "error_message": "",
                    "updated_at": now,
                },
                "id = ?",
                (operation_id,),
            )
            self._queue_operation(operation)

            logging.info(
                f"已重试操作: ID={operation_id}, Type={operation.operation_type}"
            )
            return True

        except Exception as e:
            logging.error(f"重试操作时出错: ID={operation_id}, Error={e}")
            return False

    def cancel_operation(self, operation_id: int) -> bool:
        """取消操作"""
        try:
            db.update(
                "offline_operations",
                {
                    "status": OperationStatus.CANCELLED.value,
                    "completed_at": datetime.now().isoformat(),
                    "updated_at": datetime.now().isoformat(),
                },
                "id = ? AND status IN ('pending', 'queued', 'retrying')",
                (operation_id,),
            )

            logging.info(f"已取消操作: ID={operation_id}")
            return True

        except Exception as e:
            logging.error(f"取消操作时出错: ID={operation_id}, Error={e}")
            return False

    def clear_completed_operations(self, older_than_days: int = 7) -> int:
        """清理已完成的操作（保留指定天数）"""
        try:
            cutoff_date = (datetime.now() - timedelta(days=older_than_days)).isoformat()

            sql = """
                DELETE FROM offline_operations
                WHERE status IN ('success', 'failed', 'cancelled')
                  AND completed_at < ?
            """

            result = db.execute(sql, (cutoff_date,))
            count = result.rowcount if result else 0

            logging.info(f"清理了 {count} 个已完成的操作（早于 {cutoff_date}）")
            return count

        except Exception as e:
            logging.error(f"清理操作时出错: {e}")
            return 0

    def _queue_operation(self, operation: OfflineOperation) -> None:
        """将操作添加到内存队列"""
        priority_score = -operation.priority * 1000 + operation.id
        self._queue.put((priority_score, operation))

    @classmethod
    def get_by_id(cls, operation_id: int) -> Optional[OfflineOperation]:
        """根据ID获取操作"""
        try:
            sql = "SELECT * FROM offline_operations WHERE id = ?"
            row = db.fetchone(sql, (operation_id,))

            if row:
                return OfflineOperation.from_dict(row)
            return None

        except Exception as e:
            logging.error(f"获取操作时出错: ID={operation_id}, Error={e}")
            return None


# 单例实例
_offline_queue_instance: Optional[OfflineQueue] = None


def get_offline_queue() -> OfflineQueue:
    """获取离线队列实例"""
    global _offline_queue_instance

    if _offline_queue_instance is None:
        _offline_queue_instance = OfflineQueue()

    return _offline_queue_instance


# 默认操作处理器（需要应用程序注册实际的处理器）
def default_mark_read_handler(data: Dict[str, Any], account_id: int) -> bool:
    """默认标记已读处理器"""
    try:
        email_ids = data.get("email_ids", [])
        if not email_ids:
            return True

        from openemail.storage.database import db

        db.update_safe("emails", {"is_read": 1}, {"id": email_ids})
        logging.info(f"批量标记 {len(email_ids)} 封邮件为已读")
        return True

    except Exception as e:
        logging.error(f"标记已读失败: {e}")
        return False


def default_move_handler(data: Dict[str, Any], account_id: int) -> bool:
    """默认移动邮件处理器"""
    try:
        email_ids = data.get("email_ids", [])
        target_folder_id = data.get("target_folder_id")

        if not email_ids or not target_folder_id:
            return False

        from openemail.storage.database import db

        db.update_safe("emails", {"folder_id": target_folder_id}, {"id": email_ids})
        logging.info(f"批量移动 {len(email_ids)} 封邮件到文件夹 {target_folder_id}")
        return True

    except Exception as e:
        logging.error(f"移动邮件失败: {e}")
        return False


def init_default_handlers(queue: OfflineQueue) -> None:
    """初始化默认处理器"""
    # 注册默认处理器
    queue.register_operation_handler(OperationType.MARK_READ, default_mark_read_handler)
    queue.register_operation_handler(
        OperationType.MARK_UNREAD, default_mark_read_handler
    )  # 暂时使用相同处理器
    queue.register_operation_handler(OperationType.MOVE_TO_FOLDER, default_move_handler)

    # TODO: 注册其他操作的默认处理器

    logging.info("离线队列默认处理器已注册")


# 自动初始化
if __name__ == "__main__":
    # 配置日志
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )

    # 创建队列并启动（仅在直接运行时）
    queue = get_offline_queue()
    init_default_handlers(queue)
    queue.start_workers()
