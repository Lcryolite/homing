"""Tests for MailStore attachment cleanup and Email delete consistency."""

from __future__ import annotations

import pytest

from openemail.models.account import Account
from openemail.models.email import Email
from openemail.models.folder import Folder
from openemail.storage.mail_store import MailStore
from openemail.storage.database import Database


@pytest.fixture
def account(temp_db: Database) -> Account:
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
def folder(account: Account) -> Folder:
    f = Folder(
        account_id=account.id,
        name="INBOX",
        path="INBOX",
        is_system=True,
        special_use="inbox",
    )
    f.save()
    return f


class TestEmailDeleteCleanup:
    def test_delete_removes_raw_file(self, account: Account, folder: Folder) -> None:
        store = MailStore()
        file_path = store.save_raw(account.id, folder.name, "1", b"raw data")
        assert file_path.exists()

        em = Email(
            account_id=account.id,
            folder_id=folder.id,
            uid="1",
            file_path=str(file_path),
            preview_text="test",
        )
        em.save()

        em.delete()
        assert not file_path.exists()

    def test_delete_removes_attachments(self, account: Account, folder: Folder) -> None:
        store = MailStore()
        em = Email(
            account_id=account.id,
            folder_id=folder.id,
            uid="2",
            has_attachment=True,
            preview_text="test",
        )
        em.save()

        att_path = store.save_attachment(em.id, "file.txt", b"data")
        assert att_path.exists()

        em.delete()
        assert not att_path.parent.exists()


class TestOrphanCleanup:
    def test_cleanup_removes_orphan_attachments(self, account: Account, folder: Folder) -> None:
        store = MailStore()
        em = Email(
            account_id=account.id,
            folder_id=folder.id,
            uid="3",
            has_attachment=True,
            preview_text="test",
        )
        em.save()
        att_path = store.save_attachment(em.id, "file.txt", b"data")

        # Delete email record directly to simulate orphan
        from openemail.storage.database import db
        db.execute("DELETE FROM emails WHERE id = ?", (em.id,))

        # File still on disk
        assert att_path.exists()

        removed = store.cleanup_orphan_attachments()
        assert removed >= 1
        assert not att_path.parent.exists()

    def test_cleanup_keeps_valid_attachments(self, account: Account, folder: Folder) -> None:
        store = MailStore()
        em = Email(
            account_id=account.id,
            folder_id=folder.id,
            uid="4",
            has_attachment=True,
            preview_text="test",
        )
        em.save()
        att_path = store.save_attachment(em.id, "file.txt", b"data")

        removed = store.cleanup_orphan_attachments()
        assert removed == 0
        assert att_path.exists()
