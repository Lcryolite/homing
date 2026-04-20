from __future__ import annotations

import asyncio
import logging
import threading
import json
from dataclasses import dataclass
from datetime import datetime
from typing import List, Optional, Tuple, Dict, Any
import sqlite3

from openemail.models.email import Email
from openemail.storage.database import db

logger = logging.getLogger(__name__)


def _get_np():
    try:
        import numpy as np

        return np
    except ImportError:
        return None


@dataclass
class EmailEmbedding:
    email_id: int
    account_id: int
    embedding: Any  # np.ndarray when numpy available, else None
    text_hash: str
    created_at: datetime
    updated_at: datetime

    @staticmethod
    def from_row(row: dict) -> EmailEmbedding:
        np = _get_np()
        embedding_bytes = row["embedding_blob"]
        if embedding_bytes and np is not None:
            embedding = np.frombuffer(embedding_bytes, dtype=np.float32)
        elif np is not None:
            embedding = np.zeros(384, dtype=np.float32)
        else:
            embedding = None

        return EmailEmbedding(
            email_id=row["email_id"],
            account_id=row["account_id"],
            embedding=embedding,
            text_hash=row["text_hash"] or "",
            created_at=datetime.fromisoformat(row["created_at"]),
            updated_at=datetime.fromisoformat(row["updated_at"] or row["created_at"]),
        )


class EmbeddingService:
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
        if _get_np() is None:
            return False
        try:
            from sentence_transformers import SentenceTransformer
            import torch

            if not self._model_loaded:
                with self._load_model_lock:
                    if not self._model_loaded:
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
        text_parts = []
        if email.subject:
            text_parts.append(f"主题: {email.subject}")
        if email.display_sender:
            text_parts.append(f"发件人: {email.display_sender}")
        if email.preview_text:
            preview = email.preview_text[:500]
            text_parts.append(f"内容: {preview}")
        return "\n".join(text_parts)

    def generate_embedding(self, text: str) -> Optional[Any]:
        if not self.is_model_available():
            return None
        np = _get_np()
        if np is None:
            return None

        try:
            if not text or len(text.strip()) == 0:
                return None

            clean_text = text.strip()
            if len(clean_text) < 10:
                return None

            embedding = self._model.encode(
                [clean_text],
                convert_to_tensor=True,
                normalize_embeddings=True,
            )

            embedding_np = embedding.detach().cpu().numpy().flatten()

            logger.debug(
                f"Generated embedding for text length {len(clean_text)}: vector shape {embedding_np.shape}"
            )
            return embedding_np

        except Exception as e:
            logger.error(f"Error generating embedding: {e}")
            return None

    def compute_similarity(self, embedding1: Any, embedding2: Any) -> float:
        np = _get_np()
        if np is None or embedding1 is None or embedding2 is None:
            return 0.0

        try:
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
        embedding1 = self.generate_embedding(text1)
        embedding2 = self.generate_embedding(text2)

        if embedding1 is None or embedding2 is None:
            return 0.0

        return self.compute_similarity(embedding1, embedding2)

    def generate_email_embedding(self, email: Email) -> Optional[Any]:
        try:
            text_for_embedding = self.get_email_text_for_embedding(email)

            if not text_for_embedding:
                logger.debug(f"No text for embedding for email {email.id}")
                return None

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
    @staticmethod
    def create_tables() -> None:
        try:
            db.execute("""
                CREATE TABLE IF NOT EXISTS email_embeddings (
                    email_id INTEGER PRIMARY KEY,
                    account_id INTEGER NOT NULL,
                    embedding_blob BLOB,
                    text_hash TEXT NOT NULL,
                    model_version TEXT DEFAULT 'v1',
                    embedding_dim INTEGER DEFAULT 384,
                    similar_email_ids TEXT,
                    similarity_scores TEXT,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (email_id) REFERENCES emails(id) ON DELETE CASCADE,
                    FOREIGN KEY (account_id) REFERENCES accounts(id) ON DELETE CASCADE
                )
            """)

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
        email_id: int, account_id: int, embedding: Any, text_hash: str
    ) -> bool:
        np = _get_np()
        if np is None or embedding is None:
            return False
        try:
            embedding_bytes = embedding.astype(np.float32).tobytes()

            existing = db.fetchone(
                "SELECT email_id FROM email_embeddings WHERE email_id = ?", (email_id,)
            )

            now = datetime.now().isoformat()

            if existing:
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
        try:
            db.execute("DELETE FROM email_embeddings WHERE email_id = ?", (email_id,))
            logger.debug(f"Deleted embedding for email {email_id}")
            return True
        except Exception as e:
            logger.error(f"Failed to delete embedding for email {email_id}: {e}")
            return False

    @staticmethod
    def batch_get_embeddings(email_ids: List[int]) -> Dict[int, EmailEmbedding]:
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
        try:
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
        try:
            row = db.fetchone(
                "SELECT similar_email_ids, similarity_scores FROM email_embeddings WHERE email_id = ?",
                (email_id,),
            )
            if not row:
                return []

            similar_ids_str = row["similar_email_ids"]
            scores_str = row["similarity_scores"]

            if not similar_ids_str or not scores_str:
                return []

            similar_ids = json.loads(similar_ids_str)
            scores = json.loads(scores_str)

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
    def __init__(self, batch_size: int = 10) -> None:
        self._batch_size = batch_size
        self._running = False
        self._worker_thread: Optional[threading.Thread] = None
        self._embedding_service = EmbeddingService()
        self._pending_emails: List[Email] = []
        self._pending_lock = threading.Lock()

    def start(self) -> None:
        if self._running:
            logger.warning("Embedding worker already running")
            return

        self._running = True
        self._worker_thread = threading.Thread(target=self._worker_loop, daemon=True)
        self._worker_thread.start()
        logger.info("Embedding worker started")

    def stop(self) -> None:
        if not self._running:
            return

        logger.info("Stopping embedding worker")
        self._running = False

        if self._worker_thread:
            self._worker_thread.join(timeout=5.0)

        logger.info("Embedding worker stopped")

    def schedule_email_for_embedding(self, email: Email) -> None:
        with self._pending_lock:
            self._pending_emails.append(email)
            logger.debug(f"Scheduled email {email.id} for embedding")

    def _worker_loop(self) -> None:
        while self._running:
            try:
                with self._pending_lock:
                    if not self._pending_emails:
                        continue

                    batch = self._pending_emails[: self._batch_size]
                    self._pending_emails = self._pending_emails[self._batch_size :]

                self._process_batch(batch)

            except Exception as e:
                logger.error(f"Error in embedding worker loop: {e}")

            import time

            time.sleep(1)

    def _process_batch(self, emails: List[Email]) -> None:
        if not self._embedding_service.is_model_available():
            logger.debug("Semantic model not available, skipping batch")
            return

        for email in emails:
            try:
                import hashlib

                email_text = self._embedding_service.get_email_text_for_embedding(email)
                if not email_text:
                    continue

                text_hash = hashlib.md5(email_text.encode("utf-8")).hexdigest()

                existing = db.fetchone(
                    "SELECT email_id FROM email_embeddings WHERE email_id = ? AND text_hash = ?",
                    (email.id, text_hash),
                )

                if existing:
                    logger.debug(
                        f"Embedding already exists for email {email.id} with same hash"
                    )
                    continue

                embedding = self._embedding_service.generate_email_embedding(email)
                if embedding is None:
                    logger.debug(f"Failed to generate embedding for email {email.id}")
                    continue

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


embedding_service = EmbeddingService()
embedding_storage = EmbeddingStorage()
embedding_worker = EmbeddingWorker()

EmbeddingStorage.create_tables()
