from __future__ import annotations

import logging
import pickle
import sqlite3
from pathlib import Path
from typing import List, Optional, Tuple, Dict, Any
import numpy as np
import os

from openemail.storage.database import db
from openemail.search.embedding_service import embedding_service, EmailEmbedding
from openemail.models.email import Email

logger = logging.getLogger(__name__)


class FaissIndexManager:
    """Faiss 向量索引管理器，用于快速相似度搜索"""

    def __init__(self, workspace_dir: Optional[Path] = None):
        if workspace_dir is None:
            import tempfile

            workspace_dir = Path(tempfile.gettempdir()) / "openemail_faiss"

        self._workspace_dir = Path(workspace_dir)
        self._workspace_dir.mkdir(parents=True, exist_ok=True)

        self._index = None
        self._index_type = "Flat"  # 或 "IVF", "HNSW" 等
        self._embeddings_cache: Dict[int, np.ndarray] = {}
        self._index_loaded = False
        self._dimension = 384  # paraphrase-multilingual-MiniLM-L12-v2 的维度

    def initialize_index(self) -> bool:
        """初始化 Faiss 索引"""
        try:
            import faiss

            # 创建索引 - 使用内积作为相似度（因为向量是归一化的）
            self._index = faiss.IndexFlatIP(self._dimension)
            self._index_loaded = True
            logger.info(f"Faiss index initialized with dimension {self._dimension}")
            return True

        except ImportError as e:
            logger.warning(f"Faiss not available: {e}")
            logger.info("Install faiss: pip install faiss-cpu")
            return False
        except Exception as e:
            logger.error(f"Failed to initialize Faiss index: {e}")
            return False

    def is_available(self) -> bool:
        """检查 Faiss 是否可用"""
        try:
            import faiss

            if not hasattr(self, "_index") or self._index is None:
                return self.initialize_index()
            return True
        except ImportError:
            return False

    def build_index_from_database(self, account_id: Optional[int] = None) -> bool:
        """从数据库加载所有嵌入并构建索引"""
        if not self.is_available():
            logger.warning("Faiss not available, cannot build index")
            return False

        try:
            import faiss

            # 清空缓存
            self._embeddings_cache.clear()

            # 准备查询
            where_clause = "1=1"
            params = []
            if account_id is not None:
                where_clause = "account_id = ?"
                params.append(account_id)

            # 获取所有嵌入
            sql = f"SELECT email_id, embedding_blob FROM email_embeddings WHERE {where_clause}"
            rows = db.fetchall(sql, params)

            if not rows:
                logger.warning("No embeddings found in database")
                return False

            # 收集嵌入向量
            embeddings = []
            email_ids = []

            for row in rows:
                try:
                    email_id = row["email_id"]
                    embedding_bytes = row["embedding_blob"]

                    if embedding_bytes:
                        embedding = np.frombuffer(embedding_bytes, dtype=np.float32)

                        # 确保维度正确
                        if embedding.shape[0] == self._dimension:
                            embeddings.append(embedding)
                            email_ids.append(email_id)

                            # 添加到缓存
                            self._embeddings_cache[email_id] = embedding
                except Exception as e:
                    logger.warning(
                        f"Error processing embedding for email {row.get('email_id')}: {e}"
                    )
                    continue

            if not embeddings:
                logger.warning("No valid embeddings found")
                return False

            # 转换为 numpy 数组
            embeddings_array = np.vstack(embeddings).astype(np.float32)

            # 检查是否需要重新初始化索引（维度不匹配或索引为空）
            if self._index is None or self._index.d != self._dimension:
                self.initialize_index()

            # 添加向量到索引
            self._index.add(embeddings_array)

            logger.info(f"Built Faiss index with {len(email_ids)} embeddings")

            # 保存索引元数据
            self._save_index_metadata(email_ids, account_id)

            return True

        except Exception as e:
            logger.error(f"Failed to build Faiss index: {e}")
            return False

    def _save_index_metadata(
        self, email_ids: List[int], account_id: Optional[int]
    ) -> None:
        """保存索引元数据"""
        try:
            metadata = {
                "email_ids": email_ids,
                "account_id": account_id,
                "dimension": self._dimension,
                "count": len(email_ids),
                "index_type": self._index_type,
                "timestamp": os.path.getmtime(Path(__file__)),
            }

            metadata_path = self._workspace_dir / "index_metadata.pkl"
            with open(metadata_path, "wb") as f:
                pickle.dump(metadata, f)

            logger.debug(f"Saved index metadata for {len(email_ids)} embeddings")

        except Exception as e:
            logger.error(f"Failed to save index metadata: {e}")

    def add_embedding_to_index(self, email_id: int, embedding: np.ndarray) -> bool:
        """添加单个嵌入到索引"""
        if not self.is_available():
            return False

        try:
            import faiss

            # 确保维度正确
            if embedding.shape[0] != self._dimension:
                logger.error(
                    f"Embedding dimension mismatch: {embedding.shape[0]} != {self._dimension}"
                )
                return False

            # 添加到索引
            embedding_reshaped = embedding.reshape(1, -1).astype(np.float32)
            self._index.add(embedding_reshaped)

            # 添加到缓存
            self._embeddings_cache[email_id] = embedding

            logger.debug(f"Added embedding for email {email_id} to Faiss index")
            return True

        except Exception as e:
            logger.error(f"Failed to add embedding to index: {e}")
            return False

    def remove_embedding_from_index(self, email_id: int) -> bool:
        """从索引中移除嵌入（Faiss 不支持删除，需要重建）"""
        logger.warning(
            "Faiss does not support removing vectors from index, will rebuild on next search"
        )
        if email_id in self._embeddings_cache:
            del self._embeddings_cache[email_id]
        return False

    def search_similar(
        self,
        query_embedding: np.ndarray,
        k: int = 10,
        account_id: Optional[int] = None,
        exclude_email_ids: Optional[List[int]] = None,
    ) -> List[Tuple[int, float]]:
        """搜索相似邮件"""
        if not self.is_available():
            logger.warning("Faiss not available for similarity search")
            return []

        try:
            import faiss

            if exclude_email_ids is None:
                exclude_email_ids = []

            # 搜索数量加倍以过滤排除的邮件
            search_k = min(k * 2 + len(exclude_email_ids), self._index.ntotal)
            if search_k <= 0:
                return []

            # 准备查询向量
            query_embedding_reshaped = query_embedding.reshape(1, -1).astype(np.float32)

            # 执行搜索
            distances, indices = self._index.search(query_embedding_reshaped, search_k)

            # 获取元数据中的邮件ID映射
            metadata_path = self._workspace_dir / "index_metadata.pkl"
            email_id_mapping = {}

            if metadata_path.exists():
                try:
                    with open(metadata_path, "rb") as f:
                        metadata = pickle.load(f)
                        email_id_mapping = dict(
                            enumerate(metadata.get("email_ids", []))
                        )
                except Exception as e:
                    logger.warning(f"Failed to load index metadata: {e}")
                    return []
            else:
                logger.warning("Index metadata not found, using cache")
                # 从缓存构建映射
                cached_ids = list(self._embeddings_cache.keys())
                email_id_mapping = dict(enumerate(cached_ids))

            # 处理结果
            results = []
            seen_emails = set()

            for i, distance in zip(indices[0], distances[0]):
                if i in email_id_mapping:
                    email_id = email_id_mapping[i]

                    # 排除特定邮件
                    if email_id in exclude_email_ids:
                        continue

                    # 去重
                    if email_id in seen_emails:
                        continue

                    # 应用账户过滤
                    if account_id is not None:
                        # 需要查询数据库获取账户信息
                        row = db.fetchone(
                            "SELECT account_id FROM email_embeddings WHERE email_id = ?",
                            (email_id,),
                        )
                        if not row or row.get("account_id") != account_id:
                            continue

                    # 距离转换为相似度（Faiss 内积越大越相似）
                    similarity = float(distance)  # 对于归一化向量，内积就是余弦相似度

                    # 确保相似度在合理范围内
                    similarity = max(-1.0, min(1.0, similarity))

                    results.append((email_id, similarity))
                    seen_emails.add(email_id)

                    if len(results) >= k:
                        break

            logger.debug(f"Found {len(results)} similar emails")
            return results

        except Exception as e:
            logger.error(f"Failed to search similar emails: {e}")
            return []

    def search_by_text(
        self,
        query_text: str,
        k: int = 10,
        account_id: Optional[int] = None,
        exclude_email_ids: Optional[List[int]] = None,
    ) -> List[Tuple[Email, float]]:
        """通过文本搜索相似邮件"""
        # 生成查询嵌入
        query_embedding = embedding_service.generate_embedding(query_text)
        if query_embedding is None:
            logger.warning("Failed to generate query embedding")
            return []

        # 搜索相似向量
        similar_emails = self.search_similar(
            query_embedding, k, account_id, exclude_email_ids
        )

        # 获取邮件对象
        results = []
        for email_id, similarity in similar_emails:
            email = Email.get_by_id(email_id)
            if email:
                results.append((email, similarity))

        # 按相似度排序
        results.sort(key=lambda x: x[1], reverse=True)
        return results

    def compute_email_similarity(self, email1_id: int, email2_id: int) -> float:
        """计算两个邮件的相似度"""
        # 从缓存获取嵌入
        embedding1 = self._embeddings_cache.get(email1_id)
        embedding2 = self._embeddings_cache.get(email2_id)

        # 如果不在缓存中，从数据库获取
        if embedding1 is None:
            emb1_obj = embedding_service.generate_email_embedding(
                Email.get_by_id(email1_id)
            )
            if emb1_obj is not None:
                embedding1 = emb1_obj
                self._embeddings_cache[email1_id] = embedding1

        if embedding2 is None:
            emb2_obj = embedding_service.generate_email_embedding(
                Email.get_by_id(email2_id)
            )
            if emb2_obj is not None:
                embedding2 = emb2_obj
                self._embeddings_cache[email2_id] = embedding2

        if embedding1 is None or embedding2 is None:
            return 0.0

        # 计算余弦相似度
        similarity = embedding_service.compute_similarity(embedding1, embedding2)
        return similarity

    def batch_compute_similarities(
        self, email_id: int, candidate_ids: List[int]
    ) -> List[Tuple[int, float]]:
        """批量计算与候选邮件的相似度"""
        results = []

        # 获取查询邮件的嵌入
        query_embedding = self._embeddings_cache.get(email_id)
        if query_embedding is None:
            emb_obj = embedding_service.generate_email_embedding(
                Email.get_by_id(email_id)
            )
            if emb_obj is not None:
                query_embedding = emb_obj
                self._embeddings_cache[email_id] = query_embedding
            else:
                return results

        # 批量计算相似度
        for candidate_id in candidate_ids:
            # 获取候选邮件嵌入
            candidate_embedding = self._embeddings_cache.get(candidate_id)
            if candidate_embedding is None:
                emb_obj = embedding_service.generate_email_embedding(
                    Email.get_by_id(candidate_id)
                )
                if emb_obj is not None:
                    candidate_embedding = emb_obj
                    self._embeddings_cache[candidate_id] = candidate_embedding
                else:
                    continue

            # 计算相似度
            similarity = embedding_service.compute_similarity(
                query_embedding, candidate_embedding
            )
            results.append((candidate_id, similarity))

        # 按相似度排序
        results.sort(key=lambda x: x[1], reverse=True)
        return results

    def get_index_stats(self) -> Dict[str, Any]:
        """获取索引统计信息"""
        stats = {
            "available": self.is_available(),
            "loaded": self._index_loaded,
            "dimension": self._dimension,
            "index_type": self._index_type,
        }

        if self._index is not None:
            try:
                stats["total_vectors"] = self._index.ntotal
                stats["cache_size"] = len(self._embeddings_cache)
            except:
                pass

        return stats


# 全局实例
faiss_index_manager = FaissIndexManager()

# 尝试初始化
if faiss_index_manager.is_available():
    logger.info("Faiss index manager initialized successfully")
else:
    logger.info("Faiss index manager not available (faiss-cpu not installed)")


class SemanticSearchService:
    """语义搜索服务，结合 Faiss 和混合搜索"""

    def __init__(self):
        self._faiss_manager = faiss_index_manager
        self._embedding_service = embedding_service

    def search_semantic_only(
        self,
        query: str,
        account_id: Optional[int] = None,
        folder_id: Optional[int] = None,
        limit: int = 20,
        similarity_threshold: float = 0.3,
    ) -> List[Tuple[Email, float]]:
        """纯语义搜索"""
        if not self._faiss_manager.is_available():
            logger.debug("Faiss not available for semantic search")
            return []

        # 执行Faiss搜索
        results = self._faiss_manager.search_by_text(
            query_text=query,
            k=limit * 2,  # 多搜索一些用于过滤
            account_id=account_id,
        )

        # 应用文件夹过滤
        filtered_results = []
        for email, similarity in results:
            if similarity < similarity_threshold:
                continue

            if folder_id is not None and email.folder_id != folder_id:
                continue

            filtered_results.append((email, similarity))

        # 限制数量
        return filtered_results[:limit]

    def hybrid_search(
        self,
        fts_results: List[Email],
        query: str,
        semantic_weight: float = 0.5,
        rerank_limit: int = 50,
    ) -> List[Email]:
        """混合搜索：FTS5结果 + 语义重排"""
        if semantic_weight <= 0 or not query or not fts_results:
            return fts_results

        if not self._faiss_manager.is_available():
            logger.debug("Faiss not available, skipping hybrid search")
            return fts_results

        # 限制重排的邮件数量
        emails_to_rerank = fts_results[:rerank_limit]

        # 为查询生成嵌入
        query_embedding = self._embedding_service.generate_embedding(query)
        if query_embedding is None:
            return fts_results

        # 计算每个邮件的相似度
        scored_emails = []
        for email in emails_to_rerank:
            # 获取邮件嵌入
            email_embedding_obj = self._embedding_service.generate_email_embedding(
                email
            )
            if email_embedding_obj is None:
                # 如果没有嵌入，FTS得分权重为1，语义权重为0
                scored_emails.append((email, 1.0, 0.0))
                continue

            email_embedding = email_embedding_obj

            # 计算语义相似度
            similarity = embedding_service.compute_similarity(
                query_embedding, email_embedding
            )

            # 假设FTS排名越高得分越高（这里简化为位置反比）
            fts_position_score = (
                1.0 - (fts_results.index(email) / len(fts_results))
                if email in fts_results
                else 0.5
            )

            scored_emails.append((email, fts_position_score, similarity))

        # 混合评分
        reranked = []
        for email, fts_score, semantic_score in scored_emails:
            # 组合得分
            combined_score = (
                1.0 - semantic_weight
            ) * fts_score + semantic_weight * semantic_score
            reranked.append((email, combined_score))

        # 按综合得分排序
        reranked.sort(key=lambda x: x[1], reverse=True)

        # 提取邮件
        reranked_emails = [email for email, _ in reranked]

        # 加上未重排的邮件
        remaining_emails = fts_results[rerank_limit:]
        if remaining_emails:
            reranked_emails.extend(remaining_emails)

        return reranked_emails

    def find_similar_emails(
        self, email: Email, limit: int = 10, similarity_threshold: float = 0.5
    ) -> List[Tuple[Email, float]]:
        """查找与指定邮件相似的邮件"""
        if not self._faiss_manager.is_available():
            return []

        # 使用Faiss搜索相似邮件
        email_embedding = self._embedding_service.generate_email_embedding(email)
        if email_embedding is None:
            return []

        similar_results = self._faiss_manager.search_similar(
            query_embedding=email_embedding,
            k=limit * 2,  # 多搜索一些用于过滤
            account_id=email.account_id,
            exclude_email_ids=[email.id],
        )

        # 过滤和获取邮件对象
        results = []
        for email_id, similarity in similar_results:
            if similarity < similarity_threshold:
                continue

            similar_email = Email.get_by_id(email_id)
            if similar_email:
                results.append((similar_email, similarity))

            if len(results) >= limit:
                break

        return results

    def build_index_for_account(self, account_id: Optional[int] = None) -> bool:
        """为账户构建向量索引（后台任务）"""
        return self._faiss_manager.build_index_from_database(account_id)


# 全局实例
semantic_search_service = SemanticSearchService()
