import logging
import re
import sqlite3
from typing import Any, Dict

from openemail.config import settings
from openemail.storage.migrations import SCHEMA_VERSION, MIGRATIONS
from openemail.utils.exceptions import safe_execute

logger = logging.getLogger(__name__)


class Database:
    _instance: "Database | None" = None

    def __new__(cls) -> "Database":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self) -> None:
        if hasattr(self, "_conn"):
            return
        self._db_path = settings.db_path
        self._conn: sqlite3.Connection | None = None

    @safe_execute(default_value=None, log_exception=True)
    def connect(self):
        if self._conn is not None:
            return self._conn
        self._conn = sqlite3.connect(str(self._db_path), check_same_thread=False)
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute("PRAGMA foreign_keys=ON")
        self._conn.row_factory = sqlite3.Row
        self._migrate()
        return self._conn

    def close(self) -> None:
        if self._conn is not None:
            self._conn.close()
            self._conn = None

    @property
    def conn(self) -> sqlite3.Connection:
        if self._conn is None:
            self.connect()
        assert self._conn is not None
        return self._conn

    def _migrate(self) -> None:
        import shutil

        assert self._conn is not None
        cur = self._conn.cursor()
        cur.execute(
            "CREATE TABLE IF NOT EXISTS schema_version (version INTEGER PRIMARY KEY)"
        )
        cur.execute("SELECT MAX(version) FROM schema_version")
        row = cur.fetchone()
        current = row[0] if row and row[0] is not None else 0

        logger.info("数据库当前版本: %d, 目标版本: %d", current, SCHEMA_VERSION)

        for version in range(current + 1, SCHEMA_VERSION + 1):
            statements = MIGRATIONS.get(version, [])
            if not statements:
                logger.debug("版本 %d: 无迁移语句", version)
                continue

            # 迁移前备份
            backup_path = str(self._db_path) + f".pre-v{version}.bak"
            try:
                self._conn.close()
                shutil.copy2(str(self._db_path), backup_path)
                self._conn = sqlite3.connect(
                    str(self._db_path), check_same_thread=False
                )
                self._conn.execute("PRAGMA journal_mode=WAL")
                self._conn.execute("PRAGMA foreign_keys=ON")
                self._conn.row_factory = sqlite3.Row
                cur = self._conn.cursor()
            except OSError as e:
                logger.error("备份数据库失败 (v%d): %s", version, e)
                raise

            logger.info("执行版本 %d 迁移... (备份: %s)", version, backup_path)
            migration_ok = True
            try:
                for stmt in statements:
                    try:
                        cur.execute(stmt)
                    except sqlite3.OperationalError as e:
                        if "duplicate column name" in str(e) or "already exists" in str(
                            e
                        ):
                            logger.debug("跳过已存在的操作: %s...", stmt[:60])
                        else:
                            logger.error("迁移 v%d 错误: %s", version, e)
                            migration_ok = False
                            break
                if migration_ok:
                    self._conn.commit()
                else:
                    self._conn.rollback()
            except Exception as e:
                logger.error("迁移 v%d 异常: %s", version, e)
                self._conn.rollback()
                migration_ok = False

            if not migration_ok:
                # 恢复备份
                logger.warning("迁移 v%d 失败，正在恢复备份...", version)
                self._conn.close()
                shutil.copy2(backup_path, str(self._db_path))
                self._conn = sqlite3.connect(
                    str(self._db_path), check_same_thread=False
                )
                self._conn.execute("PRAGMA journal_mode=WAL")
                self._conn.execute("PRAGMA foreign_keys=ON")
                self._conn.row_factory = sqlite3.Row
                raise RuntimeError(f"Migration v{version} failed, restored from backup")

            cur.execute(
                "INSERT OR REPLACE INTO schema_version (version) VALUES (?)", (version,)
            )
            self._conn.commit()
            logger.info("版本 %d 迁移完成", version)
            # 迁移成功后删除备份
            try:
                import os

                os.unlink(backup_path)
            except OSError:
                pass

    def execute(self, sql: str, params: tuple = ()) -> sqlite3.Cursor:
        return self.conn.execute(sql, params)

    def executemany(self, sql: str, params_seq: list[tuple]) -> sqlite3.Cursor:
        return self.conn.executemany(sql, params_seq)

    def commit(self) -> None:
        self.conn.commit()

    def rollback(self) -> None:
        self.conn.rollback()

    def rollback_to_version(self, target_version: int) -> None:
        """Rollback migrations from current version down to target_version.
        Only works for versions with ROLLBACKS entries (v8+)."""
        from openemail.storage.migrations import ROLLBACKS

        cur = self.conn.cursor()
        cur.execute("SELECT MAX(version) FROM schema_version")
        row = cur.fetchone()
        current = row[0] if row and row[0] is not None else 0

        if target_version >= current:
            logger.info("当前版本 %d <= 目标 %d，无需回滚", current, target_version)
            return

        for version in range(current, target_version, -1):
            rollback_stmts = ROLLBACKS.get(version)
            if not rollback_stmts:
                logger.warning("版本 %d 无回滚语句，跳过", version)
                continue

            logger.info("回滚版本 %d...", version)
            for stmt in rollback_stmts:
                try:
                    cur.execute(stmt)
                except sqlite3.OperationalError as e:
                    logger.warning("回滚 v%d 语句失败 (可能已不存在): %s", version, e)

            cur.execute("DELETE FROM schema_version WHERE version = ?", (version,))
            self._conn.commit()
            logger.info("版本 %d 回滚完成", version)

    def fetchone(self, sql: str, params: tuple = ()) -> sqlite3.Row | None:
        cur = self.execute(sql, params)
        return cur.fetchone()

    def fetchall(self, sql: str, params: tuple = ()) -> list[sqlite3.Row]:
        cur = self.execute(sql, params)
        return cur.fetchall()

    def insert(self, table: str, data: dict) -> int:
        """Auto-commit insert for backward compatibility.

        For multi-statement atomicity, use transaction() + execute().
        """
        columns = ", ".join(f'"{k}"' for k in data.keys())
        placeholders = ", ".join("?" for _ in data)
        sql = f"INSERT INTO {table} ({columns}) VALUES ({placeholders})"
        cur = self.execute(sql, tuple(data.values()))
        self.commit()
        return cur.lastrowid

    def update(
        self, table: str, data: dict, where: str, where_params: tuple = ()
    ) -> int:
        """Auto-commit update for backward compatibility.

        For multi-statement atomicity, use transaction() + execute().
        """
        # 添加SQL注入验证（向后兼容）
        self._validate_sql_injection(where)
        self._validate_identifier(table)
        for field in data.keys():
            self._validate_identifier(field)

        set_clause = ", ".join(f'"{k}" = ?' for k in data)
        sql = f"UPDATE {table} SET {set_clause} WHERE {where}"
        cur = self.execute(sql, tuple(data.values()) + where_params)
        self.commit()
        return cur.rowcount

    def delete(self, table: str, where: str, params: tuple = ()) -> int:
        """Auto-commit delete for backward compatibility.

        For multi-statement atomicity, use transaction() + execute().
        """
        self._validate_sql_injection(where)
        sql = f"DELETE FROM {table} WHERE {where}"
        cur = self.execute(sql, params)
        self.commit()
        return cur.rowcount

    # --- 事务支持 ---

    def transaction(self):
        """返回一个事务上下文管理器，支持多语句原子提交/回滚。

        Usage:
            with db.transaction():
                db.execute("INSERT INTO ...", (...))
                db.execute("UPDATE ...", (...))
                # commits on successful exit, rolls back on exception
        """
        return _TransactionContext(self.conn)

    def insert_tx(self, table: str, data: dict) -> int:
        """Non-committing insert — caller must manage transaction."""
        columns = ", ".join(f'"{k}"' for k in data.keys())
        placeholders = ", ".join("?" for _ in data)
        sql = f"INSERT INTO {table} ({columns}) VALUES ({placeholders})"
        cur = self.execute(sql, tuple(data.values()))
        return cur.lastrowid

    def update_tx(
        self, table: str, data: dict, where: str, where_params: tuple = ()
    ) -> int:
        """Non-committing update — caller must manage transaction."""
        self._validate_sql_injection(where)
        self._validate_identifier(table)
        for field in data.keys():
            self._validate_identifier(field)
        set_clause = ", ".join(f'"{k}" = ?' for k in data)
        sql = f"UPDATE {table} SET {set_clause} WHERE {where}"
        cur = self.execute(sql, tuple(data.values()) + where_params)
        return cur.rowcount

    def delete_tx(self, table: str, where: str, params: tuple = ()) -> int:
        """Non-committing delete — caller must manage transaction."""
        self._validate_sql_injection(where)
        sql = f"DELETE FROM {table} WHERE {where}"
        cur = self.execute(sql, params)
        return cur.rowcount

    # --- 安全接口部分 ---

    def _validate_sql_injection(self, where_clause: str | None) -> None:
        """Validate WHERE clause is a simple safe expression (whitelist approach).

        Allowed patterns:
        - column = ?
        - column <> ?  / column != ?
        - column < ? / column <= ? / column > ? / column >= ?
        - column LIKE ?
        - column IN (?, ?, ...)
        - column IS ? / column IS NOT ?
        - combinations of above joined by AND (no OR, no parentheses)

        Anything else is rejected.
        """
        if where_clause is None:
            raise ValueError("WHERE clause cannot be None")

        clause = where_clause.strip()
        if not clause:
            raise ValueError("WHERE clause cannot be empty")

        # Blocklist of dangerous characters / patterns
        dangerous = [";", "--", "/*", "*/", "(", ")", "'", '"']
        for d in dangerous:
            if d in clause:
                raise ValueError(
                    f"SQL injection risk: WHERE clause contains forbidden character '{d}': {clause}"
                )

        # Split by AND, validate each part
        parts = [p.strip() for p in clause.split(" AND ")]
        for part in parts:
            if not part:
                continue
            # Must match: identifier [NOT] op [? | (?, ?, ...)]
            # Supported ops after identifier: =, <>, !=, <, <=, >, >=, LIKE, IN, IS, IS NOT
            tokens = part.split()
            if len(tokens) < 3:
                raise ValueError(
                    f"SQL injection risk: WHERE clause part too short: '{part}'"
                )

            # First token must be a safe identifier
            self._validate_identifier(tokens[0])

            # Detect operator
            op_start = 1
            if tokens[1].upper() == "NOT":
                op_start = 2

            if op_start >= len(tokens):
                raise ValueError(
                    f"SQL injection risk: malformed WHERE clause part: '{part}'"
                )

            op = tokens[op_start].upper()
            if op not in {"=", "<>", "!=", "<", "<=", ">", ">=", "LIKE", "IN", "IS"}:
                raise ValueError(
                    f"SQL injection risk: unsupported operator '{op}' in WHERE clause: {clause}"
                )

            # After op, only ? or (?, ?, ...) allowed
            rest = " ".join(tokens[op_start + 1 :]).strip()
            if not rest:
                raise ValueError(
                    f"SQL injection risk: missing value in WHERE clause part: '{part}'"
                )

            if op == "IN":
                if not (rest.startswith("?") or rest.startswith("(")):
                    raise ValueError(
                        f"SQL injection risk: malformed IN clause: '{part}'"
                    )
            else:
                if rest != "?":
                    raise ValueError(
                        f"SQL injection risk: parameterized queries must use '?' placeholder: '{part}'"
                    )

    def update_by_id(self, table: str, data: dict, record_id: int) -> int:
        """Safe update of a single record by its primary key."""
        self._validate_identifier(table)
        for field in data.keys():
            self._validate_identifier(field)

        set_clause = ", ".join(f'"{k}" = ?' for k in data)
        sql = f"UPDATE {table} SET {set_clause} WHERE id = ?"
        cur = self.execute(sql, tuple(data.values()) + (record_id,))
        self.commit()
        return cur.rowcount

    def delete_by_id(self, table: str, record_id: int) -> int:
        """Safe delete of a single record by its primary key."""
        self._validate_identifier(table)
        sql = f"DELETE FROM {table} WHERE id = ?"
        cur = self.execute(sql, (record_id,))
        self.commit()
        return cur.rowcount

    def _validate_identifier(self, identifier: str) -> None:
        """验证标识符（表名、字段名）是否安全"""
        # 只允许字母、数字、下划线
        if not re.match(r"^[a-zA-Z_][a-zA-Z0-9_]*$", identifier):
            raise ValueError(f"不安全的标识符: {identifier}")

    def update_all(self, table: str, data: dict) -> int:
        """Safe unconditional update of all rows in a table.

        Use sparingly — this bypasses the WHERE clause validator.
        """
        self._validate_identifier(table)
        for field in data.keys():
            self._validate_identifier(field)

        set_clause = ", ".join(f'"{k}" = ?' for k in data)
        sql = f"UPDATE {table} SET {set_clause}"
        cur = self.execute(sql, tuple(data.values()))
        self.commit()
        return cur.rowcount

    def update_safe(
        self, table: str, data: Dict[str, Any], filters: Dict[str, Any]
    ) -> int:
        """
        安全更新接口

        Args:
            table: 表名
            data: 要更新的字段和值 {field: value}
            filters: 过滤条件 {field: value} 或 {field: (op, value)}
        """
        self._validate_identifier(table)

        # 构建SET子句
        set_parts = []
        set_values = []
        for field, value in data.items():
            self._validate_identifier(field)
            set_parts.append(f'"{field}" = ?')
            set_values.append(value)

        # 构建WHERE子句
        where_parts = []
        where_values = []
        for field, condition in filters.items():
            self._validate_identifier(field)
            if isinstance(condition, tuple) and len(condition) == 2:
                # {field: ('=', value)} 格式
                op, value = condition
                if op.upper() not in [
                    "=",
                    "<>",
                    "!=",
                    "<",
                    "<=",
                    ">",
                    ">=",
                    "LIKE",
                    "IN",
                    "IS",
                ]:
                    raise ValueError(f"不支持的操作符: {op}")
                where_parts.append(f"{field} {op} ?")
                where_values.append(value)
            elif isinstance(condition, list):
                # IN 查询 {field: [value1, value2, ...]} 格式
                placeholders = ",".join("?" * len(condition))
                where_parts.append(f"{field} IN ({placeholders})")
                where_values.extend(condition)
            else:
                # 默认等值查询 {field: value} 格式
                where_parts.append(f"{field} = ?")
                where_values.append(condition)

        if not where_parts:
            raise ValueError("更新操作必须提供过滤条件")

        set_clause = ", ".join(set_parts)
        where_clause = " AND ".join(where_parts)

        sql = f"UPDATE {table} SET {set_clause} WHERE {where_clause}"
        cur = self.execute(sql, tuple(set_values + where_values))
        self.commit()
        return cur.rowcount

    def delete_safe(self, table: str, filters: Dict[str, Any]) -> int:
        """
        安全删除接口

        Args:
            table: 表名
            filters: 过滤条件 {field: value} 或 {field: (op, value)}
        """
        self._validate_identifier(table)

        where_parts = []
        where_values = []
        for field, condition in filters.items():
            self._validate_identifier(field)
            if isinstance(condition, tuple) and len(condition) == 2:
                # {field: ('=', value)} 格式
                op, value = condition
                if op.upper() not in [
                    "=",
                    "<>",
                    "!=",
                    "<",
                    "<=",
                    ">",
                    ">=",
                    "LIKE",
                    "IN",
                    "IS",
                ]:
                    raise ValueError(f"不支持的操作符: {op}")
                where_parts.append(f"{field} {op} ?")
                where_values.append(value)
            elif isinstance(condition, list):
                # IN 查询 {field: [value1, value2, ...]} 格式
                placeholders = ",".join("?" * len(condition))
                where_parts.append(f"{field} IN ({placeholders})")
                where_values.extend(condition)
            else:
                # 默认等值查询 {field: value} 格式
                where_parts.append(f"{field} = ?")
                where_values.append(condition)

        if not where_parts:
            raise ValueError("删除操作必须提供过滤条件")

        where_clause = " AND ".join(where_parts)
        sql = f"DELETE FROM {table} WHERE {where_clause}"
        cur = self.execute(sql, tuple(where_values))
        self.commit()
        return cur.rowcount


    def health_check(self) -> dict[str, Any]:
        """Return a summary of database health."""
        result: dict[str, Any] = {"ok": True, "issues": []}
        try:
            cur = self.conn.cursor()

            # Integrity check
            cur.execute("PRAGMA integrity_check")
            integrity = cur.fetchone()
            if integrity is None or integrity[0] != "ok":
                result["ok"] = False
                result["issues"].append(f"integrity_check: {integrity[0] if integrity else 'unknown'}")

            # Table counts
            tables = ["accounts", "folders", "emails", "drafts", "email_threads", "offline_operations"]
            counts = {}
            for t in tables:
                try:
                    cur.execute(f"SELECT COUNT(*) FROM {t}")
                    counts[t] = cur.fetchone()[0]
                except Exception:
                    counts[t] = -1
            result["counts"] = counts

            # Database size
            db_size = self._db_path.stat().st_size
            result["db_size_bytes"] = db_size

            # FTS5 table presence
            try:
                cur.execute("SELECT COUNT(*) FROM emails_fts")
                result["fts5_rows"] = cur.fetchone()[0]
            except Exception as e:
                result["fts5_rows"] = -1
                result["issues"].append(f"fts5 check: {e}")

            # Orphan folder check (folders with no account)
            try:
                cur.execute(
                    "SELECT COUNT(*) FROM folders WHERE account_id NOT IN (SELECT id FROM accounts)"
                )
                orphan_folders = cur.fetchone()[0]
                if orphan_folders > 0:
                    result["issues"].append(f"orphan_folders: {orphan_folders}")
            except Exception:
                pass

            # Orphan email check (emails with no folder)
            try:
                cur.execute(
                    "SELECT COUNT(*) FROM emails WHERE folder_id NOT IN (SELECT id FROM folders)"
                )
                orphan_emails = cur.fetchone()[0]
                if orphan_emails > 0:
                    result["issues"].append(f"orphan_emails: {orphan_emails}")
            except Exception:
                pass

        except Exception as e:
            result["ok"] = False
            result["issues"].append(f"health_check exception: {e}")

        return result


class _TransactionContext:
    """SQLite transaction context manager — commit on success, rollback on exception."""

    def __init__(self, conn: sqlite3.Connection) -> None:
        self._conn = conn
        self._depth = 0

    def __enter__(self) -> "_TransactionContext":
        # SQLite supports SAVEPOINT for nested transactions
        if self._depth == 0:
            self._conn.execute("BEGIN")
        else:
            self._conn.execute(f"SAVEPOINT sp_{self._depth}")
        self._depth += 1
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        self._depth -= 1
        if exc_type is None:
            if self._depth == 0:
                self._conn.commit()
            else:
                self._conn.execute(f"RELEASE SAVEPOINT sp_{self._depth}")
        else:
            if self._depth == 0:
                self._conn.rollback()
            else:
                self._conn.execute(f"ROLLBACK TO SAVEPOINT sp_{self._depth}")


db = Database()
