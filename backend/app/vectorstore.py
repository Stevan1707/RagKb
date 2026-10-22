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

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        faiss.write_index(self.index, str(self.path))
