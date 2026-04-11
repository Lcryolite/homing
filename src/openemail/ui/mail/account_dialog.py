from __future__ import annotations

from PyQt6.QtCore import pyqtSignal
from PyQt6.QtWidgets import (
    QComboBox,
    QDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from openemail.models.account import Account, PROVIDER_PRESETS


class AccountDialog(QDialog):
    account_saved = pyqtSignal(int)

    def __init__(
        self, account: Account | None = None, parent: QWidget | None = None
    ) -> None:
        super().__init__(parent)
        self._account = account
        self._is_edit = account is not None
        self._setup_ui()
        if account:
            self._load_account(account)

    def _setup_ui(self) -> None:
        self.setWindowTitle("编辑账户" if self._is_edit else "添加账户")
        self.setMinimumWidth(500)

        layout = QVBoxLayout(self)

        provider_row = QHBoxLayout()
        provider_label = QLabel("服务商预设:")
        self._provider_combo = QComboBox()
        self._provider_combo.addItem("自定义", "custom")
        for key, preset in PROVIDER_PRESETS.items():
            self._provider_combo.addItem(preset["name"], key)
        self._provider_combo.currentIndexChanged.connect(self._on_provider_changed)
        provider_row.addWidget(provider_label)
        provider_row.addWidget(self._provider_combo, 1)
        layout.addLayout(provider_row)

        form = QFormLayout()
        form.setSpacing(8)

        self._name_edit = QLineEdit()
        self._name_edit.setPlaceholderText("显示名称")
        form.addRow("名称:", self._name_edit)

        self._email_edit = QLineEdit()
        self._email_edit.setPlaceholderText("your@email.com")
        form.addRow("邮箱:", self._email_edit)

        self._password_edit = QLineEdit()
        self._password_edit.setEchoMode(QLineEdit.EchoMode.Password)
        self._password_edit.setPlaceholderText("授权码或密码")
        form.addRow("密码/授权码:", self._password_edit)

        self._protocol_combo = QComboBox()
        self._protocol_combo.addItem("IMAP", "imap")
        self._protocol_combo.addItem("POP3", "pop3")
        form.addRow("收信协议:", self._protocol_combo)

        self._imap_host_edit = QLineEdit()
        form.addRow("IMAP 服务器:", self._imap_host_edit)

        self._imap_port_spin = QSpinBox()
        self._imap_port_spin.setRange(1, 65535)
        self._imap_port_spin.setValue(993)
        form.addRow("IMAP 端口:", self._imap_port_spin)

        self._pop3_host_edit = QLineEdit()
        form.addRow("POP3 服务器:", self._pop3_host_edit)

        self._pop3_port_spin = QSpinBox()
        self._pop3_port_spin.setRange(1, 65535)
        self._pop3_port_spin.setValue(995)
        form.addRow("POP3 端口:", self._pop3_port_spin)

        self._smtp_host_edit = QLineEdit()
        form.addRow("SMTP 服务器:", self._smtp_host_edit)

        self._smtp_port_spin = QSpinBox()
        self._smtp_port_spin.setRange(1, 65535)
        self._smtp_port_spin.setValue(465)
        form.addRow("SMTP 端口:", self._smtp_port_spin)

        self._ssl_combo = QComboBox()
        self._ssl_combo.addItem("SSL/TLS", "ssl")
        self._ssl_combo.addItem("STARTTLS", "starttls")
        self._ssl_combo.addItem("无加密", "none")
        form.addRow("加密方式:", self._ssl_combo)

        self._auth_combo = QComboBox()
        self._auth_combo.addItem("密码/授权码", "password")
        self._auth_combo.addItem("OAuth2", "oauth2")
        self._auth_combo.addItem("应用专用密码", "app_password")
        form.addRow("认证方式:", self._auth_combo)

        layout.addLayout(form)

        btn_row = QHBoxLayout()
        btn_row.addStretch()

        self._test_btn = QPushButton("测试连接")
        self._test_btn.clicked.connect(self._test_connection)
        btn_row.addWidget(self._test_btn)

        self._save_btn = QPushButton("保存")
        self._save_btn.setProperty("class", "primary")
        self._save_btn.clicked.connect(self._save)
        btn_row.addWidget(self._save_btn)

        cancel_btn = QPushButton("取消")
        cancel_btn.clicked.connect(self.reject)
        btn_row.addWidget(cancel_btn)

        layout.addLayout(btn_row)

    def _on_provider_changed(self, index: int) -> None:
        provider = self._provider_combo.currentData()
        if provider == "custom":
            return

        preset = PROVIDER_PRESETS.get(provider, {})
        self._name_edit.setText(preset.get("name", ""))
        self._protocol_combo.setCurrentIndex(
            0 if preset.get("protocol") == "imap" else 1
        )
        self._imap_host_edit.setText(preset.get("imap_host", ""))
        self._imap_port_spin.setValue(preset.get("imap_port", 993))
        self._smtp_host_edit.setText(preset.get("smtp_host", ""))
        self._smtp_port_spin.setValue(preset.get("smtp_port", 465))

        ssl_map = {"ssl": 0, "starttls": 1, "none": 2}
        self._ssl_combo.setCurrentIndex(ssl_map.get(preset.get("ssl_mode", "ssl"), 0))

        auth_map = {"password": 0, "oauth2": 1, "app_password": 2}
        self._auth_combo.setCurrentIndex(
            auth_map.get(preset.get("auth_type", "password"), 0)
        )

    def _load_account(self, account: Account) -> None:
        self._name_edit.setText(account.name)
        self._email_edit.setText(account.email)
        self._protocol_combo.setCurrentIndex(0 if account.protocol == "imap" else 1)
        self._imap_host_edit.setText(account.imap_host)
        self._imap_port_spin.setValue(account.imap_port)
        self._pop3_host_edit.setText(account.pop3_host)
        self._pop3_port_spin.setValue(account.pop3_port)
        self._smtp_host_edit.setText(account.smtp_host)
        self._smtp_port_spin.setValue(account.smtp_port)

        ssl_map = {"ssl": 0, "starttls": 1, "none": 2}
        self._ssl_combo.setCurrentIndex(ssl_map.get(account.ssl_mode, 0))

        auth_map = {"password": 0, "oauth2": 1, "app_password": 2}
        self._auth_combo.setCurrentIndex(auth_map.get(account.auth_type, 0))

    def _save(self) -> None:
        email_addr = self._email_edit.text().strip()
        if not email_addr:
            return

        if self._is_edit and self._account:
            account = self._account
        else:
            account = Account()

        account.name = self._name_edit.text().strip() or email_addr
        account.email = email_addr
        account.protocol = self._protocol_combo.currentData()
        account.imap_host = self._imap_host_edit.text().strip()
        account.imap_port = self._imap_port_spin.value()
        account.pop3_host = self._pop3_host_edit.text().strip()
        account.pop3_port = self._pop3_port_spin.value()
        account.smtp_host = self._smtp_host_edit.text().strip()
        account.smtp_port = self._smtp_port_spin.value()
        account.ssl_mode = self._ssl_combo.currentData()
        account.auth_type = self._auth_combo.currentData()

        password = self._password_edit.text()
        if password:
            account.password = password

        account_id = account.save()
        self.account_saved.emit(account_id)
        self.accept()

    def _test_connection(self) -> None:
        self._test_btn.setEnabled(False)
        self._test_btn.setText("测试中...")

        import asyncio
        from openemail.core.imap_client import IMAPClient
        from openemail.core.smtp_client import SMTPClient

        temp_account = Account(
            email=self._email_edit.text().strip(),
            imap_host=self._imap_host_edit.text().strip(),
            imap_port=self._imap_port_spin.value(),
            smtp_host=self._smtp_host_edit.text().strip(),
            smtp_port=self._smtp_port_spin.value(),
            ssl_mode=self._ssl_combo.currentData(),
            auth_type=self._auth_combo.currentData(),
        )
        password = self._password_edit.text()
        if password:
            temp_account.password = password

        loop = asyncio.new_event_loop()
        try:
            imap_ok = False
            smtp_ok = False

            if temp_account.imap_host:
                client = IMAPClient(temp_account)
                imap_ok = loop.run_until_complete(client.connect())
                if imap_ok:
                    loop.run_until_complete(client.disconnect())

            if temp_account.smtp_host:
                smtp_client = SMTPClient(temp_account)
                smtp_ok = loop.run_until_complete(smtp_client.test_connection())
        finally:
            loop.close()

        imap_status = "成功" if imap_ok else "失败"
        smtp_status = "成功" if smtp_ok else "失败"
        self._test_btn.setText(f"IMAP: {imap_status} | SMTP: {smtp_status}")

        from PyQt6.QtCore import QTimer

        QTimer.singleShot(
            3000,
            lambda: (
                self._test_btn.setEnabled(True),
                self._test_btn.setText("测试连接"),
            ),
        )
