"""Smoke tests verifying shared test fixtures work (T0.5)."""

from openemail.storage.database import Database


class TestSharedFixtures:
    """Verify conftest fixtures are functional."""

    def test_temp_db_creates_schema(self, temp_db: Database):
        """temp_db fixture should run all migrations."""
        row = temp_db.fetchone("SELECT MAX(version) FROM schema_version")
        assert row is not None
        assert row[0] > 0

    def test_temp_db_has_accounts_table(self, temp_db: Database):
        row = temp_db.fetchone(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='accounts'"
        )
        assert row is not None

    def test_sample_account_inserts(self, temp_db: Database, sample_account: dict):
        assert sample_account["email"] == "test@example.com"
        assert sample_account["imap_host"] == "imap.example.com"
        assert sample_account["protocol"] == "imap"

    def test_sample_folder_inserts(self, temp_db: Database, sample_folder: dict):
        assert sample_folder["special_use"] == "inbox"
        assert sample_folder["path"] == "INBOX"

    def test_plain_email_fixture(self, sample_plain_email: bytes):
        assert b"text/plain" in sample_plain_email
        assert b"Hello Bob" in sample_plain_email

    def test_html_email_fixture(self, sample_html_email: bytes):
        assert b"text/html" in sample_html_email
        assert b"<b>HTML</b>" in sample_html_email

    def test_multipart_email_fixture(self, sample_multipart_email: bytes):
        assert b"multipart/alternative" in sample_multipart_email
        assert b"boundary" in sample_multipart_email

    def test_attachment_email_fixture(self, sample_attachment_email: bytes):
        assert b"Content-Disposition: attachment" in sample_attachment_email
        assert b"data.csv" in sample_attachment_email

    def test_reply_email_fixture(self, sample_reply_email: bytes):
        assert b"In-Reply-To:" in sample_reply_email
        assert b"References:" in sample_reply_email

    def test_forward_email_fixture(self, sample_forward_email: bytes):
        assert b"Fwd:" in sample_forward_email
        assert b"Forwarded message" in sample_forward_email

    def test_empty_db_not_connected(self, empty_db: Database):
        """empty_db fixture should NOT call connect()."""
        assert empty_db._conn is None
