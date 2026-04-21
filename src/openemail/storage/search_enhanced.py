from __future__ import annotations

import re
import sqlite3
import logging
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any, Tuple

from openemail.models.email import Email
from openemail.storage.database import db

logger = logging.getLogger(__name__)


class EnhancedSearchEngine:
    """增强版全文搜索引擎，支持智能搜索和语义分析"""

    @staticmethod
    def search(
        query: str,
        account_id: Optional[int] = None,
        folder_id: Optional[int] = None,
        limit: int = 50,
        offset: int = 0,
        include_attachments: bool = False,
        semantic_weight: float = 0.3,
    ) -> List[Email]:
        """
        增强版全文搜索，支持混合搜索（FTS5 + 语义分析）

        参数:
            query: 搜索查询字符串
            account_id: 账户ID筛选
            folder_id: 文件夹ID筛选
            limit: 返回结果数量限制
            offset: 偏移量
            include_attachments: 是否搜索附件内容
            semantic_weight: 语义搜索权重 (0.0-1.0)
        """
        # 解析查询，提取过滤器和搜索词
        filters, search_terms = EnhancedSearchEngine._parse_advanced_query(query)

        # 首先尝试传统的FTS5搜索
        fts_results = EnhancedSearchEngine._fts_search(
            search_terms,
            filters,
            account_id,
            folder_id,
            limit * 3,
            offset,  # 获取更多结果用于重排
        )

        # 如果启用了语义搜索且搜索词足够长，尝试混合搜索
        if semantic_weight > 0 and len(search_terms) > 0 and len(search_terms[0]) > 2:
            try:
                # 尝试进行混合搜索（重排FTS结果）
                from openemail.search.semantic_search import semantic_search_manager

                # 检查语义搜索是否可用
                if semantic_search_manager.is_available():
                    query_text = " ".join(search_terms)

                    # 进行混合搜索重排
                    mixed_results = semantic_search_manager.hybrid_search(
                        fts_results=fts_results,
                        query=query_text,
                        semantic_weight=semantic_weight,
                        rerank_limit=len(fts_results),
                    )

                    # 返回重排后的结果
                    return mixed_results[:limit]
                else:
                    # 语义搜索不可用，使用FTS结果
                    logger.debug(
                        "Semantic search not available, using FTS results only"
                    )

            except ImportError as e:
                # 语义搜索库不可用，回退到FTS5
                logger.debug(f"Semantic search import error: {e}")
                pass
            except Exception as e:
                logger.error(f"Error in hybrid search: {e}")
                # 出错时回退到FTS结果

        return fts_results[:limit]

    @staticmethod
    def search_attachments(
        query: str,
        account_id: Optional[int] = None,
        folder_id: Optional[int] = None,
        limit: int = 50,
    ) -> List[Email]:
        """搜索附件内容"""
        # 确保附件FTS表存在
        EnhancedSearchEngine._ensure_attachments_fts()

        # 构建SQL查询
        where_clauses = ["attachments_fts MATCH ?"]
        params = [query]

        if account_id:
            where_clauses.append("emails.account_id = ?")
            params.append(account_id)

        if folder_id:
            where_clauses.append("emails.folder_id = ?")
            params.append(folder_id)

        where_sql = " AND ".join(where_clauses)

        sql = f"""
            SELECT DISTINCT emails.* FROM emails
            JOIN attachments ON attachments.email_id = emails.id
            JOIN attachments_fts ON attachments_fts.rowid = attachments.id
            WHERE {where_sql}
            ORDER BY attachments_fts.rank
            LIMIT ?
        """
        params.append(limit)

        rows = db.fetchall(sql, params)
        return [Email._from_row(r) for r in rows]

    @staticmethod
    def search_conversations(
        query: str,
        account_id: Optional[int] = None,
        limit: int = 20,
    ) -> List[Dict[str, Any]]:
        """搜索对话（按主题分组）"""
        filters, search_terms = EnhancedSearchEngine._parse_advanced_query(query)

        # 构建基础查询
        where_clauses = []
        params = []

        if search_terms:
            fts_query = " ".join(search_terms)
            where_clauses.append("emails_fts MATCH ?")
            params.append(fts_query)

        if account_id:
            where_clauses.append("emails.account_id = ?")
            params.append(account_id)

        # 应用过滤器
        for key, value in filters.items():
            if key == "is_read":
                where_clauses.append("emails.is_read = ?")
                params.append(1 if value else 0)
            elif key == "has_attachment":
                where_clauses.append("emails.has_attachment = ?")
                params.append(1)
            elif key == "after_date":
                where_clauses.append("emails.date >= ?")
                params.append(value)
            elif key == "before_date":
                where_clauses.append("emails.date <= ?")
                params.append(value)

        where_sql = " AND ".join(where_clauses) if where_clauses else "1=1"

        # 按对话（subject和发件人/收件人）分组
        sql = f"""
            SELECT 
                CASE 
                    WHEN emails.subject LIKE 'Re:%' THEN SUBSTR(emails.subject, 4)
                    WHEN emails.subject LIKE 'Fwd:%' THEN SUBSTR(emails.subject, 5)
                    ELSE emails.subject
                END as conversation_subject,
                emails.sender_addr,
                GROUP_CONCAT(DISTINCT emails.to_addrs) as participants,
                COUNT(*) as message_count,
                MAX(emails.date) as last_date,
                GROUP_CONCAT(emails.id) as email_ids
            FROM emails
            JOIN emails_fts ON emails.id = emails_fts.rowid
            WHERE {where_sql}
            GROUP BY conversation_subject, emails.sender_addr
            HAVING message_count > 1
            ORDER BY last_date DESC
            LIMIT ?
        """
        params.append(limit)

        rows = db.fetchall(sql, params)
        conversations = []

        for row in rows:
            conversations.append(
                {
                    "subject": row["conversation_subject"],
                    "sender": row["sender_addr"],
                    "participants": row["participants"].split(","),
                    "message_count": row["message_count"],
                    "last_date": row["last_date"],
                    "email_ids": [
                        int(id_str) for id_str in row["email_ids"].split(",")
                    ],
                }
            )

        return conversations

    @staticmethod
    def search_suggestions(
        query: str,
        account_id: Optional[int] = None,
        limit: int = 10,
    ) -> List[Dict[str, Any]]:
        """搜索建议（自动补全）"""
        suggestions = []

        # 1. 搜索联系人建议
        if query and len(query) > 1:
            try:
                from openemail.models.contact import Contact

                contacts = Contact.search(query, account_id, limit=5)

                for contact in contacts:
                    suggestions.append(
                        {
                            "type": "contact",
                            "text": contact.display_name,
                            "value": f"from:{contact.email}",
                            "description": contact.email,
                            "icon": "👤",
                        }
                    )
            except Exception:
                pass

        # 2. 搜索主题建议
        if query and len(query) > 2:
            sql = """
                SELECT DISTINCT subject FROM emails
                WHERE subject LIKE ? AND subject IS NOT NULL
                LIMIT ?
            """
            rows = db.fetchall(sql, (f"%{query}%", limit))

            for row in rows:
                subject = row["subject"]
                suggestions.append(
                    {
                        "type": "subject",
                        "text": subject[:50],
                        "value": f"subject:{subject}",
                        "description": "主题",
                        "icon": "📋",
                    }
                )

        # 3. 搜索文件夹建议
        if "in:" in query.lower():
            from openemail.models.folder import Folder

            folders = Folder.get_by_account(account_id)

            folder_term = query.lower().split("in:")[-1].strip()
            for folder in folders:
                if folder_term in folder.name.lower():
                    suggestions.append(
                        {
                            "type": "folder",
                            "text": folder.name,
                            "value": f"in:{folder.name}",
                            "description": "文件夹",
                            "icon": "📁",
                        }
                    )

        # 4. 搜索日期建议
        date_patterns = {
            "today": ("今天", datetime.now().strftime("%Y-%m-%d")),
            "yesterday": (
                "昨天",
                (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d"),
            ),
            "this week": ("本周", "this week"),
            "last week": ("上周", "last week"),
            "this month": ("本月", "this month"),
        }

        for pattern, (display, value) in date_patterns.items():
            if pattern in query.lower():
                suggestions.append(
                    {
                        "type": "date",
                        "text": display,
                        "value": f"after:{value}"
                        if "after" in query
                        else f"before:{value}",
                        "description": "日期范围",
                        "icon": "📅",
                    }
                )

        return suggestions[:limit]

    @staticmethod
    def _fts_search(
        search_terms: List[str],
        filters: Dict[str, Any],
        account_id: Optional[int],
        folder_id: Optional[int],
        limit: int,
        offset: int,
    ) -> List[Email]:
        """传统FTS5搜索"""
        # When no search terms and no filters, return empty to avoid invalid MATCH '*'
        if not search_terms and not filters and not folder_id:
            return []

        use_fts = bool(search_terms)
        if use_fts:
            fts_query = " AND ".join([f'"{term}"' for term in search_terms])

        if use_fts:
            where_clauses = ["emails_fts MATCH ?"]
            params: list = [fts_query]
        else:
            # No text search - query emails table directly
            where_clauses = ["1=1"]
            params = []

        if account_id:
            where_clauses.append("emails.account_id = ?")
            params.append(account_id)

        if folder_id:
            where_clauses.append("emails.folder_id = ?")
            params.append(folder_id)

        # 应用过滤器
        for key, value in filters.items():
            if key == "from":
                where_clauses.append("emails.sender_addr LIKE ?")
                params.append(f"%{value}%")
            elif key == "to":
                where_clauses.append("emails.to_addrs LIKE ?")
                params.append(f"%{value}%")
            elif key == "subject":
                where_clauses.append("emails.subject LIKE ?")
                params.append(f"%{value}%")
            elif key == "is_read":
                where_clauses.append("emails.is_read = ?")
                params.append(1 if value else 0)
            elif key == "is_flagged":
                where_clauses.append("emails.is_flagged = ?")
                params.append(1)
            elif key == "has_attachment":
                where_clauses.append("emails.has_attachment = ?")
                params.append(1)
            elif key == "after_date":
                where_clauses.append("emails.date >= ?")
                params.append(value)
            elif key == "before_date":
                where_clauses.append("emails.date <= ?")
                params.append(value)

        where_sql = " AND ".join(where_clauses)

        if use_fts:
            sql = f"""
                SELECT emails.*,
                       emails_fts.rank,
                       snippet(emails_fts, 0, '<b>', '</b>', '...', 30) AS snippet_subject,
                       snippet(emails_fts, 3, '<b>', '</b>', '...', 60) AS snippet_body,
                       highlight(emails_fts, 0, '<b>', '</b>') AS highlight_subject,
                       highlight(emails_fts, 3, '<b>', '</b>') AS highlight_body
                FROM emails
                JOIN emails_fts ON emails.id = emails_fts.rowid
                WHERE {where_sql}
                ORDER BY emails_fts.rank, emails.date DESC
                LIMIT ? OFFSET ?
            """
        else:
            # No FTS - simple query on emails table
            sql = f"""
                SELECT emails.*
                FROM emails
                WHERE {where_sql}
                ORDER BY emails.date DESC
                LIMIT ? OFFSET ?
            """
        params.extend([limit, offset])

        rows = db.fetchall(sql, params)
        results = []
        for r in rows:
            email = Email._from_row(r)
            email._search_snippet = r.get("snippet_body", "")
            email._search_highlight = r.get("highlight_body", "")
            results.append(email)
        return results

    @staticmethod
    def _semantic_search(
        search_terms: List[str],
        account_id: Optional[int],
        folder_id: Optional[int],
        limit: int,
    ) -> List[Email]:
        """语义相似度搜索（需要外部库）"""
        try:
            # 导入语义搜索服务
            from openemail.search.semantic_search import semantic_search_service

            # 创建查询文本
            query_text = " ".join(search_terms)
            if not query_text or len(query_text.strip()) < 2:
                return []

            # 执行语义搜索
            semantic_results = semantic_search_service.search_semantic_only(
                query=query_text,
                account_id=account_id,
                folder_id=folder_id,
                limit=limit * 2,  # 搜索多一些，用于后续过滤
            )

            # 提取邮件列表
            emails = [email for email, _ in semantic_results]
            return emails[:limit]

        except ImportError as e:
            # 库不可用，不提供语义搜索
            logger.warning(f"Semantic search requires additional libraries: {e}")
            return []
        except Exception as e:
            logger.error(f"Semantic search error: {e}")
            return []

    @staticmethod
    def _parse_advanced_query(query: str) -> Tuple[Dict[str, Any], List[str]]:
        """解析高级搜索查询"""
        filters: Dict[str, Any] = {}
        remaining = query

        # All filter keyword prefixes for lookahead
        _KW = r"(?:from|to|subject|has|is|after|before|in):"
        _quoted = r'"[^"]*"|\'[^\']*\''
        _word = r"\S+"

        # 1) Text filters: capture until next keyword or end (respecting quotes)
        for key, fkey in [("from", "from"), ("to", "to"), ("subject", "subject")]:
            pattern = rf"{key}:({_quoted}|.+?)(?=\s*(?:{_KW})|$)"
            for m in re.finditer(pattern, remaining, re.IGNORECASE):
                val = m.group(1).strip().strip("\"'")
                if val:
                    filters[fkey] = val

        # 2) has:attachment
        for m in re.finditer(rf"has:({_word})", remaining, re.IGNORECASE):
            if m.group(1).lower() in ("attachment", "attachments"):
                filters["has_attachment"] = True

        # 3) is:read/unread/flagged/spam
        for m in re.finditer(rf"is:({_word})", remaining, re.IGNORECASE):
            val = m.group(1).lower()
            if val in ("read", "unread"):
                filters["is_read"] = val == "read"
            elif val == "flagged":
                filters["is_flagged"] = True
            elif val == "spam":
                filters["is_spam"] = True

        # 4) after:/before: date filters
        for m in re.finditer(r"after:(\d{4}-\d{2}-\d{2})", remaining, re.IGNORECASE):
            filters["after_date"] = m.group(1)
        for m in re.finditer(r"before:(\d{4}-\d{2}-\d{2})", remaining, re.IGNORECASE):
            filters["before_date"] = m.group(1)

        # 5) in:folder
        for m in re.finditer(rf"in:({_word})", remaining, re.IGNORECASE):
            filters["folder"] = m.group(1)

        # Strip all filter expressions from remaining query
        remaining = re.sub(
            rf"(?:from|to|subject):(?:{_quoted}|.+?)(?=\s*(?:{_KW})|$)",
            "",
            remaining,
            flags=re.IGNORECASE,
        )
        remaining = re.sub(r"(?:has|is|in):\S+", "", remaining, flags=re.IGNORECASE)
        remaining = re.sub(
            r"(?:after|before):\d{4}-\d{2}-\d{2}", "", remaining, flags=re.IGNORECASE
        )
        remaining = remaining.strip()

        # Remaining = search terms
        search_terms: List[str] = []
        if remaining:
            terms = re.findall(r'[^\s"\']+|"[^"]+"|\'[^\']+\'', remaining)
            for term in terms:
                term_clean = term.strip("\"'")
                if len(term_clean) > 1:
                    search_terms.append(term_clean)

        return filters, search_terms

    @staticmethod
    def _ensure_attachments_fts():
        """确保附件FTS表存在"""
        try:
            # 检查表是否存在
            row = db.fetchone(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='attachments_fts'"
            )
            if not row:
                # 创建附件FTS表
                db.execute("""
                    CREATE VIRTUAL TABLE IF NOT EXISTS attachments_fts USING fts5(
                        filename, 
                        extracted_text,
                        content='attachments',
                        content_rowid='id'
                    )
                """)

                # 创建触发器保持同步
                db.execute("""
                    CREATE TRIGGER IF NOT EXISTS attachments_fts_ai AFTER INSERT ON attachments
                    BEGIN
                        INSERT INTO attachments_fts(rowid, filename, extracted_text)
                        VALUES (new.id, new.filename, COALESCE(new.extracted_text, ''));
                    END
                """)

                db.execute("""
                    CREATE TRIGGER IF NOT EXISTS attachments_fts_ad AFTER DELETE ON attachments
                    BEGIN
                        DELETE FROM attachments_fts WHERE rowid = old.id;
                    END
                """)

                db.execute("""
                    CREATE TRIGGER IF NOT EXISTS attachments_fts_au AFTER UPDATE ON attachments
                    BEGIN
                        DELETE FROM attachments_fts WHERE rowid = old.id;
                        INSERT INTO attachments_fts(rowid, filename, extracted_text)
                        VALUES (new.id, new.filename, COALESCE(new.extracted_text, ''));
                    END
                """)
        except sqlite3.Error as e:
            logger.error("创建附件FTS表失败: %s", e)

    @staticmethod
    def generate_search_snippets(
        email: Email,
        query: str,
        max_snippets: int = 3,
        snippet_length: int = 100,
    ) -> List[str]:
        """生成搜索摘要片段"""
        snippets = []

        # 检查主题
        if email.subject and query:
            subject_lower = email.subject.lower()
            query_lower = query.lower()

            if query_lower in subject_lower:
                start = max(0, subject_lower.find(query_lower) - 20)
                end = min(len(email.subject), start + snippet_length)
                snippet = email.subject[start:end]
                if start > 0:
                    snippet = "..." + snippet
                if end < len(email.subject):
                    snippet = snippet + "..."
                snippets.append(snippet)

        # 检查预览文本
        if email.preview_text and query:
            preview_lower = email.preview_text.lower()
            query_lower = query.lower()

            # 查找所有匹配位置
            start_pos = 0
            while len(snippets) < max_snippets:
                pos = preview_lower.find(query_lower, start_pos)
                if pos == -1:
                    break

                start = max(0, pos - 30)
                end = min(len(email.preview_text), start + snippet_length)
                snippet = email.preview_text[start:end]

                if start > 0:
                    snippet = "..." + snippet
                if end < len(email.preview_text):
                    snippet = snippet + "..."

                snippets.append(snippet)
                start_pos = pos + len(query_lower)

        return snippets

    @staticmethod
    def save_search_history(
        query: str,
        account_id: Optional[int] = None,
        result_count: int = 0,
    ) -> None:
        """保存搜索历史"""
        try:
            db.insert(
                "search_history",
                {
                    "query": query,
                    "account_id": account_id,
                    "result_count": result_count,
                    "searched_at": datetime.now().isoformat(),
                },
            )
        except Exception:
            pass  # 如果表不存在，忽略

    @staticmethod
    def get_search_history(
        account_id: Optional[int] = None,
        limit: int = 10,
    ) -> List[Dict[str, Any]]:
        """获取搜索历史"""
        try:
            where_clause = "1=1"
            params = []

            if account_id:
                where_clause = "account_id = ? OR account_id IS NULL"
                params.append(account_id)

            sql = f"""
                SELECT query, result_count, searched_at 
                FROM search_history 
                WHERE {where_clause}
                ORDER BY searched_at DESC
                LIMIT ?
            """
            params.append(limit)

            rows = db.fetchall(sql, params)
            return [
                {
                    "query": row["query"],
                    "count": row["result_count"],
                    "time": row["searched_at"],
                }
                for row in rows
            ]
        except Exception:
            return []  # 如果表不存在，返回空列表


# 初始化时创建必要的表
def init_enhanced_search():
    """初始化增强搜索系统"""
    # 创建搜索历史表
    db.execute("""
        CREATE TABLE IF NOT EXISTS search_history (
            id           INTEGER PRIMARY KEY,
            query        TEXT NOT NULL,
            account_id   INTEGER,
            result_count INTEGER DEFAULT 0,
            searched_at  TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # 创建索引
    db.execute(
        "CREATE INDEX IF NOT EXISTS idx_search_history_account ON search_history(account_id)"
    )
    db.execute(
        "CREATE INDEX IF NOT EXISTS idx_search_history_time ON search_history(searched_at)"
    )

    # 确保附件FTS表
    EnhancedSearchEngine._ensure_attachments_fts()


# 自动初始化
init_enhanced_search()
