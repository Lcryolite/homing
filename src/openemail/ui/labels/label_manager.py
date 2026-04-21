from __future__ import annotations

import json
from typing import List, Optional

from PyQt6.QtCore import Qt, pyqtSignal, QPoint
from PyQt6.QtGui import (
    QFont,
    QColor,
    QIcon,
    QPainter,
    QPen,
)
from PyQt6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QPushButton,
    QLabel,
    QLineEdit,
    QComboBox,
    QGroupBox,
    QFormLayout,
    QTextEdit,
    QSplitter,
    QDialog,
    QDialogButtonBox,
    QMessageBox,
    QMenu,
    QTreeWidget,
    QTreeWidgetItem,
    QColorDialog,
    QInputDialog,
)

from openemail.models.label import Label, LabelType, LabelVisibility
from openemail.models.account import Account


class LabelColorWidget(QPushButton):
    """标签颜色选择器"""

    color_changed = pyqtSignal(str)

    def __init__(self, color: str = "#7C8A9A", parent=None):
        super().__init__(parent)

        self._color = color
        self._setup_ui()
        self._connect_signals()

    def _setup_ui(self):
        """设置UI"""
        self.setText("")
        self.setFixedSize(32, 32)
        self._update_color_display()

    def _connect_signals(self):
        """连接信号"""
        self.clicked.connect(self._choose_color)

    def _update_color_display(self):
        """更新颜色显示"""
        self.setStyleSheet(f"""
            QPushButton {{
                background-color: {self._color};
                border: 2px solid #E8E1D8;
                border-radius: 6px;
            }}
            QPushButton:hover {{
                border-color: #7C8A9A;
            }}
        """)

    def _choose_color(self):
        """选择颜色"""
        dialog = QColorDialog(QColor(self._color), self)
        dialog.setWindowTitle("选择标签颜色")

        # 设置预设颜色
        preset_colors = [
            "#7C8A9A",
            "#74c7ec",
            "#89dceb",
            "#94e2d5",  # 蓝色系
            "#a6e3a1",
            "#C97850",
            "#fab387",
            "#C97850",  # 绿色/黄色/橙色/粉色
            "#cba6f7",
            "#f2cdcd",
            "#f5c2e7",
            "#bac2de",  # 紫色/红色/粉色/灰色
        ]

        for i, color in enumerate(preset_colors):
            dialog.setCustomColor(i, QColor(color))

        if dialog.exec() == QDialog.DialogCode.Accepted:
            new_color = dialog.selectedColor()
            self._color = new_color.name()
            self._update_color_display()
            self.color_changed.emit(self._color)

    def get_color(self) -> str:
        """获取颜色"""
        return self._color

    def set_color(self, color: str):
        """设置颜色"""
        self._color = color
        self._update_color_display()


class LabelTreeWidget(QTreeWidget):
    """标签树控件"""

    label_selected = pyqtSignal(int)  # 标签ID
    label_edited = pyqtSignal(int)  # 标签ID
    label_deleted = pyqtSignal(int)  # 标签ID

    def __init__(self, parent=None):
        super().__init__(parent)

        self.setHeaderHidden(True)
        self.setColumnCount(3)
        self.setSelectionMode(QTreeWidget.SelectionMode.SingleSelection)

        # 右键菜单
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.customContextMenuRequested.connect(self._show_context_menu)

        # 双击编辑
        self.itemDoubleClicked.connect(self._on_item_double_clicked)

        # 样式
        self.setStyleSheet("""
            QTreeWidget {
                background-color: transparent;
                border: 1px solid #E8E1D8;
                border-radius: 4px;
            }
            QTreeWidget::item {
                padding: 6px;
                border-bottom: 1px solid #FBF8F3;
            }
            QTreeWidget::item:selected {
                background-color: #E8E1D8;
            }
            QTreeWidget::item:hover {
                background-color: #6C665F;
            }
        """)

    def load_labels(self, labels: List[Label]):
        """加载标签"""
        self.clear()

        # 按类型分组
        label_groups = {}
        for label in labels:
            if label.type not in label_groups:
                label_groups[label.type] = []
            label_groups[label.type].append(label)

        # 创建分组
        type_names = {
            LabelType.SYSTEM.value: "系统标签",
            LabelType.USER.value: "用户标签",
            LabelType.SMART.value: "智能标签",
            LabelType.CATEGORY.value: "分类",
        }

        for label_type in [
            LabelType.SYSTEM.value,
            LabelType.USER.value,
            LabelType.SMART.value,
            LabelType.CATEGORY.value,
        ]:
            if label_type in label_groups and label_groups[label_type]:
                group_item = QTreeWidgetItem(self)
                group_item.setText(0, type_names.get(label_type, label_type))
                group_item.setFont(0, QFont("", 10, QFont.Weight.Bold))
                group_item.setExpanded(True)

                # 添加标签项
                for label in label_groups[label_type]:
                    self._add_label_item(group_item, label)

        # 展开所有
        self.expandAll()

    def _add_label_item(self, parent: QTreeWidgetItem, label: Label):
        """添加标签项"""
        item = QTreeWidgetItem(parent)

        # 颜色方块
        _color_item = QTreeWidgetItem()

        # 标签名称和计数
        display_text = f"{label.display_name}"
        if label.email_count > 0:
            if label.unread_count > 0:
                display_text += f" ({label.unread_count}/{label.email_count})"
            else:
                display_text += f" ({label.email_count})"

        item.setText(0, display_text)
        item.setData(0, Qt.ItemDataRole.UserRole, label.id)

        # 设置工具提示
        tooltip = f"名称: {label.name}\n"
        if label.description:
            tooltip += f"描述: {label.description}\n"
        tooltip += f"类型: {label.type}\n"
        tooltip += f"颜色: {label.color}\n"
        tooltip += f"邮件数: {label.email_count}\n"
        tooltip += f"未读: {label.unread_count}"

        item.setToolTip(0, tooltip)

        # 设置图标（颜色）
        icon = self._create_color_icon(label.color)
        item.setIcon(0, icon)

        # 递归添加子标签
        child_labels = Label.get_child_labels(label.id)
        for child in child_labels:
            self._add_label_item(item, child)

    def _create_color_icon(self, color: str) -> QIcon:
        """创建颜色图标"""
        from PyQt6.QtGui import QPixmap

        pixmap = QPixmap(16, 16)
        pixmap.fill(Qt.GlobalColor.transparent)

        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        # 绘制颜色圆
        painter.setBrush(QColor(color))
        painter.setPen(QPen(QColor("#E8E1D8"), 1))
        painter.drawEllipse(0, 0, 15, 15)

        painter.end()

        return QIcon(pixmap)

    def _show_context_menu(self, position: QPoint):
        """显示右键菜单"""
        item = self.itemAt(position)
        if not item:
            return

        label_id = item.data(0, Qt.ItemDataRole.UserRole)
        if not label_id:
            return

        menu = QMenu()

        edit_action = menu.addAction("编辑标签")
        edit_action.triggered.connect(lambda: self.label_edited.emit(label_id))

        delete_action = menu.addAction("删除标签")
        delete_action.triggered.connect(lambda: self.label_deleted.emit(label_id))

        menu.addSeparator()

        add_child_action = menu.addAction("添加子标签")
        add_child_action.triggered.connect(lambda: self._add_child_label(label_id))

        menu.exec(self.mapToGlobal(position))

    def _on_item_double_clicked(self, item: QTreeWidgetItem, column: int):
        """双击事件"""
        label_id = item.data(0, Qt.ItemDataRole.UserRole)
        if label_id:
            self.label_selected.emit(label_id)

    def _add_child_label(self, parent_id: int):
        """添加子标签"""
        dialog = QInputDialog(self)
        dialog.setWindowTitle("添加子标签")
        dialog.setLabelText("请输入子标签名称:")
        dialog.setTextValue("")

        if dialog.exec() == QDialog.DialogCode.Accepted:
            name = dialog.textValue().strip()
            if name:
                # 创建子标签
                parent_label = Label.get_by_id(parent_id)
                if parent_label:
                    child_label = Label(
                        name=name,
                        display_name=name,
                        color=parent_label.color,  # 继承父标签颜色
                        parent_id=parent_id,
                        account_id=parent_label.account_id,
                    )
                    child_label.save()

                    # 刷新列表
                    self._refresh_tree()

    def _refresh_tree(self):
        """刷新树"""
        # 重新加载所有标签
        current_labels = Label.get_all()
        self.load_labels(current_labels)


class LabelEditorDialog(QDialog):
    """标签编辑器对话框"""

    label_saved = pyqtSignal(Label)

    def __init__(
        self,
        label: Optional[Label] = None,
        account_id: Optional[int] = None,
        parent=None,
    ):
        super().__init__(parent)

        self.label = label
        self.account_id = account_id
        self.is_editing = label is not None

        if self.is_editing:
            self.setWindowTitle("编辑标签")
        else:
            self.setWindowTitle("创建标签")

        self.setMinimumSize(400, 450)

        self._setup_ui()
        self._load_label()

    def _setup_ui(self):
        """设置UI"""
        layout = QVBoxLayout()

        # 基本信息组
        basic_group = QGroupBox("基本信息")
        basic_layout = QFormLayout()

        self.name_input = QLineEdit()
        self.name_input.setPlaceholderText("标签名称（英文，无空格）")
        basic_layout.addRow("名称*:", self.name_input)

        self.display_input = QLineEdit()
        self.display_input.setPlaceholderText("显示名称")
        basic_layout.addRow("显示名称:", self.display_input)

        self.description_input = QTextEdit()
        self.description_input.setMaximumHeight(60)
        self.description_input.setPlaceholderText("标签描述（可选）")
        basic_layout.addRow("描述:", self.description_input)

        basic_group.setLayout(basic_layout)
        layout.addWidget(basic_group)

        # 外观组
        appearance_group = QGroupBox("外观")
        appearance_layout = QFormLayout()

        self.color_widget = LabelColorWidget()
        appearance_layout.addRow("颜色:", self.color_widget)

        appearance_group.setLayout(appearance_layout)
        layout.addWidget(appearance_group)

        # 设置组
        settings_group = QGroupBox("设置")
        settings_layout = QVBoxLayout()

        # 标签类型
        type_layout = QHBoxLayout()
        type_layout.addWidget(QLabel("类型:"))

        self.type_combo = QComboBox()
        self.type_combo.addItem("用户标签", LabelType.USER.value)
        self.type_combo.addItem("智能标签", LabelType.SMART.value)
        self.type_combo.addItem("分类", LabelType.CATEGORY.value)

        if not self.is_editing:  # 编辑时不能修改系统标签类型
            self.type_combo.addItem("系统标签", LabelType.SYSTEM.value)

        type_layout.addWidget(self.type_combo)
        type_layout.addStretch()
        settings_layout.addLayout(type_layout)

        # 可见性
        visibility_layout = QHBoxLayout()
        visibility_layout.addWidget(QLabel("可见性:"))

        self.visibility_combo = QComboBox()
        self.visibility_combo.addItem("显示", LabelVisibility.VISIBLE.value)
        self.visibility_combo.addItem("隐藏", LabelVisibility.HIDDEN.value)
        self.visibility_combo.addItem("归档", LabelVisibility.ARCHIVE.value)

        visibility_layout.addWidget(self.visibility_combo)
        visibility_layout.addStretch()
        settings_layout.addLayout(visibility_layout)

        # 父标签
        parent_layout = QHBoxLayout()
        parent_layout.addWidget(QLabel("父标签:"))

        self.parent_combo = QComboBox()
        self.parent_combo.addItem("（无）", None)
        self._load_parent_labels()

        parent_layout.addWidget(self.parent_combo)
        parent_layout.addStretch()
        settings_layout.addLayout(parent_layout)

        settings_group.setLayout(settings_layout)
        layout.addWidget(settings_group)

        # 智能标签规则（仅当类型为智能标签时显示）
        self.smart_rules_group = QGroupBox("智能标签规则")
        self.smart_rules_layout = QVBoxLayout()

        self.rules_edit = QTextEdit()
        self.rules_edit.setPlaceholderText("输入JSON格式的规则...")
        self.rules_edit.setMaximumHeight(100)
        self.smart_rules_layout.addWidget(self.rules_edit)

        example_btn = QPushButton("查看示例")
        example_btn.clicked.connect(self._show_rule_example)
        self.smart_rules_layout.addWidget(example_btn)

        self.smart_rules_group.setLayout(self.smart_rules_layout)
        self.smart_rules_group.setVisible(False)  # 默认隐藏
        layout.addWidget(self.smart_rules_group)

        # 类型变化时显示/隐藏规则编辑器
        self.type_combo.currentTextChanged.connect(self._on_type_changed)

        # 按钮
        button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        button_box.accepted.connect(self._save_label)
        button_box.rejected.connect(self.reject)

        layout.addWidget(button_box)

        self.setLayout(layout)

    def _load_parent_labels(self):
        """加载父标签选项"""
        labels = Label.get_all(account_id=self.account_id, include_hidden=True)

        if self.label:
            # 排除自己和自己的子标签
            exclude_ids = {self.label.id}

            def get_child_ids(parent_id):
                children = Label.get_child_labels(parent_id)
                for child in children:
                    exclude_ids.add(child.id)
                    get_child_ids(child.id)

            get_child_ids(self.label.id)

        self.parent_combo.clear()
        self.parent_combo.addItem("（无）", None)

        for label in labels:
            if self.label and (label.id in exclude_ids):
                continue
            self.parent_combo.addItem(f"{label.display_name} ({label.type})", label.id)

    def _load_label(self):
        """加载标签数据"""
        if not self.label:
            return

        self.name_input.setText(self.label.name)
        self.display_input.setText(self.label.display_name or self.label.name)
        self.description_input.setPlainText(self.label.description)
        self.color_widget.set_color(self.label.color)

        # 设置类型
        index = self.type_combo.findData(self.label.type)
        if index >= 0:
            self.type_combo.setCurrentIndex(index)

        # 设置可见性
        index = self.visibility_combo.findData(self.label.visibility)
        if index >= 0:
            self.visibility_combo.setCurrentIndex(index)

        # 设置父标签
        if self.label.parent_id:
            for i in range(self.parent_combo.count()):
                if self.parent_combo.itemData(i) == self.label.parent_id:
                    self.parent_combo.setCurrentIndex(i)
                    break

        # 如果是智能标签，加载规则
        if self.label.type == LabelType.SMART.value and self.label.description:
            try:
                rules = json.loads(self.label.description)
                self.rules_edit.setPlainText(
                    json.dumps(rules, indent=2, ensure_ascii=False)
                )
            except Exception:
                self.rules_edit.setPlainText(self.label.description)

        # 更新规则编辑器可见性
        self._on_type_changed(self.label.type)

    def _on_type_changed(self, type_name: str):
        """类型变化事件"""
        is_smart = type_name == LabelType.SMART.value
        self.smart_rules_group.setVisible(is_smart)

        # 调整对话框大小
        if is_smart:
            self.resize(self.width(), 550)
        else:
            self.resize(self.width(), 450)

    def _show_rule_example(self):
        """显示规则示例"""
        example = {
            "conditions": [
                {
                    "type": "keyword",
                    "field": "subject",
                    "operator": "contains",
                    "value": "重要",
                }
            ],
            "condition_logic": "or",
        }

        self.rules_edit.setPlainText(json.dumps(example, indent=2, ensure_ascii=False))

    def _save_label(self):
        """保存标签"""
        # 验证输入
        name = self.name_input.text().strip()
        if not name:
            QMessageBox.warning(self, "错误", "请输入标签名称")
            return

        display_name = self.display_input.text().strip()
        if not display_name:
            display_name = name

        description = self.description_input.toPlainText().strip()
        color = self.color_widget.get_color()
        label_type = self.type_combo.currentData()
        visibility = self.visibility_combo.currentData()
        parent_id = self.parent_combo.currentData()

        # 如果是智能标签，验证规则
        if label_type == LabelType.SMART.value:
            rule_text = self.rules_edit.toPlainText().strip()
            if not rule_text:
                QMessageBox.warning(self, "错误", "请输入智能标签规则")
                return

            try:
                json.loads(rule_text)  # 验证JSON
                description = rule_text
            except json.JSONDecodeError as e:
                QMessageBox.warning(self, "错误", f"规则JSON格式错误: {e}")
                return

        # 创建或更新标签
        if not self.label:
            self.label = Label()

        self.label.name = name
        self.label.display_name = display_name
        self.label.description = description
        self.label.color = color
        self.label.type = label_type
        self.label.visibility = visibility
        self.label.parent_id = parent_id
        self.label.account_id = self.account_id

        try:
            self.label.save()
            self.accept()
        except Exception as e:
            QMessageBox.critical(self, "错误", f"保存标签失败: {e}")

    def get_label(self) -> Optional[Label]:
        """获取标签"""
        return self.label


class LabelManager(QWidget):
    """标签管理器"""

    labels_changed = pyqtSignal()

    def __init__(self, account_id: Optional[int] = None, parent=None):
        super().__init__(parent)

        self.account_id = account_id
        self.current_label_id: Optional[int] = None

        self._setup_ui()
        self._connect_signals()
        self._load_labels()

    def _setup_ui(self):
        """设置UI"""
        layout = QVBoxLayout()

        # 工具栏
        toolbar = QHBoxLayout()

        self.create_btn = QPushButton("创建标签")
        self.create_btn.clicked.connect(self._create_label)
        toolbar.addWidget(self.create_btn)

        self.edit_btn = QPushButton("编辑")
        self.edit_btn.clicked.connect(self._edit_label)
        self.edit_btn.setEnabled(False)
        toolbar.addWidget(self.edit_btn)

        self.delete_btn = QPushButton("删除")
        self.delete_btn.clicked.connect(self._delete_label)
        self.delete_btn.setEnabled(False)
        toolbar.addWidget(self.delete_btn)

        self.merge_btn = QPushButton("合并")
        self.merge_btn.clicked.connect(self._merge_labels)
        self.merge_btn.setEnabled(False)
        toolbar.addWidget(self.merge_btn)

        toolbar.addStretch()

        # 账户选择
        self.account_combo = QComboBox()
        self.account_combo.addItem("所有账户", None)
        self._load_accounts()
        self.account_combo.currentIndexChanged.connect(self._on_account_changed)
        toolbar.addWidget(QLabel("账户:"))
        toolbar.addWidget(self.account_combo)

        layout.addLayout(toolbar)

        # 主内容区域
        content_splitter = QSplitter(Qt.Orientation.Horizontal)

        # 左侧：标签树
        left_panel = QWidget()
        left_layout = QVBoxLayout()

        left_layout.addWidget(QLabel("标签列表"))
        self.label_tree = LabelTreeWidget()
        left_layout.addWidget(self.label_tree, 1)

        left_panel.setLayout(left_layout)

        # 右侧：标签详情
        right_panel = QWidget()
        right_layout = QVBoxLayout()

        right_layout.addWidget(QLabel("标签详情"))
        self.detail_widget = QWidget()
        self.detail_layout = QVBoxLayout()
        self.detail_widget.setLayout(self.detail_layout)

        # 占位符文本
        self.placeholder_label = QLabel("选择标签查看详情")
        self.placeholder_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.placeholder_label.setStyleSheet("font-style: italic;")
        self.detail_layout.addWidget(self.placeholder_label)

        right_layout.addWidget(self.detail_widget, 1)

        right_panel.setLayout(right_layout)

        # 添加到分割器
        content_splitter.addWidget(left_panel)
        content_splitter.addWidget(right_panel)
        content_splitter.setSizes([300, 400])

        layout.addWidget(content_splitter, 1)

        self.setLayout(layout)

    def _load_accounts(self):
        """加载账户列表"""
        try:
            accounts = Account.get_all()
            for account in accounts:
                self.account_combo.addItem(
                    f"{account.name} ({account.email})", account.id
                )
        except Exception:
            pass

    def _connect_signals(self):
        """连接信号"""
        self.label_tree.label_selected.connect(self._on_label_selected)
        self.label_tree.label_edited.connect(self._edit_label)
        self.label_tree.label_deleted.connect(self._delete_label)

    def _load_labels(self):
        """加载标签"""
        account_id = self.account_combo.currentData()
        labels = Label.get_all(account_id=account_id)
        self.label_tree.load_labels(labels)
        # 发出标签变化信号
        self.labels_changed.emit()

    def _on_account_changed(self):
        """账户变化事件"""
        self._load_labels()
        self._clear_detail()

    def _on_label_selected(self, label_id: int):
        """标签选择事件"""
        self.current_label_id = label_id
        self.edit_btn.setEnabled(True)
        self.delete_btn.setEnabled(True)
        self.merge_btn.setEnabled(True)

        label = Label.get_by_id(label_id)
        if label:
            self._show_label_detail(label)

    def _show_label_detail(self, label: Label):
        """显示标签详情"""
        # 清除当前详情
        self._clear_detail()

        # 移除占位符
        self.placeholder_label.setVisible(False)

        # 创建详情表单
        form = QFormLayout()

        # 基本信息
        form.addRow("名称:", QLabel(label.name))
        form.addRow("显示名称:", QLabel(label.display_name or label.name))

        # 颜色预览
        color_label = QLabel()
        color_label.setFixedSize(20, 20)
        color_label.setStyleSheet(
            f"background-color: {label.color}; border: 1px solid #E8E1D8; border-radius: 3px;"
        )
        form.addRow("颜色:", color_label)

        # 类型和可见性
        type_names = {
            LabelType.USER.value: "用户标签",
            LabelType.SYSTEM.value: "系统标签",
            LabelType.SMART.value: "智能标签",
            LabelType.CATEGORY.value: "分类",
        }
        form.addRow("类型:", QLabel(type_names.get(label.type, label.type)))

        visibility_names = {
            LabelVisibility.VISIBLE.value: "显示",
            LabelVisibility.HIDDEN.value: "隐藏",
            LabelVisibility.ARCHIVE.value: "归档",
        }
        form.addRow(
            "可见性:", QLabel(visibility_names.get(label.visibility, label.visibility))
        )

        # 父标签
        if label.parent_id:
            parent = Label.get_by_id(label.parent_id)
            if parent:
                form.addRow("父标签:", QLabel(parent.display_name))

        # 计数
        form.addRow("邮件总数:", QLabel(str(label.email_count)))
        form.addRow("未读邮件:", QLabel(str(label.unread_count)))

        # 同步状态
        sync_text = "已同步" if label.is_synced else "未同步"
        if label.sync_state != "synced":
            sync_text += f" ({label.sync_state})"
        form.addRow("同步状态:", QLabel(sync_text))

        # 创建时间
        if label.created_at:
            created = label.created_at.strftime("%Y-%m-%d %H:%M:%S")
            form.addRow("创建时间:", QLabel(created))

        # 描述
        if label.description:
            desc_label = QLabel(label.description)
            desc_label.setWordWrap(True)
            form.addRow("描述:", desc_label)

        # 添加到详情面板
        group = QGroupBox("标签信息")
        group.setLayout(form)
        self.detail_layout.addWidget(group)

        # 如果是智能标签，显示规则
        if label.type == LabelType.SMART.value and label.description:
            try:
                rules = json.loads(label.description)
                rules_text = QTextEdit()
                rules_text.setPlainText(json.dumps(rules, indent=2, ensure_ascii=False))
                rules_text.setReadOnly(True)

                rules_group = QGroupBox("智能标签规则")
                rules_layout = QVBoxLayout()
                rules_layout.addWidget(rules_text)
                rules_group.setLayout(rules_layout)

                self.detail_layout.addWidget(rules_group)
            except Exception:
                pass

        # 添加操作按钮
        action_btn = QPushButton("应用此标签到邮件...")
        action_btn.clicked.connect(lambda: self._apply_label_to_emails(label.id))
        self.detail_layout.addWidget(action_btn)

        self.detail_layout.addStretch()

    def _clear_detail(self):
        """清除详情显示"""
        # 隐藏所有小组件
        for i in reversed(range(self.detail_layout.count())):
            widget = self.detail_layout.itemAt(i).widget()
            if widget:
                widget.setParent(None)

        # 显示占位符
        self.placeholder_label.setVisible(True)

    def _create_label(self):
        """创建标签"""
        account_id = self.account_combo.currentData()
        dialog = LabelEditorDialog(account_id=account_id, parent=self)

        if dialog.exec() == QDialog.DialogCode.Accepted:
            self._load_labels()

    def _edit_label(self, label_id: Optional[int] = None):
        """编辑标签"""
        label_id = label_id or self.current_label_id
        if not label_id:
            return

        label = Label.get_by_id(label_id)
        if not label:
            return

        dialog = LabelEditorDialog(
            label=label, account_id=label.account_id, parent=self
        )

        if dialog.exec() == QDialog.DialogCode.Accepted:
            self._load_labels()

            # 如果正在查看此标签，刷新详情
            if self.current_label_id == label_id:
                self._on_label_selected(label_id)

    def _delete_label(self, label_id: Optional[int] = None):
        """删除标签"""
        label_id = label_id or self.current_label_id
        if not label_id:
            return

        label = Label.get_by_id(label_id)
        if not label:
            return

        # 系统标签不能删除
        if label.type == LabelType.SYSTEM.value:
            QMessageBox.warning(self, "提示", "系统标签不能删除")
            return

        # 确认对话框
        reply = QMessageBox.question(
            self,
            "确认删除",
            f"确定要删除标签 '{label.display_name}' 吗？\n"
            f"此操作将移除所有邮件上的此标签。",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )

        if reply == QMessageBox.StandardButton.Yes:
            if label.delete():
                QMessageBox.information(self, "成功", "标签已删除")
                self._load_labels()
                self._clear_detail()
                self.edit_btn.setEnabled(False)
                self.delete_btn.setEnabled(False)
                self.merge_btn.setEnabled(False)
            else:
                QMessageBox.critical(self, "错误", "删除标签失败")

    def _merge_labels(self):
        """合并标签"""
        if not self.current_label_id:
            return

        # 获取所有可合并的标签（排除当前标签）
        account_id = self.account_combo.currentData()
        labels = Label.get_all(account_id=account_id)

        merge_dialog = QDialog(self)
        merge_dialog.setWindowTitle("合并标签")
        merge_dialog.setMinimumSize(300, 200)

        layout = QVBoxLayout()

        layout.addWidget(QLabel("将当前标签合并到:"))

        self.merge_target_combo = QComboBox()
        for label in labels:
            if label.id != self.current_label_id:
                self.merge_target_combo.addItem(
                    f"{label.display_name} ({label.type})", label.id
                )

        if self.merge_target_combo.count() == 0:
            QMessageBox.warning(self, "提示", "没有其他标签可合并")
            return

        layout.addWidget(self.merge_target_combo)

        button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )

        def merge_confirm():
            target_id = self.merge_target_combo.currentData()
            if not target_id:
                return

            current_label = Label.get_by_id(self.current_label_id)
            if current_label and current_label.merge_with(target_id):
                QMessageBox.information(self, "成功", "标签已合并")
                merge_dialog.accept()
                self._load_labels()
                self._clear_detail()
            else:
                QMessageBox.critical(self, "错误", "合并标签失败")

        button_box.accepted.connect(merge_confirm)
        button_box.rejected.connect(merge_dialog.reject)

        layout.addWidget(button_box)
        merge_dialog.setLayout(layout)
        merge_dialog.exec()

    def _apply_label_to_emails(self, label_id: int):
        """应用标签到邮件（批量操作）"""
        # TODO: 实现批量应用标签功能
        QMessageBox.information(self, "功能开发中", "批量应用标签功能正在开发中...")

    def refresh_labels(self):
        """刷新标签列表"""
        self._load_labels()
