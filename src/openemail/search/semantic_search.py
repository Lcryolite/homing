from __future__ import annotations

import logging
from typing import List, Optional, Tuple

from openemail.models.email import Email
from openemail.search.embedding_service import (
    embedding_service,
    embedding_worker,
    embedding_storage,
)
from openemail.search.faiss_index import faiss_index_manager, semantic_search_service

logger = logging.getLogger(__name__)


class SemanticSearchManager:
    """语义搜索管理器，整合所有语义搜索相关服务"""

    def __init__(self):
        self._embedding_service = embedding_service
        self._embedding_storage = embedding_storage
        self._embedding_worker = embedding_worker
        self._faiss_index_manager = faiss_index_manager
        self._semantic_search_service = semantic_search_service

    def initialize(self) -> bool:
        """初始化语义搜索系统"""
        try:
            # 检查模型是否可用
            if not self._embedding_service.is_model_available():
                logger.warning("Semantic model not available, semantic search disabled")
                logger.info("Install: pip install sentence-transformers torch")
                return False

            # 启动嵌入工作器
            self._embedding_worker.start()

            logger.info("Semantic search system initialized")
            return True

        except Exception as e:
            logger.error(f"Failed to initialize semantic search system: {e}")
            return False

    def shutdown(self) -> None:
        """关闭语义搜索系统"""
        try:
            self._embedding_worker.stop()
            logger.info("Semantic search system shut down")
        except Exception as e:
            logger.error(f"Error shutting down semantic search system: {e}")

    def is_available(self) -> bool:
        """检查语义搜索是否可用"""
        return (
            self._embedding_service.is_model_available()
            and self._faiss_index_manager.is_available()
        )

    def schedule_email_for_embedding(self, email: Email) -> None:
        """调度邮件进行嵌入生成"""
        if not self._embedding_service.is_model_available():
            return

        self._embedding_worker.schedule_email_for_embedding(email)

    def schedule_multiple_emails_for_embedding(self, emails: List[Email]) -> None:
        """批量调度邮件进行嵌入生成"""
        if not self._embedding_service.is_model_available():
            return

        for email in emails:
            self._embedding_worker.schedule_email_for_embedding(email)

    def build_vector_index(self, account_id: Optional[int] = None) -> bool:
        """构建向量索引"""
        if not self.is_available():
            logger.warning("Semantic search not available, cannot build index")
            return False

        return self._semantic_search_service.build_index_for_account(account_id)

    def search(
        self,
        query: str,
        account_id: Optional[int] = None,
        folder_id: Optional[int] = None,
        limit: int = 20,
        semantic_weight: float = 0.3,
        similarity_threshold: float = 0.2,
    ) -> List[Tuple[Email, float]]:
        """语义搜索"""
        if not self.is_available():
            logger.debug("Semantic search not available")
            return []

        return self._semantic_search_service.search_semantic_only(
            query=query,
            account_id=account_id,
            folder_id=folder_id,
            limit=limit,
            similarity_threshold=similarity_threshold,
        )

    def hybrid_search(
        self,
        fts_results: List[Email],
        query: str,
        semantic_weight: float = 0.3,
        rerank_limit: int = 50,
    ) -> List[Email]:
        """混合搜索：重新排序FTS结果"""
        if not self.is_available() or semantic_weight <= 0:
            return fts_results

        return self._semantic_search_service.hybrid_search(
            fts_results=fts_results,
            query=query,
            semantic_weight=semantic_weight,
            rerank_limit=rerank_limit,
        )

    def find_similar_emails(
        self, email: Email, limit: int = 10, similarity_threshold: float = 0.4
    ) -> List[Tuple[Email, float]]:
        """查找相似邮件"""
        if not self.is_available():
            return []

        return self._semantic_search_service.find_similar_emails(
            email=email, limit=limit, similarity_threshold=similarity_threshold
        )

    def get_similar_conversations(
        self, email: Email, limit: int = 5
    ) -> List[Tuple[Email, float]]:
        """查找相似对话（基于主题和内容）"""
        # 首先获取相似邮件
        similar_emails = self.find_similar_emails(
            email=email, limit=limit * 2, similarity_threshold=0.3
        )

        # 按主题分组（简单的对话检测）
        conversations = {}
        for similar_email, similarity in similar_emails:
            # 清理主题（移除Re:, Fwd:等前缀）
            raw_subject = similar_email.subject or ""
            base_subject = raw_subject.lower().strip()
            for prefix in ["re:", "fwd:", "fw:", "回复：", "转发："]:
                if base_subject.startswith(prefix):
                    base_subject = base_subject[len(prefix) :].strip()

            # 使用发件人和基础主题作为对话键
            conversation_key = f"{base_subject}_{similar_email.sender_addr}"

            if conversation_key not in conversations:
                conversations[conversation_key] = {
                    "subject": raw_subject,
                    "sender": similar_email.sender_addr,
                    "emails": [],
                    "max_similarity": similarity,
                }

            conversations[conversation_key]["emails"].append(
                (similar_email, similarity)
            )
            conversations[conversation_key]["max_similarity"] = max(
                conversations[conversation_key]["max_similarity"], similarity
            )

        # 转换为结果列表并排序
        conversation_results = []
        for key, conv_data in conversations.items():
            # 取代表性的邮件（相似度最高的）
            if conv_data["emails"]:
                best_email, best_similarity = max(
                    conv_data["emails"], key=lambda x: x[1]
                )
                conversation_results.append((best_email, best_similarity))

        # 按相似度排序
        conversation_results.sort(key=lambda x: x[1], reverse=True)
        return conversation_results[:limit]

    def compute_search_quality_metrics(
        self,
        query: str,
        fts_results: List[Email],
        hybrid_results: List[Email],
        semantic_weight: float = 0.3,
    ) -> dict:
        """计算搜索质量指标"""
        metrics = {
            "fts_count": len(fts_results),
            "hybrid_count": len(hybrid_results),
            "overlap": 0,
            "rank_correlation": 0.0,
            "semantic_weight": semantic_weight,
        }

        # 计算重叠（多少邮件在两个结果集中）
        if fts_results and hybrid_results:
            fts_ids = set(email.id for email in fts_results)
            hybrid_ids = set(email.id for email in hybrid_results)
            overlap = len(fts_ids.intersection(hybrid_ids))
            metrics["overlap"] = overlap

        # 计算排名相关性（简单的Kendall tau）
        try:
            # 创建排名映射
            fts_rank = {email.id: i for i, email in enumerate(fts_results)}
            hybrid_rank = {email.id: i for i, email in enumerate(hybrid_results)}

            # 计算共同邮件的排名差
            common_ids = set(fts_rank.keys()).intersection(set(hybrid_rank.keys()))
            if len(common_ids) > 1:
                rank_diffs = [
                    abs(fts_rank[email_id] - hybrid_rank[email_id])
                    for email_id in common_ids
                ]
                # 归一化的平均排名差（分数越低越好）
                max_possible_diff = len(fts_results) - 1
                avg_normalized_diff = sum(rank_diffs) / (
                    len(rank_diffs) * max(1, max_possible_diff)
                )
                metrics["rank_correlation"] = 1.0 - avg_normalized_diff
        except Exception as e:
            logger.debug(f"Error computing rank correlation: {e}")

        return metrics

    def get_system_status(self) -> dict:
        """获取语义搜索系统状态"""
        return {
            "available": self.is_available(),
            "model_loaded": self._embedding_service.is_model_available(),
            "faiss_available": self._faiss_index_manager.is_available(),
            "index_stats": self._faiss_index_manager.get_index_stats(),
            "embedding_service": "loaded"
            if self._embedding_service.is_model_available()
            else "not_available",
            "worker_running": True,  # 简化，实际需要从worker获取状态
        }


# 创建全局实例
semantic_search_manager = SemanticSearchManager()


def init_semantic_search() -> bool:
    """初始化语义搜索系统（应用启动时调用）"""
    try:
        # 检查依赖
        import importlib.util

        dependencies = ["torch", "sentence_transformers", "faiss"]
        missing_deps = []

        for dep in dependencies:
            if importlib.util.find_spec(dep) is None:
                missing_deps.append(dep)

        if missing_deps:
            logger.info(f"Semantic search dependencies missing: {missing_deps}")
            logger.info(
                "Install with: pip install sentence-transformers torch faiss-cpu"
            )
            return False

        # 初始化语义搜索管理器
        success = semantic_search_manager.initialize()

        if success:
            logger.info("Semantic search system initialized successfully")
        else:
            logger.warning("Semantic search system initialization failed")

        return success

    except Exception as e:
        logger.error(f"Failed to initialize semantic search: {e}")
        return False


def shutdown_semantic_search() -> None:
    """关闭语义搜索系统（应用退出时调用）"""
    semantic_search_manager.shutdown()
