from __future__ import annotations

import json
import logging
from email.message import Message

from openemail.core.imap_client import IMAPClient
from openemail.models.account import Account
from openemail.models.draft import Draft
from openemail.models.folder import Folder
from openemail.core.mail_builder import MailBuilder

logger = logging.getLogger(__name__)


class DraftSyncer:
    """草稿远程同步器，通过 IMAP APPEND 同步到 \\Drafts 文件夹"""

    @staticmethod
    async def sync_draft_to_remote(account: Account, draft: Draft) -> bool:
        """
        将本地草稿通过 IMAP APPEND 同步到远端 \\Drafts 文件夹。

        Returns:
            True 表示同步成功
        """
        if draft.is_syncing:
            return False

        try:
            draft.is_syncing = True
            draft.save()

            client = IMAPClient(account)
            if not await client.connect():
                raise ConnectionError(f"Cannot connect for draft sync: {account.email}")

            try:
                drafts_folder = await DraftSyncer._find_drafts_folder(account)
                if not drafts_folder:
                    logger.warning("未找到 Drafts 文件夹，跳过远程同步")
                    return False

                msg = DraftSyncer._build_mime_message(draft, account)
                msg_bytes = msg.as_bytes()

                new_uid = await client.append_message(
                    drafts_folder.name,
                    msg_bytes,
                    flags=["\\Draft"],
                )

                if new_uid is not None:
                    draft.mark_synced(new_uid)
                    logger.info("草稿已同步到远端: ID=%d, UID=%s", draft.id, new_uid or "unknown")
                    return True
                else:
                    raise RuntimeError("IMAP APPEND failed: no UID returned")

            finally:
                await client.disconnect()

        except Exception as e:
            logger.error("草稿远程同步失败: ID=%d, Error=%s", draft.id, e)
            draft.is_syncing = False
            draft.save()
            return False

    @staticmethod
    async def sync_all_unsynced(account: Account) -> int:
        """
        同步所有未同步的本地草稿到远端。

        Returns:
            成功同步的数量
        """
        unsynced = Draft.get_unsynced(account.id)
        if not unsynced:
            return 0

        success_count = 0
        for draft in unsynced:
            if await DraftSyncer.sync_draft_to_remote(account, draft):
                success_count += 1

        return success_count

    @staticmethod
    async def delete_remote_draft(account: Account, draft: Draft) -> bool:
        """删除远端草稿（通过 IMAP STORE + EXPUNGE）"""
        if not draft.uid or draft.is_local_only:
            return True

        try:
            client = IMAPClient(account)
            if not await client.connect():
                return False

            try:
                drafts_folder = await DraftSyncer._find_drafts_folder(account)
                if not drafts_folder:
                    return False

                await client.delete_email(draft.uid, drafts_folder.name)
                logger.info("远端草稿已删除: UID=%s", draft.uid)
                return True

            finally:
                await client.disconnect()

        except Exception as e:
            logger.error("删除远端草稿失败: UID=%s, Error=%s", draft.uid, e)
            return False

    @staticmethod
    async def _find_drafts_folder(account: Account) -> Folder | None:
        """查找账户的 Drafts 文件夹，支持多种命名。"""
        for special_use in ["drafts", "\\Drafts"]:
            folder = Folder.get_by_special_use(account.id, special_use)
            if folder:
                return folder

        for name in ["Drafts", "草稿", "DRAFTS", "[Gmail]/Drafts"]:
            folder = Folder.get_by_name(account.id, name)
            if folder:
                return folder

        return None

    @staticmethod
    def _build_mime_message(draft: Draft, account: Account) -> Message:
        builder = MailBuilder()
        builder.set_from(draft.from_addr, account.name)
        if draft.to_addrs:
            builder.set_to(draft.get_to_list())
        if draft.cc_addrs:
            builder.set_cc(draft.get_cc_list())
        builder.set_subject(draft.subject or "(No Subject)")
        if draft.body_text:
            builder.set_text_body(draft.body_text)
        if draft.body_html:
            builder.set_html_body(draft.body_html)
        if draft.in_reply_to:
            builder.set_in_reply_to(draft.in_reply_to)
        if draft.references:
            builder.set_references(draft.references)

        # 附加本地附件
        attachments = draft.get_attachments_list()
        for att in attachments:
            path = att.get("path") if isinstance(att, dict) else None
            if not path or not __import__("os").path.exists(path):
                continue
            try:
                with open(path, "rb") as f:
                    data = f.read()
                filename = att.get("filename") or __import__("os").path.basename(path)
                mime_type = att.get("mime_type") or "application/octet-stream"
                builder.add_attachment(filename, data, mime_type)
            except Exception as e:
                logger.warning("附件 %s 读取失败，跳过: %s", path, e)

        builder.add_header("X-Draft-Id", str(draft.id))
        return builder.build()
