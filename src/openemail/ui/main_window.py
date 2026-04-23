from __future__ import annotations

import logging
from typing import List

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QAction
from PyQt6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QPushButton,
    QSplitter,
    QStackedWidget,
    QStatusBar,
    QToolBar,
    QVBoxLayout,
    QWidget,
)

from openemail.config import settings
from openemail.models.account import Account
from openemail.models.email import Email
from openemail.models.folder import Folder
from openemail.ui.sidebar import Page, Sidebar
from openemail.ui.keyboard_shortcuts import (
    KeyboardShortcutManager,
    setup_application_shortcuts,
)

logger = logging.getLogger(__name__)


class PlaceholderPage(QWidget):
    def __init__(self, title: str, description: str = "") -> None:
        super().__init__()
        self.setProperty("class", "placeholder")
        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        title_label = QLabel(title)
        title_label.setProperty("class", "heading")
        title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title_label)

        if description:
            desc_label = QLabel(description)
            desc_label.setProperty("class", "placeholder-text")
            desc_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            layout.addWidget(desc_label)


class MailPageWidget(QWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._current_account: Account | None = None
        self._current_folder: Folder | None = None
        self._current_email: Email | None = None
        self._initial_sync_scheduled = False  # 首次同步调度标志
        self._last_sync_time = None  # 上次同步时间
        self._setup_ui()

        # 检查并更新引导状态
        self._check_and_update_onboarding_state()

    def _create_mail_list(self) -> QWidget:
        """创建邮件列表部件（尝试使用增强版）"""
        try:
            from openemail.ui.mail.mail_list_enhanced import (
                EnhancedMailListWidget as MailListWidget,
            )

            mail_list = MailListWidget()

            # 连接增强版的信号
            mail_list.email_selected.connect(self._on_email_selected)

            # 批量操作信号
            mail_list.batch_mark_read.connect(self._on_batch_mark_read)
            mail_list.batch_mark_unread.connect(self._on_batch_mark_unread)
            mail_list.batch_mark_flagged.connect(self._on_batch_mark_flagged)
            mail_list.batch_move.connect(self._on_batch_move)
            mail_list.batch_delete.connect(self._on_batch_delete)
            mail_list.batch_mark_spam.connect(self._on_batch_mark_spam)

            # 向后兼容的信号
            mail_list.mark_read_requested.connect(self._on_mark_read)
            mail_list.mark_flagged_requested.connect(self._on_mark_flagged)
            mail_list.delete_requested.connect(self._on_delete_email)
            mail_list.mark_spam_requested.connect(self._on_mark_spam)
            mail_list.mark_not_spam_requested.connect(self._on_mark_not_spam)

            logger.info("使用增强版邮件列表（支持多选和批量操作）")
            return mail_list

        except ImportError as e:
            logger.warning("无法加载增强版邮件列表: %s, 使用原版", e)
            from openemail.ui.mail.mail_list import MailListWidget

            mail_list = MailListWidget()
            mail_list.email_selected.connect(self._on_email_selected)
            mail_list.mark_read_requested.connect(self._on_mark_read)
            mail_list.mark_flagged_requested.connect(self._on_mark_flagged)
            mail_list.delete_requested.connect(self._on_delete_email)
            mail_list.mark_spam_requested.connect(self._on_mark_spam)
            mail_list.mark_not_spam_requested.connect(self._on_mark_not_spam)
            return mail_list

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # 尝试使用增强版搜索栏
        try:
            from openemail.ui.search.search_enhanced_ui import EnhancedSearchBar

            self._search_bar = EnhancedSearchBar()
            self._search_bar.search_requested.connect(self._on_search)
            self._search_bar.advanced_search_requested.connect(self._on_advanced_search)
            logger.info("使用增强版搜索栏（支持语法高亮和自动建议）")
        except ImportError:
            # 回退到原版搜索栏
            from openemail.ui.mail.search_bar import SearchBar

            self._search_bar = SearchBar()
            self._search_bar.search_requested.connect(self._on_search)
            self._search_bar.search_cleared.connect(self._on_search_cleared)

        layout.addWidget(self._search_bar)

        # 创建邮件列表（尝试使用增强版，失败则回退到原版）
        self._mail_list = self._create_mail_list()
        layout.addWidget(self._mail_list, 1)

    def load_folder(self, account: Account, folder: Folder) -> None:
        self._current_account = account
        self._current_folder = folder
        self._current_email = None

        folder_names = {
            "INBOX": "收件箱",
            "Sent": "已发送",
            "Drafts": "草稿",
            "Spam": "垃圾邮件",
            "Trash": "已删除",
        }
        title = folder_names.get(folder.name, folder.name)
        if account.name:
            title = f"{title} - {account.name}"
        self._mail_list.set_title(title)

        emails = Email.get_by_folder(folder.id, limit=self._mail_list.PAGE_SIZE)
        self._mail_list.load_emails(emails, folder_id=folder.id)

    def load_spam(self, account: Account) -> None:
        spam_folder = Folder.get_by_name(account.id, "Spam")
        if spam_folder:
            self.load_folder(account, spam_folder)
        else:
            self._mail_list.set_title(f"垃圾邮件 - {account.name}")
            self._mail_list.load_emails(Email.get_spam(account.id))

    def _on_email_selected(self, email_id: int) -> None:
        email_obj = Email.get_by_id(email_id)
        if email_obj is None:
            return
        self._current_email = email_obj

        if not email_obj.is_read:
            email_obj.mark_read()
            self._mail_list.refresh_email(email_obj)

        main_window = self._get_main_window()
        if main_window:
            main_window.show_email_detail(email_obj)

    def _on_mark_read(self, email_id: int) -> None:
        email_obj = Email.get_by_id(email_id)
        if email_obj:
            if email_obj.is_read:
                email_obj.is_read = False
                from openemail.storage.database import db

                db.update("emails", {"is_read": 0}, "id = ?", (email_id,))
            else:
                email_obj.mark_read()
            self._mail_list.refresh_email(email_obj)

    def _on_mark_flagged(self, email_id: int, flagged: bool) -> None:
        email_obj = Email.get_by_id(email_id)
        if email_obj:
            email_obj.mark_flagged(flagged)
            self._mail_list.refresh_email(email_obj)

    def _on_delete_email(self, email_id: int) -> None:
        email_obj = Email.get_by_id(email_id)
        if email_obj:
            email_obj.is_deleted = True
            from openemail.storage.database import db

            db.update("emails", {"is_deleted": 1}, "id = ?", (email_id,))
            self._mail_list.remove_email(email_id)
            if self._current_email and self._current_email.id == email_id:
                self._current_email = None
                main_window = self._get_main_window()
                if main_window:
                    main_window.clear_email_detail()

    def _on_mark_spam(self, email_id: int) -> None:
        email_obj = Email.get_by_id(email_id)
        if email_obj:
            email_obj.mark_spam("手动标记")
            spam_folder = Folder.get_by_name(email_obj.account_id, "Spam")
            if spam_folder:
                email_obj.move_to_folder(spam_folder.id)
            self._mail_list.remove_email(email_id)

    def _on_mark_not_spam(self, email_id: int) -> None:
        email_obj = Email.get_by_id(email_id)
        if email_obj:
            email_obj.mark_not_spam()
            inbox = Folder.get_by_name(email_obj.account_id, "INBOX")
            if inbox:
                email_obj.move_to_folder(inbox.id)
            self._mail_list.remove_email(email_id)

    # 批量操作方法
    def _on_batch_mark_read(self, email_ids: List[int]) -> None:
        """批量标记为已读"""

        for email_id in email_ids:
            email_obj = Email.get_by_id(email_id)
            if email_obj:
                email_obj.mark_read()
                if hasattr(self._mail_list, "refresh_email"):
                    self._mail_list.refresh_email(email_obj)

        if hasattr(self._mail_list, "show_progress"):
            self._mail_list.show_progress(
                False, f"标记了 {len(email_ids)} 封邮件为已读"
            )

    def _on_batch_mark_unread(self, email_ids: List[int]) -> None:
        """批量标记为未读"""
        from openemail.storage.database import db

        for email_id in email_ids:
            email_obj = Email.get_by_id(email_id)
            if email_obj:
                email_obj.is_read = False
                db.update("emails", {"is_read": 0}, "id = ?", (email_id,))
                if hasattr(self._mail_list, "refresh_email"):
                    self._mail_list.refresh_email(email_obj)

        if hasattr(self._mail_list, "show_progress"):
            self._mail_list.show_progress(
                False, f"标记了 {len(email_ids)} 封邮件为未读"
            )

    def _on_batch_mark_flagged(self, email_ids: List[int], flagged: bool) -> None:
        """批量标记星标"""
        for email_id in email_ids:
            email_obj = Email.get_by_id(email_id)
            if email_obj:
                email_obj.mark_flagged(flagged)
                if hasattr(self._mail_list, "refresh_email"):
                    self._mail_list.refresh_email(email_obj)

        action = "加星标" if flagged else "取消星标"
        if hasattr(self._mail_list, "show_progress"):
            self._mail_list.show_progress(False, f"{action}了 {len(email_ids)} 封邮件")

    def _on_batch_move(self, email_ids: List[int]) -> None:
        """批量移动邮件（显示文件夹选择对话框）"""
        if not self._current_account:
            return

        from PyQt6.QtWidgets import (
            QDialog,
            QVBoxLayout,
            QListWidget,
            QPushButton,
            QLabel,
        )

        dialog = QDialog(self)
        dialog.setWindowTitle("移动到文件夹")
        dialog.setMinimumWidth(300)

        layout = QVBoxLayout(dialog)

        label = QLabel(f"选择目标文件夹 ({len(email_ids)}封邮件):")
        layout.addWidget(label)

        folder_list = QListWidget()

        # 获取所有系统文件夹
        system_folders = Folder.get_system_folders(self._current_account.id)
        for folder in system_folders:
            folder_list.addItem(folder.name)

        layout.addWidget(folder_list)

        def do_move():
            selected_items = folder_list.selectedItems()
            if not selected_items:
                return

            target_folder = selected_items[0].text()
            folder_obj = Folder.get_by_name(self._current_account.id, target_folder)
            if not folder_obj:
                return

            for email_id in email_ids:
                email_obj = Email.get_by_id(email_id)
                if email_obj:
                    email_obj.move_to_folder(folder_obj.id)
                    if hasattr(self._mail_list, "remove_email"):
                        self._mail_list.remove_email(email_id)

            dialog.accept()

            if hasattr(self._mail_list, "show_progress"):
                self._mail_list.show_progress(
                    False, f"移动了 {len(email_ids)} 封邮件到 {target_folder}"
                )

        btn_layout = QHBoxLayout()
        move_btn = QPushButton("移动")
        move_btn.clicked.connect(do_move)
        btn_layout.addWidget(move_btn)

        cancel_btn = QPushButton("取消")
        cancel_btn.clicked.connect(dialog.reject)
        btn_layout.addWidget(cancel_btn)

        layout.addLayout(btn_layout)

        dialog.exec()

    def _on_batch_delete(self, email_ids: List[int]) -> None:
        """批量删除邮件"""
        count = len(email_ids)

        if count > 5:
            from PyQt6.QtWidgets import QMessageBox

            reply = QMessageBox.question(
                self,
                "确认批量删除",
                f"确定要删除 {count} 封邮件吗？",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            if reply != QMessageBox.StandardButton.Yes:
                return

        from openemail.storage.database import db

        for email_id in email_ids:
            email_obj = Email.get_by_id(email_id)
            if email_obj:
                email_obj.is_deleted = True
                db.update("emails", {"is_deleted": 1}, "id = ?", (email_id,))

                if hasattr(self._mail_list, "remove_email"):
                    self._mail_list.remove_email(email_id)

                # 如果当前显示的邮件被删除，清空详情
                if self._current_email and self._current_email.id == email_id:
                    self._current_email = None
                    main_window = self._get_main_window()
                    if main_window:
                        main_window.clear_email_detail()

        if hasattr(self._mail_list, "show_progress"):
            self._mail_list.show_progress(False, f"删除了 {count} 封邮件")

    def _on_batch_mark_spam(self, email_ids: List[int]) -> None:
        """批量标记为垃圾邮件"""
        spam_folder = None
        if self._current_account:
            spam_folder = Folder.get_by_name(self._current_account.id, "Spam")

        for email_id in email_ids:
            email_obj = Email.get_by_id(email_id)
            if email_obj:
                email_obj.mark_spam("批量标记")

                if spam_folder:
                    email_obj.move_to_folder(spam_folder.id)

                if hasattr(self._mail_list, "remove_email"):
                    self._mail_list.remove_email(email_id)

        if hasattr(self._mail_list, "show_progress"):
            self._mail_list.show_progress(
                False, f"标记了 {len(email_ids)} 封邮件为垃圾邮件"
            )

    def _on_search(self, query: str) -> None:
        if self._current_account:
            # 尝试使用增强版搜索
            try:
                from openemail.storage.search_enhanced import EnhancedSearchEngine

                emails = EnhancedSearchEngine.search(
                    query=query,
                    account_id=self._current_account.id,
                    folder_id=None,
                    limit=100,
                    include_attachments=True,
                )
                logger.debug("增强版搜索找到 %d 个结果", len(emails))
            except ImportError:
                # 回退到原版搜索
                emails = Email.search(self._current_account.id, query)
                logger.debug("原版搜索找到 %d 个结果", len(emails))

            self._mail_list.load_emails(emails)
            self._mail_list.set_title(f"搜索: {query}")

    def _on_advanced_search(self) -> None:
        """显示高级搜索对话框"""
        try:
            from openemail.ui.search.search_enhanced_ui import AdvancedSearchDialog

            if self._current_account:
                dialog = AdvancedSearchDialog(self._current_account.id, self)
                dialog.search_requested.connect(self._on_search)
                dialog.show()
        except ImportError:
            logger.debug("高级搜索对话框不可用")

    def _on_search_cleared(self) -> None:
        if self._current_account and self._current_folder:
            self.load_folder(self._current_account, self._current_folder)

    def _get_main_window(self):
        widget = self.parent()
        while widget:
            if isinstance(widget, MainWindow):
                return widget
            widget = widget.parent()
        return None

    def _check_and_update_onboarding_state(self) -> None:
        """检查并更新引导状态，实现老用户兼容和恢复逻辑"""
        try:
            # 批次 D2：清理历史脏账号
            try:
                from openemail.core.account_cleanup import run_account_cleanup

                run_account_cleanup()
            except Exception as cleanup_error:
                logger.warning("账号清理失败: %s", str(cleanup_error))

            current_state = settings.onboarding_state
            accounts = Account.get_valid_for_display()  # 批次 D2：只计算有效的账号

            logger.debug(
                "当前引导状态: %s, 有效账号数: %d",
                current_state,
                len(accounts) if accounts else 0,
            )

            # 状态处理逻辑
            if current_state == "completed":
                logger.debug("引导状态已为 completed，无需处理")
                return

            elif current_state == "not_started":
                # 新用户首次启动
                if accounts:
                    # 老用户兼容：已有账号但状态为not_started，直接设为completed
                    logger.info(
                        "检测到已有活跃账号，自动将引导状态从 not_started 更新为 completed"
                    )
                    settings.onboarding_state = "completed"
                else:
                    logger.debug("新用户首次启动，保持 not_started")

            elif current_state == "in_progress":
                # 引导进行中，如果已有账户则可能是上次引导未完成但已创建账户
                if accounts:
                    logger.warning(
                        "检测到引导中断（in_progress），但已有账户，恢复为 completed"
                    )
                    # 检查并补全缺失资源
                    self._recover_from_interrupted_onboarding(accounts)
                    settings.onboarding_state = "completed"
                else:
                    # 可能是中途退出，重置到安全状态
                    logger.info("引导中断（in_progress）且无账户，重置为 not_started")
                    settings.onboarding_state = "not_started"

            elif current_state == "submitting":
                # 提交中崩溃，需要恢复处理
                logger.warning("检测到上次引导在提交过程中崩溃（submitting状态）")
                self._handle_submitting_recovery(accounts)

            elif current_state == "recovery_needed":
                # 需要用户干预的恢复状态
                logger.error("引导状态为 recovery_needed，需要用户干预")
                self._show_recovery_hint(accounts)

            else:
                # 未知状态，保守处理
                logger.warning("未知引导状态: %s", current_state)
                if accounts:
                    settings.onboarding_state = "completed"

        except Exception as e:
            logger.error("检查引导状态时出错: %s", str(e))
            # 出错时保守处理：如果有账号，则设为 completed
            try:
                accounts = Account.get_all_active()
                if accounts:
                    settings.onboarding_state = "completed"
            except Exception as inner_e:
                logger.error("保守处理也失败: %s", str(inner_e))

    def _recover_from_interrupted_onboarding(self, accounts):
        """从中断的引导中恢复（补全缺失资源）"""
        try:
            from openemail.models.folder import Folder

            for account in accounts:
                logger.info("为账户 %s 补全系统文件夹", account.email)
                Folder.ensure_system_folders(account.id)

        except Exception as e:
            logger.error("恢复中断引导时出错: %s", str(e))

    def _handle_submitting_recovery(self, accounts):
        """处理submitting状态的恢复"""
        try:
            if accounts:
                # 提交途中已有账户，说明账户保存成功但状态未更新
                logger.info("提交中恢复：已有账户，补全资源并设为 completed")
                self._recover_from_interrupted_onboarding(accounts)
                settings.onboarding_state = "completed"
            else:
                # 提交中但无账户，可能是账户创建失败
                logger.warning("提交中恢复：无账户，重置为 in_progress 让用户重试")
                settings.onboarding_state = "in_progress"

        except Exception as e:
            logger.error("处理submitting恢复时出错: %s", str(e))
            # 出错时保守重置为 in_progress
            settings.onboarding_state = "in_progress"

    def _show_recovery_hint(self, accounts) -> None:
        """显示恢复提示（TODO：批次B3实现）"""
        pass


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self._setup_window()
        self._setup_menubar()
        self._setup_ui()
        self._restore_geometry()
        self._check_first_run()
        self._setup_keyboard_shortcuts()
        self._setup_auto_sync()

    def _check_first_run(self) -> None:
        """检查是否首次启动（使用新的引导状态逻辑）"""
        try:
            current_state = settings.onboarding_state
            accounts = Account.get_valid_for_display()  # 批次 D2：只考虑有效账号

            logger.debug(
                "首次启动检查：状态=%s, 有效账户数=%d", current_state, len(accounts)
            )

            # 根据状态和账户情况决定是否显示引导
            if current_state == "completed":
                logger.debug("引导已完成，不显示引导对话框")
                return

            elif current_state in ["not_started", "in_progress"]:
                if accounts:
                    # 已有账户但状态未更新（老用户兼容或异常情况）
                    logger.info(
                        "已有账户但引导状态为 %s，自动更新为 completed", current_state
                    )
                    settings.onboarding_state = "completed"
                else:
                    # 新用户或中途退出，显示引导
                    logger.info("显示引导对话框，当前状态: %s", current_state)
                    self._show_onboarding_dialog()

            elif current_state == "submitting":
                # 提交中崩溃，处理恢复
                logger.warning("检测到提交中状态，处理恢复")
                self._handle_submitting_recovery(accounts)
                # 恢复后可能需要重新显示引导
                if (
                    settings.onboarding_state in ["in_progress", "not_started"]
                    and not accounts
                ):
                    self._show_onboarding_dialog()

            elif current_state == "recovery_needed":
                logger.error("需要用户干预的恢复状态")
                # TODO: 显示恢复对话框而不是标准引导
                if not accounts:
                    self._show_onboarding_dialog()

        except Exception as e:
            logger.error("首次启动检查时出错: %s", str(e))
            # 出错时保守处理：不显示引导，避免阻塞用户

    def _show_onboarding_dialog(self) -> None:
        """显示引导对话框"""
        try:
            from openemail.ui.mail.welcome_dialog_enhanced import WelcomeDialogEnhanced

            dialog = WelcomeDialogEnhanced(self)
            dialog.account_added.connect(self._on_account_added)
            dialog.setup_completed.connect(self._on_setup_completed)
            dialog.exec()
        except Exception as e:
            logger.error("显示引导对话框时出错: %s", str(e))

    def _setup_window(self) -> None:
        self.setWindowTitle("OpenEmail")
        self.setMinimumSize(800, 600)

    def _setup_menubar(self) -> None:
        menubar = self.menuBar()

        file_menu = menubar.addMenu("文件")

        # 添加账户管理菜单项
        manage_accounts_action = QAction("管理账户", self)
        manage_accounts_action.setShortcut("Ctrl+Shift+A")
        manage_accounts_action.triggered.connect(self._show_manage_accounts)
        file_menu.addAction(manage_accounts_action)

        add_account_action = QAction("添加邮箱", self)
        add_account_action.setShortcut("Ctrl+N")
        add_account_action.triggered.connect(self._show_add_account)
        file_menu.addAction(add_account_action)

        sync_action = QAction("同步所有账户", self)
        sync_action.setShortcut("Ctrl+S")
        sync_action.triggered.connect(self._sync_all)
        file_menu.addAction(sync_action)

        file_menu.addSeparator()
        quit_action = QAction("退出", self)
        quit_action.setShortcut("Ctrl+Q")
        quit_action.triggered.connect(self.close)
        file_menu.addAction(quit_action)

        mail_menu = menubar.addMenu("邮件")
        compose_action = QAction("写邮件", self)
        compose_action.setShortcut("Ctrl+Shift+N")
        compose_action.triggered.connect(self._show_compose)
        mail_menu.addAction(compose_action)

        view_menu = menubar.addMenu("视图")
        self._theme_menu = view_menu.addMenu("主题")

        self._light_action = QAction("浅色", self)
        self._light_action.setCheckable(True)
        self._light_action.triggered.connect(lambda: self._set_theme("light"))
        self._theme_menu.addAction(self._light_action)

        self._dark_action = QAction("深色", self)
        self._dark_action.setCheckable(True)
        self._dark_action.triggered.connect(lambda: self._set_theme("dark"))
        self._theme_menu.addAction(self._dark_action)

        self._system_action = QAction("跟随系统", self)
        self._system_action.setCheckable(True)
        self._system_action.triggered.connect(lambda: self._set_theme("system"))
        self._theme_menu.addAction(self._system_action)

        self._update_theme_actions()

        tools_menu = menubar.addMenu("工具")

        filter_rules_action = QAction("过滤规则", self)
        filter_rules_action.triggered.connect(self._show_filter_rules)
        tools_menu.addAction(filter_rules_action)

        account_settings_action = QAction("账户设置", self)
        account_settings_action.setShortcut("Ctrl+,")
        account_settings_action.triggered.connect(self._navigate_to_settings)
        tools_menu.addAction(account_settings_action)

        tools_menu.addSeparator()

        account_cleanup_action = QAction("账户清理工具", self)
        account_cleanup_action.triggered.connect(self._show_account_cleanup)
        tools_menu.addAction(account_cleanup_action)

        help_menu = menubar.addMenu("帮助")
        about_action = QAction("关于", self)
        help_menu.addAction(about_action)

        # Add keyboard shortcuts help to help menu
        shortcuts_action = QAction("键盘快捷键", self)
        shortcuts_action.setShortcut("F1")
        shortcuts_action.triggered.connect(self._show_keyboard_shortcuts_help)
        help_menu.addAction(shortcuts_action)

    def _setup_keyboard_shortcuts(self) -> None:
        """Setup keyboard shortcuts for the main window."""
        self._shortcut_manager = KeyboardShortcutManager(self)

        # Navigation shortcuts
        self._shortcut_manager.add_named_shortcut(
            self, "nav_inbox", lambda: self._navigate_to_folder("inbox")
        )
        self._shortcut_manager.add_named_shortcut(
            self, "nav_sent", lambda: self._navigate_to_folder("sent")
        )
        self._shortcut_manager.add_named_shortcut(
            self, "nav_drafts", lambda: self._navigate_to_folder("drafts")
        )
        self._shortcut_manager.add_named_shortcut(
            self, "nav_trash", lambda: self._navigate_to_folder("trash")
        )
        self._shortcut_manager.add_named_shortcut(
            self, "nav_search", self._focus_search_bar
        )

        # Mail actions shortcuts (connect to existing methods)
        self._shortcut_manager.add_named_shortcut(
            self, "mail_compose", self._show_compose
        )
        self._shortcut_manager.add_named_shortcut(self, "mail_refresh", self._sync_all)

        # Selection shortcuts
        self._shortcut_manager.add_named_shortcut(
            self, "select_none", self._clear_selection
        )

        # Create application-wide shortcuts manager
        setup_application_shortcuts(self)

        logger.info("Setup keyboard shortcuts for main window")

    def _show_keyboard_shortcuts_help(self) -> None:
        """Show keyboard shortcuts help dialog."""
        from PyQt6.QtWidgets import (
            QDialog,
            QVBoxLayout,
            QLabel,
            QTableWidget,
            QTableWidgetItem,
        )

        dialog = QDialog(self)
        dialog.setWindowTitle("键盘快捷键")
        dialog.setMinimumSize(500, 400)

        layout = QVBoxLayout(dialog)

        # Create table
        table = QTableWidget()
        table.setColumnCount(2)
        table.setHorizontalHeaderLabels(["快捷键", "功能"])

        # Get list of shortcuts with descriptions
        shortcuts = [
            ("Ctrl+Shift+N", "写邮件"),
            ("C", "写邮件（快速版）"),
            ("Ctrl+S", "同步所有账户"),
            ("Alt+1", "切换到收件箱"),
            ("Alt+2", "切换到已发送"),
            ("Alt+3", "切换到草稿箱"),
            ("Alt+4", "切换到垃圾箱"),
            ("Ctrl+F", "聚焦搜索框"),
            ("J", "下一个项目"),
            ("K", "上一个项目"),
            ("R", "回复邮件"),
            ("Shift+R", "全部回复"),
            ("F", "转发邮件"),
            ("Delete", "删除邮件"),
            ("E", "归档邮件"),
            ("Shift+I", "标记为已读"),
            ("Shift+U", "标记为未读"),
            ("Shift+S", "切换星标/加旗"),
            ("!", "标记为垃圾邮件"),
            ("Ctrl+A", "全选"),
            ("Esc", "取消选择"),
            ("Ctrl+Q", "退出应用"),
            ("F11", "切换全屏"),
            ("Ctrl+,", "打开设置"),
            ("F1", "显示快捷键帮助"),
            ("Enter", "打开选中邮件"),
            ("Space", "预览选中邮件"),
        ]

        table.setRowCount(len(shortcuts))
        for i, (shortcut, description) in enumerate(shortcuts):
            table.setItem(i, 0, QTableWidgetItem(shortcut))
            table.setItem(i, 1, QTableWidgetItem(description))

        table.resizeColumnsToContents()

        layout.addWidget(QLabel("常用键盘快捷键:"))
        layout.addWidget(table)

        dialog.exec()

    def _focus_search_bar(self) -> None:
        """Focus the search bar."""
        if hasattr(self, "_search_bar"):
            self._search_bar.setFocus()

    def _clear_selection(self) -> None:
        """Clear current selection."""
        # This will be implemented when we add selection support
        logger.debug("Clear selection requested (shortcut)")

    def _navigate_to_folder(self, folder_type: str) -> None:
        """Navigate to a specific folder type."""
        # Find folder by type and navigate
        logger.debug(f"Navigate to folder type: {folder_type}")

    def _show_account_cleanup(self) -> None:
        """显示账户清理工具"""
        try:
            from openemail.ui.tools.account_cleanup_dialog import (
                show_account_cleanup_dialog,
            )

            show_account_cleanup_dialog(self)
        except Exception as e:
            logger.error(f"Failed to show account cleanup dialog: {e}")
            self._show_error("无法打开账户清理工具", str(e))

    def _setup_ui(self) -> None:
        central = QWidget()
        self.setCentralWidget(central)

        main_layout = QVBoxLayout(central)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        self._toolbar = QToolBar()
        self._toolbar.setMovable(False)
        self._toolbar.setStyleSheet("""
            QToolBar {
                border: none;
                padding: 4px 8px;
                spacing: 6px;
            }
        """)

        self._toolbar.addSeparator()

        self._compose_btn_toolbar = QPushButton("✏ 写邮件")
        self._compose_btn_toolbar.setProperty("class", "primary")
        self._compose_btn_toolbar.setToolTip("写邮件 (Ctrl+Shift+N)")
        self._compose_btn_toolbar.setCursor(Qt.CursorShape.PointingHandCursor)
        self._compose_btn_toolbar.setStyleSheet("""
            QPushButton {
                padding: 6px 16px;
                border-radius: 6px;
                font-size: 12px;
                font-weight: bold;
            }
        """)
        self._compose_btn_toolbar.clicked.connect(self._show_compose)
        self._toolbar.addWidget(self._compose_btn_toolbar)

        self._toolbar.addSeparator()

        self._add_account_btn = QPushButton("➕ 添加邮箱")
        self._add_account_btn.setToolTip("添加邮箱账户 (Ctrl+N)")
        self._add_account_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._add_account_btn.setStyleSheet("""
            QPushButton {
                padding: 6px 14px;
                border-radius: 6px;
                font-size: 12px;
            }
        """)
        self._add_account_btn.clicked.connect(self._show_add_account)
        self._toolbar.addWidget(self._add_account_btn)

        spacer = QWidget()
        spacer.setSizePolicy(
            spacer.sizePolicy().horizontalPolicy().Expanding,
            spacer.sizePolicy().verticalPolicy().Preferred,
        )
        self._toolbar.addWidget(spacer)

        self._account_label = QLabel("")
        self._account_label.setStyleSheet("font-size: 12px; padding: 0 8px;")
        self._update_account_label()
        self._toolbar.addWidget(self._account_label)

        main_layout.addWidget(self._toolbar)

        content_layout = QHBoxLayout()
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(0)

        self._sidebar = Sidebar()
        self._sidebar.page_changed.connect(self._on_page_changed)
        self._sidebar.compose_requested.connect(self._show_compose)

        self._content_stack = QStackedWidget()
        self._setup_pages()

        from openemail.ui.mail.mail_view import MailViewWidget

        self._mail_view = MailViewWidget()
        self._mail_view.reply_requested.connect(self._on_reply)
        self._mail_view.reply_all_requested.connect(self._on_reply_all)
        self._mail_view.forward_requested.connect(self._on_forward)
        self._mail_view.delete_requested.connect(self._on_delete_from_view)

        self._detail_widget = QWidget()
        self._detail_widget.setProperty("class", "detail")
        detail_layout = QVBoxLayout(self._detail_widget)
        detail_layout.setContentsMargins(0, 0, 0, 0)
        detail_layout.addWidget(self._mail_view)

        content_splitter = QSplitter(Qt.Orientation.Horizontal)
        content_splitter.addWidget(self._content_stack)
        content_splitter.addWidget(self._detail_widget)
        content_splitter.setStretchFactor(0, 2)
        content_splitter.setStretchFactor(1, 3)

        main_splitter = QSplitter(Qt.Orientation.Horizontal)
        main_splitter.addWidget(self._sidebar)
        main_splitter.addWidget(content_splitter)

        geo = settings.window_geometry
        sidebar_w = geo.get("sidebar_width", 220)
        main_splitter.setSizes([sidebar_w, geo.get("width", 1200) - sidebar_w])
        main_splitter.setStretchFactor(0, 0)
        main_splitter.setStretchFactor(1, 1)

        content_layout.addWidget(main_splitter)
        main_layout.addLayout(content_layout, 1)

        self._statusbar = QStatusBar()
        self.setStatusBar(self._statusbar)
        self._statusbar.showMessage("就绪")

        try:
            from openemail.ui.queue.offline_queue_manager import SimpleQueueStatusWidget

            self.queue_status_widget = SimpleQueueStatusWidget()
            self._statusbar.addPermanentWidget(self.queue_status_widget)
        except ImportError:
            pass

    def _create_labels_page(self) -> QWidget:
        """创建标签管理页面"""
        try:
            from openemail.ui.labels.label_manager import LabelManager

            label_manager = LabelManager(self)
            # 连接标签变化信号到刷新邮件列表
            label_manager.labels_changed.connect(self._refresh_mail_lists)
            return label_manager
        except ImportError as e:
            logger.warning("无法加载标签管理页面: %s, 使用占位页面", e)
            return PlaceholderPage("标签", "标签管理功能将在此显示")

    def _create_contact_page(self) -> QWidget:
        """创建联系人页面"""
        try:
            from openemail.ui.contacts.contact_page import ContactPageWidget

            contact_page = ContactPageWidget()
            contact_page.email_requested.connect(self._on_contact_email_requested)
            return contact_page
        except ImportError as e:
            logger.warning("无法加载联系人页面: %s, 使用占位页面", e)
            return PlaceholderPage("联系人", "联系人管理功能将在此显示")

    def _on_contact_email_requested(self, email_address: str):
        """从联系人页面请求发送邮件"""
        account = Account.get_default_for_display()
        if not account:
            need_action = Account.get_need_action_accounts()
            if need_action:
                self._statusbar.showMessage("没有可用邮箱账号，请先修复或添加邮箱")
            else:
                self._statusbar.showMessage("请先添加邮箱账号")
            return

        # 使用增强版撰写窗口给指定邮箱写邮件
        try:
            from openemail.ui.mail.compose_window import ComposeWindowEnhanced

            compose = ComposeWindowEnhanced(account, self)
            compose._to_field.setText(email_address)
            compose.sent.connect(
                lambda: self._statusbar.showMessage("邮件已发送", 3000)
            )
            compose.exec()
        except ImportError:
            # 如果增强版不可用，回退到原版
            from openemail.ui.mail.compose_window import ComposeWindow

            compose = ComposeWindow(account, self)
            compose._to_field.setText(email_address)
            compose.sent.connect(
                lambda: self._statusbar.showMessage("邮件已发送", 3000)
            )
            compose.exec()

    def _create_calendar_page(self) -> QWidget:
        try:
            from openemail.ui.calendar.calendar_page import CalendarPageWidget

            return CalendarPageWidget()
        except ImportError as e:
            logger.warning("无法加载日历页面: %s", e)
            return PlaceholderPage("日历", "日历视图将在此显示")

    def _create_todo_page(self, view_mode: str = "all") -> QWidget:
        try:
            from openemail.ui.todo.todo_page import TodoPageWidget

            return TodoPageWidget(view_mode=view_mode)
        except ImportError as e:
            logger.warning("无法加载待办页面: %s", e)
            return PlaceholderPage("待办", "待办事项将在此显示")

    def _create_project_page(self) -> QWidget:
        try:
            from openemail.ui.project.project_page import ProjectPageWidget

            return ProjectPageWidget()
        except ImportError as e:
            logger.warning("无法加载项目板页面: %s", e)
            return PlaceholderPage("项目板", "项目看板将在此显示")

    def _create_settings_page(self) -> QWidget:
        try:
            from openemail.ui.settings.settings_page import SettingsPageWidget

            page = SettingsPageWidget()
            page.theme_changed.connect(self._on_theme_changed_from_settings)
            page.accounts_changed.connect(self._on_accounts_changed)
            return page
        except ImportError as e:
            logger.warning("无法加载设置页面: %s", e)
            return PlaceholderPage("设置", "应用设置将在此显示")

    def _setup_pages(self) -> None:
        self._mail_pages: dict[Page, MailPageWidget] = {
            Page.MAIL_INBOX: MailPageWidget(),
            Page.MAIL_SENT: MailPageWidget(),
            Page.MAIL_DRAFTS: MailPageWidget(),
            Page.MAIL_SPAM: MailPageWidget(),
            Page.MAIL_TRASH: MailPageWidget(),
        }

        self._pages: dict[Page, QWidget] = {
            **self._mail_pages,
            Page.LABELS: self._create_labels_page(),
            Page.CONTACTS: self._create_contact_page(),
            Page.CALENDAR: self._create_calendar_page(),
            Page.TODO_TODAY: self._create_todo_page("today"),
            Page.TODO_WEEK: self._create_todo_page("week"),
            Page.TODO_ALL: self._create_todo_page("all"),
            Page.PROJECTS: self._create_project_page(),
            Page.SETTINGS: self._create_settings_page(),
        }
        for page in Page:
            widget = self._pages.get(page)
            if widget:
                self._content_stack.addWidget(widget)

    def _on_page_changed(self, page: Page) -> None:
        widget = self._pages.get(page)
        if widget:
            self._content_stack.setCurrentWidget(widget)

        is_mail = page in (
            Page.MAIL_INBOX,
            Page.MAIL_SENT,
            Page.MAIL_DRAFTS,
            Page.MAIL_SPAM,
            Page.MAIL_TRASH,
        )
        self._detail_widget.setVisible(is_mail)

        if is_mail:
            self._load_mail_page(page)

        page_names = {
            Page.MAIL_INBOX: "收件箱",
            Page.MAIL_SENT: "已发送",
            Page.MAIL_DRAFTS: "草稿",
            Page.MAIL_SPAM: "垃圾邮件",
            Page.MAIL_TRASH: "已删除",
            Page.CONTACTS: "联系人",
            Page.CALENDAR: "日历",
            Page.TODO_TODAY: "今天",
            Page.TODO_WEEK: "本周",
            Page.TODO_ALL: "全部待办",
            Page.PROJECTS: "项目板",
            Page.SETTINGS: "设置",
        }
        self._statusbar.showMessage(f"当前视图: {page_names.get(page, '')}")

    def _load_mail_page(self, page: Page) -> None:
        account = Account.get_default_for_display()
        if not account:
            mail_page = self._mail_pages.get(page)
            if mail_page:
                mail_page._mail_list.set_title("请先配置邮箱")
                mail_page._mail_list.load_emails([])

                # 检查是否有需要修复的账号
                need_action_accounts = Account.get_need_action_accounts()
                if need_action_accounts:
                    # 如果有需要修复的账号，可以在这里提示用户
                    pass
            return

        folder_name_map = {
            Page.MAIL_INBOX: "INBOX",
            Page.MAIL_SENT: "Sent",
            Page.MAIL_DRAFTS: "Drafts",
            Page.MAIL_SPAM: "Spam",
            Page.MAIL_TRASH: "Trash",
        }

        mail_page = self._mail_pages.get(page)
        if not mail_page:
            return

        if page == Page.MAIL_SPAM:
            mail_page.load_spam(account)
        else:
            folder_name = folder_name_map.get(page, "INBOX")
            folder = Folder.get_by_name(account.id, folder_name)
            if folder:
                mail_page.load_folder(account, folder)
            else:
                Folder.ensure_system_folders(account.id)
                folder = Folder.get_by_name(account.id, folder_name)
                if folder:
                    mail_page.load_folder(account, folder)
                else:
                    mail_page._mail_list.set_title(folder_name)
                    mail_page._mail_list.load_emails([])

    def _refresh_mail_lists(self) -> None:
        """刷新所有邮件列表（标签变化时调用）"""
        current_page = self._sidebar._buttons[0]._page if self._sidebar._buttons else 0
        self._load_mail_page(current_page)

    def show_email_detail(self, email_obj: Email) -> None:
        self._mail_view.load_email(email_obj)

    def clear_email_detail(self) -> None:
        self._mail_view.clear()

    def _on_reply(self, email_id: int) -> None:
        email_obj = Email.get_by_id(email_id)
        if email_obj:
            self._open_compose_reply(email_obj, reply_all=False)

    def _on_reply_all(self, email_id: int) -> None:
        email_obj = Email.get_by_id(email_id)
        if email_obj:
            self._open_compose_reply(email_obj, reply_all=True)

    def _on_forward(self, email_id: int) -> None:
        email_obj = Email.get_by_id(email_id)
        if email_obj:
            self._open_compose_forward(email_obj)

    def _on_delete_from_view(self, email_id: int) -> None:
        email_obj = Email.get_by_id(email_id)
        if email_obj:
            email_obj.is_deleted = True
            from openemail.storage.database import db

            db.update("emails", {"is_deleted": 1}, "id = ?", (email_id,))
            self._mail_view.clear()

    def _open_compose_reply(self, email_obj: Email, reply_all: bool = False) -> None:
        account = Account.get_default_for_display()
        if not account:
            self._statusbar.showMessage("没有可用邮箱账号，无法回复邮件")
            return
        from openemail.ui.mail.compose_window import ComposeWindow

        compose = ComposeWindow(account, self)
        compose.set_reply(email_obj, reply_all=reply_all)
        compose.exec()

    def _open_compose_forward(self, email_obj: Email) -> None:
        account = Account.get_default_for_display()
        if not account:
            self._statusbar.showMessage("没有可用邮箱账号，无法转发邮件")
            return
        from openemail.ui.mail.compose_window import ComposeWindow

        compose = ComposeWindow(account, self)
        compose.set_forward(email_obj)
        compose.exec()

    def _show_manage_accounts(self) -> None:
        """显示账户管理对话框"""
        try:
            from openemail.ui.accounts_dialog import AccountsDialog
        except ImportError:
            from PyQt6.QtWidgets import QMessageBox

            QMessageBox.warning(
                self, "功能未实现", "账户管理功能尚未实现，请使用'添加邮箱'功能。"
            )
            return

        dialog = AccountsDialog(parent=self)
        dialog.accounts_changed.connect(self._on_accounts_changed)
        dialog.exec()

    def _show_add_account(self) -> None:
        from openemail.ui.mail.account_dialog import AccountDialog

        dialog = AccountDialog(parent=self)
        dialog.account_saved.connect(self._on_account_added)
        dialog.exec()

    def _on_account_added(self, account_id: int) -> None:
        account = Account.get_by_id(account_id)
        if account:
            Folder.ensure_system_folders(account_id)
        self._statusbar.showMessage(f"账户已添加: {account.email if account else ''}")

    def _on_setup_completed(self) -> None:
        """设置完成后的初始化（与首次同步解耦）"""
        logger.info("引导设置完成，准备初始化应用")

        # 更新状态栏
        self._statusbar.showMessage("设置完成！应用正在初始化...", 3000)

        # 延迟触发首次同步（非阻塞方式）
        from PyQt6.QtCore import QTimer

        QTimer.singleShot(2000, self._schedule_initial_sync)

        # 刷新界面显示
        self._refresh_all()

        # 显示欢迎提示
        self._show_welcome_hint()

    def _schedule_initial_sync(self) -> None:
        """调度首次同步（收紧触发条件）"""
        try:
            # 1. 检查主窗口对象是否仍有效
            if not self or not self.isVisible():
                logger.warning("主窗口无效或不可见，跳过首次同步调度")
                return

            # 2. 检查是否有重复同步任务（简单防抖）
            if (
                hasattr(self, "_initial_sync_scheduled")
                and self._initial_sync_scheduled
            ):
                logger.warning("首次同步已调度，避免重复调度")
                return
            self._initial_sync_scheduled = True

            # 3. 延迟1秒执行，确保UI完全初始化
            from PyQt6.QtCore import QTimer

            logger.info("调度首次同步：1秒后执行")
            QTimer.singleShot(1000, self._check_and_perform_initial_sync)

        except Exception as e:
            logger.error("调度首次同步时出错: %s", str(e))

    def _check_and_perform_initial_sync(self) -> None:
        """检查和执行首次同步（更严格的条件）"""
        try:
            # 1. 再次检查主窗口对象有效性
            if not self or not self.isVisible():
                logger.warning("检查同步时主窗口无效，取消同步")
                return

            # 2. 获取可同步账户（批次D/D2）
            accounts = Account.get_syncable()
            if not accounts:
                logger.warning("没有可同步的账户")
                need_action = Account.get_need_action_accounts()
                if need_action:
                    msg = f"有 {len(need_action)} 个账户需要修复"
                else:
                    msg = "请先添加并验证邮箱账户"
                self._statusbar.showMessage(msg, 3000)
                return

            # 3. 检查每个账户是否允许同步（已由get_syncable()确保）
            # 目前先检查是否有账户数据
            valid_accounts = []
            for account in accounts:
                if account and account.email:
                    # 基本检查：账户对象有效且有邮箱
                    # 未来这里会检查 connection_status 等字段
                    valid_accounts.append(account)

            if not valid_accounts:
                logger.warning("无有效账户可同步")
                self._statusbar.showMessage("所有账户状态异常，无法同步", 3000)
                return

            # 4. 执行同步
            logger.info("开始执行首次同步，有效账户数: %d", len(valid_accounts))
            self._statusbar.showMessage(
                f"正在同步 {len(valid_accounts)} 个账户的邮件..."
            )
            self._perform_initial_sync(valid_accounts)

        except Exception as e:
            logger.error("检查并执行首次同步时出错: %s", str(e))
            self._statusbar.showMessage("同步准备失败，请稍后手动同步", 5000)
        finally:
            # 重置调度标志
            if hasattr(self, "_initial_sync_scheduled"):
                self._initial_sync_scheduled = False

    def _perform_initial_sync(self, accounts) -> None:
        """执行首次同步（带账户过滤）"""
        try:
            # 记录同步开始
            logger.info(
                "执行首次同步，账户列表: %s",
                [f"{acc.email}(id:{acc.id})" for acc in accounts],
            )

            # 调用同步管理器
            from openemail.core.mail_sync import mail_sync_manager

            mail_sync_manager.sync_all()

            # 显示同步状态
            self._statusbar.showMessage(f"正在同步 {len(accounts)} 个账户...", 3000)

            # 设置状态跟踪
            self._last_sync_time = "刚刚"

        except Exception as e:
            logger.error("首次同步失败: %s", str(e))
            self._statusbar.showMessage(f"同步失败: {str(e)}", 5000)

    def _show_welcome_hint(self) -> None:
        """显示欢迎提示（在状态栏显示）"""
        import random

        hints = [
            "欢迎使用 OpenEmail！",
            "您可以在设置中添加更多邮箱账户。",
            "试试深色/浅色主题切换功能。",
            "使用搜索功能快速查找邮件。",
            "设置邮件规则来自动管理邮件。",
        ]
        hint = random.choice(hints)
        self._statusbar.showMessage(f"💡 {hint}", 5000)

    def _show_compose(self) -> None:
        account = Account.get_default_for_display()
        if not account:
            need_action = Account.get_need_action_accounts()
            if need_action:
                msg = f"有 {len(need_action)} 个邮箱需要修复或验证"
            else:
                msg = "请先添加邮箱账户"
            self._statusbar.showMessage(msg)
            return

        # 使用增强版撰写窗口
        try:
            from openemail.ui.mail.compose_window import ComposeWindowEnhanced

            compose = ComposeWindowEnhanced(account, self)
        except ImportError:
            # 如果增强版不可用，回退到原版
            from openemail.ui.mail.compose_window import ComposeWindow

            compose = ComposeWindow(account, self)

        compose.sent.connect(lambda: self._statusbar.showMessage("邮件已发送", 3000))
        compose.exec()

    def _setup_auto_sync(self) -> None:
        """设置自动同步：连接信号 + 定时器"""
        from PyQt6.QtCore import QTimer
        from openemail.core.mail_sync import mail_sync_manager

        # 连接同步完成信号，刷新当前邮件列表
        mail_sync_manager.sync_finished.connect(self._on_sync_finished)
        mail_sync_manager.sync_error.connect(self._on_sync_error)

        # 定时自动同步（每 5 分钟）
        self._auto_sync_timer = QTimer(self)
        self._auto_sync_timer.timeout.connect(self._auto_sync)
        self._auto_sync_timer.start(5 * 60 * 1000)  # 5 minutes

    def _auto_sync(self) -> None:
        """定时触发后台同步（静默，不打扰用户）"""
        from openemail.core.mail_sync import mail_sync_manager

        # sync_all() 内部已有 isRunning() 防重入
        mail_sync_manager.sync_all()

    def _on_sync_finished(self, account_id: int, total: int) -> None:
        """同步完成，刷新当前显示的邮件列表"""
        if total > 0:
            logger.info("账户 %d 同步完成，新增 %d 封邮件", account_id, total)
            self._reload_current_folder()
        self._statusbar.showMessage("同步完成", 2000)

    def _on_sync_error(self, account_id: int, error_msg: str) -> None:
        """同步出错，仅日志"""
        logger.warning("账户 %d 同步出错: %s", account_id, error_msg)

    def _reload_current_folder(self) -> None:
        """重新加载当前文件夹的邮件列表"""
        try:
            if hasattr(self, "_current_account") and hasattr(self, "_current_folder"):
                if self._current_account and self._current_folder:
                    self.load_folder(self._current_account, self._current_folder)
        except Exception:
            logger.debug("刷新邮件列表时出错", exc_info=True)

    def _sync_all(self) -> None:
        from openemail.core.mail_sync import mail_sync_manager

        mail_sync_manager.sync_all()
        self._statusbar.showMessage("正在同步...")

    def _set_theme(self, theme: str) -> None:
        settings.theme = theme
        self._update_theme_actions()
        from openemail.app import apply_theme

        apply_theme()

    def _show_filter_rules(self) -> None:
        from openemail.ui.filter.filter_dialog import FilterRulesDialog

        dialog = FilterRulesDialog(self)
        dialog.exec()

    def _navigate_to_settings(self) -> None:
        self._sidebar.set_active_page(Page.SETTINGS)
        self._on_page_changed(Page.SETTINGS)

    def _show_account_settings(self) -> None:
        """显示账户设置面板"""
        from openemail.ui.settings.account_settings import AccountSettingsPanel

        self._account_settings_panel = AccountSettingsPanel(self)
        self._account_settings_panel.setWindowTitle("账户设置")
        self._account_settings_panel.setMinimumSize(600, 500)
        self._account_settings_panel.account_changed.connect(self._on_accounts_changed)
        self._account_settings_panel.exec()

    def _on_accounts_changed(self) -> None:
        self._load_mail_page(
            self._sidebar._buttons[0]._page if self._sidebar._buttons else 0
        )
        self._update_account_label()

    def _on_theme_changed_from_settings(self) -> None:
        from openemail.app import apply_theme

        apply_theme()
        self._update_theme_actions()

    def _update_account_label(self) -> None:
        account = Account.get_default_for_display()
        if account:
            self._account_label.setText(f"📧 {account.email}")
        else:
            self._account_label.setText("")

    def _update_theme_actions(self) -> None:
        theme = settings.theme
        self._light_action.setChecked(theme == "light")
        self._dark_action.setChecked(theme == "dark")
        self._system_action.setChecked(theme == "system")

    def _restore_geometry(self) -> None:
        geo = settings.window_geometry
        x, y = geo.get("x", -1), geo.get("y", -1)
        w, h = geo.get("width", 1200), geo.get("height", 800)
        self.resize(w, h)
        if x >= 0 and y >= 0:
            self.move(x, y)

    def closeEvent(self, event) -> None:
        from openemail.core.mail_sync import mail_sync_manager

        mail_sync_manager.stop_all()

        geo = self.geometry()
        central = self.centralWidget()
        main_layout = central.layout()
        content_item = main_layout.itemAt(1)
        if content_item and isinstance(content_item.layout(), QHBoxLayout):
            splitter_item = content_item.layout().itemAt(0)
            if splitter_item and isinstance(splitter_item.widget(), QSplitter):
                sidebar_w = splitter_item.widget().sizes()[0]
            else:
                sidebar_w = 220
        else:
            sidebar_w = 220
        settings.save_window_geometry(
            geo.x(), geo.y(), geo.width(), geo.height(), sidebar_w
        )

        super().closeEvent(event)
