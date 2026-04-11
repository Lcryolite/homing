from __future__ import annotations

import base64
import json
import secrets
import webbrowser
from http.server import HTTPServer, BaseHTTPRequestHandler
from typing import Any
from urllib.parse import parse_qs, urlparse

from authlib.integrations.httpx_client import OAuth2Client
from authlib.oauth2.rfc7636 import create_s256_code_challenge

from openemail.models.account import Account


OAUTH_CONFIGS: dict[str, dict[str, Any]] = {
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
    "yahoo": {
        "authorize_url": "https://api.login.yahoo.com/oauth2/request_auth",
        "token_url": "https://api.login.yahoo.com/oauth2/get_token",
        "scope": "mail-w",
        "client_id": "",
        "client_secret": "",
    },
}

_REDIRECT_PORT = 8742
_REDIRECT_PATH = "/callback"
_REDIRECT_URI = f"http://127.0.0.1:{_REDIRECT_PORT}{_REDIRECT_PATH}"


class _CallbackHandler(BaseHTTPRequestHandler):
    auth_code: str = ""
    error: str = ""

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        params = parse_qs(parsed.query)

        if "code" in params:
            _CallbackHandler.auth_code = params["code"][0]
            self.send_response(200)
            self.end_headers()
            self.wfile.write(
                b"<html><body><h1>Authorization successful! You can close this tab.</h1></body></html>"
            )
        elif "error" in params:
            _CallbackHandler.error = params.get(
                "error_description", [params["error"][0]]
            )[0]
            self.send_response(400)
            self.end_headers()
            self.wfile.write(
                f"<html><body><h1>Error: {_CallbackHandler.error}</h1></body></html>".encode()
            )
        else:
            self.send_response(400)
            self.end_headers()

    def log_message(self, format, *args) -> None:
        pass


class OAuth2Authenticator:
    def __init__(self, provider: str) -> None:
        self._provider = provider
        self._config = OAUTH_CONFIGS.get(provider, {})
        self._client: OAuth2Client | None = None

    def set_client_credentials(self, client_id: str, client_secret: str) -> None:
        self._config["client_id"] = client_id
        self._config["client_secret"] = client_secret

    def get_authorization_url(self) -> tuple[str, str]:
        code_verifier = secrets.token_urlsafe(32)
        code_challenge = create_s256_code_challenge(code_verifier)

        self._client = OAuth2Client(
            client_id=self._config["client_id"],
            client_secret=self._config["client_secret"],
            authorize_url=self._config["authorize_url"],
            token_endpoint=self._config["token_url"],
            redirect_uri=_REDIRECT_URI,
            scope=self._config["scope"],
        )

        url, state = self._client.create_authorization_url(
            self._config["authorize_url"],
            code_challenge=code_challenge,
            code_challenge_method="S256",
            state=code_verifier,
            access_type="offline",
            prompt="consent",
        )
        return url, code_verifier

    def authorize_interactive(self) -> dict[str, str] | None:
        url, code_verifier = self.get_authorization_url()
        webbrowser.open(url)

        _CallbackHandler.auth_code = ""
        _CallbackHandler.error = ""

        server = HTTPServer(("127.0.0.1", _REDIRECT_PORT), _CallbackHandler)
        server.handle_request()

        if _CallbackHandler.error:
            return None
        if not _CallbackHandler.auth_code:
            return None

        return self._exchange_code(_CallbackHandler.auth_code, code_verifier)

    def _exchange_code(self, code: str, code_verifier: str) -> dict[str, str] | None:
        if self._client is None:
            return None
        try:
            token = self._client.fetch_token(
                self._config["token_url"],
                code=code,
                code_verifier=code_verifier,
            )
            return {
                "access_token": token.get("access_token", ""),
                "refresh_token": token.get("refresh_token", ""),
                "token_type": token.get("token_type", "Bearer"),
                "expires_in": str(token.get("expires_in", 0)),
            }
        except Exception:
            return None

    def refresh_token(self, refresh_token: str) -> dict[str, str] | None:
        if self._client is None:
            self._client = OAuth2Client(
                client_id=self._config["client_id"],
                client_secret=self._config["client_secret"],
                token_endpoint=self._config["token_url"],
            )
        try:
            token = self._client.refresh_token(
                self._config["token_url"],
                refresh_token=refresh_token,
            )
            return {
                "access_token": token.get("access_token", ""),
                "refresh_token": token.get("refresh_token", refresh_token),
                "token_type": token.get("token_type", "Bearer"),
                "expires_in": str(token.get("expires_in", 0)),
            }
        except Exception:
            return None

    @staticmethod
    def build_xoauth2_string(email: str, access_token: str) -> str:
        auth_string = f"user={email}\x01auth=Bearer {access_token}\x01\x01"
        return base64.b64encode(auth_string.encode()).decode()

    @staticmethod
    def apply_to_account(account: Account, tokens: dict[str, str]) -> None:
        account.oauth_token = tokens.get("access_token", "")
        account.oauth_refresh = tokens.get("refresh_token", "")
        account.save()
