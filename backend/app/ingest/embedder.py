"""把文本块编码成向量。

模型只加载一次（lru_cache），入库和检索必须用同一个模型，否则向量不在同一坐标系。
"""

from functools import lru_cache

import numpy as np
from sentence_transformers import SentenceTransformer
# 使用sentence-transformers模型来将文本编码成向量
from app.config import settings

# BGE 官方建议：查询侧加指令前缀，文档侧不加
QUERY_INSTRUCTION = "为这个句子生成表示以用于检索相关文章："


@lru_cache(maxsize=1)
def get_model() -> SentenceTransformer:
    # 本地模型目录优先，避免每次启动都依赖 HuggingFace 网络
    return SentenceTransformer(settings.embed_model_ref)


def dimension() -> int:
    return get_model().get_embedding_dimension()


def encode_passages(texts: list[str]) -> np.ndarray:
    """文档块向量，形状 (N, dim)，已 L2 归一化。"""
    vectors = get_model().encode(
        texts,
        batch_size=32,
        normalize_embeddings=True,
        convert_to_numpy=True,
        show_progress_bar=False,
    )
    return np.asarray(vectors, dtype=np.float32)


def encode_query(text: str) -> np.ndarray:
    """查询向量，形状 (1, dim)。"""
    vector = get_model().encode(
        [QUERY_INSTRUCTION + text],
        normalize_embeddings=True,
        convert_to_numpy=True,
        show_progress_bar=False,
    )
    return np.asarray(vector, dtype=np.float32)
