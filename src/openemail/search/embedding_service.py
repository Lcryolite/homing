from __future__ import annotations

import asyncio
import logging
import threading
import json
from dataclasses import dataclass
from datetime import datetime
from typing import List, Optional, Tuple, Dict, Any
import numpy as np
import sqlite3

from openemail.models.email import Email
from openemail.storage.database import db

logger = logging.getLogger(__name__)


@dataclass
class EmailEmbedding:
    """邮件文本嵌入"""

    email_id: int
    account_id: int
    embedding: np.ndarray  # 768-dim 向量（paraphrase-multilingual-MiniLM-L12-v2）
    text_hash: str  # 文本哈希，用于检测变化
    created_at: datetime
    updated_at: datetime

    @staticmethod
    def from_row(row: dict) -> EmailEmbedding:
        """从数据库行创建对象"""
        embedding_bytes = row.get("embedding_blob")
        if embedding_bytes:
            embedding = np.frombuffer(embedding_bytes, dtype=np.float32)
        else:
            embedding = np.zeros(384, dtype=np.float32)  # 默认向量

        return EmailEmbedding(
            email_id=row["email_id"],
            account_id=row["account_id"],
            embedding=embedding,
            text_hash=row["text_hash"] or "",
            created_at=datetime.fromisoformat(row["created_at"]),
            updated_at=datetime.fromisoformat(row.get("updated_at", row["created_at"])),
        )


class EmbeddingService:
    """邮件文本嵌入服务，生成和存储邮件文本嵌入"""

    _instance: Optional[EmbeddingService] = None

    def __new__(cls) -> EmbeddingService:
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self) -> None:
        if not self._initialized:
            self._model = None
            self._model_loaded = False
            self._load_model_lock = threading.Lock()
            self._initialized = True

    def is_model_available(self) -> bool:
        """检查语义模型是否可用"""
        try:
            # 尝试导入模型库
            from sentence_transformers import SentenceTransformer
            import torch

            # 尝试加载模型
            if not self._model_loaded:
                with self._load_model_lock:
                    if not self._model_loaded:
                        # 使用轻型多语言模型（中英文都支持）
                        self._model = SentenceTransformer(
                            "paraphrase-multilingual-MiniLM-L12-v2"
                        )
                        self._model_loaded = True
                        logger.info(
                            "Semantic model loaded: paraphrase-multilingual-MiniLM-L12-v2"
                        )

            return self._model_loaded and self._model is not None

        except ImportError as e:
            logger.warning(f"SentenceTransformers not available: {e}")
            return False
        except Exception as e:
            logger.error(f"Error loading semantic model: {e}")
            return False

    def get_email_text_for_embedding(self, email: Email) -> str:
        """提取邮件文本用于生成嵌入"""
        text_parts = []

        # 主题
        if email.subject:
            text_parts.append(f"主题: {email.subject}")

        # 发件人/收件人信息
        if email.display_sender:
            text_parts.append(f"发件人: {email.display_sender}")

        # 正文预览
        if email.preview_text:
            # 取前500字符作为摘要
            preview = email.preview_text[:500]
            text_parts.append(f"内容: {preview}")

        # 如果有正文文件，可以读取更多内容（为了性能，这里只使用预览）

        return "\n".join(text_parts)

    def generate_embedding(self, text: str) -> Optional[np.ndarray]:
        """为文本生成嵌入向量"""
        if not self.is_model_available():
            return None

        try:
            if not text or len(text.strip()) == 0:
                return None

            # 清理文本
            clean_text = text.strip()
            if len(clean_text) < 10:  # 太短的文本可能没有意义
                return None

            # 使用模型生成嵌入
            embedding = self._model.encode(
                [clean_text],
                convert_to_tensor=True,
                normalize_embeddings=True,  # 归一化，便于cosine相似度计算
            )

            # 转换为numpy数组并分离梯度
            embedding_np = embedding.detach().cpu().numpy().flatten()

            logger.debug(
                f"Generated embedding for text length {len(clean_text)}: vector shape {embedding_np.shape}"
            )
            return embedding_np

        except Exception as e:
            logger.error(f"Error generating embedding: {e}")
            return None

    def compute_similarity(
        self, embedding1: np.ndarray, embedding2: np.ndarray
    ) -> float:
        """计算两个嵌入向量的余弦相似度"""
        if embedding1 is None or embedding2 is None:
            return 0.0

        try:
            # 计算余弦相似度
            dot_product = np.dot(embedding1, embedding2)
            norm1 = np.linalg.norm(embedding1)
            norm2 = np.linalg.norm(embedding2)

            if norm1 == 0 or norm2 == 0:
                return 0.0

            similarity = dot_product / (norm1 * norm2)
            return float(similarity)

        except Exception as e:
            logger.error(f"Error computing similarity: {e}")
            return 0.0

    def compute_text_similarity(self, text1: str, text2: str) -> float:
        """计算两个文本的语义相似度"""
        embedding1 = self.generate_embedding(text1)
        embedding2 = self.generate_embedding(text2)

        if embedding1 is None or embedding2 is None:
            return 0.0

        return self.compute_similarity(embedding1, embedding2)

    def generate_email_embedding(self, email: Email) -> Optional[np.ndarray]:
        """为邮件生成嵌入"""
        try:
            # 提取邮件文本
            text_for_embedding = self.get_email_text_for_embedding(email)

            if not text_for_embedding:
                logger.debug(f"No text for embedding for email {email.id}")
                return None

            # 生成嵌入
            embedding = self.generate_embedding(text_for_embedding)

            if embedding is None:
                logger.debug(f"Failed to generate embedding for email {email.id}")
                return None

            logger.info(
                f"Generated embedding for email {email.id}: shape {embedding.shape}"
            )
            return embedding

        except Exception as e:
            logger.error(f"Error generating email embedding: {e}")
            return None


class EmbeddingStorage:
    """嵌入向量存储管理"""

    @staticmethod
    def create_tables() -> None:
        """创建嵌入存储表"""
        try:
            # 创建邮件嵌入表
            db.execute("""
                CREATE TABLE IF NOT EXISTS email_embeddings (
                    email_id INTEGER PRIMARY KEY,
                    account_id INTEGER NOT NULL,
                    embedding_blob BLOB,
                    text_hash TEXT NOT NULL,
                    model_version TEXT DEFAULT 'v1',
                    embedding_dim INTEGER DEFAULT 384,
                    similar_email_ids TEXT,  -- 相似邮件ID列表（JSON）
                    similarity_scores TEXT,  -- 相似度分数（JSON）
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (email_id) REFERENCES emails(id) ON DELETE CASCADE,
                    FOREIGN KEY (account_id) REFERENCES accounts(id) ON DELETE CASCADE
                )
            """)

            # 创建索引
            db.execute(
                "CREATE INDEX IF NOT EXISTS idx_embedding_account ON email_embeddings(account_id)"
            )
            db.execute(
                "CREATE INDEX IF NOT EXISTS idx_embedding_hash ON email_embeddings(text_hash)"
            )
            db.execute(
                "CREATE INDEX IF NOT EXISTS idx_embedding_updated ON email_embeddings(updated_at)"
            )

            logger.info("Email embedding tables created")

        except sqlite3.Error as e:
            logger.error(f"Failed to create embedding tables: {e}")

    @staticmethod
    def save_embedding(
        email_id: int, account_id: int, embedding: np.ndarray, text_hash: str
    ) -> bool:
        """保存邮件嵌入"""
        try:
            embedding_bytes = embedding.astype(np.float32).tobytes()

            # 检查是否已存在
            existing = db.fetchone(
                "SELECT email_id FROM email_embeddings WHERE email_id = ?", (email_id,)
            )

            now = datetime.now().isoformat()

            if existing:
                # 更新现有记录
                db.execute(
                    """
                    UPDATE email_embeddings 
                    SET embedding_blob = ?, text_hash = ?, updated_at = ?
                    WHERE email_id = ?
                """,
                    (embedding_bytes, text_hash, now, email_id),
                )
                logger.debug(f"Updated embedding for email {email_id}")
            else:
                # 插入新记录
                db.execute(
                    """
                    INSERT INTO email_embeddings 
                    (email_id, account_id, embedding_blob, text_hash, created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?)
                """,
                    (email_id, account_id, embedding_bytes, text_hash, now, now),
                )
                logger.debug(f"Saved new embedding for email {email_id}")

            return True

        except Exception as e:
            logger.error(f"Failed to save embedding for email {email_id}: {e}")
            return False

    @staticmethod
    def get_embedding(email_id: int) -> Optional[EmailEmbedding]:
        """获取邮件嵌入"""
        try:
            row = db.fetchone(
                "SELECT * FROM email_embeddings WHERE email_id = ?", (email_id,)
            )
            if row:
                return EmailEmbedding.from_row(row)
            return None
        except Exception as e:
            logger.error(f"Failed to get embedding for email {email_id}: {e}")
            return None

    @staticmethod
    def delete_embedding(email_id: int) -> bool:
        """删除邮件嵌入"""
        try:
            db.execute("DELETE FROM email_embeddings WHERE email_id = ?", (email_id,))
            logger.debug(f"Deleted embedding for email {email_id}")
            return True
        except Exception as e:
            logger.error(f"Failed to delete embedding for email {email_id}: {e}")
            return False

    @staticmethod
    def batch_get_embeddings(email_ids: List[int]) -> Dict[int, EmailEmbedding]:
        """批量获取邮件嵌入"""
        embeddings = {}
        try:
            for email_id in email_ids:
                embedding = EmbeddingStorage.get_embedding(email_id)
                if embedding:
                    embeddings[email_id] = embedding
        except Exception as e:
            logger.error(f"Failed to batch get embeddings: {e}")

        return embeddings

    @staticmethod
    def update_similar_emails(
        email_id: int, similar_emails: List[Tuple[int, float]]
    ) -> bool:
        """更新相似邮件列表"""
        try:
            # 格式化为JSON
            similar_ids = [email_id for email_id, _ in similar_emails]
            similarity_scores = [str(score) for _, score in similar_emails]

            similar_ids_json = json.dumps(similar_ids)
            scores_json = json.dumps(similarity_scores)

            db.execute(
                """
                UPDATE email_embeddings 
                SET similar_email_ids = ?, similarity_scores = ?
                WHERE email_id = ?
            """,
                (similar_ids_json, scores_json, email_id),
            )

            logger.debug(f"Updated similar emails for email {email_id}")
            return True

        except Exception as e:
            logger.error(f"Failed to update similar emails for email {email_id}: {e}")
            return False

    @staticmethod
    def get_similar_emails(email_id: int, limit: int = 10) -> List[Tuple[int, float]]:
        """获取相似邮件"""
        try:
            row = db.fetchone(
                "SELECT similar_email_ids, similarity_scores FROM email_embeddings WHERE email_id = ?",
                (email_id,),
            )
            if not row:
                return []

            similar_ids_str = row.get("similar_email_ids")
            scores_str = row.get("similarity_scores")

            if not similar_ids_str or not scores_str:
                return []

            similar_ids = json.loads(similar_ids_str)
            scores = json.loads(scores_str)

            # 组合并限制数量
            results = []
            for i, (similar_id, score_str) in enumerate(zip(similar_ids, scores)):
                if i >= limit:
                    break
                try:
                    score = float(score_str)
                    results.append((similar_id, score))
                except (ValueError, TypeError):
                    continue

            return results

        except Exception as e:
            logger.error(f"Failed to get similar emails for email {email_id}: {e}")
            return []


class EmbeddingWorker:
    """后台嵌入生成工作器"""

    def __init__(self, batch_size: int = 10) -> None:
        self._batch_size = batch_size
        self._running = False
        self._worker_thread: Optional[threading.Thread] = None
        self._embedding_service = EmbeddingService()
        self._pending_emails: List[Email] = []
        self._pending_lock = threading.Lock()

    def start(self) -> None:
        """启动工作器"""
        if self._running:
            logger.warning("Embedding worker already running")
            return

        self._running = True
        self._worker_thread = threading.Thread(target=self._worker_loop, daemon=True)
        self._worker_thread.start()
        logger.info("Embedding worker started")

    def stop(self) -> None:
        """停止工作器"""
        if not self._running:
            return

        logger.info("Stopping embedding worker")
        self._running = False

        if self._worker_thread:
            self._worker_thread.join(timeout=5.0)

        logger.info("Embedding worker stopped")

    def schedule_email_for_embedding(self, email: Email) -> None:
        """调度邮件进行嵌入生成"""
        with self._pending_lock:
            self._pending_emails.append(email)
            logger.debug(f"Scheduled email {email.id} for embedding")

    def _worker_loop(self) -> None:
        """工作器主循环"""
        while self._running:
            try:
                # 获取待处理邮件
                with self._pending_lock:
                    if not self._pending_emails:
                        continue

                    batch = self._pending_emails[: self._batch_size]
                    self._pending_emails = self._pending_emails[self._batch_size :]

                # 处理批次
                self._process_batch(batch)

            except Exception as e:
                logger.error(f"Error in embedding worker loop: {e}")

            # 休眠避免CPU占用过高
            import time

            time.sleep(1)

    def _process_batch(self, emails: List[Email]) -> None:
        """处理一批邮件"""
        if not self._embedding_service.is_model_available():
            logger.debug("Semantic model not available, skipping batch")
            return

        for email in emails:
            try:
                # 计算文本哈希（简单的MD5）
                import hashlib

                email_text = self._embedding_service.get_email_text_for_embedding(email)
                if not email_text:
                    continue

                text_hash = hashlib.md5(email_text.encode("utf-8")).hexdigest()

                # 检查是否已存在相同哈希的嵌入
                existing = db.fetchone(
                    "SELECT email_id FROM email_embeddings WHERE email_id = ? AND text_hash = ?",
                    (email.id, text_hash),
                )

                if existing:
                    logger.debug(
                        f"Embedding already exists for email {email.id} with same hash"
                    )
                    continue

                # 生成嵌入
                embedding = self._embedding_service.generate_email_embedding(email)
                if embedding is None:
                    logger.debug(f"Failed to generate embedding for email {email.id}")
                    continue

                # 保存嵌入
                success = EmbeddingStorage.save_embedding(
                    email.id, email.account_id, embedding, text_hash
                )
                if success:
                    logger.info(f"Generated and saved embedding for email {email.id}")
                else:
                    logger.warning(f"Failed to save embedding for email {email.id}")

            except Exception as e:
                logger.error(f"Error processing email {email.id} for embedding: {e}")
                continue


# 全局实例
embedding_service = EmbeddingService()
embedding_storage = EmbeddingStorage()
embedding_worker = EmbeddingWorker()

# 在启动时创建表
EmbeddingStorage.create_tables()
