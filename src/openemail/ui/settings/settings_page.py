from __future__ import annotations

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QRadioButton,
    QScrollArea,
    QSpinBox,
    QTableWidget,
    QTableWidgetItem,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from openemail.config import settings
from openemail.models.account import Account
from openemail.storage.database import db

_CATPPUCCIN_BASE = "#F7F4EE"
_CATPPUCCIN_SURFACE = "#FBF8F3"
_CATPPUCCIN_OVERLAY = "#E8E1D8"
_CATPPUCCIN_TEXT = "#141413"
_CATPPUCCIN_SUBTEXT = "#6C665F"
_CATPPUCCIN_BLUE = "#7C8A9A"
_CATPPUCCIN_GREEN = "#7D9174"
_CATPPUCCIN_RED = "#C97850"
_CATPPUCCIN_YELLOW = "#C97850"
_CATPPUCCIN_LAVENDER = "#7C8A9A"
_CATPPUCCIN_MANTLE = "#FBF8F3"
_CATPPUCCIN_CRUST = "#E8E1D8"

_CALDAV_PROVIDERS = {
    "google": "Google",
    "nextcloud": "Nextcloud",
    "fastmail": "Fastmail",
    "icloud": "iCloud",
    "custom": "自定义",
}


class SettingsPageWidget(QWidget):
    theme_changed = pyqtSignal()
    accounts_changed = pyqtSignal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setProperty("class", "settings-page")
        self._setup_ui()
        self._apply_styles()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        header = QWidget()
        header.setProperty("class", "settings-header")
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(20, 16, 20, 16)
        title = QLabel("设置")
        title.setProperty("class", "settings-title")
        title_font = QFont()
        title_font.setPointSize(18)
        title_font.setBold(True)
        title.setFont(title_font)
        header_layout.addWidget(title)
        header_layout.addStretch()
        layout.addWidget(header)

        self._tab_widget = QTabWidget()
        self._tab_widget.setProperty("class", "settings-tabs")

        self._tab_widget.addTab(self._create_general_tab(), "通用")
        self._tab_widget.addTab(self._create_accounts_tab(), "账户")
        self._tab_widget.addTab(self._create_sync_tab(), "同步")
        self._tab_widget.addTab(self._create_filter_tab(), "过滤规则")
        self._tab_widget.addTab(self._create_tools_tab(), "工具")
        self._tab_widget.addTab(self._create_about_tab(), "关于")

        layout.addWidget(self._tab_widget)

    def _wrap_in_scroll(self, content: QWidget) -> QScrollArea:
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        scroll.setProperty("class", "settings-scroll")
        scroll.setWidget(content)
        return scroll

    def _create_general_tab(self) -> QScrollArea:
        content = QWidget()
        layout = QVBoxLayout(content)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(20)

        theme_group = QGroupBox("主题")
        theme_group.setProperty("class", "settings-group")
        theme_layout = QVBoxLayout(theme_group)
        theme_layout.setSpacing(10)

        self._theme_light = QRadioButton("浅色")
        self._theme_dark = QRadioButton("深色")
        self._theme_system = QRadioButton("跟随系统")

        current_theme = settings.theme
        if current_theme == "light":
            self._theme_light.setChecked(True)
        elif current_theme == "dark":
            self._theme_dark.setChecked(True)
        else:
            self._theme_system.setChecked(True)

        for rb in (self._theme_light, self._theme_dark, self._theme_system):
            rb.setProperty("class", "settings-radio")
            theme_layout.addWidget(rb)

        layout.addWidget(theme_group)

        sync_group = QGroupBox("同步")
        sync_group.setProperty("class", "settings-group")
        sync_form = QFormLayout(sync_group)
        sync_form.setSpacing(10)

        self._sync_interval_spin = QSpinBox()
        self._sync_interval_spin.setRange(1, 60)
        self._sync_interval_spin.setValue(settings.sync_interval)
        self._sync_interval_spin.setSuffix(" 分钟")
        self._sync_interval_spin.setProperty("class", "settings-spin")
        sync_form.addRow("同步间隔:", self._sync_interval_spin)

        layout.addWidget(sync_group)

        lang_group = QGroupBox("语言")
        lang_group.setProperty("class", "settings-group")
        lang_layout = QHBoxLayout(lang_group)
        lang_label = QLabel("中文")
        lang_label.setProperty("class", "settings-value")
        lang_layout.addWidget(lang_label)
        lang_layout.addStretch()
        layout.addWidget(lang_group)

        search_group = QGroupBox("搜索")
        search_group.setProperty("class", "settings-group")
        search_layout = QVBoxLayout(search_group)

        self._semantic_search_check = QCheckBox("启用语义搜索（实验性）")
        self._semantic_search_check.setChecked(
            settings.get("semantic_search_enabled", False)
        )
        self._semantic_search_check.setProperty("class", "settings-check")
        search_layout.addWidget(self._semantic_search_check)

        semantic_hint = QLabel(
            "语义搜索需要安装额外依赖（numpy 等），启用后搜索速度可能降低。"
        )
        semantic_hint.setProperty("class", "settings-subtext")
        semantic_hint.setWordWrap(True)
        search_layout.addWidget(semantic_hint)

        layout.addWidget(search_group)

        self._save_general_btn = QPushButton("保存设置")
        self._save_general_btn.setProperty("class", "primary")
        self._save_general_btn.clicked.connect(self._save_general_settings)
        layout.addWidget(self._save_general_btn)

        layout.addStretch()
        return self._wrap_in_scroll(content)

    def _create_accounts_tab(self) -> QScrollArea:
        content = QWidget()
        layout = QVBoxLayout(content)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(16)

        self._account_table = QTableWidget()
        self._account_table.setColumnCount(4)
        self._account_table.setHorizontalHeaderLabels(["名称", "邮箱", "协议", "状态"])
        self._account_table.horizontalHeader().setStretchLastSection(True)
        self._account_table.setSelectionBehavior(
            QTableWidget.SelectionBehavior.SelectRows
        )
        self._account_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self._account_table.setProperty("class", "settings-table")
        self._account_table.setAlternatingRowColors(True)
        layout.addWidget(self._account_table)

        btn_layout = QHBoxLayout()
        btn_layout.addStretch()

        self._add_account_btn = QPushButton("添加邮箱")
        self._add_account_btn.setProperty("class", "primary")
        self._add_account_btn.clicked.connect(self._on_add_account)
        btn_layout.addWidget(self._add_account_btn)

        self._edit_account_btn = QPushButton("编辑")
        self._edit_account_btn.setProperty("class", "secondary")
        self._edit_account_btn.clicked.connect(self._on_edit_account)
        btn_layout.addWidget(self._edit_account_btn)

        self._delete_account_btn = QPushButton("删除")
        self._delete_account_btn.setProperty("class", "danger")
        self._delete_account_btn.clicked.connect(self._on_delete_account)
        btn_layout.addWidget(self._delete_account_btn)

        self._set_default_btn = QPushButton("设为默认")
        self._set_default_btn.setProperty("class", "secondary")
        self._set_default_btn.clicked.connect(self._on_set_default_account)
        btn_layout.addWidget(self._set_default_btn)

        layout.addLayout(btn_layout)
        layout.addStretch()

        self._load_accounts()
        return self._wrap_in_scroll(content)

    def _create_sync_tab(self) -> QScrollArea:
        content = QWidget()
        layout = QVBoxLayout(content)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(20)

        caldav_group = QGroupBox("CalDAV 日历同步")
        caldav_group.setProperty("class", "settings-group")
        caldav_form = QFormLayout(caldav_group)
        caldav_form.setSpacing(10)

        self._caldav_enabled = QCheckBox("启用 CalDAV 同步")
        self._caldav_enabled.setChecked(settings.get("calendar_sync_enabled", False))
        self._caldav_enabled.setProperty("class", "settings-check")
        caldav_form.addRow(self._caldav_enabled)

        self._caldav_provider = QComboBox()
        for key, name in _CALDAV_PROVIDERS.items():
            self._caldav_provider.addItem(name, key)
        self._caldav_provider.setProperty("class", "settings-combo")
        self._caldav_provider.currentIndexChanged.connect(
            self._on_caldav_provider_changed
        )
        caldav_form.addRow("服务商:", self._caldav_provider)

        self._caldav_url = QLineEdit()
        self._caldav_url.setPlaceholderText("CalDAV 服务器 URL")
        self._caldav_url.setProperty("class", "settings-input")
        caldav_form.addRow("服务器 URL:", self._caldav_url)

        self._caldav_username = QLineEdit()
        self._caldav_username.setPlaceholderText("用户名/邮箱")
        self._caldav_username.setProperty("class", "settings-input")
        caldav_form.addRow("用户名:", self._caldav_username)

        self._caldav_password = QLineEdit()
        self._caldav_password.setEchoMode(QLineEdit.EchoMode.Password)
        self._caldav_password.setPlaceholderText("密码/应用密码")
        self._caldav_password.setProperty("class", "settings-input")
        caldav_form.addRow("密码:", self._caldav_password)

        self._test_caldav_btn = QPushButton("测试连接")
        self._test_caldav_btn.setProperty("class", "secondary")
        self._test_caldav_btn.clicked.connect(self._test_caldav_connection)
        caldav_form.addRow(self._test_caldav_btn)

        layout.addWidget(caldav_group)

        todo_group = QGroupBox("待办同步")
        todo_group.setProperty("class", "settings-group")
        todo_layout = QVBoxLayout(todo_group)

        self._todo_enabled = QCheckBox("启用待办同步")
        self._todo_enabled.setChecked(settings.get("todo_sync_enabled", False))
        self._todo_enabled.setProperty("class", "settings-check")
        todo_layout.addWidget(self._todo_enabled)

        layout.addWidget(todo_group)
        layout.addStretch()

        return self._wrap_in_scroll(content)

    def _create_filter_tab(self) -> QScrollArea:
        content = QWidget()
        layout = QVBoxLayout(content)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(16)

        self._filter_table = QTableWidget()
        self._filter_table.setColumnCount(4)
        self._filter_table.setHorizontalHeaderLabels(
            ["名称", "类型", "匹配字段", "动作"]
        )
        self._filter_table.horizontalHeader().setStretchLastSection(True)
        self._filter_table.setSelectionBehavior(
            QTableWidget.SelectionBehavior.SelectRows
        )
        self._filter_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self._filter_table.setProperty("class", "settings-table")
        self._filter_table.setAlternatingRowColors(True)
        layout.addWidget(self._filter_table)

        btn_layout = QHBoxLayout()
        btn_layout.addStretch()

        self._add_filter_btn = QPushButton("新建规则")
        self._add_filter_btn.setProperty("class", "primary")
        self._add_filter_btn.clicked.connect(self._on_add_filter)
        btn_layout.addWidget(self._add_filter_btn)

        self._edit_filter_btn = QPushButton("编辑")
        self._edit_filter_btn.setProperty("class", "secondary")
        self._edit_filter_btn.clicked.connect(self._on_edit_filter)
        btn_layout.addWidget(self._edit_filter_btn)

        self._delete_filter_btn = QPushButton("删除")
        self._delete_filter_btn.setProperty("class", "danger")
        self._delete_filter_btn.clicked.connect(self._on_delete_filter)
        btn_layout.addWidget(self._delete_filter_btn)

        layout.addLayout(btn_layout)
        layout.addStretch()

        self._load_filter_rules()
        return self._wrap_in_scroll(content)

    def _create_tools_tab(self) -> QScrollArea:
        content = QWidget()
        layout = QVBoxLayout(content)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(16)

        diag_group = QGroupBox("诊断与维护")
        diag_group.setProperty("class", "settings-group")
        diag_layout = QVBoxLayout(diag_group)

        self._health_check_btn = QPushButton("数据库健康检查")
        self._health_check_btn.setProperty("class", "secondary")
        self._health_check_btn.clicked.connect(self._run_health_check)
        diag_layout.addWidget(self._health_check_btn)

        self._rebuild_fts_btn = QPushButton("重建 FTS 索引")
        self._rebuild_fts_btn.setProperty("class", "secondary")
        self._rebuild_fts_btn.clicked.connect(self._run_rebuild_fts)
        diag_layout.addWidget(self._rebuild_fts_btn)

        self._cleanup_att_btn = QPushButton("清理孤儿附件")
        self._cleanup_att_btn.setProperty("class", "secondary")
        self._cleanup_att_btn.clicked.connect(self._run_cleanup_attachments)
        diag_layout.addWidget(self._cleanup_att_btn)

        layout.addWidget(diag_group)
        layout.addStretch()

        return self._wrap_in_scroll(content)

    def _create_about_tab(self) -> QScrollArea:
        content = QWidget()
        layout = QVBoxLayout(content)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(16)
        layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        about_group = QGroupBox("关于")
        about_group.setProperty("class", "settings-group")
        about_layout = QVBoxLayout(about_group)
        about_layout.setSpacing(12)

        app_name = QLabel("OpenEmail")
        app_name_font = QFont()
        app_name_font.setPointSize(22)
        app_name_font.setBold(True)
        app_name.setFont(app_name_font)
        app_name.setAlignment(Qt.AlignmentFlag.AlignCenter)
        app_name.setProperty("class", "about-app-name")
        about_layout.addWidget(app_name)

        version_label = QLabel("版本 0.1.0")
        version_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        version_label.setProperty("class", "settings-value")
        about_layout.addWidget(version_label)

        desc_label = QLabel("Linux桌面邮件客户端")
        desc_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        desc_label.setProperty("class", "settings-subtext")
        about_layout.addWidget(desc_label)

        about_layout.addSpacing(12)

        license_label = QLabel("许可证: GPL v3")
        license_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        license_label.setProperty("class", "settings-value")
        about_layout.addWidget(license_label)

        about_layout.addSpacing(12)

        credits_label = QLabel(
            "基于 PyQt6 构建\n使用 IMAP/SMTP/ActiveSync 协议\n开源邮件客户端项目"
        )
        credits_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        credits_label.setProperty("class", "settings-subtext")
        about_layout.addWidget(credits_label)

        links_label = QLabel(
            '<a href="https://github.com/anomalyco/openemail" style="color: #7C8A9A;">GitHub</a>'
        )
        links_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        links_label.setOpenExternalLinks(True)
        about_layout.addWidget(links_label)

        layout.addWidget(about_group)
        layout.addStretch()

        return self._wrap_in_scroll(content)

    def _load_accounts(self) -> None:
        accounts = Account.get_all()
        self._account_table.setRowCount(len(accounts))
        for i, acc in enumerate(accounts):
            name_item = QTableWidgetItem(acc.name or acc.email)
            if acc.is_default:
                font = name_item.font()
                font.setBold(True)
                name_item.setFont(font)
            self._account_table.setItem(i, 0, name_item)
            self._account_table.setItem(i, 1, QTableWidgetItem(acc.email))
            self._account_table.setItem(i, 2, QTableWidgetItem(acc.protocol.upper()))
            self._account_table.setItem(i, 3, QTableWidgetItem(acc.status_display))

    def _load_filter_rules(self) -> None:
        try:
            rows = db.fetchall("SELECT * FROM filter_rules ORDER BY priority")
        except Exception:
            rows = []
        self._filter_table.setRowCount(len(rows))
        for i, row in enumerate(rows):
            self._filter_table.setItem(i, 0, QTableWidgetItem(row["name"] or ""))
            self._filter_table.setItem(i, 1, QTableWidgetItem(row["rule_type"] or ""))
            self._filter_table.setItem(
                i, 2, QTableWidgetItem(row["match_field"] or "all")
            )
            action_text = row["action"] or ""
            action_target = row["action_target"] or ""
            if action_target:
                action_text = f"{action_text} → {action_target}"
            self._filter_table.setItem(i, 3, QTableWidgetItem(action_text))

    def _save_general_settings(self) -> None:
        if self._theme_light.isChecked():
            new_theme = "light"
        elif self._theme_dark.isChecked():
            new_theme = "dark"
        else:
            new_theme = "system"

        old_theme = settings.theme
        settings.theme = new_theme
        settings.set("sync_interval_minutes", self._sync_interval_spin.value())
        settings.set(
            "semantic_search_enabled", self._semantic_search_check.isChecked()
        )

        if new_theme != old_theme:
            self.theme_changed.emit()

        QMessageBox.information(self, "设置已保存", "通用设置已保存")

    def _on_add_account(self) -> None:
        from openemail.ui.mail.account_dialog import AccountDialog

        dialog = AccountDialog(parent=self)
        dialog.account_saved.connect(self._on_account_saved)
        dialog.exec()

    def _on_edit_account(self) -> None:
        selected = self._account_table.selectedItems()
        if not selected:
            QMessageBox.information(self, "提示", "请先选择一个账户")
            return
        row = selected[0].row()
        accounts = Account.get_all()
        if row < len(accounts):
            from openemail.ui.mail.account_dialog import AccountDialog

            dialog = AccountDialog(account=accounts[row], parent=self)
            dialog.account_saved.connect(self._on_account_saved)
            dialog.exec()

    def _on_delete_account(self) -> None:
        selected = self._account_table.selectedItems()
        if not selected:
            QMessageBox.information(self, "提示", "请先选择一个账户")
            return
        row = selected[0].row()
        accounts = Account.get_all()
        if row < len(accounts):
            reply = QMessageBox.question(
                self,
                "确认删除",
                f"确定要删除账户 {accounts[row].email} 吗？",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            if reply == QMessageBox.StandardButton.Yes:
                accounts[row].delete()
                self._load_accounts()
                self.accounts_changed.emit()

    def _on_set_default_account(self) -> None:
        selected = self._account_table.selectedItems()
        if not selected:
            QMessageBox.information(self, "提示", "请先选择一个账户")
            return
        row = selected[0].row()
        accounts = Account.get_all()
        if row < len(accounts):
            for acc in accounts:
                acc.is_default = False
                acc.save()
            accounts[row].is_default = True
            accounts[row].save()
            self._load_accounts()
            self.accounts_changed.emit()

    def _on_account_saved(self, account_id: int) -> None:
        self._load_accounts()
        self.accounts_changed.emit()

    def _on_caldav_provider_changed(self, index: int) -> None:
        provider_key = self._caldav_provider.currentData()
        url_templates = {
            "google": "https://caldav.googleapis.com/dav/{email}",
            "nextcloud": "https://{server}/remote.php/dav/calendars/{username}/",
            "fastmail": "https://caldav.fastmail.com/dav/{email}",
            "icloud": "https://caldav.icloud.com/{email}",
        }
        if provider_key == "custom":
            self._caldav_url.setEnabled(True)
            self._caldav_url.clear()
        elif provider_key in url_templates:
            self._caldav_url.setEnabled(False)
            self._caldav_url.setText(url_templates[provider_key])

    def _test_caldav_connection(self) -> None:
        self._test_caldav_btn.setEnabled(False)
        self._test_caldav_btn.setText("测试中...")
        QMessageBox.information(self, "测试连接", "CalDAV 连接测试功能开发中")
        self._test_caldav_btn.setEnabled(True)
        self._test_caldav_btn.setText("测试连接")

    def _run_health_check(self) -> None:
        from openemail.storage.database import db

        result = db.health_check()
        if result["ok"] and not result["issues"]:
            QMessageBox.information(self, "健康检查", "数据库状态正常。")
        else:
            lines = ["数据库健康检查发现问题：", ""]
            for issue in result.get("issues", []):
                lines.append(f"- {issue}")
            lines.append("")
            lines.append(f"数据库大小: {result.get('db_size_bytes', 0) / 1024:.1f} KB")
            QMessageBox.warning(self, "健康检查", "\n".join(lines))

    def _run_rebuild_fts(self) -> None:
        from openemail.storage.search import SearchEngine

        ok = SearchEngine.rebuild_fts_index()
        if ok:
            QMessageBox.information(self, "重建索引", "FTS 索引重建成功。")
        else:
            QMessageBox.warning(self, "重建索引", "FTS 索引重建失败，请查看日志。")

    def _run_cleanup_attachments(self) -> None:
        from openemail.storage.mail_store import mail_store

        removed = mail_store.cleanup_orphan_attachments()
        QMessageBox.information(
            self, "清理附件", f"清理完成，共移除 {removed} 个孤儿附件目录。"
        )

    def _on_add_filter(self) -> None:
        from openemail.ui.filter.filter_dialog import FilterRulesDialog

        dialog = FilterRulesDialog(parent=self)
        dialog.finished.connect(self._load_filter_rules)
        dialog.exec()

    def _on_edit_filter(self) -> None:
        selected = self._filter_table.selectedItems()
        if not selected:
            QMessageBox.information(self, "提示", "请先选择一条规则")
            return
        from openemail.ui.filter.filter_dialog import FilterRulesDialog

        dialog = FilterRulesDialog(parent=self)
        dialog.finished.connect(self._load_filter_rules)
        dialog.exec()

    def _on_delete_filter(self) -> None:
        selected = self._filter_table.selectedItems()
        if not selected:
            QMessageBox.information(self, "提示", "请先选择一条规则")
            return
        row = selected[0].row()
        try:
            rows = db.fetchall("SELECT * FROM filter_rules ORDER BY priority")
        except Exception:
            return
        if row < len(rows):
            rule_id = rows[row]["id"]
            reply = QMessageBox.question(
                self,
                "确认删除",
                "确定要删除此过滤规则吗？",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            if reply == QMessageBox.StandardButton.Yes:
                db.delete("filter_rules", "id = ?", (rule_id,))
                self._load_filter_rules()

    def _apply_styles(self) -> None:
        self.setStyleSheet(
            f"""
            SettingsPageWidget {{
                background-color: {_CATPPUCCIN_BASE};
                color: {_CATPPUCCIN_TEXT};
            }}
            .settings-header {{
                background-color: {_CATPPUCCIN_MANTLE};
                border-bottom: 1px solid {_CATPPUCCIN_SURFACE};
            }}
            .settings-title {{
                color: {_CATPPUCCIN_TEXT};
            }}
            QTabWidget::pane {{
                border: 1px solid {_CATPPUCCIN_SURFACE};
                background-color: {_CATPPUCCIN_BASE};
            }}
            QTabBar::tab {{
                background-color: {_CATPPUCCIN_MANTLE};
                color: {_CATPPUCCIN_SUBTEXT};
                padding: 10px 24px;
                border: 1px solid {_CATPPUCCIN_SURFACE};
                border-bottom: none;
                margin-right: 2px;
            }}
            QTabBar::tab:selected {{
                background-color: {_CATPPUCCIN_BASE};
                color: {_CATPPUCCIN_BLUE};
                border-bottom: 2px solid {_CATPPUCCIN_BLUE};
            }}
            QTabBar::tab:hover {{
                background-color: {_CATPPUCCIN_SURFACE};
                color: {_CATPPUCCIN_TEXT};
            }}
            .settings-scroll {{
                background-color: {_CATPPUCCIN_BASE};
                border: none;
            }}
            .settings-group {{
                background-color: {_CATPPUCCIN_MANTLE};
                border: 1px solid {_CATPPUCCIN_SURFACE};
                border-radius: 8px;
                margin-top: 12px;
                padding: 16px;
                color: {_CATPPUCCIN_TEXT};
                font-weight: bold;
            }}
            .settings-group::title {{
                subcontrol-origin: margin;
                left: 12px;
                padding: 0 6px;
                color: {_CATPPUCCIN_LAVENDER};
            }}
            .settings-radio,
            .settings-check {{
                color: {_CATPPUCCIN_TEXT};
                spacing: 8px;
            }}
            .settings-radio::indicator,
            .settings-check::indicator {{
                width: 16px;
                height: 16px;
                border: 2px solid {_CATPPUCCIN_OVERLAY};
                border-radius: 3px;
                background-color: {_CATPPUCCIN_SURFACE};
            }}
            .settings-radio::indicator {{
                border-radius: 8px;
            }}
            .settings-radio::indicator:checked,
            .settings-check::indicator:checked {{
                background-color: {_CATPPUCCIN_BLUE};
                border-color: {_CATPPUCCIN_BLUE};
            }}
            .settings-spin,
            .settings-input,
            .settings-combo {{
                background-color: {_CATPPUCCIN_SURFACE};
                color: {_CATPPUCCIN_TEXT};
                border: 1px solid {_CATPPUCCIN_OVERLAY};
                border-radius: 6px;
                padding: 6px 10px;
                min-height: 28px;
            }}
            .settings-spin:focus,
            .settings-input:focus,
            .settings-combo:focus {{
                border-color: {_CATPPUCCIN_BLUE};
            }}
            .settings-combo::drop-down {{
                border: none;
                width: 24px;
            }}
            .settings-combo QAbstractItemView {{
                background-color: {_CATPPUCCIN_SURFACE};
                color: {_CATPPUCCIN_TEXT};
                border: 1px solid {_CATPPUCCIN_OVERLAY};
                selection-background-color: {_CATPPUCCIN_BLUE};
            }}
            .settings-table {{
                background-color: {_CATPPUCCIN_MANTLE};
                alternate-background-color: {_CATPPUCCIN_SURFACE};
                color: {_CATPPUCCIN_TEXT};
                border: 1px solid {_CATPPUCCIN_SURFACE};
                border-radius: 8px;
                gridline-color: {_CATPPUCCIN_SURFACE};
            }}
            .settings-table::item {{
                padding: 6px;
            }}
            .settings-table::item:selected {{
                background-color: {_CATPPUCCIN_BLUE};
                color: {_CATPPUCCIN_CRUST};
            }}
            .settings-table QHeaderView::section {{
                background-color: {_CATPPUCCIN_SURFACE};
                color: {_CATPPUCCIN_SUBTEXT};
                padding: 8px;
                border: none;
                border-bottom: 2px solid {_CATPPUCCIN_OVERLAY};
                font-weight: bold;
            }}
            QPushButton[class="primary"] {{
                background-color: {_CATPPUCCIN_BLUE};
                color: {_CATPPUCCIN_CRUST};
                border: none;
                border-radius: 6px;
                padding: 8px 20px;
                font-weight: bold;
                min-height: 28px;
            }}
            QPushButton[class="primary"]:hover {{
                background-color: {_CATPPUCCIN_LAVENDER};
            }}
            QPushButton[class="primary"]:pressed {{
                background-color: {_CATPPUCCIN_BLUE};
            }}
            QPushButton[class="secondary"] {{
                background-color: {_CATPPUCCIN_SURFACE};
                color: {_CATPPUCCIN_TEXT};
                border: 1px solid {_CATPPUCCIN_OVERLAY};
                border-radius: 6px;
                padding: 8px 20px;
                min-height: 28px;
            }}
            QPushButton[class="secondary"]:hover {{
                background-color: {_CATPPUCCIN_OVERLAY};
            }}
            QPushButton[class="danger"] {{
                background-color: {_CATPPUCCIN_RED};
                color: {_CATPPUCCIN_CRUST};
                border: none;
                border-radius: 6px;
                padding: 8px 20px;
                font-weight: bold;
                min-height: 28px;
            }}
            QPushButton[class="danger"]:hover {{
                background-color: #7D9174;
            }}
            .settings-value {{
                color: {_CATPPUCCIN_TEXT};
                font-size: 14px;
            }}
            .settings-subtext {{
                color: {_CATPPUCCIN_SUBTEXT};
                font-size: 13px;
            }}
            .about-app-name {{
                color: {_CATPPUCCIN_BLUE};
            }}
            QLabel {{
                color: {_CATPPUCCIN_TEXT};
            }}
            QGroupBox QLabel {{
                color: {_CATPPUCCIN_TEXT};
            }}
            QScrollBar:vertical {{
                background-color: {_CATPPUCCIN_MANTLE};
                width: 10px;
                border-radius: 5px;
            }}
            QScrollBar::handle:vertical {{
                background-color: {_CATPPUCCIN_OVERLAY};
                border-radius: 5px;
                min-height: 30px;
            }}
            QScrollBar::handle:vertical:hover {{
                background-color: {_CATPPUCCIN_SUBTEXT};
            }}
            QScrollBar::add-line:vertical,
            QScrollBar::sub-line:vertical {{
                height: 0px;
            }}
            """
        )
