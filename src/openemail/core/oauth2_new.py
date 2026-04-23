from __future__ import annotations

import logging
import secrets
import time
import webbrowser
from datetime import datetime, timedelta
from enum import Enum
from http.server import HTTPServer, BaseHTTPRequestHandler
from threading import Thread
from typing import TYPE_CHECKING, Any, Optional, Callable, Tuple
from urllib.parse import parse_qs, urlparse

from authlib.integrations.httpx_client import OAuth2Client
from authlib.oauth2.rfc7636 import create_s256_code_challenge

from openemail.utils.exceptions import OAuthException

if TYPE_CHECKING:
    from openemail.models.account import Account

logger = logging.getLogger(__name__)


class OAuthErrorCode(str, Enum):
    """OAuth错误代码"""

    CONFIG_MISSING = "OAUTH_001"
    BROWSER_OPEN_FAILED = "OAUTH_002"
    CALLBACK_TIMEOUT = "OAUTH_003"
    CALLBACK_ERROR = "OAUTH_004"
    TOKEN_EXCHANGE_FAILED = "OAUTH_005"
    REFRESH_FAILED = "OAUTH_006"
    TOKEN_EXPIRED = "OAUTH_007"
    PROVIDER_UNSUPPORTED = "OAUTH_008"
    LOCAL_SERVER_FAILED = "OAUTH_009"
    UNKNOWN = "OAUTH_UNKNOWN"


class OAuthError(OAuthException):
    """OAuth错误类"""

    def __init__(self, code: OAuthErrorCode, message: str, suggestion: str = ""):
        super().__init__(message)
        self.code = code
        self.message = message
        self.suggestion = suggestion


def get_oauth_error_message(code: OAuthErrorCode) -> Tuple[str, str]:
    """获取OAuth错误码对应的用户提示和建议"""
    errors = {
        OAuthErrorCode.CONFIG_MISSING: (
            "OAuth客户端配置缺失",
            "请检查 ~/.config/openemail/oauth_creds.json 文件是否存在并配置正确",
        ),
        OAuthErrorCode.BROWSER_OPEN_FAILED: (
            "无法打开浏览器",
            "请手动访问授权链接或检查系统浏览器配置",
        ),
        OAuthErrorCode.CALLBACK_TIMEOUT: (
            "授权回调超时",
            "请重新尝试授权或检查网络连接",
        ),
        OAuthErrorCode.CALLBACK_ERROR: ("授权回调错误", "授权过程出现问题，请重新尝试"),
        OAuthErrorCode.TOKEN_EXCHANGE_FAILED: (
            "令牌交换失败",
            "请检查OAuth配置是否正确，或稍后重试",
        ),
        OAuthErrorCode.REFRESH_FAILED: (
            "令牌刷新失败",
            "需要重新授权，请点击重新授权按钮",
        ),
        OAuthErrorCode.TOKEN_EXPIRED: (
            "令牌已过期且无法恢复",
            "需要重新授权，请点击重新授权按钮",
        ),
        OAuthErrorCode.PROVIDER_UNSUPPORTED: (
            "不支持的OAuth服务商",
            "当前服务商不支持OAuth授权",
        ),
        OAuthErrorCode.LOCAL_SERVER_FAILED: (
            "本地回调服务器启动失败",
            "尝试使用其他端口或检查是否有其他程序占用端口",
        ),
    }
    return errors.get(code, ("未知错误", "请稍后重试或联系开发者"))


class OAuthConfigManager:
    """OAuth配置管理器"""

    @staticmethod
    def load_config() -> Optional[dict[str, dict[str, str]]]:
        """从配置加载OAuth凭据"""
        from openemail.config import settings

        try:
            config = settings.get_oauth_config()
            if not config:
                return None

            # 验证必需字段
            valid_config = {}
            for provider in ["google", "microsoft"]:
                if provider in config:
                    provider_config = config[provider]
                    client_id = provider_config.get("client_id", "").strip()

                    if not client_id:
                        logger.warning("Provider %s 缺少 client_id", provider)
                        continue

                    # Microsoft允许client_secret为空
                    client_secret = provider_config.get("client_secret", "").strip()

                    valid_config[provider] = {
                        "client_id": client_id,
                        "client_secret": client_secret,
                    }

            return valid_config if valid_config else None
        except Exception as e:
            logger.error("加载OAuth配置失败: %s", str(e))
            return None

    @staticmethod
    def is_provider_configured(provider: str) -> bool:
        """检查服务商是否已配置"""
        config = OAuthConfigManager.load_config()
        return config is not None and provider in config

    @staticmethod
    def get_provider_config(provider: str) -> Optional[dict[str, str]]:
        """获取特定服务商的配置"""
        config = OAuthConfigManager.load_config()
        return config.get(provider) if config else None


class OAuthCallbackServer:
    """异步OAuth回调服务器"""

    def __init__(self, port: int = 0):
        """
        初始化回调服务器

        Args:
            port: 监听端口，0表示自动选择可用端口
        """
        self.port = port
        self.server: Optional[HTTPServer] = None
        self.thread: Optional[Thread] = None
        self.auth_code: Optional[str] = None
        self.error: Optional[str] = None
        self.is_listening = False

    class _CallbackHandler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:
            """处理OAuth回调"""
            server = self.server._oauth_server_ref
            parsed = urlparse(self.path)
            params = parse_qs(parsed.query)

            if "code" in params:
                server.auth_code = params["code"][0]
                self.send_response(200)
                self.end_headers()
                self.wfile.write(
                    b"<html><body><h1>Authorization successful! You can close this tab.</h1></body></html>"
                )
            elif "error" in params:
                error_msg = params.get("error_description", [params["error"][0]])[0]
                server.error = error_msg
                self.send_response(400)
                self.end_headers()
                self.wfile.write(
                    f"<html><body><h1>Error: {error_msg}</h1></body></html>".encode(
                        "utf-8"
                    )
                )
            else:
                self.send_response(400)
                self.end_headers()

        def log_message(self, format: str, *args) -> None:
            """禁用默认日志"""
            pass

    def start(self) -> int:
        """启动回调服务器，返回实际使用的端口"""
        try:
            self.server = HTTPServer(("127.0.0.1", self.port), self._CallbackHandler)
            self.server._oauth_server_ref = self  # 传递引用给handler

            # 获取实际使用的端口
            self.port = self.server.server_address[1]

            def run_server():
                self.is_listening = True
                try:
                    self.server.serve_forever()
                except Exception as e:
                    logger.error("回调服务器运行异常: %s", str(e))
                finally:
                    self.is_listening = False

            self.thread = Thread(target=run_server, daemon=True)
            self.thread.start()

            # 等待服务器启动
            time.sleep(0.5)
            logger.info("OAuth回调服务器启动在端口 %s", self.port)
            return self.port

        except Exception as e:
            logger.error("启动回调服务器失败: %s", str(e))
            raise OAuthError(
                OAuthErrorCode.LOCAL_SERVER_FAILED, f"无法启动本地回调服务器: {str(e)}"
            )

    def wait_for_callback(
        self, timeout: int = 120
    ) -> Tuple[Optional[str], Optional[str]]:
        """
        等待回调

        Args:
            timeout: 超时时间（秒）

        Returns:
            (auth_code, error_message)
        """
        if not self.server:
            return None, "服务器未启动"

        start_time = time.time()
        while time.time() - start_time < timeout:
            if self.auth_code is not None:
                return self.auth_code, None
            elif self.error is not None:
                return None, self.error
            time.sleep(0.1)

        return None, "回调超时"

    def stop(self):
        """停止服务器"""
        if self.server:
            self.server.shutdown()
            if self.thread:
                self.thread.join(timeout=2)
            self.server = None
            self.thread = None


class OAuthAuthenticator:
    """OAuth认证器"""

    # Provider配置
    _PROVIDER_CONFIGS: dict[str, dict[str, Any]] = {
        "google": {
            "authorize_url": "https://accounts.google.com/o/oauth2/v2/auth",
            "token_url": "https://oauth2.googleapis.com/token",
            "scope": "https://mail.google.com/",
        },
        "microsoft": {
            "authorize_url": "https://login.microsoftonline.com/common/oauth2/v2.0/authorize",
            "token_url": "https://login.microsoftonline.com/common/oauth2/v2.0/token",
            "scope": "https://outlook.office365.com/IMAP.AccessAsUser.All https://outlook.office365.com/SMTP.Send https://outlook.office365.com/POP.AccessAsUser.All offline_access",
        },
    }

    def __init__(self, provider: str):
        """
        初始化OAuth认证器

        Args:
            provider: "google" 或 "microsoft"
        """
        if provider not in self._PROVIDER_CONFIGS:
            raise OAuthError(
                OAuthErrorCode.PROVIDER_UNSUPPORTED, f"不支持的OAuth服务商: {provider}"
            )

        self.provider = provider
        self.config = self._PROVIDER_CONFIGS[provider].copy()
        self.client: Optional[OAuth2Client] = None
        self._callback_server: Optional[OAuthCallbackServer] = None

        # 从配置文件加载凭据
        provider_config = OAuthConfigManager.get_provider_config(provider)
        if provider_config:
            self.set_client_credentials(
                provider_config["client_id"], provider_config["client_secret"]
            )
        else:
            logger.warning("Provider %s 未配置OAuth凭据", provider)

    def set_client_credentials(self, client_id: str, client_secret: str = "") -> None:
        """设置客户端凭据（Microsoft public-client 允许空 client_secret）"""
        self.config["client_id"] = client_id
        self.config["client_secret"] = client_secret

    def is_configured(self) -> bool:
        """检查是否已配置客户端凭据"""
        return bool(self.config.get("client_id"))

    def get_authorization_url(
        self, redirect_uri: Optional[str] = None
    ) -> Tuple[str, str]:
        """获取授权URL"""
        if not self.is_configured():
            raise OAuthError(
                OAuthErrorCode.CONFIG_MISSING, f"{self.provider} OAuth客户端配置缺失"
            )

        # 生成PKCE参数
        code_verifier = secrets.token_urlsafe(32)
        code_challenge = create_s256_code_challenge(code_verifier)

        # 创建OAuth客户端
        self.client = OAuth2Client(
            client_id=self.config["client_id"],
            client_secret=self.config.get("client_secret", ""),
            authorize_url=self.config["authorize_url"],
            token_endpoint=self.config["token_url"],
            redirect_uri=redirect_uri,
        )

        # 创建授权URL
        url, state = self.client.create_authorization_url(
            self.config["authorize_url"],
            scope=self.config["scope"],
            code_challenge=code_challenge,
            code_challenge_method="S256",
            state=code_verifier,
            access_type="offline",
            prompt="consent",
            redirect_uri=redirect_uri,
        )

        # 调试日志：记录生成的授权URL
        logger.debug(f"Generated OAuth2 authorization URL for {self.provider}")
        logger.debug(f"  Authorize URL: {self.config['authorize_url']}")
        logger.debug(f"  Redirect URI: {redirect_uri}")
        logger.debug(f"  Full URL length: {len(url)}")

        # 检查URL是否包含正确的redirect_uri
        if "redirect_uri=" in url:
            import urllib.parse

            parsed = urllib.parse.urlparse(url)
            query_params = urllib.parse.parse_qs(parsed.query)
            actual_redirect = query_params.get("redirect_uri", [""])[0]
            logger.debug(f"  Redirect URI in URL: {actual_redirect}")

            if actual_redirect != redirect_uri:
                logger.warning(
                    f"Redirect URI mismatch! Expected: {redirect_uri}, Got: {actual_redirect}"
                )
        else:
            logger.warning("Redirect URI parameter not found in authorization URL!")

        return url, code_verifier

    def authorize_interactive(self, timeout: int = 120) -> dict[str, str]:
        """
        交互式授权流程

        使用loopback redirect方式（Google推荐的桌面应用OAuth方式）：
        1. 启动本地HTTP服务器监听127.0.0.1:随机端口
        2. 用 http://127.0.0.1:端口 作为redirect_uri
        3. 打开浏览器让用户登录授权
        4. Google回调到本地服务器，自动获取授权码
        5. 用授权码交换token

        不需要在Google Console预配置redirect_uri。
        """
        if not self.is_configured():
            raise OAuthError(
                OAuthErrorCode.CONFIG_MISSING, f"{self.provider} OAuth客户端配置缺失"
            )

        # 1. 启动本地回调服务器
        self._callback_server = OAuthCallbackServer(port=0)
        port = self._callback_server.start()
        redirect_uri = f"http://127.0.0.1:{port}"
        logger.info("OAuth回调服务器启动在端口: %d", port)

        # 2. 生成授权URL（包含正确的redirect_uri）
        url, code_verifier = self.get_authorization_url(redirect_uri=redirect_uri)
        logger.info("授权URL已生成，长度: %d", len(url))

        # 3. 打开浏览器
        try:
            webbrowser.open(url)
        except Exception as e:
            self._callback_server.stop()
            raise OAuthError(
                OAuthErrorCode.BROWSER_OPEN_FAILED, f"无法打开浏览器: {str(e)}"
            )

        # 4. 等待回调
        auth_code, error_msg = self._callback_server.wait_for_callback(timeout)

        # 5. 停止服务器
        self._callback_server.stop()
        self._callback_server = None

        if error_msg:
            raise OAuthError(
                OAuthErrorCode.CALLBACK_ERROR
                if auth_code is None
                else OAuthErrorCode.CALLBACK_TIMEOUT,
                error_msg,
            )

        if not auth_code:
            raise OAuthError(OAuthErrorCode.CALLBACK_ERROR, "未收到授权码")

        # 6. 交换令牌
        try:
            tokens = self._exchange_code(auth_code, code_verifier)
            if not tokens:
                raise OAuthError(OAuthErrorCode.TOKEN_EXCHANGE_FAILED, "令牌交换失败")
            return tokens
        except Exception as e:
            if isinstance(e, OAuthError):
                raise
            raise OAuthError(
                OAuthErrorCode.TOKEN_EXCHANGE_FAILED, f"令牌交换异常: {str(e)}"
            )

    def _exchange_code(self, code: str, code_verifier: str) -> Optional[dict[str, str]]:
        """使用授权码交换令牌"""
        if self.client is None:
            return None

        try:
            token = self.client.fetch_token(
                self.config["token_url"],
                code=code,
                code_verifier=code_verifier,
            )

            expires_in = token.get("expires_in", 3600)
            expires_at = datetime.now() + timedelta(
                seconds=expires_in - 300
            )  # 提前5分钟

            return {
                "access_token": token.get("access_token", ""),
                "refresh_token": token.get("refresh_token", ""),
                "token_type": token.get("token_type", "Bearer"),
                "expires_in": str(expires_in),
                "expires_at": expires_at.isoformat(),
            }
        except Exception as e:
            logger.error("令牌交换失败: %s", str(e))
            return None

    def refresh_token(self, refresh_token: str) -> dict[str, str]:
        """刷新访问令牌"""
        if not self.is_configured():
            raise OAuthError(
                OAuthErrorCode.CONFIG_MISSING, f"{self.provider} OAuth客户端配置缺失"
            )

        # 确保客户端已初始化
        if self.client is None:
            self.client = OAuth2Client(
                client_id=self.config["client_id"],
                client_secret=self.config.get("client_secret", ""),
                token_endpoint=self.config["token_url"],
            )

        try:
            token = self.client.refresh_token(
                self.config["token_url"],
                refresh_token=refresh_token,
            )

            expires_in = token.get("expires_in", 3600)
            expires_at = datetime.now() + timedelta(
                seconds=expires_in - 300
            )  # 提前5分钟

            return {
                "access_token": token.get("access_token", ""),
                "refresh_token": token.get("refresh_token", refresh_token),
                "token_type": token.get("token_type", "Bearer"),
                "expires_in": str(expires_in),
                "expires_at": expires_at.isoformat(),
            }
        except Exception as e:
            logger.error("令牌刷新失败: %s", str(e))
            raise OAuthError(OAuthErrorCode.REFRESH_FAILED, f"令牌刷新失败: {str(e)}")

    def check_and_refresh(self, account: Account) -> bool:
        """
        检查并刷新令牌（如果需要）

        Returns:
            True - token有效或刷新成功
            False - 需要重新授权
        """
        if not account.oauth_refresh:
            return False

        # 检查令牌是否即将过期（5分钟内）
        expires_at_str = getattr(account, "token_expires_at", None)
        if expires_at_str:
            try:
                expires_at = datetime.fromisoformat(expires_at_str)
                if datetime.now() < expires_at:
                    # 令牌未过期
                    return True
            except (ValueError, TypeError):
                pass

        # 尝试刷新令牌
        try:
            new_tokens = self.refresh_token(account.oauth_refresh)
            self.apply_to_account(account, new_tokens)
            return True
        except OAuthError:
            # 刷新失败，需要重新授权
            return False

    @staticmethod
    def apply_to_account(account: Account, tokens: dict[str, str]) -> None:
        """将token信息应用到账户并持久化到数据库"""
        account.oauth_token = tokens.get("access_token", "")
        account.oauth_refresh = tokens.get("refresh_token", "")
        account.token_expires_at = tokens.get("expires_at", "")
        from openemail.core.connection_status import ConnectionStatus

        if account.oauth_token:
            account.update_status(ConnectionStatus.VERIFIED, force=True)
            account.last_verified_at = __import__("datetime").datetime.now().isoformat()
        account.save()

        if account.id and account.oauth_provider:
            OAuthAuthenticator.save_token_cache(
                account.id, account.oauth_provider, tokens
            )

    @staticmethod
    def build_xoauth2_string(email: str, access_token: str) -> str:
        """构建XOAUTH2认证字符串（原始格式，imaplib.authenticate会自动base64编码）"""
        return f"user={email}\x01auth=Bearer {access_token}\x01\x01"

    @staticmethod
    def save_token_cache(
        account_id: int, provider: str, tokens: dict[str, str]
    ) -> None:
        """持久化 token cache 到数据库"""
        from openemail.storage.database import db
        from datetime import datetime

        now = datetime.now().isoformat()
        data = {
            "account_id": account_id,
            "provider": provider,
            "access_token": tokens.get("access_token", ""),
            "refresh_token": tokens.get("refresh_token", ""),
            "token_type": tokens.get("token_type", "Bearer"),
            "scope": tokens.get("scope", ""),
            "expires_at": tokens.get("expires_at", ""),
            "updated_at": now,
        }

        existing = db.fetchone(
            "SELECT id FROM oauth_tokens WHERE account_id = ? AND provider = ?",
            (account_id, provider),
        )
        if existing:
            db.update("oauth_tokens", data, "id = ?", (existing["id"],))
        else:
            data["created_at"] = now
            db.insert("oauth_tokens", data)

    @staticmethod
    def load_token_cache(account_id: int, provider: str) -> Optional[dict[str, str]]:
        """从数据库加载 token cache"""
        from openemail.storage.database import db

        row = db.fetchone(
            "SELECT * FROM oauth_tokens WHERE account_id = ? AND provider = ?",
            (account_id, provider),
        )
        if not row:
            return None
        return {
            "access_token": row["access_token"],
            "refresh_token": row["refresh_token"] or "",
            "token_type": row["token_type"] or "Bearer",
            "scope": row["scope"] or "",
            "expires_at": row["expires_at"] or "",
        }

    @staticmethod
    def delete_token_cache(account_id: int, provider: str) -> None:
        """删除 token cache"""
        from openemail.storage.database import db

        db.delete(
            "oauth_tokens", "account_id = ? AND provider = ?", (account_id, provider)
        )


class OAuthManager:
    """全局OAuth管理器"""

    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._authenticators = {}
        return cls._instance

    def get_authenticator(self, provider: str) -> Optional[OAuthAuthenticator]:
        """获取认证器实例"""
        if provider not in self._authenticators:
            try:
                self._authenticators[provider] = OAuthAuthenticator(provider)
            except OAuthError:
                return None
        return self._authenticators[provider]

    def is_provider_available(self, provider: str) -> bool:
        """检查服务商是否可用"""
        authenticator = self.get_authenticator(provider)
        return authenticator is not None and authenticator.is_configured()

    def authorize(self, provider: str, callback: Optional[Callable] = None) -> None:
        """
        启动授权流程（异步）

        Args:
            provider: 服务商名称
            callback: 完成回调函数，签名 callback(tokens, error)
        """

        def auth_thread():
            try:
                authenticator = self.get_authenticator(provider)
                if not authenticator:
                    if callback:
                        callback(
                            None,
                            OAuthError(
                                OAuthErrorCode.CONFIG_MISSING, f"{provider} OAuth未配置"
                            ),
                        )
                    return

                tokens = authenticator.authorize_interactive()
                if callback:
                    callback(tokens=tokens, error=None)
            except OAuthError as e:
                logger.error("OAuth授权失败 [%s]: %s", e.code, e.message)
                if callback:
                    callback(tokens=None, error=e)
            except Exception as e:
                logger.error("OAuth授权异常: %s", str(e))
                if callback:
                    callback(
                        tokens=None, error=OAuthError(OAuthErrorCode.UNKNOWN, str(e))
                    )

        # 在后台线程中执行授权
        thread = Thread(target=auth_thread, daemon=True)
        thread.start()


# 全局实例
oauth_manager = OAuthManager()
