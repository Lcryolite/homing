#!/usr/bin/env python3
"""
账户管理对话框

批次 D2：主界面账户管理与脏账号恢复
提供用户在主界面管理所有邮箱账号的能力
"""

import logging
from typing import Optional

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QAbstractItemView,
    QDialog,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from openemail.models.account import Account
from openemail.core.connection_status import (
    ConnectionStatus,
    get_status_display,
    get_status_icon,
)
from openemail.ui.mail.account_dialog import AccountDialog

logger = logging.getLogger(__name__)


class AccountsDialog(QDialog):
    """账户管理对话框"""

    accounts_changed = pyqtSignal()  # 账号发生变更时发出的信号

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("账户管理")
        self.setMinimumSize(700, 500)
        self._setup_ui()
        self._load_accounts()

    def _setup_ui(self) -> None:
        """设置UI"""
        layout = QVBoxLayout(self)
        layout.setSpacing(12)

        # 标题和说明
        title_label = QLabel("邮箱账户管理")
        title_label.setStyleSheet("""
            font-size: 16px; 
            font-weight: bold; 
            margin-bottom: 8px;
        """)
        layout.addWidget(title_label)

        desc_label = QLabel(
            "管理您的所有邮箱账户。已验证的账户可用于收发邮件，未验证的账户需要修复。"
        )
        desc_label.setStyleSheet("color: #666; margin-bottom: 16px;")
        layout.addWidget(desc_label)

        # 按钮栏
        button_layout = QHBoxLayout()

        add_btn = QPushButton("添加邮箱")
        add_btn.setStyleSheet("padding: 8px 16px;")
        add_btn.clicked.connect(self._add_account)
        button_layout.addWidget(add_btn)

        edit_btn = QPushButton("编辑")
        edit_btn.setStyleSheet("padding: 8px 16px;")
        edit_btn.clicked.connect(self._edit_account)
        button_layout.addWidget(edit_btn)

        delete_btn = QPushButton("删除")
        delete_btn.setStyleSheet("padding: 8px 16px;")
        delete_btn.clicked.connect(self._delete_account)
        button_layout.addWidget(delete_btn)

        refresh_btn = QPushButton("重新验证")
        refresh_btn.setStyleSheet("padding: 8px 16px;")
        refresh_btn.clicked.connect(self._revalidate_account)
        button_layout.addWidget(refresh_btn)

        default_btn = QPushButton("设为默认")
        default_btn.setStyleSheet("padding: 8px 16px;")
        default_btn.clicked.connect(self._set_default_account)
        button_layout.addWidget(default_btn)

        button_layout.addStretch()

        close_btn = QPushButton("关闭")
        close_btn.clicked.connect(self.accept)
        button_layout.addWidget(close_btn)

        layout.addLayout(button_layout)

        # 表格
        self._table = QTableWidget()
        self._table.setColumnCount(5)
        self._table.setHorizontalHeaderLabels(
            ["名称", "邮箱", "协议", "状态", "最后同步"]
        )
        self._table.horizontalHeader().setSectionResizeMode(
            0, QHeaderView.ResizeMode.Stretch
        )
        self._table.horizontalHeader().setSectionResizeMode(
            1, QHeaderView.ResizeMode.Stretch
        )
        self._table.horizontalHeader().setSectionResizeMode(
            2, QHeaderView.ResizeMode.ResizeToContents
        )
        self._table.horizontalHeader().setSectionResizeMode(
            3, QHeaderView.ResizeMode.ResizeToContents
        )
        self._table.horizontalHeader().setSectionResizeMode(
            4, QHeaderView.ResizeMode.ResizeToContents
        )

        self._table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self._table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        layout.addWidget(self._table)

        # 状态栏
        self._status_label = QLabel("")
        self._status_label.setStyleSheet(
            "color: #666; font-size: 12px; margin-top: 8px;"
        )
        layout.addWidget(self._status_label)

        # 禁用按钮直到选择账户
        edit_btn.setEnabled(False)
        delete_btn.setEnabled(False)
        refresh_btn.setEnabled(False)
        default_btn.setEnabled(False)

    def _load_accounts(self) -> None:
        """加载所有账户到表格"""
        # 获取所有账户，包括不活跃的
        accounts = Account.get_all()

        self._table.setRowCount(len(accounts))

        for row, account in enumerate(accounts):
            # 名称
            name_text = account.name or account.email
            if account.is_default:
                name_text = f"⭐ {name_text}"
            name_item = QTableWidgetItem(name_text)
            name_item.setData(Qt.ItemDataRole.UserRole, account.id)

            # 邮箱
            email_item = QTableWidgetItem(account.email)

            # 协议
            protocol_item = QTableWidgetItem(account.protocol.upper())

            # 状态
            status_text = get_status_display(account.connection_status)
            status_icon = get_status_icon(account.connection_status)
            status_item = QTableWidgetItem(f"{status_icon} {status_text}")

            # 根据状态设置颜色
            if account.connection_status in [
                ConnectionStatus.VERIFIED,
                ConnectionStatus.SYNC_READY,
            ]:
                status_item.setForeground(Qt.GlobalColor.darkGreen)
            elif account.connection_status in [
                ConnectionStatus.AUTH_FAILED,
                ConnectionStatus.NETWORK_FAILED,
            ]:
                status_item.setForeground(Qt.GlobalColor.red)
            elif account.connection_status in [
                ConnectionStatus.VALIDATING,
                ConnectionStatus.AUTH_REQUIRED,
            ]:
                status_item.setForeground(Qt.GlobalColor.yellow)
            elif account.connection_status in [
                ConnectionStatus.UNVERIFIED,
                ConnectionStatus.DRAFT,
            ]:
                status_item.setForeground(Qt.GlobalColor.gray)
            elif account.connection_status == ConnectionStatus.DISABLED:
                status_item.setForeground(Qt.GlobalColor.darkGray)

            # 最后同步
            last_sync = account.last_sync_at or "从未"
            sync_item = QTableWidgetItem(last_sync)

            # 如果不活跃，整行变灰
            if not account.is_active:
                for item in [
                    name_item,
                    email_item,
                    protocol_item,
                    status_item,
                    sync_item,
                ]:
                    item.setForeground(Qt.GlobalColor.gray)

            # 添加到表格
            self._table.setItem(row, 0, name_item)
            self._table.setItem(row, 1, email_item)
            self._table.setItem(row, 2, protocol_item)
            self._table.setItem(row, 3, status_item)
            self._table.setItem(row, 4, sync_item)

        # 更新状态栏
        valid_count = len([acc for acc in accounts if acc.should_sync()])
        need_action_count = len(
            [acc for acc in accounts if not acc.should_sync() and acc.is_active]
        )
        disabled_count = len([acc for acc in accounts if not acc.is_active])

        self._status_label.setText(
            f"总计: {len(accounts)} | "
            f"可用: {valid_count} | "
            f"需修复: {need_action_count} | "
            f"禁用: {disabled_count}"
        )

        # 连接选择变化信号
        self._table.itemSelectionChanged.connect(self._on_selection_changed)

        # 更新按钮状态
        self._update_button_states()

    def _on_selection_changed(self) -> None:
        """表格选择变化时更新按钮状态"""
        self._update_button_states()

    def _update_button_states(self) -> None:
        """更新按钮状态"""
        selected_rows = self._table.selectionModel().selectedRows()
        has_selection = len(selected_rows) > 0

        # 获取选中的账户
        selected_account = None
        if has_selection:
            row = selected_rows[0].row()
            account_id_item = self._table.item(row, 0)
            if account_id_item:
                account_id = account_id_item.data(Qt.ItemDataRole.UserRole)
                selected_account = Account.get_by_id(account_id)

        # 按钮状态
        edit_enabled = has_selection
        delete_enabled = has_selection

        # 重新验证按钮只在需要验证的账户上启用
        refresh_enabled = False
        # 设为默认按钮只在活跃且已验证的账户上启用
        default_enabled = False

        if selected_account and selected_account.is_active:
            if selected_account.connection_status in [
                ConnectionStatus.UNVERIFIED,
                ConnectionStatus.AUTH_FAILED,
                ConnectionStatus.NETWORK_FAILED,
                ConnectionStatus.AUTH_REQUIRED,
            ]:
                refresh_enabled = True
            elif selected_account.connection_status in [
                ConnectionStatus.VERIFIED,
                ConnectionStatus.SYNC_READY,
            ]:
                refresh_enabled = True  # 已验证的账户也可以重新验证
                default_enabled = True  # 已验证的账户可以设为默认

        # 如果选中的已经是默认账户，禁用设为默认按钮
        if selected_account and selected_account.is_default:
            default_enabled = False

        # 设置按钮状态
        for btn in self.findChildren(QPushButton):
            if btn.text() == "✏️ 编辑":
                btn.setEnabled(edit_enabled)
            elif btn.text() == "🗑️ 删除":
                btn.setEnabled(delete_enabled)
            elif btn.text() == "🔄 重新验证":
                btn.setEnabled(refresh_enabled)
            elif btn.text() == "⭐ 设为默认":
                btn.setEnabled(default_enabled)

    def _get_selected_account(self) -> Optional[Account]:
        """获取选中的账户"""
        selected_rows = self._table.selectionModel().selectedRows()
        if not selected_rows:
            return None

        row = selected_rows[0].row()
        account_id_item = self._table.item(row, 0)
        if not account_id_item:
            return None

        account_id = account_id_item.data(Qt.ItemDataRole.UserRole)
        return Account.get_by_id(account_id)

    def _add_account(self) -> None:
        """添加新账户"""
        dialog = AccountDialog(parent=self)
        dialog.account_saved.connect(self._on_account_changed)
        dialog.exec()

    def _edit_account(self) -> None:
        """编辑选中的账户"""
        account = self._get_selected_account()
        if not account:
            return

        dialog = AccountDialog(account, parent=self)
        dialog.account_saved.connect(self._on_account_changed)
        dialog.exec()

    def _delete_account(self) -> None:
        """删除选中的账户"""
        account = self._get_selected_account()
        if not account:
            return

        # 确认对话框
        confirm = QMessageBox.question(
            self,
            "确认删除",
            f"确定要删除账户 '{account.email}' 吗？\n\n"
            f"此操作将删除所有相关邮件、联系人和日历事件。",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )

        if confirm == QMessageBox.StandardButton.Yes:
            try:
                # 先禁用账户
                account.is_active = False
                account.save()

                # 重新加载表格
                self._load_accounts()

                # 发出变更信号
                self.accounts_changed.emit()

                QMessageBox.information(
                    self, "删除成功", f"账户 '{account.email}' 已禁用"
                )

            except Exception as e:
                logger.error("删除账户时出错: %s", str(e))
                QMessageBox.critical(self, "删除失败", f"删除账户时出错: {str(e)}")

    def _revalidate_account(self) -> None:
        """重新验证选中的账户"""
        account = self._get_selected_account()
        if not account:
            return

        # 如果是已验证的账户，确认重新验证
        if account.connection_status in [
            ConnectionStatus.VERIFIED,
            ConnectionStatus.SYNC_READY,
        ]:
            confirm = QMessageBox.question(
                self,
                "重新验证",
                f"确定要重新验证账户 '{account.email}' 吗？\n\n"
                f"如果配置信息已更改，可能需要更新设置。",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.Yes,
            )
            if confirm != QMessageBox.StandardButton.Yes:
                return

        # 在新的对话框中编辑并测试
        dialog = AccountDialog(account, parent=self)
        dialog.account_saved.connect(self._on_account_changed)

        # 显示对话框
        dialog.exec()

    def _set_default_account(self) -> None:
        """设置选中的账户为默认账户"""
        account = self._get_selected_account()
        if not account:
            return

        # 确认设置
        confirm = QMessageBox.question(
            self,
            "设为默认账户",
            f"确定要将 '{account.email}' 设为默认账户吗？\n\n"
            f"撰写邮件、回复邮件等操作将使用此账户。",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.Yes,
        )

        if confirm != QMessageBox.StandardButton.Yes:
            return

        try:
            # 首先清除所有账户的默认标记
            from openemail.storage.database import db

            db.update("accounts", {"is_default": 0}, None, ())

            # 设置选中的账户为默认
            account.is_default = True
            account.save()

            # 重新加载表格
            self._load_accounts()

            # 发出变更信号
            self.accounts_changed.emit()

            QMessageBox.information(
                self, "设置成功", f"已将 '{account.email}' 设为默认账户"
            )

        except Exception as e:
            logger.error("设置默认账户时出错: %s", str(e))
            QMessageBox.critical(self, "设置失败", f"设置默认账户时出错: {str(e)}")

        account = self._get_selected_account()
        if not account:
            return

        # 确认设置
        confirm = QMessageBox.question(
            self,
            "设为默认账户",
            f"确定要将 '{account.email}' 设为默认账户吗？\n\n"
            f"撰写邮件、回复邮件等操作将使用此账户。",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.Yes,
        )

        if confirm != QMessageBox.StandardButton.Yes:
            return

        try:
            # 首先清除所有账户的默认标记
            from openemail.storage.database import db

            db.update("accounts", {"is_default": 0}, None, ())

            # 设置选中的账户为默认
            account.is_default = True
            account.save()

            # 重新加载表格
            self._load_accounts()

            # 发出变更信号
            self.accounts_changed.emit()

            QMessageBox.information(
                self, "设置成功", f"已将 '{account.email}' 设为默认账户"
            )

        except Exception as e:
            logger.error("设置默认账户时出错: %s", str(e))
            QMessageBox.critical(self, "设置失败", f"设置默认账户时出错: {str(e)}")

    def _on_account_changed(self, account_id: int) -> None:
        """账户保存后重新加载列表"""
        self._load_accounts()
        self.accounts_changed.emit()

        # 显示成功消息
        account = Account.get_by_id(account_id)
        if account:
            from openemail.core.connection_status import get_status_display

            status_display = get_status_display(account.connection_status)
            QMessageBox.information(
                self,
                "账户已保存",
                f"账户 '{account.email}' 已保存\n状态: {status_display}",
            )
