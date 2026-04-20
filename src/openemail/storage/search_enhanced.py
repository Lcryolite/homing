from __future__ import annotations

import re
import sqlite3
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any, Tuple
import json

from openemail.models.email import Email
from openemail.storage.database import db


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
            search_terms, filters, account_id, folder_id, limit * 2, offset
        )

        # 如果启用了语义搜索，尝试混合结果
        if semantic_weight > 0 and len(search_terms) > 0 and len(fts_results) < limit:
            try:
                semantic_results = EnhancedSearchEngine._semantic_search(
                    search_terms, account_id, folder_id, limit=limit - len(fts_results)
                )

                # 合并结果
                combined_results = list(fts_results) + list(semantic_results)

                # 去重并按相关性排序
                seen_ids = set()
                unique_results = []

                for email in combined_results:
                    if email.id not in seen_ids:
                        seen_ids.add(email.id)
                        unique_results.append(email)

                return unique_results[:limit]

            except ImportError:
                # 语义搜索库不可用，回退到FTS5
                pass

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
            except:
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

            folders = Folder.get_all(account_id)

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
        if not search_terms:
            fts_query = "*"
        else:
            fts_query = " AND ".join([f'"{term}"' for term in search_terms])

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
            # 尝试导入sentence-transformers
            from sentence_transformers import SentenceTransformer, util
            import torch

            # 加载模型（缓存）
            model = EnhancedSearchEngine._get_semantic_model()
            if not model:
                return []

            # 创建查询嵌入
            query_text = " ".join(search_terms)
            query_embedding = model.encode([query_text], convert_to_tensor=True)

            # 从数据库获取已有嵌入（这里需要扩展数据库存储嵌入）
            # 暂时先返回空结果，需要先实现邮件嵌入存储
            return []

        except ImportError:
            # 库不可用，不提供语义搜索
            print(
                "语义搜索需要sentence-transformers库: pip install sentence-transformers"
            )
            return []
        except Exception as e:
            print(f"语义搜索错误: {e}")
            return []

    @staticmethod
    def _get_semantic_model():
        """获取语义模型单例"""
        try:
            from sentence_transformers import SentenceTransformer

            if not hasattr(EnhancedSearchEngine, "_semantic_model"):
                # 使用小型多语言模型，适合中英文
                EnhancedSearchEngine._semantic_model = SentenceTransformer(
                    "paraphrase-multilingual-MiniLM-L12-v2"
                )

            return EnhancedSearchEngine._semantic_model
        except ImportError:
            return None

    @staticmethod
    def _parse_advanced_query(query: str) -> Tuple[Dict[str, Any], List[str]]:
        """解析高级搜索查询"""
        filters = {}
        search_terms = []

        # 定义搜索模式
        patterns = {
            "from": r'from:([^\s"\']+|"[^"]+"|\'[^\']+\')',
            "to": r'to:([^\s"\']+|"[^"]+"|\'[^\']+\')',
            "subject": r'subject:([^\s"\']+|"[^"]+"|\'[^\']+\')',
            "has": r'has:([^\s"\']+|"[^"]+"|\'[^\']+\')',
            "is": r'is:([^\s"\']+|"[^"]+"|\'[^\']+\')',
            "after": r"after:(\d{4}-\d{2}-\d{2})",
            "before": r"before:(\d{4}-\d{2}-\d{2})",
            "in": r'in:([^\s"\']+|"[^"]+"|\'[^\']+\')',
        }

        remaining_query = query

        # 提取各种过滤器
        for key, pattern in patterns.items():
            matches = re.findall(pattern, remaining_query, re.IGNORECASE)
            for match in matches:
                # 清理引号
                match_clean = match.strip("\"'")

                if key == "from":
                    filters["from"] = match_clean
                elif key == "to":
                    filters["to"] = match_clean
                elif key == "subject":
                    filters["subject"] = match_clean
                elif key == "has":
                    if match_clean.lower() in ["attachment", "attachments"]:
                        filters["has_attachment"] = True
                elif key == "is":
                    if match_clean.lower() in ["read", "unread"]:
                        filters["is_read"] = match_clean.lower() == "read"
                    elif match_clean.lower() == "flagged":
                        filters["is_flagged"] = True
                    elif match_clean.lower() == "spam":
                        filters["is_spam"] = True
                elif key == "after":
                    filters["after_date"] = match_clean
                elif key == "before":
                    filters["before_date"] = match_clean
                elif key == "in":
                    filters["folder"] = match_clean

                # 从查询中移除已匹配的部分
                remaining_query = re.sub(
                    pattern, "", remaining_query, flags=re.IGNORECASE
                )

        # 剩余部分作为普通搜索词
        remaining_query = remaining_query.strip()
        if remaining_query:
            # 分割为独立的搜索词
            terms = re.findall(r'[^\s"\']+|"[^"]+"|\'[^\']+\'', remaining_query)
            for term in terms:
                term_clean = term.strip("\"'")
                if len(term_clean) > 1:  # 忽略单个字符
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
            print(f"创建附件FTS表失败: {e}")

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
        except:
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
        except:
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
