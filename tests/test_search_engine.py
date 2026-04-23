"""Tests for SearchEngine query parsing and search behavior."""

from __future__ import annotations

import pytest

from openemail.models.account import Account
from openemail.models.email import Email
from openemail.models.folder import Folder
from openemail.storage.database import Database
from openemail.storage.search import SearchEngine


class TestParseQuery:
    def test_plain_text(self) -> None:
        fts, filters = SearchEngine._parse_query("hello world")
        assert "hello world" in fts
        assert filters == {}

    def test_from_filter(self) -> None:
        fts, filters = SearchEngine._parse_query("from:alice@example.com")
        assert fts == "*"
        assert filters == {"from_addr": "alice@example.com"}

    def test_to_filter(self) -> None:
        fts, filters = SearchEngine._parse_query("to:bob@example.com")
        assert fts == "*"
        assert filters == {"to_addr": "bob@example.com"}

    def test_subject_filter(self) -> None:
        fts, filters = SearchEngine._parse_query("subject:meeting")
        assert 'subject MATCH "meeting"' in fts
        assert filters == {}

    def test_has_attachment(self) -> None:
        fts, filters = SearchEngine._parse_query("has:attachment")
        assert filters == {"has_attachment": True}

    def test_is_read(self) -> None:
        fts, filters = SearchEngine._parse_query("is:read")
        assert filters == {"is_read": "read"}

    def test_is_unread(self) -> None:
        fts, filters = SearchEngine._parse_query("is:unread")
        assert filters == {"is_read": "unread"}

    def test_is_flagged(self) -> None:
        fts, filters = SearchEngine._parse_query("is:flagged")
        assert filters == {"is_flagged": True}

    def test_after_date(self) -> None:
        fts, filters = SearchEngine._parse_query("after:2024-01-01")
        assert filters == {"after": "2024-01-01"}

    def test_before_date(self) -> None:
        fts, filters = SearchEngine._parse_query("before:2024-12-31")
        assert filters == {"before": "2024-12-31"}

    def test_combined(self) -> None:
        fts, filters = SearchEngine._parse_query(
            "from:alice@example.com subject:report is:read has:attachment after:2024-01-01"
        )
        assert 'subject MATCH "report"' in fts
        assert filters == {
            "from_addr": "alice@example.com",
            "is_read": "read",
            "has_attachment": True,
            "after": "2024-01-01",
        }

    def test_empty_query(self) -> None:
        fts, filters = SearchEngine._parse_query("")
        assert fts == "*"
        assert filters == {}

    def test_remaining_text_not_polluted(self) -> None:
        fts, filters = SearchEngine._parse_query("hello from:alice world")
        assert "hello" in fts
        assert "world" in fts
        assert "from:alice" not in fts


class TestSearchIntegration:
    _counter = 0

    @pytest.fixture
    def account(self, temp_db: Database) -> Account:
        acc = Account(
            email="test@example.com",
            name="Test",
            imap_host="imap.example.com",
            imap_port=993,
            smtp_host="smtp.example.com",
            smtp_port=587,
            ssl_mode="starttls",
            auth_type="password",
            _password="secret",
        )
        acc.save()
        return acc

    @pytest.fixture
    def folder(self, account: Account) -> Folder:
        f = Folder(
            account_id=account.id,
            name="INBOX",
            path="INBOX",
            is_system=True,
            special_use="inbox",
        )
        f.save()
        return f

    def _make_email(self, account: Account, folder: Folder, **kwargs) -> Email:
        TestSearchIntegration._counter += 1
        defaults = {
            "account_id": account.id,
            "folder_id": folder.id,
            "uid": str(TestSearchIntegration._counter),
            "message_id": f"<msg-{TestSearchIntegration._counter}@example.com>",
            "subject": "Test",
            "sender_name": "Sender",
            "sender_addr": "sender@example.com",
            "to_addrs": "[]",
            "cc_addrs": "[]",
            "bcc_addrs": "[]",
            "date": "2024-06-01T10:00:00",
            "size": 100,
            "is_read": False,
            "is_flagged": False,
            "is_deleted": False,
            "is_spam": False,
            "has_attachment": False,
            "preview_text": "hello world content",
            "file_path": "",
            "in_reply_to": "",
            "references": "",
        }
        defaults.update(kwargs)
        em = Email(**defaults)
        em.save()
        return em

    def test_search_by_subject(self, account: Account, folder: Folder) -> None:
        self._make_email(account, folder, subject="Project Alpha", preview_text="alpha")
        self._make_email(account, folder, subject="Project Beta", preview_text="beta")

        results = SearchEngine.search("Alpha", account_id=account.id)
        assert len(results) == 1
        assert results[0].subject == "Project Alpha"

    def test_search_by_sender(self, account: Account, folder: Folder) -> None:
        self._make_email(
            account, folder, sender_addr="alice@example.com", preview_text="alice msg"
        )
        self._make_email(
            account, folder, sender_addr="bob@example.com", preview_text="bob msg"
        )

        results = SearchEngine.search("from:alice@example.com", account_id=account.id)
        assert len(results) == 1
        assert results[0].sender_addr == "alice@example.com"

    def test_search_no_results(self, account: Account, folder: Folder) -> None:
        self._make_email(account, folder, subject="Foo", preview_text="foo")
        results = SearchEngine.search("nonexistent", account_id=account.id)
        assert results == []

    def test_count(self, account: Account, folder: Folder) -> None:
        self._make_email(account, folder, subject="Count", preview_text="count")
        assert SearchEngine.count("Count", account_id=account.id) == 1
        assert SearchEngine.count("Nothing", account_id=account.id) == 0


class TestHighlight:
    def test_highlight_basic(self) -> None:
        text = "hello world"
        result = SearchEngine.highlight(text, "hello")
        assert "<mark>hello</mark>" in result

    def test_highlight_no_match(self) -> None:
        text = "hello world"
        result = SearchEngine.highlight(text, "xyz")
        assert result == "hello world"

    def test_highlight_truncate(self) -> None:
        text = "a" * 200
        result = SearchEngine.highlight(text, "a", max_len=50)
        assert len(result) <= 60  # includes "..."
