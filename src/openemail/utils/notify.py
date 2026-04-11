from PyQt6.QtWidgets import QSystemTrayIcon
from PyQt6.QtGui import QIcon


class NotificationManager:
    def __init__(self, tray: QSystemTrayIcon | None = None) -> None:
        self._tray = tray

    def set_tray(self, tray: QSystemTrayIcon) -> None:
        self._tray = tray

    def notify(self, title: str, message: str, icon: QIcon | None = None) -> None:
        if self._tray is None:
            return
        msg_icon = QSystemTrayIcon.MessageIcon.Information
        self._tray.showMessage(title, message, msg_icon, 5000)
