from __future__ import annotations

import re
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any, Callable

from PyQt6.QtCore import Qt, pyqtSignal, QTimer, QSize, QSortFilterProxyModel
from PyQt6.QtGui import (
    QFont,
    QTextCharFormat,
    QBrush,
    QColor,
    QPainter,
    QPen,
)
from PyQt6.QtWidgets import (
    QWidget,
    QLineEdit,
    QPushButton,
    QHBoxLayout,
    QVBoxLayout,
    QComboBox,
    QLabel,
    QTreeWidget,
    QTreeWidgetItem,
    QMenu,
    QApplication,
    QSizePolicy,
    QFrame,
    QStyleOption,
    QStyle,
    QListView,
)

from openemail.storage.search_enhanced import EnhancedSearchEngine
from openemail.models.email import Email


class SearchSyntaxHighlighter:
    """搜索输入框语法高亮器（QLineEdit版本）"""

    def __init__(self, line_edit=None):
        self.line_edit = line_edit
        self.highlighting_rules = []

        # 这个方法不能直接用在QLineEdit上，因为QLineEdit不支持QSyntaxHighlighter
        # 对于QLineEdit，我们需要使用不同的高亮方法
        # 这里暂时只定义规则，实际高亮需要在其他地方实现

    def highlight_text(self, text: str) -> str:
        """为QLineEdit返回高亮文本（使用HTML格式）"""
        if not self.line_edit:
            return text

        # 这里简单实现，实际应用中可以在文本变化时更新格式
        # 对于QLineEdit，我们可以使用setStyleSheet来实现一些基本高亮
        return text


class SearchSuggestionPopup(QWidget):
    """搜索建议弹出窗口"""

    suggestion_selected = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(
            parent, Qt.WindowType.ToolTip | Qt.WindowType.FramelessWindowHint
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)

        self.setLayout(QVBoxLayout())
        self.layout().setContentsMargins(1, 1, 1, 1)

        # 创建列表
        self.suggestion_list = QTreeWidget()
        self.suggestion_list.setColumnCount(2)
        self.suggestion_list.setHeaderHidden(True)
        self.suggestion_list.setRootIsDecorated(False)
        self.suggestion_list.setIndentation(0)
        self.layout().addWidget(self.suggestion_list)

        # 样式
        self.suggestion_list.setStyleSheet("""
            QTreeWidget {
                background-color: #2d3848;
                border: 1px solid #3d4858;
                border-radius: 4px;
                padding: 2px;
            }
            QTreeWidget::item {
                padding: 4px;
                border-radius: 2px;
            }
            QTreeWidget::item:selected {
                background-color: #404b5b;
            }
            QTreeWidget::item:hover {
                background-color: #374252;
            }
        """)

        # 连接信号
        self.suggestion_list.itemClicked.connect(self._on_item_clicked)
        self.suggestion_list.itemDoubleClicked.connect(self._on_item_double_clicked)

        self.suggestions = []

    def show_suggestions(self, suggestions: List[Dict[str, Any]], input_rect):
        """显示建议列表"""
        self.suggestions = suggestions
        self.suggestion_list.clear()

        if not suggestions:
            self.hide()
            return

        # 添加建议项
        for suggestion in suggestions:
            item = QTreeWidgetItem()

            # 图标列
            icon_item = QTreeWidgetItem()
            icon_item.setText(0, suggestion.get("icon", "⚡"))
            icon_item.setText(1, suggestion.get("text", ""))

            # 描述文本
            text_item = QTreeWidgetItem()
            text_item.setText(0, suggestion.get("text", ""))
            text_item.setText(1, suggestion.get("description", ""))

            # 设置数据
            item.setData(0, Qt.ItemDataRole.UserRole, suggestion.get("value", ""))

            # 添加到列表
            self.suggestion_list.addTopLevelItem(item)

        # 调整大小
        self.suggestion_list.setColumnWidth(0, 30)
        self.suggestion_list.setColumnWidth(1, 200)

        # 计算位置
        screen_rect = QApplication.primaryScreen().availableGeometry()
        popup_width = 250
        popup_height = min(300, len(suggestions) * 30 + 10)

        # 计算位置（在输入框下方）
        x = input_rect.left()
        y = input_rect.bottom() + 2

        # 如果会超出屏幕，则显示在上方
        if y + popup_height > screen_rect.bottom():
            y = input_rect.top() - popup_height - 2

        self.setGeometry(x, y, popup_width, popup_height)
        self.show()

        # 选择第一个项目
        if self.suggestion_list.topLevelItemCount() > 0:
            self.suggestion_list.setCurrentItem(self.suggestion_list.topLevelItem(0))

    def _on_item_clicked(self, item, column):
        """项目点击事件"""
        value = item.data(0, Qt.ItemDataRole.UserRole)
        if value:
            self.suggestion_selected.emit(value)
            self.hide()

    def _on_item_double_clicked(self, item, column):
        """项目双击事件"""
        self._on_item_clicked(item, column)

    def keyPressEvent(self, event):
        """键盘事件"""
        if event.key() in (Qt.Key.Key_Enter, Qt.Key.Key_Return):
            # 选择当前项
            item = self.suggestion_list.currentItem()
            if item:
                self._on_item_clicked(item, 0)
            event.accept()
        elif event.key() == Qt.Key.Key_Escape:
            self.hide()
            event.accept()
        elif event.key() == Qt.Key.Key_Up:
            # 上一个项目
            current = self.suggestion_list.currentItem()
            index = self.suggestion_list.indexOfTopLevelItem(current)
            if index > 0:
                self.suggestion_list.setCurrentItem(
                    self.suggestion_list.topLevelItem(index - 1)
                )
            event.accept()
        elif event.key() == Qt.Key.Key_Down:
            # 下一个项目
            current = self.suggestion_list.currentItem()
            index = self.suggestion_list.indexOfTopLevelItem(current)
            if index < self.suggestion_list.topLevelItemCount() - 1:
                self.suggestion_list.setCurrentItem(
                    self.suggestion_list.topLevelItem(index + 1)
                )
            event.accept()
        else:
            super().keyPressEvent(event)


class EnhancedSearchBar(QWidget):
    """增强版搜索栏"""

    search_requested = pyqtSignal(str)
    advanced_search_requested = pyqtSignal()

    def __init__(self, account_id: Optional[int] = None, parent=None):
        super().__init__(parent)

        self.account_id = account_id
        self.suggestion_popup = SearchSuggestionPopup(self)
        self.suggestion_timer = QTimer(self)
        self.suggestion_timer.setSingleShot(True)
        self.suggestion_timer.timeout.connect(self._update_suggestions)

        self._setup_ui()
        self._connect_signals()

    def _setup_ui(self):
        """设置UI"""
        # 主布局
        main_layout = QHBoxLayout()
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(4)

        # 搜索输入框
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("搜索邮件、附件、联系人...")
        self.search_input.setMinimumWidth(200)
        self.search_input.setClearButtonEnabled(True)

        # 设置语法高亮
        try:
            # 尝试为QLineEdit设置语法高亮
            # QLineEdit没有document()方法，所以需要使用自定义高亮
            # 暂时禁用语法高亮，因为QLineEdit不支持QSyntaxHighlighter
            self.highlighter = None
        except AttributeError:
            # 如果失败，禁用语法高亮
            self.highlighter = None

        # 搜索按钮
        self.search_button = QPushButton("🔍")
        self.search_button.setFixedSize(32, 32)
        self.search_button.setToolTip("开始搜索")

        # 高级搜索按钮
        self.advanced_button = QPushButton("设置")
        self.advanced_button.setFixedSize(32, 32)
        self.advanced_button.setToolTip("高级搜索")

        # 添加到布局
        main_layout.addWidget(self.search_input, 1)
        main_layout.addWidget(self.search_button)
        main_layout.addWidget(self.advanced_button)

        self.setLayout(main_layout)

        # 样式
        self.search_input.setStyleSheet("""
            QLineEdit {
                background-color: white;
                border: 1px solid #c0c0c0;
                border-radius: 4px;
                padding: 6px 12px;
                font-size: 14px;
            }
            QLineEdit:focus {
                border-color: #0078d4;
                background-color: white;
            }
        """)

        self.search_button.setStyleSheet("""
            QPushButton {
                background-color: #0078d4;
                border: 1px solid #0078d4;
                border-radius: 4px;
                color: white;
            }
            QPushButton:hover {
                background-color: #106ebe;
            }
            QPushButton:pressed {
                background-color: #005a9e;
            }
        """)

        self.advanced_button.setStyleSheet("""
            QPushButton {
                background-color: #f0f0f0;
                border: 1px solid #c0c0c0;
                border-radius: 4px;
            }
            QPushButton:hover {
                background-color: #e0e0e0;
            }
            QPushButton:pressed {
                background-color: #d0d0d0;
            }
        """)

    def _connect_signals(self):
        """连接信号"""
        self.search_button.clicked.connect(self._perform_search)
        self.advanced_button.clicked.connect(self.advanced_search_requested.emit)
        self.search_input.returnPressed.connect(self._perform_search)

        # 输入变化时更新建议
        self.search_input.textChanged.connect(self._on_input_changed)

        # 建议选择
        self.suggestion_popup.suggestion_selected.connect(self._on_suggestion_selected)

    def _on_input_changed(self, text):
        """输入变化事件"""
        if text.strip():
            self.suggestion_timer.start(300)  # 300ms延迟
        else:
            self.suggestion_popup.hide()

    def _update_suggestions(self):
        """更新搜索建议"""
        query = self.search_input.text().strip()
        if not query or len(query) < 2:
            self.suggestion_popup.hide()
            return

        # 获取搜索建议
        suggestions = EnhancedSearchEngine.search_suggestions(
            query=query, account_id=self.account_id, limit=10
        )

        if suggestions:
            input_rect = self.search_input.geometry()
            global_rect = self.search_input.mapToGlobal(input_rect.topLeft())
            self.suggestion_popup.show_suggestions(suggestions, global_rect)
        else:
            self.suggestion_popup.hide()

    def _on_suggestion_selected(self, value):
        """建议选择事件"""
        # 插入或替换当前查询
        current_text = self.search_input.text()

        # 查找最后一个空格位置
        last_space = current_text.rfind(" ", 0)
        if last_space == -1:
            self.search_input.setText(value)
        else:
            self.search_input.setText(current_text[: last_space + 1] + value)

        # 搜索
        self._perform_search()

    def _perform_search(self):
        """执行搜索"""
        query = self.search_input.text().strip()
        if query:
            self.search_requested.emit(query)
            # 保存搜索历史
            EnhancedSearchEngine.save_search_history(
                query=query, account_id=self.account_id
            )

        # 隐藏建议
        self.suggestion_popup.hide()

    def set_account_id(self, account_id: int):
        """设置账户ID"""
        self.account_id = account_id

    def focus_input(self):
        """聚焦到输入框"""
        self.search_input.setFocus()


class SearchHistoryWidget(QWidget):
    """搜索历史组件"""

    history_selected = pyqtSignal(str)

    def __init__(self, account_id: Optional[int] = None, parent=None):
        super().__init__(parent)

        self.account_id = account_id

        self._setup_ui()
        self._load_history()

    def _setup_ui(self):
        """设置UI"""
        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)

        # 标题
        title_label = QLabel("搜索历史")
        title_label.setStyleSheet("font-weight: bold; margin-bottom: 8px;")
        layout.addWidget(title_label)

        # 历史列表
        self.history_list = QTreeWidget()
        self.history_list.setHeaderHidden(True)
        self.history_list.setColumnCount(3)
        layout.addWidget(self.history_list)

        # 右键菜单
        self.history_list.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.history_list.customContextMenuRequested.connect(self._show_context_menu)

        # 连接点击事件
        self.history_list.itemClicked.connect(self._on_item_clicked)

        # 清除按钮
        self.clear_button = QPushButton("清除历史")
        self.clear_button.clicked.connect(self._clear_history)
        layout.addWidget(self.clear_button)

        self.setLayout(layout)

        # 样式
        self.history_list.setStyleSheet("""
            QTreeWidget {
                background-color: white;
                border: 1px solid #c0c0c0;
                border-radius: 4px;
            }
            QTreeWidget::item {
                padding: 4px;
                border-bottom: 1px solid #f0f0f0;
            }
            QTreeWidget::item:selected {
                background-color: #e6f3ff;
            }
            QTreeWidget::item:hover {
                background-color: #f5f5f5;
            }
        """)

    def _load_history(self):
        """加载搜索历史"""
        self.history_list.clear()

        history = EnhancedSearchEngine.get_search_history(
            account_id=self.account_id, limit=20
        )

        for item in history:
            history_item = QTreeWidgetItem()

            # 查询文本
            query_text = QTreeWidgetItem()
            query_text.setText(0, item["query"])

            # 结果数量和日期
            info_item = QTreeWidgetItem()
            info_item.setText(0, f"{item['count']} 个结果")
            info_item.setText(1, item["time"])

            # 设置数据
            history_item.setData(0, Qt.ItemDataRole.UserRole, item["query"])

            # 添加到列表
            self.history_list.addTopLevelItem(history_item)

    def _on_item_clicked(self, item, column):
        """历史项点击事件"""
        query = item.data(0, Qt.ItemDataRole.UserRole)
        if query:
            self.history_selected.emit(query)

    def _show_context_menu(self, position):
        """显示右键菜单"""
        item = self.history_list.itemAt(position)
        if not item:
            return

        menu = QMenu()

        # 从历史中删除
        delete_action = menu.addAction("删除此历史")
        delete_action.triggered.connect(lambda: self._delete_history_item(item))

        menu.exec(self.history_list.mapToGlobal(position))

    def _delete_history_item(self, item):
        """删除历史项"""
        query = item.data(0, Qt.ItemDataRole.UserRole)
        if query:
            # TODO: 实现从数据库删除记录
            pass

        # 刷新列表
        self._load_history()

    def _clear_history(self):
        """清除所有历史记录"""
        # TODO: 实现清除所有历史记录
        self._load_history()

    def refresh_history(self):
        """刷新历史记录"""
        self._load_history()


class EnhancedSearchResultsWidget(QWidget):
    """增强版搜索结果组件"""

    def __init__(self, parent=None):
        super().__init__(parent)

        self.current_query = ""
        self.search_results = []

        self._setup_ui()

    def _setup_ui(self):
        """设置UI"""
        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)

        # 结果统计
        self.stats_label = QLabel("")
        self.stats_label.setStyleSheet("color: #666; margin-bottom: 8px;")
        layout.addWidget(self.stats_label)

        # 搜索结果列表
        self.results_list = QTreeWidget()
        self.results_list.setHeaderLabels(["发件人", "主题", "摘要", "日期"])
        layout.addWidget(self.results_list)

        self.setLayout(layout)

    def display_search_results(self, query: str, results: List[Email]):
        """显示搜索结果"""
        self.current_query = query
        self.search_results = results

        # 更新统计
        self.stats_label.setText(f"找到 {len(results)} 个结果")

        # 清空列表
        self.results_list.clear()

        # 添加结果项
        for email in results:
            item = QTreeWidgetItem()

            # 发件人
            if hasattr(email, "sender_name"):
                sender_text = f"{email.sender_name} <{email.sender_addr}>"
            else:
                sender_text = email.sender_addr

            # 主题（带搜索片段）
            subject = email.subject or "（无主题）"

            # 生成摘要片段
            snippets = EnhancedSearchEngine.generate_search_snippets(
                email=email, query=query, max_snippets=2, snippet_length=100
            )
            snippet_text = " | ".join(snippets) if snippets else ""

            # 格式化日期
            date_text = email.date.strftime("%Y-%m-%d %H:%M") if email.date else ""

            # 设置项数据
            item.setText(0, sender_text)
            item.setText(1, subject)
            item.setText(2, snippet_text)
            item.setText(3, date_text)

            # 添加附件标识
            if hasattr(email, "has_attachment") and email.has_attachment:
                item.setText(0, f"📎 {sender_text}")

            # 未读邮件特殊样式
            if email.is_read == 0:
                bold_font = item.font(0)
                bold_font.setBold(True)
                for i in range(4):
                    item.setFont(i, bold_font)

            self.results_list.addTopLevelItem(item)

        # 调整列宽
        self.results_list.resizeColumnToContents(0)
        self.results_list.resizeColumnToContents(1)
        self.results_list.resizeColumnToContents(2)
        self.results_list.resizeColumnToContents(3)

    def clear_results(self):
        """清除结果"""
        self.current_query = ""
        self.search_results = []
        self.stats_label.setText("")
        self.results_list.clear()


class AdvancedSearchDialog(QWidget):
    """高级搜索对话框"""

    search_requested = pyqtSignal(str)

    def __init__(self, account_id: Optional[int] = None, parent=None):
        super().__init__(parent, Qt.WindowType.Window)

        self.account_id = account_id

        self.setWindowTitle("高级搜索")
        self.setMinimumSize(500, 400)

        self._setup_ui()

    def _setup_ui(self):
        """设置UI"""
        main_layout = QVBoxLayout()

        # 搜索词
        search_label = QLabel("搜索词:")
        self.search_input = QLineEdit()

        # 过滤器设置
        filters_label = QLabel("过滤器:")

        # 发件人
        from_label = QLabel("发件人:")
        self.from_input = QLineEdit()
        self.from_input.setPlaceholderText("example@domain.com")

        # 收件人
        to_label = QLabel("收件人:")
        self.to_input = QLineEdit()
        self.to_input.setPlaceholderText("example@domain.com")

        # 主题
        subject_label = QLabel("主题:")
        self.subject_input = QLineEdit()

        # 状态过滤器
        status_box = QFrame()
        status_layout = QVBoxLayout()

        self.unread_checkbox = QCheckBox("仅显示未读邮件")
        self.flagged_checkbox = QCheckBox("仅显示已标记邮件")
        self.attachments_checkbox = QCheckBox("仅显示带附件邮件")

        status_layout.addWidget(self.unread_checkbox)
        status_layout.addWidget(self.flagged_checkbox)
        status_layout.addWidget(self.attachments_checkbox)
        status_box.setLayout(status_layout)

        # 日期范围
        date_box = QFrame()
        date_layout = QHBoxLayout()

        self.start_date_input = QDateEdit()
        self.start_date_input.setDisplayFormat("yyyy-MM-dd")
        self.start_date_input.setCalendarPopup(True)

        self.end_date_input = QDateEdit()
        self.end_date_input.setDisplayFormat("yyyy-MM-dd")
        self.end_date_input.setCalendarPopup(True)
        self.end_date_input.setDate(QDate.currentDate())

        date_label = QLabel("至")

        date_layout.addWidget(QLabel("从"))
        date_layout.addWidget(self.start_date_input)
        date_layout.addWidget(date_label)
        date_layout.addWidget(self.end_date_input)
        date_box.setLayout(date_layout)

        # 按钮
        button_layout = QHBoxLayout()

        self.search_button = QPushButton("搜索")
        self.search_button.clicked.connect(self._perform_search)

        self.cancel_button = QPushButton("取消")
        self.cancel_button.clicked.connect(self.close)

        button_layout.addStretch()
        button_layout.addWidget(self.search_button)
        button_layout.addWidget(self.cancel_button)

        # 添加到主布局
        main_layout.addWidget(search_label)
        main_layout.addWidget(self.search_input)
        main_layout.addSpacing(10)

        main_layout.addWidget(filters_label)
        main_layout.addWidget(from_label)
        main_layout.addWidget(self.from_input)
        main_layout.addWidget(to_label)
        main_layout.addWidget(self.to_input)
        main_layout.addWidget(subject_label)
        main_layout.addWidget(self.subject_input)
        main_layout.addSpacing(10)

        main_layout.addWidget(status_box)
        main_layout.addSpacing(10)

        main_layout.addWidget(QLabel("日期范围:"))
        main_layout.addWidget(date_box)
        main_layout.addSpacing(20)

        main_layout.addLayout(button_layout)

        self.setLayout(main_layout)

    def _perform_search(self):
        """执行高级搜索"""
        search_parts = []

        # 基本搜索词
        if self.search_input.text().strip():
            search_parts.append(f'"{self.search_input.text().strip()}"')

        # 发件人过滤器
        if self.from_input.text().strip():
            search_parts.append(f"from:{self.from_input.text().strip()}")

        # 收件人过滤器
        if self.to_input.text().strip():
            search_parts.append(f"to:{self.to_input.text().strip()}")

        # 主题过滤器
        if self.subject_input.text().strip():
            search_parts.append(f'subject:"{self.subject_input.text().strip()}"')

        # 状态过滤器
        if self.unread_checkbox.isChecked():
            search_parts.append("is:unread")
        if self.flagged_checkbox.isChecked():
            search_parts.append("is:flagged")
        if self.attachments_checkbox.isChecked():
            search_parts.append("has:attachment")

        # 日期范围
        if self.start_date_input.date().isValid():
            start_date = self.start_date_input.date().toString("yyyy-MM-dd")
            search_parts.append(f"after:{start_date}")
        if self.end_date_input.date().isValid():
            end_date = self.end_date_input.date().toString("yyyy-MM-dd")
            search_parts.append(f"before:{end_date}")

        # 组合查询
        query = " ".join(search_parts)

        if query:
            self.search_requested.emit(query)
            self.close()


# 导入缺失的组件
try:
    from PyQt6.QtWidgets import QCheckBox, QDateEdit
    from PyQt6.QtCore import QDate
except ImportError:
    # 创建简单的占位符类
    class QCheckBox:
        pass

    class QDateEdit:
        pass

    class QDate:
        pass


class SearchSnippetLabel(QLabel):
    """搜索摘要标签组件，高亮显示匹配文本"""

    def __init__(self, text="", query="", parent=None):
        super().__init__(parent)
        self.query = query.lower()
        self._original_text = text

        # 设置格式
        self.setTextFormat(Qt.TextFormat.RichText)
        self.setWordWrap(True)

        self._update_display()

    def _update_display(self):
        """更新显示内容，高亮匹配文本"""
        if not self.query or not self._original_text:
            self.setText(self._original_text)
            return

        text_lower = self._original_text.lower()
        highlighted_text = self._original_text

        # 查找并高亮所有匹配
        pos = 0
        while True:
            pos = text_lower.find(self.query, pos)
            if pos == -1:
                break

            # 获取原始文本片段
            start_pos = pos
            end_pos = pos + len(self.query)
            match_text = self._original_text[start_pos:end_pos]

            # 添加高亮标记
            highlighted_text = (
                highlighted_text[:start_pos]
                + f'<span style="background-color: #ffff00; color: #000000;">{match_text}</span>'
                + highlighted_text[end_pos:]
            )

            # 更新位置（考虑已添加的HTML标记）
            pos = (
                end_pos
                + len(
                    '<span style="background-color: #ffff00; color: #000000;"></span>'
                )
                - len(match_text)
            )

        self.setText(highlighted_text)

    def set_text_and_query(self, text: str, query: str):
        """设置文本和查询"""
        self._original_text = text
        self.query = query.lower()
        self._update_display()

    def set_query(self, query: str):
        """设置查询"""
        self.query = query.lower()
        self._update_display()
