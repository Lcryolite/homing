from __future__ import annotations

from PyQt6.QtCore import pyqtSignal
from PyQt6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from openemail.models.account import Account


CALDAV_PROVIDERS = {
    "google": {
        "name": "Google Calendar",
        "url_template": "https://caldav.googleapis.com/dav/{email}",
        "auth_type": "oauth2",
    },
    "nextcloud": {
        "name": "Nextcloud/ownCloud",
        "url_template": "https://{server}/remote.php/dav/calendars/{username}/",
        "auth_type": "password",
    },
    "fastmail": {
        "name": "Fastmail",
        "url_template": "https://caldav.fastmail.com/dav/{email}",
        "auth_type": "password",
    },
    "icloud": {
        "name": "iCloud",
        "url_template": "https://caldav.icloud.com/{email}",
        "auth_type": "app_password",
    },
    "custom": {
        "name": "自定义",
        "url_template": None,
        "auth_type": "password",
    },
}


class AccountSettingsPanel(QWidget):
    """账户设置面板（右侧可折叠）"""

    account_changed = pyqtSignal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._setup_ui()
        self._load_accounts()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.Shape.NoFrame)

        scroll_content = QWidget()
        scroll_layout = QVBoxLayout(scroll_content)
        scroll_layout.setContentsMargins(8, 8, 8, 8)
        scroll_layout.setSpacing(16)

        # 账户列表表格
        self._account_table = QTableWidget()
        self._account_table.setColumnCount(5)
        self._account_table.setHorizontalHeaderLabels(
            ["名称", "邮箱", "协议", "状态", "操作"]
        )
        self._account_table.horizontalHeader().setStretchLastSection(True)
        self._account_table.setSelectionBehavior(
            QTableWidget.SelectionBehavior.SelectRows
        )
        self._account_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        scroll_layout.addWidget(self._account_table)

        # 按钮栏
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()

        self._add_account_btn = QPushButton("添加账户")
        self._add_account_btn.setProperty("class", "primary")
        self._add_account_btn.clicked.connect(self._on_add_account)
        btn_layout.addWidget(self._add_account_btn)

        self._edit_account_btn = QPushButton("编辑")
        self._edit_account_btn.clicked.connect(self._on_edit_account)
        btn_layout.addWidget(self._edit_account_btn)

        self._delete_account_btn = QPushButton("删除")
        self._delete_account_btn.setProperty("class", "danger")
        self._delete_account_btn.clicked.connect(self._on_delete_account)
        btn_layout.addWidget(self._delete_account_btn)

        scroll_layout.addLayout(btn_layout)

        # CalDAV 同步设置
        caldav_group = QGroupBox("CalDAV 日历同步")
        caldav_layout = QFormLayout()

        self._caldav_enabled_check = QCheckBox("启用 CalDAV 同步")
        caldav_layout.addRow(self._caldav_enabled_check)

        self._caldav_provider_combo = QComboBox()
        for key, provider in CALDAV_PROVIDERS.items():
            self._caldav_provider_combo.addItem(provider["name"], key)
        self._caldav_provider_combo.currentIndexChanged.connect(
            self._on_caldav_provider_changed
        )
        caldav_layout.addRow("服务商:", self._caldav_provider_combo)

        self._caldav_url_edit = QLineEdit()
        self._caldav_url_edit.setPlaceholderText("CalDAV 服务器 URL")
        caldav_layout.addRow("服务器 URL:", self._caldav_url_edit)

        self._caldav_username_edit = QLineEdit()
        self._caldav_username_edit.setPlaceholderText("用户名/邮箱")
        caldav_layout.addRow("用户名:", self._caldav_username_edit)

        self._caldav_password_edit = QLineEdit()
        self._caldav_password_edit.setEchoMode(QLineEdit.EchoMode.Password)
        self._caldav_password_edit.setPlaceholderText("密码/应用密码")
        caldav_layout.addRow("密码:", self._caldav_password_edit)

        caldav_group.setLayout(caldav_layout)
        scroll_layout.addWidget(caldav_group)

        scroll.setWidget(scroll_content)
        layout.addWidget(scroll)

    def _load_accounts(self) -> None:
        """加载账户列表"""
        accounts = Account.get_all()
        self._account_table.setRowCount(len(accounts))

        for i, account in enumerate(accounts):
            self._account_table.setItem(
                i, 0, QTableWidgetItem(account.name or account.email)
            )
            self._account_table.setItem(i, 1, QTableWidgetItem(account.email))
            self._account_table.setItem(
                i, 2, QTableWidgetItem(account.protocol.upper())
            )

            status_item = QTableWidgetItem(
                "🟢 活跃" if account.is_active else "🔴 禁用"
            )
            self._account_table.setItem(i, 3, status_item)

            # 操作按钮
            btn_widget = QWidget()
            btn_layout = QHBoxLayout(btn_widget)
            btn_layout.setContentsMargins(0, 0, 0, 0)

            edit_btn = QPushButton("编辑")
            edit_btn.clicked.connect(
                lambda checked, acc=account: self._edit_single_account(acc)
            )
            btn_layout.addWidget(edit_btn)

            btn_widget.setLayout(btn_layout)
            self._account_table.setCellWidget(i, 4, btn_widget)

    def _on_add_account(self) -> None:
        """添加账户"""
        from openemail.ui.mail.account_dialog import AccountDialog

        dialog = AccountDialog(parent=self)
        dialog.account_saved.connect(self._on_account_saved)
        dialog.exec()

    def _edit_single_account(self, account: Account) -> None:
        """编辑单个账户"""
        from openemail.ui.mail.account_dialog import AccountDialog

        dialog = AccountDialog(account=account, parent=self)
        dialog.account_saved.connect(self._on_account_saved)
        dialog.exec()

    def _on_edit_account(self) -> None:
        """编辑选中的账户"""
        selected_rows = self._account_table.selectedItems()
        if not selected_rows:
            return

        row = selected_rows[0].row()
        accounts = Account.get_all()
        if row < len(accounts):
            self._edit_single_account(accounts[row])

    def _on_delete_account(self) -> None:
        """删除选中的账户"""
        selected_rows = self._account_table.selectedItems()
        if not selected_rows:
            return

        row = selected_rows[0].row()
        accounts = Account.get_all()
        if row < len(accounts):
            account = accounts[row]
            account.delete()
            self._load_accounts()
            self.account_changed.emit()

    def _on_account_saved(self, account_id: int) -> None:
        """账户保存后"""
        self._load_accounts()
        self.account_changed.emit()

    def _on_caldav_provider_changed(self, index: int) -> None:
        """CalDAV 服务商改变"""
        provider_key = self._caldav_provider_combo.currentData()
        provider = CALDAV_PROVIDERS.get(provider_key, {})

        if provider_key == "custom":
            self._caldav_url_edit.setEnabled(True)
            self._caldav_url_edit.clear()
        elif provider.get("url_template"):
            self._caldav_url_edit.setEnabled(False)
            self._caldav_url_edit.setText(provider["url_template"])
