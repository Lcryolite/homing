from __future__ import annotations

import logging
from typing import List, Dict, Any
from datetime import datetime

from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QTextEdit,
    QProgressBar,
    QTableWidget,
    QTableWidgetItem,
    QHeaderView,
    QMessageBox,
)

from openemail.models.account import Account
from openemail.core.account_cleanup import (
    run_account_cleanup,
    validate_account_statuses,
    fix_inconsistent_accounts,
    check_email_risk,
)
from openemail.core.connection_status import ConnectionStatus

logger = logging.getLogger(__name__)


class AccountCleanupDialog(QDialog):
    """账户清理工具对话框"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("账户清理工具")
        self.setMinimumSize(800, 600)

        self._setup_ui()
        self._load_accounts()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(12)
        layout.setContentsMargins(16, 16, 16, 16)

        # 标题
        title_label = QLabel("账户清理与状态检查")
        title_label.setStyleSheet("""
            font-size: 18px;
            font-weight: bold;
            padding: 4px 0px;
            background: transparent;
        """)
        layout.addWidget(title_label)

        # 统计信息
        stats_layout = QHBoxLayout()
        stats_layout.setSpacing(8)

        self._total_label = QLabel("总账户: 0")
        self._active_label = QLabel("活跃: 0")
        self._disabled_label = QLabel("禁用: 0")
        self._problem_label = QLabel("问题: 0")

        for label in [
            self._total_label,
            self._active_label,
            self._disabled_label,
            self._problem_label,
        ]:
            label.setStyleSheet("""
                font-size: 12px;
                padding: 4px 8px;
                background: #313244;
                border-radius: 4px;
                border: 1px solid #45475a;
            """)
            stats_layout.addWidget(label)

        stats_layout.addStretch()
        layout.addLayout(stats_layout)

        # 操作按钮
        actions_layout = QHBoxLayout()
        actions_layout.setSpacing(8)

        self._refresh_btn = QPushButton("🔄 刷新")
        self._refresh_btn.clicked.connect(self._load_accounts)
        actions_layout.addWidget(self._refresh_btn)

        self._validate_btn = QPushButton("🔍 检查状态")
        self._validate_btn.clicked.connect(self._run_validation)
        actions_layout.addWidget(self._validate_btn)

        self._cleanup_btn = QPushButton("🧹 自动清理")
        self._cleanup_btn.clicked.connect(self._run_cleanup)
        self._cleanup_btn.setStyleSheet("""
            QPushButton {
                background: #f38ba8;
                color: #1e1e2e;
                font-weight: bold;
            }
        """)
        actions_layout.addWidget(self._cleanup_btn)

        self._export_btn = QPushButton("📋 导出报告")
        self._export_btn.clicked.connect(self._export_report)
        actions_layout.addWidget(self._export_btn)

        actions_layout.addStretch()
        layout.addLayout(actions_layout)

        # 进度条
        self._progress_bar = QProgressBar()
        self._progress_bar.setVisible(False)
        layout.addWidget(self._progress_bar)

        # 状态信息显示
        self._status_text = QTextEdit()
        self._status_text.setReadOnly(True)
        self._status_text.setMaximumHeight(100)
        self._status_text.setStyleSheet("""
            QTextEdit {
                background: #1e1e2e;
                border: 1px solid #45475a;
                border-radius: 6px;
                padding: 8px;
                font-family: monospace;
                font-size: 11px;
            }
        """)
        layout.addWidget(self._status_text)

        # 账户表格
        self._account_table = QTableWidget()
        self._account_table.setColumnCount(7)
        self._account_table.setHorizontalHeaderLabels(
            ["邮箱地址", "显示名", "状态", "活跃", "风险", "最后同步", "操作"]
        )

        self._account_table.horizontalHeader().setStretchLastSection(False)
        self._account_table.horizontalHeader().setSectionResizeMode(
            0, QHeaderView.ResizeMode.Stretch
        )
        self._account_table.horizontalHeader().setSectionResizeMode(
            1, QHeaderView.ResizeMode.ResizeToContents
        )
        self._account_table.horizontalHeader().setSectionResizeMode(
            2, QHeaderView.ResizeMode.ResizeToContents
        )
        self._account_table.horizontalHeader().setSectionResizeMode(
            3, QHeaderView.ResizeMode.ResizeToContents
        )
        self._account_table.horizontalHeader().setSectionResizeMode(
            4, QHeaderView.ResizeMode.ResizeToContents
        )
        self._account_table.horizontalHeader().setSectionResizeMode(
            5, QHeaderView.ResizeMode.ResizeToContents
        )
        self._account_table.horizontalHeader().setSectionResizeMode(
            6, QHeaderView.ResizeMode.ResizeToContents
        )

        self._account_table.setStyleSheet("""
            QTableWidget {
                background: #1e1e2e;
                border: 1px solid #45475a;
                border-radius: 6px;
                gridline-color: #45475a;
            }
            QHeaderView::section {
                background: #313244;
                color: #cdd6f4;
                border: none;
                padding: 6px 8px;
                font-weight: bold;
            }
            QTableWidget::item {
                padding: 6px 8px;
                border-bottom: 1px solid #45475a;
            }
        """)
        layout.addWidget(self._account_table, 1)

        # 关闭按钮
        close_btn = QPushButton("关闭")
        close_btn.clicked.connect(self.accept)
        close_btn.setFixedWidth(80)

        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        btn_layout.addWidget(close_btn)
        layout.addLayout(btn_layout)

    def _load_accounts(self):
        """加载所有账户"""
        try:
            # 清空表格
            self._account_table.setRowCount(0)

            # 获取所有账户
            accounts = Account.get_all()

            # 更新统计
            total = len(accounts)
            active = sum(1 for acc in accounts if acc.is_active)
            disabled = total - active

            self._total_label.setText(f"总账户: {total}")
            self._active_label.setText(f"活跃: {active}")
            self._disabled_label.setText(f"禁用: {disabled}")
            self._problem_label.setText("问题: ...")

            # 填充表格
            problem_count = 0
            self._account_table.setRowCount(total)

            for row, account in enumerate(accounts):
                # 邮箱地址
                email_item = QTableWidgetItem(account.email or "")
                email_item.setFlags(
                    Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable
                )
                self._account_table.setItem(row, 0, email_item)

                # 显示名
                name_item = QTableWidgetItem(account.name or "")
                name_item.setFlags(
                    Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable
                )
                self._account_table.setItem(row, 1, name_item)

                # 状态
                status_item = QTableWidgetItem(account.connection_status.value)
                # 根据状态设置颜色
                if account.connection_status in [
                    ConnectionStatus.VERIFIED,
                    ConnectionStatus.SYNC_READY,
                ]:
                    status_item.setForeground(Qt.GlobalColor.green)
                elif account.connection_status in [
                    ConnectionStatus.ERROR,
                    ConnectionStatus.DISABLED,
                ]:
                    status_item.setForeground(Qt.GlobalColor.red)
                else:
                    status_item.setForeground(Qt.GlobalColor.yellow)
                status_item.setFlags(
                    Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable
                )
                self._account_table.setItem(row, 2, status_item)

                # 活跃状态
                active_item = QTableWidgetItem(
                    "✅ 是" if account.is_active else "❌ 否"
                )
                active_item.setForeground(
                    Qt.GlobalColor.green if account.is_active else Qt.GlobalColor.red
                )
                active_item.setFlags(
                    Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable
                )
                self._account_table.setItem(row, 3, active_item)

                # 风险评估
                risk_info = check_email_risk(account.email)
                risk_text = self._format_risk_level(risk_info["risk_level"])
                risk_item = QTableWidgetItem(risk_text)

                if risk_info["risk_level"] == "high":
                    risk_item.setForeground(Qt.GlobalColor.red)
                    problem_count += 1
                elif risk_info["risk_level"] == "medium":
                    risk_item.setForeground(Qt.GlobalColor.yellow)
                else:
                    risk_item.setForeground(Qt.GlobalColor.green)

                risk_item.setToolTip(
                    f"原因: {risk_info['reason']}\n建议: {risk_info['suggestion']}"
                )
                risk_item.setFlags(
                    Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable
                )
                self._account_table.setItem(row, 4, risk_item)

                # 最后同步时间
                last_sync = account.last_synced_at or "从未同步"
                sync_item = QTableWidgetItem(str(last_sync))
                sync_item.setFlags(
                    Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable
                )
                self._account_table.setItem(row, 5, sync_item)

                # 操作按钮（稍后添加）
                actions_item = QTableWidgetItem("查看详情")
                actions_item.setFlags(
                    Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable
                )
                self._account_table.setItem(row, 6, actions_item)

            # 更新问题计数
            self._problem_label.setText(f"问题: {problem_count}")

            # 显示状态
            current_time = datetime.now().strftime("%H:%M:%S")
            self._status_text.append(
                f"[{current_time}] 已加载 {total} 个账户，发现 {problem_count} 个潜在问题"
            )

        except Exception as e:
            logger.error(f"加载账户失败: {e}")
            self._show_error("加载账户失败", str(e))

    def _format_risk_level(self, risk_level: str) -> str:
        """格式化风险等级"""
        icons = {"high": "🔴 高风险", "medium": "🟡 中等风险", "low": "🟢 低风险"}
        return icons.get(risk_level, "⚪ 未知风险")

    def _run_validation(self):
        """运行状态验证"""
        try:
            self._show_progress("正在检查账户状态...")

            # 运行验证
            issues = validate_account_statuses()

            self._hide_progress()

            if issues:
                self._status_text.append("\n检查结果:")
                for issue in issues:
                    self._status_text.append(f"  - {issue}")
                self._status_text.append(f"总计发现 {len(issues)} 个问题")

                # 更新问题计数
                self._problem_label.setText(f"问题: {len(issues)}")
            else:
                self._status_text.append("✅ 账户状态正常，未发现问题")

        except Exception as e:
            logger.error(f"验证失败: {e}")
            self._show_error("验证失败", str(e))
        finally:
            self._hide_progress()

    def _run_cleanup(self):
        """运行自动清理"""
        try:
            reply = QMessageBox.question(
                self,
                "确认清理",
                "这将运行账户清理工具，修复不一致的状态和标记高风险邮箱。\n\n确定要继续吗？",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )

            if reply != QMessageBox.StandardButton.Yes:
                return

            self._show_progress("正在运行账户清理...")

            # 运行清理
            run_account_cleanup()

            # 延迟重新加载账户数据
            QTimer.singleShot(500, self._reload_after_cleanup)

        except Exception as e:
            logger.error(f"清理失败: {e}")
            self._show_error("清理失败", str(e))
        finally:
            self._hide_progress()

    def _reload_after_cleanup(self):
        """清理后重新加载"""
        try:
            self._status_text.append("✅ 账户清理完成")

            # 重新加载表格数据
            self._load_accounts()

        except Exception as e:
            logger.error(f"重新加载失败: {e}")

    def _export_report(self):
        """导出报告"""
        try:
            # 获取当前所有账户
            accounts = Account.get_all()

            # 运行验证获取问题列表
            issues = validate_account_statuses()

            # 生成报告内容
            report_lines = []
            report_lines.append("=" * 60)
            report_lines.append("OpenEmail 账户状态报告")
            report_lines.append(
                f"生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
            )
            report_lines.append("=" * 60)
            report_lines.append("")

            # 统计信息
            total = len(accounts)
            active = sum(1 for acc in accounts if acc.is_active)
            disabled = total - active

            report_lines.append(f"账户总数: {total}")
            report_lines.append(f"活跃账户: {active}")
            report_lines.append(f"禁用账户: {disabled}")
            report_lines.append("")

            # 问题列表
            if issues:
                report_lines.append("发现的问题:")
                for i, issue in enumerate(issues, 1):
                    report_lines.append(f"  {i}. {issue}")
                report_lines.append(f"总计问题: {len(issues)}")
            else:
                report_lines.append("✅ 未发现问题")
            report_lines.append("")

            # 详细账户列表
            report_lines.append("账户详情:")
            report_lines.append("-" * 80)

            for account in accounts:
                risk_info = check_email_risk(account.email)
                report_lines.append(f"邮箱: {account.email}")
                report_lines.append(f"  显示名: {account.name or '无'}")
                report_lines.append(f"  状态: {account.connection_status.value}")
                report_lines.append(f"  活跃: {'是' if account.is_active else '否'}")
                report_lines.append(
                    f"  风险: {risk_info['risk_level']} ({risk_info['reason']})"
                )
                report_lines.append(f"  最后同步: {account.last_synced_at or '从未'}")
                report_lines.append("")

            report_lines.append("=" * 60)

            # 显示在文本框中
            report_text = "\n".join(report_lines)

            # 创建显示对话框
            report_dialog = QDialog(self)
            report_dialog.setWindowTitle("账户状态报告")
            report_dialog.resize(600, 500)

            layout = QVBoxLayout(report_dialog)

            text_edit = QTextEdit()
            text_edit.setPlainText(report_text)
            text_edit.setReadOnly(True)
            layout.addWidget(text_edit)

            btn_layout = QHBoxLayout()
            close_btn = QPushButton("关闭")
            close_btn.clicked.connect(report_dialog.accept)
            btn_layout.addStretch()
            btn_layout.addWidget(close_btn)
            layout.addLayout(btn_layout)

            self._status_text.append("📋 已生成账户状态报告")
            report_dialog.exec()

        except Exception as e:
            logger.error(f"导出报告失败: {e}")
            self._show_error("导出报告失败", str(e))

    def _show_progress(self, message: str):
        """显示进度条"""
        self._progress_bar.setVisible(True)
        self._progress_bar.setRange(0, 0)  # 不确定进度
        self._status_text.append(f"⏳ {message}")

    def _hide_progress(self):
        """隐藏进度条"""
        self._progress_bar.setVisible(False)
        self._progress_bar.setRange(0, 100)

    def _show_error(self, title: str, message: str):
        """显示错误消息"""
        self._status_text.append(f"❌ {title}: {message}")
        QMessageBox.critical(self, title, message)


def show_account_cleanup_dialog(parent=None):
    """显示账户清理对话框"""
    dialog = AccountCleanupDialog(parent)
    dialog.exec()
