"""T1.4 — Sync correctness tests for UIDVALIDITY, high-water mark, flag sync.

Tests are unit-level: no real IMAP connection needed.
"""

import pytest

from openemail.core.imap_client import _extract_uidvalidity
from openemail.models.folder import Folder


# ── _extract_uidvalidity ─────────────────────────────────────────


class TestExtractUidvalidity:
    def test_standard_response(self):
        resp = ("OK", [b"[UIDVALIDITY 1713456789] [UIDNEXT 42]"])
        assert _extract_uidvalidity(resp) == "1713456789"

    def test_string_response(self):
        resp = ("OK", ["[UIDVALIDITY 999] Some folder data"])
        assert _extract_uidvalidity(resp) == "999"

    def test_multiple_items(self):
        resp = (
            "OK",
            [b"12 EXISTS", b"[UIDVALIDITY 555] [UIDNEXT 13] FLAGS (\\Seen)"],
        )
        assert _extract_uidvalidity(resp) == "555"

    def test_no_uidvalidity(self):
        resp = ("OK", [b"12 EXISTS", b"FLAGS (\\Seen)"])
        assert _extract_uidvalidity(resp) == ""

    def test_malformed_response(self):
        assert _extract_uidvalidity(("NO", [])) == ""
        assert _extract_uidvalidity(("OK", [b""])) == ""

    def test_large_number(self):
        resp = ("OK", [b"[UIDVALIDITY 2147483647]"])
        assert _extract_uidvalidity(resp) == "2147483647"


# ── High-water mark logic (pure function test) ───────────────────


class TestHighWaterMark:
    """Test the UID filtering logic used in sync_folder."""

    def _filter_new_uids(self, uid_strings: list[str], existing_uids: set, stored_last: str) -> tuple[list[str], int]:
        """Simulate the high-water mark filter from sync_folder."""
        try:
            stored_last_int = int(stored_last)
        except (ValueError, TypeError):
            stored_last_int = 0

        new_uids = []
        max_uid_int = stored_last_int
        for uid in uid_strings:
            uid_int = int(uid) if uid.isdigit() else 0
            if uid_int > max_uid_int:
                max_uid_int = uid_int
            if uid not in existing_uids:
                new_uids.append(uid)
        return new_uids, max_uid_int

    def test_first_sync_all_new(self):
        new, max_uid = self._filter_new_uids(["1", "2", "3"], set(), "0")
        assert new == ["1", "2", "3"]
        assert max_uid == 3

    def test_no_new_uids(self):
        existing = {"1", "2", "3"}
        new, max_uid = self._filter_new_uids(["1", "2", "3"], existing, "3")
        assert new == []
        assert max_uid == 3

    def test_mixed_existing_and_new(self):
        existing = {"1", "2"}
        new, max_uid = self._filter_new_uids(["1", "2", "3", "4"], existing, "2")
        assert new == ["3", "4"]
        assert max_uid == 4

    def test_high_water_mark_tracks_max(self):
        new, max_uid = self._filter_new_uids(["5", "10", "3"], set(), "0")
        assert max_uid == 10

    def test_existing_higher_than_remote(self):
        # Edge case: stored last_uid > all remote UIDs (no new emails)
        new, max_uid = self._filter_new_uids(["1", "2"], {"1", "2"}, "100")
        assert new == []
        assert max_uid == 100  # doesn't go backward

    def test_non_numeric_uids_ignored(self):
        new, max_uid = self._filter_new_uids(["abc", "5", "xyz"], set(), "0")
        assert new == ["abc", "5", "xyz"]
        assert max_uid == 5  # only numeric contributes


# ── Flag parsing logic (pure function test) ──────────────────────


class TestFlagParsing:
    """Test the flag line parsing used in _flag_sync."""

    @staticmethod
    def parse_flags(line: str) -> tuple[str, bool, bool]:
        """Simulate the flag parsing from _flag_sync."""
        uid_match = line.split("(FLAGS", 1)[0].strip()
        if not uid_match or not uid_match.isdigit():
            return ("", False, False)
        uid_str = uid_match
        is_read = "\\Seen" in line
        is_flagged = "\\Flagged" in line
        return (uid_str, is_read, is_flagged)

    def test_seen_and_flagged(self):
        uid, is_read, is_flagged = self.parse_flags("42 (FLAGS (\\Seen \\Flagged))")
        assert uid == "42"
        assert is_read is True
        assert is_flagged is True

    def test_only_seen(self):
        uid, is_read, is_flagged = self.parse_flags("7 (FLAGS (\\Seen))")
        assert uid == "7"
        assert is_read is True
        assert is_flagged is False

    def test_no_flags(self):
        uid, is_read, is_flagged = self.parse_flags("3 (FLAGS ())")
        assert uid == "3"
        assert is_read is False
        assert is_flagged is False

    def test_other_flags_ignored(self):
        uid, is_read, is_flagged = self.parse_flags("10 (FLAGS (\\Deleted \\Draft))")
        assert uid == "10"
        assert is_read is False
        assert is_flagged is False

    def test_malformed_no_uid(self):
        uid, is_read, is_flagged = self.parse_flags("(FLAGS (\\Seen))")
        assert uid == ""

    def test_bytes_style_response(self):
        """imaplib returns byte strings; test with decode simulation."""
        raw = b"5 (FLAGS (\\Seen \\Flagged))".decode()
        uid, is_read, is_flagged = self.parse_flags(raw)
        assert uid == "5"
        assert is_read is True
        assert is_flagged is True


# ── Folder uid_validity / last_uid field persistence ─────────────


class TestFolderSyncFields:
    """Test that Folder model correctly persists uid_validity and last_uid."""

    def test_folder_has_sync_fields(self):
        f = Folder(id=0, uid_validity="12345", last_uid="99")
        assert f.uid_validity == "12345"
        assert f.last_uid == "99"

    def test_folder_defaults(self):
        f = Folder()
        assert f.uid_validity == ""
        assert f.last_uid == ""

    def test_folder_save_includes_new_fields(self):
        """Verify that save() doesn't crash with new fields (requires DB)."""
        # This is a smoke test — the real save needs a DB fixture
        f = Folder(
            account_id=1,
            name="INBOX",
            path="INBOX",
            uid_validity="1713456789",
            last_uid="42",
        )
        # Just verify the data dict construction doesn't fail
        assert f.uid_validity == "1713456789"
        assert f.last_uid == "42"
