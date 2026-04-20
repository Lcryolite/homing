import re
import sqlite3
from pathlib import Path
from typing import Any, Union, List, Dict, Tuple

from openemail.config import settings
from openemail.storage.migrations import SCHEMA_VERSION, MIGRATIONS
from openemail.utils.exceptions import safe_execute


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
        assert self._conn is not None
        cur = self._conn.cursor()
        cur.execute(
            "CREATE TABLE IF NOT EXISTS schema_version (version INTEGER PRIMARY KEY)"
        )
        cur.execute("SELECT MAX(version) FROM schema_version")
        row = cur.fetchone()
        current = row[0] if row and row[0] is not None else 0

        print(f"数据库当前版本: {current}, 目标版本: {SCHEMA_VERSION}")

        for version in range(current + 1, SCHEMA_VERSION + 1):
            statements = MIGRATIONS.get(version, [])
            if not statements:
                print(f"版本 {version}: 无迁移语句")
                continue

            print(f"执行版本 {version} 迁移...")
            for stmt in statements:
                try:
                    cur.execute(stmt)
                except sqlite3.OperationalError as e:
                    if "duplicate column name" in str(e) or "already exists" in str(e):
                        print(f"  跳过已存在的操作: {stmt[:60]}...")
                    else:
                        print(f"  迁移错误: {e}")
                        raise
            cur.execute(
                "INSERT OR REPLACE INTO schema_version (version) VALUES (?)", (version,)
            )
            print(f"版本 {version} 迁移完成")
        self._conn.commit()

    def execute(self, sql: str, params: tuple = ()) -> sqlite3.Cursor:
        return self.conn.execute(sql, params)

    def executemany(self, sql: str, params_seq: list[tuple]) -> sqlite3.Cursor:
        return self.conn.executemany(sql, params_seq)

    def commit(self) -> None:
        self.conn.commit()

    def rollback(self) -> None:
        self.conn.rollback()

    def fetchone(self, sql: str, params: tuple = ()) -> sqlite3.Row | None:
        cur = self.execute(sql, params)
        return cur.fetchone()

    def fetchall(self, sql: str, params: tuple = ()) -> list[sqlite3.Row]:
        cur = self.execute(sql, params)
        return cur.fetchall()

    def insert(self, table: str, data: dict) -> int:
        columns = ", ".join(data.keys())
        placeholders = ", ".join("?" for _ in data)
        sql = f"INSERT INTO {table} ({columns}) VALUES ({placeholders})"
        cur = self.execute(sql, tuple(data.values()))
        self.commit()
        return cur.lastrowid

    def update(
        self, table: str, data: dict, where: str, where_params: tuple = ()
    ) -> int:
        # 添加SQL注入验证（向后兼容）
        self._validate_sql_injection(where)
        self._validate_identifier(table)
        for field in data.keys():
            self._validate_identifier(field)

        set_clause = ", ".join(f"{k} = ?" for k in data)
        sql = f"UPDATE {table} SET {set_clause} WHERE {where}"
        cur = self.execute(sql, tuple(data.values()) + where_params)
        self.commit()
        return cur.rowcount

    def delete(self, table: str, where: str, params: tuple = ()) -> int:
        self._validate_sql_injection(where)
        sql = f"DELETE FROM {table} WHERE {where}"
        cur = self.execute(sql, params)
        self.commit()
        return cur.rowcount

    # --- 安全接口部分 ---

    def _validate_sql_injection(self, where_clause: str) -> None:
        """验证WHERE子句是否存在SQL注入风险"""
        # 检查SQL关键字
        sql_keywords = [
            "SELECT",
            "INSERT",
            "UPDATE",
            "DELETE",
            "DROP",
            "CREATE",
            "ALTER",
            "UNION",
            "JOIN",
            "OR",
            "AND",
            "EXEC",
            "EXECUTE",
        ]

        upper_where = where_clause.upper()
        for keyword in sql_keywords:
            # 检查是否包含SQL关键字，但排除合法的操作符如 "field = ?"
            pattern = rf"\b{keyword}\b"
            if re.search(pattern, upper_where) and keyword not in ["OR", "AND"]:
                raise ValueError(
                    f"SQL注入风险: WHERE子句中包含禁止的SQL关键字 '{keyword}': {where_clause}"
                )

        # 检查分号
        if ";" in where_clause:
            raise ValueError(f"SQL注入风险: WHERE子句中包含分号: {where_clause}")

    def _validate_identifier(self, identifier: str) -> None:
        """验证标识符（表名、字段名）是否安全"""
        # 只允许字母、数字、下划线
        if not re.match(r"^[a-zA-Z_][a-zA-Z0-9_]*$", identifier):
            raise ValueError(f"不安全的标识符: {identifier}")

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
            set_parts.append(f"{field} = ?")
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


db = Database()
