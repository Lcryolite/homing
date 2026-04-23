"""Tests for thread building and fallback behavior."""

from __future__ import annotations

import pytest

from openemail.core.thread_builder import ThreadBuilder
from openemail.models.account import Account
from openemail.models.email import Email
from openemail.models.email_thread import EmailThread
from openemail.models.folder import Folder
from openemail.storage.database import Database


@pytest.fixture
def account(temp_db: Database) -> Account:
    acc = Account(
        email="test@example.com",
        name="Test User",
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


_uid_counter = 0


def _make_email(account: Account, **kwargs) -> Email:
    global _uid_counter
    _uid_counter += 1

    # Ensure a folder exists for the foreign key constraint
    folder = Folder.get_by_name(account.id, "INBOX")
    if folder is None:
        folder = Folder(
            account_id=account.id,
            name="INBOX",
            path="INBOX",
            is_system=True,
            special_use="inbox",
        )
        folder.save()

    defaults = {
        "account_id": account.id,
        "folder_id": folder.id,
        "uid": str(_uid_counter),
        "message_id": f"<msg-{_uid_counter}@example.com>",
        "subject": "Test",
        "sender_name": "Sender",
        "sender_addr": "sender@example.com",
        "to_addrs": "[]",
        "cc_addrs": "[]",
        "bcc_addrs": "[]",
        "date": "2024-01-01T10:00:00",
        "size": 100,
        "is_read": False,
        "is_flagged": False,
        "is_deleted": False,
        "is_spam": False,
        "has_attachment": False,
        "preview_text": "",
        "file_path": "",
        "in_reply_to": "",
        "references": "",
    }
    defaults.update(kwargs)
    em = Email(**defaults)
    em.save()
    return em


class TestAssignToThread:
    def test_in_reply_to_match(self, account: Account) -> None:
        parent = _make_email(account, message_id="<parent@example.com>", subject="Parent")
        ThreadBuilder.assign_to_thread(parent)

        child = _make_email(
            account,
            message_id="<child@example.com>",
            in_reply_to="<parent@example.com>",
            subject="Re: Parent",
        )
        thread = ThreadBuilder.assign_to_thread(child)

        assert thread is not None
        assert thread.id == EmailThread.find_by_email_id(parent.id).id

    def test_references_match(self, account: Account) -> None:
        grandparent = _make_email(
            account, message_id="<gp@example.com>", subject="Original"
        )
        ThreadBuilder.assign_to_thread(grandparent)

        reply = _make_email(
            account,
            message_id="<r@example.com>",
            references="<gp@example.com>",
            subject="Re: Original",
        )
        thread = ThreadBuilder.assign_to_thread(reply)

        assert thread is not None
        assert thread.id == EmailThread.find_by_email_id(grandparent.id).id

    def test_subject_normalization_match(self, account: Account) -> None:
        first = _make_email(account, message_id="<s1@example.com>", subject="Meeting")
        ThreadBuilder.assign_to_thread(first)

        second = _make_email(
            account,
            message_id="<s2@example.com>",
            subject="Re: Meeting",
        )
        thread = ThreadBuilder.assign_to_thread(second)

        assert thread is not None
        assert thread.id == EmailThread.find_by_email_id(first.id).id

    def test_no_match_creates_new_thread(self, account: Account) -> None:
        em = _make_email(account, message_id="<new@example.com>", subject="Unrelated")
        thread = ThreadBuilder.assign_to_thread(em)

        assert thread is not None
        assert EmailThread.find_by_email_id(em.id) is not None

    def test_missing_message_id_does_not_crash(self, account: Account) -> None:
        em = _make_email(account, message_id="", subject="No ID")
        thread = ThreadBuilder.assign_to_thread(em)
        assert thread is not None


class TestNormalizeSubject:
    def test_re_prefix(self) -> None:
        assert ThreadBuilder._normalize_subject("Re: Hello") == "Hello"
        assert ThreadBuilder._normalize_subject("RE: Hello") == "Hello"

    def test_fwd_prefix(self) -> None:
        assert ThreadBuilder._normalize_subject("Fwd: Hello") == "Hello"
        assert ThreadBuilder._normalize_subject("Fw: Hello") == "Hello"

    def test_numbered_re(self) -> None:
        assert ThreadBuilder._normalize_subject("Re[2]: Hello") == "Hello"

    def test_no_prefix(self) -> None:
        assert ThreadBuilder._normalize_subject("Hello") == "Hello"

    def test_whitespace_trim(self) -> None:
        assert ThreadBuilder._normalize_subject("  Re: Hello  ") == "Hello"


class TestRebuildAllThreads:
    def test_rebuild_counts(self, account: Account) -> None:
        e1 = _make_email(account, message_id="<a@example.com>", subject="Topic")
        e2 = _make_email(
            account,
            message_id="<b@example.com>",
            in_reply_to="<a@example.com>",
            subject="Re: Topic",
        )
        e3 = _make_email(
            account,
            message_id="<c@example.com>",
            subject="Other",
        )

        # Initial assignment
        ThreadBuilder.assign_to_thread(e1)
        ThreadBuilder.assign_to_thread(e2)
        ThreadBuilder.assign_to_thread(e3)

        # Rebuild
        count = ThreadBuilder.rebuild_all_threads(account.id)
        assert count == 3

        threads = EmailThread.get_by_account(account.id)
        assert len(threads) == 2  # Topic + Other
