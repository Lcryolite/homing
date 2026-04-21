from __future__ import annotations

import os
import mimetypes
from typing import List, Optional, Tuple

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QFrame,
    QScrollArea,
    QMessageBox,
    QFileDialog,
    QMenu,
)
from PyQt6.QtGui import (
    QFont,
    QDragEnterEvent,
    QDropEvent,
    QContextMenuEvent,
    QIcon,
)


class AttachmentItem(QFrame):
    """单个附件项"""

    remove_clicked = pyqtSignal()
    preview_clicked = pyqtSignal()

    def __init__(self, file_path: str, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.file_path = file_path
        self.file_name = os.path.basename(file_path)
        self.file_size = self._get_file_size()
        self.file_type = (
            mimetypes.guess_type(file_path)[0] or "application/octet-stream"
        )

        self._setup_ui()

    def _get_file_size(self) -> str:
        """获取文件大小并格式化"""
        try:
            size = os.path.getsize(self.file_path)
            if size < 1024:
                return f"{size} B"
            elif size < 1024 * 1024:
                return f"{size / 1024:.1f} KB"
            elif size < 1024 * 1024 * 1024:
                return f"{size / (1024 * 1024):.1f} MB"
            else:
                return f"{size / (1024 * 1024 * 1024):.1f} GB"
        except Exception:
            return "未知大小"

    def _setup_ui(self):
        self.setFrameStyle(QFrame.Shape.Box)
        self.setStyleSheet("""
            AttachmentItem {
                background: #313244;
                border: 1px solid #45475a;
                border-radius: 6px;
                padding: 8px;
                margin: 2px;
            }
            AttachmentItem:hover {
                background: #45475a;
                border-color: #6C665F;
            }
        """)

        layout = QHBoxLayout(self)
        layout.setSpacing(8)
        layout.setContentsMargins(8, 8, 8, 8)

        # 文件图标
        icon_label = QLabel()
        icon_label.setFixedSize(24, 24)

        # 根据文件类型设置不同的图标
        icon = self._get_file_icon()
        if icon:
            icon_label.setPixmap(icon.pixmap(24, 24))
        else:
            icon_label.setText("📎")

        layout.addWidget(icon_label)

        # 文件信息
        file_layout = QVBoxLayout()
        file_layout.setSpacing(2)

        name_label = QLabel(self.file_name)
        name_label.setStyleSheet("font-weight: bold;")
        name_label.setToolTip(self.file_name)
        file_layout.addWidget(name_label)

        info_label = QLabel(f"{self.file_size} • {self.file_type.split('/')[0]}")
        info_label.setStyleSheet("font-size: 11px; color: #6C665F;")
        file_layout.addWidget(info_label)

        layout.addLayout(file_layout)
        layout.addStretch()

        # 操作按钮
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(4)

        if self._can_preview():
            preview_btn = QPushButton("预览")
            preview_btn.setFixedSize(60, 24)
            preview_btn.clicked.connect(self.preview_clicked.emit)
            preview_btn.setStyleSheet("""
                QPushButton {
                    font-size: 11px;
                    padding: 2px 8px;
                }
            """)
            btn_layout.addWidget(preview_btn)

        remove_btn = QPushButton("删除")
        remove_btn.setFixedSize(60, 24)
        remove_btn.clicked.connect(self.remove_clicked.emit)
        remove_btn.setStyleSheet("""
            QPushButton {
                font-size: 11px;
                padding: 2px 8px;
                background: #C97850;
                color: #141413;
                border: none;
                border-radius: 3px;
            }
            QPushButton:hover {
                background: #7D9174;
            }
        """)
        btn_layout.addWidget(remove_btn)

        layout.addLayout(btn_layout)

    def _get_file_icon(self) -> Optional[QIcon]:
        """获取文件图标"""
        # 这里可以扩展为根据文件类型返回不同的图标
        # 目前使用系统图标或备用文本
        return None

    def _can_preview(self) -> bool:
        """检查文件是否可以预览"""
        preview_types = [
            "image/",
            "text/",
            "application/pdf",
            "application/json",
            "application/xml",
        ]
        return any(self.file_type.startswith(t) for t in preview_types)


class AttachmentManager(QWidget):
    """附件管理器组件"""

    attachments_changed = pyqtSignal(list)  # 发送附件路径列表
    max_size_reached = pyqtSignal()  # 附件总大小超限信号

    def __init__(
        self, parent: Optional[QWidget] = None, max_total_size: int = 50 * 1024 * 1024
    ):
        super().__init__(parent)
        self.max_total_size = max_total_size  # 默认50MB限制
        self.attachments: List[AttachmentItem] = []
        self.total_size = 0

        self._setup_ui()
        self.setAcceptDrops(True)

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(12)
        layout.setContentsMargins(0, 0, 0, 0)

        # 标题栏
        title_frame = QFrame()
        title_frame.setFrameStyle(QFrame.Shape.NoFrame)
        title_layout = QHBoxLayout(title_frame)
        title_layout.setContentsMargins(0, 0, 0, 0)

        title_label = QLabel("附件")
        title_label.setFont(QFont("", 11, QFont.Weight.Bold))
        title_layout.addWidget(title_label)

        self.status_label = QLabel("0个文件 (0 B)")
        self.status_label.setStyleSheet("font-size: 11px; color: #6C665F;")
        title_layout.addWidget(self.status_label)

        title_layout.addStretch()

        add_btn = QPushButton("添加附件")
        add_btn.clicked.connect(self._add_attachments)
        add_btn.setFixedSize(80, 24)
        title_layout.addWidget(add_btn)

        layout.addWidget(title_frame)

        # 附件显示区域
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setFrameStyle(QFrame.Shape.NoFrame)
        self.scroll_area.setStyleSheet("""
            QScrollArea {
                background: #1e1e2e;
                border: 1px solid #45475a;
                border-radius: 6px;
            }
            QScrollArea > QWidget > QWidget {
                background: transparent;
            }
        """)

        self.attachments_widget = QWidget()
        self.attachments_layout = QVBoxLayout(self.attachments_widget)
        self.attachments_layout.setSpacing(4)
        self.attachments_layout.setContentsMargins(8, 8, 8, 8)
        self.attachments_layout.addStretch()

        self.scroll_area.setWidget(self.attachments_widget)
        layout.addWidget(self.scroll_area)

        # 提示信息
        self.help_label = QLabel("📎 提示：将文件拖放到此区域，或点击「添加附件」按钮")
        self.help_label.setStyleSheet("""
            font-size: 11px;
            color: #6C665F;
            background: #313244;
            padding: 8px;
            border-radius: 4px;
        """)
        self.help_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.help_label)

    def dragEnterEvent(self, event: QDragEnterEvent):
        """拖拽进入事件"""
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
            self.setStyleSheet("""
                AttachmentManager {
                    border: 2px dashed #7C8A9A;
                    border-radius: 6px;
                    background: rgba(137, 180, 250, 0.1);
                }
            """)
        else:
            event.ignore()

    def dragLeaveEvent(self, event: QDragEnterEvent):
        """拖拽离开事件"""
        self.setStyleSheet("")

    def dropEvent(self, event: QDropEvent):
        """释放拖拽文件事件"""
        self.setStyleSheet("")

        urls = event.mimeData().urls()
        if not urls:
            return

        file_paths = []
        for url in urls:
            if url.isLocalFile():
                file_path = url.toLocalFile()
                if os.path.isfile(file_path):
                    file_paths.append(file_path)

        if file_paths:
            self.add_attachments(file_paths)

        event.acceptProposedAction()

    def contextMenuEvent(self, event: QContextMenuEvent):
        """右键菜单事件"""
        menu = QMenu(self)

        add_action = menu.addAction("添加附件...")
        add_action.triggered.connect(self._add_attachments)

        if self.attachments:
            menu.addSeparator()
            clear_action = menu.addAction("清除所有附件")
            clear_action.triggered.connect(self.clear_attachments)

        menu.exec(event.globalPos())

    def _add_attachments(self):
        """添加附件文件"""
        file_dialog = QFileDialog(self)
        file_dialog.setWindowTitle("选择附件文件")
        file_dialog.setFileMode(QFileDialog.FileMode.ExistingFiles)
        file_dialog.setNameFilter("所有文件 (*.*)")

        if file_dialog.exec():
            file_paths = file_dialog.selectedFiles()
            if file_paths:
                self.add_attachments(file_paths)

    def add_attachments(self, file_paths: List[str]) -> List[str]:
        """添加附件"""
        added_paths = []

        for file_path in file_paths:
            # 检查文件大小
            try:
                file_size = os.path.getsize(file_path)
            except Exception:
                QMessageBox.warning(
                    self, "错误", f"无法读取文件：{os.path.basename(file_path)}"
                )
                continue

            # 检查单个文件大小（限制为20MB）
            if file_size > 20 * 1024 * 1024:
                QMessageBox.warning(
                    self, "大小限制", f"{os.path.basename(file_path)} 超过20MB限制"
                )
                continue

            # 检查总大小
            if self.total_size + file_size > self.max_total_size:
                QMessageBox.warning(self, "大小限制", "附件总大小超过限制")
                self.max_size_reached.emit()
                break

            # 检查重复文件
            if any(item.file_path == file_path for item in self.attachments):
                QMessageBox.information(
                    self, "提示", f"{os.path.basename(file_path)} 已添加"
                )
                continue

            # 创建附件项
            item = AttachmentItem(file_path)
            item.remove_clicked.connect(
                lambda _, p=file_path: self._remove_attachment(p)
            )
            if item._can_preview():
                item.preview_clicked.connect(
                    lambda _, p=file_path: self._preview_attachment(p)
                )

            self.attachments.append(item)
            self.attachments_layout.insertWidget(len(self.attachments) - 1, item)
            self.total_size += file_size
            added_paths.append(file_path)

        self._update_status()

        # 如果没有附件则显示帮助信息
        if self.attachments:
            self.help_label.hide()
        else:
            self.help_label.show()

        return added_paths

    def _remove_attachment(self, file_path: str):
        """删除附件"""
        for i, item in enumerate(self.attachments):
            if item.file_path == file_path:
                # 更新总大小
                try:
                    file_size = os.path.getsize(file_path)
                    self.total_size -= file_size
                except Exception:
                    pass

                # 删除UI项
                self.attachments_layout.removeWidget(item)
                item.deleteLater()
                self.attachments.pop(i)
                break

        self._update_status()

        # 如果没有附件则显示帮助信息
        if not self.attachments:
            self.help_label.show()

    def _preview_attachment(self, file_path: str):
        """预览附件"""
        from openemail.ui.mail.attachment_preview import AttachmentPreviewDialog

        dialog = AttachmentPreviewDialog(file_path, self)
        dialog.exec()

    def clear_attachments(self):
        """清除所有附件"""
        if not self.attachments:
            return

        # 确认对话框
        reply = QMessageBox.question(
            self,
            "确认清除",
            f"确定要删除 {len(self.attachments)} 个附件吗？",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )

        if reply == QMessageBox.StandardButton.Yes:
            # 删除所有附件项
            for item in self.attachments:
                self.attachments_layout.removeWidget(item)
                item.deleteLater()

            self.attachments.clear()
            self.total_size = 0
            self._update_status()
            self.help_label.show()

    def _update_status(self):
        """更新状态显示"""
        count = len(self.attachments)
        size_text = ""

        if self.total_size < 1024:
            size_text = f"{self.total_size} B"
        elif self.total_size < 1024 * 1024:
            size_text = f"{self.total_size / 1024:.1f} KB"
        elif self.total_size < 1024 * 1024 * 1024:
            size_text = f"{self.total_size / (1024 * 1024):.1f} MB"
        else:
            size_text = f"{self.total_size / (1024 * 1024 * 1024):.1f} GB"

        self.status_label.setText(f"{count}个文件 ({size_text})")
        self.attachments_changed.emit([item.file_path for item in self.attachments])

        # 如果接近大小限制，显示警告
        if self.total_size > self.max_total_size * 0.9:
            self.status_label.setStyleSheet(
                "font-size: 11px; color: #C97850; font-weight: bold;"
            )
        else:
            self.status_label.setStyleSheet("font-size: 11px; color: #6C665F;")

    def get_attachment_paths(self) -> List[str]:
        """获取所有附件路径"""
        return [item.file_path for item in self.attachments]

    def get_attachment_info(self) -> List[Tuple[str, str, int]]:
        """获取附件信息列表：文件名, MIME类型, 大小"""
        info_list = []
        for item in self.attachments:
            try:
                size = os.path.getsize(item.file_path)
                info_list.append((item.file_name, item.file_type, size))
            except Exception:
                pass
        return info_list
