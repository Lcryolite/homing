"""Tests for database migration rollback and crash recovery."""

import os
import shutil
import sqlite3
import tempfile

import pytest

from openemail.storage.database import Database
from openemail.storage.migrations import SCHEMA_VERSION, MIGRATIONS, ROLLBACKS


@pytest.fixture
def isolated_db(tmp_path):
    """Create a fresh Database instance with a temp db path."""
    db_path = tmp_path / "test.db"
    db = Database.__new__(Database)
    db._db_path = db_path
    db._conn = None
    db.connect()
    yield db
    db.close()


class TestMigrationBackupRestore:
    """Migration creates backup before each step and cleans up on success."""

    def test_no_bak_files_after_successful_migration(self, isolated_db, tmp_path):
        """Successful migration should leave no .bak files behind."""
        bak_files = list(tmp_path.glob("*.bak"))
        assert bak_files == []

    def test_schema_version_reached(self, isolated_db):
        """After connect(), schema version should match SCHEMA_VERSION."""
        row = isolated_db.fetchone("SELECT MAX(version) FROM schema_version")
        assert row[0] == SCHEMA_VERSION

    def test_all_tables_exist(self, isolated_db):
        """Core tables should exist after full migration."""
        expected_tables = {
            "accounts", "folders", "emails", "filter_rules", "bayes_tokens",
            "contacts", "calendar_events", "todos", "projects",
            "project_columns", "project_cards", "tags", "email_tags",
            "operation_queue", "drafts", "oauth_tokens",
            "email_threads", "email_thread_members", "bayes_meta",
        }
        rows = isolated_db.fetchall(
            "SELECT name FROM sqlite_master WHERE type='table'"
        )
        actual = {r["name"] for r in rows}
        missing = expected_tables - actual - {"schema_version", "sqlite_sequence"}
        assert not missing, f"Missing tables: {missing}"


class TestMigrationFailureRestore:
    """Simulate a failed migration and verify rollback to backup."""

    def test_bad_migration_restores_db(self, tmp_path):
        """If a migration statement fails, the DB should be restored from backup."""
        db_path = tmp_path / "fail_test.db"

        # Create a minimal v7 db (before drafts/oauth_tokens/threading)
        conn = sqlite3.connect(str(db_path))
        conn.execute("CREATE TABLE schema_version (version INTEGER PRIMARY KEY)")
        conn.execute("INSERT INTO schema_version VALUES (7)")
        conn.execute("CREATE TABLE accounts (id INTEGER PRIMARY KEY, email TEXT)")
        conn.commit()
        conn.close()

        # Inject a bad migration at v8 (overwrite temporarily)
        import openemail.storage.migrations as mig
        original_v8 = mig.MIGRATIONS.get(8, [])
        mig.MIGRATIONS[8] = ["THIS IS NOT VALID SQL"]

        try:
            db = Database.__new__(Database)
            db._db_path = db_path
            db._conn = None
            # connect() is wrapped with @safe_execute, so it returns None on failure
            result = db.connect()
            assert result is None, "connect() should return None on migration failure"

            # Verify the backup was restored — schema should still be at 7
            conn2 = sqlite3.connect(str(db_path))
            cur = conn2.execute("SELECT MAX(version) FROM schema_version")
            ver = cur.fetchone()[0]
            conn2.close()
            assert ver == 7, f"Expected version 7 after restore, got {ver}"
        finally:
            mig.MIGRATIONS[8] = original_v8


class TestRollback:
    """Test rollback_to_version for supported versions."""

    def test_rollback_drops_tables(self, isolated_db):
        """Rollback to v7 should drop tables from v8+."""
        # Verify drafts table exists after full migration
        row = isolated_db.fetchone(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='drafts'"
        )
        assert row is not None

        # Rollback to v7
        isolated_db.rollback_to_version(7)

        # drafts should be gone
        row = isolated_db.fetchone(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='drafts'"
        )
        assert row is None

        # oauth_tokens should be gone
        row = isolated_db.fetchone(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='oauth_tokens'"
        )
        assert row is None

        # Version should be 7
        row = isolated_db.fetchone("SELECT MAX(version) FROM schema_version")
        assert row[0] == 7

    def test_rollback_noop_if_already_at_target(self, isolated_db):
        """Rollback to current version should be a no-op."""
        isolated_db.rollback_to_version(SCHEMA_VERSION)
        row = isolated_db.fetchone("SELECT MAX(version) FROM schema_version")
        assert row[0] == SCHEMA_VERSION

    def test_rollback_skips_missing_rollback_stmts(self, isolated_db):
        """Rollback for versions without ROLLBACKS entries should log warning and skip."""
        # Rollback to v3 — v4-v7 have no ROLLBACKS, should skip without error
        isolated_db.rollback_to_version(3)
        row = isolated_db.fetchone("SELECT MAX(version) FROM schema_version")
        # Should end at v7 (the last version we can't rollback past v8)
        # Actually v8 was rolled back, then v7-v4 have no rollback stmts so they stay
        # Wait — rollback_to_version iterates current down to target+1
        # current=11, target=3 -> rolls back 11,10,9,8 (all have ROLLBACKS)
        # then tries 7,6,5,4 (no ROLLBACKS -> skip)
        # So version should be 3 (skipped versions keep their schema_version row)
        # Let me check: the loop is range(current, target, -1) = range(11, 3, -1) = 11,10,9,8,7,6,5,4
        # v11 has ROLLBACKS -> drops bayes_meta, deletes v11
        # v10 has ROLLBACKS -> drops threads, deletes v10
        # v9 has ROLLBACKS -> drops oauth_tokens, deletes v9
        # v8 has ROLLBACKS -> drops drafts, deletes v8
        # v7 no ROLLBACKS -> skip
        # v6 no ROLLBACKS -> skip
        # v5 no ROLLBACKS -> skip
        # v4 no ROLLBACKS -> skip
        # Result: version should still be 7 (v8-v11 rolled back, v4-v7 kept)
        # But wait - DELETE happens only for versions with ROLLBACKS
        # So schema_version rows 4,5,6,7 remain, MAX = 7
        assert row[0] == 7

    def test_rollback_then_re_migrate(self, isolated_db):
        """After rollback, re-running migration should restore tables."""
        # Rollback to v7
        isolated_db.rollback_to_version(7)

        # Close and reconnect to trigger re-migration
        isolated_db.close()
        isolated_db._conn = None
        isolated_db.connect()

        # Version should be back at SCHEMA_VERSION
        row = isolated_db.fetchone("SELECT MAX(version) FROM schema_version")
        assert row[0] == SCHEMA_VERSION

        # Drafts table should exist again
        row = isolated_db.fetchone(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='drafts'"
        )
        assert row is not None


class TestRollbackSentries:
    """Verify ROLLBACKS dict consistency with MIGRATIONS."""

    def test_rollback_versions_are_subset_of_migrations(self):
        """Every key in ROLLBACKS must also be a key in MIGRATIONS."""
        for version in ROLLBACKS:
            assert version in MIGRATIONS, (
                f"ROLLBACKS[{version}] exists but MIGRATIONS[{version}] does not"
            )

    def test_rollback_versions_are_valid(self):
        """All ROLLBACKS keys should be <= SCHEMA_VERSION."""
        for version in ROLLBACKS:
            assert version <= SCHEMA_VERSION
            assert version > 0
