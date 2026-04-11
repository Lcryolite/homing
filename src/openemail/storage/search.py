from __future__ import annotations

import re

from openemail.models.email import Email
from openemail.storage.database import db


class SearchEngine:
    """FTS5 全文搜索引擎"""

    @staticmethod
    def search(
        query: str,
        account_id: int | None = None,
        folder_id: int | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[Email]:
        """
        FTS5 全文搜索

        支持高级语法:
        - from:xxx@example.com  发件人
        - to:xxx@example.com    收件人
        - subject:关键词         主题
        - has:attachment        有附件
        - is:read / is:unread   已读/未读
        - is:flagged            已标记
        - after:2024-01-01      日期之后
        - before:2024-12-31     日期之前
        """
        # 解析高级搜索语法
        fts_query, filters = SearchEngine._parse_query(query)

        # 构建 SQL
        where_clauses = ["emails_fts MATCH ?"]
        params = [fts_query]

        if account_id:
            where_clauses.append("emails.account_id = ?")
            params.append(account_id)

        if folder_id:
            where_clauses.append("emails.folder_id = ?")
            params.append(folder_id)

        # 应用过滤器
        for key, value in filters.items():
            if key == "is_read":
                where_clauses.append("emails.is_read = ?")
                params.append(1 if value == "read" else 0)
            elif key == "is_flagged":
                where_clauses.append("emails.is_flagged = ?")
                params.append(1)
            elif key == "has_attachment":
                where_clauses.append("emails.has_attachment = ?")
                params.append(1)
            elif key == "after":
                where_clauses.append("emails.date >= ?")
                params.append(value)
            elif key == "before":
                where_clauses.append("emails.date <= ?")
                params.append(value)

        where_sql = " AND ".join(where_clauses)

        sql = f"""
            SELECT emails.* FROM emails
            JOIN emails_fts ON emails.id = emails_fts.rowid
            WHERE {where_sql}
            ORDER BY rank
            LIMIT ? OFFSET ?
        """
        params.extend([limit, offset])

        rows = db.fetchall(sql, tuple(params))
        return [Email._from_row(r) for r in rows]

    @staticmethod
    def count(
        query: str,
        account_id: int | None = None,
        folder_id: int | None = None,
    ) -> int:
        """搜索结果的总数"""
        fts_query, filters = SearchEngine._parse_query(query)

        where_clauses = ["emails_fts MATCH ?"]
        params = [fts_query]

        if account_id:
            where_clauses.append("emails.account_id = ?")
            params.append(account_id)

        if folder_id:
            where_clauses.append("emails.folder_id = ?")
            params.append(folder_id)

        for key, value in filters.items():
            if key == "is_read":
                where_clauses.append("emails.is_read = ?")
                params.append(1 if value == "read" else 0)
            elif key == "is_flagged":
                where_clauses.append("emails.is_flagged = ?")
                params.append(1)
            elif key == "has_attachment":
                where_clauses.append("emails.has_attachment = ?")
                params.append(1)
            elif key == "after":
                where_clauses.append("emails.date >= ?")
                params.append(value)
            elif key == "before":
                where_clauses.append("emails.date <= ?")
                params.append(value)

        where_sql = " AND ".join(where_clauses)

        sql = f"""
            SELECT COUNT(*) as c FROM emails
            JOIN emails_fts ON emails.id = emails_fts.rowid
            WHERE {where_sql}
        """

        row = db.fetchone(sql, tuple(params))
        return row["c"] if row else 0

    @staticmethod
    def _parse_query(query: str) -> tuple[str, dict]:
        """
        解析搜索查询，提取 FTS 查询和过滤器

        返回：(fts_query, filters_dict)
        """
        filters = {}
        fts_parts = []

        # 正则表达式匹配高级语法
        patterns = {
            "from": r"from:([^\s]+)",
            "to": r"to:([^\s]+)",
            "subject": r"subject:([^\s]+)",
            "has": r"has:([^\s]+)",
            "is": r"is:([^\s]+)",
            "after": r"after:(\d{4}-\d{2}-\d{2})",
            "before": r"before:(\d{4}-\d{2}-\d{2})",
        }

        remaining_query = query

        # 提取 from:
        matches = re.findall(patterns["from"], remaining_query, re.IGNORECASE)
        for match in matches:
            fts_parts.append(f'sender_addr MATCH "{match}"')
            remaining_query = remaining_query.replace(f"from:{match}", "")

        # 提取 to:
        matches = re.findall(patterns["to"], remaining_query, re.IGNORECASE)
        for match in matches:
            fts_parts.append(f'to_addrs MATCH "{match}"')
            remaining_query = remaining_query.replace(f"to:{match}", "")

        # 提取 subject:
        matches = re.findall(patterns["subject"], remaining_query, re.IGNORECASE)
        for match in matches:
            fts_parts.append(f'subject MATCH "{match}"')
            remaining_query = remaining_query.replace(f"subject:{match}", "")

        # 提取 has:
        matches = re.findall(patterns["has"], remaining_query, re.IGNORECASE)
        for match in matches:
            if match.lower() == "attachment":
                filters["has_attachment"] = True

        # 提取 is:
        matches = re.findall(patterns["is"], remaining_query, re.IGNORECASE)
        for match in matches:
            if match.lower() in ("read", "unread"):
                filters["is_read"] = match.lower()
            elif match.lower() == "flagged":
                filters["is_flagged"] = True

        # 提取 after:
        matches = re.findall(patterns["after"], remaining_query, re.IGNORECASE)
        for match in matches:
            filters["after"] = match
            remaining_query = remaining_query.replace(f"after:{match}", "")

        # 提取 before:
        matches = re.findall(patterns["before"], remaining_query, re.IGNORECASE)
        for match in matches:
            filters["before"] = match
            remaining_query = remaining_query.replace(f"before:{match}", "")

        # 剩余的作为普通全文搜索
        remaining_query = remaining_query.strip()
        if remaining_query:
            fts_parts.append(remaining_query)

        fts_query = " AND ".join(fts_parts) if fts_parts else "*"
        return fts_query, filters

    @staticmethod
    def highlight(text: str, query: str, max_len: int = 100) -> str:
        """搜索高亮（简单实现）"""
        if not text or not query:
            return text

        # 简单的高亮实现
        words = query.lower().split()
        result = text
        for word in words:
            if len(word) > 1:
                result = re.sub(
                    f"({re.escape(word)})",
                    r"<mark>\1</mark>",
                    result,
                    flags=re.IGNORECASE,
                )

        # 截断
        if len(result) > max_len:
            result = result[:max_len] + "..."

        return result
