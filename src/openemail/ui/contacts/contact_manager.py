from __future__ import annotations

import logging
from typing import Optional, List

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QApplication,
    QWidget,
    QVBoxLayout,
    QSplitter,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QProgressDialog,
    QToolBar,
    QToolButton,
    QTableWidget,
    QTableWidgetItem,
    QHeaderView,
    QMessageBox,
    QFileDialog,
    QMenu,
)
from PyQt6.QtGui import QAction, QIcon

from openemail.models.contact import Contact, ContactTag
from openemail.models.account import Account

logger = logging.getLogger(__name__)


class ContactListWidget(QWidget):
    """联系人列表部件"""

    contact_selected = pyqtSignal(int)  # contact_id
    contact_double_clicked = pyqtSignal(int)  # contact_id

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self._current_account: Optional[Account] = None
        self._contacts: List[Contact] = []
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(0)
        layout.setContentsMargins(0, 0, 0, 0)

        # 工具栏
        toolbar = QToolBar()
        toolbar.setMovable(False)
        toolbar.setFloatable(False)

        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText("搜索联系人...")
        self.search_edit.textChanged.connect(self._on_search)
        self.search_edit.setMinimumWidth(200)
        toolbar.addWidget(self.search_edit)

        toolbar.addSeparator()

        self.new_btn = QToolButton()
        self.new_btn.setText("新建")
        self.new_btn.clicked.connect(self._on_new_contact)
        toolbar.addWidget(self.new_btn)

        self.import_btn = QToolButton()
        self.import_btn.setText("导入")
        self.import_btn.clicked.connect(self._on_import)
        toolbar.addWidget(self.import_btn)

        self.export_btn = QToolButton()
        self.export_btn.setText("导出")
        self.export_btn.clicked.connect(self._on_export)
        toolbar.addWidget(self.export_btn)

        layout.addWidget(toolbar)

        # 主分割器
        splitter = QSplitter(Qt.Orientation.Horizontal)

        # 左侧：分组/标签列表
        left_widget = QWidget()
        left_layout = QVBoxLayout(left_widget)
        left_layout.setContentsMargins(0, 8, 0, 0)

        # 分组列表
        group_label = QLabel("分组")
        group_label.setStyleSheet("font-weight: bold; padding: 8px; color: #89b4fa;")
        left_layout.addWidget(group_label)

        self.group_list = QListWidget()
        self.group_list.setMaximumWidth(180)
        self.group_list.itemClicked.connect(self._on_group_selected)

        # 添加默认分组
        default_groups = [
            ("所有联系人", "all"),
            ("常用联系人", "frequent"),
            ("收藏联系人", "favorites"),
            ("公司同事", "company"),
        ]

        for name, key in default_groups:
            item = QListWidgetItem(name)
            item.setData(Qt.ItemDataRole.UserRole, key)
            self.group_list.addItem(item)

        # 添加标签分组
        tags = ContactTag.get_all()
        if tags:
            self.group_list.addItem(QListWidgetItem("--- 标签 ---"))
            for tag in tags:
                item = QListWidgetItem(f"  #{tag['name']}")
                item.setData(Qt.ItemDataRole.UserRole, f"tag:{tag['id']}")
                item.setForeground(Qt.GlobalColor.cyan)
                self.group_list.addItem(item)

        left_layout.addWidget(self.group_list)
        left_layout.addStretch()

        splitter.addWidget(left_widget)

        # 右侧：联系人表格
        right_widget = QWidget()
        right_layout = QVBoxLayout(right_widget)
        right_layout.setContentsMargins(0, 8, 0, 0)

        # 联系人表格
        self.contact_table = QTableWidget()
        self.contact_table.setColumnCount(5)
        self.contact_table.setHorizontalHeaderLabels(
            ["姓名", "邮箱", "电话", "公司", "标签"]
        )
        self.contact_table.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.Stretch
        )
        self.contact_table.horizontalHeader().setSectionResizeMode(
            0, QHeaderView.ResizeMode.ResizeToContents
        )
        self.contact_table.setSelectionBehavior(
            QTableWidget.SelectionBehavior.SelectRows
        )
        self.contact_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.contact_table.itemSelectionChanged.connect(
            self._on_table_selection_changed
        )
        self.contact_table.itemDoubleClicked.connect(self._on_table_double_clicked)
        self.contact_table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.contact_table.customContextMenuRequested.connect(self._show_context_menu)

        right_layout.addWidget(self.contact_table)

        splitter.addWidget(right_widget)

        # 设置分割器比例
        splitter.setSizes([200, 600])
        layout.addWidget(splitter, 1)

        # 状态栏
        self.status_label = QLabel("就绪")
        self.status_label.setStyleSheet(
            "padding: 4px 8px; color: #a6adc8; background: #313244; font-size: 11px;"
        )
        layout.addWidget(self.status_label)

    def set_account(self, account: Optional[Account]):
        """设置当前账户"""
        self._current_account = account
        self._load_all_contacts()

    def _load_all_contacts(self, filter_group: Optional[str] = None):
        """加载所有联系人"""
        if not self._current_account:
            self._contacts = []
            self.contact_table.setRowCount(0)
            return

        # 根据分组过滤
        if filter_group == "all":
            self._contacts = Contact.get_all(account_id=self._current_account.id)
        elif filter_group == "favorites":
            self._contacts = Contact.get_all(
                account_id=self._current_account.id, favorites_only=True
            )
        elif filter_group == "frequent":
            # 按联系频率排序
            all_contacts = Contact.get_all(account_id=self._current_account.id)
            self._contacts = sorted(
                all_contacts, key=lambda c: c.frequency, reverse=True
            )[:50]
        elif filter_group and filter_group.startswith("tag:"):
            tag_id = int(filter_group.split(":")[1])
            all_contacts = Contact.get_all(account_id=self._current_account.id)
            self._contacts = [
                c for c in all_contacts if str(tag_id) in [str(t) for t in c.tags]
            ]
        else:
            self._contacts = Contact.get_all(account_id=self._current_account.id)

        # 更新表格
        self.contact_table.setRowCount(len(self._contacts))

        for i, contact in enumerate(self._contacts):
            # 姓名
            name_item = QTableWidgetItem(contact.display_name)
            name_item.setData(Qt.ItemDataRole.UserRole, contact.id)
            if contact.is_favorite:
                name_item.setIcon(QIcon.fromTheme("starred"))
            self.contact_table.setItem(i, 0, name_item)

            # 邮箱
            email_item = QTableWidgetItem(contact.email)
            self.contact_table.setItem(i, 1, email_item)

            # 电话
            phone_text = contact.mobile if contact.mobile else contact.phone
            phone_item = QTableWidgetItem(phone_text)
            self.contact_table.setItem(i, 2, phone_item)

            # 公司
            company_item = QTableWidgetItem(contact.company or "")
            self.contact_table.setItem(i, 3, company_item)

            # 标签
            tags_text = ", ".join(contact.tags) if contact.tags else ""
            tags_item = QTableWidgetItem(tags_text)
            self.contact_table.setItem(i, 4, tags_item)

        self.status_label.setText(f"共 {len(self._contacts)} 个联系人")

    def _on_search(self, text: str):
        """搜索联系人"""
        if not self._current_account or not text.strip():
            self._load_all_contacts()
            return

        self._contacts = Contact.search(text, self._current_account.id)

        # 更新表格（与_load_all_contacts类似）
        self.contact_table.setRowCount(len(self._contacts))

        for i, contact in enumerate(self._contacts):
            name_item = QTableWidgetItem(contact.display_name)
            name_item.setData(Qt.ItemDataRole.UserRole, contact.id)
            if contact.is_favorite:
                name_item.setIcon(QIcon.fromTheme("starred"))
            self.contact_table.setItem(i, 0, name_item)

            email_item = QTableWidgetItem(contact.email)
            self.contact_table.setItem(i, 1, email_item)

            phone_text = contact.mobile if contact.mobile else contact.phone
            phone_item = QTableWidgetItem(phone_text)
            self.contact_table.setItem(i, 2, phone_item)

            company_item = QTableWidgetItem(contact.company or "")
            self.contact_table.setItem(i, 3, company_item)

            tags_text = ", ".join(contact.tags) if contact.tags else ""
            tags_item = QTableWidgetItem(tags_text)
            self.contact_table.setItem(i, 4, tags_item)

        self.status_label.setText(f"找到 {len(self._contacts)} 个匹配的联系人")

    def _on_group_selected(self, item: QListWidgetItem):
        """分组被选中"""
        group_key = item.data(Qt.ItemDataRole.UserRole)
        if group_key:
            self._load_all_contacts(group_key)

    def _on_table_selection_changed(self):
        """表格选择变化"""
        selected_items = self.contact_table.selectedItems()
        if selected_items:
            # 获取第一列的联系人ID
            row = selected_items[0].row()
            contact_id_item = self.contact_table.item(row, 0)
            if contact_id_item:
                contact_id = contact_id_item.data(Qt.ItemDataRole.UserRole)
                self.contact_selected.emit(contact_id)

    def _on_table_double_clicked(self, item: QTableWidgetItem):
        """表格双击"""
        row = item.row()
        contact_id_item = self.contact_table.item(row, 0)
        if contact_id_item:
            contact_id = contact_id_item.data(Qt.ItemDataRole.UserRole)
            self.contact_double_clicked.emit(contact_id)

    def _show_context_menu(self, pos):
        """显示右键菜单"""
        selected_items = self.contact_table.selectedItems()
        if not selected_items:
            return

        row = selected_items[0].row()
        contact_id_item = self.contact_table.item(row, 0)
        if not contact_id_item:
            return

        contact_id = contact_id_item.data(Qt.ItemDataRole.UserRole)
        contact = Contact.get_by_id(contact_id)
        if not contact:
            return

        menu = QMenu(self)

        # 编辑
        edit_action = QAction("编辑联系人", self)
        edit_action.triggered.connect(lambda: self._edit_contact(contact))
        menu.addAction(edit_action)

        # 删除
        delete_action = QAction("删除联系人", self)
        delete_action.triggered.connect(lambda: self._delete_contact(contact))
        menu.addAction(delete_action)

        menu.addSeparator()

        # 收藏/取消收藏
        if contact.is_favorite:
            unfavorite_action = QAction("取消收藏", self)
            unfavorite_action.triggered.connect(
                lambda: self._toggle_favorite(contact, False)
            )
            menu.addAction(unfavorite_action)
        else:
            favorite_action = QAction("添加到收藏", self)
            favorite_action.triggered.connect(
                lambda: self._toggle_favorite(contact, True)
            )
            menu.addAction(favorite_action)

        menu.addSeparator()

        # 写邮件
        email_action = QAction(f"发送邮件给 {contact.email}", self)
        email_action.triggered.connect(lambda: self._send_email(contact))
        menu.addAction(email_action)

        menu.addSeparator()

        # 复制信息
        copy_menu = QMenu("复制", self)

        copy_name_action = QAction("复制姓名", self)
        copy_name_action.triggered.connect(
            lambda: self._copy_to_clipboard(contact.name)
        )
        copy_menu.addAction(copy_name_action)

        copy_email_action = QAction("复制邮箱", self)
        copy_email_action.triggered.connect(
            lambda: self._copy_to_clipboard(contact.email)
        )
        copy_menu.addAction(copy_email_action)

        copy_phone_action = QAction("复制电话", self)
        copy_phone_action.triggered.connect(
            lambda: self._copy_to_clipboard(contact.phone or contact.mobile)
        )
        copy_menu.addAction(copy_phone_action)

        menu.addMenu(copy_menu)

        menu.exec(self.contact_table.mapToGlobal(pos))

    def _on_new_contact(self):
        """新建联系人"""
        from openemail.ui.contacts.contact_editor import ContactEditorDialog

        dialog = ContactEditorDialog(self._current_account, self)
        if dialog.exec():
            # 重新加载联系人
            self._load_all_contacts()

    def _on_import(self):
        """导入联系人"""
        file_dialog = QFileDialog(self)
        file_dialog.setWindowTitle("导入联系人")
        file_dialog.setFileMode(QFileDialog.FileMode.ExistingFile)
        file_dialog.setNameFilter("VCard文件 (*.vcf);;CSV文件 (*.csv);;所有文件 (*.*)")

        if file_dialog.exec():
            file_path = file_dialog.selectedFiles()[0]
            if file_path.endswith(".vcf"):
                self._import_vcard(file_path)
            elif file_path.endswith(".csv"):
                self._import_csv(file_path)

    def _on_export(self):
        """导出联系人"""
        if not self._contacts:
            QMessageBox.information(self, "导出", "没有联系人可以导出")
            return

        file_dialog = QFileDialog(self)
        file_dialog.setWindowTitle("导出联系人")
        file_dialog.setFileMode(QFileDialog.FileMode.AnyFile)
        file_dialog.setAcceptMode(QFileDialog.AcceptMode.AcceptSave)
        file_dialog.setNameFilter("VCard文件 (*.vcf);;CSV文件 (*.csv)")
        file_dialog.setDefaultSuffix("vcf")

        if file_dialog.exec():
            file_path = file_dialog.selectedFiles()[0]

            progress = QProgressDialog(
                "导出联系人...", "取消", 0, len(self._contacts), self
            )
            progress.setWindowTitle("导出进度")
            progress.setWindowModality(Qt.WindowModality.WindowModal)

            vcard_content = []
            for i, contact in enumerate(self._contacts):
                vcard = contact.export_to_vcard()
                if vcard:
                    vcard_content.append(vcard)

                progress.setValue(i + 1)
                if progress.wasCanceled():
                    break

            if not progress.wasCanceled():
                with open(file_path, "w", encoding="utf-8") as f:
                    f.write("\n".join(vcard_content))

                QMessageBox.information(
                    self,
                    "导出完成",
                    f"已导出 {len(vcard_content)} 个联系人到:\n{file_path}",
                )

    def _import_vcard(self, file_path: str):
        """导入VCard文件"""
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                content = f.read()

            contacts = Contact.import_from_vcard(content, self._current_account.id)

            QMessageBox.information(
                self, "导入完成", f"成功导入 {len(contacts)} 个联系人"
            )
            self._load_all_contacts()

        except Exception as e:
            QMessageBox.critical(self, "导入失败", f"导入VCard文件失败:\n{str(e)}")

    def _import_csv(self, file_path: str):
        """导入CSV文件（简化版）"""
        try:
            import csv

            with open(file_path, "r", encoding="utf-8") as f:
                reader = csv.DictReader(f)

                count = 0
                for row in reader:
                    contact = Contact(account_id=self._current_account.id)

                    # 尝试从CSV行中提取信息
                    contact.name = row.get("name", row.get("Name", ""))
                    contact.email = row.get("email", row.get("Email", ""))
                    contact.phone = row.get("phone", row.get("Phone", ""))
                    contact.company = row.get("company", row.get("Company", ""))
                    contact.job_title = row.get("job_title", row.get("Job Title", ""))

                    if contact.email:  # 至少需要邮箱
                        contact.save()
                        count += 1

            QMessageBox.information(self, "导入完成", f"成功导入 {count} 个联系人")
            self._load_all_contacts()

        except Exception as e:
            QMessageBox.critical(self, "导入失败", f"导入CSV文件失败:\n{str(e)}")

    def _edit_contact(self, contact: Contact):
        """编辑联系人"""
        from openemail.ui.contacts.contact_editor import ContactEditorDialog

        dialog = ContactEditorDialog(self._current_account, self, contact)
        if dialog.exec():
            self._load_all_contacts()

    def _delete_contact(self, contact: Contact):
        """删除联系人"""
        reply = QMessageBox.question(
            self,
            "确认删除",
            f"确定要删除联系人 {contact.display_name} 吗？",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )

        if reply == QMessageBox.StandardButton.Yes:
            if contact.delete():
                self._load_all_contacts()
                self.status_label.setText(f"已删除联系人: {contact.display_name}")

    def _toggle_favorite(self, contact: Contact, favorite: bool):
        """切换收藏状态"""
        contact.is_favorite = favorite
        contact.save()
        self._load_all_contacts()

    def _send_email(self, contact: Contact):
        """发送邮件给联系人"""
        # 这个功能应该由主窗口处理
        # 这里只发送信号或记录日志
        logger.debug("发送邮件给: %s", contact.email)
        # TODO: 触发主窗口的写邮件功能

    def _copy_to_clipboard(self, text: str):
        """复制文本到剪贴板"""
        clipboard = QApplication.clipboard()
        clipboard.setText(text or "")
        self.status_label.setText("已复制到剪贴板")
