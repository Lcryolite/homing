from __future__ import annotations

from datetime import datetime
from typing import Optional

from PyQt6.QtCore import Qt, pyqtSignal, QDate
from PyQt6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QSplitter,
    QLabel,
    QPushButton,
    QCalendarWidget,
    QDialog,
    QFormLayout,
    QLineEdit,
    QTextEdit,
    QCheckBox,
    QScrollArea,
    QFrame,
    QMessageBox,
    QTimeEdit,
    QSpinBox,
)
from PyQt6.QtGui import QPainter, QColor

from openemail.models.calendar_event import CalendarEvent


CATPPUCCIN_BG = "#F7F4EE"
CATPPUCCIN_ACCENT = "#7C8A9A"
CATPPUCCIN_TEXT = "#141413"
CATPPUCCIN_MUTED = "#6C665F"
CATPPUCCIN_CARD = "#FBF8F3"
CATPPUCCIN_BORDER = "#E8E1D8"

EVENT_COLORS = [
    "#7C8A9A",
    "#a6e3a1",
    "#C97850",
    "#C97850",
    "#cba6f7",
    "#fab387",
    "#94e2d5",
    "#f5c2e7",
]


class EventDotCalendarWidget(QCalendarWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._event_dates: dict[str, str] = {}
        self.setGridVisible(True)
        self.setHorizontalHeaderFormat(
            QCalendarWidget.HorizontalHeaderFormat.ShortDayNames
        )
        self.setVerticalHeaderFormat(
            QCalendarWidget.VerticalHeaderFormat.NoVerticalHeader
        )
        self.setSelectionMode(QCalendarWidget.SelectionMode.SingleSelection)

    def set_event_dates(self, dates: dict[str, str]):
        self._event_dates = dates
        self.updateCells()

    def paintCell(self, painter: QPainter, rect, date: QDate):
        super().paintCell(painter, rect, date)
        key = date.toString("yyyy-MM-dd")
        if key in self._event_dates:
            color = QColor(self._event_dates[key])
            painter.setBrush(color)
            painter.setPen(Qt.PenStyle.NoPen)
            dot_x = rect.center().x()
            dot_y = rect.bottom() - 6
            painter.drawEllipse(dot_x - 3, dot_y - 3, 6, 6)


class EventItemWidget(QWidget):
    clicked = pyqtSignal(int)

    def __init__(self, event: CalendarEvent, parent=None):
        super().__init__(parent)
        self._event_id = event.id
        self.setProperty("class", "event-item")
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFixedHeight(60)
        self.setStyleSheet(f"""
            QWidget[event-item="true"] {{
                background: {CATPPUCCIN_CARD};
                border: 1px solid {CATPPUCCIN_BORDER};
                border-radius: 8px;
                padding: 4px 8px;
            }}
            QWidget[event-item="true"]:hover {{
                background: #3b3b54;
                border-color: {CATPPUCCIN_ACCENT};
            }}
        """)

        layout = QHBoxLayout(self)
        layout.setSpacing(10)
        layout.setContentsMargins(10, 6, 10, 6)

        dot = QLabel()
        dot.setFixedSize(10, 10)
        color = event.color if event.color else CATPPUCCIN_ACCENT
        dot.setStyleSheet(f"""
            background: {color};
            border-radius: 5px;
        """)
        layout.addWidget(dot)

        info_layout = QVBoxLayout()
        info_layout.setSpacing(2)

        title = QLabel(event.title or "无标题")
        title.setStyleSheet(
            f"color: {CATPPUCCIN_TEXT}; font-size: 13px; font-weight: bold; background: transparent; border: none;"
        )
        info_layout.addWidget(title)

        time_loc_layout = QHBoxLayout()
        time_loc_layout.setSpacing(8)

        time_label = QLabel(event.display_time)
        time_label.setStyleSheet(
            f"color: {CATPPUCCIN_MUTED}; font-size: 11px; background: transparent; border: none;"
        )
        time_loc_layout.addWidget(time_label)

        if event.location:
            loc_label = QLabel(f"📍 {event.location}")
            loc_label.setStyleSheet(
                f"color: {CATPPUCCIN_MUTED}; font-size: 11px; background: transparent; border: none;"
            )
            time_loc_layout.addWidget(loc_label)

        time_loc_layout.addStretch()
        info_layout.addLayout(time_loc_layout)

        layout.addLayout(info_layout, 1)

    def mousePressEvent(self, event):
        self.clicked.emit(self._event_id)
        super().mousePressEvent(event)


class EventListWidget(QWidget):
    event_selected = pyqtSignal(int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._events: list[CalendarEvent] = []
        self._item_widgets: list[EventItemWidget] = []

        self._layout = QVBoxLayout(self)
        self._layout.setSpacing(6)
        self._layout.setContentsMargins(0, 0, 0, 0)
        self._layout.addStretch()

        self._date_label = QLabel()
        self._date_label.setStyleSheet(
            f"color: {CATPPUCCIN_TEXT}; font-size: 14px; font-weight: bold; padding: 8px 0;"
        )
        self._layout.insertWidget(0, self._date_label)

        self._empty_label = QLabel("暂无事件")
        self._empty_label.setStyleSheet(
            f"color: {CATPPUCCIN_MUTED}; font-size: 13px; padding: 20px; background: transparent; border: none;"
        )
        self._empty_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._layout.insertWidget(1, self._empty_label)

    def set_date(self, date: QDate):
        self._date_label.setText(date.toString("yyyy年MM月dd日"))
        date_str = date.toString("yyyy-MM-dd")
        start = f"{date_str}T00:00:00"
        end = f"{date_str}T23:59:59"
        self._events = CalendarEvent.get_by_date_range(start, end)
        self._rebuild()

    def _rebuild(self):
        for w in self._item_widgets:
            self._layout.removeWidget(w)
            w.deleteLater()
        self._item_widgets.clear()

        self._empty_label.setVisible(len(self._events) == 0)

        for ev in self._events:
            item = EventItemWidget(ev)
            item.clicked.connect(self.event_selected.emit)
            idx = self._layout.count() - 1
            self._layout.insertWidget(idx, item)
            self._item_widgets.append(item)

    def refresh(self, date: QDate):
        self.set_date(date)


class EventDetailPanel(QWidget):
    edit_requested = pyqtSignal(int)
    delete_requested = pyqtSignal(int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._event: Optional[CalendarEvent] = None
        self.setProperty("class", "detail-panel")
        self.setMinimumWidth(280)

        layout = QVBoxLayout(self)
        layout.setSpacing(12)
        layout.setContentsMargins(16, 16, 16, 16)

        self._title_label = QLabel("事件详情")
        self._title_label.setStyleSheet(
            f"color: {CATPPUCCIN_ACCENT}; font-size: 16px; font-weight: bold; background: transparent; border: none;"
        )
        layout.addWidget(self._title_label)

        self._content_area = QScrollArea()
        self._content_area.setWidgetResizable(True)
        self._content_area.setFrameShape(QFrame.Shape.NoFrame)
        self._content_area.setStyleSheet(
            "QScrollArea { background: transparent; border: none; }"
        )

        self._content_widget = QWidget()
        self._content_widget.setStyleSheet("background: transparent;")
        self._content_layout = QVBoxLayout(self._content_widget)
        self._content_layout.setSpacing(10)
        self._content_layout.setContentsMargins(0, 0, 0, 0)

        self._event_title = QLabel()
        self._event_title.setWordWrap(True)
        self._event_title.setStyleSheet(
            f"color: {CATPPUCCIN_TEXT}; font-size: 18px; font-weight: bold; background: transparent; border: none;"
        )
        self._content_layout.addWidget(self._event_title)

        self._time_label = QLabel()
        self._time_label.setWordWrap(True)
        self._time_label.setStyleSheet(
            f"color: {CATPPUCCIN_MUTED}; font-size: 13px; background: transparent; border: none;"
        )
        self._content_layout.addWidget(self._time_label)

        self._location_label = QLabel()
        self._location_label.setWordWrap(True)
        self._location_label.setStyleSheet(
            f"color: {CATPPUCCIN_MUTED}; font-size: 13px; background: transparent; border: none;"
        )
        self._content_layout.addWidget(self._location_label)

        self._allday_label = QLabel()
        self._allday_label.setStyleSheet(
            f"color: {CATPPUCCIN_MUTED}; font-size: 13px; background: transparent; border: none;"
        )
        self._content_layout.addWidget(self._allday_label)

        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setStyleSheet(f"color: {CATPPUCCIN_BORDER};")
        self._content_layout.addWidget(sep)

        self._desc_label = QLabel()
        self._desc_label.setWordWrap(True)
        self._desc_label.setStyleSheet(
            f"color: {CATPPUCCIN_TEXT}; font-size: 13px; background: transparent; border: none;"
        )
        self._content_layout.addWidget(self._desc_label)

        self._content_layout.addStretch()
        self._content_area.setWidget(self._content_widget)
        layout.addWidget(self._content_area, 1)

        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(8)

        self._edit_btn = QPushButton("编辑")
        self._edit_btn.setProperty("class", "primary")
        self._edit_btn.setStyleSheet(f"""
            QPushButton {{
                background: {CATPPUCCIN_ACCENT};
                color: {CATPPUCCIN_BG};
                border: none;
                border-radius: 6px;
                padding: 8px 16px;
                font-weight: bold;
            }}
            QPushButton:hover {{
                background: #7aa2f0;
            }}
        """)
        self._edit_btn.clicked.connect(self._on_edit)
        btn_layout.addWidget(self._edit_btn)

        self._delete_btn = QPushButton("删除")
        self._delete_btn.setStyleSheet(f"""
            QPushButton {{
                background: #C97850;
                color: {CATPPUCCIN_BG};
                border: none;
                border-radius: 6px;
                padding: 8px 16px;
                font-weight: bold;
            }}
            QPushButton:hover {{
                background: #e06c8c;
            }}
        """)
        self._delete_btn.clicked.connect(self._on_delete)
        btn_layout.addWidget(self._delete_btn)

        btn_layout.addStretch()
        layout.addLayout(btn_layout)

        self._placeholder = QLabel("选择一个事件查看详情")
        self._placeholder.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._placeholder.setStyleSheet(
            f"color: {CATPPUCCIN_MUTED}; font-size: 14px; background: transparent; border: none;"
        )
        layout.addWidget(self._placeholder)

        self._show_placeholder(True)

    def _show_placeholder(self, show: bool):
        self._content_area.setVisible(not show)
        self._edit_btn.setVisible(not show)
        self._delete_btn.setVisible(not show)
        self._placeholder.setVisible(show)

    def load_event(self, event: CalendarEvent):
        self._event = event
        self._show_placeholder(False)

        self._event_title.setText(event.title or "无标题")
        self._time_label.setText(
            f"🕐 {event.display_time}" if event.display_time else ""
        )
        self._location_label.setText(f"📍 {event.location}" if event.location else "")
        self._allday_label.setText("全天事件" if event.is_all_day else "")
        self._desc_label.setText(event.description or "无描述")

        color = event.color if event.color else CATPPUCCIN_ACCENT
        self._event_title.setStyleSheet(
            f"color: {color}; font-size: 18px; font-weight: bold; background: transparent; border: none;"
        )

    def clear(self):
        self._event = None
        self._show_placeholder(True)

    def _on_edit(self):
        if self._event:
            self.edit_requested.emit(self._event.id)

    def _on_delete(self):
        if self._event:
            self.delete_requested.emit(self._event.id)


class ColorPickerWidget(QWidget):
    color_selected = pyqtSignal(str)

    def __init__(self, selected: str = "", parent=None):
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setSpacing(6)
        layout.setContentsMargins(0, 0, 0, 0)

        self._buttons: list[QPushButton] = []
        for color in EVENT_COLORS:
            btn = QPushButton()
            btn.setFixedSize(24, 24)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setStyleSheet(f"""
                QPushButton {{
                    background: {color};
                    border: 2px solid transparent;
                    border-radius: 12px;
                }}
                QPushButton:hover {{
                    border-color: {CATPPUCCIN_TEXT};
                }}
            """)
            btn.clicked.connect(lambda checked, c=color: self._pick(c))
            layout.addWidget(btn)
            self._buttons.append(btn)

        if selected:
            self._select(selected)
        else:
            self._select(EVENT_COLORS[0])

        self._selected_color = selected if selected else EVENT_COLORS[0]

    def _pick(self, color: str):
        self._selected_color = color
        self._select(color)
        self.color_selected.emit(color)

    def _select(self, color: str):
        for btn, c in zip(self._buttons, EVENT_COLORS):
            if c == color:
                btn.setStyleSheet(f"""
                    QPushButton {{
                        background: {c};
                        border: 2px solid {CATPPUCCIN_TEXT};
                        border-radius: 12px;
                    }}
                """)
            else:
                btn.setStyleSheet(f"""
                    QPushButton {{
                        background: {c};
                        border: 2px solid transparent;
                        border-radius: 12px;
                    }}
                    QPushButton:hover {{
                        border-color: {CATPPUCCIN_TEXT};
                    }}
                """)

    def get_color(self) -> str:
        return self._selected_color


class EventEditDialog(QDialog):
    event_saved = pyqtSignal(int)

    def __init__(
        self,
        parent=None,
        event: Optional[CalendarEvent] = None,
        initial_date: Optional[QDate] = None,
    ):
        super().__init__(parent)
        self._event = event
        self._is_new = event is None
        self._initial_date = initial_date

        self.setWindowTitle("新建事件" if self._is_new else "编辑事件")
        self.setMinimumSize(480, 520)
        self._setup_ui()
        self._load_data()

    def _setup_ui(self):
        self.setStyleSheet(f"""
            QDialog {{
                background: {CATPPUCCIN_BG};
                color: {CATPPUCCIN_TEXT};
            }}
            QLabel {{
                color: {CATPPUCCIN_TEXT};
                background: transparent;
            }}
            QLineEdit, QTextEdit {{
                background: {CATPPUCCIN_CARD};
                color: {CATPPUCCIN_TEXT};
                border: 1px solid {CATPPUCCIN_BORDER};
                border-radius: 6px;
                padding: 6px 10px;
            }}
            QLineEdit:focus, QTextEdit:focus {{
                border-color: {CATPPUCCIN_ACCENT};
            }}
            QTimeEdit {{
                background: {CATPPUCCIN_CARD};
                color: {CATPPUCCIN_TEXT};
                border: 1px solid {CATPPUCCIN_BORDER};
                border-radius: 6px;
                padding: 4px 8px;
            }}
            QCheckBox {{
                color: {CATPPUCCIN_TEXT};
                spacing: 8px;
            }}
            QCheckBox::indicator {{
                width: 16px;
                height: 16px;
                border-radius: 3px;
                border: 1px solid {CATPPUCCIN_BORDER};
                background: {CATPPUCCIN_CARD};
            }}
            QCheckBox::indicator:checked {{
                background: {CATPPUCCIN_ACCENT};
                border-color: {CATPPUCCIN_ACCENT};
            }}
        """)

        layout = QVBoxLayout(self)
        layout.setSpacing(14)
        layout.setContentsMargins(24, 24, 24, 24)

        header = QLabel("新建事件" if self._is_new else "编辑事件")
        header.setStyleSheet(
            f"color: {CATPPUCCIN_ACCENT}; font-size: 18px; font-weight: bold; background: transparent; border: none;"
        )
        layout.addWidget(header)

        form = QFormLayout()
        form.setSpacing(12)
        form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)

        self._title_edit = QLineEdit()
        self._title_edit.setPlaceholderText("事件标题")
        form.addRow("标题:", self._title_edit)

        self._location_edit = QLineEdit()
        self._location_edit.setPlaceholderText("地点（可选）")
        form.addRow("地点:", self._location_edit)

        self._allday_check = QCheckBox("全天")
        self._allday_check.toggled.connect(self._on_allday_toggled)
        form.addRow("", self._allday_check)

        time_layout = QHBoxLayout()
        self._start_time = QTimeEdit()
        self._start_time.setDisplayFormat("HH:mm")
        self._start_time.setTime(QDate.currentDate().startOfDay().addSecs(9 * 3600))
        time_layout.addWidget(QLabel("开始:"))
        time_layout.addWidget(self._start_time)

        self._end_time = QTimeEdit()
        self._end_time.setDisplayFormat("HH:mm")
        self._end_time.setTime(QDate.currentDate().startOfDay().addSecs(10 * 3600))
        time_layout.addWidget(QLabel("结束:"))
        time_layout.addWidget(self._end_time)
        time_layout.addStretch()
        form.addRow("时间:", time_layout)

        # 提醒设置
        reminder_layout = QHBoxLayout()
        reminder_layout.setSpacing(8)

        self._reminder_spin = QSpinBox()
        self._reminder_spin.setRange(0, 1440)  # 0到24小时
        self._reminder_spin.setSingleStep(5)
        self._reminder_spin.setSuffix(" 分钟前")
        self._reminder_spin.setValue(0)

        reminder_label = QLabel("提醒:")
        reminder_layout.addWidget(reminder_label)
        reminder_layout.addWidget(self._reminder_spin)

        # 添加常用提醒选项按钮
        reminder_preset_layout = QHBoxLayout()
        reminder_preset_layout.setSpacing(4)

        self._reminder_none_btn = QPushButton("无提醒")
        self._reminder_none_btn.setCheckable(True)
        self._reminder_none_btn.setChecked(True)
        self._reminder_none_btn.clicked.connect(lambda: self._reminder_spin.setValue(0))

        self._reminder_5min_btn = QPushButton("5分钟")
        self._reminder_5min_btn.setCheckable(True)
        self._reminder_5min_btn.clicked.connect(lambda: self._reminder_spin.setValue(5))

        self._reminder_15min_btn = QPushButton("15分钟")
        self._reminder_15min_btn.setCheckable(True)
        self._reminder_15min_btn.clicked.connect(
            lambda: self._reminder_spin.setValue(15)
        )

        self._reminder_1hour_btn = QPushButton("1小时")
        self._reminder_1hour_btn.setCheckable(True)
        self._reminder_1hour_btn.clicked.connect(
            lambda: self._reminder_spin.setValue(60)
        )

        self._reminder_1day_btn = QPushButton("1天")
        self._reminder_1day_btn.setCheckable(True)
        self._reminder_1day_btn.clicked.connect(
            lambda: self._reminder_spin.setValue(1440)
        )

        reminder_preset_layout.addWidget(self._reminder_none_btn)
        reminder_preset_layout.addWidget(self._reminder_5min_btn)
        reminder_preset_layout.addWidget(self._reminder_15min_btn)
        reminder_preset_layout.addWidget(self._reminder_1hour_btn)
        reminder_preset_layout.addWidget(self._reminder_1day_btn)
        reminder_preset_layout.addStretch()

        form.addRow(reminder_layout)
        form.addRow("", reminder_preset_layout)

        color_label = QLabel("颜色:")
        self._color_picker = ColorPickerWidget()
        color_row = QHBoxLayout()
        color_row.addWidget(color_label)
        color_row.addWidget(self._color_picker)
        color_row.addStretch()
        form.addRow("", self._color_picker)

        layout.addLayout(form)

        desc_label = QLabel("描述:")
        desc_label.setStyleSheet(
            f"color: {CATPPUCCIN_TEXT}; font-size: 13px; background: transparent; border: none;"
        )
        layout.addWidget(desc_label)

        self._desc_edit = QTextEdit()
        self._desc_edit.setPlaceholderText("添加描述...")
        self._desc_edit.setMaximumHeight(120)
        self._desc_edit.setAcceptRichText(False)
        layout.addWidget(self._desc_edit)

        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(12)

        save_btn = QPushButton("保存")
        save_btn.setProperty("class", "primary")
        save_btn.setStyleSheet(f"""
            QPushButton {{
                background: {CATPPUCCIN_ACCENT};
                color: {CATPPUCCIN_BG};
                border: none;
                border-radius: 6px;
                padding: 8px 24px;
                font-weight: bold;
            }}
            QPushButton:hover {{
                background: #7aa2f0;
            }}
        """)
        save_btn.clicked.connect(self._save)
        btn_layout.addWidget(save_btn)

        cancel_btn = QPushButton("取消")
        cancel_btn.setStyleSheet(f"""
            QPushButton {{
                background: {CATPPUCCIN_CARD};
                color: {CATPPUCCIN_TEXT};
                border: 1px solid {CATPPUCCIN_BORDER};
                border-radius: 6px;
                padding: 8px 24px;
            }}
            QPushButton:hover {{
                background: #3b3b54;
            }}
        """)
        cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(cancel_btn)

        btn_layout.addStretch()
        layout.addLayout(btn_layout)

    def _on_allday_toggled(self, checked: bool):
        self._start_time.setEnabled(not checked)
        self._end_time.setEnabled(not checked)

    def _load_data(self):
        if self._event:
            self._title_edit.setText(self._event.title or "")
            self._location_edit.setText(self._event.location or "")
            self._desc_edit.setText(self._event.description or "")
            self._allday_check.setChecked(self._event.is_all_day)

            if self._event.start_time:
                try:
                    dt = datetime.fromisoformat(
                        self._event.start_time.replace("Z", "+00:00")
                    )
                    self._start_time.setTime(dt.hour, dt.minute)
                except (ValueError, TypeError):
                    pass

            if self._event.end_time:
                try:
                    dt = datetime.fromisoformat(
                        self._event.end_time.replace("Z", "+0:00")
                    )
                    self._end_time.setTime(dt.hour, dt.minute)
                except (ValueError, TypeError):
                    pass

            if self._event.color:
                self._color_picker._pick(self._event.color)

            # 加载提醒设置
            if self._event.reminder > 0:
                self._reminder_spin.setValue(self._event.reminder)
                # 选择对应的预设按钮
                if self._event.reminder == 5:
                    self._reminder_5min_btn.setChecked(True)
                elif self._event.reminder == 15:
                    self._reminder_15min_btn.setChecked(True)
                elif self._event.reminder == 60:
                    self._reminder_1hour_btn.setChecked(True)
                elif self._event.reminder == 1440:
                    self._reminder_1day_btn.setChecked(True)
                else:
                    self._reminder_none_btn.setChecked(True)
            else:
                self._reminder_none_btn.setChecked(True)

    def _save(self):
        title = self._title_edit.text().strip()
        if not title:
            QMessageBox.warning(self, "验证错误", "事件标题不能为空")
            self._title_edit.setFocus()
            return

        if self._event:
            ev = self._event
        else:
            ev = CalendarEvent()

        ev.title = title
        ev.location = self._location_edit.text().strip()
        ev.description = self._desc_edit.toPlainText().strip()
        ev.is_all_day = self._allday_check.isChecked()
        ev.color = self._color_picker.get_color()
        ev.reminder = self._reminder_spin.value()

        if self._initial_date and self._is_new:
            date_str = self._initial_date.toString("yyyy-MM-dd")
        elif self._event and self._event.start_time:
            try:
                dt = datetime.fromisoformat(
                    self._event.start_time.replace("Z", "+00:00")
                )
                date_str = dt.strftime("%Y-%m-%d")
            except (ValueError, TypeError):
                date_str = QDate.currentDate().toString("yyyy-MM-dd")
        else:
            date_str = QDate.currentDate().toString("yyyy-MM-dd")

        if ev.is_all_day:
            ev.start_time = f"{date_str}T00:00:00"
            ev.end_time = f"{date_str}T23:59:59"
        else:
            st = self._start_time.time()
            et = self._end_time.time()
            ev.start_time = f"{date_str}T{st.toString('HH:mm:ss')}"
            ev.end_time = f"{date_str}T{et.toString('HH:mm:ss')}"

        try:
            event_id = ev.save()
            self.event_saved.emit(event_id)
            self.accept()
        except Exception as e:
            QMessageBox.critical(self, "保存失败", f"保存事件时发生错误:\n{str(e)}")


class CalendarPageWidget(QWidget):
    event_created = pyqtSignal(int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._selected_date = QDate.currentDate()
        self._setup_ui()
        self._refresh_events()

    def _setup_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setSpacing(0)
        main_layout.setContentsMargins(0, 0, 0, 0)

        header = QWidget()
        header.setProperty("class", "calendar-header")
        header.setFixedHeight(48)
        header.setStyleSheet(f"""
            QWidget[calendar-header="true"] {{
                background: {CATPPUCCIN_CARD};
                border-bottom: 1px solid {CATPPUCCIN_BORDER};
            }}
        """)
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(16, 0, 16, 0)
        header_layout.setSpacing(8)

        title = QLabel("日历")
        title.setStyleSheet(
            f"color: {CATPPUCCIN_TEXT}; font-size: 16px; font-weight: bold; background: transparent; border: none;"
        )
        header_layout.addWidget(title)

        header_layout.addStretch()

        self._prev_btn = QPushButton("◀")
        self._prev_btn.setFixedSize(32, 32)
        self._prev_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._prev_btn.setStyleSheet(f"""
            QPushButton {{
                background: transparent;
                color: {CATPPUCCIN_TEXT};
                border: 1px solid {CATPPUCCIN_BORDER};
                border-radius: 6px;
                font-size: 14px;
            }}
            QPushButton:hover {{
                background: {CATPPUCCIN_CARD};
                border-color: {CATPPUCCIN_ACCENT};
            }}
        """)
        self._prev_btn.clicked.connect(self._go_prev)
        header_layout.addWidget(self._prev_btn)

        self._month_label = QLabel()
        self._month_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._month_label.setMinimumWidth(120)
        self._month_label.setStyleSheet(
            f"color: {CATPPUCCIN_TEXT}; font-size: 14px; font-weight: bold; background: transparent; border: none;"
        )
        header_layout.addWidget(self._month_label)

        self._next_btn = QPushButton("▶")
        self._next_btn.setFixedSize(32, 32)
        self._next_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._next_btn.setStyleSheet(self._prev_btn.styleSheet())
        self._next_btn.clicked.connect(self._go_next)
        header_layout.addWidget(self._next_btn)

        today_btn = QPushButton("今天")
        today_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        today_btn.setStyleSheet(f"""
            QPushButton {{
                background: {CATPPUCCIN_CARD};
                color: {CATPPUCCIN_ACCENT};
                border: 1px solid {CATPPUCCIN_ACCENT};
                border-radius: 6px;
                padding: 4px 12px;
                font-size: 13px;
            }}
            QPushButton:hover {{
                background: {CATPPUCCIN_ACCENT};
                color: {CATPPUCCIN_BG};
            }}
        """)
        today_btn.clicked.connect(self._go_today)
        header_layout.addWidget(today_btn)

        new_btn = QPushButton("新建事件")
        new_btn.setProperty("class", "primary")
        new_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        new_btn.setStyleSheet(f"""
            QPushButton {{
                background: {CATPPUCCIN_ACCENT};
                color: {CATPPUCCIN_BG};
                border: none;
                border-radius: 6px;
                padding: 6px 16px;
                font-size: 13px;
                font-weight: bold;
            }}
            QPushButton:hover {{
                background: #7aa2f0;
            }}
        """)
        new_btn.clicked.connect(self._create_event)
        header_layout.addWidget(new_btn)

        main_layout.addWidget(header)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.setStyleSheet(f"""
            QSplitter::handle {{
                background: {CATPPUCCIN_BORDER};
                width: 1px;
            }}
        """)

        left_widget = QWidget()
        left_layout = QVBoxLayout(left_widget)
        left_layout.setSpacing(8)
        left_layout.setContentsMargins(12, 12, 12, 12)

        self._calendar = EventDotCalendarWidget()
        self._calendar.setStyleSheet(f"""
            QCalendarWidget {{
                background: {CATPPUCCIN_BG};
                color: {CATPPUCCIN_TEXT};
                border: none;
            }}
            QCalendarWidget QWidget {{
                background: {CATPPUCCIN_BG};
            }}
            QCalendarWidget QToolButton {{
                background: {CATPPUCCIN_CARD};
                color: {CATPPUCCIN_TEXT};
                border: none;
                border-radius: 4px;
                padding: 4px 8px;
                font-size: 13px;
            }}
            QCalendarWidget QToolButton:hover {{
                background: {CATPPUCCIN_ACCENT};
                color: {CATPPUCCIN_BG};
            }}
            QCalendarWidget QMenu {{
                background: {CATPPUCCIN_CARD};
                color: {CATPPUCCIN_TEXT};
                border: 1px solid {CATPPUCCIN_BORDER};
            }}
            QCalendarWidget QAbstractItemView {{
                background: {CATPPUCCIN_CARD};
                color: {CATPPUCCIN_TEXT};
                selection-background-color: {CATPPUCCIN_ACCENT};
                selection-color: {CATPPUCCIN_BG};
                border: none;
            }}
            QCalendarWidget QSpinBox {{
                background: {CATPPUCCIN_CARD};
                color: {CATPPUCCIN_TEXT};
                border: 1px solid {CATPPUCCIN_BORDER};
                border-radius: 4px;
                padding: 2px;
            }}
        """)
        self._calendar.clicked.connect(self._on_date_clicked)
        self._calendar.currentPageChanged.connect(self._on_page_changed)
        left_layout.addWidget(self._calendar)

        self._event_list = EventListWidget()
        self._event_list.event_selected.connect(self._on_event_selected)
        left_layout.addWidget(self._event_list, 1)

        splitter.addWidget(left_widget)

        self._detail_panel = EventDetailPanel()
        self._detail_panel.edit_requested.connect(self._on_edit_requested)
        self._detail_panel.delete_requested.connect(self._on_delete_requested)
        splitter.addWidget(self._detail_panel)

        splitter.setSizes([600, 350])

        main_layout.addWidget(splitter, 1)

        self._update_month_label()

    def _update_month_label(self):
        y = self._calendar.yearShown()
        m = self._calendar.monthShown()
        self._month_label.setText(f"{y}年{m:02d}月")

    def _go_prev(self):
        self._calendar.showPreviousMonth()
        self._update_month_label()
        self._refresh_events()

    def _go_next(self):
        self._calendar.showNextMonth()
        self._update_month_label()
        self._refresh_events()

    def _go_today(self):
        self._calendar.showToday()
        self._calendar.setSelectedDate(QDate.currentDate())
        self._selected_date = QDate.currentDate()
        self._update_month_label()
        self._refresh_events()
        self._event_list.set_date(self._selected_date)

    def _on_date_clicked(self, date: QDate):
        self._selected_date = date
        self._event_list.set_date(date)
        self._detail_panel.clear()

    def _on_page_changed(self, year: int, month: int):
        self._update_month_label()
        self._refresh_events()

    def _on_event_selected(self, event_id: int):
        ev = CalendarEvent.get_by_id(event_id)
        if ev:
            self._detail_panel.load_event(ev)
        else:
            self._detail_panel.clear()

    def _on_edit_requested(self, event_id: int):
        ev = CalendarEvent.get_by_id(event_id)
        if ev:
            dialog = EventEditDialog(self, event=ev)
            dialog.event_saved.connect(self._on_event_saved)
            dialog.exec()

    def _on_delete_requested(self, event_id: int):
        reply = QMessageBox.question(
            self,
            "删除事件",
            "确定要删除此事件吗？",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            ev = CalendarEvent.get_by_id(event_id)
            if ev:
                ev.delete()
                self._detail_panel.clear()
                self._refresh_events()
                self._event_list.refresh(self._selected_date)

    def _create_event(self):
        dialog = EventEditDialog(self, initial_date=self._selected_date)
        dialog.event_saved.connect(self._on_event_saved)
        dialog.exec()

    def _on_event_saved(self, event_id: int):
        self.event_created.emit(event_id)
        self._refresh_events()
        self._event_list.refresh(self._selected_date)
        ev = CalendarEvent.get_by_id(event_id)
        if ev:
            self._detail_panel.load_event(ev)

    def _refresh_events(self):
        year = self._calendar.yearShown()
        month = self._calendar.monthShown()
        first = QDate(year, month, 1)
        last = first.addMonths(1).addDays(-1)

        start_str = first.toString("yyyy-MM-dd") + "T00:00:00"
        end_str = last.toString("yyyy-MM-dd") + "T23:59:59"

        events = CalendarEvent.get_by_date_range(start_str, end_str)

        event_dates: dict[str, str] = {}
        for ev in events:
            if ev.start_time:
                try:
                    dt = datetime.fromisoformat(ev.start_time.replace("Z", "+00:00"))
                    key = dt.strftime("%Y-%m-%d")
                    if key not in event_dates:
                        event_dates[key] = ev.color if ev.color else CATPPUCCIN_ACCENT
                except (ValueError, TypeError):
                    pass

        self._calendar.set_event_dates(event_dates)
