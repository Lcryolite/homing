from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QAction
from PyQt6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QSplitter,
    QStackedWidget,
    QStatusBar,
    QVBoxLayout,
    QWidget,
)

from openemail.config import settings
from openemail.models.account import Account
from openemail.models.email import Email
from openemail.models.folder import Folder, SYSTEM_FOLDERS
from openemail.ui.sidebar import Page, Sidebar


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
        self._setup_ui()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        from openemail.ui.mail.search_bar import SearchBar

        self._search_bar = SearchBar()
        self._search_bar.search_requested.connect(self._on_search)
        self._search_bar.search_cleared.connect(self._on_search_cleared)
        layout.addWidget(self._search_bar)

        from openemail.ui.mail.mail_list import MailListWidget

        self._mail_list = MailListWidget()
        self._mail_list.email_selected.connect(self._on_email_selected)
        self._mail_list.mark_read_requested.connect(self._on_mark_read)
        self._mail_list.mark_flagged_requested.connect(self._on_mark_flagged)
        self._mail_list.delete_requested.connect(self._on_delete_email)
        self._mail_list.mark_spam_requested.connect(self._on_mark_spam)
        self._mail_list.mark_not_spam_requested.connect(self._on_mark_not_spam)
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

        emails = Email.get_by_folder(folder.id)
        self._mail_list.load_emails(emails)

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

    def _on_search(self, query: str) -> None:
        if self._current_account:
            emails = Email.search(self._current_account.id, query)
            self._mail_list.load_emails(emails)
            self._mail_list.set_title(f"搜索: {query}")

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


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self._setup_window()
        self._setup_menubar()
        self._setup_ui()
        self._restore_geometry()
        # 暂时禁用首次启动检测，让用户通过菜单添加账户
        # self._check_first_run()

    def _check_first_run(self) -> None:
        """检查是否首次启动"""
        from openemail.models.account import Account

        accounts = Account.get_all_active()
        if not accounts:
            # 首次启动，无账户 → 显示引导对话框
            from openemail.ui.mail.welcome_dialog import WelcomeDialog

            dialog = WelcomeDialog(self)
            dialog.account_added.connect(self._on_account_added)
            dialog.exec()

    def _setup_window(self) -> None:
        self.setWindowTitle("OpenEmail")
        self.setMinimumSize(800, 600)

    def _setup_menubar(self) -> None:
        menubar = self.menuBar()

        file_menu = menubar.addMenu("文件")
        add_account_action = QAction("添加账户", self)
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
        account_settings_action.triggered.connect(self._show_account_settings)
        tools_menu.addAction(account_settings_action)

        help_menu = menubar.addMenu("帮助")
        about_action = QAction("关于", self)
        help_menu.addAction(about_action)

    def _setup_ui(self) -> None:
        central = QWidget()
        self.setCentralWidget(central)

        main_layout = QHBoxLayout(central)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        self._sidebar = Sidebar()
        self._sidebar.page_changed.connect(self._on_page_changed)

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

        main_layout.addWidget(main_splitter)

        self._statusbar = QStatusBar()
        self.setStatusBar(self._statusbar)
        self._statusbar.showMessage("就绪")

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
            Page.CALENDAR: PlaceholderPage("日历", "日历视图将在此显示"),
            Page.TODO_TODAY: PlaceholderPage("今天", "今天的待办事项将在此显示"),
            Page.TODO_WEEK: PlaceholderPage("本周", "本周的待办事项将在此显示"),
            Page.TODO_ALL: PlaceholderPage("全部待办", "所有待办事项将在此显示"),
            Page.PROJECTS: PlaceholderPage("项目板", "项目看板将在此显示"),
            Page.SETTINGS: PlaceholderPage("设置", "应用设置将在此显示"),
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
            Page.CALENDAR: "日历",
            Page.TODO_TODAY: "今天",
            Page.TODO_WEEK: "本周",
            Page.TODO_ALL: "全部待办",
            Page.PROJECTS: "项目板",
            Page.SETTINGS: "设置",
        }
        self._statusbar.showMessage(f"当前视图: {page_names.get(page, '')}")

    def _load_mail_page(self, page: Page) -> None:
        accounts = Account.get_all_active()
        if not accounts:
            mail_page = self._mail_pages.get(page)
            if mail_page:
                mail_page._mail_list.set_title("请先添加账户")
                mail_page._mail_list.load_emails([])
            return

        account = accounts[0]

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
        accounts = Account.get_all_active()
        if not accounts:
            return
        from openemail.ui.mail.compose_window import ComposeWindow

        compose = ComposeWindow(accounts[0], self)
        compose.set_reply(email_obj, reply_all=reply_all)
        compose.exec()

    def _open_compose_forward(self, email_obj: Email) -> None:
        accounts = Account.get_all_active()
        if not accounts:
            return
        from openemail.ui.mail.compose_window import ComposeWindow

        compose = ComposeWindow(accounts[0], self)
        compose.set_forward(email_obj)
        compose.exec()

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

    def _show_compose(self) -> None:
        accounts = Account.get_all_active()
        if not accounts:
            self._statusbar.showMessage("请先添加账户")
            return
        from openemail.ui.mail.compose_window import ComposeWindow

        compose = ComposeWindow(accounts[0], self)
        compose.exec()

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
        """显示过滤规则管理"""
        from openemail.ui.filter.filter_dialog import FilterRulesDialog

        dialog = FilterRulesDialog(self)
        dialog.exec()

    def _show_account_settings(self) -> None:
        """显示账户设置面板"""
        from openemail.ui.settings.account_settings import AccountSettingsPanel

        self._account_settings_panel = AccountSettingsPanel(self)
        self._account_settings_panel.setWindowTitle("账户设置")
        self._account_settings_panel.setMinimumSize(600, 500)
        self._account_settings_panel.account_changed.connect(self._on_accounts_changed)
        self._account_settings_panel.exec()

    def _on_accounts_changed(self) -> None:
        """账户改变后重新加载"""
        self._load_mail_page(
            self._sidebar._buttons[0]._page if self._sidebar._buttons else 0
        )

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
        splitter = self.centralWidget().layout().itemAt(0)
        if splitter and isinstance(splitter.widget(), QSplitter):
            sidebar_w = splitter.widget().sizes()[0]
        else:
            sidebar_w = 220
        settings.save_window_geometry(
            geo.x(), geo.y(), geo.width(), geo.height(), sidebar_w
        )
        super().closeEvent(event)
