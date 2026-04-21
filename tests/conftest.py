"""Shared test fixtures for OpenEmail.

Every test that needs a database, config directory, or sample data should
import from here instead of creating its own temporary environment.
"""

from __future__ import annotations

from pathlib import Path
from typing import Generator

import pytest

from openemail.storage.database import Database


# ---------------------------------------------------------------------------
# Temporary directories
# ---------------------------------------------------------------------------


@pytest.fixture()
def tmp_config_dir(tmp_path: Path) -> Generator[Path, None, None]:
    """Provide an isolated config directory (replaces ~/.openemail)."""
    d = tmp_path / "openemail"
    d.mkdir()
    yield d
    # cleanup handled by tmp_path


@pytest.fixture()
def tmp_attachment_dir(tmp_path: Path) -> Generator[Path, None, None]:
    """Provide an isolated attachment directory."""
    d = tmp_path / "attachments"
    d.mkdir()
    yield d


# ---------------------------------------------------------------------------
# Database fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def temp_db(tmp_path: Path) -> Generator[Database, None, None]:
    """Fresh Database with real schema (runs all migrations).

    Use this for any test that touches the database layer.
    """
    db_path = tmp_path / "test.db"
    db = Database.__new__(Database)
    db._db_path = db_path
    db._conn = None
    db.connect()
    yield db
    db.close()


@pytest.fixture()
def empty_db(tmp_path: Path) -> Generator[Database, None, None]:
    """Database file created but connect() NOT called (for migration tests)."""
    db_path = tmp_path / "test.db"
    db = Database.__new__(Database)
    db._db_path = db_path
    db._conn = None
    yield db


# ---------------------------------------------------------------------------
# Account / folder factories
# ---------------------------------------------------------------------------


@pytest.fixture()
def sample_account(temp_db: Database) -> dict:
    """Insert a test IMAP account and return its record."""
    temp_db.execute(
        """
        INSERT INTO accounts (name, email, protocol, imap_host, imap_port,
                              smtp_host, smtp_port, auth_type, is_active)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            "Test Account",
            "test@example.com",
            "imap",
            "imap.example.com",
            993,
            "smtp.example.com",
            465,
            "password",
            1,
        ),
    )
    temp_db.commit()
    row = temp_db.fetchone(
        "SELECT * FROM accounts WHERE email = ?", ("test@example.com",)
    )
    return dict(row)


@pytest.fixture()
def sample_folder(temp_db: Database, sample_account: dict) -> dict:
    """Insert a test folder for the sample account."""
    temp_db.execute(
        """
        INSERT INTO folders (account_id, name, path, special_use)
        VALUES (?, ?, ?, ?)
        """,
        (sample_account["id"], "INBOX", "INBOX", "inbox"),
    )
    temp_db.commit()
    row = temp_db.fetchone(
        "SELECT * FROM folders WHERE account_id = ? AND special_use = ?",
        (sample_account["id"], "inbox"),
    )
    return dict(row)


# ---------------------------------------------------------------------------
# Sample email fixtures (return raw RFC 822 bytes)
# ---------------------------------------------------------------------------

FIXTURES_DIR = Path(__file__).parent / "fixtures"


def _read_fixture(name: str) -> bytes:
    path = FIXTURES_DIR / name
    if not path.exists():
        pytest.skip(f"Fixture {name} not found")
    return path.read_bytes()


@pytest.fixture()
def sample_plain_email() -> bytes:
    return _read_fixture("plain_text.eml")


@pytest.fixture()
def sample_html_email() -> bytes:
    return _read_fixture("html.eml")


@pytest.fixture()
def sample_multipart_email() -> bytes:
    return _read_fixture("multipart.eml")


@pytest.fixture()
def sample_attachment_email() -> bytes:
    return _read_fixture("attachment.eml")


@pytest.fixture()
def sample_reply_email() -> bytes:
    return _read_fixture("reply.eml")


@pytest.fixture()
def sample_forward_email() -> bytes:
    return _read_fixture("forward.eml")
