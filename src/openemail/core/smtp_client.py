from __future__ import annotations

import asyncio
import logging
import smtplib
import ssl
from email.message import EmailMessage
from typing import Any

logger = logging.getLogger(__name__)

try:
    import aiosmtplib

    AIOSMTPLIB_AVAILABLE = True
except ImportError:
    aiosmtplib = None
    AIOSMTPLIB_AVAILABLE = False

from openemail.core.oauth2 import OAuth2Authenticator
from openemail.models.account import Account


class SMTPClient:
    def __init__(self, account: Account) -> None:
        self._account = account

    async def send(
        self,
        to: list[str],
        subject: str,
        body_text: str = "",
        body_html: str = "",
        cc: list[str] | None = None,
        bcc: list[str] | None = None,
        reply_to: str | None = None,
        attachments: list[dict[str, bytes]] | None = None,
        in_reply_to: str | None = None,
        references: str | None = None,
    ) -> bool:
        from openemail.core.mail_builder import MailBuilder

        builder = MailBuilder()
        builder.set_from(self._account.email, self._account.name)
        builder.set_to(to)
        if cc:
            builder.set_cc(cc)
        if bcc:
            builder.set_bcc(bcc)
        builder.set_subject(subject)
        if body_text:
            builder.set_text_body(body_text)
        if body_html:
            builder.set_html_body(body_html)
        if reply_to:
            builder.set_reply_to(reply_to)
        if in_reply_to:
            builder.set_in_reply_to(in_reply_to)
        if references:
            builder.set_references(references)
        if attachments:
            for att in attachments:
                builder.add_attachment(
                    att["filename"],
                    att["data"],
                    att.get("mime_type", "application/octet-stream"),
                )

        message = builder.build()
        message_str = message.as_string()

        # Collect all recipients (to + cc + bcc) for SMTP envelope
        all_recipients = list(to) + list(cc or []) + list(bcc or [])

        try:
            use_tls = self._account.ssl_mode == "ssl"
            start_tls = self._account.ssl_mode == "starttls"

            if self._account.auth_type == "oauth2":
                auth_string = OAuth2Authenticator.build_xoauth2_string(
                    self._account.email, self._account.oauth_token
                )
                await self._send_with_xoauth2(
                    message_str, all_recipients, use_tls, start_tls, auth_string
                )
            elif AIOSMTPLIB_AVAILABLE:
                await aiosmtplib.send(
                    message_str,
                    recipients=all_recipients,
                    hostname=self._account.smtp_host,
                    port=self._account.smtp_port,
                    username=self._account.email,
                    password=self._account.password,
                    use_tls=use_tls,
                    start_tls=start_tls,
                )
            else:
                await self._send_sync(message_str, all_recipients, use_tls, start_tls)
            return True
        except Exception as e:
            logger.error("SMTP send error for %s: %s", self._account.email, e)
            return False

    async def _send_sync(
        self, message_str: str, recipients: list[str], use_tls: bool, start_tls: bool
    ) -> None:
        """使用标准库smtplib发送邮件"""
        if use_tls:
            ctx = ssl.create_default_context()
            server = smtplib.SMTP_SSL(
                self._account.smtp_host,
                self._account.smtp_port,
                context=ctx,
                timeout=30,
            )
        else:
            server = smtplib.SMTP(
                self._account.smtp_host, self._account.smtp_port, timeout=30
            )
            if start_tls:
                ctx = ssl.create_default_context()
                server.starttls(context=ctx)

        server.login(self._account.email, self._account.password)
        server.sendmail(self._account.email, recipients, message_str)
        server.quit()

    async def _send_with_xoauth2(
        self, message_str: str, recipients: list[str], use_tls: bool, start_tls: bool, auth_string: str
    ) -> None:
        if AIOSMTPLIB_AVAILABLE:
            smtp = aiosmtplib.SMTP(
                hostname=self._account.smtp_host,
                port=self._account.smtp_port,
                use_tls=use_tls,
            )
            await smtp.connect()
            if start_tls:
                await smtp.starttls()
            await smtp.auth_xoauth2(self._account.email, auth_string)
            await smtp.sendmail(self._account.email, recipients, message_str)
            await smtp.quit()
        else:
            if use_tls:
                ctx = ssl.create_default_context()
                server = smtplib.SMTP_SSL(
                    self._account.smtp_host,
                    self._account.smtp_port,
                    context=ctx,
                    timeout=30,
                )
            else:
                server = smtplib.SMTP(
                    self._account.smtp_host, self._account.smtp_port, timeout=30
                )
                if start_tls:
                    ctx = ssl.create_default_context()
                    server.starttls(context=ctx)
            auth_bytes = auth_string.encode("utf-8")
            server.authenticate("XOAUTH2", lambda _: auth_bytes)
            server.sendmail(self._account.email, recipients, message_str)
            server.quit()

    async def test_connection(self) -> bool:
        try:
            use_tls = self._account.ssl_mode == "ssl"
            start_tls = self._account.ssl_mode == "starttls"

            if AIOSMTPLIB_AVAILABLE:
                if use_tls:
                    smtp = aiosmtplib.SMTP(
                        hostname=self._account.smtp_host,
                        port=self._account.smtp_port,
                        use_tls=True,
                    )
                    await smtp.connect()
                else:
                    smtp = aiosmtplib.SMTP(
                        hostname=self._account.smtp_host,
                        port=self._account.smtp_port,
                    )
                    await smtp.connect()
                    if start_tls:
                        await smtp.starttls()

                if self._account.auth_type == "password":
                    await smtp.login(self._account.email, self._account.password)

                await smtp.quit()
            else:
                # 标准库回退
                if use_tls:
                    ctx = ssl.create_default_context()
                    server = smtplib.SMTP_SSL(
                        self._account.smtp_host,
                        self._account.smtp_port,
                        context=ctx,
                        timeout=10,
                    )
                else:
                    server = smtplib.SMTP(
                        self._account.smtp_host, self._account.smtp_port, timeout=10
                    )
                    if start_tls:
                        ctx = ssl.create_default_context()
                        server.starttls(context=ctx)

                if self._account.auth_type == "password":
                    server.login(self._account.email, self._account.password)

                server.quit()

            return True
        except Exception as e:
            logger.error("SMTP test connection error: %s", e)
            return False
