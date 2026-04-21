from openemail.models.folder import (
    Folder,
    SYSTEM_FOLDERS,
)


class TestFolderSpecialUse:
    def test_rfc6154_flags_resolved(self):
        assert Folder._resolve_special_use("INBOX", ["\\Inbox"]) == "inbox"
        assert Folder._resolve_special_use("Sent", ["\\Sent"]) == "sent"
        assert Folder._resolve_special_use("Drafts", ["\\Drafts"]) == "drafts"
        assert Folder._resolve_special_use("Spam", ["\\Junk"]) == "spam"
        assert Folder._resolve_special_use("Trash", ["\\Trash"]) == "trash"
        assert Folder._resolve_special_use("Archive", ["\\Archive"]) == "archive"

    def test_fallback_name_matching(self):
        assert Folder._resolve_special_use("INBOX", []) == "inbox"
        assert Folder._resolve_special_use("Sent Items", []) == "sent"
        assert Folder._resolve_special_use("Deleted Items", []) == "trash"
        assert Folder._resolve_special_use("Junk Email", []) == "spam"
        assert Folder._resolve_special_use("Starred", []) == "flagged"

    def test_flags_take_priority_over_name(self):
        assert Folder._resolve_special_use("Custom", ["\\Sent"]) == "sent"

    def test_no_match_returns_none(self):
        assert Folder._resolve_special_use("Personal", []) is None
        assert Folder._resolve_special_use("Work", ["\\All"]) is None

    def test_discover_system_folders_dedup(self):
        from unittest.mock import patch

        remote = [
            {"name": "INBOX", "path": "INBOX", "flags": ["\\Inbox"]},
            {"name": "Sent", "path": "Sent", "flags": ["\\Sent"]},
            {"name": "Trash", "path": "Trash", "flags": ["\\Trash"]},
        ]
        with patch("openemail.models.folder.db"):
            result = Folder.discover_system_folders(99999, remote)
            special_uses = [f.special_use for f in result]
            assert len(special_uses) == len(set(special_uses))

    def test_system_folders_constant(self):
        assert "INBOX" in SYSTEM_FOLDERS
        assert "Sent" in SYSTEM_FOLDERS
        assert "Drafts" in SYSTEM_FOLDERS
        assert "Spam" in SYSTEM_FOLDERS
        assert "Trash" in SYSTEM_FOLDERS
