"""FAISS 索引读写封装：id 与 chunk.id 一一对应。

用 IndexIDMap2 包住 IndexFlatIP，这样能指定每条向量的 id；
向量已在 embedder 中做过 L2 归一化，因此内积即余弦相似度。
"""

from pathlib import Path

import faiss
import numpy as np


class FaissStore:
    def __init__(self, path: str | Path, dim: int):
        self.path = Path(path)
        self.dim = dim
        self.index = self._load()

    def _load(self):
        if self.path.exists():
            index = faiss.read_index(str(self.path))
            if index.d != self.dim:
                raise ValueError(
                    f"索引维度 {index.d} 与当前模型维度 {self.dim} 不一致，"
                    f"更换过 embedding 模型时必须重建索引"
                )
            return index
        return faiss.IndexIDMap2(faiss.IndexFlatIP(self.dim))

    @property
    def ntotal(self) -> int:
        return self.index.ntotal

    def add(self, vectors: np.ndarray, ids: list[int]) -> None:
        if len(ids) != len(vectors):
            raise ValueError(f"向量数 {len(vectors)} 与 id 数 {len(ids)} 不一致")
        self.index.add_with_ids(vectors, np.asarray(ids, dtype=np.int64))

    def remove(self, ids: list[int]) -> None:
        if not ids:
            return
        self.index.remove_ids(np.asarray(ids, dtype=np.int64))

    def search(self, vector: np.ndarray, k: int) -> tuple[list[int], list[float]]:
        """在索引里找最相近的 k 条，返回 (chunk_ids, scores)。

        - vector 形状必须是 (1, dim)，由 encode_query() 生成
        - score 是内积；因为入库和查询都做过 L2 归一化，内积 = 余弦相似度，
          取值 0～1，越大越像
        - 索引为空、k <= 0 时返回两个空列表，调用方不用特判
        """
        if self.ntotal == 0 or k <= 0:
            return [], []

        k = min(k, self.ntotal)
        scores, ids = self.index.search(np.asarray(vector, dtype=np.float32), k)

        # FAISS 在候选不足时用 -1 填充，过滤掉
        pairs = [(int(i), float(s)) for i, s in zip(ids[0], scores[0]) if i != -1]
        return [p[0] for p in pairs], [p[1] for p in pairs]

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        faiss.write_index(self.index, str(self.path))


def index_ntotal(path: str | Path) -> int:
    """只读索引里的向量条数。

    单独写成函数，是为了不加载 embedding 模型：/api/stats 会被前端频繁轮询，
    走 FaissStore + dimension() 每次都初始化一次 bge 模型，代价太大。
    索引文件不存在时返回 0（还没入过库的正常情况）。
    """
    path = Path(path)
    if not path.exists():
        return 0
    return faiss.read_index(str(path)).ntotal
