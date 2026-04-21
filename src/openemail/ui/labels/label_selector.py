from __future__ import annotations

from typing import List, Optional, Dict

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import (
    QColor,
    QBrush,
    QMouseEvent,
    QEnterEvent,
    QContextMenuEvent,
)
from PyQt6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QPushButton,
    QLabel,
    QLineEdit,
    QFrame,
    QScrollArea,
    QMenu,
    QToolButton,
    QDialog,
    QDialogButtonBox,
    QListWidget,
    QListWidgetItem,
)

from openemail.models.label import Label
from openemail.models.email import Email


class LabelBadge(QFrame):
    """标签徽章控件"""

    clicked = pyqtSignal(int)  # 标签ID
    removed = pyqtSignal(int)  # 标签ID

    def __init__(self, label: Label, removable: bool = False, parent=None):
        super().__init__(parent)

        self.label = label
        self.removable = removable
        self.hovered = False

        self._setup_ui()
        self._setup_style()

        # 启用鼠标跟踪
        self.setMouseTracking(True)

    def _setup_ui(self):
        """设置UI"""
        layout = QHBoxLayout()
        layout.setContentsMargins(6, 2, 6, 2)
        layout.setSpacing(4)

        # 颜色点
        self.color_dot = QLabel()
        self.color_dot.setFixedSize(8, 8)
        self.color_dot.setStyleSheet(f"""
            background-color: {self.label.color};
            border-radius: 4px;
        """)

        # 标签文本
        self.text_label = QLabel(self.label.display_name or self.label.name)
        self.text_label.setStyleSheet("color: white; font-size: 11px;")

        # 移除按钮（如果可移除）
        if self.removable:
            self.remove_btn = QLabel("×")
            self.remove_btn.setFixedSize(12, 12)
            self.remove_btn.setStyleSheet("""
                QLabel {
                    color: #141413;
                    font-weight: bold;
                    font-size: 10px;
                }
                QLabel:hover {
                    color: #C97850;
                }
            """)
            self.remove_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            layout.addWidget(self.remove_btn)
        else:
            self.remove_btn = None

        layout.addWidget(self.color_dot)
        layout.addWidget(self.text_label)
        layout.addStretch()

        self.setLayout(layout)

        # 设置固定高度
        self.setFixedHeight(22)

    def _setup_style(self):
        """设置样式"""
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self._update_style()

    def _update_style(self):
        """更新样式"""
        if self.hovered:
            self.setStyleSheet(f"""
                QFrame {{
                    background-color: rgba({self._hex_to_rgb(self.label.color)}, 0.3);
                    border: 1px solid {self.label.color};
                    border-radius: 4px;
                }}
            """)
        else:
            self.setStyleSheet(f"""
                QFrame {{
                    background-color: rgba({self._hex_to_rgb(self.label.color)}, 0.2);
                    border: 1px solid rgba({self._hex_to_rgb(self.label.color)}, 0.5);
                    border-radius: 4px;
                }}
            """)

    def _hex_to_rgb(self, hex_color: str) -> str:
        """将十六进制颜色转换为RGB字符串"""
        hex_color = hex_color.lstrip("#")
        if len(hex_color) == 3:
            hex_color = "".join([c * 2 for c in hex_color])

        r = int(hex_color[0:2], 16)
        g = int(hex_color[2:4], 16)
        b = int(hex_color[4:6], 16)

        return f"{r}, {g}, {b}"

    def enterEvent(self, event: QEnterEvent):
        """鼠标进入事件"""
        self.hovered = True
        self._update_style()
        super().enterEvent(event)

    def leaveEvent(self, event):
        """鼠标离开事件"""
        self.hovered = False
        self._update_style()
        super().leaveEvent(event)

    def mousePressEvent(self, event: QMouseEvent):
        """鼠标点击事件"""
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit(self.label.id)

        super().mousePressEvent(event)

    def contextMenuEvent(self, event: QContextMenuEvent):
        """右键菜单事件"""
        menu = QMenu(self)

        # 编辑标签
        edit_action = menu.addAction("编辑标签")
        edit_action.triggered.connect(lambda: self.clicked.emit(self.label.id))

        # 移除标签（如果可移除）
        if self.removable:
            menu.addSeparator()
            remove_action = menu.addAction("移除标签")
            remove_action.triggered.connect(lambda: self.removed.emit(self.label.id))

        menu.exec(event.globalPos())

    def get_label_id(self) -> int:
        """获取标签ID"""
        return self.label.id


class LabelSelector(QWidget):
    """标签选择器"""

    labels_changed = pyqtSignal(list)  # 标签ID列表

    def __init__(self, account_id: Optional[int] = None, parent=None):
        super().__init__(parent)

        self.account_id = account_id
        self.selected_labels: List[int] = []
        self.label_badges: Dict[int, LabelBadge] = {}

        self._setup_ui()
        self._load_labels()

    def _setup_ui(self):
        """设置UI"""
        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        # 标题
        title_layout = QHBoxLayout()
        title_label = QLabel("标签")
        title_label.setStyleSheet("font-weight: bold;")
        title_layout.addWidget(title_label)
        title_layout.addStretch()

        # 添加标签按钮
        self.add_btn = QToolButton()
        self.add_btn.setText("+")
        self.add_btn.setToolTip("添加标签")
        self.add_btn.setFixedSize(24, 24)
        self.add_btn.clicked.connect(self._show_add_dialog)
        title_layout.addWidget(self.add_btn)

        layout.addLayout(title_layout)

        # 标签容器（滚动区域）
        self.labels_scroll = QScrollArea()
        self.labels_scroll.setWidgetResizable(True)
        self.labels_scroll.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )
        self.labels_scroll.setVerticalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAsNeeded
        )
        self.labels_scroll.setMaximumHeight(150)
        self.labels_scroll.setStyleSheet("""
            QScrollArea {
                border: 1px solid #45475a;
                border-radius: 4px;
                background-color: #1e1e2e;
            }
            QScrollArea > QWidget > QWidget {
                background-color: transparent;
            }
        """)

        # 标签容器内部部件
        self.labels_container = QWidget()
        self.labels_layout = QVBoxLayout()
        self.labels_layout.setContentsMargins(8, 8, 8, 8)
        self.labels_layout.setSpacing(4)

        # 占位符文本
        self.placeholder_label = QLabel("无标签")
        self.placeholder_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.placeholder_label.setStyleSheet("color: #6C665F; font-style: italic;")
        self.labels_layout.addWidget(self.placeholder_label)

        self.labels_layout.addStretch()
        self.labels_container.setLayout(self.labels_layout)
        self.labels_scroll.setWidget(self.labels_container)

        layout.addWidget(self.labels_scroll)

        self.setLayout(layout)

    def _load_labels(self):
        """加载可用的标签"""
        self.available_labels = Label.get_all(account_id=self.account_id)

    def set_selected_labels(self, label_ids: List[int]):
        """设置选中的标签"""
        self.selected_labels = label_ids[:]  # 复制列表
        self._update_display()

    def add_label(self, label_id: int):
        """添加标签"""
        if label_id not in self.selected_labels:
            self.selected_labels.append(label_id)
            self._update_display()
            self.labels_changed.emit(self.selected_labels)

    def remove_label(self, label_id: int):
        """移除标签"""
        if label_id in self.selected_labels:
            self.selected_labels.remove(label_id)
            self._update_display()
            self.labels_changed.emit(self.selected_labels)

    def _update_display(self):
        """更新显示"""
        # 清除现有徽章
        for badge in self.label_badges.values():
            self.labels_layout.removeWidget(badge)
            badge.deleteLater()
        self.label_badges.clear()

        # 隐藏/显示占位符
        if self.selected_labels:
            self.placeholder_label.setVisible(False)

            # 添加选中的标签徽章
            for label_id in self.selected_labels:
                label = Label.get_by_id(label_id)
                if label:
                    badge = LabelBadge(label, removable=True)
                    badge.clicked.connect(lambda lid: self._on_label_clicked(lid))
                    badge.removed.connect(lambda lid: self.remove_label(lid))

                    self.labels_layout.insertWidget(
                        self.labels_layout.count() - 1,  # 在占位符前插入
                        badge,
                    )
                    self.label_badges[label_id] = badge
        else:
            self.placeholder_label.setVisible(True)

    def _on_label_clicked(self, label_id: int):
        """标签点击事件"""
        # TODO: 可以跳转到标签管理器编辑标签
        # 现在暂时只是发送信号
        self.labels_changed.emit(self.selected_labels)

    def _show_add_dialog(self):
        """显示添加标签对话框"""
        dialog = LabelSelectionDialog(self.available_labels, self.account_id, self)

        if dialog.exec() == QDialog.DialogCode.Accepted:
            selected_labels = dialog.get_selected_labels()
            for label_id in selected_labels:
                self.add_label(label_id)


class LabelSelectionDialog(QDialog):
    """标签选择对话框"""

    def __init__(
        self,
        available_labels: List[Label],
        account_id: Optional[int] = None,
        parent=None,
    ):
        super().__init__(parent)

        self.available_labels = available_labels
        self.account_id = account_id
        self.selected_label_ids: List[int] = []

        self.setWindowTitle("选择标签")
        self.setMinimumSize(400, 500)

        self._setup_ui()
        self._load_labels()

    def _setup_ui(self):
        """设置UI"""
        layout = QVBoxLayout()

        # 搜索框
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("搜索标签...")
        self.search_input.textChanged.connect(self._on_search_changed)
        layout.addWidget(self.search_input)

        # 标签列表
        self.labels_list = QListWidget()
        self.labels_list.setSelectionMode(QListWidget.SelectionMode.MultiSelection)
        layout.addWidget(self.labels_list, 1)

        # 快速操作
        quick_actions = QHBoxLayout()

        select_all_btn = QPushButton("全选")
        select_all_btn.clicked.connect(self._select_all)
        quick_actions.addWidget(select_all_btn)

        clear_all_btn = QPushButton("清除")
        clear_all_btn.clicked.connect(self._clear_all)
        quick_actions.addWidget(clear_all_btn)

        new_label_btn = QPushButton("新建标签")
        new_label_btn.clicked.connect(self._create_new_label)
        quick_actions.addWidget(new_label_btn)

        quick_actions.addStretch()
        layout.addLayout(quick_actions)

        # 按钮
        button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)
        layout.addWidget(button_box)

        self.setLayout(layout)

    def _load_labels(self):
        """加载标签到列表"""
        self.labels_list.clear()

        for label in self.available_labels:
            item = QListWidgetItem()
            item.setText(f"{label.display_name}")
            item.setData(Qt.ItemDataRole.UserRole, label.id)

            # 设置工具提示
            tooltip = f"名称: {label.name}\n"
            tooltip += f"类型: {label.type}\n"
            tooltip += f"邮件数: {label.email_count}"
            item.setToolTip(tooltip)

            # 设置颜色
            item.setForeground(QBrush(QColor(label.color)))

            self.labels_list.addItem(item)

    def _on_search_changed(self, text: str):
        """搜索文本变化"""
        search_text = text.strip().lower()

        for i in range(self.labels_list.count()):
            item = self.labels_list.item(i)
            label_text = item.text().lower()
            label = Label.get_by_id(item.data(Qt.ItemDataRole.UserRole))

            # 检查是否匹配搜索文本
            matches = (
                search_text in label_text
                or (label and search_text in label.name.lower())
                or (label and search_text in label.description.lower())
            )

            item.setHidden(not matches)

    def _select_all(self):
        """全选"""
        for i in range(self.labels_list.count()):
            item = self.labels_list.item(i)
            if not item.isHidden():
                item.setSelected(True)

    def _clear_all(self):
        """清除选择"""
        self.labels_list.clearSelection()

    def _create_new_label(self):
        """创建新标签"""
        from openemail.ui.labels.label_manager import LabelEditorDialog

        dialog = LabelEditorDialog(account_id=self.account_id, parent=self)

        if dialog.exec() == QDialog.DialogCode.Accepted:
            new_label = dialog.get_label()
            if new_label:
                # 重新加载标签
                self.available_labels = Label.get_all(account_id=self.account_id)
                self._load_labels()

                # 选中新创建的标签
                for i in range(self.labels_list.count()):
                    item = self.labels_list.item(i)
                    if item.data(Qt.ItemDataRole.UserRole) == new_label.id:
                        item.setSelected(True)
                        break

    def get_selected_labels(self) -> List[int]:
        """获取选中的标签"""
        selected_ids = []
        for item in self.labels_list.selectedItems():
            label_id = item.data(Qt.ItemDataRole.UserRole)
            if label_id:
                selected_ids.append(label_id)

        return selected_ids

    def accept(self):
        """接受选择"""
        self.selected_label_ids = self.get_selected_labels()
        super().accept()


class EmailLabelWidget(QWidget):
    """邮件标签小工具（用于邮件列表项）"""

    def __init__(self, email_id: Optional[int] = None, parent=None):
        super().__init__(parent)

        self.email_id = email_id
        self.labels: List[Label] = []

        self._setup_ui()

        if email_id:
            self.load_email_labels(email_id)

    def _setup_ui(self):
        """设置UI"""
        self.layout = QHBoxLayout()
        self.layout.setContentsMargins(0, 0, 0, 0)
        self.layout.setSpacing(2)
        self.layout.setAlignment(Qt.AlignmentFlag.AlignLeft)

        self.setLayout(self.layout)

    def load_email_labels(self, email_id: int):
        """加载邮件的标签"""
        self.email_id = email_id
        self.labels = Label.get_for_email(email_id)
        self._update_display()

    def _update_display(self):
        """更新显示"""
        # 清除现有徽章
        for i in reversed(range(self.layout.count())):
            widget = self.layout.itemAt(i).widget()
            if widget:
                widget.setParent(None)

        # 添加标签徽章
        for label in self.labels:
            if label.visibility != "hidden":  # 不显示隐藏的标签
                badge = LabelBadge(label, removable=False)
                badge.setFixedHeight(16)

                # 设置最大宽度
                badge.setMaximumWidth(100)
                badge.text_label.setMaximumWidth(80)
                badge.text_label.setToolTip(label.display_name)

                # 截断文本
                text = label.display_name
                if len(text) > 10:
                    text = text[:8] + "..."
                badge.text_label.setText(text)

                self.layout.addWidget(badge)

        # 如果没有标签，添加一个小的占位符
        if not self.labels:
            placeholder = QLabel("")
            placeholder.setFixedSize(1, 16)
            self.layout.addWidget(placeholder)

    def get_label_ids(self) -> List[int]:
        """获取标签ID列表"""
        return [label.id for label in self.labels]

    def refresh(self):
        """刷新显示"""
        if self.email_id:
            self.load_email_labels(self.email_id)


# 邮件详情页的标签管理器
class EmailDetailLabelManager(QWidget):
    """邮件详情标签管理器"""

    def __init__(self, email: Optional[Email] = None, parent=None):
        super().__init__(parent)

        self.email = email
        self.selector: Optional[LabelSelector] = None

        self._setup_ui()

        if email:
            self.load_email(email)

    def _setup_ui(self):
        """设置UI"""
        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)

        self.selector = LabelSelector(
            account_id=self.email.account_id if self.email else None, parent=self
        )

        layout.addWidget(self.selector)
        self.setLayout(layout)

    def load_email(self, email: Email):
        """加载邮件"""
        self.email = email
        if self.selector:
            self.selector.account_id = email.account_id

            # 加载邮件的标签
            labels = Label.get_for_email(email.id)
            label_ids = [label.id for label in labels]

            self.selector.set_selected_labels(label_ids)
            self.selector.labels_changed.connect(self._on_labels_changed)

    def _on_labels_changed(self, label_ids: List[int]):
        """标签变化事件"""
        if not self.email:
            return

        # 获取当前邮件的标签
        current_labels = Label.get_for_email(self.email.id)
        current_ids = {label.id for label in current_labels}
        new_ids = set(label_ids)

        # 找出需要添加和删除的标签
        to_add = new_ids - current_ids
        to_remove = current_ids - new_ids

        # 应用更改
        for label_id in to_add:
            label = Label.get_by_id(label_id)
            if label:
                label.add_to_email(self.email.id)

        for label_id in to_remove:
            label = Label.get_by_id(label_id)
            if label:
                label.remove_from_email(self.email.id)

    def refresh(self):
        """刷新"""
        if self.email:
            self.load_email(self.email)
