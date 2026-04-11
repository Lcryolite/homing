from __future__ import annotations

from PyQt6.QtCore import pyqtSignal
from PyQt6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QSpinBox,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from openemail.models.filter_rule import FilterRule


class FilterRulesDialog(QDialog):
    """过滤规则管理对话框"""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("过滤规则管理")
        self.setMinimumSize(800, 500)
        self._setup_ui()
        self._load_rules()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)

        # 规则列表
        self._rules_table = QTableWidget()
        self._rules_table.setColumnCount(6)
        self._rules_table.setHorizontalHeaderLabels(
            ["名称", "类型", "匹配字段", "模式", "动作", "启用"]
        )
        self._rules_table.horizontalHeader().setStretchLastSection(True)
        self._rules_table.setSelectionBehavior(
            QTableWidget.SelectionBehavior.SelectRows
        )
        self._rules_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        layout.addWidget(self._rules_table)

        # 按钮栏
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()

        self._add_rule_btn = QPushButton("添加规则")
        self._add_rule_btn.setProperty("class", "primary")
        self._add_rule_btn.clicked.connect(self._add_rule)
        btn_layout.addWidget(self._add_rule_btn)

        self._edit_rule_btn = QPushButton("编辑")
        self._edit_rule_btn.clicked.connect(self._edit_rule)
        btn_layout.addWidget(self._edit_rule_btn)

        self._delete_rule_btn = QPushButton("删除")
        self._delete_rule_btn.setProperty("class", "danger")
        self._delete_rule_btn.clicked.connect(self._delete_rule)
        btn_layout.addWidget(self._delete_rule_btn)

        layout.addLayout(btn_layout)

    def _load_rules(self) -> None:
        """加载规则列表"""
        rules = FilterRule.get_all()
        self._rules_table.setRowCount(len(rules))

        for i, rule in enumerate(rules):
            self._rules_table.setItem(i, 0, QTableWidgetItem(rule.name))
            self._rules_table.setItem(i, 1, QTableWidgetItem(rule.rule_type))
            self._rules_table.setItem(i, 2, QTableWidgetItem(rule.match_field))
            self._rules_table.setItem(i, 3, QTableWidgetItem(rule.pattern or "-"))

            action_text = rule.action
            if rule.action_target:
                action_text += f" → {rule.action_target}"
            self._rules_table.setItem(i, 4, QTableWidgetItem(action_text))

            enable_check = QCheckBox()
            enable_check.setChecked(rule.is_enabled)
            enable_check.stateChanged.connect(
                lambda state, r=rule: self._toggle_rule(r, state)
            )
            self._rules_table.setCellWidget(i, 5, enable_check)

    def _add_rule(self) -> None:
        """添加规则"""
        dialog = RuleEditDialog(parent=self)
        dialog.rule_saved.connect(self._load_rules)
        dialog.exec()

    def _edit_rule(self) -> None:
        """编辑规则"""
        selected_rows = self._rules_table.selectedItems()
        if not selected_rows:
            return

        row = selected_rows[0].row()
        rules = FilterRule.get_all()
        if row < len(rules):
            dialog = RuleEditDialog(rule=rules[row], parent=self)
            dialog.rule_saved.connect(self._load_rules)
            dialog.exec()

    def _delete_rule(self) -> None:
        """删除规则"""
        selected_rows = self._rules_table.selectedItems()
        if not selected_rows:
            return

        row = selected_rows[0].row()
        rules = FilterRule.get_all()
        if row < len(rules):
            rules[row].delete()
            self._load_rules()

    def _toggle_rule(self, rule: FilterRule, state: int) -> None:
        """启用/禁用规则"""
        rule.is_enabled = bool(state)
        rule.save()


class RuleEditDialog(QDialog):
    """规则编辑对话框"""

    rule_saved = pyqtSignal()

    def __init__(
        self, rule: FilterRule | None = None, parent: QWidget | None = None
    ) -> None:
        super().__init__(parent)
        self._rule = rule
        self.setWindowTitle("编辑过滤规则" if rule else "添加过滤规则")
        self.setMinimumWidth(400)
        self._setup_ui()
        if rule:
            self._load_rule(rule)

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        form = QFormLayout()
        form.setSpacing(8)

        self._name_edit = QLineEdit()
        self._name_edit.setPlaceholderText("规则名称")
        form.addRow("规则名称:", self._name_edit)

        self._type_combo = QComboBox()
        self._type_combo.addItem("关键词", "keyword")
        self._type_combo.addItem("正则表达式", "regex")
        self._type_combo.addItem("发件人黑名单", "blacklist_sender")
        self._type_combo.addItem("域名黑名单", "blacklist_domain")
        form.addRow("规则类型:", self._type_combo)

        self._match_field_combo = QComboBox()
        self._match_field_combo.addItem("全部", "all")
        self._match_field_combo.addItem("主题", "subject")
        self._match_field_combo.addItem("发件人", "sender")
        self._match_field_combo.addItem("正文", "body")
        form.addRow("匹配字段:", self._match_field_combo)

        self._pattern_edit = QLineEdit()
        self._pattern_edit.setPlaceholderText("关键词或正则表达式")
        form.addRow("匹配模式:", self._pattern_edit)

        self._action_combo = QComboBox()
        self._action_combo.addItem("标记为垃圾邮件", "move_spam")
        self._action_combo.addItem("移动到文件夹", "move")
        self._action_combo.addItem("打标签", "tag")
        self._action_combo.addItem("标记已读", "mark_read")
        self._action_combo.addItem("删除", "delete")
        form.addRow("执行动作:", self._action_combo)

        self._action_target_edit = QLineEdit()
        self._action_target_edit.setPlaceholderText("目标文件夹名或标签名")
        form.addRow("目标:", self._action_target_edit)

        self._priority_spin = QSpinBox()
        self._priority_spin.setRange(0, 100)
        self._priority_spin.setValue(0)
        form.addRow("优先级:", self._priority_spin)

        layout.addLayout(form)

        btn_layout = QHBoxLayout()
        btn_layout.addStretch()

        save_btn = QPushButton("保存")
        save_btn.setProperty("class", "primary")
        save_btn.clicked.connect(self._save)
        btn_layout.addWidget(save_btn)

        cancel_btn = QPushButton("取消")
        cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(cancel_btn)

        layout.addLayout(btn_layout)

    def _load_rule(self, rule: FilterRule) -> None:
        """加载规则到表单"""
        self._name_edit.setText(rule.name)
        self._type_combo.setCurrentText(rule.rule_type)
        self._match_field_combo.setCurrentText(rule.match_field)
        self._pattern_edit.setText(rule.pattern or "")
        self._action_combo.setCurrentText(rule.action)
        self._action_target_edit.setText(rule.action_target or "")
        self._priority_spin.setValue(rule.priority)

    def _save(self) -> None:
        """保存规则"""
        if not self._rule:
            self._rule = FilterRule()

        self._rule.name = self._name_edit.text().strip()
        self._rule.rule_type = self._type_combo.currentData()
        self._rule.match_field = self._match_field_combo.currentData()
        self._rule.pattern = self._pattern_edit.text().strip()
        self._rule.action = self._action_combo.currentData()
        self._rule.action_target = self._action_target_edit.text().strip()
        self._rule.priority = self._priority_spin.value()

        self._rule.save()
        self.rule_saved.emit()
        self.accept()
