"""Tests for unified auth interface (T1.3).

Covers ensure_auth(), AuthError codes, and error code completeness.
"""

import pytest
from unittest.mock import patch, MagicMock

from openemail.core.auth import (
    AuthError,
    AuthErrorCode,
    ensure_auth,
)
from openemail.models.account import Account


class TestAuthError:
    """AuthError exception behavior."""

    def test_error_has_code(self):
        err = AuthError(AuthErrorCode.PASSWORD_MISSING, "test")
        assert err.code == AuthErrorCode.PASSWORD_MISSING
        assert err.message == "test"

    def test_error_str_contains_code(self):
        err = AuthError(AuthErrorCode.PASSWORD_MISSING, "密码为空")
        assert "AUTH_001" in str(err)

    def test_error_has_suggestion(self):
        err = AuthError(
            AuthErrorCode.OAUTH_TOKEN_EXPIRED,
            "token过期",
            "请重新授权",
        )
        assert err.suggestion == "请重新授权"


class TestAuthErrorCode:
    """Enum completeness and ordering."""

    def test_all_codes_unique(self):
        codes = [e.value for e in AuthErrorCode]
        assert len(codes) == len(set(codes))

    def test_codes_start_with_auth(self):
        for e in AuthErrorCode:
            assert e.value.startswith("AUTH_")

    def test_sequential_numbering(self):
        codes = [e.value for e in AuthErrorCode]
        expected = [f"AUTH_00{i}" for i in range(1, 6)]
        assert codes == expected


class TestEnsureAuthPassword:
    """ensure_auth() with password / app_password accounts."""

    def test_valid_password_no_error(self):
        account = Account(
            email="test@example.com",
            auth_type="password",
        )
        account.password = "my-secret"
        # Should not raise
        ensure_auth(account)

    def test_valid_app_password_no_error(self):
        account = Account(
            email="test@gmail.com",
            auth_type="app_password",
        )
        account.password = "abcd-efgh-ijkl"
        ensure_auth(account)

    def test_empty_password_raises(self):
        account = Account(
            email="test@example.com",
            auth_type="password",
        )
        # password is empty by default
        with pytest.raises(AuthError) as exc_info:
            ensure_auth(account)
        assert exc_info.value.code == AuthErrorCode.PASSWORD_MISSING

    def test_empty_app_password_raises(self):
        account = Account(
            email="test@gmail.com",
            auth_type="app_password",
        )
        with pytest.raises(AuthError) as exc_info:
            ensure_auth(account)
        assert exc_info.value.code == AuthErrorCode.PASSWORD_MISSING


class TestEnsureAuthOAuth2:
    """ensure_auth() with OAuth2 accounts."""

    def _make_oauth_account(self, **overrides) -> Account:
        account = Account(
            email="user@gmail.com",
            auth_type="oauth2",
            oauth_provider="google",
        )
        account.oauth_token = overrides.get("oauth_token", "valid-token")
        account.oauth_refresh = overrides.get("oauth_refresh", "refresh-token")
        account.token_expires_at = overrides.get("token_expires_at", "2099-01-01T00:00:00")
        return account

    def test_valid_token_no_refresh(self):
        """Token not expired — should pass without refresh."""
        account = self._make_oauth_account()
        mock_auth = MagicMock()
        mock_auth.check_and_refresh.return_value = True
        with patch(
            "openemail.core.oauth2_new.OAuthAuthenticator", return_value=mock_auth
        ):
            ensure_auth(account)
            mock_auth.check_and_refresh.assert_called_once_with(account)

    def test_token_expired_refresh_succeeds(self):
        """Token expired but refresh works — should pass."""
        account = self._make_oauth_account(token_expires_at="2020-01-01T00:00:00")
        mock_auth = MagicMock()
        mock_auth.check_and_refresh.return_value = True
        with patch(
            "openemail.core.oauth2_new.OAuthAuthenticator", return_value=mock_auth
        ):
            ensure_auth(account)

    def test_token_expired_refresh_fails(self):
        """Token expired and refresh fails — should raise."""
        account = self._make_oauth_account(token_expires_at="2020-01-01T00:00:00")
        mock_auth = MagicMock()
        mock_auth.check_and_refresh.return_value = False
        with patch(
            "openemail.core.oauth2_new.OAuthAuthenticator", return_value=mock_auth
        ):
            with pytest.raises(AuthError) as exc_info:
                ensure_auth(account)
            assert exc_info.value.code == AuthErrorCode.OAUTH_TOKEN_EXPIRED

    def test_no_refresh_token_raises(self):
        """No refresh token available — should raise."""
        account = self._make_oauth_account(oauth_refresh="", token_expires_at="")
        mock_auth = MagicMock()
        mock_auth.check_and_refresh.return_value = False
        with patch(
            "openemail.core.oauth2_new.OAuthAuthenticator", return_value=mock_auth
        ):
            with pytest.raises(AuthError) as exc_info:
                ensure_auth(account)
            assert exc_info.value.code == AuthErrorCode.OAUTH_TOKEN_EXPIRED

    def test_refresh_exception_raises(self):
        """Exception during refresh — should raise AUTH_REFRESH_FAILED."""
        account = self._make_oauth_account(token_expires_at="2020-01-01T00:00:00")
        mock_auth = MagicMock()
        mock_auth.check_and_refresh.side_effect = Exception("network error")
        with patch(
            "openemail.core.oauth2_new.OAuthAuthenticator", return_value=mock_auth
        ):
            with pytest.raises(AuthError) as exc_info:
                ensure_auth(account)
            assert exc_info.value.code == AuthErrorCode.OAUTH_REFRESH_FAILED
            assert "network error" in str(exc_info.value)


class TestEnsureAuthUnknownType:
    """ensure_auth() with unknown auth types."""

    def test_unknown_type_raises(self):
        account = Account(
            email="test@example.com",
            auth_type="kerberos",
        )
        with pytest.raises(AuthError) as exc_info:
            ensure_auth(account)
        assert exc_info.value.code == AuthErrorCode.UNKNOWN_AUTH_TYPE
