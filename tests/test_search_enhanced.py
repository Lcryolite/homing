"""增强版搜索系统测试"""

import pytest
from unittest.mock import Mock, patch

from openemail.storage.search_enhanced import EnhancedSearchEngine
from openemail.models.email import Email
from openemail.models.account import Account
from openemail.models.folder import Folder


class TestEnhancedSearchEngine:
    """增强版搜索引擎测试"""

    def test_parse_advanced_query(self):
        """测试高级查询解析"""
        # 测试各种过滤器和搜索词
        test_cases = [
            # (输入查询, 预期过滤器, 预期搜索词)
            (
                "important meeting from:john@example.com",
                {"from": "john@example.com"},
                ["important", "meeting"],
            ),
            (
                "project status subject:weekly report",
                {"subject": "weekly report"},
                ["project", "status"],
            ),
            (
                "budget plan has:attachment is:unread",
                {"has_attachment": True, "is_read": False},
                ["budget", "plan"],
            ),
            (
                '"urgent task" after:2024-01-01 before:2024-12-31',
                {"after_date": "2024-01-01", "before_date": "2024-12-31"},
                ["urgent task"],
            ),
            (
                "to:team@company.com is:flagged in:inbox",
                {"to": "team@company.com", "is_flagged": True, "folder": "inbox"},
                [],
            ),
        ]

        for query, expected_filters, expected_terms in test_cases:
            filters, terms = EnhancedSearchEngine._parse_advanced_query(query)

            assert filters == expected_filters, f"过滤器解析错误: {query}"
            assert terms == expected_terms, f"搜索词解析错误: {query}"

    @patch("openemail.storage.search_enhanced.db")
    def test_fts_search(self, mock_db):
        """测试传统FTS5搜索"""
        # 模拟数据库返回
        mock_rows = [
            {
                "id": 1,
                "account_id": 1,
                "folder_id": 1,
                "sender_name": "John Doe",
                "sender_addr": "john@example.com",
                "to_addrs": "team@example.com",
                "subject": "Test Email",
                "body": "This is a test email",
                "date": "2024-01-01 10:00:00",
                "is_read": 0,
                "is_flagged": 0,
                "has_attachment": 0,
                "is_deleted": 0,
                "is_spam": 0,
                "preview_text": "This is a test email",
                "thread_id": None,
                "message_id": "test123",
            }
        ]
        mock_db.fetchall.return_value = mock_rows

        # 执行搜索
        results = EnhancedSearchEngine._fts_search(
            search_terms=["test", "email"],
            filters={},
            account_id=1,
            folder_id=None,
            limit=10,
            offset=0,
        )

        assert len(results) == 1
        assert results[0].id == 1
        assert results[0].subject == "Test Email"

        # 验证SQL参数
        mock_db.fetchall.assert_called_once()
        args = mock_db.fetchall.call_args[0]
        # args[0] = SQL, args[1] = params list where params[0] is the FTS query
        params = args[1] if len(args) > 1 else []
        assert any("test" in str(p) for p in params)  # FTS query contains search terms

    @patch("openemail.storage.search_enhanced.db")
    def test_search_attachments(self, mock_db):
        """测试附件内容搜索"""
        # 模拟数据库返回
        mock_rows = [
            {
                "id": 2,
                "account_id": 1,
                "folder_id": 1,
                "sender_name": "Jane Smith",
                "sender_addr": "jane@example.com",
                "to_addrs": "team@example.com",
                "subject": "Meeting Notes",
                "body": "Attached are the meeting notes",
                "date": "2024-01-01 14:00:00",
                "is_read": 0,
                "is_flagged": 0,
                "has_attachment": 1,
                "is_deleted": 0,
                "is_spam": 0,
                "preview_text": "Attached are the meeting notes",
                "thread_id": None,
                "message_id": "test456",
            }
        ]
        mock_db.fetchall.return_value = mock_rows

        # 执行附件搜索
        results = EnhancedSearchEngine.search_attachments(
            query="meeting", account_id=1, folder_id=None, limit=10
        )

        assert len(results) == 1
        assert results[0].id == 2
        assert results[0].subject == "Meeting Notes"
        assert results[0].has_attachment == 1

        # 验证SQL包含附件搜索
        mock_db.fetchall.assert_called_once()
        args = mock_db.fetchall.call_args[0]
        assert "attachments_fts MATCH" in args[0]

    def test_search_conversations(self):
        """测试对话搜索（按主题分组）"""
        # 注意：这个测试可能依赖实际数据，这里简化测试
        # 在实际项目中可能需要添加更多模拟

        # 测试空查询
        conversations = EnhancedSearchEngine.search_conversations(
            query="", account_id=1, limit=10
        )

        assert isinstance(conversations, list)

    def test_search_suggestions(self):
        """测试搜索建议"""
        # 测试基础建议
        suggestions = EnhancedSearchEngine.search_suggestions(
            query="john", account_id=1, limit=5
        )

        assert isinstance(suggestions, list)

        # 测试文件夹建议
        folder_suggestions = EnhancedSearchEngine.search_suggestions(
            query="in:", account_id=1, limit=5
        )

        assert isinstance(folder_suggestions, list)

    @patch("openemail.storage.search_enhanced.db")
    def test_save_search_history(self, mock_db):
        """测试保存搜索历史"""
        # 模拟数据库操作
        mock_db.insert.return_value = True

        # 保存搜索历史
        EnhancedSearchEngine.save_search_history(
            query="test email", account_id=1, result_count=5
        )

        # 验证数据库调用（不对 searched_at 做精确匹配，因为它用 datetime.now()）
        mock_db.insert.assert_called_once()
        call_args = mock_db.insert.call_args[0]
        assert call_args[0] == "search_history"
        data = call_args[1]
        assert data["query"] == "test email"
        assert data["account_id"] == 1
        assert data["result_count"] == 5
        assert "searched_at" in data  # just verify key exists

    @patch("openemail.storage.search_enhanced.db")
    def test_get_search_history(self, mock_db):
        """测试获取搜索历史"""
        # 模拟数据库返回
        mock_rows = [
            {
                "query": "test email",
                "result_count": 5,
                "searched_at": "2024-01-01 10:00:00",
            }
        ]
        mock_db.fetchall.return_value = mock_rows

        # 获取搜索历史
        history = EnhancedSearchEngine.get_search_history(account_id=1, limit=10)

        assert len(history) == 1
        assert history[0]["query"] == "test email"
        assert history[0]["count"] == 5

        # 验证SQL调用
        mock_db.fetchall.assert_called_once()

    def test_generate_search_snippets(self):
        """测试生成搜索摘要片段"""
        # 创建测试邮件对象
        test_email = Mock(spec=Email)
        test_email.subject = "Important Meeting about Project"
        test_email.preview_text = (
            "This is an important meeting about the project status and budget."
        )

        # 测试主题匹配
        snippets = EnhancedSearchEngine.generate_search_snippets(
            email=test_email, query="meeting", max_snippets=2, snippet_length=50
        )

        assert len(snippets) > 0
        assert "important" in snippets[0].lower() or "meeting" in snippets[0].lower()

        # 测试正文匹配
        snippets = EnhancedSearchEngine.generate_search_snippets(
            email=test_email, query="project", max_snippets=2, snippet_length=50
        )

        assert len(snippets) > 0

        # 测试无匹配
        snippets = EnhancedSearchEngine.generate_search_snippets(
            email=test_email, query="nonexistent", max_snippets=2, snippet_length=50
        )

        assert len(snippets) == 0

    def test_init_enhanced_search(self):
        """测试初始化增强搜索系统"""
        # 调用初始化函数
        from openemail.storage.search_enhanced import init_enhanced_search

        # 确保不会抛出异常
        try:
            init_enhanced_search()
        except Exception as e:
            pytest.fail(f"init_enhanced_search 抛出异常: {e}")

    def test_semantic_search_missing_dependency(self):
        """测试缺少依赖时的语义搜索"""
        # 当 sentence_transformers 未安装时，_semantic_search 应返回空列表
        from openemail.storage.search_enhanced import EnhancedSearchEngine
        results = EnhancedSearchEngine._semantic_search(
            search_terms=["test"], account_id=1, folder_id=None, limit=10
        )
        # sentence_transformers 未安装，应该优雅降级返回空列表
        assert isinstance(results, list)

    @patch("openemail.storage.search_enhanced.db")
    def test_search_with_filters(self, mock_db):
        """测试带过滤器的搜索"""
        # 模拟数据库返回
        mock_rows = [
            {
                "id": 3,
                "account_id": 1,
                "folder_id": 1,
                "sender_name": "Bob Wilson",
                "sender_addr": "bob@example.com",
                "to_addrs": "team@example.com",
                "subject": "Urgent: Server Down",
                "body": "The production server is down.",
                "date": "2024-01-01 15:00:00",
                "is_read": 0,
                "is_flagged": 0,
                "has_attachment": 0,
                "is_deleted": 0,
                "is_spam": 0,
                "preview_text": "The production server is down.",
                "thread_id": None,
                "message_id": "test789",
            }
        ]
        mock_db.fetchall.return_value = mock_rows

        # 执行带过滤器的搜索
        results = EnhancedSearchEngine._fts_search(
            search_terms=[],
            filters={"from": "bob", "is_read": False},
            account_id=1,
            folder_id=None,
            limit=10,
            offset=0,
        )

        assert len(results) == 1
        assert "bob@example.com" in results[0].sender_addr

        # 验证SQL包含过滤器
        mock_db.fetchall.assert_called_once()
        args = mock_db.fetchall.call_args[0]
        assert "sender_addr LIKE" in args[0]
        assert "is_read = ?" in args[0]


class TestSearchIntegration:
    """搜索集成测试"""

    @pytest.fixture
    def test_data(self):
        """测试数据设置"""
        # 创建测试账户
        account = Account(
            id=1,
            name="Test Account",
            email="test@example.com",
            protocol="imap",
            server="mail.example.com",
            port=993,
            username="test",
            password="pass",
            use_ssl=True,
        )

        # 创建测试文件夹
        folder = Folder(
            id=1,
            account_id=1,
            name="INBOX",
            type="system",
            sync_state="synced",
            last_synced="2024-01-01 00:00:00",
        )

        return {"account": account, "folder": folder}

    @patch("openemail.storage.search_enhanced.Email")
    def test_enhanced_search_main_method(self, mock_email_class):
        """测试增强版搜索主方法"""
        # 模拟电子邮件返回
        mock_email = Mock(spec=Email)
        mock_email.id = 1
        mock_email_class._from_row.return_value = mock_email

        # 模拟数据库返回
        with patch("openemail.storage.search_enhanced.db") as mock_db:
            mock_rows = [{"id": 1, "subject": "Test"}]
            mock_db.fetchall.return_value = mock_rows

            # 执行增强版搜索
            results = EnhancedSearchEngine.search(
                query="test message", account_id=1, folder_id=None, limit=50
            )

            assert len(results) == 1
            assert results[0].id == 1

    def test_search_error_handling(self):
        """测试搜索错误处理"""
        # 测试不存在的账户
        results = EnhancedSearchEngine.search(
            query="test",
            account_id=99999,  # 不存在的账户
            folder_id=None,
            limit=10,
        )

        assert isinstance(results, list)  # 应该是空列表而不是异常

        # 测试空查询
        results = EnhancedSearchEngine.search(
            query="",  # 空查询
            account_id=1,
            folder_id=None,
            limit=10,
        )

        assert isinstance(results, list)


if __name__ == "__main__":
    # 运行测试
    pytest.main([__file__, "-v"])
