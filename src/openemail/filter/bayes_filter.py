from __future__ import annotations

import logging
import math
from collections import Counter
from dataclasses import dataclass, field
from typing import Optional

from openemail.filter.tokenizer import Tokenizer
from openemail.models.email import Email
from openemail.storage.database import db

logger = logging.getLogger(__name__)

SPAM_THRESHOLD = 0.85
HAM_THRESHOLD = 0.15
MIN_TRAINING_SAMPLES = 10


@dataclass
class SpamResult:
    is_spam: bool = False
    is_ham: bool = False
    is_unsure: bool = True
    probability: float = 0.5
    tokens_used: int = 0
    top_spam_tokens: list = field(default_factory=list)
    top_ham_tokens: list = field(default_factory=list)


class BayesianSpamFilter:
    """贝叶斯垃圾邮件分类器"""

    _instance: Optional[BayesianSpamFilter] = None

    def __new__(cls) -> BayesianSpamFilter:
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._loaded = False
            cls._instance._spam_word_probs: dict[str, float] = {}
            cls._instance._ham_word_probs: dict[str, float] = {}
            cls._instance._spam_count = 0
            cls._instance._ham_count = 0
        return cls._instance

    def ensure_loaded(self) -> None:
        if not self._loaded:
            self._load_from_db()

    def classify(self, email: Email) -> SpamResult:
        self.ensure_loaded()

        if (
            self._spam_count < MIN_TRAINING_SAMPLES
            or self._ham_count < MIN_TRAINING_SAMPLES
        ):
            return SpamResult(is_unsure=True, probability=0.5)

        text = f"{email.subject} {email.preview_text}"
        tokens = Tokenizer.tokenize(text)

        if not tokens:
            return SpamResult(is_unsure=True, probability=0.5)

        probs = []
        for token in set(tokens):
            sp = self._spam_word_probs.get(token, 0.5)
            hp = self._ham_word_probs.get(token, 0.5)
            ratio = sp / (sp + hp) if (sp + hp) > 0 else 0.5
            ratio = max(0.01, min(0.99, ratio))
            probs.append((token, ratio))

        probs.sort(key=lambda x: abs(x[1] - 0.5), reverse=True)
        significant = probs[: min(len(probs), 150)]

        if not significant:
            return SpamResult(is_unsure=True, probability=0.5)

        log_spam = sum(math.log(p) for _, p in significant)
        log_ham = sum(math.log(1 - p) for _, p in significant)

        try:
            spam_prob = 1.0 / (1.0 + math.exp(log_ham - log_spam))
        except OverflowError:
            spam_prob = 1.0 if log_spam > log_ham else 0.0

        top_spam = sorted(significant, key=lambda x: x[1], reverse=True)[:5]
        top_ham = sorted(significant, key=lambda x: x[1])[:5]

        return SpamResult(
            is_spam=spam_prob >= SPAM_THRESHOLD,
            is_ham=spam_prob <= HAM_THRESHOLD,
            is_unsure=HAM_THRESHOLD < spam_prob < SPAM_THRESHOLD,
            probability=spam_prob,
            tokens_used=len(significant),
            top_spam_tokens=[(t, round(p, 3)) for t, p in top_spam],
            top_ham_tokens=[(t, round(p, 3)) for t, p in top_ham],
        )

    def train_spam(self, email: Email) -> None:
        self._train(email, is_spam=True)

    def train_ham(self, email: Email) -> None:
        self._train(email, is_spam=False)

    def _train(self, email: Email, is_spam: bool) -> None:
        text = f"{email.subject} {email.preview_text}"
        tokens = Tokenizer.tokenize(text)
        token_counts = Counter(tokens)

        _label = "spam" if is_spam else "ham"
        for token, count in token_counts.items():
            row = db.fetchone(
                "SELECT spam_count, ham_count FROM bayes_tokens WHERE token = ?",
                (token,),
            )
            if row:
                sc = row["spam_count"] + (count if is_spam else 0)
                hc = row["ham_count"] + (count if not is_spam else 0)
                db.update(
                    "bayes_tokens",
                    {"spam_count": sc, "ham_count": hc},
                    "token = ?",
                    (token,),
                )
            else:
                db.insert(
                    "bayes_tokens",
                    {
                        "token": token,
                        "spam_count": count if is_spam else 0,
                        "ham_count": count if not is_spam else 0,
                    },
                )

        if is_spam:
            self._spam_count += 1
        else:
            self._ham_count += 1

        self._update_meta()
        self._loaded = False

    def untrain(self, email: Email, was_spam: bool) -> None:
        text = f"{email.subject} {email.preview_text}"
        tokens = Tokenizer.tokenize(text)
        token_counts = Counter(tokens)

        for token, count in token_counts.items():
            row = db.fetchone(
                "SELECT spam_count, ham_count FROM bayes_tokens WHERE token = ?",
                (token,),
            )
            if row:
                sc = max(0, row["spam_count"] - (count if was_spam else 0))
                hc = max(0, row["ham_count"] - (count if not was_spam else 0))
                if sc == 0 and hc == 0:
                    db.delete("bayes_tokens", "token = ?", (token,))
                else:
                    db.update(
                        "bayes_tokens",
                        {"spam_count": sc, "ham_count": hc},
                        "token = ?",
                        (token,),
                    )

        if was_spam:
            self._spam_count = max(0, self._spam_count - 1)
        else:
            self._ham_count = max(0, self._ham_count - 1)

        self._update_meta()
        self._loaded = False

    def _load_from_db(self) -> None:
        rows = db.fetchall("SELECT token, spam_count, ham_count FROM bayes_tokens")
        total_spam = 0
        total_ham = 0

        for row in rows:
            token = row["token"]
            sc = row["spam_count"]
            hc = row["ham_count"]
            total_spam += sc
            total_ham += hc

            if sc + hc > 0:
                self._spam_word_probs[token] = sc / max(1, total_spam)
                self._ham_word_probs[token] = hc / max(1, total_ham)

        meta = db.fetchone("SELECT spam_count, ham_count FROM bayes_meta WHERE id = 1")
        if meta:
            self._spam_count = meta["spam_count"]
            self._ham_count = meta["ham_count"]

        self._loaded = True

    def _update_meta(self) -> None:
        existing = db.fetchone("SELECT id FROM bayes_meta WHERE id = 1")
        data = {"spam_count": self._spam_count, "ham_count": self._ham_count}
        if existing:
            db.update("bayes_meta", data, "id = 1")
        else:
            data["id"] = 1
            db.insert("bayes_meta", data)

    def get_stats(self) -> dict:
        self.ensure_loaded()
        return {
            "spam_count": self._spam_count,
            "ham_count": self._ham_count,
            "token_count": len(self._spam_word_probs),
            "is_ready": self._spam_count >= MIN_TRAINING_SAMPLES
            and self._ham_count >= MIN_TRAINING_SAMPLES,
        }


bayes_filter = BayesianSpamFilter()
