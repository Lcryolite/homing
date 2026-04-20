from __future__ import annotations

from datetime import datetime

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QSplitter,
    QLabel,
    QPushButton,
    QListWidget,
    QListWidgetItem,
    QCheckBox,
    QDialog,
    QFormLayout,
    QLineEdit,
    QTextEdit,
    QComboBox,
    QDateEdit,
    QMessageBox,
    QFrame,
    QSizePolicy,
)
from PyQt6.QtGui import QPixmap, QPainter, QColor, QFont

from openemail.models.todo import Todo

PRIORITY_COLORS = {
    "urgent": "#f38ba8",
    "high": "#fab387",
    "normal": "#89b4fa",
    "low": "#a6adc8",
}

PRIORITY_ORDER = {"urgent": 0, "high": 1, "normal": 2, "low": 3}

STATUS_LABELS = {
    "pending": "待办",
    "in_progress": "进行中",
    "completed": "已完成",
    "cancelled": "已取消",
}

VIEW_TITLES = {
    "today": "今天的待办",
    "week": "本周待办",
    "all": "全部待办",
}

CATPPUCCIN_BASE = "#1e1e2e"
CATPPUCCIN_SURFACE0 = "#313244"
CATPPUCCIN_SURFACE1 = "#45475a"
CATPPUCCIN_SURFACE2 = "#585b70"
CATPPUCCIN_OVERLAY0 = "#6c7086"
CATPPUCCIN_TEXT = "#cdd6f4"
CATPPUCCIN_SUBTEXT = "#a6adc8"
CATPPUCCIN_BLUE = "#89b4fa"
CATPPUCCIN_GREEN = "#a6e3a1"
CATPPUCCIN_RED = "#f38ba8"
CATPPUCCIN_YELLOW = "#f9e2af"
CATPPUCCIN_MAUVE = "#cba6f7"
CATPPUCCIN_PEACH = "#fab387"
CATPPUCCIN_TEAL = "#94e2d5"


def _make_priority_dot(color: str, size: int = 12) -> QPixmap:
    pixmap = QPixmap(size, size)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.setBrush(QColor(color))
    painter.setPen(Qt.PenStyle.NoPen)
    painter.drawEllipse(1, 1, size - 2, size - 2)
    painter.end()
    return pixmap


class TodoEditDialog(QDialog):
    todo_saved = pyqtSignal(int)

    def __init__(self, parent=None, todo: Todo | None = None):
        super().__init__(parent)
        self._todo = todo or Todo()
        self._is_new = todo is None
        self.setWindowTitle("新建任务" if self._is_new else "编辑任务")
        self.setMinimumSize(480, 520)
        self._setup_ui()
        self._load_data()

    def _setup_ui(self):
        self.setStyleSheet(f"""
            QDialog {{
                background: {CATPPUCCIN_BASE};
                color: {CATPPUCCIN_TEXT};
            }}
            QLabel {{
                color: {CATPPUCCIN_TEXT};
                font-size: 13px;
            }}
            QLineEdit, QTextEdit, QComboBox, QDateEdit {{
                background: {CATPPUCCIN_SURFACE0};
                color: {CATPPUCCIN_TEXT};
                border: 1px solid {CATPPUCCIN_SURFACE1};
                border-radius: 6px;
                padding: 8px 12px;
                font-size: 13px;
            }}
            QLineEdit:focus, QTextEdit:focus, QComboBox:focus, QDateEdit:focus {{
                border-color: {CATPPUCCIN_BLUE};
            }}
            QComboBox::drop-down {{
                border: none;
                padding-right: 8px;
            }}
            QComboBox QAbstractItemView {{
                background: {CATPPUCCIN_SURFACE0};
                color: {CATPPUCCIN_TEXT};
                border: 1px solid {CATPPUCCIN_SURFACE1};
                selection-background-color: {CATPPUCCIN_SURFACE1};
            }}
        """)

        layout = QVBoxLayout(self)
        layout.setSpacing(16)
        layout.setContentsMargins(24, 24, 24, 24)

        title_label = QLabel("任务信息")
        title_label.setFont(QFont("", 16, QFont.Weight.Bold))
        title_label.setStyleSheet(f"color: {CATPPUCCIN_BLUE}; margin-bottom: 4px;")
        layout.addWidget(title_label)

        form = QFormLayout()
        form.setSpacing(12)
        form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)

        self.title_edit = QLineEdit()
        self.title_edit.setPlaceholderText("任务标题")
        form.addRow("标题:", self.title_edit)

        self.desc_edit = QTextEdit()
        self.desc_edit.setPlaceholderText("任务描述（可选）")
        self.desc_edit.setMaximumHeight(100)
        self.desc_edit.setAcceptRichText(False)
        form.addRow("描述:", self.desc_edit)

        self.priority_combo = QComboBox()
        self.priority_combo.addItem("紧急", "urgent")
        self.priority_combo.addItem("高", "high")
        self.priority_combo.addItem("普通", "normal")
        self.priority_combo.addItem("低", "low")
        form.addRow("优先级:", self.priority_combo)

        self.due_date_edit = QDateEdit()
        self.due_date_edit.setCalendarPopup(True)
        self.due_date_edit.setDisplayFormat("yyyy-MM-dd")
        self.due_date_edit.setDate(datetime.now().date())
        self.due_date_edit.setSpecialValueText("无截止日期")
        form.addRow("截止日期:", self.due_date_edit)

        self.no_due_date_check = QCheckBox("无截止日期")
        self.no_due_date_check.setStyleSheet(
            f"color: {CATPPUCCIN_SUBTEXT}; font-size: 13px;"
        )
        self.no_due_date_check.toggled.connect(self._toggle_due_date)
        form.addRow("", self.no_due_date_check)

        self.tags_edit = QLineEdit()
        self.tags_edit.setPlaceholderText("用逗号分隔标签，例如：工作,重要")
        form.addRow("标签:", self.tags_edit)

        layout.addLayout(form)

        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(12)

        self.save_btn = QPushButton("保存")
        self.save_btn.setMinimumWidth(100)
        self.save_btn.setStyleSheet(f"""
            QPushButton {{
                background: {CATPPUCCIN_BLUE};
                color: {CATPPUCCIN_BASE};
                border: none;
                border-radius: 6px;
                padding: 8px 20px;
                font-weight: bold;
                font-size: 13px;
            }}
            QPushButton:hover {{
                background: {CATPPUCCIN_MAUVE};
            }}
        """)
        self.save_btn.clicked.connect(self._save)
        btn_layout.addWidget(self.save_btn)

        cancel_btn = QPushButton("取消")
        cancel_btn.setMinimumWidth(80)
        cancel_btn.setStyleSheet(f"""
            QPushButton {{
                background: {CATPPUCCIN_SURFACE1};
                color: {CATPPUCCIN_TEXT};
                border: none;
                border-radius: 6px;
                padding: 8px 20px;
                font-size: 13px;
            }}
            QPushButton:hover {{
                background: {CATPPUCCIN_SURFACE2};
            }}
        """)
        cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(cancel_btn)

        btn_layout.addStretch()
        layout.addLayout(btn_layout)

    def _toggle_due_date(self, checked: bool):
        self.due_date_edit.setEnabled(not checked)

    def _load_data(self):
        if not self._is_new:
            self.title_edit.setText(self._todo.title)
            self.desc_edit.setText(self._todo.description)
            priority_map = {"urgent": 0, "high": 1, "normal": 2, "low": 3}
            idx = priority_map.get(self._todo.priority, 2)
            self.priority_combo.setCurrentIndex(idx)
            if self._todo.due_date:
                try:
                    dt = datetime.fromisoformat(
                        self._todo.due_date.replace("Z", "+00:00")
                    )
                    self.due_date_edit.setDate(dt.date())
                except (ValueError, TypeError):
                    pass
            else:
                self.no_due_date_check.setChecked(True)
            self.tags_edit.setText(self._todo.tags)

    def _save(self):
        title = self.title_edit.text().strip()
        if not title:
            QMessageBox.warning(self, "验证错误", "任务标题不能为空")
            self.title_edit.setFocus()
            return

        self._todo.title = title
        self._todo.description = self.desc_edit.toPlainText().strip()
        self._todo.priority = self.priority_combo.currentData()
        if self.no_due_date_check.isChecked():
            self._todo.due_date = ""
        else:
            self._todo.due_date = self.due_date_edit.date().toString("yyyy-MM-dd")
        self._todo.tags = self.tags_edit.text().strip()

        try:
            todo_id = self._todo.save()
            self.todo_saved.emit(todo_id)
            self.accept()
        except Exception as e:
            QMessageBox.critical(self, "保存失败", f"保存任务时发生错误:\n{str(e)}")


class TodoItemWidget(QWidget):
    clicked = pyqtSignal(int)
    completion_toggled = pyqtSignal(int, bool)

    def __init__(self, todo: Todo, parent=None):
        super().__init__(parent)
        self._todo = todo
        self._setup_ui()

    def _setup_ui(self):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 6, 8, 6)
        layout.setSpacing(10)

        self.checkbox = QCheckBox()
        self.checkbox.setChecked(self._todo.status == "completed")
        self.checkbox.setStyleSheet(f"""
            QCheckBox::indicator {{
                width: 18px;
                height: 18px;
                border-radius: 9px;
                border: 2px solid {CATPPUCCIN_SURFACE2};
            }}
            QCheckBox::indicator:checked {{
                background: {CATPPUCCIN_GREEN};
                border-color: {CATPPUCCIN_GREEN};
            }}
            QCheckBox::indicator:unchecked {{
                background: transparent;
            }}
        """)
        self.checkbox.toggled.connect(self._on_toggled)
        layout.addWidget(self.checkbox)

        priority_color = PRIORITY_COLORS.get(self._todo.priority, CATPPUCCIN_SURFACE2)
        dot_label = QLabel()
        dot_label.setPixmap(_make_priority_dot(priority_color, 14))
        dot_label.setFixedSize(14, 14)
        layout.addWidget(dot_label)

        title_label = QLabel(self._todo.title)
        title_label.setStyleSheet(f"""
            QLabel {{
                color: {CATPPUCCIN_TEXT if self._todo.status != "completed" else CATPPUCCIN_OVERLAY0};
                font-size: 13px;
                {"text-decoration: line-through;" if self._todo.status == "completed" else ""}
            }}
        """)
        title_label.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred
        )
        layout.addWidget(title_label, 1)

        if self._todo.due_date:
            due_text = self._format_due_date(self._todo.due_date)
            due_color = CATPPUCCIN_RED if self._todo.is_overdue else CATPPUCCIN_SUBTEXT
            due_label = QLabel(due_text)
            due_label.setStyleSheet(f"color: {due_color}; font-size: 11px;")
            layout.addWidget(due_label)

        if self._todo.tags:
            tag_parts = [t.strip() for t in self._todo.tags.split(",") if t.strip()]
            if tag_parts:
                tag_text = " ".join(f"#{t}" for t in tag_parts[:3])
                tag_label = QLabel(tag_text)
                tag_label.setStyleSheet(f"color: {CATPPUCCIN_TEAL}; font-size: 11px;")
                layout.addWidget(tag_label)

    def _format_due_date(self, due_date: str) -> str:
        try:
            dt = datetime.fromisoformat(due_date.replace("Z", "+00:00"))
            return dt.strftime("%m/%d")
        except (ValueError, TypeError):
            return due_date

    def _on_toggled(self, checked: bool):
        self.completion_toggled.emit(self._todo.id, checked)

    def mousePressEvent(self, event):
        self.clicked.emit(self._todo.id)
        super().mousePressEvent(event)


class TodoDetailWidget(QWidget):
    edit_requested = pyqtSignal(int)
    delete_requested = pyqtSignal(int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._todo: Todo | None = None
        self._setup_ui()

    def _setup_ui(self):
        self.setStyleSheet(f"background: {CATPPUCCIN_BASE};")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(12)

        self.empty_label = QLabel("选择一个任务查看详情")
        self.empty_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.empty_label.setStyleSheet(f"""
            color: {CATPPUCCIN_OVERLAY0};
            font-size: 14px;
        """)
        layout.addWidget(self.empty_label)

        self.detail_frame = QFrame()
        self.detail_frame.setStyleSheet(f"""
            QFrame {{
                background: {CATPPUCCIN_SURFACE0};
                border-radius: 8px;
                padding: 4px;
            }}
        """)
        detail_layout = QVBoxLayout(self.detail_frame)
        detail_layout.setSpacing(10)

        self.title_label = QLabel()
        self.title_label.setWordWrap(True)
        self.title_label.setFont(QFont("", 16, QFont.Weight.Bold))
        self.title_label.setStyleSheet(f"color: {CATPPUCCIN_TEXT}; border: none;")
        detail_layout.addWidget(self.title_label)

        sep1 = QFrame()
        sep1.setFrameShape(QFrame.Shape.HLine)
        sep1.setStyleSheet(
            f"background: {CATPPUCCIN_SURFACE1}; border: none; max-height: 1px;"
        )
        detail_layout.addWidget(sep1)

        info_layout = QFormLayout()
        info_layout.setSpacing(8)
        info_layout.setLabelAlignment(Qt.AlignmentFlag.AlignRight)

        self.status_label = QLabel()
        self.priority_label = QLabel()
        self.due_label = QLabel()
        self.tags_label = QLabel()
        self.created_label = QLabel()
        self.updated_label = QLabel()

        for lbl in (
            self.status_label,
            self.priority_label,
            self.due_label,
            self.tags_label,
            self.created_label,
            self.updated_label,
        ):
            lbl.setStyleSheet(
                f"color: {CATPPUCCIN_TEXT}; font-size: 13px; border: none;"
            )

        info_layout.addRow(self._make_field_label("状态:"), self.status_label)
        info_layout.addRow(self._make_field_label("优先级:"), self.priority_label)
        info_layout.addRow(self._make_field_label("截止日期:"), self.due_label)
        info_layout.addRow(self._make_field_label("标签:"), self.tags_label)
        info_layout.addRow(self._make_field_label("创建时间:"), self.created_label)
        info_layout.addRow(self._make_field_label("更新时间:"), self.updated_label)

        detail_layout.addLayout(info_layout)

        sep2 = QFrame()
        sep2.setFrameShape(QFrame.Shape.HLine)
        sep2.setStyleSheet(
            f"background: {CATPPUCCIN_SURFACE1}; border: none; max-height: 1px;"
        )
        detail_layout.addWidget(sep2)

        self.desc_title = QLabel("描述")
        self.desc_title.setStyleSheet(
            f"color: {CATPPUCCIN_OVERLAY0}; font-size: 12px; font-weight: bold; border: none;"
        )
        detail_layout.addWidget(self.desc_title)

        self.desc_label = QLabel()
        self.desc_label.setWordWrap(True)
        self.desc_label.setStyleSheet(
            f"color: {CATPPUCCIN_SUBTEXT}; font-size: 13px; border: none;"
        )
        detail_layout.addWidget(self.desc_label)

        detail_layout.addStretch()

        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(12)

        self.edit_btn = QPushButton("编辑")
        self.edit_btn.setMinimumWidth(90)
        self.edit_btn.setStyleSheet(f"""
            QPushButton {{
                background: {CATPPUCCIN_BLUE};
                color: {CATPPUCCIN_BASE};
                border: none;
                border-radius: 6px;
                padding: 8px 16px;
                font-weight: bold;
                font-size: 13px;
            }}
            QPushButton:hover {{
                background: {CATPPUCCIN_MAUVE};
            }}
        """)
        self.edit_btn.clicked.connect(
            lambda: self.edit_requested.emit(self._todo.id) if self._todo else None
        )
        btn_layout.addWidget(self.edit_btn)

        self.delete_btn = QPushButton("删除")
        self.delete_btn.setMinimumWidth(90)
        self.delete_btn.setStyleSheet(f"""
            QPushButton {{
                background: {CATPPUCCIN_RED};
                color: {CATPPUCCIN_BASE};
                border: none;
                border-radius: 6px;
                padding: 8px 16px;
                font-weight: bold;
                font-size: 13px;
            }}
            QPushButton:hover {{
                background: {CATPPUCCIN_PEACH};
            }}
        """)
        self.delete_btn.clicked.connect(
            lambda: self.delete_requested.emit(self._todo.id) if self._todo else None
        )
        btn_layout.addWidget(self.delete_btn)

        btn_layout.addStretch()
        detail_layout.addLayout(btn_layout)

        self.detail_frame.hide()
        layout.addWidget(self.detail_frame)

    def _make_field_label(self, text: str) -> QLabel:
        lbl = QLabel(text)
        lbl.setStyleSheet(
            f"color: {CATPPUCCIN_OVERLAY0}; font-size: 13px; border: none;"
        )
        return lbl

    def load_todo(self, todo: Todo):
        self._todo = todo
        self.empty_label.hide()
        self.detail_frame.show()

        self.title_label.setText(todo.title)

        status_text = STATUS_LABELS.get(todo.status, todo.status)
        status_color = {
            "pending": CATPPUCCIN_YELLOW,
            "in_progress": CATPPUCCIN_BLUE,
            "completed": CATPPUCCIN_GREEN,
            "cancelled": CATPPUCCIN_OVERLAY0,
        }.get(todo.status, CATPPUCCIN_TEXT)
        self.status_label.setText(status_text)
        self.status_label.setStyleSheet(
            f"color: {status_color}; font-size: 13px; border: none;"
        )

        priority_color = PRIORITY_COLORS.get(todo.priority, CATPPUCCIN_SURFACE2)
        self.priority_label.setText(todo.display_priority)
        self.priority_label.setStyleSheet(
            f"color: {priority_color}; font-size: 13px; font-weight: bold; border: none;"
        )

        if todo.due_date:
            try:
                dt = datetime.fromisoformat(todo.due_date.replace("Z", "+00:00"))
                due_text = dt.strftime("%Y-%m-%d")
            except (ValueError, TypeError):
                due_text = todo.due_date
            due_color = CATPPUCCIN_RED if todo.is_overdue else CATPPUCCIN_TEXT
            self.due_label.setText(due_text)
            self.due_label.setStyleSheet(
                f"color: {due_color}; font-size: 13px; border: none;"
            )
        else:
            self.due_label.setText("无")
            self.due_label.setStyleSheet(
                f"color: {CATPPUCCIN_OVERLAY0}; font-size: 13px; border: none;"
            )

        self.tags_label.setText(todo.tags if todo.tags else "无")

        self.created_label.setText(self._format_datetime(todo.created_at))
        self.updated_label.setText(self._format_datetime(todo.updated_at))

        self.desc_label.setText(todo.description if todo.description else "无描述")

    def clear(self):
        self._todo = None
        self.detail_frame.hide()
        self.empty_label.show()

    def _format_datetime(self, dt_str: str) -> str:
        if not dt_str:
            return "—"
        try:
            dt = datetime.fromisoformat(dt_str.replace("Z", "+00:00"))
            return dt.strftime("%Y-%m-%d %H:%M")
        except (ValueError, TypeError):
            return dt_str


class TodoPageWidget(QWidget):
    todo_created = pyqtSignal(int)

    def __init__(self, view_mode: str = "all", parent=None):
        super().__init__(parent)
        self._view_mode = view_mode
        self._filter_status: str | None = None
        self._selected_todo_id: int | None = None
        self._setup_ui()
        self._load_todos()

    def _setup_ui(self):
        self.setStyleSheet(f"background: {CATPPUCCIN_BASE};")

        main_layout = QVBoxLayout(self)
        main_layout.setSpacing(0)
        main_layout.setContentsMargins(0, 0, 0, 0)

        header = QFrame()
        header.setStyleSheet(f"""
            QFrame {{
                background: {CATPPUCCIN_SURFACE0};
                border-bottom: 1px solid {CATPPUCCIN_SURFACE1};
            }}
        """)
        header_layout = QVBoxLayout(header)
        header_layout.setContentsMargins(16, 12, 16, 12)
        header_layout.setSpacing(8)

        top_row = QHBoxLayout()
        top_row.setSpacing(12)

        title = QLabel(VIEW_TITLES.get(self._view_mode, "全部待办"))
        title.setFont(QFont("", 16, QFont.Weight.Bold))
        title.setStyleSheet(f"color: {CATPPUCCIN_TEXT}; border: none;")
        top_row.addWidget(title)

        top_row.addStretch()

        new_btn = QPushButton("新建任务")
        new_btn.setStyleSheet(f"""
            QPushButton {{
                background: {CATPPUCCIN_BLUE};
                color: {CATPPUCCIN_BASE};
                border: none;
                border-radius: 6px;
                padding: 8px 20px;
                font-weight: bold;
                font-size: 13px;
            }}
            QPushButton:hover {{
                background: {CATPPUCCIN_MAUVE};
            }}
        """)
        new_btn.clicked.connect(self._on_new_todo)
        top_row.addWidget(new_btn)

        header_layout.addLayout(top_row)

        filter_row = QHBoxLayout()
        filter_row.setSpacing(6)

        self._filter_buttons: dict[str, QPushButton] = {}
        filter_configs = [
            ("all", "全部"),
            ("pending", "待办"),
            ("in_progress", "进行中"),
            ("completed", "已完成"),
        ]
        for key, label in filter_configs:
            btn = QPushButton(label)
            btn.setCheckable(True)
            btn.setChecked(key == "all")
            btn.setProperty("filter_key", key)
            btn.setStyleSheet(self._filter_btn_style(key == "all"))
            btn.clicked.connect(lambda checked, k=key: self._on_filter_clicked(k))
            filter_row.addWidget(btn)
            self._filter_buttons[key] = btn

        filter_row.addStretch()
        header_layout.addLayout(filter_row)

        main_layout.addWidget(header)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.setStyleSheet(f"""
            QSplitter::handle {{
                background: {CATPPUCCIN_SURFACE1};
                width: 1px;
            }}
        """)

        list_frame = QFrame()
        list_frame.setStyleSheet(f"background: {CATPPUCCIN_BASE};")
        list_layout = QVBoxLayout(list_frame)
        list_layout.setContentsMargins(0, 0, 0, 0)
        list_layout.setSpacing(0)

        self._todo_list = QListWidget()
        self._todo_list.setStyleSheet(f"""
            QListWidget {{
                background: {CATPPUCCIN_BASE};
                border: none;
                outline: none;
            }}
            QListWidget::item {{
                border-bottom: 1px solid {CATPPUCCIN_SURFACE0};
                padding: 2px 0px;
            }}
            QListWidget::item:selected {{
                background: {CATPPUCCIN_SURFACE0};
            }}
            QListWidget::item:hover {{
                background: {CATPPUCCIN_SURFACE0};
            }}
        """)
        self._todo_list.currentRowChanged.connect(self._on_todo_selected)
        list_layout.addWidget(self._todo_list)

        splitter.addWidget(list_frame)

        self._detail_widget = TodoDetailWidget()
        self._detail_widget.edit_requested.connect(self._on_edit_todo)
        self._detail_widget.delete_requested.connect(self._on_delete_todo)
        splitter.addWidget(self._detail_widget)

        splitter.setSizes([450, 400])
        main_layout.addWidget(splitter, 1)

    def _filter_btn_style(self, active: bool) -> str:
        if active:
            return f"""
                QPushButton {{
                    background: {CATPPUCCIN_BLUE};
                    color: {CATPPUCCIN_BASE};
                    border: none;
                    border-radius: 4px;
                    padding: 5px 14px;
                    font-size: 12px;
                    font-weight: bold;
                }}
                QPushButton:hover {{
                    background: {CATPPUCCIN_MAUVE};
                }}
            """
        return f"""
            QPushButton {{
                background: {CATPPUCCIN_SURFACE1};
                color: {CATPPUCCIN_SUBTEXT};
                border: none;
                border-radius: 4px;
                padding: 5px 14px;
                font-size: 12px;
            }}
            QPushButton:hover {{
                background: {CATPPUCCIN_SURFACE2};
                color: {CATPPUCCIN_TEXT};
            }}
            QPushButton:checked {{
                background: {CATPPUCCIN_BLUE};
                color: {CATPPUCCIN_BASE};
                font-weight: bold;
            }}
        """

    def _on_filter_clicked(self, key: str):
        if key == "all":
            self._filter_status = None
        else:
            self._filter_status = key
        for k, btn in self._filter_buttons.items():
            btn.setChecked(k == key)
            btn.setStyleSheet(self._filter_btn_style(k == key))
        self._load_todos()

    def _load_todos(self):
        self._todo_list.clear()

        if self._view_mode == "today":
            todos = Todo.get_due_today()
        elif self._view_mode == "week":
            todos = Todo.get_due_this_week()
        else:
            todos = Todo.get_all()

        if self._filter_status:
            todos = [t for t in todos if t.status == self._filter_status]

        todos.sort(
            key=lambda t: (PRIORITY_ORDER.get(t.priority, 3), t.due_date or "zzz")
        )

        for todo in todos:
            item = QListWidgetItem(self._todo_list)
            item.setData(Qt.ItemDataRole.UserRole, todo.id)
            widget = TodoItemWidget(todo)
            widget.clicked.connect(self._on_item_clicked)
            widget.completion_toggled.connect(self._on_completion_toggled)
            item.setSizeHint(widget.sizeHint())
            self._todo_list.setItemWidget(item, widget)

    def _on_item_clicked(self, todo_id: int):
        for i in range(self._todo_list.count()):
            item = self._todo_list.item(i)
            if item.data(Qt.ItemDataRole.UserRole) == todo_id:
                self._todo_list.setCurrentItem(item)
                break

    def _on_todo_selected(self, row: int):
        if row < 0:
            self._detail_widget.clear()
            self._selected_todo_id = None
            return
        item = self._todo_list.item(row)
        todo_id = item.data(Qt.ItemDataRole.UserRole)
        self._selected_todo_id = todo_id
        todo = Todo.get_by_id(todo_id)
        if todo:
            self._detail_widget.load_todo(todo)
        else:
            self._detail_widget.clear()

    def _on_completion_toggled(self, todo_id: int, checked: bool):
        todo = Todo.get_by_id(todo_id)
        if todo:
            todo.toggle_complete()
            self._load_todos()
            if self._selected_todo_id == todo_id:
                refreshed = Todo.get_by_id(todo_id)
                if refreshed:
                    self._detail_widget.load_todo(refreshed)

    def _on_new_todo(self):
        dialog = TodoEditDialog(self)
        dialog.todo_saved.connect(self._on_todo_saved)
        dialog.exec()

    def _on_edit_todo(self, todo_id: int):
        todo = Todo.get_by_id(todo_id)
        if todo:
            dialog = TodoEditDialog(self, todo=todo)
            dialog.todo_saved.connect(self._on_todo_saved)
            dialog.exec()

    def _on_delete_todo(self, todo_id: int):
        todo = Todo.get_by_id(todo_id)
        if not todo:
            return
        reply = QMessageBox.question(
            self,
            "删除任务",
            f"确定要删除任务「{todo.title}」吗？",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            todo.delete()
            if self._selected_todo_id == todo_id:
                self._detail_widget.clear()
                self._selected_todo_id = None
            self._load_todos()

    def _on_todo_saved(self, todo_id: int):
        self._load_todos()
        self._selected_todo_id = todo_id
        for i in range(self._todo_list.count()):
            item = self._todo_list.item(i)
            if item.data(Qt.ItemDataRole.UserRole) == todo_id:
                self._todo_list.setCurrentItem(item)
                break
        todo = Todo.get_by_id(todo_id)
        if todo:
            self._detail_widget.load_todo(todo)
        self.todo_created.emit(todo_id)
