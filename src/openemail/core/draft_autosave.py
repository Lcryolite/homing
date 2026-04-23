from __future__ import annotations

import logging
from typing import Optional

from PyQt6.QtCore import QObject, QTimer

from openemail.models.draft import Draft

logger = logging.getLogger(__name__)


class DraftAutoSave(QObject):
    """草稿自动保存管理器，定时保存撰写内容到本地数据库"""

    AUTOSAVE_INTERVAL_MS = 30000

    def __init__(self, account_id: int, parent: Optional[QObject] = None) -> None:
        super().__init__(parent)
        self._account_id = account_id
        self._draft_id: int = 0
        self._timer = QTimer(self)
        self._timer.setInterval(self.AUTOSAVE_INTERVAL_MS)
        self._timer.timeout.connect(self._do_autosave)
        self._dirty = False

        self._from_addr: str = ""
        self._to_addrs: str = ""
        self._cc_addrs: str = ""
        self._subject: str = ""
        self._body_text: str = ""
        self._body_html: str = ""
        self._attachments: str = "{}"
        self._in_reply_to: str = ""
        self._references: str = ""

    def start(self) -> None:
        self._timer.start()

    def stop(self) -> None:
        self._timer.stop()
        if self._dirty:
            self._do_autosave()

    def load_draft(self, draft_id: int) -> bool:
        draft = Draft.get_by_id(draft_id)
        if not draft:
            return False
        self._draft_id = draft.id
        self._from_addr = draft.from_addr
        self._to_addrs = draft.to_addrs
        self._cc_addrs = draft.cc_addrs
        self._subject = draft.subject
        self._body_text = draft.body_text
        self._body_html = draft.body_html
        self._attachments = draft.attachments
        self._in_reply_to = draft.in_reply_to
        self._references = draft.references
        self._dirty = False
        return True

    def update_content(
        self,
        from_addr: str = "",
        to_addrs: str = "",
        cc_addrs: str = "",
        subject: str = "",
        body_text: str = "",
        body_html: str = "",
        attachments: str = "{}",
        in_reply_to: str = "",
        references: str = "",
    ) -> None:
        if from_addr != self._from_addr:
            self._from_addr = from_addr
            self._dirty = True
        if to_addrs != self._to_addrs:
            self._to_addrs = to_addrs
            self._dirty = True
        if cc_addrs != self._cc_addrs:
            self._cc_addrs = cc_addrs
            self._dirty = True
        if subject != self._subject:
            self._subject = subject
            self._dirty = True
        if body_text != self._body_text:
            self._body_text = body_text
            self._dirty = True
        if body_html != self._body_html:
            self._body_html = body_html
            self._dirty = True
        if attachments != self._attachments:
            self._attachments = attachments
            self._dirty = True
        if in_reply_to != self._in_reply_to:
            self._in_reply_to = in_reply_to
            self._dirty = True
        if references != self._references:
            self._references = references
            self._dirty = True

    def _do_autosave(self) -> None:
        if not self._dirty:
            return
        if (
            not self._from_addr
            and not self._to_addrs
            and not self._subject
            and not self._body_text
        ):
            return

        try:
            draft = Draft(
                id=self._draft_id,
                account_id=self._account_id,
                from_addr=self._from_addr,
                to_addrs=self._to_addrs,
                cc_addrs=self._cc_addrs,
                subject=self._subject,
                body_text=self._body_text,
                body_html=self._body_html,
                attachments=self._attachments,
                in_reply_to=self._in_reply_to,
                references=self._references,
            )
            draft.save()
            self._draft_id = draft.id
            self._dirty = False
            logger.debug("草稿自动保存: ID=%d", draft.id)
        except Exception as e:
            logger.error("草稿自动保存失败: %s", e)

    def save_now(self) -> int:
        self._do_autosave()
        return self._draft_id

    def delete_draft(self) -> None:
        if self._draft_id:
            Draft.get_by_id(self._draft_id)
            draft = Draft.get_by_id(self._draft_id)
            if draft:
                draft.delete()
            self._draft_id = 0
        self._dirty = False
