from __future__ import annotations

from typing import Optional

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QColor
from PyQt6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QScrollArea,
    QFrame,
    QLabel,
    QPushButton,
    QComboBox,
    QLineEdit,
    QTextEdit,
    QDateEdit,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QMessageBox,
    QColorDialog,
    QSizePolicy,
    QApplication,
)

from openemail.models.project import Project, ProjectColumn, ProjectCard

PRIORITY_COLORS = {
    "urgent": "#f38ba8",
    "high": "#fab387",
    "normal": "#89b4fa",
    "low": "#a6adc8",
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
CATPPUCCIN_MAUVE = "#cba6f7"


class ProjectEditDialog(QDialog):
    def __init__(
        self, project: Optional[Project] = None, parent: Optional[QWidget] = None
    ):
        super().__init__(parent)
        self._project = project
        self._color = project.color if project else "#89b4fa"
        self._is_edit = project is not None
        self.setWindowTitle("编辑项目" if self._is_edit else "新建项目")
        self.setMinimumWidth(400)
        self._setup_ui()
        self._load_project()

    def _setup_ui(self):
        layout = QVBoxLayout(self)

        form = QFormLayout()

        self._name_edit = QLineEdit()
        self._name_edit.setPlaceholderText("项目名称")
        form.addRow("名称:", self._name_edit)

        self._desc_edit = QTextEdit()
        self._desc_edit.setMaximumHeight(80)
        self._desc_edit.setPlaceholderText("项目描述（可选）")
        form.addRow("描述:", self._desc_edit)

        color_row = QHBoxLayout()
        self._color_btn = QPushButton()
        self._color_btn.setFixedSize(32, 32)
        self._color_btn.clicked.connect(self._pick_color)
        self._update_color_btn()
        color_row.addWidget(self._color_btn)
        color_row.addStretch()
        form.addRow("颜色:", color_row)

        layout.addLayout(form)

        btn_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        btn_box.accepted.connect(self._save)
        btn_box.rejected.connect(self.reject)
        layout.addWidget(btn_box)

    def _load_project(self):
        if not self._project:
            return
        self._name_edit.setText(self._project.name)
        self._desc_edit.setPlainText(self._project.description)
        self._color = self._project.color or "#89b4fa"
        self._update_color_btn()

    def _pick_color(self):
        dlg = QColorDialog(QColor(self._color), self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            self._color = dlg.selectedColor().name()
            self._update_color_btn()

    def _update_color_btn(self):
        self._color_btn.setStyleSheet(
            f"background-color: {self._color}; border: 2px solid {CATPPUCCIN_SURFACE1}; border-radius: 6px;"
        )

    def _save(self):
        name = self._name_edit.text().strip()
        if not name:
            QMessageBox.warning(self, "错误", "请输入项目名称")
            return
        if not self._project:
            self._project = Project()
        self._project.name = name
        self._project.description = self._desc_edit.toPlainText().strip()
        self._project.color = self._color
        self._project.save()
        self.accept()

    def get_project(self) -> Optional[Project]:
        return self._project


class ColumnEditDialog(QDialog):
    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.setWindowTitle("新建列")
        self.setMinimumWidth(320)
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)

        form = QFormLayout()
        self._name_edit = QLineEdit()
        self._name_edit.setPlaceholderText("列名称")
        form.addRow("名称:", self._name_edit)
        layout.addLayout(form)

        btn_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        btn_box.accepted.connect(self._save)
        btn_box.rejected.connect(self.reject)
        layout.addWidget(btn_box)

    def _save(self):
        name = self._name_edit.text().strip()
        if not name:
            QMessageBox.warning(self, "错误", "请输入列名称")
            return
        self.accept()

    def get_column_name(self) -> str:
        return self._name_edit.text().strip()


class CardEditDialog(QDialog):
    def __init__(
        self, card: Optional[ProjectCard] = None, parent: Optional[QWidget] = None
    ):
        super().__init__(parent)
        self._card = card
        self._is_edit = card is not None
        self.setWindowTitle("编辑卡片" if self._is_edit else "添加卡片")
        self.setMinimumWidth(420)
        self._setup_ui()
        self._load_card()

    def _setup_ui(self):
        layout = QVBoxLayout(self)

        form = QFormLayout()

        self._title_edit = QLineEdit()
        self._title_edit.setPlaceholderText("卡片标题")
        form.addRow("标题:", self._title_edit)

        self._desc_edit = QTextEdit()
        self._desc_edit.setMaximumHeight(80)
        self._desc_edit.setPlaceholderText("描述（可选）")
        form.addRow("描述:", self._desc_edit)

        self._priority_combo = QComboBox()
        self._priority_combo.addItem("紧急", "urgent")
        self._priority_combo.addItem("高", "high")
        self._priority_combo.addItem("普通", "normal")
        self._priority_combo.addItem("低", "low")
        self._priority_combo.setCurrentIndex(2)
        form.addRow("优先级:", self._priority_combo)

        self._due_date_edit = QDateEdit()
        self._due_date_edit.setCalendarPopup(True)
        self._due_date_edit.setDisplayFormat("yyyy-MM-dd")
        self._due_date_edit.setSpecialValueText("无")
        self._due_date_edit.setDate(self._due_date_edit.minimumDate())
        form.addRow("截止日期:", self._due_date_edit)

        self._assignee_edit = QLineEdit()
        self._assignee_edit.setPlaceholderText("负责人（可选）")
        form.addRow("负责人:", self._assignee_edit)

        self._tags_edit = QLineEdit()
        self._tags_edit.setPlaceholderText("标签，逗号分隔（可选）")
        form.addRow("标签:", self._tags_edit)

        layout.addLayout(form)

        btn_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        btn_box.accepted.connect(self._save)
        btn_box.rejected.connect(self.reject)
        layout.addWidget(btn_box)

    def _load_card(self):
        if not self._card:
            return
        self._title_edit.setText(self._card.title)
        self._desc_edit.setPlainText(self._card.description)
        idx = self._priority_combo.findData(self._card.priority)
        if idx >= 0:
            self._priority_combo.setCurrentIndex(idx)
        if self._card.due_date:
            from datetime import datetime

            try:
                dt = datetime.strptime(self._card.due_date, "%Y-%m-%d")
                self._due_date_edit.setDate(dt)
            except ValueError:
                pass
        self._assignee_edit.setText(self._card.assignee)
        self._tags_edit.setText(self._card.tags)

    def _save(self):
        title = self._title_edit.text().strip()
        if not title:
            QMessageBox.warning(self, "错误", "请输入卡片标题")
            return
        if not self._card:
            self._card = ProjectCard()
        self._card.title = title
        self._card.description = self._desc_edit.toPlainText().strip()
        self._card.priority = self._priority_combo.currentData()
        due = self._due_date_edit.date()
        if due != self._due_date_edit.minimumDate():
            self._card.due_date = due.toString("yyyy-MM-dd")
        else:
            self._card.due_date = ""
        self._card.assignee = self._assignee_edit.text().strip()
        self._card.tags = self._tags_edit.text().strip()
        self.accept()

    def get_card(self) -> Optional[ProjectCard]:
        return self._card


class CardDetailDialog(QDialog):
    def __init__(self, card: ProjectCard, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self._card = card
        self.setWindowTitle(card.title)
        self.setMinimumSize(450, 400)
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)

        form = QFormLayout()

        title_lbl = QLabel(self._card.title)
        title_lbl.setStyleSheet(
            f"font-size: 14px; font-weight: bold; color: {CATPPUCCIN_TEXT};"
        )
        form.addRow("标题:", title_lbl)

        priority_color = PRIORITY_COLORS.get(
            self._card.priority, PRIORITY_COLORS["normal"]
        )
        priority_lbl = QLabel(self._card.priority.upper())
        priority_lbl.setStyleSheet(
            f"background-color: {priority_color}; color: {CATPPUCCIN_BASE}; "
            f"padding: 2px 8px; border-radius: 3px; font-weight: bold; font-size: 11px;"
        )
        form.addRow("优先级:", priority_lbl)

        if self._card.due_date:
            due_lbl = QLabel(self._card.due_date)
            due_lbl.setStyleSheet(f"color: {CATPPUCCIN_SUBTEXT};")
            form.addRow("截止日期:", due_lbl)

        if self._card.assignee:
            assignee_lbl = QLabel(self._card.assignee)
            assignee_lbl.setStyleSheet(f"color: {CATPPUCCIN_TEXT};")
            form.addRow("负责人:", assignee_lbl)

        if self._card.tags:
            tags_widget = QWidget()
            tags_layout = QHBoxLayout(tags_widget)
            tags_layout.setContentsMargins(0, 0, 0, 0)
            tags_layout.setSpacing(4)
            for tag in self._card.tags.split(","):
                tag = tag.strip()
                if tag:
                    tag_lbl = QLabel(tag)
                    tag_lbl.setStyleSheet(
                        f"background-color: {CATPPUCCIN_SURFACE1}; color: {CATPPUCCIN_TEXT}; "
                        f"padding: 1px 6px; border-radius: 3px; font-size: 11px;"
                    )
                    tags_layout.addWidget(tag_lbl)
            tags_layout.addStretch()
            form.addRow("标签:", tags_widget)

        if self._card.description:
            desc_lbl = QLabel(self._card.description)
            desc_lbl.setWordWrap(True)
            desc_lbl.setStyleSheet(f"color: {CATPPUCCIN_SUBTEXT};")
            form.addRow("描述:", desc_lbl)

        if self._card.created_at:
            created_lbl = QLabel(self._card.created_at)
            created_lbl.setStyleSheet(f"color: {CATPPUCCIN_OVERLAY0}; font-size: 11px;")
            form.addRow("创建时间:", created_lbl)

        layout.addLayout(form)

        btn_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        btn_box.rejected.connect(self.reject)
        layout.addWidget(btn_box)


class CardWidget(QFrame):
    clicked = pyqtSignal(int)
    move_up_requested = pyqtSignal(int)
    move_down_requested = pyqtSignal(int)

    def __init__(self, card: ProjectCard, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self._card = card
        self.setProperty("class", "card")
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self._setup_ui()
        self._apply_style()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(4)

        top_row = QHBoxLayout()
        top_row.setSpacing(6)

        title_lbl = QLabel(self._card.title)
        title_lbl.setStyleSheet(
            f"font-weight: bold; color: {CATPPUCCIN_TEXT}; font-size: 13px;"
        )
        title_lbl.setWordWrap(True)
        top_row.addWidget(title_lbl, 1)

        priority_color = PRIORITY_COLORS.get(
            self._card.priority, PRIORITY_COLORS["normal"]
        )
        priority_lbl = QLabel(self._card.priority[0].upper())
        priority_lbl.setFixedSize(20, 20)
        priority_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        priority_lbl.setStyleSheet(
            f"background-color: {priority_color}; color: {CATPPUCCIN_BASE}; "
            f"border-radius: 10px; font-weight: bold; font-size: 10px;"
        )
        top_row.addWidget(priority_lbl)

        layout.addLayout(top_row)

        if self._card.due_date:
            due_lbl = QLabel(f"📅 {self._card.due_date}")
            due_lbl.setStyleSheet(f"color: {CATPPUCCIN_SUBTEXT}; font-size: 11px;")
            layout.addWidget(due_lbl)

        if self._card.assignee:
            assignee_lbl = QLabel(f"👤 {self._card.assignee}")
            assignee_lbl.setStyleSheet(f"color: {CATPPUCCIN_SUBTEXT}; font-size: 11px;")
            layout.addWidget(assignee_lbl)

        if self._card.tags:
            tags_widget = QWidget()
            tags_layout = QHBoxLayout(tags_widget)
            tags_layout.setContentsMargins(0, 0, 0, 0)
            tags_layout.setSpacing(3)
            for tag in self._card.tags.split(","):
                tag = tag.strip()
                if tag:
                    tag_lbl = QLabel(tag)
                    tag_lbl.setStyleSheet(
                        f"background-color: {CATPPUCCIN_SURFACE1}; color: {CATPPUCCIN_TEXT}; "
                        f"padding: 0px 5px; border-radius: 2px; font-size: 10px;"
                    )
                    tags_layout.addWidget(tag_lbl)
            tags_layout.addStretch()
            layout.addWidget(tags_widget)

        btn_row = QHBoxLayout()
        btn_row.setSpacing(4)

        up_btn = QPushButton("▲")
        up_btn.setFixedSize(22, 22)
        up_btn.setStyleSheet(
            f"QPushButton {{ background-color: {CATPPUCCIN_SURFACE0}; color: {CATPPUCCIN_SUBTEXT}; "
            f"border: none; border-radius: 3px; font-size: 10px; }}"
            f"QPushButton:hover {{ background-color: {CATPPUCCIN_SURFACE2}; }}"
        )
        up_btn.clicked.connect(lambda: self.move_up_requested.emit(self._card.id))
        btn_row.addWidget(up_btn)

        down_btn = QPushButton("▼")
        down_btn.setFixedSize(22, 22)
        down_btn.setStyleSheet(
            f"QPushButton {{ background-color: {CATPPUCCIN_SURFACE0}; color: {CATPPUCCIN_SUBTEXT}; "
            f"border: none; border-radius: 3px; font-size: 10px; }}"
            f"QPushButton:hover {{ background-color: {CATPPUCCIN_SURFACE2}; }}"
        )
        down_btn.clicked.connect(lambda: self.move_down_requested.emit(self._card.id))
        btn_row.addWidget(down_btn)

        btn_row.addStretch()
        layout.addLayout(btn_row)

    def _apply_style(self):
        self.setStyleSheet(
            f'[class="card"] {{ background-color: {CATPPUCCIN_SURFACE0}; '
            f"border: 1px solid {CATPPUCCIN_SURFACE1}; border-radius: 6px; }}"
            f'[class="card"]:hover {{ border-color: {CATPPUCCIN_BLUE}; }}'
        )

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit(self._card.id)
        super().mousePressEvent(event)


class ColumnWidget(QFrame):
    card_clicked = pyqtSignal(int)
    add_card_requested = pyqtSignal(int)
    card_move_up = pyqtSignal(int)
    card_move_down = pyqtSignal(int)

    def __init__(self, column: ProjectColumn, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self._column = column
        self.setProperty("class", "kanban-column")
        self._setup_ui()
        self._apply_style()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(6)

        cards = self._column.get_cards()

        header_row = QHBoxLayout()
        name_lbl = QLabel(self._column.name)
        name_lbl.setStyleSheet(
            f"font-weight: bold; color: {CATPPUCCIN_TEXT}; font-size: 14px;"
        )
        header_row.addWidget(name_lbl, 1)

        count_lbl = QLabel(str(len(cards)))
        count_lbl.setStyleSheet(
            f"background-color: {CATPPUCCIN_SURFACE1}; color: {CATPPUCCIN_SUBTEXT}; "
            f"padding: 1px 7px; border-radius: 8px; font-size: 11px;"
        )
        header_row.addWidget(count_lbl)
        layout.addLayout(header_row)

        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setStyleSheet(f"color: {CATPPUCCIN_SURFACE1};")
        layout.addWidget(sep)

        for card in cards:
            card_w = CardWidget(card)
            card_w.clicked.connect(self.card_clicked.emit)
            card_w.move_up_requested.connect(self.card_move_up.emit)
            card_w.move_down_requested.connect(self.card_move_down.emit)
            layout.addWidget(card_w)

        layout.addStretch()

        add_btn = QPushButton("+ 添加卡片")
        add_btn.setStyleSheet(
            f"QPushButton {{ background-color: {CATPPUCCIN_SURFACE1}; color: {CATPPUCCIN_SUBTEXT}; "
            f"border: none; border-radius: 4px; padding: 6px; font-size: 12px; }}"
            f"QPushButton:hover {{ background-color: {CATPPUCCIN_SURFACE2}; color: {CATPPUCCIN_TEXT}; }}"
        )
        add_btn.clicked.connect(lambda: self.add_card_requested.emit(self._column.id))
        layout.addWidget(add_btn)

    def _apply_style(self):
        self.setStyleSheet(
            f'[class="kanban-column"] {{ background-color: {CATPPUCCIN_BASE}; '
            f"border: 1px solid {CATPPUCCIN_SURFACE1}; border-radius: 8px; }}"
        )

    def setFixedWidthTo(self, width: int):
        self.setFixedWidth(width)


class ProjectPageWidget(QWidget):
    project_changed = pyqtSignal()

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self._current_project: Optional[Project] = None
        self._setup_ui()
        self._load_projects()

    def _setup_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        header = QFrame()
        header.setStyleSheet(
            f"background-color: {CATPPUCCIN_SURFACE0}; border-bottom: 1px solid {CATPPUCCIN_SURFACE1};"
        )
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(16, 10, 16, 10)
        header_layout.setSpacing(12)

        title_lbl = QLabel("项目板")
        title_lbl.setStyleSheet(
            f"font-size: 18px; font-weight: bold; color: {CATPPUCCIN_TEXT};"
        )
        header_layout.addWidget(title_lbl)

        self._project_combo = QComboBox()
        self._project_combo.setMinimumWidth(200)
        self._project_combo.setStyleSheet(
            f"QComboBox {{ background-color: {CATPPUCCIN_SURFACE1}; color: {CATPPUCCIN_TEXT}; "
            f"border: 1px solid {CATPPUCCIN_SURFACE2}; border-radius: 4px; padding: 5px 10px; }}"
            f"QComboBox::drop-down {{ border: none; }}"
            f"QComboBox QAbstractItemView {{ background-color: {CATPPUCCIN_SURFACE0}; "
            f"color: {CATPPUCCIN_TEXT}; selection-background-color: {CATPPUCCIN_SURFACE2}; }}"
        )
        self._project_combo.currentIndexChanged.connect(self._on_project_selected)
        header_layout.addWidget(self._project_combo)

        new_project_btn = QPushButton("新建项目")
        new_project_btn.setStyleSheet(
            f"QPushButton {{ background-color: {CATPPUCCIN_MAUVE}; color: {CATPPUCCIN_BASE}; "
            f"border: none; border-radius: 4px; padding: 6px 14px; font-weight: bold; }}"
            f"QPushButton:hover {{ background-color: {CATPPUCCIN_BLUE}; }}"
        )
        new_project_btn.clicked.connect(self._create_project)
        header_layout.addWidget(new_project_btn)

        new_col_btn = QPushButton("新建列")
        new_col_btn.setStyleSheet(
            f"QPushButton {{ background-color: {CATPPUCCIN_SURFACE1}; color: {CATPPUCCIN_TEXT}; "
            f"border: 1px solid {CATPPUCCIN_SURFACE2}; border-radius: 4px; padding: 6px 14px; }}"
            f"QPushButton:hover {{ background-color: {CATPPUCCIN_SURFACE2}; }}"
        )
        new_col_btn.clicked.connect(self._create_column)
        header_layout.addWidget(new_col_btn)

        header_layout.addStretch()
        main_layout.addWidget(header)

        self._scroll_area = QScrollArea()
        self._scroll_area.setWidgetResizable(True)
        self._scroll_area.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOn
        )
        self._scroll_area.setVerticalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )
        self._scroll_area.setStyleSheet(
            f"QScrollArea {{ background-color: {CATPPUCCIN_BASE}; border: none; }}"
            f"QScrollBar:horizontal {{ height: 10px; background-color: {CATPPUCCIN_SURFACE0}; }}"
            f"QScrollBar::handle:horizontal {{ background-color: {CATPPUCCIN_SURFACE2}; border-radius: 5px; min-width: 40px; }}"
            f"QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{ width: 0px; }}"
        )

        self._columns_container = QWidget()
        self._columns_layout = QHBoxLayout(self._columns_container)
        self._columns_layout.setContentsMargins(16, 12, 16, 12)
        self._columns_layout.setSpacing(12)
        self._columns_layout.setAlignment(Qt.AlignmentFlag.AlignLeft)

        self._scroll_area.setWidget(self._columns_container)
        main_layout.addWidget(self._scroll_area, 1)

        self._placeholder = QLabel("请选择或创建一个项目")
        self._placeholder.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._placeholder.setStyleSheet(
            f"color: {CATPPUCCIN_OVERLAY0}; font-size: 16px; font-style: italic;"
        )
        self._columns_layout.addWidget(self._placeholder)

    def _load_projects(self):
        self._project_combo.blockSignals(True)
        self._project_combo.clear()
        self._project_combo.addItem("选择项目...", 0)
        projects = Project.get_all()
        for p in projects:
            self._project_combo.addItem(p.name, p.id)
        self._project_combo.blockSignals(False)

    def _on_project_selected(self, index: int):
        project_id = self._project_combo.itemData(index)
        if not project_id:
            self._current_project = None
            self._clear_columns()
            self._show_placeholder("请选择或创建一个项目")
            return
        self._current_project = Project.get_by_id(project_id)
        self._load_columns()
        self.project_changed.emit()

    def _clear_columns(self):
        while self._columns_layout.count():
            item = self._columns_layout.takeAt(0)
            w = item.widget()
            if w:
                w.setParent(None)
                w.deleteLater()

    def _show_placeholder(self, text: str):
        self._clear_columns()
        lbl = QLabel(text)
        lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lbl.setStyleSheet(
            f"color: {CATPPUCCIN_OVERLAY0}; font-size: 16px; font-style: italic;"
        )
        self._columns_layout.addWidget(lbl)

    def _load_columns(self):
        self._clear_columns()
        if not self._current_project:
            self._show_placeholder("请选择或创建一个项目")
            return
        columns = self._current_project.get_columns()
        if not columns:
            self._show_placeholder("暂无列，点击「新建列」添加")
            return
        for col in columns:
            col_w = ColumnWidget(col)
            col_w.setFixedWidthTo(280)
            col_w.card_clicked.connect(self._on_card_clicked)
            col_w.add_card_requested.connect(self._add_card)
            col_w.card_move_up.connect(self._move_card_up)
            col_w.card_move_down.connect(self._move_card_down)
            self._columns_layout.addWidget(col_w)
        self._columns_layout.addStretch()

    def _create_project(self):
        dlg = ProjectEditDialog(parent=self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            project = dlg.get_project()
            if project:
                self._load_projects()
                idx = self._project_combo.findData(project.id)
                if idx >= 0:
                    self._project_combo.setCurrentIndex(idx)
                self.project_changed.emit()

    def _create_column(self):
        if not self._current_project:
            QMessageBox.information(self, "提示", "请先选择一个项目")
            return
        dlg = ColumnEditDialog(parent=self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            name = dlg.get_column_name()
            if name:
                self._current_project.add_column(name)
                self._load_columns()
                self.project_changed.emit()

    def _add_card(self, column_id: int):
        dlg = CardEditDialog(parent=self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            card = dlg.get_card()
            if card:
                card.column_id = column_id
                col = ProjectColumn.get_by_id(column_id)
                if col:
                    row_result = None
                    from openemail.storage.database import db

                    row_result = db.fetchone(
                        "SELECT MAX(position) as max_pos FROM project_cards WHERE column_id = ?",
                        (column_id,),
                    )
                    card.position = (
                        (row_result["max_pos"] or 0) + 1
                        if row_result and row_result["max_pos"] is not None
                        else 0
                    )
                card.save()
                self._load_columns()
                self.project_changed.emit()

    def _on_card_clicked(self, card_id: int):
        card = ProjectCard.get_by_id(card_id)
        if card:
            dlg = CardDetailDialog(card, self)
            dlg.exec()

    def _move_card_up(self, card_id: int):
        card = ProjectCard.get_by_id(card_id)
        if not card or card.position <= 0:
            return
        card.set_position(card.position - 1)
        self._load_columns()

    def _move_card_down(self, card_id: int):
        card = ProjectCard.get_by_id(card_id)
        if not card:
            return
        col = ProjectColumn.get_by_id(card.column_id)
        if not col:
            return
        cards = col.get_cards()
        if card.position >= len(cards) - 1:
            return
        card.set_position(card.position + 1)
        self._load_columns()

    def refresh(self):
        self._load_projects()
        if self._current_project:
            self._current_project = Project.get_by_id(self._current_project.id)
            self._load_columns()
