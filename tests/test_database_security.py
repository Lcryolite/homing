"""数据库安全接口测试"""

import pytest
import tempfile
import os
from pathlib import Path

from openemail.storage.database import Database


@pytest.fixture
def temp_db():
    """创建临时数据库用于测试"""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = f.name

    # 创建Database实例
    db = Database.__new__(Database)
    db._db_path = Path(db_path)
    db._conn = None
    db.connect()

    # 创建测试表
    db.execute("""
        CREATE TABLE test_table (
            id INTEGER PRIMARY KEY,
            name TEXT,
            value INTEGER,
            status TEXT DEFAULT 'active'
        )
    """)
    db.execute("""
        CREATE TABLE users (
            id INTEGER PRIMARY KEY,
            username TEXT,
            email TEXT,
            is_active INTEGER DEFAULT 1
        )
    """)

    # 插入测试数据
    db.execute("INSERT INTO test_table (name, value) VALUES (?, ?)", ("test1", 100))
    db.execute("INSERT INTO test_table (name, value) VALUES (?, ?)", ("test2", 200))
    db.execute("INSERT INTO test_table (name, value) VALUES (?, ?)", ("test3", 300))

    db.execute(
        "INSERT INTO users (username, email) VALUES (?, ?)", ("user1", "user1@test.com")
    )
    db.execute(
        "INSERT INTO users (username, email) VALUES (?, ?)", ("user2", "user2@test.com")
    )

    db.commit()

    yield db

    # 清理
    db.close()
    os.unlink(db_path)


class TestDatabaseSecurity:
    """数据库安全测试"""

    def test_sql_injection_validation(self, temp_db):
        """测试SQL注入验证"""
        # 测试合法的WHERE子句
        temp_db._validate_sql_injection("id = ?")
        temp_db._validate_sql_injection("name LIKE ?")
        temp_db._validate_sql_injection("status = ? AND id > ?")

        # 测试非法的WHERE子句
        with pytest.raises(ValueError, match="SQL注入风险"):
            temp_db._validate_sql_injection("id = 1; DROP TABLE users")

        with pytest.raises(ValueError, match="SQL注入风险"):
            temp_db._validate_sql_injection("id = 1 UNION SELECT * FROM users")

        with pytest.raises(ValueError, match="SQL注入风险"):
            temp_db._validate_sql_injection("id = 1 OR 1=1")

    def test_identifier_validation(self, temp_db):
        """测试标识符验证"""
        # 测试合法的标识符
        temp_db._validate_identifier("id")
        temp_db._validate_identifier("user_name")
        temp_db._validate_identifier("status123")

        # 测试非法的标识符
        with pytest.raises(ValueError, match="不安全的标识符"):
            temp_db._validate_identifier("id;")

        with pytest.raises(ValueError, match="不安全的标识符"):
            temp_db._validate_identifier("name'")

        with pytest.raises(ValueError, match="不安全的标识符"):
            temp_db._validate_identifier("123id")

    def test_update_safe_basic(self, temp_db):
        """测试安全更新接口基本功能"""
        # 更新单条记录
        result = temp_db.update_safe(
            table="test_table", data={"value": 150}, filters={"name": "test1"}
        )
        assert result == 1

        # 验证更新结果
        row = temp_db.fetchone(
            "SELECT value FROM test_table WHERE name = ?", ("test1",)
        )
        assert row["value"] == 150

    def test_update_safe_with_multiple_filters(self, temp_db):
        """测试带多个过滤条件的更新"""
        # 先设置一些状态
        temp_db.execute(
            "UPDATE test_table SET status = 'inactive' WHERE name = 'test3'"
        )
        temp_db.commit()

        # 使用多个条件更新
        result = temp_db.update_safe(
            table="test_table",
            data={"value": 250},
            filters={"status": "active", "value": ("<", 200)},
        )
        assert result == 1  # 应该只更新test1

    def test_update_safe_with_in_query(self, temp_db):
        """测试IN查询更新"""
        result = temp_db.update_safe(
            table="test_table",
            data={"status": "processed"},
            filters={"name": ["test1", "test2"]},
        )
        assert result == 2

        # 验证更新结果
        rows = temp_db.fetchall(
            "SELECT name FROM test_table WHERE status = 'processed'"
        )
        names = {row["name"] for row in rows}
        assert names == {"test1", "test2"}

    def test_delete_safe_basic(self, temp_db):
        """测试安全删除接口基本功能"""
        # 删除单条记录
        result = temp_db.delete_safe(table="test_table", filters={"name": "test1"})
        assert result == 1

        # 验证删除结果
        rows = temp_db.fetchall("SELECT * FROM test_table")
        assert len(rows) == 2

    def test_update_legacy_with_validation(self, temp_db):
        """测试旧接口验证功能"""
        # 合法的旧接口调用应该工作
        result = temp_db.update(
            table="test_table",
            data={"value": 999},
            where="name = ?",
            where_params=("test2",),
        )
        assert result == 1

        # 非法的WHERE子句应该被拒绝
        with pytest.raises(ValueError, match="SQL注入风险"):
            temp_db.update(
                table="test_table",
                data={"value": 0},
                where="name = ? OR 1=1",
                where_params=("hack",),
            )

    def test_update_safe_rejects_invalid_operators(self, temp_db):
        """测试安全接口拒绝不支持的运算符"""
        with pytest.raises(ValueError, match="不支持的操作符"):
            temp_db.update_safe(
                table="test_table",
                data={"value": 100},
                filters={"name": ("EXEC", "malicious")},
            )

    def test_empty_filters_rejected(self, temp_db):
        """测试空过滤条件被拒绝"""
        with pytest.raises(ValueError, match="更新操作必须提供过滤条件"):
            temp_db.update_safe(table="test_table", data={"value": 100}, filters={})

        with pytest.raises(ValueError, match="删除操作必须提供过滤条件"):
            temp_db.delete_safe(table="test_table", filters={})

    def test_table_name_validation(self, temp_db):
        """测试表名验证"""
        # 非法的表名应该被拒绝
        with pytest.raises(ValueError, match="不安全的标识符"):
            temp_db.update_safe(
                table="users; DROP TABLE test_table",
                data={"value": 100},
                filters={"id": 1},
            )


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
