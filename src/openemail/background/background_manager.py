from __future__ import annotations

import asyncio
import logging
import threading
from typing import Optional

from openemail.utils.calendar_reminder import calendar_reminder_manager

logger = logging.getLogger(__name__)


class BackgroundTaskManager:
    """后台任务管理器，管理所有需要在后台运行的任务."""

    _instance: Optional[BackgroundTaskManager] = None

    def __new__(cls) -> BackgroundTaskManager:
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self) -> None:
        if not self._initialized:
            self._running = False
            self._tasks: list[asyncio.Task] = []
            self._event_loop: Optional[asyncio.AbstractEventLoop] = None
            self._thread: Optional[threading.Thread] = None
            self._initialized = True

    def start(self) -> None:
        """启动所有后台任务."""
        if self._running:
            logger.warning("Background task manager already running")
            return

        logger.info("Starting background task manager")
        self._running = True

        # 创建新线程来运行 asyncio 事件循环
        def run_event_loop():
            """在新线程中运行 asyncio 事件循环."""
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

            self._event_loop = loop

            try:
                # 启动所有后台任务
                asyncio.run_coroutine_threadsafe(self._start_tasks(), loop)
                loop.run_forever()
            except Exception as e:
                logger.error(f"Event loop error: {e}")
            finally:
                tasks = asyncio.all_tasks(loop=loop)
                for task in tasks:
                    task.cancel()
                loop.run_until_complete(asyncio.gather(*tasks, return_exceptions=True))
                loop.close()

        # 启动后台线程
        self._thread = threading.Thread(target=run_event_loop, daemon=True)
        self._thread.start()

        logger.info("Background task manager started")

    async def _start_tasks(self) -> None:
        """启动所有后台任务协程."""
        # 启动日历提醒管理器
        await calendar_reminder_manager.start()
        logger.info("Calendar reminder manager started")

        # 可以在这里添加其他后台任务

        logger.info("All background tasks started")

    def stop(self) -> None:
        """停止所有后台任务."""
        if not self._running:
            return

        logger.info("Stopping background task manager")
        self._running = False

        # 停止日历提醒管理器
        if self._event_loop and not self._event_loop.is_closed():
            asyncio.run_coroutine_threadsafe(
                calendar_reminder_manager.stop(), self._event_loop
            )

        # 停止事件循环
        if self._event_loop and self._event_loop.is_running():
            self._event_loop.call_soon_threadsafe(self._event_loop.stop)

        # 等待线程结束
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=5.0)

        logger.info("Background task manager stopped")

    def is_running(self) -> bool:
        """检查后台任务管理器是否正在运行."""
        return self._running

    def schedule_reminder(
        self,
        title: str,
        time: str,  # ISO格式的时间字符串
        minutes_before: int = 15,
        description: str = "",
        location: str = "",
    ) -> None:
        """调度一个自定义提醒."""
        try:
            # 解析时间
            from datetime import datetime

            event_time = datetime.fromisoformat(time.replace("Z", "+00:00"))

            if self._event_loop and self._event_loop.is_running():
                # 在主应用线程中执行
                calendar_reminder_manager.schedule_custom_reminder(
                    title=title,
                    time=event_time,
                    minutes_before=minutes_before,
                    description=description,
                    location=location,
                )
                logger.debug(f"Scheduled reminder: {title} at {time}")
            else:
                logger.warning("Cannot schedule reminder: event loop not running")
        except Exception as e:
            logger.error(f"Error scheduling reminder: {e}")


# 全局实例
background_task_manager = BackgroundTaskManager()
