from PyQt6.QtCore import pyqtSignal, QTimer
from PyQt6.QtWidgets import QHBoxLayout, QLineEdit, QPushButton, QWidget


class SearchBar(QWidget):
    search_requested = pyqtSignal(str)
    search_cleared = pyqtSignal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._setup_ui()

    def _setup_ui(self) -> None:
        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 4, 8, 4)
        layout.setSpacing(4)

        self._input = QLineEdit()
        self._input.setPlaceholderText("搜索邮件 (主题/发件人/内容)...")
        self._input.setClearButtonEnabled(True)
        self._input.textChanged.connect(self._on_text_changed)
        self._input.returnPressed.connect(self._on_search)
        layout.addWidget(self._input, 1)

        self._search_btn = QPushButton("搜索")
        self._search_btn.setProperty("class", "primary")
        self._search_btn.clicked.connect(self._on_search)
        layout.addWidget(self._search_btn)

        self._clear_btn = QPushButton("清除")
        self._clear_btn.clicked.connect(self._clear)
        layout.addWidget(self._clear_btn)

        self._debounce_timer = QTimer()
        self._debounce_timer.setSingleShot(True)
        self._debounce_timer.setInterval(500)
        self._debounce_timer.timeout.connect(self._on_debounced_search)

    def _on_text_changed(self, text: str) -> None:
        if not text:
            self.search_cleared.emit()
        else:
            self._debounce_timer.start()

    def _on_debounced_search(self) -> None:
        text = self._input.text().strip()
        if text:
            self.search_requested.emit(text)

    def _on_search(self) -> None:
        text = self._input.text().strip()
        if text:
            self.search_requested.emit(text)

    def _clear(self) -> None:
        self._input.clear()
        self.search_cleared.emit()

    def set_focus(self) -> None:
        self._input.setFocus()
