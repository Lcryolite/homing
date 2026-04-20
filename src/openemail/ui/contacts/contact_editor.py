from __future__ import annotations

from typing import Optional

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QFormLayout,
    QLabel,
    QLineEdit,
    QTextEdit,
    QPushButton,
    QFrame,
    QComboBox,
    QCheckBox,
    QGroupBox,
    QMessageBox,
    QFileDialog,
)
from PyQt6.QtGui import QFont, QPixmap, QIcon

from openemail.models.contact import Contact
from openemail.models.account import Account


class ContactEditorDialog(QDialog):
    """联系人编辑器对话框"""

    contact_saved = pyqtSignal(int)  # contact_id

    def __init__(
        self, account: Optional[Account], parent=None, contact: Optional[Contact] = None
    ):
        super().__init__(parent)
        self._account = account
        self._contact = contact or Contact(account_id=account.id if account else None)
        self._is_new = contact is None

        self.setWindowTitle("新建联系人" if self._is_new else "编辑联系人")
        self.setMinimumSize(500, 600)
        self._setup_ui()
        self._load_contact_data()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(16)
        layout.setContentsMargins(24, 24, 24, 24)

        # 标题
        title_label = QLabel("联系人信息")
        title_label.setFont(QFont("", 18, QFont.Weight.Bold))
        title_label.setStyleSheet("color: #89b4fa; margin-bottom: 8px;")
        layout.addWidget(title_label)

        # 头像区域
        avatar_frame = QFrame()
        avatar_frame.setFrameStyle(QFrame.Shape.Box)
        avatar_frame.setStyleSheet("""
            QFrame {
                background: #313244;
                border: 2px solid #45475a;
                border-radius: 8px;
                padding: 20px;
            }
        """)
        avatar_layout = QHBoxLayout(avatar_frame)
        avatar_layout.setSpacing(20)

        # 头像显示
        self.avatar_label = QLabel()
        self.avatar_label.setFixedSize(80, 80)
        self.avatar_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.avatar_label.setStyleSheet("""
            QLabel {
                background: #585b70;
                color: #cdd6f4;
                border-radius: 40px;
                font-size: 32px;
                font-weight: bold;
            }
        """)
        avatar_layout.addWidget(self.avatar_label)

        # 头像操作按钮
        avatar_btn_layout = QVBoxLayout()
        avatar_btn_layout.setSpacing(8)

        self.change_avatar_btn = QPushButton("更改头像")
        self.change_avatar_btn.clicked.connect(self._change_avatar)
        self.change_avatar_btn.setMinimumWidth(100)
        avatar_btn_layout.addWidget(self.change_avatar_btn)

        self.clear_avatar_btn = QPushButton("清除头像")
        self.clear_avatar_btn.clicked.connect(self._clear_avatar)
        self.clear_avatar_btn.setMinimumWidth(100)
        avatar_btn_layout.addWidget(self.clear_avatar_btn)

        avatar_layout.addLayout(avatar_btn_layout)
        avatar_layout.addStretch()

        layout.addWidget(avatar_frame)

        # 基本信息表单
        form_group = QGroupBox("基本信息")
        form_group.setStyleSheet("""
            QGroupBox {
                font-weight: bold;
                font-size: 14px;
                border: 1px solid #45475a;
                border-radius: 6px;
                margin-top: 12px;
                padding-top: 10px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px 0 5px;
            }
        """)

        form_layout = QFormLayout(form_group)
        form_layout.setSpacing(12)
        form_layout.setContentsMargins(16, 20, 16, 20)

        # 姓名
        self.name_edit = QLineEdit()
        self.name_edit.setPlaceholderText("输入姓名")
        self.name_edit.textChanged.connect(self._update_avatar_initials)
        form_layout.addRow("姓名:", self.name_edit)

        # 邮箱
        self.email_edit = QLineEdit()
        self.email_edit.setPlaceholderText("example@domain.com")
        form_layout.addRow("邮箱:", self.email_edit)

        # 电话
        self.phone_edit = QLineEdit()
        self.phone_edit.setPlaceholderText("工作电话")
        form_layout.addRow("工作电话:", self.phone_edit)

        # 手机
        self.mobile_edit = QLineEdit()
        self.mobile_edit.setPlaceholderText("手机号码")
        form_layout.addRow("手机:", self.mobile_edit)

        # 公司
        self.company_edit = QLineEdit()
        self.company_edit.setPlaceholderText("公司名称")
        form_layout.addRow("公司:", self.company_edit)

        # 职位
        self.job_title_edit = QLineEdit()
        self.job_title_edit.setPlaceholderText("职位/头衔")
        form_layout.addRow("职位:", self.job_title_edit)

        # 地址
        self.address_edit = QLineEdit()
        self.address_edit.setPlaceholderText("地址")
        form_layout.addRow("地址:", self.address_edit)

        layout.addWidget(form_group)

        # 备注区域
        notes_group = QGroupBox("备注")
        notes_group.setStyleSheet(form_group.styleSheet())

        notes_layout = QVBoxLayout(notes_group)
        notes_layout.setContentsMargins(16, 20, 16, 16)

        self.notes_edit = QTextEdit()
        self.notes_edit.setPlaceholderText("添加备注信息...")
        self.notes_edit.setMaximumHeight(100)
        self.notes_edit.setAcceptRichText(False)
        notes_layout.addWidget(self.notes_edit)

        layout.addWidget(notes_group)

        # 标签区域
        tags_group = QGroupBox("标签")
        tags_group.setStyleSheet(form_group.styleSheet())

        tags_layout = QVBoxLayout(tags_group)
        tags_layout.setContentsMargins(16, 20, 16, 16)

        self.tags_edit = QLineEdit()
        self.tags_edit.setPlaceholderText("用逗号分隔标签，例如：同事,朋友,家人")
        tags_layout.addWidget(self.tags_edit)

        layout.addWidget(tags_group)

        # 选项区域
        options_layout = QHBoxLayout()

        self.favorite_check = QCheckBox("收藏联系人")
        self.favorite_check.setStyleSheet("font-size: 13px;")
        options_layout.addWidget(self.favorite_check)

        options_layout.addStretch()
        layout.addLayout(options_layout)

        # 按钮区域
        button_layout = QHBoxLayout()
        button_layout.setSpacing(12)

        self.save_btn = QPushButton("保存")
        self.save_btn.setProperty("class", "primary")
        self.save_btn.setMinimumWidth(100)
        self.save_btn.clicked.connect(self._save_contact)
        button_layout.addWidget(self.save_btn)

        self.save_and_new_btn = QPushButton("保存并新建")
        self.save_and_new_btn.setMinimumWidth(100)
        self.save_and_new_btn.clicked.connect(self._save_and_new)
        button_layout.addWidget(self.save_and_new_btn)

        button_layout.addStretch()

        cancel_btn = QPushButton("取消")
        cancel_btn.setMinimumWidth(80)
        cancel_btn.clicked.connect(self.reject)
        button_layout.addWidget(cancel_btn)

        layout.addLayout(button_layout)

    def _load_contact_data(self):
        """加载联系人数据到表单"""
        if not self._is_new:
            self.name_edit.setText(self._contact.name or "")
            self.email_edit.setText(self._contact.email or "")
            self.phone_edit.setText(self._contact.phone or "")
            self.mobile_edit.setText(self._contact.mobile or "")
            self.company_edit.setText(self._contact.company or "")
            self.job_title_edit.setText(self._contact.job_title or "")
            self.address_edit.setText(self._contact.address or "")
            self.notes_edit.setText(self._contact.notes or "")
            self.tags_edit.setText(", ".join(self._contact.tags))
            self.favorite_check.setChecked(self._contact.is_favorite)

        # 更新头像显示
        self._update_avatar_initials()

    def _update_avatar_initials(self):
        """更新头像首字母显示"""
        initials = self._contact.initials
        if self.name_edit.text():
            # 根据当前输入的名称计算首字母
            name = self.name_edit.text()
            if any("\u4e00" <= c <= "\u9fff" for c in name):
                initials = name[0]
            else:
                parts = name.split()
                if len(parts) >= 2:
                    initials = (parts[0][0] + parts[-1][0]).upper()
                elif len(parts) == 1:
                    initials = parts[0][0].upper()

        self.avatar_label.setText(initials)

    def _change_avatar(self):
        """更改头像"""
        file_dialog = QFileDialog(self)
        file_dialog.setWindowTitle("选择头像")
        file_dialog.setFileMode(QFileDialog.FileMode.ExistingFile)
        file_dialog.setNameFilter(
            "图片文件 (*.png *.jpg *.jpeg *.gif *.bmp);;所有文件 (*.*)"
        )

        if file_dialog.exec():
            file_path = file_dialog.selectedFiles()[0]

            # 验证文件大小
            import os

            if os.path.getsize(file_path) > 2 * 1024 * 1024:  # 2MB限制
                QMessageBox.warning(self, "文件过大", "头像文件不能超过2MB")
                return

            # 创建头像缩略图
            pixmap = QPixmap(file_path)
            if pixmap.isNull():
                QMessageBox.warning(self, "无效图片", "无法加载图片文件")
                return

            # 缩放并设置为圆形
            pixmap = pixmap.scaled(
                80,
                80,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )

            # 创建圆形蒙版（简化版：不实际处理，只显示方形）
            self.avatar_label.setPixmap(pixmap)

            # 保存文件路径
            self._contact.avatar_path = file_path

    def _clear_avatar(self):
        """清除头像"""
        self._contact.avatar_path = ""
        self._update_avatar_initials()

    def _save_contact(self):
        """保存联系人"""
        if not self._validate_form():
            return

        # 更新联系人数据
        self._contact.name = self.name_edit.text().strip()
        self._contact.email = self.email_edit.text().strip()
        self._contact.phone = self.phone_edit.text().strip()
        self._contact.mobile = self.mobile_edit.text().strip()
        self._contact.company = self.company_edit.text().strip()
        self._contact.job_title = self.job_title_edit.text().strip()
        self._contact.address = self.address_edit.text().strip()
        self._contact.notes = self.notes_edit.toPlainText().strip()
        self._contact.is_favorite = self.favorite_check.isChecked()

        # 处理标签
        tags_text = self.tags_edit.text().strip()
        if tags_text:
            tags = [tag.strip() for tag in tags_text.split(",")]
            self._contact.tags = [tag for tag in tags if tag]
        else:
            self._contact.tags = []

        try:
            # 保存到数据库
            contact_id = self._contact.save()

            # 如果是新联系人，增加联系频率
            if self._is_new:
                self._contact.increment_frequency()

            self.contact_saved.emit(contact_id)
            self.accept()

        except Exception as e:
            QMessageBox.critical(self, "保存失败", f"保存联系人时发生错误:\n{str(e)}")

    def _save_and_new(self):
        """保存并新建"""
        if not self._validate_form():
            return

        self._save_contact()

        # 如果保存成功，创建新的编辑器
        if self.result() == QDialog.DialogCode.Accepted:
            # 创建新的联系人对象
            new_contact = Contact(
                account_id=self._account.id if self._account else None
            )

            # 创建新的对话框
            new_dialog = ContactEditorDialog(self._account, self.parent())
            new_dialog.exec()

    def _validate_form(self) -> bool:
        """验证表单数据"""
        email = self.email_edit.text().strip()

        if not email:
            QMessageBox.warning(self, "验证错误", "邮箱地址不能为空")
            self.email_edit.setFocus()
            return False

        if "@" not in email or "." not in email.split("@")[1]:
            QMessageBox.warning(self, "验证错误", "请输入有效的邮箱地址")
            self.email_edit.setFocus()
            return False

        # 检查是否已存在相同邮箱的联系人
        if self._is_new or self._contact.email != email:
            existing = Contact.get_by_email(
                email, self._account.id if self._account else None
            )
            if existing and existing.id != self._contact.id:
                reply = QMessageBox.question(
                    self,
                    "重复联系人",
                    f"邮箱 {email} 已经存在于联系人 {existing.display_name} 中。\n是否继续保存？",
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                    QMessageBox.StandardButton.No,
                )
                if reply != QMessageBox.StandardButton.Yes:
                    return False

        return True
