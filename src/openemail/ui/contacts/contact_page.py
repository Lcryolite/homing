from __future__ import annotations

from typing import Optional

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QSplitter,
    QLabel,
    QMessageBox,
)

from openemail.models.contact import Contact
from openemail.models.account import Account
from openemail.ui.contacts.contact_manager import ContactListWidget
from openemail.ui.contacts.contact_detail import ContactDetailWidget


class ContactPageWidget(QWidget):
    """联系人页面"""

    email_requested = pyqtSignal(str)  # email_address

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self._current_account: Optional[Account] = None
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(0)
        layout.setContentsMargins(0, 0, 0, 0)

        # 标题
        self.title_label = QLabel("联系人")
        self.title_label.setStyleSheet("""
            QLabel {
                font-size: 16px;
                font-weight: bold;
                padding: 12px 16px;
                background: #313244;
                border-radius: 6px 6px 0 0;
                border-bottom: 1px solid #45475a;
            }
        """)
        layout.addWidget(self.title_label)

        # 主分割器
        splitter = QSplitter(Qt.Orientation.Horizontal)

        # 左侧：联系人列表
        self.contact_list = ContactListWidget()
        self.contact_list.contact_selected.connect(self._on_contact_selected)
        self.contact_list.contact_double_clicked.connect(
            self._on_contact_double_clicked
        )
        splitter.addWidget(self.contact_list)

        # 右侧：联系人详情
        self.contact_detail = ContactDetailWidget()
        self.contact_detail.edit_requested.connect(self._on_edit_requested)
        self.contact_detail.email_requested.connect(self.email_requested.emit)
        splitter.addWidget(self.contact_detail)

        # 设置分割器比例
        splitter.setSizes([400, 400])
        layout.addWidget(splitter, 1)

    def set_account(self, account: Optional[Account]):
        """设置当前账户"""
        self._current_account = account
        self.contact_list.set_account(account)

        # 更新标题
        if account and account.name:
            self.title_label.setText(f"联系人 - {account.name}")
        else:
            self.title_label.setText("联系人")

    def load_contacts(self):
        """加载联系人"""
        self.contact_list._load_all_contacts()  # 直接调用内部方法

    def _on_contact_selected(self, contact_id: int):
        """联系人被选中"""
        contact = Contact.get_by_id(contact_id)
        if contact:
            self.contact_detail.load_contact(contact)
        else:
            self.contact_detail.clear()

    def _on_contact_double_clicked(self, contact_id: int):
        """联系人双击"""
        contact = Contact.get_by_id(contact_id)
        if contact:
            self._show_edit_dialog(contact)

    def _on_edit_requested(self, contact_id: int):
        """编辑联系人请求"""
        contact = Contact.get_by_id(contact_id)
        if contact:
            self._show_edit_dialog(contact)

    def _show_edit_dialog(self, contact: Contact):
        """显示编辑对话框"""
        from openemail.ui.contacts.contact_editor import ContactEditorDialog

        dialog = ContactEditorDialog(self._current_account, self, contact)
        dialog.contact_saved.connect(self._on_contact_saved)
        dialog.exec()

    def _on_contact_saved(self, contact_id: int):
        """联系人保存后刷新"""
        # 刷新列表
        self.contact_list._load_all_contacts()

        # 如果当前显示的联系人被编辑，更新详情视图
        if (
            self.contact_detail._contact
            and self.contact_detail._contact.id == contact_id
        ):
            contact = Contact.get_by_id(contact_id)
            if contact:
                self.contact_detail.load_contact(contact)
