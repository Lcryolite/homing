from __future__ import annotations

import logging
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
    QComboBox,
    QTabWidget,
    QScrollArea,
    QFrame,
    QGroupBox,
    QCheckBox,
    QProgressBar,
    QMessageBox,
)
from PyQt6.QtGui import QFont, QPixmap, QIcon

from openemail.config import settings
from openemail.core.connection_tester import (
    get_connection_tester,
    ProtocolType,
    ConnectionTestSummary,
)
from openemail.models.account import Account, PROVIDER_PRESETS

logger = logging.getLogger(__name__)


class WelcomeDialogEnhanced(QDialog):
    """增强版首次启动引导对话框，提供更好的用户体验"""

    account_added = pyqtSignal(int)
    setup_completed = pyqtSignal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("欢迎使用 OpenEmail")
        self.setMinimumSize(500, 600)
        self.setMaximumWidth(600)
        self.setWindowFlags(
            self.windowFlags() & ~Qt.WindowType.WindowContextHelpButtonHint
        )
        self._current_step = 0
        self._finish_state = "not_started"
        self._test_worker = None  # 连接测试工作线程
        self._oauth_tokens = None  # OAuth令牌缓存
        self._oauth_provider_success = None  # 成功授权的OAuth提供商
        self._setup_ui()
        self._show_step(0)

        # 设置in_progress状态
        if settings.onboarding_state == "not_started":
            settings.onboarding_state = "in_progress"
            logger.debug("初始化引导状态为 in_progress")

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setSpacing(12)
        layout.setContentsMargins(24, 24, 24, 24)

        # 标题区域
        title_widget = QFrame()
        title_widget.setFrameStyle(QFrame.Shape.NoFrame)
        title_layout = QVBoxLayout(title_widget)
        title_layout.setSpacing(8)
        title_layout.setContentsMargins(0, 0, 0, 0)

        title = QLabel("欢迎来到 OpenEmail")
        title.setFont(QFont("", 24, QFont.Weight.Bold))
        title.setStyleSheet("color: #89b4fa; margin-bottom: 8px;")
        title_layout.addWidget(title)

        subtitle = QLabel("轻松设置您的邮箱账户")
        subtitle.setFont(QFont("", 11))
        subtitle.setStyleSheet("color: #a6adc8;")
        title_layout.addWidget(subtitle)

        layout.addWidget(title_widget)
        layout.addSpacing(12)

        # 进度条
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 3)
        self.progress_bar.setTextVisible(True)
        self.progress_bar.setFormat("步骤 %v/%m")
        layout.addWidget(self.progress_bar)

        layout.addSpacing(16)

        # 步骤容器
        self.steps_widget = QTabWidget()
        self.steps_widget.setTabBarAutoHide(True)
        self.steps_widget.tabBar().setVisible(False)
        layout.addWidget(self.steps_widget)

        # 步骤1: 欢迎介绍
        step1_widget = self._create_welcome_step()
        self.steps_widget.addTab(step1_widget, "欢迎")

        # 步骤2: 账户设置
        step2_widget = self._create_account_step()
        self.steps_widget.addTab(step2_widget, "账户")

        # 步骤3: 高级选项
        step3_widget = self._create_options_step()
        self.steps_widget.addTab(step3_widget, "选项")

        # 步骤4: 完成设置
        step4_widget = self._create_finish_step()
        self.steps_widget.addTab(step4_widget, "完成")

        layout.addSpacing(24)

        # 导航按钮
        nav_widget = QFrame()
        nav_widget.setFrameStyle(QFrame.Shape.NoFrame)
        nav_layout = QHBoxLayout(nav_widget)
        nav_layout.setContentsMargins(0, 0, 0, 0)
        nav_layout.setSpacing(12)

        self.prev_btn = QPushButton("上一步")
        self.prev_btn.clicked.connect(self._go_previous)
        self.prev_btn.setMinimumWidth(80)
        nav_layout.addWidget(self.prev_btn)

        nav_layout.addStretch()

        self.next_btn = QPushButton("下一步")
        self.next_btn.clicked.connect(self._go_next)
        self.next_btn.setProperty("class", "primary")
        self.next_btn.setMinimumWidth(80)
        nav_layout.addWidget(self.next_btn)

        layout.addWidget(nav_widget)

    def _create_welcome_step(self) -> QWidget:
        """创建欢迎步骤"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setSpacing(16)
        layout.setContentsMargins(8, 8, 8, 8)

        # 功能介绍
        intro_label = QLabel("OpenEmail 是一款功能强大的桌面邮件客户端，支持：")
        intro_label.setWordWrap(True)
        intro_label.setFont(QFont("", 11))
        layout.addWidget(intro_label)

        # 功能列表
        features_frame = QFrame()
        features_frame.setFrameStyle(QFrame.Shape.Box)
        features_frame.setStyleSheet("""
            QFrame {
                background: #313244;
                border: 1px solid #45475a;
                border-radius: 6px;
                padding: 16px;
            }
        """)
        features_layout = QVBoxLayout(features_frame)
        features_layout.setSpacing(8)

        features = [
            "📧 多账户管理 - 支持主流邮件服务商（Gmail、QQ、163等）",
            "🗑️ 智能垃圾邮件过滤 - 自动识别和过滤垃圾邮件",
            "🔍 强大的邮件搜索 - 快速找到您需要的邮件",
            "🎨 多种主题 - 支持明暗主题切换",
            "📱 离线可用 - 网络不佳时也可查看已保存邮件",
        ]

        for feature in features:
            feature_label = QLabel(f"• {feature}")
            feature_label.setWordWrap(True)
            feature_label.setStyleSheet("font-size: 13px; color: #cdd6f4;")
            features_layout.addWidget(feature_label)

        layout.addWidget(features_frame)

        # 提示信息
        tip_label = QLabel("💡 只需几分钟，即可完成初始设置并开始使用。")
        tip_label.setStyleSheet("font-size: 12px; color: #a6adc8; font-style: italic;")
        tip_label.setWordWrap(True)
        layout.addWidget(tip_label)

        layout.addStretch()
        return widget

    def _create_account_step(self) -> QWidget:
        """创建账户设置步骤"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setSpacing(16)
        layout.setContentsMargins(8, 8, 8, 8)

        # 服务商选择
        provider_group = QGroupBox("选择您的邮箱服务商")
        provider_layout = QVBoxLayout(provider_group)
        provider_layout.setSpacing(8)

        self._provider_combo = QComboBox()
        self._provider_combo.setMinimumHeight(36)
        for key, preset in PROVIDER_PRESETS.items():
            self._provider_combo.addItem(preset["name"], key)
        self._provider_combo.addItem("其他/自定义", "custom")
        self._provider_combo.currentIndexChanged.connect(self._on_provider_changed)
        provider_layout.addWidget(self._provider_combo)

        layout.addWidget(provider_group)

        # 账户信息表单
        form_group = QGroupBox("账户信息")
        form = QFormLayout(form_group)
        form.setSpacing(12)
        form.setContentsMargins(12, 16, 12, 16)

        self._email_edit = QLineEdit()
        self._email_edit.setPlaceholderText("your@email.com")
        self._email_edit.setMinimumHeight(36)
        form.addRow("邮箱地址:", self._email_edit)

        self._password_edit = QLineEdit()
        self._password_edit.setEchoMode(QLineEdit.EchoMode.Password)
        self._password_edit.setPlaceholderText("密码或授权码")
        self._password_edit.setMinimumHeight(36)
        form.addRow("密码/授权码:", self._password_edit)

        # OAuth 授权按钮（用于 Gmail/Outlook）
        self._oauth_btn = QPushButton("OAuth2 授权")
        self._oauth_btn.clicked.connect(self._on_oauth_clicked)
        self._oauth_btn.setVisible(False)
        self._oauth_btn.setMinimumHeight(36)
        oauth_row = QHBoxLayout()
        oauth_row.addSpacing(
            form.labelForField(self._password_edit).sizeHint().width()
            + form.spacing() * 2
        )
        oauth_row.addWidget(self._oauth_btn)
        form.addRow("", oauth_row)

        layout.addWidget(form_group)

        # 连接测试区域
        test_group = QGroupBox("验证设置")
        test_layout = QHBoxLayout(test_group)
        test_layout.setSpacing(12)

        self._test_btn = QPushButton("测试连接")
        self._test_btn.clicked.connect(self._test_connection)
        self._test_btn.setMinimumHeight(36)
        test_layout.addWidget(self._test_btn)

        self._test_result = QLabel("")
        self._test_result.setStyleSheet("font-size: 13px;")
        test_layout.addWidget(self._test_result)

        test_layout.addStretch()
        layout.addWidget(test_group)

        # 重要提示
        tip_frame = QFrame()
        tip_frame.setFrameStyle(QFrame.Shape.Box)
        tip_frame.setStyleSheet("""
            QFrame {
                background: #f9c9c6;
                border: 1px solid #eba0ac;
                border-radius: 6px;
                padding: 12px;
            }
            QLabel {
                color: #8839ef;
                font-size: 12px;
            }
        """)
        tip_layout = QVBoxLayout(tip_frame)
        tip_layout.setSpacing(4)

        warning_label = QLabel("⚠️ 重要提示")
        warning_label.setFont(QFont("", 11, QFont.Weight.Bold))
        tip_layout.addWidget(warning_label)

        tips = [
            "• Gmail需要使用授权码，请先在Google账户中生成",
            "• QQ、163等国内邮箱也需要使用授权码而非登录密码",
            "• 设置完成后将自动下载最近的邮件",
        ]

        for tip in tips:
            tip_label = QLabel(tip)
            tip_label.setWordWrap(True)
            tip_layout.addWidget(tip_label)

        layout.addWidget(tip_frame)
        layout.addStretch()

        return widget

    def _create_options_step(self) -> QWidget:
        """创建选项设置步骤"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setSpacing(16)
        layout.setContentsMargins(8, 8, 8, 8)

        # 同步设置
        sync_group = QGroupBox("同步设置")
        sync_layout = QVBoxLayout(sync_group)
        sync_layout.setSpacing(12)

        self._auto_sync_check = QCheckBox("自动同步邮件（推荐）")
        self._auto_sync_check.setChecked(True)
        sync_layout.addWidget(self._auto_sync_check)

        self._keep_mail_days_label = QLabel("本地保留邮件天数:")
        self._keep_mail_days_combo = QComboBox()
        self._keep_mail_days_combo.addItems(["30天", "90天", "180天", "1年", "全部"])
        self._keep_mail_days_combo.setCurrentIndex(1)
        sync_layout.addWidget(self._keep_mail_days_label)
        sync_layout.addWidget(self._keep_mail_days_combo)

        layout.addWidget(sync_group)

        # 通知设置
        notify_group = QGroupBox("通知设置")
        notify_layout = QVBoxLayout(notify_group)
        notify_layout.setSpacing(12)

        self._desktop_notify_check = QCheckBox("桌面通知新邮件")
        self._desktop_notify_check.setChecked(True)
        notify_layout.addWidget(self._desktop_notify_check)

        self._sound_notify_check = QCheckBox("声音提醒")
        self._sound_notify_check.setChecked(True)
        notify_layout.addWidget(self._sound_notify_check)

        layout.addWidget(notify_group)

        # 隐私设置
        privacy_group = QGroupBox("隐私与安全")
        privacy_layout = QVBoxLayout(privacy_group)
        privacy_layout.setSpacing(12)

        self._encrypt_local_check = QCheckBox("加密本地邮件数据")
        self._encrypt_local_check.setChecked(True)
        privacy_layout.addWidget(self._encrypt_local_check)

        self._auto_logout_check = QCheckBox("闲置15分钟后自动锁定")
        self._auto_logout_check.setChecked(False)
        privacy_layout.addWidget(self._auto_logout_check)

        layout.addWidget(privacy_group)

        layout.addStretch()

        return widget

    def _create_finish_step(self) -> QWidget:
        """创建完成设置步骤"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setSpacing(20)
        layout.setContentsMargins(8, 8, 8, 8)

        # 完成图标和标题
        icon_label = QLabel("🎉")
        icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        icon_label.setFont(QFont("", 64))
        layout.addWidget(icon_label)

        title_label = QLabel("设置完成！")
        title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title_label.setFont(QFont("", 24, QFont.Weight.Bold))
        title_label.setStyleSheet("color: #89b4fa;")
        layout.addWidget(title_label)

        # 恭喜信息
        congrats_label = QLabel(
            "恭喜！您已成功完成 OpenEmail 的初始设置。\n"
            "点击「开始使用」按钮进入主界面。"
        )
        congrats_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        congrats_label.setFont(QFont("", 13))
        congrats_label.setStyleSheet("color: #cdd6f4; line-height: 1.5;")
        congrats_label.setWordWrap(True)
        layout.addWidget(congrats_label)

        # 下一步提示
        tips_frame = QFrame()
        tips_frame.setFrameStyle(QFrame.Shape.Box)
        tips_frame.setStyleSheet("""
            QFrame {
                background: #313244;
                border: 1px solid #45475a;
                border-radius: 6px;
                padding: 16px;
                margin: 12px 0;
            }
        """)
        tips_layout = QVBoxLayout(tips_frame)
        tips_layout.setSpacing(8)

        tips_title = QLabel("📋 使用建议:")
        tips_title.setFont(QFont("", 13, QFont.Weight.Bold))
        tips_layout.addWidget(tips_title)

        tips = [
            "• 在「文件」菜单中添加更多邮箱账户",
            "• 设置邮件过滤规则来管理订阅邮件",
            "• 尝试不同的主题（浅色/深色模式）",
            "• 使用搜索功能快速查找邮件",
        ]

        for tip in tips:
            tip_label = QLabel(tip)
            tip_label.setWordWrap(True)
            tip_label.setStyleSheet("font-size: 12px; margin-left: 8px;")
            tips_layout.addWidget(tip_label)

        layout.addWidget(tips_frame)

        layout.addStretch()
        return widget

    def _show_step(self, step_index: int) -> None:
        """显示指定步骤"""
        self._current_step = step_index
        self.steps_widget.setCurrentIndex(step_index)
        self.progress_bar.setValue(step_index)

        # 更新按钮状态
        self.prev_btn.setEnabled(step_index > 0)

        if step_index == self.steps_widget.count() - 1:
            self.next_btn.setText("开始使用")
            self.next_btn.setProperty("class", "success")
        else:
            self.next_btn.setText("下一步")
            self.next_btn.setProperty("class", "primary")

        if step_index == 1:  # 账户设置页
            self._validate_account_step()

    def _go_previous(self) -> None:
        """上一步"""
        if self._current_step > 0:
            self._show_step(self._current_step - 1)

    def _go_next(self) -> None:
        """下一步（支持幂等操作）"""
        # 防止重复点击：检查按钮是否已禁用
        if not self.next_btn.isEnabled():
            logger.debug("下一步按钮已被禁用，忽略重复点击")
            return

        if self._current_step == 0:
            # 欢迎页面，直接到下一步
            self._show_step(1)

        elif self._current_step == 1:
            # 账户设置页面，需要验证账户信息
            if self._validate_account_step():
                self._show_step(2)

        elif self._current_step == 2:
            # 选项页面，保存设置
            self._save_settings()
            self._show_step(3)

        elif self._current_step == 3:
            # 完成页面，添加账户并关闭
            # 临时禁用按钮防止重复提交
            self.next_btn.setEnabled(False)

            # 异步执行账户添加，避免阻塞UI
            from PyQt6.QtCore import QTimer

            QTimer.singleShot(0, self._execute_account_addition)

    def _execute_account_addition(self) -> None:
        """执行账户添加操作（固化的完成顺序）"""
        try:
            result = self._add_account()

            if result:
                # 固化的对话框关闭和信号发射顺序
                # 1. 关闭对话框（UI层面完成）
                self.accept()
                logger.debug("对话框已关闭")

                # 2. 使用QTimer.singleShot确保UI更新已完成后发射信号
                from PyQt6.QtCore import QTimer

                QTimer.singleShot(0, self._emit_setup_completed)
            else:
                # 添加失败，恢复按钮状态已在 _add_account 的 finally 中处理
                pass

        except Exception as e:
            logger.error("执行账户添加时发生异常: %s", str(e))
            self._show_error_state(f"系统错误: {str(e)}")
            # 保险起见，恢复按钮状态
            self.next_btn.setEnabled(True)
            self.prev_btn.setEnabled(self._current_step > 0)

    def _emit_setup_completed(self) -> None:
        """在UI更新完成后发射setup_completed信号"""
        try:
            logger.debug("发射 setup_completed 信号")
            self.setup_completed.emit()

            # 验证状态持久化
            if settings.onboarding_state != "completed":
                logger.error(
                    "状态不一致：信号发射时状态不是 completed，而是 %s",
                    settings.onboarding_state,
                )
                # 自动纠正
                settings.onboarding_state = "completed"
        except Exception as e:
            logger.error("发射 setup_completed 信号时出错: %s", str(e))

    def _on_provider_changed(self, index: int) -> None:
        """服务商改变"""
        provider = self._provider_combo.currentData()

        # 清空测试结果
        self._test_result.setText("")

        if provider == "custom":
            self._email_edit.setPlaceholderText("your@email.com")
            self._password_edit.setPlaceholderText("密码")
            self._oauth_btn.setVisible(False)
        else:
            preset = PROVIDER_PRESETS.get(provider, {})
            auth_type = preset.get("auth_type", "password")

            if auth_type == "app_password":
                self._password_edit.setPlaceholderText("授权码（非登录密码）")
                self._oauth_btn.setVisible(False)
            elif auth_type == "oauth2":
                self._password_edit.setPlaceholderText("OAuth2授权中...")
                self._password_edit.setEnabled(False)
                self._oauth_btn.setVisible(True)
                self._oauth_btn.setText(
                    "Gmail OAuth 授权" if provider == "gmail" else "Outlook OAuth 授权"
                )
            else:
                self._password_edit.setPlaceholderText("登录密码")
                self._oauth_btn.setVisible(False)

    def _test_connection(self) -> None:
        """测试连接（使用统一测试器）"""
        if not self._validate_account_step():
            return

        self._test_btn.setEnabled(False)
        self._test_btn.setText("测试连接中...")
        self._test_result.setText("正在连接服务器...")

        provider = self._provider_combo.currentData()
        email = self._email_edit.text().strip()
        password = self._password_edit.text()

        # 创建临时账户获取配置
        account = Account.create_from_preset(provider, email, "", password)

        # 准备账户数据
        account_data = {
            "email": email,
            "password": password,
            "imap_host": account.imap_host,
            "imap_port": account.imap_port,
            "smtp_host": account.smtp_host,
            "smtp_port": account.smtp_port,
            "pop3_host": account.pop3_host,
            "pop3_port": account.pop3_port,
            "eas_host": account.eas_host,
            "eas_path": account.eas_path,
            "ssl_mode": account.ssl_mode,
            "auth_type": account.auth_type,
        }

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
            self._test_result.setText("❌ 无可用协议配置")
            self._test_btn.setEnabled(True)
            self._test_btn.setText("测试连接")
            return

        # 启动测试
        tester = get_connection_tester()
        self._test_worker = tester.start_test(
            account_data=account_data,
            protocols=protocols,
            callback=self._on_test_completed,
        )

        # 设置超时恢复（防止测试卡死）
        from PyQt6.QtCore import QTimer

        QTimer.singleShot(45000, self._on_test_timeout)

    def _on_test_completed(self, summary: ConnectionTestSummary) -> None:
        """连接测试完成回调"""
        self._test_btn.setEnabled(True)
        self._test_btn.setText("测试连接")

        # 分析验证级别
        details = []
        warning_details = []
        error_details = []

        incoming_verified = False
        outgoing_verified = False
        only_precheck = False
        unsupported_protocol = False

        for result in summary.results:
            protocol = result.protocol.value.upper()
            success = result.success
            level = getattr(result, "level", "unknown")
            error_msg = result.error_message or ""

            # 分析验证级别
            if result.success:
                if level == "full_protocol_verified":
                    details.append(f"✅ {protocol}: 完全验证通过")
                    if protocol in ["IMAP", "POP3"]:
                        incoming_verified = True
                    if protocol == "SMTP":
                        outgoing_verified = True
                elif level == "auth_verified":
                    details.append(f"✅ {protocol}: 认证通过")
                    if protocol in ["IMAP", "POP3"]:
                        incoming_verified = True
                    if protocol == "SMTP":
                        outgoing_verified = True
                elif level == "connection_verified":
                    details.append(f"○ {protocol}: 连接已建立")
                elif level == "endpoint_verified":
                    details.append(f"○ {protocol}: 服务端点可达")
                elif level == "precheck":
                    details.append(f"⚠ {protocol}: 仅预检通过")
                    only_precheck = True
                else:
                    details.append(f"✓ {protocol}: 验证通过")
            else:
                # 失败情况
                if (
                    "not_implemented" in str(level).lower()
                    or "unsupported" in str(level).lower()
                ):
                    warning_details.append(f"⚠ {protocol}: 协议未支持")
                    unsupported_protocol = True
                elif (
                    "auth" in error_msg.lower()
                    or "invalid credentials" in error_msg.lower()
                ):
                    error_details.append(f"✗ {protocol}: 认证失败 - {error_msg[:30]}")
                elif (
                    "timeout" in error_msg.lower()
                    or "timed out" in error_msg.lower()
                    or result.status == "timeout"
                ):
                    error_details.append(f"✗ {protocol}: 连接超时")
                elif "ssl" in error_msg.lower() or "tls" in error_msg.lower():
                    error_details.append(
                        f"✗ {protocol}: SSL/TLS 错误 - {error_msg[:30]}"
                    )
                else:
                    error_details.append(f"✗ {protocol}: {error_msg[:60]}")

        # 构建状态文本
        status_summary = ""

        if incoming_verified and outgoing_verified:
            status_summary = "✅ 收信和发信都已验证"
        elif incoming_verified and not outgoing_verified:
            status_summary = "✅ 收信已验证 ⚠ 发信未验证"
        elif not incoming_verified and outgoing_verified:
            status_summary = "⚠ 发信已验证 ✗ 收信未验证"
        elif only_precheck:
            status_summary = "⚠ 仅预检通过"
        elif unsupported_protocol:
            status_summary = "⚠ 部分协议未支持"
        elif error_details:
            status_summary = "✗ 验证失败"
        else:
            status_summary = "❓ 验证状态未知"

        self._test_result.setText(status_summary)

        # 构建详细tooltip
        tooltip_lines = [f"验证状态: {status_summary}"]
        if details:
            tooltip_lines.append("\n通过的项目:")
            tooltip_lines.extend(details)

        if warning_details:
            tooltip_lines.append("\n警告的项目:")
            tooltip_lines.extend(warning_details)

        if error_details:
            tooltip_lines.append("\n失败的项目:")
            tooltip_lines.extend(error_details)

        tooltip_lines.append(
            f"\n总计: {summary.successful_tests}/{summary.total_tests} 个协议通过"
        )

        self._test_result.setToolTip("\n".join(tooltip_lines))

    def _on_test_timeout(self) -> None:
        """测试超时处理"""
        if not self._test_btn.isEnabled():
            # 按钮仍处于禁用状态，说明测试可能卡住了
            tester = get_connection_tester()
            if tester.is_testing():
                tester.cancel_current_test()
                self._test_result.setText("❌ 测试超时，请重试")
                self._test_btn.setEnabled(True)
                self._test_btn.setText("测试连接")

    def _save_settings(self) -> None:
        """保存设置选项"""
        import json
        from openemail.config import settings

        settings_dict = {
            "auto_sync": self._auto_sync_check.isChecked(),
            "desktop_notify": self._desktop_notify_check.isChecked(),
            "sound_notify": self._sound_notify_check.isChecked(),
            "encrypt_local": self._encrypt_local_check.isChecked(),
            "auto_logout": self._auto_logout_check.isChecked(),
        }

        settings.set("general/settings", json.dumps(settings_dict))

    def _add_account(self) -> bool:
        """添加账户（固化的完成顺序）"""
        try:
            # 防止重复点击
            self.next_btn.setEnabled(False)
            self.prev_btn.setEnabled(False)

            # 1. 进入submitting状态（更新UI和持久化状态）
            self._update_finish_step_state("submitting")
            # 立即持久化submitting状态，以便崩溃恢复
            settings.onboarding_state = "submitting"

            if not self._validate_account_step():
                self._show_error_state("账户信息验证失败")
                # 回退到in_progress状态
                settings.onboarding_state = "in_progress"
                return False

            provider = self._provider_combo.currentData()
            email = self._email_edit.text().strip()
            password = self._password_edit.text()

            # 防止重复保存：检查是否已经有相同邮箱的账户
            from openemail.models.account import Account

            existing_accounts = Account.get_all()
            for acc in existing_accounts:
                if acc.email.lower() == email.lower():
                    logger.warning("已经存在相同邮箱的账户: %s", email)
                    # 如果已有账户，直接完成引导
                    # 先更新UI状态
                    self._update_finish_step_state("completed")
                    # 再持久化completed状态
                    settings.onboarding_state = "completed"
                    return True

            try:
                # 固化的完成顺序
                # 1. 创建并保存账户
                account = Account.create_from_preset(
                    provider, email, email.split("@")[0], password
                )

                # 特殊处理 OAuth 账户
                if account.auth_type == "oauth2":
                    if hasattr(self, "_oauth_tokens") and self._oauth_tokens:
                        # 如果有真实的OAuth令牌，应用到账户
                        from openemail.core.oauth2_new import OAuthAuthenticator

                        OAuthAuthenticator.apply_to_account(account, self._oauth_tokens)
                        account.mark_for_sync()
                        logger.info("创建 OAuth 账户，已应用真实令牌并标记为同步就绪")
                    elif password in [
                        "[OAuth授权模式]",
                        "[OAuth授权进行中...]",
                        "[✅ OAuth授权成功]",
                    ]:
                        # 对于没有真实令牌的OAuth账户，标记为需要授权
                        account.password = ""  # 清空占位符
                        account.update_status("auth_required")  # 需要授权状态
                        logger.info("创建 OAuth 账户，进入 auth_required 状态")
                    else:
                        # 对于没有令牌也没有标记的OAuth账户，无法创建
                        QMessageBox.warning(
                            self,
                            "保存失败",
                            "OAuth账户需要先完成授权。请点击'OAuth2授权'按钮。",
                        )
                        # 回退到in_progress状态
                        settings.onboarding_state = "in_progress"
                        return False

                account_id = account.save()
                logger.info("账户保存完成: ID=%d", account_id)

                # 2. 创建系统文件夹
                from openemail.models.folder import Folder

                Folder.ensure_system_folders(account_id)
                logger.info("系统文件夹创建完成")

                # 3. 持久化 completed 状态
                settings.onboarding_state = "completed"
                logger.info("引导状态持久化为 completed")

                # 4. 更新UI状态（但对话框还未关闭）
                self._update_finish_step_state("completed")

                # 5. 发射账户添加信号（注意：对话框还未关闭）
                self.account_added.emit(account_id)

                return True

            except Exception as e:
                logger.error("添加账户失败: %s", str(e))
                self._show_error_state(f"添加账户失败: {str(e)}")
                # 回退到in_progress状态
                settings.onboarding_state = "in_progress"
                return False

        except Exception as e:
            logger.error("添加账户过程中发生异常: %s", str(e))
            self._show_error_state(f"系统错误: {str(e)}")
            # 保守回退到in_progress状态
            try:
                settings.onboarding_state = "in_progress"
            except:
                pass
            return False
        finally:
            # 无论成功失败，都恢复按钮状态（除了 completed 状态）
            if not hasattr(self, "_finish_state") or self._finish_state != "completed":
                self.next_btn.setEnabled(True)
                self.prev_btn.setEnabled(self._current_step > 0)

    def _update_finish_step_state(self, state: str) -> None:
        """更新完成步骤的状态显示"""
        self._finish_state = state

        # 获取完成步骤的 widgets
        finish_widget = self.steps_widget.widget(3)

        if state == "submitting":
            # 修改按钮文本和样式
            self.next_btn.setText("正在保存...")
            self.next_btn.setEnabled(False)
            # 可以添加加载动画或进度指示器
            logger.info("引导状态: 正在提交账户信息")

        elif state == "completed":
            # 成功状态
            self.next_btn.setText("开始使用")
            self.next_btn.setEnabled(True)
            self.next_btn.setProperty("class", "success")
            logger.info("引导状态: 已完成")

        elif state == "recovery_needed":
            # 需要恢复的状态
            self.next_btn.setText("重试")
            self.next_btn.setEnabled(True)
            self.next_btn.setProperty("class", "warning")
            logger.warning("引导状态: 需要恢复")

        elif state == "error":
            # 错误状态
            self.next_btn.setText("重试")
            self.next_btn.setEnabled(True)
            logger.error("引导状态: 发生错误")

    def _show_error_state(self, error_message: str) -> None:
        """显示错误状态"""
        self._update_finish_step_state("error")

        # 创建错误消息框
        error_box = QMessageBox(self)
        error_box.setIcon(QMessageBox.Icon.Warning)
        error_box.setWindowTitle("设置失败")
        error_box.setText(f"账户设置过程中发生错误：\n{error_message}")
        error_box.setDetailedText(
            "请检查网络连接和账户信息是否正确。\n错误详情：\n" + str(error_message)
        )

        # 添加重试选项
        error_box.addButton("重试", QMessageBox.ButtonRole.ActionRole)
        error_box.addButton("跳过验证", QMessageBox.ButtonRole.ActionRole)
        error_box.addButton("取消", QMessageBox.ButtonRole.RejectRole)

        response = error_box.exec()

        if error_box.clickedButton().text() == "重试":
            # 用户选择重试，重新尝试添加账户
            self._update_finish_step_state("submitting")
            # 重新执行添加账户逻辑
            return
        elif error_box.clickedButton().text() == "跳过验证":
            # 用户选择跳过验证（不推荐）
            logger.warning("用户选择跳过账户验证")
            # 标记状态为 completed 但仍然没有有效账户
            settings.onboarding_state = "completed"
            self.setup_completed.emit()
            self.accept()
        else:
            # 用户选择取消，回到上一步
            self._show_step(self._current_step - 1)

    def _on_oauth_clicked(self):
        """OAuth授权按钮点击事件 - 真实调用OAuth流程"""
        provider = self._provider_combo.currentData()
        email = self._email_edit.text().strip()

        if not email:
            QMessageBox.warning(self, "授权失败", "请输入邮箱地址")
            return

        # 映射provider到对应的oauth_provider
        if provider == "gmail_oauth":
            oauth_provider = "google"
        elif provider == "outlook":
            oauth_provider = "microsoft"
        else:
            # 尝试从邮箱推断
            from openemail.models.account import Account

            oauth_provider = Account.get_ouath_provider_for_email(email)
            if not oauth_provider:
                QMessageBox.warning(self, "授权失败", "不支持此邮箱的OAuth授权")
                return

        # 禁用按钮，显示授权中状态
        self._oauth_btn.setEnabled(False)
        self._oauth_btn.setText("授权中...")

        # 设置密码字段为授权状态
        self._password_edit.setText("[OAuth授权进行中...]")
        self._password_edit.setEnabled(False)

        # 检查OAuth配置是否可用
        try:
            from openemail.core.oauth2_new import OAuthManager

            oauth_mgr = OAuthManager()

            if not oauth_mgr.is_provider_available(oauth_provider):
                QMessageBox.warning(
                    self,
                    "OAuth未配置",
                    f"{oauth_provider.capitalize()} OAuth客户端未配置。\n\n"
                    "请检查 ~/.config/openemail/oauth_creds.json 文件。",
                )
                self._reset_oauth_button()
                return

            # 启动真实OAuth授权流程
            self._oauth_manager = oauth_mgr

            def oauth_callback(tokens=None, error=None):
                """OAuth授权完成回调"""
                from PyQt6.QtCore import QTimer

                QTimer.singleShot(
                    0,
                    lambda: self._handle_oauth_result(
                        tokens, error, email, oauth_provider
                    ),
                )

            oauth_mgr.authorize(oauth_provider, oauth_callback)

        except Exception as e:
            import logging

            logger = logging.getLogger(__name__)
            logger.error(f"OAuth授权启动失败: {e}")
            QMessageBox.warning(self, "授权失败", f"OAuth授权过程启动失败:\n{str(e)}")
            self._reset_oauth_button()

    def _handle_oauth_result(self, tokens, error, email, oauth_provider):
        """处理OAuth授权结果"""
        if error:
            from openemail.core.oauth2_new import get_oauth_error_message

            error_msg, suggestion = get_oauth_error_message(error.code)

            QMessageBox.warning(self, "授权失败", f"{error_msg}\n\n建议: {suggestion}")
            self._password_edit.setText("")
            self._password_edit.setEnabled(True)
            self._reset_oauth_button()
            return

        if not tokens:
            QMessageBox.warning(self, "授权失败", "未获取到OAuth令牌")
            self._password_edit.setText("")
            self._password_edit.setEnabled(True)
            self._reset_oauth_button()
            return

        # 授权成功，保存令牌到临时变量
        self._oauth_tokens = tokens
        self._oauth_provider_success = oauth_provider

        # 在密码字段显示成功标记
        self._password_edit.setText("[✅ OAuth授权成功]")
        self._password_edit.setEnabled(False)

        # 更新按钮状态
        provider_name = "Google" if oauth_provider == "google" else "Microsoft"
        self._oauth_btn.setText(f"{provider_name} OAuth 已授权")

        QMessageBox.information(
            self,
            "授权成功",
            f"✅ OAuth授权成功！\n\n"
            f"• {provider_name} OAuth令牌已获取\n"
            f"• 请点击'下一步'完成账户创建\n"
            f"• 令牌将会在保存账户时持久化到数据库",
        )

    def _reset_oauth_button(self):
        """重置OAuth按钮状态"""
        provider = self._provider_combo.currentData()
        self._oauth_btn.setEnabled(True)
        self._oauth_btn.setText(
            "Gmail OAuth 授权" if provider == "gmail" else "Outlook OAuth 授权"
        )

    def _validate_account_step(self) -> bool:
        """验证账户信息（返回布尔值）"""
        email = self._email_edit.text().strip()
        password = self._password_edit.text()

        # 检查是否是OAuth提供商
        provider = self._provider_combo.currentData()
        preset = PROVIDER_PRESETS.get(provider, {}) if provider != "custom" else {}
        auth_type = preset.get("auth_type", "password")

        if not email:
            QMessageBox.warning(self, "邮箱为空", "请输入邮箱地址")
            return False

        # OAuth 账户不需要密码
        if auth_type == "oauth2":
            self._password_edit.setText("[OAuth授权模式]")
            self._password_edit.setEnabled(False)
            # 显示OAuth专用提示
            QMessageBox.information(
                self,
                "OAuth账户设置",
                "✅ OAuth账户设置完成\n\n"
                "• 此账户使用OAuth2授权模式\n"
                "• 无需输入密码\n"
                "• 点击下一步完成账户创建\n\n"
                "注意：实际使用时需要完成真实的OAuth授权流程。",
            )
            return True
        else:
            # 非OAuth账户需要密码
            if not password:
                QMessageBox.warning(self, "密码为空", "请输入密码或授权码")
                return False

        # 简单的邮箱格式验证
        if "@" not in email or "." not in email.split("@")[1]:
            QMessageBox.warning(self, "邮箱格式错误", "请输入有效的邮箱地址")
            return False

        return True
