from __future__ import annotations

try:
    import jieba

    JIEBA_AVAILABLE = True
except ImportError:
    JIEBA_AVAILABLE = False


class Tokenizer:
    """中文分词器"""

    @staticmethod
    def tokenize(text: str) -> list[str]:
        """将文本分词"""
        if not text:
            return []

        if JIEBA_AVAILABLE:
            # 使用 jieba 分词
            return list(jieba.cut(text))
        else:
            # 简单按空格和标点分词
            import re

            # 按空格、标点分割
            tokens = re.split(r"[\s,;.!?，。！？；：]+", text)
            return [t for t in tokens if t.strip()]

    @staticmethod
    def tokenize_for_search(query: str) -> list[str]:
        """搜索查询分词"""
        return Tokenizer.tokenize(query)
