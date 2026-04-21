from __future__ import annotations

from PyQt6.QtCore import pyqtSignal
from PyQt6.QtWidgets import (
    QDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
    QComboBox,
)

from openemail.models.account import Account, PROVIDER_PRESETS


class WelcomeDialog(QDialog):
    """首次启动引导对话框"""

    account_added = pyqtSignal(int)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("欢迎使用 OpenEmail")
        self.setMinimumWidth(400)
        self._setup_ui()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setSpacing(16)

        # 欢迎标题
        title = QLabel("欢迎使用 OpenEmail")
        title.setStyleSheet("font-size: 24px; font-weight: bold;")
        layout.addWidget(title)

        subtitle = QLabel("添加您的第一个邮箱账户")
        subtitle.setStyleSheet("font-size: 14px; ")
        layout.addWidget(subtitle)

        # 服务商选择
        form = QFormLayout()
        form.setSpacing(8)

        self._provider_label = QLabel("选择邮箱服务商:")
        form.addRow(self._provider_label)

        self._provider_combo = QComboBox()
        for key, preset in PROVIDER_PRESETS.items():
            self._provider_combo.addItem(preset["name"], key)
        self._provider_combo.addItem("其他/自定义", "custom")
        self._provider_combo.currentIndexChanged.connect(self._on_provider_changed)
        form.addRow(self._provider_combo)

        self._email_edit = QLineEdit()
        self._email_edit.setPlaceholderText("your@email.com")
        form.addRow("邮箱地址:", self._email_edit)

        self._password_edit = QLineEdit()
        self._password_edit.setEchoMode(QLineEdit.EchoMode.Password)
        self._password_edit.setPlaceholderText("密码或授权码")
        form.addRow("密码/授权码:", self._password_edit)

        layout.addLayout(form)

        # 提示信息
        tip_label = QLabel("💡 提示：QQ/163 等邮箱需要使用授权码而非登录密码")
        tip_label.setStyleSheet("font-size: 12px; ")
        tip_label.setWordWrap(True)
        layout.addWidget(tip_label)

        # 按钮
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()

        self._test_btn = QPushButton("测试连接")
        self._test_btn.clicked.connect(self._test_connection)
        btn_layout.addWidget(self._test_btn)

        self._add_btn = QPushButton("添加账户")
        self._add_btn.setProperty("class", "primary")
        self._add_btn.clicked.connect(self._add_account)
        btn_layout.addWidget(self._add_btn)

        self._skip_btn = QPushButton("稍后设置")
        self._skip_btn.clicked.connect(self.reject)
        btn_layout.addWidget(self._skip_btn)

        layout.addLayout(btn_layout)

    def _on_provider_changed(self, index: int) -> None:
        """服务商改变"""
        provider = self._provider_combo.currentData()
        if provider == "custom":
            self._email_edit.setPlaceholderText("your@email.com")
            self._password_edit.setPlaceholderText("密码")
        else:
            preset = PROVIDER_PRESETS.get(provider, {})
            auth_type = preset.get("auth_type", "password")
            if auth_type == "app_password":
                self._password_edit.setPlaceholderText("授权码")
            elif auth_type == "oauth2":
                self._password_edit.setPlaceholderText("OAuth2 将自动授权")
            else:
                self._password_edit.setPlaceholderText("密码")

    def _test_connection(self) -> None:
        """测试连接"""
        self._test_btn.setEnabled(False)
        self._test_btn.setText("测试中...")

        provider = self._provider_combo.currentData()
        email = self._email_edit.text().strip()
        password = self._password_edit.text()

        if not email or not password:
            self._test_btn.setEnabled(True)
            self._test_btn.setText("测试连接")
            return

        # 创建临时账户测试
        account = Account.create_from_preset(provider, email, "", password)

        import asyncio
        from openemail.core.imap_client import IMAPClient

        loop = asyncio.new_event_loop()
        try:
            if account.protocol == "imap":
                client = IMAPClient(account)
                success = loop.run_until_complete(client.connect())
                if success:
                    loop.run_until_complete(client.disconnect())
            else:
                success = False
        finally:
            loop.close()

        if success:
            self._test_btn.setText("✅ 连接成功")
        else:
            self._test_btn.setText("❌ 连接失败")

        self._test_btn.setEnabled(True)

    def _add_account(self) -> None:
        """添加账户"""
        provider = self._provider_combo.currentData()
        email = self._email_edit.text().strip()
        password = self._password_edit.text()

        if not email or not password:
            return

        account = Account.create_from_preset(
            provider, email, email.split("@")[0], password
        )
        account_id = account.save()

        from openemail.models.folder import Folder

        Folder.ensure_system_folders(account_id)

        self.account_added.emit(account_id)
        self.accept()
