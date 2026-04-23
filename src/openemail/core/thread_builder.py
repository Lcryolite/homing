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
    回退到本地 References/In-Reply-To 头部匹配 + Subject 模糊匹配。
    """

    # Fuzzy-match threshold for subject similarity (0–1, higher = stricter)
    SUBJECT_SIMILARITY_THRESHOLD = 0.85

    @staticmethod
    def assign_to_thread(email: Email) -> Optional[EmailThread]:
        """
        将邮件分配到线程（本地 fallback 算法）。

        算法：
        1. 如果有 In-Reply-To，找到对应邮件的线程
        2. 如果有 References，找到最早引用邮件的线程
        3. 如果都没有，按 Subject 去掉 Re:/Fwd: 前缀模糊匹配
        4. 无匹配则创建新线程
        5. 如果新邮件连接了两个独立线程（In-Reply-To 和 References 指向不同线程），自动合并
        """
        if not email.id:
            return None

        # Try to find thread by In-Reply-To
        thread_irt = ThreadBuilder._find_by_in_reply_to(email)

        # Try to find thread by References
        thread_ref = ThreadBuilder._find_by_references(email)

        # If both found and different, merge them (References wins as older thread)
        if thread_irt and thread_ref and thread_irt.id != thread_ref.id:
            thread_ref = ThreadBuilder._merge_threads(thread_ref, thread_irt)

        # Use whichever thread was found
        target_thread = thread_ref or thread_irt

        if target_thread:
            target_thread.add_email(email.id)
            if email.date:
                target_thread.last_date = email.date
                target_thread.save()
            return target_thread

        # Fallback to subject matching
        thread_subj = ThreadBuilder._find_by_subject(email)
        if thread_subj:
            thread_subj.add_email(email.id)
            if email.date:
                thread_subj.last_date = email.date
                thread_subj.save()
            return thread_subj

        # No match — create new thread
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
        # Search from oldest reference first (most likely to be the root)
        for ref_id in ref_ids:
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

        # Exact match first
        rows = db.fetchall(
            "SELECT id, subject FROM email_threads WHERE account_id = ?",
            (email.account_id,),
        )
        best_match = None
        best_score = 0.0
        for row in rows:
            candidate_norm = ThreadBuilder._normalize_subject(row["subject"] or "")
            score = ThreadBuilder._subject_similarity(norm_subject, candidate_norm)
            if score > best_score and score >= ThreadBuilder.SUBJECT_SIMILARITY_THRESHOLD:
                best_score = score
                best_match = row["id"]

        if best_match:
            return EmailThread.get_by_id(best_match)
        return None

    @staticmethod
    def _normalize_subject(subject: str) -> str:
        """Strip reply/forward prefixes and normalize whitespace."""
        if not subject:
            return ""
        s = subject.strip()
        # Remove Re:/Fwd:/Fw: prefixes (with optional number counters like [2])
        s = re.sub(r"^(Re|Fwd|Fw)\s*(\[\d+\])?\s*[:：]\s*", "", s, flags=re.IGNORECASE)
        # Remove Chinese reply prefixes
        s = re.sub(r"^[回复|转发]\s*[:：]\s*", "", s)
        # Remove bracketed tags like [tag] at the start
        s = re.sub(r"^\[[^\]]+\]\s*", "", s)
        # Normalize whitespace
        s = re.sub(r"\s+", " ", s).strip()
        return s

    @staticmethod
    def _subject_similarity(a: str, b: str) -> float:
        """Simple similarity score for subjects (0–1)."""
        if not a or not b:
            return 0.0
        if a == b:
            return 1.0
        # Jaccard similarity on character bigrams
        def bigrams(s):
            return {s[i:i + 2] for i in range(len(s) - 1)}
        bg_a = bigrams(a)
        bg_b = bigrams(b)
        if not bg_a or not bg_b:
            return 0.0
        intersection = len(bg_a & bg_b)
        union = len(bg_a | bg_b)
        return intersection / union if union else 0.0

    @staticmethod
    def _merge_threads(
        primary: EmailThread, secondary: EmailThread
    ) -> EmailThread:
        """Merge secondary thread into primary. Returns the merged thread."""
        if primary.id == secondary.id:
            return primary

        logger.info(
            "Merging thread %d into %d (subject: %s -> %s)",
            secondary.id, primary.id, secondary.subject, primary.subject,
        )

        # Move all emails from secondary to primary
        secondary_email_ids = secondary.get_email_ids()
        for email_id in secondary_email_ids:
            primary.add_email(email_id)

        # Update last_date if secondary is newer
        if secondary.last_date and (
            not primary.last_date or secondary.last_date > primary.last_date
        ):
            primary.last_date = secondary.last_date
            primary.save()

        # Delete secondary
        secondary.delete()
        return primary

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

    @staticmethod
    def cleanup_orphan_threads(account_id: int) -> int:
        """Remove threads with zero members. Returns number deleted."""
        rows = db.fetchall(
            "SELECT t.id FROM email_threads t "
            "LEFT JOIN email_thread_members m ON t.id = m.thread_id "
            "WHERE t.account_id = ? AND m.email_id IS NULL",
            (account_id,),
        )
        deleted = 0
        for row in rows:
            thread = EmailThread.get_by_id(row["id"])
            if thread:
                thread.delete()
                deleted += 1
        if deleted:
            logger.info("Cleaned up %d orphan threads for account %d", deleted, account_id)
        return deleted
