from __future__ import annotations

from typing import Optional

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QFrame,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QHeaderView,
    QTextEdit,
    QScrollArea,
    QGroupBox,
)
from PyQt6.QtGui import QFont

from openemail.models.contact import Contact


class ContactDetailWidget(QWidget):
    """联系人详情视图"""

    edit_requested = pyqtSignal(int)  # contact_id
    email_requested = pyqtSignal(str)  # email_address

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self._contact: Optional[Contact] = None
        self._setup_ui()
        self.clear()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(0)
        layout.setContentsMargins(0, 0, 0, 0)

        # 工具栏
        toolbar = QFrame()
        toolbar.setFrameStyle(QFrame.Shape.Box)
        toolbar.setStyleSheet("""
            QFrame {
                background: #FBF8F3;
                border: 1px solid #E8E1D8;
                border-bottom: none;
                padding: 12px;
            }
        """)

        toolbar_layout = QHBoxLayout(toolbar)
        toolbar_layout.setContentsMargins(0, 0, 0, 0)
        toolbar_layout.setSpacing(12)

        self.edit_btn = QPushButton("编辑")
        self.edit_btn.clicked.connect(self._on_edit)
        self.edit_btn.setEnabled(False)
        toolbar_layout.addWidget(self.edit_btn)

        self.email_btn = QPushButton("写邮件")
        self.email_btn.clicked.connect(self._on_send_email)
        self.email_btn.setEnabled(False)
        toolbar_layout.addWidget(self.email_btn)

        toolbar_layout.addStretch()

        layout.addWidget(toolbar)

        # 主内容区域
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setFrameStyle(QFrame.Shape.NoFrame)
        self.scroll_area.setStyleSheet("""
            QScrollArea {
                background: #F7F4EE;
                border: 1px solid #E8E1D8;
                border-top: none;
            }
            QScrollArea > QWidget > QWidget {
                background: transparent;
            }
        """)

        self.content_widget = QWidget()
        self.content_layout = QVBoxLayout(self.content_widget)
        self.content_layout.setSpacing(16)
        self.content_layout.setContentsMargins(24, 24, 24, 24)

        self.scroll_area.setWidget(self.content_widget)
        layout.addWidget(self.scroll_area, 1)

        # 占位文本
        self.placeholder_label = QLabel("选择联系人查看详情")
        self.placeholder_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.placeholder_label.setStyleSheet("""
            QLabel {
                font-size: 14px;
                color: #6C665F;
                padding: 40px;
            }
        """)
        self.content_layout.addWidget(self.placeholder_label)

        # 初始化其他部件（默认隐藏）
        self._init_profile_section()
        self._init_contact_info_section()
        self._init_notes_section()
        self._init_related_emails_section()

        # 默认隐藏这些部件
        self.profile_section.setVisible(False)
        self.contact_info_section.setVisible(False)
        self.notes_section.setVisible(False)
        self.related_emails_section.setVisible(False)

    def _init_profile_section(self):
        """初始化个人信息部分"""
        self.profile_section = QFrame()
        self.profile_section.setFrameStyle(QFrame.Shape.Box)
        self.profile_section.setStyleSheet("""
            QFrame {
                background: #FBF8F3;
                border: 1px solid #E8E1D8;
                border-radius: 8px;
                padding: 20px;
            }
        """)

        profile_layout = QHBoxLayout(self.profile_section)
        profile_layout.setSpacing(20)

        # 头像
        self.avatar_label = QLabel()
        self.avatar_label.setFixedSize(80, 80)
        self.avatar_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.avatar_label.setStyleSheet("""
            QLabel {
                background: #6C665F;
                color: #141413;
                border-radius: 40px;
                font-size: 32px;
                font-weight: bold;
            }
        """)
        profile_layout.addWidget(self.avatar_label)

        # 姓名和基本信息
        info_layout = QVBoxLayout()
        info_layout.setSpacing(8)

        self.name_label = QLabel()
        self.name_label.setFont(QFont("", 18, QFont.Weight.Bold))
        self.name_label.setStyleSheet("")
        info_layout.addWidget(self.name_label)

        self.email_label = QLabel()
        self.email_label.setStyleSheet("color: #7C8A9A; font-size: 14px;")
        info_layout.addWidget(self.email_label)

        self.company_label = QLabel()
        self.company_label.setStyleSheet("font-size: 13px;")
        info_layout.addWidget(self.company_label)

        info_layout.addStretch()

        # 标签区域
        self.tags_label = QLabel()
        self.tags_label.setStyleSheet("color: #C97850; font-size: 12px;")
        info_layout.addWidget(self.tags_label)

        profile_layout.addLayout(info_layout, 1)

        # 右侧：操作按钮
        action_layout = QVBoxLayout()
        action_layout.setSpacing(8)

        self.favorite_btn = QPushButton("★ 收藏")
        self.favorite_btn.setCheckable(True)
        self.favorite_btn.clicked.connect(self._toggle_favorite)
        self.favorite_btn.setFixedWidth(100)
        action_layout.addWidget(self.favorite_btn)

        action_layout.addStretch()
        profile_layout.addLayout(action_layout)

        self.content_layout.addWidget(self.profile_section)

    def _init_contact_info_section(self):
        """初始化联系信息部分"""
        self.contact_info_section = QGroupBox("联系信息")
        self.contact_info_section.setStyleSheet("""
            QGroupBox {
                font-weight: bold;
                font-size: 14px;
                border: 1px solid #E8E1D8;
                border-radius: 6px;
                padding-top: 10px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px 0 5px;
                color: #7C8A9A;
            }
        """)

        info_layout = QVBoxLayout(self.contact_info_section)
        info_layout.setSpacing(8)
        info_layout.setContentsMargins(16, 20, 16, 16)

        # 创建信息行
        self.phone_row = self._create_info_row("电话:", "")
        self.mobile_row = self._create_info_row("手机:", "")
        self.company_row = self._create_info_row("公司:", "")
        self.job_title_row = self._create_info_row("职位:", "")
        self.address_row = self._create_info_row("地址:", "")

        info_layout.addWidget(self.phone_row)
        info_layout.addWidget(self.mobile_row)
        info_layout.addWidget(self.company_row)
        info_layout.addWidget(self.job_title_row)
        info_layout.addWidget(self.address_row)

        self.content_layout.addWidget(self.contact_info_section)

    def _init_notes_section(self):
        """初始化备注部分"""
        self.notes_section = QGroupBox("备注")
        self.notes_section.setStyleSheet(self.contact_info_section.styleSheet())

        notes_layout = QVBoxLayout(self.notes_section)
        notes_layout.setContentsMargins(16, 20, 16, 16)

        self.notes_text = QTextEdit()
        self.notes_text.setReadOnly(True)
        self.notes_text.setMaximumHeight(100)
        self.notes_text.setStyleSheet("""
            QTextEdit {
                background: #F7F4EE;
                color: #141413;
                border: 1px solid #6C665F;
                border-radius: 4px;
                padding: 8px;
            }
        """)
        notes_layout.addWidget(self.notes_text)

        self.content_layout.addWidget(self.notes_section)

    def _init_related_emails_section(self):
        """初始化相关邮件部分"""
        self.related_emails_section = QGroupBox("相关邮件")
        self.related_emails_section.setStyleSheet(
            self.contact_info_section.styleSheet()
        )

        emails_layout = QVBoxLayout(self.related_emails_section)
        emails_layout.setContentsMargins(16, 20, 16, 16)

        self.emails_table = QTableWidget()
        self.emails_table.setColumnCount(4)
        self.emails_table.setHorizontalHeaderLabels(["主题", "日期", "状态", "操作"])
        self.emails_table.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.Stretch
        )
        self.emails_table.horizontalHeader().setSectionResizeMode(
            1, QHeaderView.ResizeMode.ResizeToContents
        )
        self.emails_table.horizontalHeader().setSectionResizeMode(
            2, QHeaderView.ResizeMode.ResizeToContents
        )
        self.emails_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.emails_table.setMaximumHeight(200)

        emails_layout.addWidget(self.emails_table)

        self.content_layout.addWidget(self.related_emails_section)

    def _create_info_row(self, label_text: str, value_text: str) -> QWidget:
        """创建信息行部件"""
        row = QWidget()
        row_layout = QHBoxLayout(row)
        row_layout.setContentsMargins(0, 0, 0, 0)
        row_layout.setSpacing(12)

        label = QLabel(label_text)
        label.setStyleSheet("font-weight: bold; min-width: 60px;")
        row_layout.addWidget(label)

        value = QLabel(value_text)
        value.setStyleSheet("")
        value.setWordWrap(True)
        row_layout.addWidget(value, 1)

        return row

    def load_contact(self, contact: Contact):
        """加载联系人数据"""
        self._contact = contact

        # 隐藏占位文本，显示内容
        self.placeholder_label.setVisible(False)
        self.profile_section.setVisible(True)
        self.contact_info_section.setVisible(True)
        self.notes_section.setVisible(True)
        self.related_emails_section.setVisible(True)

        # 启用按钮
        self.edit_btn.setEnabled(True)
        self.email_btn.setEnabled(True)

        # 更新个人信息
        self._update_profile_section()
        self._update_contact_info_section()
        self._update_notes_section()
        self._update_related_emails()

    def clear(self):
        """清除显示"""
        self._contact = None

        # 显示占位文本，隐藏内容
        self.placeholder_label.setVisible(True)
        self.profile_section.setVisible(False)
        self.contact_info_section.setVisible(False)
        self.notes_section.setVisible(False)
        self.related_emails_section.setVisible(False)

        # 禁用按钮
        self.edit_btn.setEnabled(False)
        self.email_btn.setEnabled(False)

    def _update_profile_section(self):
        """更新个人信息部分"""
        if not self._contact:
            return

        # 头像
        self.avatar_label.setText(self._contact.initials)

        # 姓名
        self.name_label.setText(self._contact.display_name)

        # 邮箱
        self.email_label.setText(self._contact.email)

        # 公司
        if self._contact.company:
            self.company_label.setText(self._contact.company)
            if self._contact.job_title:
                self.company_label.setText(
                    f"{self._contact.company} • {self._contact.job_title}"
                )
        else:
            self.company_label.setText("")

        # 标签
        if self._contact.tags:
            tags_text = "标签: " + ", ".join([f"#{tag}" for tag in self._contact.tags])
            self.tags_label.setText(tags_text)
        else:
            self.tags_label.setText("")

        # 收藏按钮
        self.favorite_btn.setChecked(self._contact.is_favorite)
        self.favorite_btn.setText("★ 已收藏" if self._contact.is_favorite else "☆ 收藏")

    def _update_contact_info_section(self):
        """更新联系信息部分"""
        if not self._contact:
            return

        # 更新各个信息行的值
        self._update_info_row(self.phone_row, 1, self._contact.phone or "未设置")
        self._update_info_row(self.mobile_row, 1, self._contact.mobile or "未设置")
        self._update_info_row(self.company_row, 1, self._contact.company or "未设置")
        self._update_info_row(
            self.job_title_row, 1, self._contact.job_title or "未设置"
        )
        self._update_info_row(self.address_row, 1, self._contact.address or "未设置")

    def _update_info_row(self, row: QWidget, value_index: int, text: str):
        """更新信息行的值"""
        layout = row.layout()
        if layout:
            value_widget = layout.itemAt(value_index).widget()
            if value_widget and isinstance(value_widget, QLabel):
                value_widget.setText(text)

    def _update_notes_section(self):
        """更新备注部分"""
        if not self._contact:
            return

        if self._contact.notes:
            self.notes_text.setText(self._contact.notes)
            self.notes_section.setVisible(True)
        else:
            self.notes_text.setText("")
            self.notes_section.setVisible(False)

    def _update_related_emails(self):
        """更新相关邮件"""
        if not self._contact:
            return

        emails = self._contact.get_related_emails(limit=10)

        if emails:
            self.emails_table.setRowCount(len(emails))

            for i, email_info in enumerate(emails):
                # 主题
                subject_item = QTableWidgetItem(email_info["subject"][:50])
                subject_item.setToolTip(email_info["subject"])
                self.emails_table.setItem(i, 0, subject_item)

                # 日期
                date_item = QTableWidgetItem(email_info["date"])
                self.emails_table.setItem(i, 1, date_item)

                # 状态
                status_text = "已读" if email_info["is_read"] else "未读"
                if email_info["has_attachment"]:
                    status_text += " 📎"
                status_item = QTableWidgetItem(status_text)
                self.emails_table.setItem(i, 2, status_item)

                # 操作按钮（占位）
                action_item = QTableWidgetItem("查看")
                self.emails_table.setItem(i, 3, action_item)

            self.related_emails_section.setVisible(True)
        else:
            self.emails_table.setRowCount(0)
            self.related_emails_section.setVisible(False)

    def _on_edit(self):
        """编辑联系人"""
        if self._contact:
            self.edit_requested.emit(self._contact.id)

    def _on_send_email(self):
        """发送邮件"""
        if self._contact and self._contact.email:
            self.email_requested.emit(self._contact.email)

    def _toggle_favorite(self):
        """切换收藏状态"""
        if self._contact:
            self._contact.is_favorite = not self._contact.is_favorite
            self._contact.save()

            # 更新按钮状态
            self.favorite_btn.setChecked(self._contact.is_favorite)
            self.favorite_btn.setText(
                "★ 已收藏" if self._contact.is_favorite else "☆ 收藏"
            )
