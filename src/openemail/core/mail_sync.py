from __future__ import annotations

import asyncio
import logging
from datetime import datetime

from PyQt6.QtCore import QThread, pyqtSignal, QMutex, QObject

logger = logging.getLogger(__name__)

from openemail.config import settings  # noqa: E402
from openemail.core.imap_client import IMAPClient  # noqa: E402
from openemail.core.pop3_client import POP3Client  # noqa: E402
from openemail.core.activesync_client import MockActiveSyncClient  # noqa: E402
from openemail.models.account import Account  # noqa: E402
from openemail.models.email import Email  # noqa: E402
from openemail.models.folder import Folder  # noqa: E402


class SyncWorker(QThread):
    sync_started = pyqtSignal(int)
    sync_finished = pyqtSignal(int, int)
    sync_error = pyqtSignal(int, str)
    new_emails = pyqtSignal(int, list)
    folder_updated = pyqtSignal(int, str, int)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._running = False
        self._mutex = QMutex()
        self._loop: asyncio.AbstractEventLoop | None = None

    def run(self) -> None:
        self._running = True
        self._loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self._loop)
        try:
            self._loop.run_until_complete(self._sync_all_accounts())
        except Exception as e:
            logger.debug("Suppressed exception in %s: %s", __name__, e)
        finally:
            self._loop.close()

    async def _sync_all_accounts(self) -> None:
        accounts = Account.get_syncable()  # 只获取可同步的账号
        for account in accounts:
            if not self._running:
                break

            # 记录同步日志
            logger.info(
                "开始同步账号: %s (状态: %s)",
                account.email,
                account.connection_status.value,
            )

            self.sync_started.emit(account.id)
            try:
                total = await self._sync_account(account)
                self.sync_finished.emit(account.id, total)

                # 记录同步成功日志
                logger.info("账号同步完成: %s, 处理邮件: %d", account.email, total)

            except Exception as e:
                logger.error("同步账号 %s 时出错: %s", account.email, str(e))
                self.sync_error.emit(account.id, str(e))

                # 增加失败计数
                try:
                    account.sync_fail_count += 1
                    account.last_error_code = "SYNC_ERROR"
                    account.last_error_at = datetime.now().isoformat()
                    account.save()
                except Exception as save_error:
                    logger.error("更新账号失败计数时出错: %s", str(save_error))

    async def _sync_account(self, account: Account) -> int:
        total_synced = 0

        # OAuth2: 刷新过期 token
        if account.is_oauth_enabled() and not account.check_and_refresh_token():
            raise ConnectionError(
                f"OAuth token refresh failed for {account.email}, re-authorization needed"
            )

        if account.protocol == "imap":
            total_synced = await self._sync_imap(account)
        elif account.protocol == "pop3":
            total_synced = await self._sync_pop3(account)
        elif account.protocol == "activesync":
            total_synced = await self._sync_activesync(account)

        account.last_sync_at = datetime.now().isoformat()
        account.save()
        return total_synced

    async def _sync_imap(self, account: Account) -> int:
        client = IMAPClient(account)
        if not await client.connect():
            raise ConnectionError(f"Cannot connect to IMAP server for {account.email}")

        try:
            folders = Folder.get_by_account(account.id)
            logger.info("数据库中找到 %d 个文件夹", len(folders))
            if not folders:
                remote_folders = await client.list_folders()
                logger.info("远程发现 %d 个文件夹", len(remote_folders))
                Folder.discover_system_folders(account.id, remote_folders)
                for rf in remote_folders:
                    name = rf["name"]
                    folder = Folder.get_by_name(account.id, name)
                    if folder is None:
                        flags = rf.get("flags", [])
                        special_use = Folder._resolve_special_use(name, flags) or ""
                        folder = Folder(
                            account_id=account.id,
                            name=name,
                            path=rf["path"],
                            is_system=bool(special_use),
                            special_use=special_use,
                        )
                        folder.save()
                    folders.append(folder)

            total = 0
            for folder in folders:
                if not self._running:
                    break
                try:
                    logger.info("同步文件夹: %s (id=%d)", folder.name, folder.id)
                    count = await client.sync_folder(folder.name, folder.id)
                    total += count
                    logger.info("文件夹 %s 同步完成: %d 封新邮件", folder.name, count)
                    if count > 0:
                        folder.update_unread()
                        self.folder_updated.emit(
                            account.id, folder.name, folder.unread_count
                        )
                except Exception as e:
                    logger.warning("文件夹 %s 同步失败: %s", folder.name, e)

            return total
        finally:
            await client.disconnect()

    async def _sync_pop3(self, account: Account) -> int:
        client = POP3Client(account)
        if not client.connect():
            raise ConnectionError(f"Cannot connect to POP3 server for {account.email}")

        try:
            inbox = Folder.get_by_name(account.id, "INBOX")
            if inbox is None:
                inbox = Folder(
                    account_id=account.id, name="INBOX", path="INBOX", is_system=True
                )
                inbox.save()

            total = client.sync_emails(inbox.id)
            if total > 0:
                inbox.update_unread()
                self.folder_updated.emit(account.id, "INBOX", inbox.unread_count)

            return total
        finally:
            client.disconnect()

    def stop(self) -> None:
        self._running = False
        self.wait(5000)


class IdleWorker(QThread):
    new_mail_notification = pyqtSignal(int, str, str)
    idle_error = pyqtSignal(int, str)

    IDLE_RESET_SECONDS = 1740  # 29 minutes per RFC 2177
    RECONNECT_DELAY_SECONDS = 30
    NOOP_POLL_INTERVAL_SECONDS = 60
    MAX_RECONNECT_ATTEMPTS = 5

    def __init__(self, account_id: int, parent=None) -> None:
        super().__init__(parent)
        self._account_id = account_id
        self._running = False
        self._idle_supported = True

    def run(self) -> None:
        self._running = True
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            loop.run_until_complete(self._idle_loop())
        except Exception as e:
            logger.debug("Suppressed exception in %s: %s", __name__, e)
        finally:
            loop.close()

    async def _idle_loop(self) -> None:
        account = Account.get_by_id(self._account_id)
        if account is None or account.protocol != "imap":
            return

        reconnect_attempts = 0
        while self._running:
            try:
                client = IMAPClient(account)
                # OAuth2: 刷新过期 token
                if account.is_oauth_enabled() and not account.check_and_refresh_token():
                    raise ConnectionError(
                        f"OAuth token refresh failed for {account.email}, re-authorization needed"
                    )
                if not await client.connect():
                    raise ConnectionError("Cannot connect for IDLE")

                self._idle_supported = await self._check_idle_capability(client)
                reconnect_attempts = 0

                if self._idle_supported:
                    await self._do_idle_loop(client, account)
                else:
                    await self._do_noop_loop(client, account)

            except Exception as e:
                if not self._running:
                    break
                reconnect_attempts += 1
                self.idle_error.emit(self._account_id, str(e))
                if reconnect_attempts >= self.MAX_RECONNECT_ATTEMPTS:
                    logger.error(
                        "IDLE max reconnect attempts reached for account %d",
                        self._account_id,
                    )
                    break
                await asyncio.sleep(self.RECONNECT_DELAY_SECONDS)

    async def _check_idle_capability(self, client: IMAPClient) -> bool:
        try:
            if hasattr(client._client, "capability"):
                caps = await client._client.capability()
                if caps and "IDLE" in str(caps).upper():
                    return True
            return False
        except Exception:
            return False

    async def _do_idle_loop(self, client: IMAPClient, account: Account) -> None:
        import time

        try:
            while self._running:
                idle_start = time.monotonic()
                try:
                    results = await client.idle(
                        "INBOX", timeout=self.IDLE_RESET_SECONDS
                    )
                    if results and self._running:
                        self.new_mail_notification.emit(
                            self._account_id, account.email, "New mail received"
                        )
                except Exception as e:
                    if not self._running:
                        break
                    self.idle_error.emit(self._account_id, str(e))
                    raise

                elapsed = time.monotonic() - idle_start
                if elapsed >= self.IDLE_RESET_SECONDS - 10:
                    logger.debug("IDLE 29min reset for account %d", self._account_id)
        except Exception:
            raise

    async def _do_noop_loop(self, client: IMAPClient, account: Account) -> None:
        logger.info(
            "IDLE not supported, falling back to NOOP polling for account %d",
            self._account_id,
        )
        try:
            while self._running:
                try:
                    if hasattr(client._client, "noop"):
                        await client._client.noop()
                    await asyncio.sleep(self.NOOP_POLL_INTERVAL_SECONDS)
                    self.new_mail_notification.emit(
                        self._account_id, account.email, "Poll check"
                    )
                except Exception:
                    if not self._running:
                        break
                    raise
        except Exception:
            raise

    def stop(self) -> None:
        self._running = False
        self.wait(5000)


class MailSyncManager(QObject):
    _instance: MailSyncManager | None = None

    # Proxy signals forwarded from SyncWorker
    sync_finished = pyqtSignal(int, int)
    sync_error = pyqtSignal(int, str)

    def __new__(cls) -> MailSyncManager:
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        if hasattr(self, "_initialized"):
            return
        self._initialized = True
        self._sync_worker: SyncWorker | None = None
        self._idle_workers: dict[int, IdleWorker] = {}
        self._auto_sync_timer = None

    def sync_all(self) -> None:
        if self._sync_worker and self._sync_worker.isRunning():
            return
        self._sync_worker = SyncWorker()
        # Forward worker signals to manager-level signals
        self._sync_worker.sync_finished.connect(self.sync_finished)
        self._sync_worker.sync_error.connect(self.sync_error)
        self._sync_worker.start()

    def stop_sync(self) -> None:
        if self._sync_worker and self._sync_worker.isRunning():
            self._sync_worker.stop()

    def start_idle(self, account_id: int) -> None:
        if (
            account_id in self._idle_workers
            and self._idle_workers[account_id].isRunning()
        ):
            return
        worker = IdleWorker(account_id)
        worker.new_mail_notification.connect(self._on_new_mail_notification)
        self._idle_workers[account_id] = worker
        worker.start()

    def _on_new_mail_notification(
        self, account_id: int, account_email: str, message: str
    ) -> None:
        from openemail.utils.desktop_notifier import desktop_notifier

        desktop_notifier.notify_new_mail(
            sender="New Mail",
            subject=message,
            account_email=account_email,
        )

    def stop_idle(self, account_id: int) -> None:
        worker = self._idle_workers.pop(account_id, None)
        if worker and worker.isRunning():
            worker.stop()

    def stop_all_idle(self) -> None:
        for account_id in list(self._idle_workers.keys()):
            self.stop_idle(account_id)

    def start_auto_sync(self) -> None:
        from PyQt6.QtCore import QTimer

        interval = settings.sync_interval * 60 * 1000
        self._auto_sync_timer = QTimer()
        self._auto_sync_timer.timeout.connect(self.sync_all)
        self._auto_sync_timer.start(interval)

    def stop_auto_sync(self) -> None:
        if self._auto_sync_timer:
            self._auto_sync_timer.stop()
            self._auto_sync_timer = None

    def stop_all(self) -> None:
        self.stop_sync()
        self.stop_all_idle()
        self.stop_auto_sync()

    async def _sync_activesync(self, account: Account) -> int:
        """ActiveSync协议同步"""
        try:
            # 使用Mock客户端进行测试
            client = MockActiveSyncClient(account)
            # 实际环境中使用: client = ActiveSyncClient(account)

            if not await client.connect():
                raise ConnectionError(
                    f"Cannot connect to ActiveSync server for {account.email}"
                )

            try:
                # 同步文件夹
                remote_folders = await client.folder_sync()
                total_synced = 0

                for rf in remote_folders:
                    folder_name = rf["name"]
                    folder_type = rf.get("type", "")

                    # 确保文件夹存在
                    folder = Folder.get_by_name(account.id, folder_name)
                    if folder is None:
                        folder = Folder(
                            account_id=account.id,
                            name=folder_name,
                            path=folder_name,
                            is_system=folder_type
                            in ["inbox", "sent", "drafts", "trash"],
                        )
                        folder.save()

                    # 同步邮件
                    sync_result = await client.email_sync(rf["id"], limit=50)
                    emails_data = sync_result.get("emails", [])

                    for email_data in emails_data:
                        try:
                            email_obj = Email(
                                account_id=account.id,
                                folder_id=folder.id,
                                uid=email_data["id"],
                                subject=email_data.get("subject", ""),
                                sender_addr=email_data.get("from", ""),
                                date=email_data.get("date", ""),
                                is_read=email_data.get("read", False),
                                is_flagged=email_data.get("flagged", False),
                                preview_text=email_data.get("preview", ""),
                            )

                            # 保存邮件
                            existing = Email.get_by_uid(account.id, email_obj.uid)
                            if existing:
                                # 更新现有邮件
                                existing.subject = email_obj.subject
                                existing.is_read = email_obj.is_read
                                existing.is_flagged = email_obj.is_flagged
                                existing.save()
                            else:
                                email_obj.save()
                                total_synced += 1

                        except Exception as e:
                            logger.error("处理ActiveSync邮件失败: %s", e)

                    # 更新文件夹计数
                    if emails_data:
                        self._sync_worker.folder_updated.emit(
                            account.id, folder.name, len(emails_data)
                        )

                return total_synced

            finally:
                await client.disconnect()

        except Exception as e:
            logger.error("ActiveSync同步失败 %s: %s", account.email, e)
            return 0


mail_sync_manager = MailSyncManager()
