from __future__ import annotations

from typing import Dict, Optional
import re

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QPushButton,
    QLabel,
    QLineEdit,
    QComboBox,
    QSpinBox,
    QCheckBox,
    QGroupBox,
    QFormLayout,
    QTextEdit,
    QSplitter,
    QDialog,
    QDialogButtonBox,
    QMessageBox,
    QTableWidget,
    QTableWidgetItem,
    QDateEdit,
    QMenu,
)

from openemail.filter.enhanced_filter_engine import (
    EnhancedFilterRule,
    EnhancedFilterEngine,
)
from openemail.models.folder import Folder

from openemail.models.label import Label


class ConditionWidget(QWidget):
    """单个条件编辑器部件"""

    condition_changed = pyqtSignal()

    def __init__(self, condition: Optional[Dict] = None, parent=None):
        super().__init__(parent)

        self.condition = condition or {}
        self._setup_ui()
        self._load_condition()

    def _setup_ui(self):
        """设置UI"""
        layout = QHBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)

        # 字段选择
        self.field_combo = QComboBox()
        self.field_combo.addItems(
            ["subject", "sender", "sender_name", "to", "body", "preview"]
        )
        self.field_combo.currentTextChanged.connect(self._on_field_changed)

        # 条件类型
        self.type_combo = QComboBox()
        self.type_combo.addItems(
            ["keyword", "regex", "sender", "date", "size", "flag", "attachment"]
        )
        self.type_combo.currentTextChanged.connect(self._on_type_changed)

        # 操作符
        self.operator_combo = QComboBox()
        self._update_operators()
        self.operator_combo.currentTextChanged.connect(self.condition_changed.emit)

        # 值输入
        self.value_input = QLineEdit()
        self.value_input.textChanged.connect(self.condition_changed.emit)

        # 日期控件（用于日期条件）
        self.date_input = QDateEdit()
        self.date_input.setDisplayFormat("yyyy-MM-dd")
        self.date_input.setCalendarPopup(True)
        self.date_input.dateChanged.connect(self._on_date_changed)
        self.date_input.hide()

        # 大小控件（用于大小条件）
        self.size_spin = QSpinBox()
        self.size_spin.setRange(1, 10000)
        self.size_spin.setSuffix(" KB")
        self.size_spin.valueChanged.connect(self._on_size_changed)
        self.size_spin.hide()

        # 标记控件（用于标记条件）
        self.flag_combo = QComboBox()
        self.flag_combo.addItems(["true", "false"])
        self.flag_combo.currentTextChanged.connect(self._on_flag_changed)
        self.flag_combo.hide()

        # 删除按钮
        self.delete_button = QPushButton("×")
        self.delete_button.setFixedSize(24, 24)
        self.delete_button.setStyleSheet("""
            QPushButton {
                background-color: #C97850;
                color: white;
                border: none;
                border-radius: 4px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #B56A42;
            }
        """)

        # 添加到布局
        layout.addWidget(self.field_combo)
        layout.addWidget(self.type_combo)
        layout.addWidget(self.operator_combo)
        layout.addWidget(self.value_input, 1)
        layout.addWidget(self.date_input)
        layout.addWidget(self.size_spin)
        layout.addWidget(self.flag_combo)
        layout.addWidget(self.delete_button)

        self.setLayout(layout)

    def _update_operators(self):
        """根据类型和字段更新操作符"""
        self.operator_combo.clear()

        condition_type = self.type_combo.currentText()
        _field = self.field_combo.currentText()

        operators = []

        if condition_type == "keyword":
            operators = [
                "contains",
                "not_contains",
                "equals",
                "starts_with",
                "ends_with",
            ]

        elif condition_type == "regex":
            operators = ["matches", "not_matches"]

        elif condition_type == "sender":
            operators = ["equals", "contains", "domain", "in_contacts"]

        elif condition_type == "date":
            operators = ["older_than", "newer_than", "on_date", "before", "after"]

        elif condition_type == "size":
            operators = ["greater_than", "less_than", "between"]

        elif condition_type == "flag":
            operators = ["equals"]

        elif condition_type == "attachment":
            operators = ["has", "has_not"]

        self.operator_combo.addItems(operators)

    def _update_value_widget(self):
        """根据类型更新值输入控件"""
        condition_type = self.type_combo.currentText()
        operator = self.operator_combo.currentText()

        # 隐藏所有特殊控件
        self.value_input.show()
        self.date_input.hide()
        self.size_spin.hide()
        self.flag_combo.hide()

        # 显示适当的控件
        if condition_type == "date":
            if operator in ["older_than", "newer_than"]:
                self.value_input.show()
            else:
                self.date_input.show()
                self.value_input.hide()

        elif condition_type == "size":
            if operator == "between":
                self.value_input.show()
                self.value_input.setPlaceholderText("最小值,最大值 (KB)")
            else:
                self.size_spin.show()
                self.value_input.hide()

        elif condition_type == "flag":
            self.flag_combo.show()
            self.value_input.hide()

    def _on_field_changed(self):
        """字段变化事件"""
        self._update_operators()
        self.condition_changed.emit()

    def _on_type_changed(self):
        """类型变化事件"""
        self._update_operators()
        self._update_value_widget()
        self.condition_changed.emit()

    def _on_date_changed(self, date):
        """日期变化事件"""
        value = date.toString("yyyy-MM-dd")
        self.value_input.setText(value)

    def _on_size_changed(self, value):
        """大小变化事件"""
        self.value_input.setText(str(value))

    def _on_flag_changed(self, value):
        """标记变化事件"""
        self.value_input.setText(value)

    def _load_condition(self):
        """加载条件"""
        if not self.condition:
            return

        # 设置字段
        field = self.condition.get("field", "subject")
        if self.field_combo.findText(field) >= 0:
            self.field_combo.setCurrentText(field)

        # 设置类型
        condition_type = self.condition.get("type", "keyword")
        if self.type_combo.findText(condition_type) >= 0:
            self.type_combo.setCurrentText(condition_type)

        # 设置操作符
        operator = self.condition.get("operator", "contains")
        if self.operator_combo.findText(operator) >= 0:
            self.operator_combo.setCurrentText(operator)

        # 设置值
        value = self.condition.get("value", "")
        self.value_input.setText(str(value))

        # 更新控件状态
        self._update_value_widget()

    def get_condition(self) -> Dict:
        """获取条件"""
        return {
            "type": self.type_combo.currentText(),
            "field": self.field_combo.currentText(),
            "operator": self.operator_combo.currentText(),
            "value": self.value_input.text().strip(),
        }

    def is_valid(self) -> bool:
        """检查条件是否有效"""
        value = self.value_input.text().strip()

        if self.type_combo.currentText() == "regex":
            try:
                re.compile(value)
                return True
            except re.error:
                return False

        condition_type = self.type_combo.currentText()
        operator = self.operator_combo.currentText()

        if condition_type == "date":
            if operator in ["older_than", "newer_than"]:
                try:
                    int(value)
                    return True
                except ValueError:
                    return False

        if condition_type == "size":
            if operator == "between":
                parts = value.split(",")
                if len(parts) != 2:
                    return False
                try:
                    int(parts[0].strip())
                    int(parts[1].strip())
                    return True
                except ValueError:
                    return False

        return bool(value)


class ActionWidget(QWidget):
    """单个动作编辑器部件"""

    action_changed = pyqtSignal()

    def __init__(self, action: Optional[Dict] = None, parent=None):
        super().__init__(parent)

        self.action = action or {}
        self._setup_ui()
        self._load_action()

    def _setup_ui(self):
        """设置UI"""
        layout = QHBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)

        # 动作类型
        self.type_combo = QComboBox()
        self.type_combo.addItems(
            [
                "move_to_folder",
                "apply_label",
                "mark_read",
                "mark_important",
                "set_flag",
                "delete",
                "mark_spam",
            ]
        )
        self.type_combo.currentTextChanged.connect(self._on_type_changed)

        # 目标输入
        self.target_input = QLineEdit()
        self.target_input.textChanged.connect(self.action_changed.emit)

        # 文件夹选择（用于move_to_folder）
        self.folder_combo = QComboBox()
        self.folder_combo.currentTextChanged.connect(self._on_folder_changed)
        self.folder_combo.hide()

        # 标签选择（用于apply_label）
        self.label_combo = QComboBox()
        self.label_combo.setEditable(True)
        self.label_combo.currentTextChanged.connect(self._on_label_changed)
        self.label_combo.hide()

        # 标记状态（用于set_flag）
        self.flag_combo = QComboBox()
        self.flag_combo.addItems(["true", "false"])
        self.flag_combo.currentTextChanged.connect(self._on_flag_changed)
        self.flag_combo.hide()

        # 删除按钮
        self.delete_button = QPushButton("×")
        self.delete_button.setFixedSize(24, 24)
        self.delete_button.setStyleSheet("""
            QPushButton {
                background-color: #C97850;
                color: white;
                border: none;
                border-radius: 4px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #B56A42;
            }
        """)

        # 添加到布局
        layout.addWidget(self.type_combo)
        layout.addWidget(self.target_input, 1)
        layout.addWidget(self.folder_combo)
        layout.addWidget(self.label_combo)
        layout.addWidget(self.flag_combo)
        layout.addWidget(self.delete_button)

        self.setLayout(layout)

        # 加载文件夹和标签
        self._load_folders()
        self._load_labels()

    def _load_folders(self):
        """加载文件夹列表"""
        try:
            folders = [f.name for f in Folder.get_all() if f.type != "system"]
            self.folder_combo.clear()
            self.folder_combo.addItems(folders)
        except Exception:
            pass

    def _load_labels(self):
        """加载标签列表"""
        try:
            labels = [label.name for label in Label.get_all()]
            self.label_combo.clear()
            self.label_combo.addItems(labels)
        except Exception:
            pass

    def _on_type_changed(self):
        """类型变化事件"""
        action_type = self.type_combo.currentText()

        # 隐藏所有特殊控件
        self.target_input.show()
        self.folder_combo.hide()
        self.label_combo.hide()
        self.flag_combo.hide()

        # 显示适当的控件
        if action_type == "move_to_folder":
            self.folder_combo.show()
            self.target_input.hide()
        elif action_type == "apply_label":
            self.label_combo.show()
            self.target_input.hide()
        elif action_type == "set_flag":
            self.flag_combo.show()
            self.target_input.hide()
        elif action_type in ["mark_read", "mark_important", "delete", "mark_spam"]:
            self.target_input.hide()

        self.action_changed.emit()

    def _on_folder_changed(self, folder_name):
        """文件夹变化事件"""
        self.target_input.setText(folder_name)

    def _on_label_changed(self, label_name):
        """标签变化事件"""
        self.target_input.setText(label_name)

    def _on_flag_changed(self, flag_value):
        """标记状态变化事件"""
        self.target_input.setText(flag_value)

    def _load_action(self):
        """加载动作"""
        if not self.action:
            return

        # 设置类型
        action_type = self.action.get("type", "move_to_folder")
        if self.type_combo.findText(action_type) >= 0:
            self.type_combo.setCurrentText(action_type)

        # 设置目标
        target = self.action.get("target", "")
        self.target_input.setText(target)

        # 更新控件状态
        self._on_type_changed()

        # 设置特殊控件的值
        action_type = self.type_combo.currentText()
        if action_type == "move_to_folder":
            if self.folder_combo.findText(target) >= 0:
                self.folder_combo.setCurrentText(target)
        elif action_type == "apply_label":
            if self.label_combo.findText(target) >= 0:
                self.label_combo.setCurrentText(target)
        elif action_type == "set_flag":
            if self.flag_combo.findText(target) >= 0:
                self.flag_combo.setCurrentText(target)

    def get_action(self) -> Dict:
        """获取动作"""
        return {
            "type": self.type_combo.currentText(),
            "target": self.target_input.text().strip(),
        }

    def is_valid(self) -> bool:
        """检查动作是否有效"""
        action_type = self.type_combo.currentText()
        target = self.target_input.text().strip()

        # 某些动作不需要目标
        if action_type in ["mark_read", "mark_important", "delete", "mark_spam"]:
            return True

        # move_to_folder 需要目标文件夹存在
        if action_type == "move_to_folder":
            return bool(target)

        # 其他动作需要非空目标
        return bool(target)


class EnhancedFilterRuleEditor(QDialog):
    """增强版过滤规则编辑器对话框"""

    rule_saved = pyqtSignal(EnhancedFilterRule)

    def __init__(self, rule: Optional[EnhancedFilterRule] = None, parent=None):
        super().__init__(parent)

        self.rule = rule
        self.condition_widgets = []
        self.action_widgets = []

        self.setWindowTitle(f"{'编辑' if rule else '创建'}过滤规则")
        self.setMinimumSize(800, 600)

        self._setup_ui()
        self._load_rule()

    def _setup_ui(self):
        """设置UI"""
        layout = QVBoxLayout()

        # 基本信息组
        info_group = QGroupBox("基本信息")
        info_layout = QFormLayout()

        self.name_input = QLineEdit()
        self.name_input.setPlaceholderText("规则名称")
        info_layout.addRow("规则名称:", self.name_input)

        self.description_input = QTextEdit()
        self.description_input.setMaximumHeight(60)
        self.description_input.setPlaceholderText("规则描述（可选）")
        info_layout.addRow("描述:", self.description_input)

        info_group.setLayout(info_layout)
        layout.addWidget(info_group)

        # 条件和动作容器
        splitter = QSplitter(Qt.Orientation.Horizontal)

        # 条件面板
        conditions_panel = QWidget()
        conditions_layout = QVBoxLayout()

        conditions_header = QHBoxLayout()
        conditions_header.addWidget(QLabel("条件"))
        add_condition_btn = QPushButton("添加条件")
        add_condition_btn.clicked.connect(self._add_condition)
        conditions_header.addWidget(add_condition_btn)
        conditions_header.addStretch()

        logic_group = QGroupBox("逻辑关系")
        logic_layout = QHBoxLayout()
        self.and_radio = QCheckBox("AND（所有条件必须满足）")
        self.and_radio.setChecked(True)
        self.or_radio = QCheckBox("OR（任一条件满足）")
        logic_layout.addWidget(self.and_radio)
        logic_layout.addWidget(self.or_radio)
        logic_group.setLayout(logic_layout)

        self.conditions_container = QWidget()
        self.conditions_container.setLayout(QVBoxLayout())
        self.conditions_container.layout().setContentsMargins(0, 0, 0, 0)

        conditions_scroll = QWidget()
        conditions_scroll_layout = QVBoxLayout()
        conditions_scroll_layout.addWidget(self.conditions_container)
        conditions_scroll_layout.addStretch(1)
        conditions_scroll.setLayout(conditions_scroll_layout)

        conditions_layout.addLayout(conditions_header)
        conditions_layout.addWidget(logic_group)
        conditions_layout.addWidget(conditions_scroll, 1)

        conditions_panel.setLayout(conditions_layout)

        # 动作面板
        actions_panel = QWidget()
        actions_layout = QVBoxLayout()

        actions_header = QHBoxLayout()
        actions_header.addWidget(QLabel("动作"))
        add_action_btn = QPushButton("添加动作")
        add_action_btn.clicked.connect(self._add_action)
        actions_header.addWidget(add_action_btn)
        actions_header.addStretch()

        options_group = QGroupBox("选项")
        options_layout = QVBoxLayout()

        self.enabled_check = QCheckBox("启用规则")
        self.enabled_check.setChecked(True)
        options_layout.addWidget(self.enabled_check)

        self.stop_processing_check = QCheckBox("匹配后停止处理其他规则")
        options_layout.addWidget(self.stop_processing_check)

        options_group.setLayout(options_layout)

        self.actions_container = QWidget()
        self.actions_container.setLayout(QVBoxLayout())
        self.actions_container.layout().setContentsMargins(0, 0, 0, 0)

        actions_scroll = QWidget()
        actions_scroll_layout = QVBoxLayout()
        actions_scroll_layout.addWidget(self.actions_container)
        actions_scroll_layout.addStretch(1)
        actions_scroll.setLayout(actions_scroll_layout)

        actions_layout.addLayout(actions_header)
        actions_layout.addWidget(options_group)
        actions_layout.addWidget(actions_scroll, 1)

        actions_panel.setLayout(actions_layout)

        # 添加到分割器
        splitter.addWidget(conditions_panel)
        splitter.addWidget(actions_panel)
        splitter.setSizes([400, 400])

        layout.addWidget(splitter, 1)

        # 优先级和按钮
        bottom_layout = QHBoxLayout()

        priority_layout = QHBoxLayout()
        priority_layout.addWidget(QLabel("优先级:"))
        self.priority_spin = QSpinBox()
        self.priority_spin.setRange(0, 100)
        self.priority_spin.setValue(0)
        self.priority_spin.setToolTip("数值越大，优先级越高")
        priority_layout.addWidget(self.priority_spin)
        bottom_layout.addLayout(priority_layout)

        bottom_layout.addStretch()

        self.test_button = QPushButton("测试")
        self.test_button.clicked.connect(self._test_rule)
        self.test_button.setEnabled(self.rule and self.rule.id)
        bottom_layout.addWidget(self.test_button)

        button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        button_box.accepted.connect(self._save_rule)
        button_box.rejected.connect(self.reject)
        bottom_layout.addWidget(button_box)

        layout.addLayout(bottom_layout)

        self.setLayout(layout)

    def _add_condition(self, condition: Optional[Dict] = None):
        """添加条件"""
        condition_widget = ConditionWidget(condition)
        condition_widget.delete_button.clicked.connect(
            lambda: self._remove_widget(
                condition_widget, self.condition_widgets, self.conditions_container
            )
        )

        self.condition_widgets.append(condition_widget)
        self.conditions_container.layout().addWidget(condition_widget)

    def _add_action(self, action: Optional[Dict] = None):
        """添加动作"""
        action_widget = ActionWidget(action)
        action_widget.delete_button.clicked.connect(
            lambda: self._remove_widget(
                action_widget, self.action_widgets, self.actions_container
            )
        )

        self.action_widgets.append(action_widget)
        self.actions_container.layout().addWidget(action_widget)

    def _remove_widget(self, widget, widget_list, container):
        """移除部件"""
        container.layout().removeWidget(widget)
        widget.deleteLater()
        widget_list.remove(widget)

    def _load_rule(self):
        """加载规则"""
        if not self.rule:
            # 添加默认条件
            self._add_condition()
            # 添加默认动作
            self._add_action()
            return

        # 基本信息
        self.name_input.setText(self.rule.name)
        self.description_input.setText(self.rule.description)

        # 条件逻辑
        if self.rule.condition_logic == "and":
            self.and_radio.setChecked(True)
            self.or_radio.setChecked(False)
        else:
            self.and_radio.setChecked(False)
            self.or_radio.setChecked(True)

        # 加载条件
        for condition in self.rule.conditions:
            self._add_condition(condition)

        # 加载动作
        for action in self.rule.actions:
            self._add_action(action)

        # 选项
        self.enabled_check.setChecked(self.rule.is_enabled)
        self.stop_processing_check.setChecked(self.rule.stop_processing)

        # 优先级
        self.priority_spin.setValue(self.rule.priority)

    def _save_rule(self):
        """保存规则"""
        # 验证基本信息
        name = self.name_input.text().strip()
        if not name:
            QMessageBox.warning(self, "错误", "请输入规则名称")
            return

        # 收集条件
        conditions = []
        for widget in self.condition_widgets:
            if widget.is_valid():
                conditions.append(widget.get_condition())

        if not conditions:
            QMessageBox.warning(self, "错误", "至少需要一个有效条件")
            return

        # 收集动作
        actions = []
        for widget in self.action_widgets:
            if widget.is_valid():
                actions.append(widget.get_action())

        if not actions:
            QMessageBox.warning(self, "错误", "至少需要一个有效动作")
            return

        # 创建或更新规则
        if not self.rule:
            self.rule = EnhancedFilterRule()

        self.rule.name = name
        self.rule.description = self.description_input.toPlainText().strip()
        self.rule.conditions = conditions
        self.rule.condition_logic = "and" if self.and_radio.isChecked() else "or"
        self.rule.actions = actions
        self.rule.is_enabled = self.enabled_check.isChecked()
        self.rule.priority = self.priority_spin.value()
        self.rule.stop_processing = self.stop_processing_check.isChecked()

        try:
            self.rule.save()
            self.accept()
        except Exception as e:
            QMessageBox.critical(self, "错误", f"保存规则时出错: {e}")

    def _test_rule(self):
        """测试规则"""
        # TODO: 实现规则测试功能
        QMessageBox.information(self, "测试", "测试功能开发中...")

    def get_rule(self) -> EnhancedFilterRule:
        """获取规则"""
        return self.rule


class EnhancedFilterManager(QWidget):
    """增强版过滤器管理器"""

    def __init__(self, parent=None):
        super().__init__(parent)

        self.filter_engine = EnhancedFilterEngine()
        self._setup_ui()
        self._load_rules()

    def _setup_ui(self):
        """设置UI"""
        layout = QVBoxLayout()

        # 工具栏
        toolbar = QHBoxLayout()

        create_btn = QPushButton("创建规则")
        create_btn.clicked.connect(self._create_rule)
        toolbar.addWidget(create_btn)

        edit_btn = QPushButton("编辑规则")
        edit_btn.clicked.connect(self._edit_rule)
        toolbar.addWidget(edit_btn)

        delete_btn = QPushButton("删除规则")
        delete_btn.clicked.connect(self._delete_rule)
        toolbar.addWidget(delete_btn)

        enable_btn = QPushButton("启用/禁用")
        enable_btn.clicked.connect(self._toggle_enabled)
        toolbar.addWidget(enable_btn)

        test_btn = QPushButton("测试规则")
        test_btn.clicked.connect(self._test_selected_rule)
        toolbar.addWidget(test_btn)

        import_btn = QPushButton("导入")
        import_btn.clicked.connect(self._import_rules)
        toolbar.addWidget(import_btn)

        export_btn = QPushButton("导出")
        export_btn.clicked.connect(self._export_rules)
        toolbar.addWidget(export_btn)

        toolbar.addStretch()

        refresh_btn = QPushButton("刷新")
        refresh_btn.clicked.connect(self._load_rules)
        toolbar.addWidget(refresh_btn)

        layout.addLayout(toolbar)

        # 规则列表
        self.rules_table = QTableWidget()
        self.rules_table.setColumnCount(6)
        self.rules_table.setHorizontalHeaderLabels(
            ["名称", "启用", "优先级", "命中次数", "最后触发", "类型"]
        )
        self.rules_table.horizontalHeader().setStretchLastSection(True)
        self.rules_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.rules_table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)

        # 右键菜单
        self.rules_table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.rules_table.customContextMenuRequested.connect(self._show_context_menu)

        layout.addWidget(self.rules_table, 1)

        # 统计信息
        self.stats_label = QLabel("")
        self._update_stats()
        layout.addWidget(self.stats_label)

        self.setLayout(layout)

    def _load_rules(self):
        """加载规则"""
        self.rules_table.setRowCount(0)

        rules = EnhancedFilterRule.get_all()

        for i, rule in enumerate(rules):
            self.rules_table.insertRow(i)

            # 名称
            name_item = QTableWidgetItem(rule.name)
            name_item.setData(Qt.ItemDataRole.UserRole, rule.id)
            if rule.description:
                name_item.setToolTip(rule.description)
            self.rules_table.setItem(i, 0, name_item)

            # 启用状态
            enabled_item = QTableWidgetItem("✓" if rule.is_enabled else "✗")
            enabled_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.rules_table.setItem(i, 1, enabled_item)

            # 优先级
            priority_item = QTableWidgetItem(str(rule.priority))
            priority_item.setTextAlignment(
                Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
            )
            self.rules_table.setItem(i, 2, priority_item)

            # 命中次数
            hits_item = QTableWidgetItem(str(rule.hit_count))
            hits_item.setTextAlignment(
                Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
            )
            self.rules_table.setItem(i, 3, hits_item)

            # 最后触发
            last_triggered = (
                rule.last_triggered.strftime("%Y-%m-%d %H:%M")
                if rule.last_triggered
                else "从未"
            )
            last_item = QTableWidgetItem(last_triggered)
            self.rules_table.setItem(i, 4, last_item)

            # 类型
            type_item = QTableWidgetItem(rule.rule_type)
            self.rules_table.setItem(i, 5, type_item)

        self.rules_table.resizeColumnsToContents()
        self._update_stats()

    def _update_stats(self):
        """更新统计信息"""
        stats = self.filter_engine.get_statistics()

        total = stats.get("total_rules", 0)
        enabled = stats.get("enabled_rules", 0)
        hits = stats.get("total_hits", 0)

        self.stats_label.setText(
            f"总规则数: {total} | 启用: {enabled} | 总命中次数: {hits}"
        )

    def _get_selected_rule_id(self) -> Optional[int]:
        """获取选中的规则ID"""
        selected = self.rules_table.selectedItems()
        if not selected:
            return None

        row = selected[0].row()
        item = self.rules_table.item(row, 0)
        return item.data(Qt.ItemDataRole.UserRole)

    def _get_selected_rule(self) -> Optional[EnhancedFilterRule]:
        """获取选中的规则"""
        rule_id = self._get_selected_rule_id()
        if not rule_id:
            return None

        return EnhancedFilterRule.get_by_id(rule_id)

    def _create_rule(self):
        """创建规则"""
        dialog = EnhancedFilterRuleEditor(parent=self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self._load_rules()

    def _edit_rule(self):
        """编辑规则"""
        rule = self._get_selected_rule()
        if not rule:
            QMessageBox.warning(self, "提示", "请先选择一个规则")
            return

        dialog = EnhancedFilterRuleEditor(rule, parent=self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self._load_rules()

    def _delete_rule(self):
        """删除规则"""
        rule = self._get_selected_rule()
        if not rule:
            QMessageBox.warning(self, "提示", "请先选择一个规则")
            return

        reply = QMessageBox.question(
            self,
            "确认删除",
            f"确定要删除规则 '{rule.name}' 吗？",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )

        if reply == QMessageBox.StandardButton.Yes:
            rule.delete()
            self._load_rules()

    def _toggle_enabled(self):
        """切换启用状态"""
        rule = self._get_selected_rule()
        if not rule:
            QMessageBox.warning(self, "提示", "请先选择一个规则")
            return

        rule.is_enabled = not rule.is_enabled
        rule.save()
        self._load_rules()

    def _test_selected_rule(self):
        """测试选中的规则"""
        rule = self._get_selected_rule()
        if not rule:
            QMessageBox.warning(self, "提示", "请先选择一个规则")
            return

        # TODO: 实现规则测试对话框
        QMessageBox.information(self, "测试", f"测试规则 '{rule.name}'...")

    def _show_context_menu(self, position):
        """显示右键菜单"""
        menu = QMenu()

        edit_action = menu.addAction("编辑")
        edit_action.triggered.connect(self._edit_rule)

        delete_action = menu.addAction("删除")
        delete_action.triggered.connect(self._delete_rule)

        toggle_action = menu.addAction("启用/禁用")
        toggle_action.triggered.connect(self._toggle_enabled)

        menu.addSeparator()

        test_action = menu.addAction("测试规则")
        test_action.triggered.connect(self._test_selected_rule)

        menu.exec(self.rules_table.mapToGlobal(position))

    def _import_rules(self):
        """导入规则"""
        QMessageBox.information(self, "导入", "导入功能开发中...")

    def _export_rules(self):
        """导出规则"""
        QMessageBox.information(self, "导出", "导出功能开发中...")

    def refresh_rules(self):
        """刷新规则列表"""
        self._load_rules()
