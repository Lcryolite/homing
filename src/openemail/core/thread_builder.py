from __future__ import annotations

import logging
import re
from typing import Optional

from openemail.models.email import Email
from openemail.models.email_thread import EmailThread
from openemail.storage.database import db

logger = logging.getLogger(__name__)


class ThreadBuilder:
    """
    邮件线程构建器。

    优先使用 IMAP THREAD=REFERENCES (RFC 5256)，
    回退到本地 References/In-Reply-To 头部匹配。
    """

    @staticmethod
    def assign_to_thread(email: Email) -> Optional[EmailThread]:
        """
        将邮件分配到线程（本地 fallback 算法）。

        算法：
        1. 如果有 In-Reply-To，找到对应邮件的线程
        2. 如果有 References，找到最早引用邮件的线程
        3. 如果都没有，按 Subject 去掉 Re:/Fwd: 前缀匹配
        4. 无匹配则创建新线程
        """
        if not email.id:
            return None

        thread = ThreadBuilder._find_by_in_reply_to(email)
        if thread:
            thread.add_email(email.id)
            if email.date:
                thread.last_date = email.date
                thread.save()
            return thread

        thread = ThreadBuilder._find_by_references(email)
        if thread:
            thread.add_email(email.id)
            if email.date:
                thread.last_date = email.date
                thread.save()
            return thread

        thread = ThreadBuilder._find_by_subject(email)
        if thread:
            thread.add_email(email.id)
            if email.date:
                thread.last_date = email.date
                thread.save()
            return thread

        thread = EmailThread(
            account_id=email.account_id,
            subject=ThreadBuilder._normalize_subject(email.subject),
            message_count=1,
            last_date=email.date,
        )
        thread.save()
        thread.add_email(email.id)
        return thread

    @staticmethod
    def _find_by_in_reply_to(email: Email) -> Optional[EmailThread]:
        in_reply_to = getattr(email, "in_reply_to", "")
        if not in_reply_to:
            return None

        row = db.fetchone(
            "SELECT id FROM emails WHERE message_id = ? AND account_id = ?",
            (in_reply_to, email.account_id),
        )
        if row:
            return EmailThread.find_by_email_id(row["id"])
        return None

    @staticmethod
    def _find_by_references(email: Email) -> Optional[EmailThread]:
        references = getattr(email, "references", "")
        if not references:
            return None

        ref_ids = [r.strip() for r in re.split(r"\s+", references) if r.strip()]
        for ref_id in reversed(ref_ids):
            row = db.fetchone(
                "SELECT id FROM emails WHERE message_id = ? AND account_id = ?",
                (ref_id, email.account_id),
            )
            if row:
                thread = EmailThread.find_by_email_id(row["id"])
                if thread:
                    return thread
        return None

    @staticmethod
    def _find_by_subject(email: Email) -> Optional[EmailThread]:
        norm_subject = ThreadBuilder._normalize_subject(email.subject)
        if not norm_subject:
            return None

        rows = db.fetchall(
            "SELECT id FROM email_threads WHERE account_id = ? AND subject = ?",
            (email.account_id, norm_subject),
        )
        if rows:
            return EmailThread.get_by_id(rows[0]["id"])
        return None

    @staticmethod
    def _normalize_subject(subject: str) -> str:
        s = subject.strip()
        s = re.sub(r"^(Re|Fwd|Fw)\s*(\[\d+\])?\s*:\s*", "", s, flags=re.IGNORECASE)
        s = s.strip()
        return s

    @staticmethod
    def rebuild_all_threads(account_id: int) -> int:
        """
        重建账户的所有线程（全量重建）。

        Returns:
            构建的线程数
        """
        db.execute(
            "DELETE FROM email_thread_members WHERE thread_id IN (SELECT id FROM email_threads WHERE account_id = ?)",
            (account_id,),
        )
        db.execute("DELETE FROM email_threads WHERE account_id = ?", (account_id,))

        rows = db.fetchall(
            "SELECT id FROM emails WHERE account_id = ? ORDER BY date ASC",
            (account_id,),
        )

        count = 0
        for row in rows:
            email = Email.get_by_id(row["id"])
            if email:
                ThreadBuilder.assign_to_thread(email)
                count += 1

        logger.info(
            "Rebuilt threads for account %d: %d emails processed", account_id, count
        )
        return count

    @staticmethod
    async def apply_server_threads(account_id: int, thread_data: list[dict]) -> int:
        """
        应用 IMAP THREAD=REFERENCES 服务端结果。

        Args:
            account_id: 账户ID
            thread_data: 服务端返回的线程分组，每组是 UID 列表

        Returns:
            构建的线程数
        """
        db.execute(
            "DELETE FROM email_thread_members WHERE thread_id IN (SELECT id FROM email_threads WHERE account_id = ?)",
            (account_id,),
        )
        db.execute("DELETE FROM email_threads WHERE account_id = ?", (account_id,))

        count = 0
        for group in thread_data:
            uids = group if isinstance(group, list) else group.get("uids", [])
            if not uids:
                continue

            first_email = None
            for uid in uids:
                row = db.fetchone(
                    "SELECT id FROM emails WHERE uid = ? AND account_id = ?",
                    (str(uid), account_id),
                )
                if row:
                    email = Email.get_by_id(row["id"])
                    if email:
                        if first_email is None:
                            first_email = email
                            thread = EmailThread(
                                account_id=account_id,
                                subject=ThreadBuilder._normalize_subject(email.subject),
                                message_count=0,
                                last_date=email.date,
                            )
                            thread.save()
                        thread.add_email(email.id)
                        count += 1

        logger.info(
            "Applied server threads for account %d: %d emails", account_id, count
        )
        return count
