from __future__ import annotations

import logging
import shutil
import subprocess
from typing import Optional

logger = logging.getLogger(__name__)


class DesktopNotifier:
    """桌面通知发送器，使用 D-Bus freedesktop.org 通知规范"""

    _instance: Optional[DesktopNotifier] = None

    def __new__(cls) -> DesktopNotifier:
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._available = None
        return cls._instance

    def is_available(self) -> bool:
        if self._available is None:
            self._available = shutil.which("notify-send") is not None
            if not self._available:
                try:
                    import dbus

                    self._available = True
                except ImportError:
                    pass
        return self._available

    def notify(
        self,
        title: str,
        body: str,
        icon: str = "mail-message-new",
        urgency: str = "normal",
        timeout: int = 5000,
    ) -> bool:
        if not self.is_available():
            logger.debug("Desktop notifications not available")
            return False

        try:
            return self._notify_dbus(title, body, icon, urgency, timeout)
        except Exception:
            try:
                return self._notify_send(title, body, icon, urgency, timeout)
            except Exception as e:
                logger.error("Desktop notification failed: %s", e)
                return False

    def _notify_dbus(
        self, title: str, body: str, icon: str, urgency: str, timeout: int
    ) -> bool:
        import dbus

        bus = dbus.SessionBus()
        proxy = bus.get_object(
            "org.freedesktop.Notifications", "/org/freedesktop/Notifications"
        )
        interface = dbus.Interface(proxy, "org.freedesktop.Notifications")

        urgency_map = {"low": 0, "normal": 1, "critical": 2}
        urgency_val = urgency_map.get(urgency, 1)

        interface.Notify(
            "OpenEmail",
            0,
            icon,
            title,
            body,
            [],
            {"urgency": dbus.Byte(urgency_val)},
            timeout,
        )
        return True

    def _notify_send(
        self, title: str, body: str, icon: str, urgency: str, timeout: int
    ) -> bool:
        cmd = ["notify-send", "-u", urgency, "-t", str(timeout)]
        if icon:
            cmd.extend(["-i", icon])
        cmd.extend([title, body])

        result = subprocess.run(cmd, capture_output=True, timeout=5)
        return result.returncode == 0

    def notify_new_mail(
        self,
        sender: str,
        subject: str,
        account_email: str = "",
        preview: str = "",
    ) -> bool:
        title = f"新邮件: {sender}"
        body_parts = [subject]
        if account_email:
            body_parts.append(f"账号: {account_email}")
        if preview:
            preview_short = preview[:80] + ("..." if len(preview) > 80 else "")
            body_parts.append(preview_short)
        body = "\n".join(body_parts)

        return self.notify(title=title, body=body, icon="mail-message-new")


desktop_notifier = DesktopNotifier()
