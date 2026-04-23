from __future__ import annotations

import asyncio
import logging
import os

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QKeySequence, QShortcut
from PyQt6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QSplitter,
    QTextEdit,
    QVBoxLayout,
    QWidget,
    QTabWidget,
    QFrame,
    QMenu,
    QColorDialog,
)

from openemail.core.mail_builder import MailBuilder
from openemail.core.smtp_client import SMTPClient
from openemail.core.draft_autosave import DraftAutoSave
from openemail.models.account import Account
from openemail.models.draft import Draft
from openemail.models.email import Email
from openemail.core.mail_parser import MailParser
from openemail.storage.mail_store import mail_store
from openemail.ui.mail.attachment_manager import AttachmentManager
from openemail.utils.i18n import get_string

logger = logging.getLogger(__name__)


class ComposeWindow(QDialog):
    """原撰写窗口，保持向后兼容"""

    sent = pyqtSignal()

    def __init__(self, account: Account, draft_id: int = 0, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._account = account
        self._draft_id = draft_id
        self._reply_to_email: Email | None = None
        self._forward_email: Email | None = None
        self._attachments: list[str] = []
        self._autosave = DraftAutoSave(account.id, self)
        self._setup_ui()
        self._setup_keyboard_shortcuts()

    def _setup_ui(self) -> None:
        self.setWindowTitle(get_string("ComposeWindow", "window_title_compose"))
        self.setMinimumSize(700, 500)
        self.resize(900, 700)

        main_layout = QVBoxLayout(self)
        main_layout.setSpacing(0)
        main_layout.setContentsMargins(0, 0, 0, 0)

        # 创建主分割器
        splitter = QSplitter(Qt.Orientation.Vertical)
        main_layout.addWidget(splitter, 1)

        # 上半部分：邮件头信息
        top_widget = QWidget()
        top_layout = QVBoxLayout(top_widget)
        top_layout.setSpacing(8)
        top_layout.setContentsMargins(12, 12, 12, 12)

        # 发件人
        from_row = QHBoxLayout()
        from_label = QLabel("发件人:")
        from_label.setFixedWidth(70)
        self._from_field = QLineEdit(self._account.email)
        self._from_field.setReadOnly(True)
        self._from_field.setStyleSheet("""
            QLineEdit {
                border-radius: 4px;
                padding: 6px 8px;
            }
        """)
        from_row.addWidget(from_label)
        from_row.addWidget(self._from_field, 1)
        top_layout.addLayout(from_row)

        # 收件人
        to_row = QHBoxLayout()
        to_label = QLabel("收件人:")
        to_label.setFixedWidth(70)
        self._to_field = QLineEdit()
        self._to_field.setPlaceholderText("输入收件人地址，多个用逗号分隔")
        self._to_field.setStyleSheet("""
            QLineEdit {
                border-radius: 4px;
                padding: 6px 8px;
            }
            QLineEdit:focus {
                border-color: #7C8A9A;
            }
        """)
        to_row.addWidget(to_label)
        to_row.addWidget(self._to_field, 1)
        top_layout.addLayout(to_row)

        # 抄送
        cc_row = QHBoxLayout()
        cc_label = QLabel("抄送:")
        cc_label.setFixedWidth(70)
        self._cc_field = QLineEdit()
        self._cc_field.setPlaceholderText("抄送地址，多个用逗号分隔")
        self._cc_field.setStyleSheet("""
            QLineEdit {
                border-radius: 4px;
                padding: 6px 8px;
            }
            QLineEdit:focus {
                border-color: #7C8A9A;
            }
        """)
        cc_row.addWidget(cc_label)
        cc_row.addWidget(self._cc_field, 1)
        top_layout.addLayout(cc_row)

        # 主题
        subject_row = QHBoxLayout()
        subject_label = QLabel("主题:")
        subject_label.setFixedWidth(70)
        self._subject_field = QLineEdit()
        self._subject_field.setPlaceholderText("邮件主题")
        self._subject_field.setStyleSheet("""
            QLineEdit {
                border-radius: 4px;
                padding: 6px 8px;
                font-size: 14px;
            }
            QLineEdit:focus {
                border-color: #7C8A9A;
            }
        """)
        subject_row.addWidget(subject_label)
        subject_row.addWidget(self._subject_field, 1)
        top_layout.addLayout(subject_row)

        splitter.addWidget(top_widget)
        splitter.setStretchFactor(0, 2)

        # 中间部分：正文编辑器
        editor_widget = QWidget()
        editor_layout = QVBoxLayout(editor_widget)
        editor_layout.setSpacing(0)
        editor_layout.setContentsMargins(0, 0, 0, 0)

        # 创建标签页（纯文本/富文本）
        self.tab_widget = QTabWidget()

        # 纯文本编辑器
        self._body_edit = QTextEdit()
        self._body_edit.setPlaceholderText("在此输入邮件正文...")
        self._body_edit.setAcceptRichText(False)
        self._body_edit.setStyleSheet("""
            QTextEdit {
                border: none;
                font-family: sans-serif;
                font-size: 13px;
                line-height: 1.5;
            }
            QTextEdit:focus {
                border: none;
            }
        """)
        self.tab_widget.addTab(self._body_edit, "纯文本")

        # 富文本编辑器
        self._html_edit = QTextEdit()
        self._html_edit.setPlaceholderText("在此输入邮件正文（支持富文本格式）...")
        self._html_edit.setAcceptRichText(True)
        self._html_edit.setStyleSheet(self._body_edit.styleSheet())
        self.tab_widget.addTab(self._html_edit, "富文本")
        self.tab_widget.currentChanged.connect(self._on_tab_changed)

        editor_layout.addWidget(self.tab_widget)
        splitter.addWidget(editor_widget)
        splitter.setStretchFactor(1, 4)

        # 下半部分：附件管理器
        bottom_widget = QWidget()
        bottom_layout = QVBoxLayout(bottom_widget)
        bottom_layout.setSpacing(0)
        bottom_layout.setContentsMargins(0, 0, 0, 0)

        self.attachment_manager = AttachmentManager()
        self.attachment_manager.setMaximumHeight(200)
        self.attachment_manager.attachments_changed.connect(
            self._on_attachments_changed
        )
        self.attachment_manager.max_size_reached.connect(self._on_max_size_reached)
        self.attachment_manager.setStyleSheet("""
            AttachmentManager {
                border-top: 1px solid #E8E1D8;
            }
        """)
        bottom_layout.addWidget(self.attachment_manager)

        splitter.addWidget(bottom_widget)
        splitter.setStretchFactor(2, 1)

        # 设置分割器初始比例
        splitter.setSizes([100, 400, 100])

        # 底部按钮栏
        bottom_buttons = QFrame()
        bottom_buttons.setFrameStyle(QFrame.Shape.Box)
        bottom_buttons.setStyleSheet("""
            QFrame {
                border-top: 1px solid #E8E1D8;
                padding: 0;
            }
        """)
        btn_layout = QHBoxLayout(bottom_buttons)
        btn_layout.setContentsMargins(12, 8, 12, 8)
        btn_layout.setSpacing(12)

        # 格式按钮（预留）
        format_layout = QHBoxLayout()
        format_layout.setSpacing(6)

        self.bold_btn = QPushButton("粗体")
        self.bold_btn.setFixedSize(75, 28)
        self.bold_btn.clicked.connect(self._on_bold)
        self.italic_btn = QPushButton("斜体")
        self.italic_btn.setFixedSize(75, 28)
        self.italic_btn.clicked.connect(self._on_italic)
        self.underline_btn = QPushButton("下划线")
        self.underline_btn.setFixedSize(75, 28)
        self.underline_btn.clicked.connect(self._on_underline)
        self.bullet_list_btn = QPushButton("• 列表")
        self.bullet_list_btn.setFixedSize(75, 28)
        self.bullet_list_btn.clicked.connect(self._on_bullet_list)
        self.font_color_btn = QPushButton("颜色")
        self.font_color_btn.setFixedSize(75, 28)
        self.font_color_btn.clicked.connect(self._on_font_color)
        self.font_size_combo = QPushButton("大小")
        self.font_size_combo.setFixedSize(75, 28)
        self.font_size_combo.setMenu(self._create_font_size_menu())

        format_layout.addWidget(self.bold_btn)
        format_layout.addWidget(self.italic_btn)
        format_layout.addWidget(self.underline_btn)
        format_layout.addWidget(self.bullet_list_btn)
        format_layout.addWidget(self.font_color_btn)
        format_layout.addWidget(self.font_size_combo)
        format_layout.addStretch()

        btn_layout.addLayout(format_layout, 1)

        # 动作按钮
        attach_btn = QPushButton("📎 添加附件")
        attach_btn.setFixedSize(100, 28)
        attach_btn.clicked.connect(self.attachment_manager._add_attachments)
        btn_layout.addWidget(attach_btn)

        self._save_draft_btn = QPushButton("存草稿")
        self._save_draft_btn.setFixedSize(80, 28)
        self._save_draft_btn.clicked.connect(self._save_draft)
        btn_layout.addWidget(self._save_draft_btn)

        self._send_btn = QPushButton(get_string("ComposeWindow", "btn_send"))
        self._send_btn.setProperty("class", "primary")
        self._send_btn.setFixedSize(100, 28)
        self._send_btn.clicked.connect(self._on_send)
        btn_layout.addWidget(self._send_btn)

        cancel_btn = QPushButton("取消")
        cancel_btn.setFixedSize(80, 28)
        cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(cancel_btn)

        main_layout.addWidget(bottom_buttons)

        self._to_field.textChanged.connect(self._on_content_changed)
        self._cc_field.textChanged.connect(self._on_content_changed)
        self._subject_field.textChanged.connect(self._on_content_changed)
        self._body_edit.textChanged.connect(self._on_content_changed)
        self._html_edit.textChanged.connect(self._on_content_changed)

        self._autosave.update_content(from_addr=self._account.email)

        # Restore draft if draft_id provided
        if self._draft_id:
            self._autosave.load_draft(self._draft_id)
            draft = Draft.get_by_id(self._draft_id)
            if draft:
                self._from_field.setText(draft.from_addr)
                self._to_field.setText(draft.to_addrs)
                self._cc_field.setText(draft.cc_addrs)
                self._subject_field.setText(draft.subject)
                self._body_edit.setPlainText(draft.body_text)
                if draft.body_html:
                    self._html_edit.setHtml(draft.body_html)
                if draft.attachments:
                    try:
                        import json
                        atts = json.loads(draft.attachments)
                        for att in atts:
                            if isinstance(att, dict) and att.get("path"):
                                self.attachment_manager.add_attachments([att["path"]])
                    except Exception as e:
                        logger.warning("Failed to restore draft attachments: %s", e)

        self._autosave.start()

    def _on_content_changed(self) -> None:
        body_text = (
            self._html_edit.toPlainText()
            if self.tab_widget.currentIndex() == 1
            else self._body_edit.toPlainText()
        )
        self._autosave.update_content(
            from_addr=self._account.email,
            to_addrs=self._to_field.text().strip(),
            cc_addrs=self._cc_field.text().strip(),
            subject=self._subject_field.text().strip(),
            body_text=body_text,
        )

    def reject(self) -> None:
        self._autosave.stop()
        super().reject()

    def closeEvent(self, event) -> None:
        """窗口关闭（包括点 X 按钮）时强制保存草稿"""
        self._autosave.stop()
        event.accept()

    def _on_attachments_changed(self, attachments: list[str]) -> None:
        """附件变化时更新"""
        self._attachments = attachments

    def _on_max_size_reached(self) -> None:
        """附件总大小超限提示"""
        from PyQt6.QtWidgets import QMessageBox

        QMessageBox.warning(
            self,
            "大小限制",
            "附件总大小已超过限制。\n"
            "建议的解决方案：\n"
            "1. 删除部分大附件\n"
            "2. 使用云存储分享链接\n"
            "3. 分批发送邮件",
        )

    def _save_draft(self) -> None:
        """保存草稿到本地数据库"""
        body_text = (
            self._html_edit.toPlainText()
            if self.tab_widget.currentIndex() == 1
            else self._body_edit.toPlainText()
        )
        self._autosave.update_content(
            from_addr=self._account.email,
            to_addrs=self._to_field.text().strip(),
            cc_addrs=self._cc_field.text().strip(),
            subject=self._subject_field.text().strip(),
            body_text=body_text,
        )
        draft_id = self._autosave.save_now()
        if draft_id:
            # Trigger background remote sync
            try:
                import threading
                from openemail.core.draft_syncer import DraftSyncer
                from openemail.models.draft import Draft

                draft = Draft.get_by_id(draft_id)
                if draft:

                    def _sync():
                        loop = asyncio.new_event_loop()
                        asyncio.set_event_loop(loop)
                        try:
                            loop.run_until_complete(
                                DraftSyncer.sync_draft_to_remote(self._account, draft)
                            )
                        finally:
                            loop.close()

                    t = threading.Thread(target=_sync, daemon=True)
                    t.start()
            except Exception as e:
                logger.debug("Background draft sync trigger failed: %s", e)

            from PyQt6.QtWidgets import QMessageBox

            QMessageBox.information(
                self,
                get_string("ComposeWindow", "draft_saved"),
                get_string("ComposeWindow", "draft_saved_local"),
            )
        else:
            from PyQt6.QtWidgets import QMessageBox

            QMessageBox.warning(
                self,
                get_string("ComposeWindow", "draft_save_failed"),
                get_string("ComposeWindow", "draft_save_failed_msg"),
            )

    def set_reply(self, email_obj: Email, reply_all: bool = False) -> None:
        self._reply_to_email = email_obj
        self.setWindowTitle(get_string("ComposeWindow", "window_title_reply"))

        to_addrs = []
        if reply_all:
            to_addrs = email_obj.to_list + email_obj.cc_list
            to_addrs = [a for a in to_addrs if a != self._account.email]
            if email_obj.sender_addr != self._account.email:
                to_addrs.insert(0, email_obj.sender_addr)
        else:
            to_addrs = [email_obj.sender_addr]

        self._to_field.setText(", ".join(to_addrs))
        self._subject_field.setText(f"Re: {email_obj.subject}")

        reply_prefix = (
            f"\n\n--- 在 {email_obj.date}，{email_obj.display_sender} 写道：---\n"
        )
        self._body_edit.setPlainText(reply_prefix)
        # 如果当前是HTML模式，同步内容
        if self.tab_widget.currentIndex() == 1:
            self._html_edit.setHtml(self._convert_plain_to_html(reply_prefix))

        if email_obj.file_path:
            raw = mail_store.read_raw(email_obj.file_path)
            if raw:
                parsed = MailParser.parse_raw(raw)
                original_text = parsed.text_body or "(HTML邮件，请查看原邮件)"
                # 添加缩进和引用标记
                lines = original_text.split("\n")
                quoted_lines = [f"> {line}" for line in lines]
                quoted_text = "\n".join(quoted_lines)
                self._body_edit.append(quoted_text)
                # 同步到HTML编辑器
                if self.tab_widget.currentIndex() == 1:
                    current_html = self._html_edit.toHtml()
                    new_content = self._convert_plain_to_html(quoted_text)
                    self._html_edit.setHtml(current_html + new_content)

    def set_forward(self, email_obj: Email) -> None:
        self._forward_email = email_obj
        self.setWindowTitle(get_string("ComposeWindow", "window_title_forward"))

        self._subject_field.setText(f"Fwd: {email_obj.subject}")

        forward_prefix = f"\n\n--- 转发邮件 ---\n发件人: {email_obj.display_sender}\n收件人: {email_obj.display_to}\n日期: {email_obj.date}\n主题: {email_obj.subject}\n"
        self._body_edit.setPlainText(forward_prefix)
        # 如果当前是HTML模式，同步内容
        if self.tab_widget.currentIndex() == 1:
            self._html_edit.setHtml(self._convert_plain_to_html(forward_prefix))

        if email_obj.file_path:
            raw = mail_store.read_raw(email_obj.file_path)
            if raw:
                parsed = MailParser.parse_raw(raw)
                original_text = parsed.text_body or "(HTML邮件，请查看原邮件)"
                self._body_edit.append(f"\n{original_text}")
                # 同步到HTML编辑器
                if self.tab_widget.currentIndex() == 1:
                    current_html = self._html_edit.toHtml()
                    new_content = self._convert_plain_to_html(f"\n{original_text}")
                    self._html_edit.setHtml(current_html + new_content)

                # 如果原邮件有附件，也添加到附件管理器
                if parsed.attachments:
                    # 创建临时文件保存附件
                    import tempfile

                    for att in parsed.attachments:
                        try:
                            # 创建临时文件
                            with tempfile.NamedTemporaryFile(
                                delete=False, suffix=att["filename"]
                            ) as tmp:
                                tmp.write(att["data"])
                                tmp_path = tmp.name

                            # 添加到附件管理器
                            self.attachment_manager.add_attachments([tmp_path])
                        except Exception as e:
                            logger.error("无法保存转发附件: %s", e)

    def _on_send(self) -> None:
        to_text = self._to_field.text().strip()
        if not to_text:
            return

        to_addrs = [a.strip() for a in to_text.split(",") if a.strip()]
        cc_text = self._cc_field.text().strip()
        cc_addrs = (
            [a.strip() for a in cc_text.split(",") if a.strip()] if cc_text else []
        )

        subject = self._subject_field.text().strip()
        is_html_mode = self.tab_widget.currentIndex() == 1
        body = self._get_html_content_for_sending()

        # 验证收件人格式
        for addr in to_addrs + cc_addrs:
            if "@" not in addr or "." not in addr.split("@")[1]:
                from PyQt6.QtWidgets import QMessageBox

                QMessageBox.warning(
                    self,
                    get_string("ComposeWindow", "format_error"),
                    get_string("ComposeWindow", "invalid_email").format(addr),
                )
                return

        self._send_btn.setEnabled(False)
        self._send_btn.setText(get_string("ComposeWindow", "btn_sending"))

        # 在后台线程中发送邮件，避免阻塞UI
        import threading

        plain_text = self._html_edit.toPlainText() if is_html_mode else ""

        thread = threading.Thread(
            target=self._do_send,
            args=(to_addrs, cc_addrs, subject, body, is_html_mode, plain_text),
        )
        thread.daemon = True
        thread.start()

    def _do_send(
        self,
        to_addrs: list[str],
        cc_addrs: list[str],
        subject: str,
        body: str,
        is_html_mode: bool,
        plain_text: str,
    ) -> None:
        """实际发送邮件的后台任务"""
        try:
            builder = MailBuilder()
            builder.set_from(self._account.email, self._account.name)
            builder.set_to(to_addrs)
            if cc_addrs:
                builder.set_cc(cc_addrs)
            builder.set_subject(subject)
            if is_html_mode:
                # HTML模式：发送HTML邮件，包含text fallback
                plain_text = self._html_edit.toPlainText()
                builder.set_html_body(body).set_text_body(plain_text)
            else:
                # 纯文本模式
                builder.set_text_body(body)

            if self._reply_to_email and self._reply_to_email.message_id:
                builder.set_in_reply_to(self._reply_to_email.message_id)
                refs = self._reply_to_email.message_id
                builder.set_references(refs)

            # 添加当前附件管理器中的附件
            if self._attachments:
                for file_path in self._attachments:
                    try:
                        with open(file_path, "rb") as f:
                            data = f.read()
                        file_name = os.path.basename(file_path)
                        mime_type = self._guess_mime_type(file_path)
                        builder.add_attachment(file_name, data, mime_type)
                    except Exception as e:
                        logger.error("无法添加附件 %s: %s", file_path, e)
                        # TODO: 发送到主线程显示错误

            # 如果是转发邮件，也包含原邮件的附件
            if self._forward_email and self._forward_email.file_path:
                raw = mail_store.read_raw(self._forward_email.file_path)
                if raw:
                    parsed = MailParser.parse_raw(raw)
                    for att in parsed.attachments:
                        builder.add_attachment(
                            att["filename"], att["data"], att["mime_type"]
                        )

            _message = builder.build()

            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

            try:
                client = SMTPClient(self._account)
                success = loop.run_until_complete(
                    client.send(
                        to=to_addrs,
                        subject=subject,
                        body_text=plain_text if is_html_mode else body,
                        body_html=body if is_html_mode else "",
                        cc=cc_addrs,
                        in_reply_to=self._reply_to_email.message_id
                        if self._reply_to_email
                        else None,
                        references=self._reply_to_email.message_id
                        if self._reply_to_email
                        else None,
                    )
                )
            finally:
                loop.close()

            # 发送完成，更新UI
            from PyQt6.QtCore import QTimer

            if success:

                def _on_success():
                    self._autosave.delete_draft()
                    self.sent.emit()
                    self.accept()

                QTimer.singleShot(0, _on_success)
            else:

                def _on_failure():
                    from PyQt6.QtWidgets import QMessageBox

                    self._send_btn.setEnabled(True)
                    self._send_btn.setText(get_string("ComposeWindow", "btn_send"))
                    QMessageBox.critical(
                        self,
                        get_string("ComposeWindow", "send_failed"),
                        get_string("ComposeWindow", "send_failed_msg"),
                    )

                QTimer.singleShot(0, _on_failure)

        except Exception as e:
            logger.error("发送异常: %s", e)
            from PyQt6.QtCore import QTimer

            err = e

            def _on_exception(exc=err):
                from PyQt6.QtWidgets import QMessageBox

                self._send_btn.setEnabled(True)
                self._send_btn.setText(get_string("ComposeWindow", "btn_send"))
                QMessageBox.critical(
                    self,
                    get_string("ComposeWindow", "send_error"),
                    f"发送过程中发生错误:\n{str(exc)}",
                )

            QTimer.singleShot(0, _on_exception)

    def _on_tab_changed(self, index: int) -> None:
        """标签页切换时更新格式按钮状态"""
        is_rich_text = index == 1  # 1是富文本标签页
        self.bold_btn.setEnabled(is_rich_text)
        self.italic_btn.setEnabled(is_rich_text)
        self.underline_btn.setEnabled(is_rich_text)
        self.bullet_list_btn.setEnabled(is_rich_text)
        self.font_color_btn.setEnabled(is_rich_text)
        self.font_size_combo.setEnabled(is_rich_text)

        # 如果是切换到富文本，确保内容同步
        if is_rich_text and self._body_edit.toPlainText():
            self._html_edit.setHtml(
                self._convert_plain_to_html(self._body_edit.toPlainText())
            )

    def _on_bold(self) -> None:
        """粗体切换"""
        if self.tab_widget.currentIndex() == 1:  # 富文本模式
            font = self._html_edit.currentFont()
            font.setBold(not font.bold())
            self._html_edit.setCurrentFont(font)

    def _on_italic(self) -> None:
        """斜体切换"""
        if self.tab_widget.currentIndex() == 1:  # 富文本模式
            font = self._html_edit.currentFont()
            font.setItalic(not font.italic())
            self._html_edit.setCurrentFont(font)

    def _on_underline(self) -> None:
        """下划线切换"""
        if self.tab_widget.currentIndex() == 1:  # 富文本模式
            font = self._html_edit.currentFont()
            font.setUnderline(not font.underline())
            self._html_edit.setCurrentFont(font)

    def _on_bullet_list(self) -> None:
        """无序列表"""
        if self.tab_widget.currentIndex() == 1:  # 富文本模式
            cursor = self._html_edit.textCursor()
            # 插入HTML无序列表
            cursor.insertHtml("<ul><li>列表项</li></ul>")

    def _on_font_color(self) -> None:
        """字体颜色选择"""
        if self.tab_widget.currentIndex() == 1:  # 富文本模式
            color = QColorDialog.getColor()
            if color.isValid():
                self._html_edit.setTextColor(color)

    def _create_font_size_menu(self) -> QMenu:
        """创建字体大小菜单"""
        menu = QMenu()
        sizes = [8, 9, 10, 11, 12, 14, 16, 18, 20, 24, 28, 36, 48, 72]

        def create_size_action(size):
            def set_font_size():
                if self.tab_widget.currentIndex() == 1:  # 富文本模式
                    font = self._html_edit.currentFont()
                    font.setPointSize(size)
                    self._html_edit.setCurrentFont(font)

            return set_font_size

        for size in sizes:
            action = menu.addAction(f"{size} px")
            action.triggered.connect(create_size_action(size))

        return menu

    def _convert_plain_to_html(self, plain_text: str) -> str:
        """将纯文本转换为简单HTML"""
        # 保留换行符
        html_text = plain_text.replace("\n", "<br>")
        # 替换特殊字符
        html_text = (
            html_text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        )
        # 包裹在基本HTML结构中
        return f"<div style='font-family: sans-serif; font-size: 13px; line-height: 1.5; color: #141413;'>{html_text}</div>"

    def _get_html_content_for_sending(self) -> str:
        """获取HTML格式内容用于发送"""
        if self.tab_widget.currentIndex() == 0:  # 纯文本模式
            return self._body_edit.toPlainText()
        else:  # 富文本模式
            return self._html_edit.toHtml()

    def _setup_keyboard_shortcuts(self) -> None:
        """Setup keyboard shortcuts for compose window."""
        # Send shortcuts
        send_shortcut = QShortcut(QKeySequence("Ctrl+Return"), self)
        send_shortcut.activated.connect(self._on_send)

        alt_send_shortcut = QShortcut(QKeySequence("Ctrl+Enter"), self)
        alt_send_shortcut.activated.connect(self._on_send)

        # Save draft shortcut
        save_shortcut = QShortcut(QKeySequence("Ctrl+S"), self)
        save_shortcut.activated.connect(self._save_draft)

        # Cancel shortcut
        cancel_shortcut = QShortcut(QKeySequence("Esc"), self)
        cancel_shortcut.activated.connect(self.reject)

        # Text formatting shortcuts (only work in rich text mode)
        bold_shortcut = QShortcut(QKeySequence("Ctrl+B"), self)
        bold_shortcut.setContext(Qt.ShortcutContext.WidgetWithChildrenShortcut)
        bold_shortcut.activated.connect(self._on_bold)

        italic_shortcut = QShortcut(QKeySequence("Ctrl+I"), self)
        italic_shortcut.setContext(Qt.ShortcutContext.WidgetWithChildrenShortcut)
        italic_shortcut.activated.connect(self._on_italic)

        underline_shortcut = QShortcut(QKeySequence("Ctrl+U"), self)
        underline_shortcut.setContext(Qt.ShortcutContext.WidgetWithChildrenShortcut)
        underline_shortcut.activated.connect(self._on_underline)

        # Tab switching shortcuts
        next_tab_shortcut = QShortcut(QKeySequence("Ctrl+Tab"), self)
        next_tab_shortcut.activated.connect(self._next_tab)

        prev_tab_shortcut = QShortcut(QKeySequence("Ctrl+Shift+Tab"), self)
        prev_tab_shortcut.activated.connect(self._prev_tab)

    def _next_tab(self) -> None:
        """Switch to next tab."""
        current = self.tab_widget.currentIndex()
        if current < self.tab_widget.count() - 1:
            self.tab_widget.setCurrentIndex(current + 1)

    def _prev_tab(self) -> None:
        """Switch to previous tab."""
        current = self.tab_widget.currentIndex()
        if current > 0:
            self.tab_widget.setCurrentIndex(current - 1)

    def _guess_mime_type(self, file_path: str) -> str:
        """猜测文件的MIME类型"""
        import mimetypes

        mime_type, _ = mimetypes.guess_type(file_path)
        if mime_type:
            return mime_type

        # 根据文件扩展名猜测
        ext = os.path.splitext(file_path)[1].lower()
        mime_map = {
            ".jpg": "image/jpeg",
            ".jpeg": "image/jpeg",
            ".png": "image/png",
            ".gif": "image/gif",
            ".pdf": "application/pdf",
            ".doc": "application/msword",
            ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            ".xls": "application/vnd.ms-excel",
            ".xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            ".ppt": "application/vnd.ms-powerpoint",
            ".pptx": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
            ".zip": "application/zip",
            ".rar": "application/x-rar-compressed",
        }

        return mime_map.get(ext, "application/octet-stream")


class ComposeWindowEnhanced(ComposeWindow):
    """增强版撰写窗口，支持附件管理"""

    def __init__(self, account: Account, parent: QWidget | None = None) -> None:
        super().__init__(account, parent)
