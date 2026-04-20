from __future__ import annotations

import os
from typing import List, Optional

from PyQt6.QtCore import Qt, pyqtSignal, QSize, QTimer
from PyQt6.QtGui import QAction, QFont, QIcon, QKeySequence, QPixmap
from PyQt6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QFrame,
    QMenu,
    QAbstractItemView,
    QListView,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QToolBar,
    QToolButton,
    QProgressBar,
    QMessageBox,
    QApplication,
)

from openemail.models.email import Email
from openemail.models.folder import Folder


class EnhancedMailItemWidget(QWidget):
    """支持选择的邮件项部件"""

    clicked = pyqtSignal(int)
    selection_changed = pyqtSignal(int, bool)  # email_id, is_selected

    def __init__(self, email: Email, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self._email_id = email.id
        self._is_selected = False
        self._email = email
        self._setup_ui(email)

        # 允许点击选择
        self.setAttribute(Qt.WidgetAttribute.WA_Hover, True)

    def _setup_ui(self, email: Email):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 8, 12, 8)
        layout.setSpacing(8)

        # 选择复选框
        self._checkbox = QLabel()
        self._checkbox.setFixedSize(20, 20)
        self._checkbox.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._update_checkbox_style()
        layout.addWidget(self._checkbox)

        # 发件人图标
        sender_icon = QLabel()
        sender_icon.setFixedSize(32, 32)
        sender_icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        sender_icon.setText(self._get_sender_icon(email))
        sender_icon.setStyleSheet("""
            QLabel {
                background: #585b70;
                color: #cdd6f4;
                border-radius: 16px;
                font-size: 14px;
                font-weight: bold;
            }
        """)
        layout.addWidget(sender_icon)

        # 邮件信息（左侧）
        info_layout = QVBoxLayout()
        info_layout.setSpacing(2)

        # 发件人和时间
        sender_time_layout = QHBoxLayout()

        sender_label = QLabel(email.sender_name or email.sender_addr)
        sender_label.setStyleSheet("font-weight: bold; font-size: 13px;")
        if not email.is_read:
            sender_label.setStyleSheet(
                "font-weight: bold; font-size: 13px; color: #cdd6f4;"
            )
        sender_time_layout.addWidget(sender_label)

        sender_time_layout.addStretch()

        date_label = QLabel(email.display_date)
        date_label.setStyleSheet("color: #a6adc8; font-size: 11px;")
        sender_time_layout.addWidget(date_label)

        info_layout.addLayout(sender_time_layout)

        # 主题
        subject_label = QLabel(email.subject or "(无主题)")
        subject_label.setStyleSheet("font-size: 12px;")
        if not email.is_read:
            subject_label.setStyleSheet(
                "font-size: 12px; font-weight: bold; color: #cdd6f4;"
            )
        info_layout.addWidget(subject_label)

        # 预览文本
        if email.preview_text:
            preview_label = QLabel(email.preview_text)
            preview_label.setStyleSheet("color: #a6adc8; font-size: 11px;")
            preview_label.setWordWrap(False)
            info_layout.addWidget(preview_label)

        layout.addLayout(info_layout, 1)

        # 右侧图标区域
        icon_layout = QHBoxLayout()
        icon_layout.setSpacing(6)

        # 标签/标签图标
        try:
            # 首先尝试显示新的标签系统
            from openemail.models.label import Label, LabelEmailRel

            label_ids = LabelEmailRel.get_label_ids_for_email(email.id)
            for label_id in label_ids[:2]:  # 最多显示2个标签
                label = Label.get_by_id(label_id)
                if label:
                    label_label = QLabel(label.icon or "🏷️")
                    label_label.setToolTip(label.display_name or label.name)
                    label_label.setStyleSheet(f"font-size: 12px; color: {label.color};")
                    icon_layout.addWidget(label_label)
        except ImportError:
            # 回退到旧的标签系统
            tags = email.get_tags()
            if tags:
                for tag in tags[:2]:  # 最多显示2个标签
                    tag_label = QLabel(tag.icon)
                    tag_label.setToolTip(tag.name)
                    tag_label.setStyleSheet(f"font-size: 12px; color: {tag.color};")
                    icon_layout.addWidget(tag_label)

        # 星标图标
        if email.is_flagged:
            flag_label = QLabel("★")
            flag_label.setStyleSheet("color: #f9e2af; font-size: 14px;")
            flag_label.setToolTip("已加星标")
            icon_layout.addWidget(flag_label)

        # 附件图标
        if email.has_attachment:
            att_label = QLabel("📎")
            att_label.setStyleSheet("font-size: 12px; color: #a6adc8;")
            att_label.setToolTip("有附件")
            icon_layout.addWidget(att_label)

        # 垃圾邮件图标
        if email.is_spam:
            spam_label = QLabel("🚫")
            spam_label.setStyleSheet("font-size: 12px; color: #f38ba8;")
            spam_label.setToolTip("垃圾邮件")
            icon_layout.addWidget(spam_label)

        layout.addLayout(icon_layout)

        # 设置鼠标事件
        self.setMouseTracking(True)

    def _get_sender_icon(self, email: Email) -> str:
        """获取发件人头像图标"""
        # 使用发件人名字的第一个字母，或邮箱的第一个字母
        name = email.sender_name or email.sender_addr
        if not name:
            return "?"

        # 如果是中文，取第一个字符
        if any("\u4e00" <= c <= "\u9fff" for c in name):
            return name[0]

        # 英文取第一个字母的大写
        for char in name:
            if char.isalpha():
                return char.upper()

        # 如果都是非字母字符，取第一个字符
        return name[0] if name else "?"

    def _update_checkbox_style(self):
        """更新复选框样式"""
        if self._is_selected:
            self._checkbox.setText("✓")
            self._checkbox.setStyleSheet("""
                QLabel {
                    background: #89b4fa;
                    color: #11111b;
                    border: 2px solid #89b4fa;
                    border-radius: 4px;
                    font-size: 12px;
                    font-weight: bold;
                }
            """)
        else:
            self._checkbox.setText("")
            self._checkbox.setStyleSheet("""
                QLabel {
                    background: transparent;
                    border: 2px solid #585b70;
                    border-radius: 4px;
                }
                QLabel:hover {
                    border-color: #89b4fa;
                }
            """)

        # 更新背景色
        if self._is_selected:
            self.setStyleSheet("""
                EnhancedMailItemWidget {
                    background: rgba(137, 180, 250, 0.2);
                    border-left: 4px solid #89b4fa;
                }
                EnhancedMailItemWidget:hover {
                    background: rgba(137, 180, 250, 0.3);
                }
            """)
        elif not self._email.is_read:
            self.setStyleSheet("""
                EnhancedMailItemWidget {
                    background: #313244;
                    border-left: 4px solid transparent;
                }
                EnhancedMailItemWidget:hover {
                    background: #45475a;
                }
            """)
        else:
            self.setStyleSheet("""
                EnhancedMailItemWidget {
                    background: transparent;
                    border-left: 4px solid transparent;
                }
                EnhancedMailItemWidget:hover {
                    background: #313244;
                }
            """)

    def set_selected(self, selected: bool):
        """设置选中状态"""
        if self._is_selected != selected:
            self._is_selected = selected
            self._update_checkbox_style()
            self.selection_changed.emit(self._email_id, selected)

    def toggle_selection(self):
        """切换选中状态"""
        self.set_selected(not self._is_selected)

    def is_selected(self) -> bool:
        """返回是否选中"""
        return self._is_selected

    @property
    def email_id(self) -> int:
        return self._email_id

    def mousePressEvent(self, event):
        """鼠标点击事件"""
        if event.button() == Qt.MouseButton.LeftButton:
            # 点击复选框区域进行选择
            if event.pos().x() < 40:  # 复选框区域
                self.toggle_selection()
                self.clicked.emit(self._email_id)
            else:
                # 点击其他区域跳转到邮件
                self.clicked.emit(self._email_id)

        super().mousePressEvent(event)

    def mouseDoubleClickEvent(self, event):
        """鼠标双击事件"""
        if event.button() == Qt.MouseButton.LeftButton:
            # 禁用复选框选择的双击事件
            if event.pos().x() >= 40:
                self.clicked.emit(self._email_id)
        super().mouseDoubleClickEvent(event)


class BatchActionToolbar(QToolBar):
    """批量操作工具栏"""

    mark_read_requested = pyqtSignal(list)  # email_ids
    mark_unread_requested = pyqtSignal(list)  # email_ids
    mark_flagged_requested = pyqtSignal(list, bool)  # email_ids, is_flagged
    move_requested = pyqtSignal(list)  # email_ids
    delete_requested = pyqtSignal(list)  # email_ids
    mark_spam_requested = pyqtSignal(list)  # email_ids
    clear_selection = pyqtSignal()

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self._selected_count = 0
        self._setup_ui()

    def _setup_ui(self):
        self.setMovable(False)
        self.setFloatable(False)
        self.setStyleSheet("""
            QToolBar {
                background: #313244;
                border: 1px solid #45475a;
                border-radius: 6px;
                padding: 4px;
                spacing: 8px;
            }
            QToolButton {
                padding: 4px 12px;
                border-radius: 4px;
                font-size: 12px;
            }
            QToolButton:hover {
                background: #45475a;
            }
            QToolButton:disabled {
                color: #585b70;
            }
        """)

        # 选择计数
        self._count_label = QLabel("选择 0 封邮件")
        self._count_label.setStyleSheet(
            "font-size: 12px; color: #a6adc8; padding: 0 8px;"
        )
        self.addWidget(self._count_label)

        self.addSeparator()

        # 标记为已读
        self._mark_read_btn = QToolButton()
        self._mark_read_btn.setText("标记为已读")
        self._mark_read_btn.clicked.connect(self._on_mark_read)
        self.addWidget(self._mark_read_btn)

        # 标记为未读
        self._mark_unread_btn = QToolButton()
        self._mark_unread_btn.setText("标记为未读")
        self._mark_unread_btn.clicked.connect(self._on_mark_unread)
        self.addWidget(self._mark_unread_btn)

        self.addSeparator()

        # 加星标
        self._flag_btn = QToolButton()
        self._flag_btn.setText("加星标")
        self._flag_btn.clicked.connect(lambda: self._on_flag(True))
        self.addWidget(self._flag_btn)

        # 取消星标
        self._unflag_btn = QToolButton()
        self._unflag_btn.setText("取消星标")
        self._unflag_btn.clicked.connect(lambda: self._on_flag(False))
        self.addWidget(self._unflag_btn)

        self.addSeparator()

        # 移动到文件夹
        self._move_btn = QToolButton()
        self._move_btn.setText("移动到")
        self._move_btn.clicked.connect(self._on_move)
        self.addWidget(self._move_btn)

        # 删除
        self._delete_btn = QToolButton()
        self._delete_btn.setText("删除")
        self._delete_btn.setStyleSheet("color: #f38ba8;")
        self._delete_btn.clicked.connect(self._on_delete)
        self.addWidget(self._delete_btn)

        # 标记为垃圾邮件
        self._spam_btn = QToolButton()
        self._spam_btn.setText("标记为垃圾")
        self._spam_btn.setStyleSheet("color: #f38ba8;")
        self._spam_btn.clicked.connect(self._on_mark_spam)
        self.addWidget(self._spam_btn)

        self.addSeparator()

        # 清除选择
        self._clear_btn = QToolButton()
        self._clear_btn.setText("清除选择")
        self._clear_btn.clicked.connect(self.clear_selection.emit)
        self.addWidget(self._clear_btn)

        # 初始状态：禁用所有按钮
        self._update_button_states()

    def update_selection_count(self, count: int):
        """更新选择计数"""
        self._selected_count = count
        if count > 0:
            self._count_label.setText(f"选择 {count} 封邮件")
            self._count_label.setStyleSheet(
                "font-size: 12px; color: #89b4fa; font-weight: bold; padding: 0 8px;"
            )
        else:
            self._count_label.setText("选择 0 封邮件")
            self._count_label.setStyleSheet(
                "font-size: 12px; color: #a6adc8; padding: 0 8px;"
            )

        self._update_button_states()

    def _update_button_states(self):
        """更新按钮状态"""
        has_selection = self._selected_count > 0

        self._mark_read_btn.setEnabled(has_selection)
        self._mark_unread_btn.setEnabled(has_selection)
        self._flag_btn.setEnabled(has_selection)
        self._unflag_btn.setEnabled(has_selection)
        self._move_btn.setEnabled(has_selection)
        self._delete_btn.setEnabled(has_selection)
        self._spam_btn.setEnabled(has_selection)
        self._clear_btn.setEnabled(has_selection)

    def _on_mark_read(self):
        """标记为已读"""
        self.mark_read_requested.emit([])  # 空列表表示当前选中

    def _on_mark_unread(self):
        """标记为未读"""
        self.mark_unread_requested.emit([])  # 空列表表示当前选中

    def _on_flag(self, flagged: bool):
        """标记星标"""
        self.mark_flagged_requested.emit([], flagged)  # 空列表表示当前选中

    def _on_move(self):
        """移动到文件夹"""
        self.move_requested.emit([])  # 空列表表示当前选中

    def _on_delete(self):
        """删除邮件"""
        # 确认对话框
        if self._selected_count > 5:  # 大量删除时提示
            reply = QMessageBox.question(
                self,
                "确认删除",
                f"确定要删除 {self._selected_count} 封邮件吗？",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            if reply == QMessageBox.StandardButton.Yes:
                self.delete_requested.emit([])
        else:
            self.delete_requested.emit([])

    def _on_mark_spam(self):
        """标记为垃圾邮件"""
        self.mark_spam_requested.emit([])  # 空列表表示当前选中


class EnhancedMailListWidget(QWidget):
    """增强版邮件列表，支持多选和批量操作"""

    # 基础信号
    email_selected = pyqtSignal(int)
    email_double_clicked = pyqtSignal(int)

    # 批量操作信号
    batch_mark_read = pyqtSignal(list)  # email_ids
    batch_mark_unread = pyqtSignal(list)  # email_ids
    batch_mark_flagged = pyqtSignal(list, bool)  # email_ids, is_flagged
    batch_move = pyqtSignal(list)  # email_ids
    batch_delete = pyqtSignal(list)  # email_ids
    batch_mark_spam = pyqtSignal(list)  # email_ids

    # 单个操作信号（向后兼容）
    mark_read_requested = pyqtSignal(int)
    mark_flagged_requested = pyqtSignal(int, bool)
    delete_requested = pyqtSignal(int)
    mark_spam_requested = pyqtSignal(int)
    mark_not_spam_requested = pyqtSignal(int)

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self._emails: List[Email] = []
        self._selected_ids: set[int] = set()
        self._selection_mode = False
        self._last_selected_index = -1
        self._setup_ui()

        # 设置键盘快捷键
        self._setup_shortcuts()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)

        # 标题栏
        self._header = QLabel("收件箱")
        self._header.setStyleSheet("""
            QLabel {
                font-size: 16px;
                font-weight: bold;
                padding: 12px 16px;
                background: #313244;
                border-radius: 6px 6px 0 0;
                border-bottom: 1px solid #45475a;
            }
        """)
        layout.addWidget(self._header)

        # 批量操作工具栏（初始隐藏）
        self._batch_toolbar = BatchActionToolbar()
        self._batch_toolbar.setVisible(False)
        self._batch_toolbar.mark_read_requested.connect(self._on_batch_mark_read)
        self._batch_toolbar.mark_unread_requested.connect(self._on_batch_mark_unread)
        self._batch_toolbar.mark_flagged_requested.connect(self._on_batch_mark_flagged)
        self._batch_toolbar.move_requested.connect(self._on_batch_move)
        self._batch_toolbar.delete_requested.connect(self._on_batch_delete)
        self._batch_toolbar.mark_spam_requested.connect(self._on_batch_mark_spam)
        self._batch_toolbar.clear_selection.connect(self._clear_selection)
        layout.addWidget(self._batch_toolbar)

        # 邮件列表（使用QListWidget实现多选）
        self._list_widget = QListWidget()
        self._list_widget.setSelectionMode(QListWidget.SelectionMode.NoSelection)
        self._list_widget.setVerticalScrollMode(QListWidget.ScrollMode.ScrollPerPixel)
        self._list_widget.setStyleSheet("""
            QListWidget {
                background: #1e1e2e;
                border: none;
                outline: none;
            }
            QListWidget::item {
                border-bottom: 1px solid #313244;
            }
            QListWidget::item:selected {
                background: transparent;
            }
        """)

        layout.addWidget(self._list_widget, 1)

        # 状态栏
        self._status_bar = QFrame()
        self._status_bar.setStyleSheet("""
            QFrame {
                background: #313244;
                border: none;
                border-top: 1px solid #45475a;
                padding: 8px 16px;
            }
        """)
        status_layout = QHBoxLayout(self._status_bar)
        status_layout.setContentsMargins(0, 0, 0, 0)

        self._status_label = QLabel("就绪")
        self._status_label.setStyleSheet("color: #a6adc8; font-size: 11px;")
        status_layout.addWidget(self._status_label)

        status_layout.addStretch()

        self._progress_bar = QProgressBar()
        self._progress_bar.setVisible(False)
        self._progress_bar.setMaximumWidth(200)
        self._progress_bar.setTextVisible(False)
        status_layout.addWidget(self._progress_bar)

        layout.addWidget(self._status_bar)

    def _setup_shortcuts(self):
        """设置键盘快捷键"""
        # Ctrl+A: 全选/取消全选
        select_all_action = QAction("全选", self)
        select_all_action.setShortcut(QKeySequence.StandardKey.SelectAll)
        select_all_action.triggered.connect(self._toggle_select_all)
        self.addAction(select_all_action)

        # Escape: 清除选择
        escape_action = QAction("清除选择", self)
        escape_action.setShortcut(QKeySequence.StandardKey.Cancel)
        escape_action.triggered.connect(self._clear_selection)
        self.addAction(escape_action)

        # Delete: 删除选中邮件
        delete_action = QAction("删除", self)
        delete_action.setShortcut(QKeySequence.StandardKey.Delete)
        delete_action.triggered.connect(self._delete_selected)
        self.addAction(delete_action)

        # Ctrl+Shift+A: 反选
        invert_action = QAction("反选", self)
        invert_action.setShortcut(QKeySequence("Ctrl+Shift+A"))
        invert_action.triggered.connect(self._invert_selection)
        self.addAction(invert_action)

    def set_title(self, title: str):
        """设置标题"""
        self._header.setText(title)

    def load_emails(self, emails: List[Email]):
        """加载邮件列表"""
        self._emails = emails
        self._list_widget.clear()
        self._selected_ids.clear()

        for email in emails:
            item = QListWidgetItem(self._list_widget)
            widget = EnhancedMailItemWidget(email)
            widget.clicked.connect(self._on_item_clicked)
            widget.selection_changed.connect(self._on_item_selection_changed)

            item.setSizeHint(widget.sizeHint())
            self._list_widget.setItemWidget(item, widget)
            self._list_widget.addItem(item)

        self._update_status(f"加载了 {len(emails)} 封邮件")
        self._update_batch_toolbar()

    def add_email(self, email: Email):
        """添加邮件"""
        self._emails.insert(0, email)

        item = QListWidgetItem(self._list_widget)
        widget = EnhancedMailItemWidget(email)
        widget.clicked.connect(self._on_item_clicked)
        widget.selection_changed.connect(self._on_item_selection_changed)

        item.setSizeHint(widget.sizeHint())
        self._list_widget.setItemWidget(item, widget)
        self._list_widget.insertItem(0, item)

        self._update_status(f"收到新邮件: {email.subject}")

    def remove_email(self, email_id: int):
        """删除邮件"""
        # 从列表中移除
        self._emails = [e for e in self._emails if e.id != email_id]

        # 从UI中移除
        for i in range(self._list_widget.count()):
            item = self._list_widget.item(i)
            widget = self._list_widget.itemWidget(item)
            if widget and widget.email_id == email_id:
                self._list_widget.takeItem(i)
                break

        # 如果邮件被选中，从选中集中移除
        if email_id in self._selected_ids:
            self._selected_ids.remove(email_id)
            self._update_batch_toolbar()

    def refresh_email(self, email: Email):
        """刷新邮件显示"""
        for i in range(self._list_widget.count()):
            item = self._list_widget.item(i)
            widget = self._list_widget.itemWidget(item)
            if widget and widget.email_id == email.id:
                # 创建新部件替换旧的
                new_widget = EnhancedMailItemWidget(email)
                new_widget.clicked.connect(self._on_item_clicked)
                new_widget.selection_changed.connect(self._on_item_selection_changed)
                new_widget.set_selected(email.id in self._selected_ids)  # 保持选择状态

                self._list_widget.setItemWidget(item, new_widget)
                break

    def get_selected_email_id(self) -> Optional[int]:
        """获取选中的邮件ID（单选的向后兼容）"""
        selected = list(self._selected_ids)
        if selected:
            return selected[0]
        return None

    def get_selected_email_ids(self) -> List[int]:
        """获取所有选中的邮件ID"""
        return list(self._selected_ids)

    def _on_item_clicked(self, email_id: int):
        """邮件项被点击"""
        item_idx = self._find_item_index(email_id)
        if item_idx >= 0:
            modifier = QApplication.keyboardModifiers()

            if modifier & Qt.KeyboardModifier.ControlModifier:
                # Ctrl+点击：切换选择
                widget = self._get_item_widget(item_idx)
                if widget:
                    widget.toggle_selection()
            elif modifier & Qt.KeyboardModifier.ShiftModifier:
                # Shift+点击：范围选择
                if self._last_selected_index >= 0:
                    self._select_range(self._last_selected_index, item_idx)
            else:
                # 普通点击：触发选择信号
                self.email_selected.emit(email_id)

            self._last_selected_index = item_idx

    def _on_item_selection_changed(self, email_id: int, selected: bool):
        """邮件项选择状态变化"""
        if selected:
            self._selected_ids.add(email_id)
        else:
            self._selected_ids.discard(email_id)

        self._update_batch_toolbar()

    def _find_item_index(self, email_id: int) -> int:
        """查找邮件项索引"""
        for i in range(self._list_widget.count()):
            item = self._list_widget.item(i)
            widget = self._list_widget.itemWidget(item)
            if widget and widget.email_id == email_id:
                return i
        return -1

    def _get_item_widget(self, index: int) -> Optional[EnhancedMailItemWidget]:
        """获取指定索引的部件"""
        if 0 <= index < self._list_widget.count():
            item = self._list_widget.item(index)
            return self._list_widget.itemWidget(item)
        return None

    def _select_range(self, start_idx: int, end_idx: int):
        """选择范围"""
        if start_idx > end_idx:
            start_idx, end_idx = end_idx, start_idx

        for i in range(start_idx, end_idx + 1):
            widget = self._get_item_widget(i)
            if widget:
                widget.set_selected(True)

    def _toggle_select_all(self):
        """切换全选/取消全选"""
        all_selected = len(self._selected_ids) == len(self._emails)

        for i in range(self._list_widget.count()):
            widget = self._get_item_widget(i)
            if widget:
                widget.set_selected(not all_selected)

        self._update_status(
            f"{'取消全选' if all_selected else '已全选'} {len(self._emails)} 封邮件"
        )

    def _clear_selection(self):
        """清除选择"""
        for email_id in list(self._selected_ids):
            idx = self._find_item_index(email_id)
            if idx >= 0:
                widget = self._get_item_widget(idx)
                if widget:
                    widget.set_selected(False)

        self._selected_ids.clear()
        self._update_batch_toolbar()
        self._update_status("选择已清除")

    def _invert_selection(self):
        """反选"""
        for i in range(self._list_widget.count()):
            widget = self._get_item_widget(i)
            if widget:
                widget.toggle_selection()

        self._update_status("已反选")

    def _delete_selected(self):
        """删除选中邮件"""
        if self._selected_ids:
            self.batch_delete.emit(list(self._selected_ids))

    def _update_batch_toolbar(self):
        """更新批量操作工具栏"""
        has_selection = len(self._selected_ids) > 0
        self._batch_toolbar.setVisible(has_selection)

        if has_selection:
            self._batch_toolbar.update_selection_count(len(self._selected_ids))

            # 如果选择了邮件，暂时隐藏状态栏
            self._status_bar.setVisible(False)
        else:
            self._status_bar.setVisible(True)

    def _update_status(self, message: str):
        """更新状态栏"""
        self._status_label.setText(message)
        self._status_bar.setVisible(True)

        # 5秒后清除状态消息
        QTimer.singleShot(5000, lambda: self._status_label.setText("就绪"))

    def show_progress(self, visible: bool, message: str = ""):
        """显示/隐藏进度条"""
        self._progress_bar.setVisible(visible)
        if message:
            self._status_label.setText(message)

    def set_progress(self, value: int, maximum: int = 100):
        """设置进度条"""
        self._progress_bar.setMaximum(maximum)
        self._progress_bar.setValue(value)

    # 批量操作信号处理
    def _on_batch_mark_read(self, email_ids: List[int]):
        """批量标记为已读"""
        if not email_ids:  # 空列表表示使用当前选中
            email_ids = self.get_selected_email_ids()
        self.batch_mark_read.emit(email_ids)

    def _on_batch_mark_unread(self, email_ids: List[int]):
        """批量标记为未读"""
        if not email_ids:  # 空列表表示使用当前选中
            email_ids = self.get_selected_email_ids()
        self.batch_mark_unread.emit(email_ids)

    def _on_batch_mark_flagged(self, email_ids: List[int], flagged: bool):
        """批量标记星标"""
        if not email_ids:  # 空列表表示使用当前选中
            email_ids = self.get_selected_email_ids()
        self.batch_mark_flagged.emit(email_ids, flagged)

    def _on_batch_move(self, email_ids: List[int]):
        """批量移动（需要文件夹选择）"""
        if not email_ids:  # 空列表表示使用当前选中
            email_ids = self.get_selected_email_ids()

        # 这里应该显示文件夹选择对话框
        # 暂时直接发出信号，让父组件处理
        self.batch_move.emit(email_ids)

    def _on_batch_delete(self, email_ids: List[int]):
        """批量删除"""
        if not email_ids:  # 空列表表示使用当前选中
            email_ids = self.get_selected_email_ids()
        self.batch_delete.emit(email_ids)

    def _on_batch_mark_spam(self, email_ids: List[int]):
        """批量标记为垃圾邮件"""
        if not email_ids:  # 空列表表示使用当前选中
            email_ids = self.get_selected_email_ids()
        self.batch_mark_spam.emit(email_ids)

    # 向后兼容的信号处理
    def _show_context_menu(self, pos):
        """显示右键菜单（向后兼容）"""
        item = self._list_widget.itemAt(pos)
        if not item:
            return

        widget = self._list_widget.itemWidget(item)
        if not widget:
            return

        email_id = widget.email_id
        email = Email.get_by_id(email_id)
        if not email:
            return

        menu = QMenu(self)

        # 单个操作
        mark_read_action = QAction(
            "标记为已读" if not email.is_read else "标记为未读", self
        )
        mark_read_action.triggered.connect(
            lambda: self.mark_read_requested.emit(email_id)
        )
        menu.addAction(mark_read_action)

        flag_action = QAction("取消星标" if email.is_flagged else "添加星标", self)
        flag_action.triggered.connect(
            lambda: self.mark_flagged_requested.emit(email_id, not email.is_flagged)
        )
        menu.addAction(flag_action)

        menu.addSeparator()

        # 添加到批量操作菜单
        batch_menu = menu.addMenu("批量操作")

        if len(self._selected_ids) > 1:
            select_count = len(self._selected_ids)
            select_all_action = QAction(f"应用到选中的 {select_count} 封邮件", self)
            select_all_action.setEnabled(False)
            batch_menu.addAction(select_all_action)
            batch_menu.addSeparator()

        mark_all_read = QAction("标记所有未读为已读")
        mark_all_read.triggered.connect(self._mark_all_unread_as_read)
        batch_menu.addAction(mark_all_read)

        # 垃圾邮件操作
        if not email.is_spam:
            spam_action = QAction("标记为垃圾邮件", self)
            spam_action.triggered.connect(
                lambda: self.mark_spam_requested.emit(email_id)
            )
            menu.addAction(spam_action)
        else:
            not_spam_action = QAction("这不是垃圾邮件", self)
            not_spam_action.triggered.connect(
                lambda: self.mark_not_spam_requested.emit(email_id)
            )
            menu.addAction(not_spam_action)

        menu.addSeparator()
        delete_action = QAction("删除", self)
        delete_action.triggered.connect(lambda: self.delete_requested.emit(email_id))
        menu.addAction(delete_action)

        menu.addSeparator()

        # 复制菜单项
        copy_menu = menu.addMenu("复制")
        copy_email_action = QAction("复制邮箱地址", self)
        copy_email_action.triggered.connect(
            lambda: self._copy_to_clipboard(email.sender_addr)
        )
        copy_menu.addAction(copy_email_action)

        copy_subject_action = QAction("复制主题", self)
        copy_subject_action.triggered.connect(
            lambda: self._copy_to_clipboard(email.subject)
        )
        copy_menu.addAction(copy_subject_action)

        # 标签菜单
        menu.addSeparator()
        label_menu = menu.addMenu("标签")

        # 管理标签项
        manage_labels_action = QAction("管理标签...", self)
        manage_labels_action.triggered.connect(
            lambda: self._show_label_manager(email_id)
        )
        label_menu.addAction(manage_labels_action)

        # 分隔线
        label_menu.addSeparator()

        # 从数据库获取标签并添加到菜单
        try:
            from openemail.models.label import Label, LabelEmailRel

            # 获取邮件的标签
            label_ids = LabelEmailRel.get_label_ids_for_email(email_id)
            current_labels = {label_id: True for label_id in label_ids}

            # 获取所有可用的标签
            all_labels = Label.get_all(account_id=email.account_id)

            for label in all_labels:
                # 跳过系统标签（除非特别处理）
                if label.type == 1:  # SYSTEM
                    continue

                is_applied = label.id in current_labels
                label_action = QAction(
                    f"{'✓ ' if is_applied else ''}{label.display_name or label.name}",
                    self,
                )
                label_action.setCheckable(True)
                label_action.setChecked(is_applied)

                # 使用lambda闭包捕获label.id
                label_action.triggered.connect(
                    lambda checked, eid=email_id, lid=label.id: (
                        self._toggle_email_label(eid, lid, checked)
                    )
                )
                label_menu.addAction(label_action)

        except ImportError as e:
            # 标签模块不可用
            no_labels_action = QAction("标签功能未启用", self)
            no_labels_action.setEnabled(False)
            label_menu.addAction(no_labels_action)

        menu.exec(self.mapToGlobal(pos))

    def _mark_all_unread_as_read(self):
        """标记所有未读邮件为已读"""
        unread_ids = [e.id for e in self._emails if not e.is_read]
        if unread_ids:
            self.batch_mark_read.emit(unread_ids)

    def _copy_to_clipboard(self, text: str):
        """复制文本到剪贴板"""
        clipboard = QApplication.clipboard()
        clipboard.setText(text or "")
        self._update_status("已复制到剪贴板")

    def _show_label_manager(self, email_id: int):
        """显示标签管理对话框"""
        try:
            from openemail.ui.labels.label_selector import EmailDetailLabelManager

            email = Email.get_by_id(email_id)
            if not email:
                return

            dialog = EmailDetailLabelManager(email_id, self)
            dialog.labels_changed.connect(self._on_labels_changed)
            dialog.exec()

        except ImportError as e:
            QMessageBox.warning(self, "错误", f"标签管理器加载失败: {e}")

    def _toggle_email_label(self, email_id: int, label_id: int, checked: bool):
        """切换邮件的标签"""
        try:
            from openemail.models.label import LabelEmailRel

            if checked:
                # 添加标签
                if not LabelEmailRel.exists(email_id, label_id):
                    LabelEmailRel.create(email_id, label_id)
            else:
                # 移除标签
                LabelEmailRel.delete_by_email_and_label(email_id, label_id)

            # 发出信号通知标签变化
            if hasattr(self, "labels_changed"):
                self.labels_changed.emit()

        except Exception as e:
            print(f"切换标签失败: {e}")

    def _on_labels_changed(self):
        """标签变化时刷新邮件显示"""
        # 可以在这里添加刷新逻辑，比如重新加载当前邮件项
        pass
