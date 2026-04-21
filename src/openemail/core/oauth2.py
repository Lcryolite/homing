from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Optional, Callable

from openemail.core.oauth2_new import (
    OAuthAuthenticator,
    OAuthError,
    OAuthErrorCode,
)

if TYPE_CHECKING:
    from openemail.models.account import Account

logger = logging.getLogger(__name__)


# 保持向后兼容的常量
OAUTH_CONFIGS = {
    "google": {
        "authorize_url": "https://accounts.google.com/o/oauth2/v2/auth",
        "token_url": "https://oauth2.googleapis.com/token",
        "scope": "https://mail.google.com/",
        "client_id": "",
        "client_secret": "",
    },
    "microsoft": {
        "authorize_url": "https://login.microsoftonline.com/common/oauth2/v2.0/authorize",
        "token_url": "https://login.microsoftonline.com/common/oauth2/v2.0/token",
        "scope": "https://outlook.office365.com/IMAP.AccessAsUser.All https://outlook.office365.com/SMTP.Send offline_access",
        "client_id": "",
        "client_secret": "",
    },
}

_REDIRECT_URI = "http://127.0.0.1:8742"

# 旧的回调处理器已移除，使用oauth2_new.py中的新实现


class OAuth2Authenticator:
    """OAuth2认证器（线程安全版本）"""

    def __init__(self, provider: str) -> None:
        self._authenticator = OAuthAuthenticator(provider)

    def set_client_credentials(self, client_id: str, client_secret: str) -> None:
        self._authenticator.set_client_credentials(client_id, client_secret)

    def get_authorization_url(self) -> tuple[str, str]:
        """获取授权URL"""
        try:
            return self._authenticator.get_authorization_url()
        except OAuthError as e:
            logger.error("获取授权URL失败: %s", e.message)
            raise

    def authorize_interactive(self) -> dict[str, str] | None:
        """交互式授权（阻塞式，UI应使用authorize_interactive_async）"""
        try:
            return self._authenticator.authorize_interactive()
        except OAuthError as e:
            logger.error("交互授权失败: %s", e.message)
            return None

    def authorize_interactive_async(
        self, callback: Callable[[Optional[dict[str, str]], Optional[OAuthError]], None]
    ) -> None:
        """异步交互式授权"""

        def auth_thread():
            try:
                tokens = self._authenticator.authorize_interactive()
                callback(tokens, None)
            except OAuthError as e:
                logger.error("异步授权失败: %s", e.message)
                callback(None, e)
            except Exception as e:
                logger.error("异步授权异常: %s", str(e))
                callback(
                    None,
                    OAuthError(
                        OAuthErrorCode.TOKEN_EXCHANGE_FAILED, f"授权异常: {str(e)}"
                    ),
                )

        # 在新线程中执行授权
        import threading

        thread = threading.Thread(target=auth_thread, daemon=True)
        thread.start()

    def refresh_token(self, refresh_token: str) -> dict[str, str] | None:
        """刷新令牌"""
        try:
            return self._authenticator.refresh_token(refresh_token)
        except OAuthError as e:
            logger.error("令牌刷新失败: %s", e.message)
            return None

    def check_and_refresh(self, account: Account) -> bool:
        """检查并刷新令牌"""
        return self._authenticator.check_and_refresh(account)

    @staticmethod
    def build_xoauth2_string(email: str, access_token: str) -> str:
        """构建XOAUTH2认证字符串"""
        from openemail.core.oauth2_new import OAuthAuthenticator

        return OAuthAuthenticator.build_xoauth2_string(email, access_token)

    @staticmethod
    def apply_to_account(account: Account, tokens: dict[str, str]) -> None:
        """将token信息应用到账户"""
        from openemail.core.oauth2_new import OAuthAuthenticator

        OAuthAuthenticator.apply_to_account(account, tokens)
