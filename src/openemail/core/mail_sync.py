from __future__ import annotations

import asyncio
from datetime import datetime
from typing import Any

from PyQt6.QtCore import QThread, pyqtSignal, QMutex

from openemail.config import settings
from openemail.core.imap_client import IMAPClient
from openemail.core.pop3_client import POP3Client
from openemail.models.account import Account
from openemail.models.email import Email
from openemail.models.folder import Folder


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
            pass
        finally:
            self._loop.close()

    async def _sync_all_accounts(self) -> None:
        accounts = Account.get_all_active()
        for account in accounts:
            if not self._running:
                break
            self.sync_started.emit(account.id)
            try:
                total = await self._sync_account(account)
                self.sync_finished.emit(account.id, total)
            except Exception as e:
                self.sync_error.emit(account.id, str(e))

    async def _sync_account(self, account: Account) -> int:
        total_synced = 0

        if account.protocol == "imap":
            total_synced = await self._sync_imap(account)
        elif account.protocol == "pop3":
            total_synced = await self._sync_pop3(account)

        account.last_sync_at = datetime.now().isoformat()
        account.save()
        return total_synced

    async def _sync_imap(self, account: Account) -> int:
        client = IMAPClient(account)
        if not await client.connect():
            raise ConnectionError(f"Cannot connect to IMAP server for {account.email}")

        try:
            folders = Folder.get_by_account(account.id)
            if not folders:
                remote_folders = await client.list_folders()
                for rf in remote_folders:
                    name = rf["name"]
                    folder = Folder.get_by_name(account.id, name)
                    if folder is None:
                        folder = Folder(
                            account_id=account.id,
                            name=name,
                            path=rf["path"],
                            is_system=name in Folder.SYSTEM_FOLDERS,
                        )
                        folder.save()
                    folders.append(folder)

            total = 0
            for folder in folders:
                if not self._running:
                    break
                try:
                    count = await client.sync_folder(folder.name, folder.id)
                    total += count
                    if count > 0:
                        folder.update_unread()
                        self.folder_updated.emit(
                            account.id, folder.name, folder.unread_count
                        )
                except Exception:
                    pass

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

    def __init__(self, account_id: int, parent=None) -> None:
        super().__init__(parent)
        self._account_id = account_id
        self._running = False

    def run(self) -> None:
        self._running = True
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            loop.run_until_complete(self._idle_loop())
        except Exception:
            pass
        finally:
            loop.close()

    async def _idle_loop(self) -> None:
        account = Account.get_by_id(self._account_id)
        if account is None or account.protocol != "imap":
            return

        client = IMAPClient(account)
        if not await client.connect():
            self.idle_error.emit(self._account_id, "Cannot connect for IDLE")
            return

        try:
            while self._running:
                try:
                    results = await client.idle("INBOX", timeout=300)
                    if results and self._running:
                        self.new_mail_notification.emit(
                            self._account_id, account.email, "New mail received"
                        )
                except Exception as e:
                    if self._running:
                        self.idle_error.emit(self._account_id, str(e))
                        await asyncio.sleep(30)
        finally:
            await client.disconnect()

    def stop(self) -> None:
        self._running = False
        self.wait(5000)


class MailSyncManager:
    _instance: MailSyncManager | None = None

    def __new__(cls) -> MailSyncManager:
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self) -> None:
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
        self._idle_workers[account_id] = worker
        worker.start()

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


mail_sync_manager = MailSyncManager()
