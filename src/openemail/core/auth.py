"""Unified authentication interface for IMAP and SMTP.

Provides a single entry point to ensure an account's credentials are
valid before a connection attempt. Handles OAuth2 token refresh,
password validation, and auth-type dispatch.

Usage::

    from openemail.core.auth import ensure_auth, AuthError

    try:
        ensure_auth(account)
    except AuthError as exc:
        # surface exc.code + exc.message to the UI
"""

from __future__ import annotations

import logging
from enum import Enum
from typing import TYPE_CHECKING

from openemail.utils.exceptions import AuthException

if TYPE_CHECKING:
    from openemail.models.account import Account

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Error codes — shared between IMAP and SMTP
# ---------------------------------------------------------------------------

class AuthErrorCode(str, Enum):
    """Machine-readable auth failure codes."""

    PASSWORD_MISSING = "AUTH_001"
    OAUTH_NO_REFRESH = "AUTH_002"
    OAUTH_REFRESH_FAILED = "AUTH_003"
    OAUTH_TOKEN_EXPIRED = "AUTH_004"
    UNKNOWN_AUTH_TYPE = "AUTH_005"


class AuthError(AuthException):
    """Raised when pre-connection auth validation fails."""

    def __init__(self, code: AuthErrorCode, message: str, suggestion: str = "") -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.suggestion = suggestion

    def __str__(self) -> str:
        return f"[{self.code.value}] {self.message}"


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def ensure_auth(account: Account) -> None:
    """Validate or refresh credentials *before* connecting.

    Raises :class:`AuthError` if the account cannot authenticate.
    For OAuth2 accounts this ensures the access token is fresh.
    For password accounts this checks that a password is present.
    """
    auth_type = account.auth_type

    if auth_type == "oauth2":
        _ensure_oauth(account)
    elif auth_type in ("password", "app_password"):
        _ensure_password(account)
    else:
        raise AuthError(
            AuthErrorCode.UNKNOWN_AUTH_TYPE,
            f"未知的认证类型: {auth_type}",
            "请在账户设置中选择正确的认证方式",
        )


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _ensure_oauth(account: Account) -> None:
    """Ensure the OAuth2 access token is valid, refreshing if needed."""
    from openemail.core.oauth2_new import OAuthAuthenticator

    authenticator = OAuthAuthenticator(account.oauth_provider or "google")

    try:
        ok = authenticator.check_and_refresh(account)
    except Exception as e:  # noqa: BLE001
        logger.error("OAuth token refresh error for %s: %s", account.email, e)
        raise AuthError(
            AuthErrorCode.OAUTH_REFRESH_FAILED,
            f"OAuth 令牌刷新异常: {e}",
            "请尝试重新授权",
        ) from e

    if not ok:
        raise AuthError(
            AuthErrorCode.OAUTH_TOKEN_EXPIRED,
            "OAuth 令牌已过期且无法自动刷新",
            "请在账户设置中重新授权",
        )


def _ensure_password(account: Account) -> None:
    """Check that a password / app-password is present."""
    if not account.password:
        raise AuthError(
            AuthErrorCode.PASSWORD_MISSING,
            "密码为空",
            "请在账户设置中填写密码或应用专用密码",
        )
