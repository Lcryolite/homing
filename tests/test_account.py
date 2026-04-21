"""Tests for provider presets and account model (T1.1)."""

from __future__ import annotations

from openemail.models.account import (
    PROVIDER_PRESETS,
    AUTH_TYPE_LABELS,
    _PROVIDER_STATUS_LABELS,
)


class TestProviderPresets:
    """Every provider preset must be structurally valid."""

    def test_all_presets_have_required_fields(self):
        required = {"name", "protocol", "auth_type", "supported_auth_types", "status"}
        for key, preset in PROVIDER_PRESETS.items():
            missing = required - set(preset.keys())
            assert not missing, f"{key} missing fields: {missing}"

    def test_auth_type_in_supported_list(self):
        """Default auth_type must be inside supported_auth_types."""
        for key, preset in PROVIDER_PRESETS.items():
            assert preset["auth_type"] in preset["supported_auth_types"], (
                f"{key}: auth_type '{preset['auth_type']}' not in "
                f"supported_auth_types {preset['supported_auth_types']}"
            )

    def test_status_is_valid(self):
        valid = {"stable", "experimental"}
        for key, preset in PROVIDER_PRESETS.items():
            assert preset["status"] in valid, (
                f"{key}: invalid status '{preset['status']}'"
            )

    def test_imap_presets_have_host(self):
        for key, preset in PROVIDER_PRESETS.items():
            if preset["protocol"] == "imap":
                assert preset.get("imap_host"), f"{key}: IMAP preset missing imap_host"
                assert preset.get("smtp_host"), f"{key}: IMAP preset missing smtp_host"

    def test_activesync_presets_have_eas_host(self):
        for key, preset in PROVIDER_PRESETS.items():
            if preset["protocol"] == "activesync":
                assert preset.get("eas_host"), f"{key}: EAS preset missing eas_host"

    def test_no_auth_type_password(self):
        """'password' auth type is legacy — all presets should use 'app_password' or 'oauth2'."""
        for key, preset in PROVIDER_PRESETS.items():
            assert preset["auth_type"] != "password", (
                f"{key}: uses legacy 'password' auth_type, should be 'app_password' or 'oauth2'"
            )

    def test_outlook_activesync_is_experimental(self):
        assert PROVIDER_PRESETS["outlook_activesync"]["status"] == "experimental"

    def test_gmail_supports_both_password_and_oauth(self):
        supported = PROVIDER_PRESETS["gmail"]["supported_auth_types"]
        assert "app_password" in supported
        assert "oauth2" in supported

    def test_outlook_only_oauth(self):
        assert PROVIDER_PRESETS["outlook"]["supported_auth_types"] == ["oauth2"]

    def test_display_name_with_status_suffix(self):
        """Provider name display should include experimental suffix when applicable."""
        for key, preset in PROVIDER_PRESETS.items():
            suffix = _PROVIDER_STATUS_LABELS.get(preset.get("status", ""), "")
            display = f"{preset['name']}{suffix}"
            if preset["status"] == "experimental":
                assert "实验性" in display, f"{key}: experimental missing suffix"
            else:
                assert "实验性" not in display, f"{key}: stable should not have suffix"

    def test_auth_type_labels_cover_all_types(self):
        """AUTH_TYPE_LABELS should cover all auth types used in presets."""
        used_types = set()
        for preset in PROVIDER_PRESETS.values():
            used_types.update(preset["supported_auth_types"])
        for auth_type in used_types:
            assert auth_type in AUTH_TYPE_LABELS, (
                f"auth_type '{auth_type}' used in presets but missing from AUTH_TYPE_LABELS"
            )

    def test_provider_count(self):
        """There should be exactly 8 provider presets."""
        assert len(PROVIDER_PRESETS) == 8
