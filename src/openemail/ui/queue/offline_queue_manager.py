from __future__ import annotations

import json
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
import logging
from enum import Enum

from PyQt6.QtCore import Qt, pyqtSignal, QTimer, QSortFilterProxyModel, QModelIndex
from PyQt6.QtGui import (
    QFont,
    QColor,
    QBrush,
    QIcon,
    QTextCharFormat,
    QSyntaxHighlighter,
    QAction,
)
from PyQt6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QHeaderView,
    QComboBox,
    QSpinBox,
    QDateEdit,
    QGroupBox,
    QFormLayout,
    QSplitter,
    QTextEdit,
    QDialog,
    QDialogButtonBox,
    QMessageBox,
    QTabWidget,
    QTreeWidget,
    QTreeWidgetItem,
    QMenu,
    QApplication,
    QProgressBar,
    QCheckBox,
    QFrame,
    QStackedWidget,
)

from openemail.queue.offline_queue import (
    get_offline_queue,
    OfflineOperation,
    OfflineQueueStats,
    OperationType,
    OperationStatus,
    PriorityLevel,
)


class OperationStatusIndicator(QWidget):
    """操作状态指示器"""

    STATUS_COLORS = {
        OperationStatus.PENDING.value: QColor("#ff9800"),  # 橙色
        OperationStatus.QUEUED.value: QColor("#2196f3"),  # 蓝色
        OperationStatus.PROCESSING.value: QColor("#9c27b0"),  # 紫色
        OperationStatus.SUCCESS.value: QColor("#4caf50"),  # 绿色
        OperationStatus.FAILED.value: QColor("#f44336"),  # 红色
        OperationStatus.RETRY_ING.value: QColor("#ff9800"),  # 橙色
        OperationStatus.CANCELLED.value: QColor("#9e9e9e"),  # 灰色
    }

    STATUS_LABELS = {
        OperationStatus.PENDING.value: "待处理",
        OperationStatus.QUEUED.value: "已排队",
        OperationStatus.PROCESSING.value: "处理中",
        OperationStatus.SUCCESS.value: "成功",
        OperationStatus.FAILED.value: "失败",
        OperationStatus.RETRY_ING.value: "重试中",
        OperationStatus.CANCELLED.value: "已取消",
    }

    def __init__(self, status: str, parent=None):
        super().__init__(parent)

        self.status = status
        self._setup_ui()

    def _setup_ui(self):
        """设置UI"""
        layout = QHBoxLayout()
        layout.setContentsMargins(4, 2, 4, 2)
        layout.setSpacing(6)

        # 状态颜色点
        color_frame = QFrame()
        color_frame.setFixedSize(12, 12)
        color_frame.setStyleSheet(f"""
            background-color: {self.STATUS_COLORS.get(self.status, "#9e9e9e").name()};
            border-radius: 6px;
        """)

        # 状态文本
        status_text = self.STATUS_LABELS.get(self.status, self.status)
        status_label = QLabel(status_text)

        layout.addWidget(color_frame)
        layout.addWidget(status_label)
        layout.addStretch()

        self.setLayout(layout)


class PriorityIndicator(QWidget):
    """优先级指示器"""

    PRIORITY_COLORS = {
        PriorityLevel.LOW.value: QColor("#4caf50"),  # 绿色
        PriorityLevel.NORMAL.value: QColor("#2196f3"),  # 蓝色
        PriorityLevel.HIGH.value: QColor("#ff9800"),  # 橙色
        PriorityLevel.CRITICAL.value: QColor("#f44336"),  # 红色
    }

    PRIORITY_LABELS = {
        PriorityLevel.LOW.value: "低",
        PriorityLevel.NORMAL.value: "中",
        PriorityLevel.HIGH.value: "高",
        PriorityLevel.CRITICAL.value: "紧急",
    }

    def __init__(self, priority: int, parent=None):
        super().__init__(parent)

        self.priority = priority
        self._setup_ui()

    def _setup_ui(self):
        """设置UI"""
        layout = QHBoxLayout()
        layout.setContentsMargins(4, 2, 4, 2)
        layout.setSpacing(4)

        # 优先级标签
        priority_label = self.PRIORITY_LABELS.get(self.priority, str(self.priority))
        label = QLabel(priority_label)

        # 颜色条
        color_bar = QFrame()
        color_bar.setFixedHeight(8)
        color_bar.setStyleSheet(f"""
            background-color: {self.PRIORITY_COLORS.get(self.priority, "#9e9e9e").name()};
            border-radius: 2px;
        """)

        layout.addWidget(label)
        layout.addWidget(color_bar)
        layout.addStretch()

        self.setLayout(layout)


class OperationDetailDialog(QDialog):
    """操作详情对话框"""

    def __init__(self, operation: OfflineOperation, parent=None):
        super().__init__(parent)

        self.operation = operation
        self.setWindowTitle(f"操作详情 - {operation.id}")
        self.setMinimumSize(500, 400)

        self._setup_ui()

    def _setup_ui(self):
        """设置UI"""
        layout = QVBoxLayout()

        # 基本信息标签页
        details_tab = QTabWidget()

        # 基本信息
        basic_info = QWidget()
        basic_layout = QFormLayout()

        basic_layout.addRow("操作ID:", QLabel(str(self.operation.id)))

        operation_type = self.operation.operation_type
        type_label = QLabel(operation_type)
        basic_layout.addRow("操作类型:", type_label)

        status_widget = OperationStatusIndicator(self.operation.status)
        basic_layout.addRow("状态:", status_widget)

        priority_widget = PriorityIndicator(self.operation.priority)
        basic_layout.addRow("优先级:", priority_widget)

        if self.operation.account_id:
            basic_layout.addRow("账户ID:", QLabel(str(self.operation.account_id)))

        retry_info = f"{self.operation.retry_count}/{self.operation.max_retries}"
        basic_layout.addRow("重试次数:", QLabel(retry_info))

        if self.operation.created_at:
            created_str = self.operation.created_at.strftime("%Y-%m-%d %H:%M:%S")
            basic_layout.addRow("创建时间:", QLabel(created_str))

        if self.operation.last_attempt:
            last_attempt_str = self.operation.last_attempt.strftime("%Y-%m-%d %H:%M:%S")
            basic_layout.addRow("最后尝试:", QLabel(last_attempt_str))

        basic_info.setLayout(basic_layout)
        details_tab.addTab(basic_info, "基本信息")

        # 操作数据
        data_widget = QWidget()
        data_layout = QVBoxLayout()

        if self.operation.data:
            try:
                # 将数据格式化为JSON字符串
                data_json = json.dumps(
                    self.operation.data, indent=2, ensure_ascii=False
                )
                data_text = QTextEdit()
                data_text.setReadOnly(True)
                data_text.setPlainText(data_json)
                data_text.setStyleSheet("font-family: monospace;")
                data_layout.addWidget(data_text)
            except Exception:
                data_label = QLabel("无法解析操作数据")
                data_layout.addWidget(data_label)
        else:
            data_label = QLabel("无操作数据")
            data_layout.addWidget(data_label)

        data_widget.setLayout(data_layout)
        details_tab.addTab(data_widget, "操作数据")

        # 错误信息
        if self.operation.error_message:
            error_widget = QWidget()
            error_layout = QVBoxLayout()

            error_text = QTextEdit()
            error_text.setReadOnly(True)
            error_text.setPlainText(self.operation.error_message)
            error_text.setStyleSheet("color: #d32f2f; font-family: monospace;")

            error_layout.addWidget(error_text)
            error_widget.setLayout(error_layout)
            details_tab.addTab(error_widget, "错误信息")

        layout.addWidget(details_tab, 1)

        # 按钮
        button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok)
        button_box.accepted.connect(self.accept)
        layout.addWidget(button_box)

        self.setLayout(layout)


class OfflineQueueManager(QWidget):
    """离线队列管理器"""

    def __init__(self, parent=None):
        super().__init__(parent)

        self.queue = get_offline_queue()
        self.stats_timer = QTimer(self)
        self.refresh_timer = QTimer(self)

        self._setup_ui()
        self._connect_signals()
        self._refresh_data()

    def _setup_ui(self):
        """设置UI"""
        layout = QVBoxLayout()

        # 控制面板
        control_panel = QFrame()
        control_layout = QHBoxLayout()

        # 启动/停止按钮
        self.start_button = QPushButton("启动工作线程")
        self.start_button.clicked.connect(self._toggle_workers)
        self.start_button.setEnabled(True)
        self.stop_button = QPushButton("停止工作线程")
        self.stop_button.clicked.connect(self.queue.stop_workers)
        self.stop_button.setEnabled(True)

        # 刷新按钮
        refresh_button = QPushButton("刷新")
        refresh_button.clicked.connect(self._refresh_data)

        # 清理按钮
        clear_button = QPushButton("清理已完成")

        def cleanup_completed():
            result = QMessageBox.question(
                self,
                "确认",
                "确定要清理已完成（成功、失败、已取消）的操作吗？\n（默认保留7天内数据）",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            )
            if result == QMessageBox.StandardButton.Yes:
                count = self.queue.clear_completed_operations()
                QMessageBox.information(self, "完成", f"清理了 {count} 个操作")
                self._refresh_data()

        clear_button.clicked.connect(cleanup_completed)

        control_layout.addWidget(self.start_button)
        control_layout.addWidget(self.stop_button)
        control_layout.addWidget(refresh_button)
        control_layout.addWidget(clear_button)
        control_layout.addStretch()

        # 统计信息标签
        self.stats_label = QLabel("离线队列统计：加载中...")
        self.stats_label.setStyleSheet("font-weight: bold;")
        control_layout.addWidget(self.stats_label)

        control_panel.setLayout(control_layout)
        layout.addWidget(control_panel)

        # 主内容区域
        content_splitter = QSplitter(Qt.Orientation.Horizontal)

        # 左侧：操作列表
        operations_panel = QWidget()
        operations_layout = QVBoxLayout()

        # 操作列表表格
        self.operations_table = QTableWidget()
        self.operations_table.setColumnCount(6)
        self.operations_table.setHorizontalHeaderLabels(
            ["ID", "操作类型", "状态", "优先级", "重试", "创建时间"]
        )
        self.operations_table.horizontalHeader().setStretchLastSection(True)
        self.operations_table.setSelectionBehavior(
            QTableWidget.SelectionBehavior.SelectRows
        )
        self.operations_table.setSelectionMode(
            QTableWidget.SelectionMode.SingleSelection
        )

        # 右键菜单
        self.operations_table.setContextMenuPolicy(
            Qt.ContextMenuPolicy.CustomContextMenu
        )
        self.operations_table.customContextMenuRequested.connect(
            self._show_operation_menu
        )

        operations_layout.addWidget(self.operations_table, 1)

        # 底部操作按钮
        operations_buttons = QHBoxLayout()

        details_button = QPushButton("查看详情")
        details_button.clicked.connect(self._show_operation_details)
        operations_buttons.addWidget(details_button)

        retry_button = QPushButton("重试")
        retry_button.clicked.connect(self._retry_operation)
        operations_buttons.addWidget(retry_button)

        cancel_button = QPushButton("取消")
        cancel_button.clicked.connect(self._cancel_operation)
        operations_buttons.addWidget(cancel_button)

        delete_button = QPushButton("删除")
        delete_button.clicked.connect(self._delete_operation)
        delete_button.setStyleSheet("background-color: #f44336; color: white;")
        operations_buttons.addWidget(delete_button)

        operations_buttons.addStretch()

        # 过滤选项
        filter_group = QGroupBox("过滤选项")
        filter_layout = QHBoxLayout()

        self.status_filter = QComboBox()
        self.status_filter.addItem("所有状态", "")
        for status in OperationStatus:
            self.status_filter.addItem(
                OperationStatusIndicator.STATUS_LABELS.get(status.value, status.value),
                status.value,
            )
        self.status_filter.currentIndexChanged.connect(self._refresh_data)
        filter_layout.addWidget(QLabel("状态:"))
        filter_layout.addWidget(self.status_filter)

        self.type_filter = QComboBox()
        self.type_filter.addItem("所有类型", "")
        for op_type in OperationType:
            self.type_filter.addItem(op_type.value, op_type.value)
        self.type_filter.currentIndexChanged.connect(self._refresh_data)
        filter_layout.addWidget(QLabel("类型:"))
        filter_layout.addWidget(self.type_filter)

        self.priority_filter = QComboBox()
        self.priority_filter.addItem("所有优先级", -1)
        for priority in PriorityLevel:
            self.priority_filter.addItem(
                PriorityIndicator.PRIORITY_LABELS.get(
                    priority.value, str(priority.value)
                ),
                priority.value,
            )
        self.priority_filter.currentIndexChanged.connect(self._refresh_data)
        filter_layout.addWidget(QLabel("优先级:"))
        filter_layout.addWidget(self.priority_filter)

        filter_layout.addStretch()
        filter_group.setLayout(filter_layout)

        operations_layout.addLayout(operations_buttons)
        operations_layout.addWidget(filter_group)

        operations_panel.setLayout(operations_layout)

        # 右侧：统计信息
        stats_panel = QWidget()
        stats_layout = QVBoxLayout()

        stats_group = QGroupBox("详细统计")
        stats_container = QVBoxLayout()

        # 基本统计
        basic_stats = QFrame()
        basic_stats_layout = QFormLayout()

        self.total_ops_label = QLabel("0")
        basic_stats_layout.addRow("总操作数:", self.total_ops_label)

        self.pending_ops_label = QLabel("0")
        basic_stats_layout.addRow("待处理:", self.pending_ops_label)

        self.queued_ops_label = QLabel("0")
        basic_stats_layout.addRow("已排队:", self.queued_ops_label)

        self.processing_ops_label = QLabel("0")
        basic_stats_layout.addRow("处理中:", self.processing_ops_label)

        self.success_ops_label = QLabel("0")
        basic_stats_layout.addRow("成功:", self.success_ops_label)

        self.failed_ops_label = QLabel("0")
        basic_stats_layout.addRow("失败:", self.failed_ops_label)

        self.retrying_ops_label = QLabel("0")
        basic_stats_layout.addRow("重试中:", self.retrying_ops_label)

        self.cancelled_ops_label = QLabel("0")
        basic_stats_layout.addRow("已取消:", self.cancelled_ops_label)

        basic_stats.setLayout(basic_stats_layout)
        stats_container.addWidget(basic_stats)

        # 性能统计
        perf_stats = QGroupBox("性能统计")
        perf_layout = QFormLayout()

        self.success_rate_label = QLabel("0%")
        perf_layout.addRow("成功率:", self.success_rate_label)

        self.avg_queue_time_label = QLabel("0秒")
        perf_layout.addRow("平均排队时间:", self.avg_queue_time_label)

        self.ops_per_minute_label = QLabel("0")
        perf_layout.addRow("每分钟操作数:", self.ops_per_minute_label)

        self.total_retries_label = QLabel("0")
        perf_layout.addRow("总重试数:", self.total_retries_label)

        perf_stats.setLayout(perf_layout)
        stats_container.addWidget(perf_stats)

        # 按类型统计
        type_stats_group = QGroupBox("按类型统计")
        type_stats_layout = QVBoxLayout()

        self.type_stats_table = QTableWidget()
        self.type_stats_table.setColumnCount(3)
        self.type_stats_table.setHorizontalHeaderLabels(["类型", "数量", "成功率"])
        self.type_stats_table.horizontalHeader().setStretchLastSection(True)
        self.type_stats_table.setAlternatingRowColors(True)

        type_stats_layout.addWidget(self.type_stats_table)
        type_stats_group.setLayout(type_stats_layout)
        stats_container.addWidget(type_stats_group)

        stats_container.addStretch()
        stats_group.setLayout(stats_container)
        stats_layout.addWidget(stats_group)

        stats_panel.setLayout(stats_layout)

        # 添加到分割器
        content_splitter.addWidget(operations_panel)
        content_splitter.addWidget(stats_panel)
        content_splitter.setSizes([600, 400])

        layout.addWidget(content_splitter, 1)

        self.setLayout(layout)

    def _connect_signals(self):
        """连接信号"""
        # 设置定时器
        self.stats_timer.timeout.connect(self._update_stats)
        self.stats_timer.start(5000)  # 每5秒更新一次统计

        self.refresh_timer.timeout.connect(self._refresh_data)
        self.refresh_timer.start(10000)  # 每10秒刷新一次数据

    def _toggle_workers(self):
        """切换工作线程状态"""
        try:
            self.queue.start_workers(3)  # 启动3个工作线程
            QMessageBox.information(self, "成功", "工作线程已启动")
        except Exception as e:
            QMessageBox.critical(self, "错误", f"启动工作线程失败: {e}")

    def _refresh_data(self):
        """刷新数据"""
        self._load_operations()
        self._update_stats()

    def _load_operations(self):
        """加载操作列表"""
        try:
            # 获取过滤条件
            status_filter = self.status_filter.currentData()
            type_filter = self.type_filter.currentData()
            priority_filter = self.priority_filter.currentData()

            # 构建查询条件
            conditions = []
            params = []

            if status_filter:
                conditions.append("status = ?")
                params.append(status_filter)

            if type_filter:
                conditions.append("operation_type = ?")
                params.append(type_filter)

            if priority_filter != -1:
                conditions.append("priority = ?")
                params.append(priority_filter)

            # 构建SQL
            where_clause = " AND ".join(conditions) if conditions else "1=1"
            sql = f"""
                SELECT * FROM offline_operations
                WHERE {where_clause}
                ORDER BY created_at DESC, id DESC
                LIMIT 100
            """

            rows = self.queue.db.fetchall(sql, params)
            operations = [OfflineOperation.from_dict(r) for r in rows]

            # 更新表格
            self.operations_table.setRowCount(len(operations))

            for i, operation in enumerate(operations):
                # ID
                id_item = QTableWidgetItem(str(operation.id))
                id_item.setData(Qt.ItemDataRole.UserRole, operation.id)
                self.operations_table.setItem(i, 0, id_item)

                # 操作类型
                type_item = QTableWidgetItem(operation.operation_type)
                self.operations_table.setItem(i, 1, type_item)

                # 状态
                status_widget = OperationStatusIndicator(operation.status)
                self.operations_table.setCellWidget(i, 2, status_widget)

                # 优先级
                priority_widget = PriorityIndicator(operation.priority)
                self.operations_table.setCellWidget(i, 3, priority_widget)

                # 重试次数
                retry_text = f"{operation.retry_count}/{operation.max_retries}"
                retry_item = QTableWidgetItem(retry_text)
                retry_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                self.operations_table.setItem(i, 4, retry_item)

                # 创建时间
                if operation.created_at:
                    created_text = operation.created_at.strftime("%m-%d %H:%M")
                    created_item = QTableWidgetItem(created_text)
                    self.operations_table.setItem(i, 5, created_item)

            # 调整列宽
            self.operations_table.resizeColumnsToContents()

        except Exception as e:
            logging.error(f"加载操作列表时出错: {e}")
            QMessageBox.warning(self, "错误", f"加载数据失败: {e}")

    def _update_stats(self):
        """更新统计信息"""
        try:
            stats = self.queue.get_queue_stats()

            # 更新基本统计标签
            self.stats_label.setText(
                f"离线队列：总计 {stats.total_operations} | "
                f"成功 {stats.successful_operations} | "
                f"失败 {stats.failed_operations} | "
                f"成功率 {stats.success_rate:.1f}%"
            )

            # 更新详细统计
            self.total_ops_label.setText(str(stats.total_operations))
            self.pending_ops_label.setText(str(stats.pending_operations))
            self.queued_ops_label.setText(str(stats.queued_operations))
            self.processing_ops_label.setText(str(stats.processing_operations))
            self.success_ops_label.setText(str(stats.successful_operations))
            self.failed_ops_label.setText(str(stats.failed_operations))
            self.retrying_ops_label.setText(str(stats.retrying_operations))
            self.cancelled_ops_label.setText(str(stats.cancelled_operations))

            # 更新性能统计
            self.success_rate_label.setText(f"{stats.success_rate:.1f}%")
            self.avg_queue_time_label.setText(f"{stats.avg_queue_time_seconds:.1f}秒")
            self.ops_per_minute_label.setText(f"{stats.operations_per_minute:.1f}")
            self.total_retries_label.setText(str(stats.total_retries))

            # 更新按类型统计
            self.type_stats_table.setRowCount(len(stats.operations_by_type))

            for i, (op_type, count) in enumerate(stats.operations_by_type.items()):
                # 类型
                type_item = QTableWidgetItem(op_type)
                self.type_stats_table.setItem(i, 0, type_item)

                # 数量
                count_item = QTableWidgetItem(str(count))
                count_item.setTextAlignment(
                    Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
                )
                self.type_stats_table.setItem(i, 1, count_item)

                # 成功率
                success_rate = stats.success_rate_by_type.get(op_type, 0)
                rate_item = QTableWidgetItem(f"{success_rate:.1f}%")
                rate_item.setTextAlignment(
                    Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
                )

                # 根据成功率设置颜色
                if success_rate >= 90:
                    rate_item.setForeground(QBrush(QColor("#4caf50")))  # 绿色
                elif success_rate >= 70:
                    rate_item.setForeground(QBrush(QColor("#ff9800")))  # 橙色
                else:
                    rate_item.setForeground(QBrush(QColor("#f44336")))  # 红色

                self.type_stats_table.setItem(i, 2, rate_item)

            self.type_stats_table.resizeColumnsToContents()

        except Exception as e:
            logging.error(f"更新统计信息时出错: {e}")

    def _get_selected_operation_id(self) -> Optional[int]:
        """获取选中的操作ID"""
        selected_items = self.operations_table.selectedItems()
        if not selected_items:
            return None

        row = selected_items[0].row()
        item = self.operations_table.item(row, 0)
        return item.data(Qt.ItemDataRole.UserRole)

    def _get_selected_operation(self) -> Optional[OfflineOperation]:
        """获取选中的操作"""
        operation_id = self._get_selected_operation_id()
        if not operation_id:
            return None

        return OfflineOperation.get_by_id(operation_id)

    def _show_operation_details(self):
        """显示操作详情"""
        operation = self._get_selected_operation()
        if not operation:
            QMessageBox.warning(self, "提示", "请先选择一个操作")
            return

        dialog = OperationDetailDialog(operation, self)
        dialog.exec()

    def _retry_operation(self):
        """重试操作"""
        operation_id = self._get_selected_operation_id()
        if not operation_id:
            QMessageBox.warning(self, "提示", "请先选择一个操作")
            return

        success = self.queue.retry_failed_operation(operation_id)
        if success:
            QMessageBox.information(self, "成功", "操作已重新排队重试")
            self._refresh_data()
        else:
            QMessageBox.warning(self, "错误", "重试操作失败")

    def _cancel_operation(self):
        """取消操作"""
        operation = self._get_selected_operation()
        if not operation:
            QMessageBox.warning(self, "提示", "请先选择一个操作")
            return

        # 只有特定状态可以取消
        cancelable_states = [
            OperationStatus.PENDING.value,
            OperationStatus.QUEUED.value,
            OperationStatus.RETRY_ING.value,
        ]

        if operation.status not in cancelable_states:
            QMessageBox.warning(
                self, "错误", f"此操作的状态 '{operation.status}' 无法取消"
            )
            return

        reply = QMessageBox.question(
            self,
            "确认取消",
            f"确定要取消操作 '{operation.operation_type}' (ID: {operation.id}) 吗？",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )

        if reply == QMessageBox.StandardButton.Yes:
            success = self.queue.cancel_operation(operation.id)
            if success:
                QMessageBox.information(self, "成功", "操作已取消")
                self._refresh_data()
            else:
                QMessageBox.warning(self, "错误", "取消操作失败")

    def _delete_operation(self):
        """删除操作"""
        operation_id = self._get_selected_operation_id()
        if not operation_id:
            QMessageBox.warning(self, "提示", "请先选择一个操作")
            return

        reply = QMessageBox.question(
            self,
            "确认删除",
            f"确定要删除操作 (ID: {operation_id}) 吗？此操作不可恢复！",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )

        if reply == QMessageBox.StandardButton.Yes:
            try:
                from openemail.storage.database import db

                db.delete("offline_operations", "id = ?", (operation_id,))
                QMessageBox.information(self, "成功", "操作已删除")
                self._refresh_data()
            except Exception as e:
                QMessageBox.critical(self, "错误", f"删除操作失败: {e}")

    def _show_operation_menu(self, position):
        """显示操作右键菜单"""
        operation = self._get_selected_operation()
        if not operation:
            return

        menu = QMenu()

        details_action = menu.addAction("查看详情")
        details_action.triggered.connect(self._show_operation_details)

        # 根据状态显示不同选项
        if operation.status in [
            OperationStatus.FAILED.value,
            OperationStatus.RETRY_ING.value,
        ]:
            retry_action = menu.addAction("重试")
            retry_action.triggered.connect(self._retry_operation)

        if operation.status in [
            OperationStatus.PENDING.value,
            OperationStatus.QUEUED.value,
            OperationStatus.RETRY_ING.value,
        ]:
            cancel_action = menu.addAction("取消")
            cancel_action.triggered.connect(self._cancel_operation)

        menu.addSeparator()

        delete_action = menu.addAction("删除")
        delete_action.triggered.connect(self._delete_operation)

        menu.exec(self.operations_table.mapToGlobal(position))

    def closeEvent(self, event):
        """关闭事件"""
        self.stats_timer.stop()
        self.refresh_timer.stop()
        super().closeEvent(event)


# 简化版本的队列管理器（用于在主界面显示简单状态）
class SimpleQueueStatusWidget(QWidget):
    """简化版队列状态小工具"""

    def __init__(self, parent=None):
        super().__init__(parent)

        self.queue = get_offline_queue()
        self.timer = QTimer(self)
        self.timer.timeout.connect(self._update_status)

        self._setup_ui()
        self.timer.start(30000)  # 每30秒更新一次
        self._update_status()

    def _setup_ui(self):
        """设置UI"""
        layout = QHBoxLayout()
        layout.setContentsMargins(6, 2, 6, 2)
        layout.setSpacing(8)

        # 队列图标
        self.queue_icon = QLabel("⏱")
        self.queue_icon.setStyleSheet("font-size: 14px;")

        # 状态标签
        self.status_label = QLabel("离线队列")
        self.status_label.setStyleSheet("color: #666; font-size: 11px;")

        # 计数标签
        self.count_label = QLabel("0")
        self.count_label.setStyleSheet("""
            font-weight: bold; 
            font-size: 11px; 
            background-color: #f0f0f0; 
            border-radius: 8px;
            padding: 1px 6px;
            min-width: 20px;
            text-align: center;
        """)

        layout.addWidget(self.queue_icon)
        layout.addWidget(self.status_label)
        layout.addWidget(self.count_label)
        layout.addStretch()

        self.setLayout(layout)

        # 点击事件
        self.setCursor(Qt.CursorShape.PointingHandCursor)

        def show_manager():
            dialog = OfflineQueueManager()
            dialog.setWindowTitle("离线队列管理器")
            dialog.resize(1000, 700)
            dialog.exec()

        self.mousePressEvent = lambda e: (
            show_manager() if e.button() == Qt.MouseButton.LeftButton else None
        )

    def _update_status(self):
        """更新状态"""
        try:
            stats = self.queue.get_queue_stats()
            pending = (
                stats.pending_operations
                + stats.queued_operations
                + stats.retrying_operations
            )

            if pending == 0:
                self.status_label.setText("离线队列")
                self.count_label.setText("0")
                self.count_label.setStyleSheet("""
                    font-weight: bold; 
                    font-size: 11px; 
                    background-color: #e0e0e0; 
                    border-radius: 8px;
                    padding: 1px 6px;
                    min-width: 20px;
                    text-align: center;
                    color: #666;
                """)
            elif pending <= 10:
                self.status_label.setText("离线队列")
                self.count_label.setText(str(pending))
                self.count_label.setStyleSheet("""
                    font-weight: bold; 
                    font-size: 11px; 
                    background-color: #4caf50; 
                    border-radius: 8px;
                    padding: 1px 6px;
                    min-width: 20px;
                    text-align: center;
                    color: white;
                """)
            else:
                self.status_label.setText("离线队列")
                self.count_label.setText(str(pending))
                self.count_label.setStyleSheet("""
                    font-weight: bold; 
                    font-size: 11px; 
                    background-color: #ff9800; 
                    border-radius: 8px;
                    padding: 1px 6px;
                    min-width: 20px;
                    text-align: center;
                    color: white;
                """)

        except Exception as e:
            logging.error(f"更新队列状态时出错: {e}")
            self.status_label.setText("队列错误")
            self.count_label.setText("!")
