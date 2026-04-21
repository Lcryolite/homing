"""Tests for connection tester integration with status machine (T1.2)."""

import pytest

from openemail.core.connection_tester import (
    ConnectionTestErrorCategory,
    ConnectionTestResult,
    ConnectionTestStatus,
    ConnectionTestSummary,
    ProtocolType,
)
from openemail.core.connection_status import (
    AccountValidationResult,
    ConnectionStatus,
    can_transition,
    get_next_status,
    get_suggestions_for_categories,
    get_status_display,
)


class TestGetNextStatusWithCategories:
    """Test get_next_status uses error_categories, not string matching."""

    def test_auth_error_category_maps_to_auth_failed(self):
        vr = AccountValidationResult(
            inbound_success=False,
            test_id="t1",
            error_categories=["auth_error"],
        )
        assert get_next_status(ConnectionStatus.VALIDATING, vr) == ConnectionStatus.AUTH_FAILED

    def test_authentication_error_category_maps_to_auth_failed(self):
        vr = AccountValidationResult(
            inbound_success=False,
            test_id="t1",
            error_categories=["authentication_error"],
        )
        assert get_next_status(ConnectionStatus.VALIDATING, vr) == ConnectionStatus.AUTH_FAILED

    def test_network_error_category_maps_to_network_failed(self):
        vr = AccountValidationResult(
            inbound_success=False,
            test_id="t1",
            error_categories=["network_error"],
        )
        assert get_next_status(ConnectionStatus.VALIDATING, vr) == ConnectionStatus.NETWORK_FAILED

    def test_dns_error_category_maps_to_network_failed(self):
        vr = AccountValidationResult(
            inbound_success=False,
            test_id="t1",
            error_categories=["dns_error"],
        )
        assert get_next_status(ConnectionStatus.VALIDATING, vr) == ConnectionStatus.NETWORK_FAILED

    def test_ssl_error_category_maps_to_network_failed(self):
        vr = AccountValidationResult(
            inbound_success=False,
            test_id="t1",
            error_categories=["ssl_error"],
        )
        assert get_next_status(ConnectionStatus.VALIDATING, vr) == ConnectionStatus.NETWORK_FAILED

    def test_timeout_error_category_maps_to_network_failed(self):
        vr = AccountValidationResult(
            inbound_success=False,
            test_id="t1",
            error_categories=["timeout_error"],
        )
        assert get_next_status(ConnectionStatus.VALIDATING, vr) == ConnectionStatus.NETWORK_FAILED

    def test_success_maps_to_verified(self):
        vr = AccountValidationResult(
            inbound_success=True,
            test_id="t1",
        )
        assert get_next_status(ConnectionStatus.VALIDATING, vr) == ConnectionStatus.VERIFIED

    def test_multiple_categories_auth_wins(self):
        """When both auth and network errors present, auth_failed takes priority."""
        vr = AccountValidationResult(
            inbound_success=False,
            test_id="t1",
            error_categories=["network_error", "auth_error"],
        )
        assert get_next_status(ConnectionStatus.VALIDATING, vr) == ConnectionStatus.AUTH_FAILED

    def test_empty_categories_with_error_message(self):
        """Error message present but no categories — should still fail."""
        vr = AccountValidationResult(
            inbound_success=False,
            test_id="t1",
            error_message="something went wrong",
            error_categories=[],
        )
        result = get_next_status(ConnectionStatus.VALIDATING, vr)
        assert result == ConnectionStatus.AUTH_FAILED


class TestGetSuggestionsForCategories:
    """Test error category to human-readable suggestion mapping."""

    def test_auth_error_suggestion(self):
        suggestions = get_suggestions_for_categories(["auth_error"])
        assert len(suggestions) == 1
        assert "密码" in suggestions[0]

    def test_network_error_suggestion(self):
        suggestions = get_suggestions_for_categories(["network_error"])
        assert len(suggestions) == 1
        assert "网络" in suggestions[0]

    def test_dns_error_suggestion(self):
        suggestions = get_suggestions_for_categories(["dns_error"])
        assert len(suggestions) == 1
        assert "DNS" in suggestions[0]

    def test_ssl_error_suggestion(self):
        suggestions = get_suggestions_for_categories(["ssl_error"])
        assert len(suggestions) == 1
        assert "SSL" in suggestions[0]

    def test_multiple_categories_no_duplicates(self):
        suggestions = get_suggestions_for_categories(
            ["auth_error", "authentication_error"]
        )
        # Both map to the same suggestion, should deduplicate
        assert len(suggestions) == 1

    def test_unknown_category_ignored(self):
        suggestions = get_suggestions_for_categories(["unknown_category"])
        assert len(suggestions) == 0

    def test_empty_categories(self):
        suggestions = get_suggestions_for_categories([])
        assert len(suggestions) == 0

    def test_mixed_categories(self):
        suggestions = get_suggestions_for_categories(
            ["auth_error", "dns_error", "ssl_error"]
        )
        assert len(suggestions) == 3


class TestStatusDisplayMapping:
    """Test that ConnectionStatus maps to correct display strings."""

    def test_verified_display(self):
        assert get_status_display(ConnectionStatus.VERIFIED) == "已验证"

    def test_auth_failed_display(self):
        assert get_status_display(ConnectionStatus.AUTH_FAILED) == "认证失败"

    def test_network_failed_display(self):
        assert get_status_display(ConnectionStatus.NETWORK_FAILED) == "连接失败"

    def test_disabled_display(self):
        assert get_status_display(ConnectionStatus.DISABLED) == "已禁用"


class TestStateTransitions:
    """Test state machine transitions are consistent."""

    def test_from_auth_failed_can_retry(self):
        assert can_transition(ConnectionStatus.AUTH_FAILED, ConnectionStatus.VALIDATING)

    def test_from_network_failed_can_retry(self):
        assert can_transition(ConnectionStatus.NETWORK_FAILED, ConnectionStatus.VALIDATING)

    def test_from_auth_failed_can_disable(self):
        assert can_transition(ConnectionStatus.AUTH_FAILED, ConnectionStatus.DISABLED)

    def test_verified_cannot_go_back_to_validating(self):
        assert not can_transition(ConnectionStatus.VERIFIED, ConnectionStatus.VALIDATING)

    def test_sync_ready_cannot_go_to_verified(self):
        assert not can_transition(ConnectionStatus.SYNC_READY, ConnectionStatus.VERIFIED)
