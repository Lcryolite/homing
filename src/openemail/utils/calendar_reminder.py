from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timedelta
from typing import List, Optional, Tuple

from openemail.models.calendar_event import CalendarEvent
from openemail.utils.desktop_notifier import desktop_notifier

logger = logging.getLogger(__name__)


class CalendarReminderManager:
    """日历提醒管理器."""

    _instance: Optional[CalendarReminderManager] = None

    def __new__(cls) -> CalendarReminderManager:
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self) -> None:
        if not self._initialized:
            self._tasks: List[asyncio.Task] = []
            self._running = False
            self._initialized = True

    async def start(self) -> None:
        """启动提醒管理器."""
        if self._running:
            logger.warning("Calendar reminder manager already running")
            return

        self._running = True
        logger.info("Starting calendar reminder manager")

        # 启动扫描任务
        scan_task = asyncio.create_task(self._scan_loop())
        self._tasks.append(scan_task)

    async def stop(self) -> None:
        """停止提醒管理器."""
        if not self._running:
            return

        logger.info("Stopping calendar reminder manager")
        self._running = False

        # 取消所有任务
        for task in self._tasks:
            task.cancel()

        # 等待任务完成
        if self._tasks:
            await asyncio.gather(*self._tasks, return_exceptions=True)
        self._tasks.clear()

        logger.info("Calendar reminder manager stopped")

    async def _scan_loop(self) -> None:
        """扫描循环，定期检查即将到来的日历事件."""
        scan_interval = 60  # 每分钟扫描一次

        while self._running:
            try:
                await self._scan_upcoming_events()
            except Exception as e:
                logger.error(f"Error scanning calendar events: {e}")

            await asyncio.sleep(scan_interval)

    async def _scan_upcoming_events(self) -> None:
        """扫描即将到来的日历事件，检查是否需要提醒."""
        now = datetime.now()
        check_end = now + timedelta(days=1)  # 检查未来24小时

        # 转换为ISO格式字符串以便于查询
        now_str = now.isoformat()
        end_str = check_end.isoformat()

        # 获取未来24小时内的所有事件
        upcoming_events = CalendarEvent.get_by_date_range(now_str, end_str)

        if not upcoming_events:
            return

        logger.debug(f"Found {len(upcoming_events)} upcoming calendar events")

        # 对每个事件检查是否需要提醒
        for event in upcoming_events:
            await self._check_and_notify_event(event)

    async def _check_and_notify_event(self, event: CalendarEvent) -> None:
        """检查事件是否需要提醒并发送通知."""
        # 如果没有设置提醒，跳过
        if event.reminder <= 0:
            return

        # 解析事件时间
        try:
            event_time = datetime.fromisoformat(event.start_time.replace("Z", "+00:00"))
        except ValueError:
            logger.warning(
                f"Cannot parse event time for event {event.id}: {event.start_time}"
            )
            return

        # 计算提醒时间
        reminder_time = event_time - timedelta(minutes=event.reminder)
        now = datetime.now()

        # 如果现在已经过了提醒时间但还没到事件时间，发送提醒
        if reminder_time <= now < event_time:
            # 检查是否已经发送过提醒
            if not await self._should_send_reminder(event.id, event_time):
                return

            # 发送提醒
            await self._send_reminder(event)

    async def _should_send_reminder(self, event_id: int, event_time: datetime) -> bool:
        """检查是否应该发送提醒。

        使用简单的本地缓存来避免在短时间内重复发送同一事件的提醒。
        """
        # TODO: 实现基于数据库的更复杂的提醒状态逻辑
        # 目前，我们只是简单检查如果事件已经开始或已经结束，就不发送提醒

        now = datetime.now()
        # 如果事件已经开始，不发送提醒
        if event_time <= now:
            return False

        # 对于重复事件，需要更复杂的状态管理（未来实现）
        return True

    async def _send_reminder(self, event: CalendarEvent) -> None:
        """发送日历事件提醒."""
        try:
            event_time = datetime.fromisoformat(event.start_time.replace("Z", "+00:00"))
            time_str = event_time.strftime("%Y-%m-%d %H:%M")

            # 构建通知内容
            title = f"日历提醒: {event.title}"

            body_parts = []
            if event.description:
                desc_short = event.description[:60] + (
                    "..." if len(event.description) > 60 else ""
                )
                body_parts.append(f"内容: {desc_short}")

            body_parts.append(f"时间: {time_str}")

            if event.location:
                body_parts.append(f"地点: {event.location}")

            body = "\n".join(body_parts)

            # 发送桌面通知
            success = desktop_notifier.notify(
                title=title,
                body=body,
                icon="appointment-soon",  # GNOME 日历图标
                urgency="normal",
                timeout=10000,  # 10秒显示时间
            )

            if success:
                logger.info(f"Sent calendar reminder for event: {event.title}")

                # TODO: 记录提醒已发送的状态到数据库
                # 这样可以避免重复发送
            else:
                logger.warning(
                    f"Failed to send calendar reminder for event: {event.title}"
                )

        except Exception as e:
            logger.error(f"Error sending calendar reminder: {e}")

    def schedule_custom_reminder(
        self,
        title: str,
        time: datetime,
        minutes_before: int = 15,
        description: str = "",
        location: str = "",
    ) -> None:
        """调度自定义提醒（不需要保存到数据库）."""
        # 计算提醒时间
        reminder_time = time - timedelta(minutes=minutes_before)

        # 如果是过去的提醒，立即触发
        if reminder_time <= datetime.now():
            self._send_custom_reminder_now(title, time, description, location)
        else:
            # 安排未来提醒
            delay = (reminder_time - datetime.now()).total_seconds()
            asyncio.create_task(
                self._schedule_single_reminder(
                    delay, title, time, description, location
                )
            )

    async def _schedule_single_reminder(
        self,
        delay: float,
        title: str,
        time: datetime,
        description: str = "",
        location: str = "",
    ) -> None:
        """安排单个自定义提醒."""
        try:
            await asyncio.sleep(delay)
            self._send_custom_reminder_now(title, time, description, location)
        except asyncio.CancelledError:
            logger.debug(f"Custom reminder cancelled: {title}")
        except Exception as e:
            logger.error(f"Error in scheduled custom reminder: {e}")

    def _send_custom_reminder_now(
        self, title: str, time: datetime, description: str = "", location: str = ""
    ) -> None:
        """立即发送自定义提醒."""
        time_str = time.strftime("%Y-%m-%d %H:%M")

        title_msg = f"提醒: {title}"
        body_parts = []

        if description:
            desc_short = description[:80] + ("..." if len(description) > 80 else "")
            body_parts.append(f"内容: {desc_short}")

        body_parts.append(f"时间: {time_str}")

        if location:
            body_parts.append(f"地点: {location}")

        body = "\n".join(body_parts)

        # 发送通知
        desktop_notifier.notify(
            title=title_msg,
            body=body,
            icon="appointment-soon",
            urgency="normal",
            timeout=8000,
        )

    def get_upcoming_reminders(
        self, hours_ahead: int = 24
    ) -> List[Tuple[CalendarEvent, datetime]]:
        """获取即将到来的所有提醒."""
        now = datetime.now()
        end_time = now + timedelta(hours=hours_ahead)

        now_str = now.isoformat()
        end_str = end_time.isoformat()

        events = CalendarEvent.get_by_date_range(now_str, end_str)
        reminders = []

        for event in events:
            if event.reminder > 0:
                try:
                    event_time = datetime.fromisoformat(
                        event.start_time.replace("Z", "+00:00")
                    )
                    reminder_time = event_time - timedelta(minutes=event.reminder)

                    if now <= reminder_time <= end_time:
                        reminders.append((event, reminder_time))
                except ValueError:
                    continue

        # 按提醒时间排序
        reminders.sort(key=lambda x: x[1])
        return reminders


# 全局实例
calendar_reminder_manager = CalendarReminderManager()
