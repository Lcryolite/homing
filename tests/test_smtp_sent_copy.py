"""Tests for SMTP sent-copy save logic."""

import pytest

from openemail.core.mail_builder import MailBuilder
from openemail.core.smtp_client import _save_sent_copy
from openemail.models.account import Account
from openemail.models.email import Email
from openemail.models.folder import Folder


@pytest.fixture
def account(temp_db):
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


@pytest.fixture
def sent_message():
    builder = MailBuilder()
    builder.set_from("test@example.com", "Test User")
    builder.set_to(["to@example.com"])
    builder.set_subject("Hello")
    builder.set_text_body("World")
    return builder.build()


class TestSaveSentCopy:
    def test_creates_sent_folder_if_missing(self, account, sent_message, temp_db) -> None:
        assert Folder.get_by_name(account.id, "Sent") is None

        _save_sent_copy(account, sent_message)

        sent_folder = Folder.get_by_name(account.id, "Sent")
        assert sent_folder is not None
        assert sent_folder.special_use == "sent"
        assert sent_folder.is_system is True

    def test_creates_email_record(self, account, sent_message, temp_db) -> None:
        _save_sent_copy(account, sent_message)

        sent_folder = Folder.get_by_name(account.id, "Sent")
        emails = Email.get_by_folder(sent_folder.id)
        assert len(emails) == 1
        em = emails[0]
        assert em.subject == "Hello"
        assert em.sender_addr == "test@example.com"
        assert em.is_read is True
        assert em.folder_id == sent_folder.id

    def test_uid_prefix(self, account, sent_message, temp_db) -> None:
        _save_sent_copy(account, sent_message)

        sent_folder = Folder.get_by_name(account.id, "Sent")
        em = Email.get_by_folder(sent_folder.id)[0]
        assert em.uid.startswith("sent-")

    def test_uses_existing_sent_folder(self, account, sent_message, temp_db) -> None:
        existing = Folder(
            account_id=account.id,
            name="Sent",
            path="Sent",
            is_system=True,
            special_use="sent",
        )
        existing.save()

        _save_sent_copy(account, sent_message)

        emails = Email.get_by_folder(existing.id)
        assert len(emails) == 1
        assert emails[0].folder_id == existing.id
