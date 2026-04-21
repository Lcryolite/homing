from __future__ import annotations

import logging
from PyQt6.QtCore import pyqtSignal, QTimer
from PyQt6.QtWidgets import (
    QComboBox,
    QDialog,
    QFormLayout,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
    QGroupBox,
)

from openemail.core.connection_tester import (
    get_connection_tester,
    ProtocolType,
    ConnectionTestSummary,
)
from openemail.core.connection_status import ConnectionStatus, get_status_display
from openemail.core.validation_snapshot import (
    AccountValidationSnapshot,
    get_validation_manager,
)
from openemail.models.account import Account, PROVIDER_PRESETS
from openemail.core.oauth2_new import (
    get_oauth_error_message,
    OAuthManager,
)

logger = logging.getLogger(__name__)


class AccountDialog(QDialog):
    account_saved = pyqtSignal(int)
    _oauth_result_signal = pyqtSignal(object, object)
    _test_result_signal = pyqtSignal(object)

    def __init__(
        self, account: Account | None = None, parent: QWidget | None = None
    ) -> None:
        super().__init__(parent)
        self._account = account
        self._is_edit = account is not None
        self._test_worker = None  # 连接测试工作线程
        self._last_test_id: str = ""  # 最后测试ID
        self._last_validation_result = None  # 最后验证结果
        self._current_snapshot: AccountValidationSnapshot | None = None  # 当前表单快照
        self._setup_ui()
        self._oauth_result_signal.connect(self._handle_oauth_result)
        self._test_result_signal.connect(self._handle_test_result)
        if account:
            self._load_account(account)

    def _setup_ui(self) -> None:
        self.setWindowTitle("编辑账户" if self._is_edit else "添加账户")
        self.setMinimumWidth(500)

        layout = QVBoxLayout(self)

        # 状态显示标签
        self._status_label = QLabel("状态: 未验证")
        self._status_label.setStyleSheet("color: gray;")
        layout.addWidget(self._status_label)

        from openemail.models.account import _PROVIDER_STATUS_LABELS

        provider_row = QHBoxLayout()
        provider_label = QLabel("服务商预设:")
        self._provider_combo = QComboBox()
        self._provider_combo.addItem("自定义", "custom")
        for key, preset in PROVIDER_PRESETS.items():
            status_suffix = _PROVIDER_STATUS_LABELS.get(preset.get("status", ""), "")
            display_name = f"{preset['name']}{status_suffix}"
            self._provider_combo.addItem(display_name, key)
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
        self._protocol_combo.addItem("Exchange ActiveSync", "activesync")
        self._protocol_combo.currentIndexChanged.connect(self._on_protocol_changed)
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

        # ActiveSync字段
        self._eas_host_edit = QLineEdit()
        self._eas_host_edit.setPlaceholderText("例如: outlook.office365.com")
        eas_host_row = QHBoxLayout()
        eas_host_row.addWidget(QLabel("ActiveSync 服务器:"))
        eas_host_row.addWidget(self._eas_host_edit)
        form.addRow(eas_host_row)

        self._eas_path_edit = QLineEdit()
        self._eas_path_edit.setText("/Microsoft-Server-ActiveSync")
        self._eas_path_edit.setPlaceholderText("ActiveSync路径")
        eas_path_row = QHBoxLayout()
        eas_path_row.addWidget(QLabel("ActiveSync 路径:"))
        eas_path_row.addWidget(self._eas_path_edit)
        form.addRow(eas_path_row)

        self._ssl_combo = QComboBox()
        self._ssl_combo.addItem("SSL/TLS", "ssl")
        self._ssl_combo.addItem("STARTTLS", "starttls")
        self._ssl_combo.addItem("无加密", "none")
        form.addRow("加密方式:", self._ssl_combo)

        self._auth_combo = QComboBox()
        self._auth_combo.currentIndexChanged.connect(self._on_auth_type_changed)
        form.addRow("认证方式:", self._auth_combo)
        self._populate_auth_combo()  # initial population with all types

        # OAuth状态和授权按钮
        oauth_group = QGroupBox("OAuth2 授权")
        oauth_layout = QGridLayout(oauth_group)

        self._oauth_status_label = QLabel("状态: 未配置OAuth")
        self._oauth_status_label.setStyleSheet("color: gray;")
        oauth_layout.addWidget(self._oauth_status_label, 0, 0, 1, 2)

        self._authorize_btn = QPushButton("授权")
        self._authorize_btn.clicked.connect(self._on_authorize_clicked)
        self._authorize_btn.setEnabled(False)
        oauth_layout.addWidget(self._authorize_btn, 1, 0)

        self._refresh_btn = QPushButton("检查令牌")
        self._refresh_btn.clicked.connect(self._on_check_token_clicked)
        self._refresh_btn.setEnabled(False)
        oauth_layout.addWidget(self._refresh_btn, 1, 1)

        layout.addWidget(oauth_group)
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

        # 初始隐藏ActiveSync字段
        self._on_protocol_changed(0)

        # 监听邮箱变化以更新OAuth状态
        self._email_edit.textChanged.connect(self._update_oauth_status)

    def _on_protocol_changed(self, index: int) -> None:
        """协议变化事件"""
        protocol = self._protocol_combo.currentData()

        # 显示/隐藏相关字段
        is_imap = protocol == "imap"
        is_pop3 = protocol == "pop3"
        is_activesync = protocol == "activesync"

        # IMAP/POP3字段
        imap_visible = is_imap or is_pop3
        self._imap_host_edit.setVisible(is_imap)
        self._imap_port_spin.setVisible(is_imap)
        self._pop3_host_edit.setVisible(is_pop3)
        self._pop3_port_spin.setVisible(is_pop3)
        self._smtp_host_edit.setVisible(imap_visible)
        self._smtp_port_spin.setVisible(imap_visible)
        self._ssl_combo.setVisible(imap_visible)

        # ActiveSync字段
        self._eas_host_edit.setVisible(is_activesync)
        self._eas_path_edit.setVisible(is_activesync)

        # 更新标签文本
        for i in range(self.layout().count()):
            widget = self.layout().itemAt(i).widget()
            if isinstance(widget, QLabel):
                text = widget.text()
                if "IMAP" in text and not is_imap:
                    widget.setVisible(False)
                elif "POP3" in text and not is_pop3:
                    widget.setVisible(False)
                elif "SMTP" in text and not imap_visible:
                    widget.setVisible(False)
                elif "ActiveSync" in text and not is_activesync:
                    widget.setVisible(False)

    def _populate_auth_combo(self, supported_types: list[str] | None = None) -> None:
        """Re-populate auth combo with only the given types (or all if None)."""
        from openemail.models.account import AUTH_TYPE_LABELS

        self._auth_combo.blockSignals(True)
        self._auth_combo.clear()
        types = supported_types or list(AUTH_TYPE_LABELS.keys())
        for auth_type in types:
            label = AUTH_TYPE_LABELS.get(auth_type, auth_type)
            self._auth_combo.addItem(label, auth_type)
        self._auth_combo.blockSignals(False)
        if self._auth_combo.count() > 0:
            self._on_auth_type_changed()

    def _on_provider_changed(self, index: int) -> None:
        provider = self._provider_combo.currentData()
        if provider == "custom":
            self._populate_auth_combo()  # show all auth types
            return

        preset = PROVIDER_PRESETS.get(provider, {})
        self._name_edit.setText(preset.get("name", ""))

        # 动态更新认证方式选项（仅显示 provider 支持的类型）
        supported = preset.get("supported_auth_types")
        self._populate_auth_combo(supported)

        # 协议选择
        protocol = preset.get("protocol", "imap")
        if protocol == "imap":
            self._protocol_combo.setCurrentIndex(0)
        elif protocol == "pop3":
            self._protocol_combo.setCurrentIndex(1)
        elif protocol == "activesync":
            self._protocol_combo.setCurrentIndex(2)

        self._imap_host_edit.setText(preset.get("imap_host", ""))
        self._imap_port_spin.setValue(preset.get("imap_port", 993))
        self._smtp_host_edit.setText(preset.get("smtp_host", ""))
        self._smtp_port_spin.setValue(preset.get("smtp_port", 465))
        self._eas_host_edit.setText(preset.get("eas_host", ""))
        self._eas_path_edit.setText(
            preset.get("eas_path", "/Microsoft-Server-ActiveSync")
        )

        ssl_map = {"ssl": 0, "starttls": 1, "none": 2}
        self._ssl_combo.setCurrentIndex(ssl_map.get(preset.get("ssl_mode", "ssl"), 0))

        # Set auth type by data (not hardcoded index)
        target_auth = preset.get("auth_type", "password")
        for i in range(self._auth_combo.count()):
            if self._auth_combo.itemData(i) == target_auth:
                self._auth_combo.setCurrentIndex(i)
                break

        # 更新OAuth状态
        self._update_oauth_status()

    def _load_account(self, account: Account) -> None:
        self._name_edit.setText(account.name)
        self._email_edit.setText(account.email)

        # 协议选择
        if account.protocol == "imap":
            self._protocol_combo.setCurrentIndex(0)
        elif account.protocol == "pop3":
            self._protocol_combo.setCurrentIndex(1)
        elif account.protocol == "activesync":
            self._protocol_combo.setCurrentIndex(2)

        self._imap_host_edit.setText(account.imap_host)
        self._imap_port_spin.setValue(account.imap_port)
        self._pop3_host_edit.setText(account.pop3_host)
        self._pop3_port_spin.setValue(account.pop3_port)
        self._smtp_host_edit.setText(account.smtp_host)
        self._smtp_port_spin.setValue(account.smtp_port)
        self._eas_host_edit.setText(account.eas_host)
        self._eas_path_edit.setText(account.eas_path)

        ssl_map = {"ssl": 0, "starttls": 1, "none": 2}
        self._ssl_combo.setCurrentIndex(ssl_map.get(account.ssl_mode, 0))

        auth_map = {"password": 0, "oauth2": 1, "app_password": 2}
        self._auth_combo.setCurrentIndex(auth_map.get(account.auth_type, 0))

        # 更新OAuth状态显示
        self._update_oauth_status()

    def _on_auth_type_changed(self, index: int):
        """认证方式变化处理"""
        auth_type = self._auth_combo.currentData()
        is_oauth = auth_type == "oauth2"

        # 密码字段状态
        self._password_edit.setEnabled(not is_oauth)
        self._password_edit.setPlaceholderText(
            "OAuth将自动获取令牌" if is_oauth else "授权码或密码"
        )

        # 更新OAuth状态
        self._update_oauth_status()

    def _update_oauth_status(self):
        """更新OAuth状态显示"""
        auth_type = self._auth_combo.currentData()
        email = self._email_edit.text().strip()

        if auth_type != "oauth2":
            self._oauth_status_label.setText("状态: OAuth未启用")
            self._oauth_status_label.setStyleSheet("color: gray;")
            self._authorize_btn.setEnabled(False)
            self._refresh_btn.setEnabled(False)
            return

        if not email:
            self._oauth_status_label.setText("状态: 请输入邮箱地址")
            self._oauth_status_label.setStyleSheet("color: orange;")
            self._authorize_btn.setEnabled(False)
            self._refresh_btn.setEnabled(False)
            return

        # 推断OAuth服务商
        from openemail.models.account import Account

        provider = Account.get_ouath_provider_for_email(email)

        if not provider:
            self._oauth_status_label.setText("状态: 不支持此邮箱的OAuth")
            self._oauth_status_label.setStyleSheet("color: red;")
            self._authorize_btn.setEnabled(False)
            self._refresh_btn.setEnabled(False)
            return

        # 检查OAuth配置
        oauth_mgr = OAuthManager()
        if not oauth_mgr.is_provider_available(provider):
            self._oauth_status_label.setText("状态: OAuth客户端未配置")
            self._oauth_status_label.setStyleSheet("color: orange;")
            self._authorize_btn.setEnabled(False)
            self._refresh_btn.setEnabled(False)
            return

        # 检查协议支持矩阵
        protocol = self._protocol_combo.currentData()
        status_suffix = self._get_protocol_support_text(provider, protocol)

        # 如果是编辑模式，检查现有OAuth状态
        if self._account and self._account.is_oauth_enabled():
            status_text = self._account.oauth_status_display()
            if "需要重新授权" in status_text or "令牌即将过期" in status_text:
                self._oauth_status_label.setText(f"状态: {status_text}{status_suffix}")
                self._oauth_status_label.setStyleSheet("color: orange;")
                self._authorize_btn.setEnabled(True)
                self._refresh_btn.setEnabled(True)
            elif "已授权" in status_text:
                self._oauth_status_label.setText(f"状态: {status_text}{status_suffix}")
                self._oauth_status_label.setStyleSheet("color: green;")
                self._authorize_btn.setEnabled(True)
                self._refresh_btn.setEnabled(True)
            else:
                self._oauth_status_label.setText(f"状态: {status_text}{status_suffix}")
                self._oauth_status_label.setStyleSheet("color: blue;")
                self._authorize_btn.setEnabled(True)
                self._refresh_btn.setEnabled(False)
        else:
            self._oauth_status_label.setText(
                f"状态: 点击授权按钮开始OAuth流程{status_suffix}"
            )
            self._oauth_status_label.setStyleSheet("color: blue;")
            self._authorize_btn.setEnabled(True)
            self._refresh_btn.setEnabled(False)

    def _get_protocol_support_text(self, provider: str, protocol: str) -> str:
        """
        Get protocol support information text

        Returns:
            Protocol support info, e.g., " (IMAP: ✓, SMTP: ⚡)"
        """
        support_map = {
            "google": {
                "imap": "✓ (tested)",  # Gmail IMAP OAuth tested
                "smtp": "⚡ (pending)",
                "pop3": "⚡ (pending)",
                "activesync": "⚡ (n/a)",
            },
            "microsoft": {
                "imap": "🔬 (code ready)",
                "smtp": "⚡ (pending)",
                "pop3": "⚡ (pending)",
                "activesync": "⚡ (pending)",
            },
        }

        provider_map = support_map.get(provider, {})

        # Build full matrix display
        matrix_parts = []
        for proto, status in provider_map.items():
            if proto == "imap":
                matrix_parts.append(f"IMAP: {status}")
            elif proto == "smtp":
                matrix_parts.append(f"SMTP: {status}")
            elif proto == "pop3":
                matrix_parts.append(f"POP3: {status}")
            elif proto == "activesync":
                matrix_parts.append(f"ActiveSync: {status}")

        if matrix_parts:
            return f" [{', '.join(matrix_parts)}]"
        return ""

    def _on_authorize_clicked(self):
        """OAuth授权按钮点击事件"""
        email = self._email_edit.text().strip()
        if not email:
            QMessageBox.warning(self, "授权失败", "请输入邮箱地址")
            return

        from openemail.models.account import Account

        provider = Account.get_ouath_provider_for_email(email)

        if not provider:
            QMessageBox.warning(self, "授权失败", "不支持此邮箱的OAuth授权")
            return

        # 显示provider状态
        protocol = self._protocol_combo.currentData()
        support_text = self._get_protocol_support_text(provider, protocol)

        # 禁用按钮，显示授权中状态
        self._authorize_btn.setEnabled(False)
        self._authorize_btn.setText("授权中...")

        provider_name = "Google" if provider == "google" else "Microsoft"
        if provider == "microsoft":
            self._oauth_status_label.setText(
                f"状态: {provider_name} OAuth代码就绪，待真实环境验证{support_text}"
            )
            self._oauth_status_label.setStyleSheet("color: blue;")

            # 对于Microsoft，显示信息对话框而不是实际启动
            _reply = QMessageBox.information(
                self,
                "Outlook OAuth状态",
                f"Microsoft OAuth实现代码完成，但需要真实Azure AD应用凭据。\n\n"
                f"当前状态: 代码就绪，待真实环境验证\n"
                f"支持情况:{support_text}\n\n"
                f"要测试真实OAuth，请在Microsoft Azure Portal创建应用并配置client_id。",
            )

            # 恢复按钮状态
            self._authorize_btn.setText("授权")
            self._authorize_btn.setEnabled(True)
            return
        else:
            self._oauth_status_label.setText(
                f"状态: 打开{provider_name}授权页面...{support_text}"
            )
            self._oauth_status_label.setStyleSheet("color: orange;")

        # 启动异步授权
        from openemail.core.oauth2_new import oauth_manager

        oauth_manager.authorize(provider, self._on_oauth_completed)

    def _on_oauth_completed(self, tokens=None, error=None):
        """OAuth授权完成回调（从后台线程调用）"""
        # 使用信号安全地传递到UI线程
        self._oauth_result_signal.emit(tokens, error)

    def _handle_oauth_result(self, tokens, error):
        """处理OAuth结果（在UI线程中）"""
        email = self._email_edit.text().strip()
        from openemail.models.account import Account

        provider = Account.get_ouath_provider_for_email(email) if email else ""
        protocol = self._protocol_combo.currentData()
        support_text = (
            self._get_protocol_support_text(provider, protocol) if provider else ""
        )

        if error:
            error_msg, suggestion = get_oauth_error_message(error.code)

            # 针对真实Google OAuth失败的特殊处理
            if provider == "google" and error.code.value == "OAUTH_004":
                # 可能是Google测试客户端问题，提供更多信息
                error_msg += " (测试客户端可能需要额外配置)"
                suggestion = "请确认Google API Console中的重定向URI配置正确"

            QMessageBox.warning(self, "授权失败", f"{error_msg}\n\n建议: {suggestion}")
            self._authorize_btn.setText("授权失败，重试")
            self._oauth_status_label.setText(f"状态: 授权失败{support_text}")
            self._oauth_status_label.setStyleSheet("color: red;")

            # 3秒后恢复按钮
            QTimer.singleShot(3000, self._reset_oauth_buttons)
            return

        if not tokens:
            QMessageBox.warning(self, "授权失败", "未获取到令牌")
            self._authorize_btn.setText("授权失败，重试")
            self._oauth_status_label.setText(f"状态: 授权失败{support_text}")
            self._oauth_status_label.setStyleSheet("color: red;")
            QTimer.singleShot(3000, self._reset_oauth_buttons)
            return

        # 保存令牌到当前账户（如果存在）或创建临时账户
        if self._account:
            from openemail.core.oauth2_new import OAuthAuthenticator

            OAuthAuthenticator.apply_to_account(self._account, tokens)

            from openemail.core.connection_status import ConnectionStatus

            self._account.update_status(ConnectionStatus.VERIFIED, force=True)
            self._account.mark_for_sync()

            # 记录到日志
            access_token_preview = tokens.get("access_token", "")[:10]
            _refresh_token_preview = tokens.get("refresh_token", "")[:10]
            expires_at = tokens.get("expires_at", "")

            import logging

            logger = logging.getLogger(__name__)
            logger.info(
                f"OAuth授权成功 - 账户: {self._account.email}, "
                f"访问令牌前10位: {access_token_preview}..., "
                f"过期时间: {expires_at}"
            )

            # 更新UI状态
            self._oauth_status_label.setText(
                f"状态: 授权成功，令牌已保存到数据库{support_text}"
            )
            self._oauth_status_label.setStyleSheet("color: green;")
            self._authorize_btn.setText("重新授权")

            QMessageBox.information(
                self,
                "授权成功",
                f"✅ OAuth授权成功！\n\n"
                f"• 访问令牌已获取\n"
                f"• 刷新令牌已保存\n"
                f"• 过期时间: {expires_at}\n"
                f"• 账户已标记为同步就绪\n\n"
                f"支持情况:{support_text}\n\n"
                f"保存后即可开始同步邮件。",
            )
        else:
            # 新账户，保存tokens供保存时使用
            self._pending_oauth_tokens = tokens
            self._password_edit.setText("[OAuth授权成功]")
            self._password_edit.setEnabled(False)

            # 为临时展示保存令牌
            import json

            temp_tokens_json = json.dumps(tokens, ensure_ascii=False)
            self._password_edit.setToolTip(f"OAuth令牌: {temp_tokens_json[:200]}...")

            self._oauth_status_label.setText(
                f"状态: 授权成功，请完成配置并保存账户{support_text}"
            )
            self._oauth_status_label.setStyleSheet("color: green;")
            self._authorize_btn.setText("重新授权")

            QMessageBox.information(
                self,
                "授权成功",
                f"✅ OAuth授权成功！\n\n"
                f"令牌信息已临时保存。\n"
                f"支持情况:{support_text}\n\n"
                f"请完成其他配置并：\n"
                f"1. 点击'保存'将令牌持久化到数据库\n"
                f"2. 然后点击'测试连接'验证账号",
            )

        # 启用刷新按钮
        self._refresh_btn.setEnabled(True)

    def _on_check_token_clicked(self):
        """检查令牌按钮点击事件"""
        if not self._account:
            QMessageBox.information(self, "检查令牌", "请先保存账户后再检查令牌状态")
            return

        if not self._account.is_oauth_enabled():
            QMessageBox.information(self, "检查令牌", "此账户未启用OAuth")
            return

        from openemail.core.oauth2_new import OAuthManager

        oauth_mgr = OAuthManager()
        authenticator = oauth_mgr.get_authenticator(self._account.oauth_provider)

        if not authenticator:
            QMessageBox.warning(self, "检查令牌", "无法获取OAuth认证器")
            return

        # 检查令牌状态
        import logging

        logger = logging.getLogger(__name__)

        # 检查令牌是否存在
        if not self._account.oauth_token:
            QMessageBox.warning(self, "检查令牌", "账户没有OAuth访问令牌")
            self._account.update_status("auth_required")
            self._account.save()
            self._update_oauth_status()
            return

        # 检查令牌是否即将过期
        needs_refresh = self._account.needs_token_refresh()

        if not needs_refresh:
            # 令牌未过期
            token_preview = self._account.oauth_token[:10]
            expires_at = self._account.token_expires_at or "未知"

            logger.info(
                f"令牌检查 - 账户: {self._account.email}, "
                f"令牌前10位: {token_preview}..., "
                f"过期时间: {expires_at}, "
                f"状态: 正常"
            )

            QMessageBox.information(
                self,
                "检查令牌",
                f"✅ 令牌状态正常\n\n"
                f"• 访问令牌: {token_preview}...\n"
                f"• 过期时间: {expires_at}\n"
                f"• 状态: 未过期，无需刷新\n\n"
                f"账户连接状态: {self._account.status_display}",
            )
            self._update_oauth_status()
            return

        # 尝试刷新令牌
        logger.info(
            f"令牌检查 - 账户: {self._account.email}, 令牌即将过期，尝试刷新..."
        )

        try:
            refresh_success = authenticator.check_and_refresh(self._account)

            if refresh_success:
                # 刷新成功
                new_token_preview = self._account.oauth_token[:10]
                new_expires = self._account.token_expires_at or "未知"

                logger.info(
                    f"令牌刷新成功 - 账户: {self._account.email}, "
                    f"新令牌前10位: {new_token_preview}..., "
                    f"新过期时间: {new_expires}"
                )

                QMessageBox.information(
                    self,
                    "检查令牌",
                    f"🔄 令牌刷新成功\n\n"
                    f"• 新访问令牌: {new_token_preview}...\n"
                    f"• 新过期时间: {new_expires}\n"
                    f"• 数据已更新到数据库\n\n"
                    f"账户连接状态: {self._account.status_display}",
                )
            else:
                # 刷新失败，需要重新授权
                logger.warning(
                    f"令牌刷新失败 - 账户: {self._account.email}, 需要重新授权"
                )
                self._account.update_status("auth_required")
                self._account.save()

                QMessageBox.warning(
                    self,
                    "检查令牌",
                    "⚠️ 令牌刷新失败\n\n"
                    "• 刷新令牌无效或已撤销\n"
                    "• 账户状态已更新为: 需要重新授权\n\n"
                    "请点击'授权'按钮重新获取令牌。",
                )
        except Exception as e:
            # 刷新过程异常
            logger.error(f"令牌刷新异常 - 账户: {self._account.email}, 错误: {str(e)}")
            self._account.update_status("auth_required")
            self._account.save()

            QMessageBox.critical(
                self,
                "检查令牌",
                f"❌ 令牌刷新异常\n\n"
                f"异常信息: {str(e)[:100]}\n"
                f"账户状态已更新为: 需要重新授权\n\n"
                f"请点击'授权'按钮重新获取令牌。",
            )

        self._update_oauth_status()

    def _reset_oauth_buttons(self):
        """重置OAuth按钮状态"""
        self._authorize_btn.setText("授权")
        self._authorize_btn.setEnabled(True)
        self._update_oauth_status()

    def _save(self) -> None:
        email_addr = self._email_edit.text().strip()
        if not email_addr:
            QMessageBox.warning(self, "保存失败", "请输入邮箱地址")
            return

        # 创建当前表单快照
        current_snapshot = self._create_snapshot()

        # 检查验证结果是否有效
        validation_manager = get_validation_manager()
        validation_result = None

        if self._last_test_id:
            validation_result = validation_manager.get_validation_result(
                self._last_test_id, current_snapshot
            )

        # 确定目标状态（如果是新账号或历史账号，目标为verified）
        target_status = ConnectionStatus.VERIFIED

        # 检查是否可以保存
        can_save = validation_manager.can_save_account(
            current_snapshot, validation_result, target_status.value
        )

        if not can_save:
            # 尝试自动触发测试
            should_test = QMessageBox.question(
                self,
                "需要验证连接",
                "账号需要先通过连接验证才能保存。是否立即测试连接？",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.Yes,
            )

            if should_test == QMessageBox.StandardButton.Yes:
                self._test_connection()
            else:
                QMessageBox.warning(
                    self,
                    "保存失败",
                    "账号未通过连接验证，无法保存。请先使用'测试连接'按钮验证账号配置。",
                )
            return

        # 创建或更新账号
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
        account.eas_host = self._eas_host_edit.text().strip()
        account.eas_path = (
            self._eas_path_edit.text().strip() or "/Microsoft-Server-ActiveSync"
        )
        account.ssl_mode = self._ssl_combo.currentData()
        account.auth_type = self._auth_combo.currentData()

        password = self._password_edit.text()
        auth_type = self._auth_combo.currentData()

        # OAuth处理
        if auth_type == "oauth2":
            provider = Account.get_ouath_provider_for_email(email_addr)
            account.oauth_provider = provider

            # 检查是否有待处理的OAuth令牌
            pending_tokens = getattr(self, "_pending_oauth_tokens", None)
            if pending_tokens:
                from openemail.core.oauth2_new import OAuthAuthenticator

                OAuthAuthenticator.apply_to_account(account, pending_tokens)
                self._pending_oauth_tokens = None
            elif self._account and self._account.is_oauth_enabled():
                account.oauth_token = self._account.oauth_token
                account.oauth_refresh = self._account.oauth_refresh
                account.token_expires_at = self._account.token_expires_at
            else:
                QMessageBox.warning(
                    self,
                    "保存失败",
                    "OAuth账号需要先授权。请点击'OAuth2授权'区域的'授权'按钮。",
                )
                return

            account.password = ""
        else:
            # 非OAuth账户需要密码
            if password:
                account.password = password
            else:
                QMessageBox.warning(self, "保存失败", "请输入密码或授权码")
                return

        # 设置验证结果和状态
        if validation_result:
            account.record_validation_result(validation_result)
            account.update_status(ConnectionStatus.VERIFIED)
        elif auth_type == "oauth2" and account.oauth_token:
            account.update_status(ConnectionStatus.VERIFIED, force=True)
            account.mark_for_sync()
        else:
            account.update_status(ConnectionStatus.UNVERIFIED)

        try:
            account_id = account.save()
            self.account_saved.emit(account_id)

            # 显示保存成功消息
            status_display = get_status_display(account.connection_status)
            QMessageBox.information(
                self, "保存成功", f"账号已保存。\n状态: {status_display}"
            )

            self.accept()

        except ValueError as e:
            QMessageBox.critical(self, "保存失败", f"无法保存账号: {str(e)}")
        except Exception as e:
            logger.error("保存账号时出错: %s", str(e))
            QMessageBox.critical(self, "保存失败", f"保存时发生错误: {str(e)}")

    def _test_connection(self) -> None:
        """测试连接（使用统一测试器，非阻塞）"""
        # 禁用按钮，显示测试中状态
        self._test_btn.setEnabled(False)
        self._test_btn.setText("测试中...")

        # 检查基本字段
        email = self._email_edit.text().strip()
        if not email:
            self._show_test_error("请输入邮箱地址")
            return

        password = self._password_edit.text()
        if not password:
            self._show_test_error("请输入密码")
            return

        # 准备账户数据
        auth_type = self._auth_combo.currentData()

        account_data = {
            "email": email,
            "imap_host": self._imap_host_edit.text().strip(),
            "imap_port": self._imap_port_spin.value(),
            "smtp_host": self._smtp_host_edit.text().strip(),
            "smtp_port": self._smtp_port_spin.value(),
            "pop3_host": "",  # TODO: 从UI获取POP3设置
            "pop3_port": 995,
            "eas_host": "",  # TODO: 从UI获取ActiveSync设置
            "eas_path": "/Microsoft-Server-ActiveSync",
            "ssl_mode": self._ssl_combo.currentData(),
            "auth_type": auth_type,
        }

        # OAuth处理
        if auth_type == "oauth2":
            # 如果是已存在的账户，使用其OAuth令牌
            if self._account and self._account.is_oauth_enabled():
                account_data["password"] = ""
                account_data["oauth_token"] = self._account.oauth_token
                account_data["oauth_provider"] = self._account.oauth_provider
            else:
                # 检查是否有待处理的OAuth令牌
                pending_tokens = getattr(self, "_pending_oauth_tokens", None)
                if pending_tokens:
                    account_data["password"] = ""
                    account_data["oauth_token"] = pending_tokens.get("access_token", "")
                    account_data["oauth_provider"] = (
                        Account.get_ouath_provider_for_email(email)
                    )
                elif password and "[OAuth授权成功]" in password:
                    account_data["password"] = ""
                    account_data["oauth_token"] = ""
                else:
                    self._show_test_error("OAuth账号需要先授权")
                    return
        else:
            # 非OAuth账户需要密码
            account_data["password"] = password
            account_data["oauth_token"] = ""

        # 确定要测试的协议
        protocols = []
        if account_data["imap_host"]:
            protocols.append(ProtocolType.IMAP)
        if account_data["smtp_host"]:
            protocols.append(ProtocolType.SMTP)
        if account_data["pop3_host"]:
            protocols.append(ProtocolType.POP3)
        if account_data["eas_host"]:
            protocols.append(ProtocolType.ACTIVESYNC)

        if not protocols:
            self._show_test_error("请至少配置一个协议（IMAP 或 SMTP）")
            return

        # 启动测试
        tester = get_connection_tester()
        self._test_worker = tester.start_test(
            account_data=account_data,
            protocols=protocols,
            callback=self._on_test_completed,
            test_id=self._last_test_id,  # 使用之前的test_id，如果存在
        )

        # 设置超时恢复（防止测试卡死）
        QTimer.singleShot(45000, self._on_test_timeout)

    def _on_test_completed(self, summary: ConnectionTestSummary) -> None:
        """连接测试完成回调（从后台线程调用）"""
        self._test_result_signal.emit(summary)

    def _handle_test_result(self, summary: ConnectionTestSummary) -> None:
        """处理测试结果（在UI线程中）"""
        try:
            self._test_btn.setEnabled(True)

            # 保存测试ID和验证结果
            self._last_test_id = summary.test_id
            self._last_validation_result = summary.validation_result

            if summary.overall_success:
                # 至少一个协议成功
                success_text = "连接成功"
                if summary.successful_tests == summary.total_tests:
                    success_text = "所有协议连接成功"
                else:
                    success_text = (
                        f"{summary.successful_tests}/{summary.total_tests} 个协议成功"
                    )

                self._test_btn.setText(success_text)
                self._test_btn.setStyleSheet("background-color: #90EE90;")

                # 显示详细结果
                details = []
                for result in summary.results:
                    status = "✓" if result.success else "✗"
                    latency = f"{result.latency_ms}ms"
                    details.append(
                        f"{status} {result.protocol.value.upper()}: {result.error_message or '成功'} ({latency})"
                    )

                if details:
                    # 区分收信和发信结果
                    inbound_success = (
                        summary.validation_result.inbound_success
                        if summary.validation_result
                        else False
                    )
                    outbound_success = (
                        summary.validation_result.outbound_success
                        if summary.validation_result
                        else False
                    )

                    status_message = "连接测试完成:\n\n" + "\n".join(details)
                    if inbound_success:
                        status_message += "\n\n✅ 收信协议验证通过"
                    if outbound_success:
                        status_message += "\n✅ 发信协议验证通过"

                    QMessageBox.information(self, "连接测试结果", status_message)

                    # 更新状态标签
                    if inbound_success:
                        self._update_status_label("收信验证通过")
                    elif outbound_success:
                        self._update_status_label("发信验证通过")
                    else:
                        self._update_status_label("连接成功")
            else:
                # 所有测试都失败
                self._show_test_error("所有协议连接失败")
                self._update_status_label("连接失败")

            # 3秒后重置按钮状态
            QTimer.singleShot(3000, self._reset_test_button)

        except Exception as e:
            logger.error("处理测试结果时出错: %s", str(e))
            self._show_test_error("处理结果时出错")

    def _on_test_timeout(self) -> None:
        """测试超时处理"""
        if not self._test_btn.isEnabled():
            # 按钮仍处于禁用状态，说明测试可能卡住了
            tester = get_connection_tester()
            if tester.is_testing():
                tester.cancel_current_test()
                self._show_test_error("测试超时，已取消")

    def _connect_form_change_signals(self) -> None:
        """连接表单变更信号"""
        # 监听所有可能影响验证结果的字段
        fields_to_watch = [
            self._email_edit,
            self._password_edit,
            self._imap_host_edit,
            self._pop3_host_edit,
            self._smtp_host_edit,
            self._eas_host_edit,
            self._eas_path_edit,
        ]

        for field in fields_to_watch:
            if hasattr(field, "textChanged"):
                field.textChanged.connect(self._on_form_changed)

        # 监听组合框变更
        combo_boxes = [
            self._protocol_combo,
            self._ssl_combo,
            self._auth_combo,
        ]

        for combo in combo_boxes:
            combo.currentIndexChanged.connect(self._on_form_changed)

        # 监听数字框变更
        spin_boxes = [
            self._imap_port_spin,
            self._pop3_port_spin,
            self._smtp_port_spin,
        ]

        for spin in spin_boxes:
            spin.valueChanged.connect(self._on_form_changed)

    def _on_form_changed(self) -> None:
        """表单内容变化处理"""
        # 当表单内容变化时，使旧的验证结果失效
        if self._last_test_id:
            logger.debug("Form changed, invalidating previous test result")
            self._last_test_id = ""  # 清空测试ID
            self._last_validation_result = None  # 清空验证结果
            self._update_status_label("已变更, 需要重新验证")

    def _update_status_label(self, status_text: str) -> None:
        """更新状态标签"""
        status_display = f"状态: {status_text}"
        self._status_label.setText(status_display)

        # 根据状态设置颜色
        if "验证通过" in status_text or "已验证" in status_text:
            self._status_label.setStyleSheet("color: green; font-weight: bold;")
        elif "失败" in status_text or "错误" in status_text:
            self._status_label.setStyleSheet("color: red; font-weight: bold;")
        elif "验证中" in status_text:
            self._status_label.setStyleSheet("color: orange; font-weight: bold;")
        elif "未验证" in status_text or "需要重新验证" in status_text:
            self._status_label.setStyleSheet("color: gray;")
        else:
            self._status_label.setStyleSheet("color: black;")

    def _show_test_error(self, message: str) -> None:
        """显示测试错误"""
        self._test_btn.setText(message)
        self._test_btn.setStyleSheet("background-color: #FFB6C1;")
        self._test_btn.setEnabled(True)
        QTimer.singleShot(3000, self._reset_test_button)

    def _reset_test_button(self) -> None:
        """重置测试按钮状态"""
        self._test_btn.setText("测试连接")
        self._test_btn.setStyleSheet("")  # 清除样式
        self._test_btn.setEnabled(True)

    def _create_snapshot(self) -> AccountValidationSnapshot:
        """创建当前表单的快照"""
        form_data = {
            "email": self._email_edit.text().strip(),
            "protocol": self._protocol_combo.currentData(),
            "auth_type": self._auth_combo.currentData(),
            "imap_host": self._imap_host_edit.text().strip(),
            "imap_port": self._imap_port_spin.value(),
            "smtp_host": self._smtp_host_edit.text().strip(),
            "smtp_port": self._smtp_port_spin.value(),
            "pop3_host": self._pop3_host_edit.text().strip(),
            "pop3_port": self._pop3_port_spin.value(),
            "eas_host": self._eas_host_edit.text().strip(),
            "eas_path": self._eas_path_edit.text().strip()
            or "/Microsoft-Server-ActiveSync",
            "ssl_mode": self._ssl_combo.currentData(),
            "oauth_provider": self._account.oauth_provider if self._account else "",
            "password": self._password_edit.text(),
        }
        return AccountValidationSnapshot.from_form_data(form_data)
