"""轻量连接缓存 — 按 account_id 缓存 IMAP/SMTP 连接，减少频繁建连。

使用方式:
    from openemail.core.connection_manager import connection_manager

    # 获取或创建 IMAP 连接
    client = await connection_manager.get_imap(account)

    # 用完后归还（可选，断开时自动失效）
    connection_manager.release_imap(account.id)

    # SMTP 同理
    smtp = await connection_manager.get_smtp(account)
"""

from __future__ import annotations

import asyncio
import logging
import time
from typing import Any

logger = logging.getLogger(__name__)

# 连接最大空闲秒数（超过则回收）
MAX_IDLE_SECONDS = 300
# 连接最大存活秒数
MAX_LIFETIME_SECONDS = 1800
# 后台清理间隔（秒）
CLEANUP_INTERVAL = 60


class _CachedConn:
    __slots__ = ("conn", "created_at", "last_used_at")

    def __init__(self, conn: Any) -> None:
        self.conn = conn
        self.created_at = time.monotonic()
        self.last_used_at = self.created_at

    def touch(self) -> None:
        self.last_used_at = time.monotonic()

    def is_expired(self) -> bool:
        now = time.monotonic()
        return (now - self.last_used_at > MAX_IDLE_SECONDS) or (
            now - self.created_at > MAX_LIFETIME_SECONDS
        )


class ConnectionManager:
    """线程安全的连接缓存管理器。"""

    _instance: ConnectionManager | None = None
    _new_lock = __import__("threading").Lock()

    def __new__(cls) -> ConnectionManager:
        with cls._new_lock:
            if cls._instance is None:
                cls._instance = super().__new__(cls)
                cls._instance._init()
        return cls._instance

    def _init(self) -> None:
        self._imap_cache: dict[int, _CachedConn] = {}
        self._smtp_cache: dict[int, _CachedConn] = {}
        self._lock = asyncio.Lock()
        self._cleanup_task: asyncio.Task | None = None

    # ── IMAP ──────────────────────────────────────────────

    async def get_imap(self, account) -> Any:
        """返回可用的 IMAPClient（已连接）。"""
        from openemail.core.imap_client import IMAPClient

        aid = account.id
        async with self._lock:
            cached = self._imap_cache.get(aid)
            if cached and not cached.is_expired():
                cached.touch()
                return cached.conn
            # 过期或不存在 → 先丢弃旧连接
            if cached:
                try:
                    await cached.conn.disconnect()
                except Exception:
                    pass
                del self._imap_cache[aid]

        # 新建连接（锁外，不阻塞其他 account）
        client = IMAPClient(account)
        ok = await client.connect()
        if not ok:
            raise ConnectionError(f"IMAP connect failed for account {aid}")
        async with self._lock:
            self._imap_cache[aid] = _CachedConn(client)
        return client

    async def release_imap(self, account_id: int) -> None:
        async with self._lock:
            cached = self._imap_cache.pop(account_id, None)
        if cached:
            try:
                await cached.conn.disconnect()
            except Exception:
                pass

    # ── SMTP ──────────────────────────────────────────────

    async def get_smtp(self, account) -> Any:
        """返回可用的 SMTPClient（已连接）。"""
        from openemail.core.smtp_client import SMTPClient

        aid = account.id
        async with self._lock:
            cached = self._smtp_cache.get(aid)
            if cached and not cached.is_expired():
                cached.touch()
                return cached.conn
            if cached:
                try:
                    await cached.conn.disconnect()
                except Exception:
                    pass
                del self._smtp_cache[aid]

        client = SMTPClient(account)
        ok = await client.connect()
        if not ok:
            raise ConnectionError(f"SMTP connect failed for account {aid}")
        async with self._lock:
            self._smtp_cache[aid] = _CachedConn(client)
        return client

    async def release_smtp(self, account_id: int) -> None:
        async with self._lock:
            cached = self._smtp_cache.pop(account_id, None)
        if cached:
            try:
                await cached.conn.disconnect()
            except Exception:
                pass

    # ── 后台清理 ─────────────────────────────────────────

    async def start_cleanup(self) -> None:
        if self._cleanup_task is None or self._cleanup_task.done():
            self._cleanup_task = asyncio.ensure_future(self._cleanup_loop())

    async def stop_cleanup(self) -> None:
        if self._cleanup_task:
            self._cleanup_task.cancel()
            try:
                await self._cleanup_task
            except asyncio.CancelledError:
                pass
            self._cleanup_task = None

    async def _cleanup_loop(self) -> None:
        while True:
            await asyncio.sleep(CLEANUP_INTERVAL)
            await self._evict_expired()

    async def _evict_expired(self) -> None:
        async with self._lock:
            for cache in (self._imap_cache, self._smtp_cache):
                expired_ids = [
                    aid for aid, c in cache.items() if c.is_expired()
                ]
                for aid in expired_ids:
                    cached = cache.pop(aid)
                    try:
                        await cached.conn.disconnect()
                    except Exception:
                        pass
                    logger.debug("Evicted expired connection for account %d", aid)


connection_manager = ConnectionManager()
