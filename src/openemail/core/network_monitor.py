from __future__ import annotations

import socket

from PyQt6.QtCore import QTimer, pyqtSignal, QObject

from openemail.core.operation_queue import operation_queue


class NetworkMonitor(QObject):
    """网络状态监控器"""

    network_changed = pyqtSignal(bool)  # True=在线，False=离线

    def __init__(
        self, parent: QObject | None = None, check_interval: int = 30000
    ) -> None:
        super().__init__(parent)
        self._check_interval = check_interval  # 毫秒
        self._timer = QTimer()
        self._timer.timeout.connect(self._check_network)
        self._is_online = True

    def start(self) -> None:
        """启动监控"""
        self._check_network()
        self._timer.start(self._check_interval)

    def stop(self) -> None:
        """停止监控"""
        self._timer.stop()

    def _check_network(self) -> None:
        """检查网络连通性"""
        try:
            # 尝试连接公共 DNS
            socket.setdefaulttimeout(5)
            socket.socket(socket.AF_INET, socket.SOCK_STREAM).connect(("8.8.8.8", 53))
            new_state = True
        except Exception:
            new_state = False

        if new_state != self._is_online:
            self._is_online = new_state
            self.network_changed.emit(new_state)
            operation_queue.set_network_available(new_state)

    def is_online(self) -> bool:
        """当前是否在线"""
        return self._is_online


network_monitor = NetworkMonitor()
