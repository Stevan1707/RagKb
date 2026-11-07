"""查询侧入口：问题 → 片段。

两路召回 + RRF 融合：

    vector：encode_query → FAISS 找 recall_k 个 → 语义相近
    bm25  ：字面匹配 → 精确命中编号、人名、型号
    融合  ：RRF 只看名次，合并成 top_k

mode 可选 hybrid（默认）/ vector / bm25，方便对比与排查。

BM25 的语料来自 MySQL，不依赖 FAISS；入库或删除后调用 invalidate_bm25()，
下一次检索会自动重建，避免每次查询都重新分词。
"""

import asyncio
from collections import defaultdict
from dataclasses import dataclass, field

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.bm25 import BM25Index
from app.config import settings
from app.fusion import rrf
from app.ingest.embedder import encode_query
from app.models import Chunk, Document
from app.vectorstore import FaissStore

MODES = ("hybrid", "vector", "bm25")


@dataclass
class Hit:
    """一条检索结果，也是最终返回给前端的 source 结构。"""

    chunk_id: int
    doc_id: int
    doc_name: str
    page: int
    content: str
    score: float
    sources: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "chunk_id": self.chunk_id,
            "doc_id": self.doc_id,
            "doc_name": self.doc_name,
            "page": self.page,
            "content": self.content,
            "score": round(self.score, 4),
        }


# ---------------------------------------------------------------------------
# BM25 索引的缓存与失效
# ---------------------------------------------------------------------------

_bm25: BM25Index | None = None
_bm25_version = 0          # 每次入库/删除 +1
_bm25_built_version = -1   # 当前内存索引对应的版本
_bm25_lock = asyncio.Lock()


def invalidate_bm25() -> None:
    """入库或删除后调用：打版本号，等下次检索再重建。"""
    global _bm25_version
    _bm25_version += 1


async def _get_bm25(db: AsyncSession) -> BM25Index:
    global _bm25, _bm25_built_version
    if _bm25 is not None and _bm25_built_version == _bm25_version:
        return _bm25

    async with _bm25_lock:
        if _bm25 is not None and _bm25_built_version == _bm25_version:
            return _bm25

        rows = (await db.execute(select(Chunk.id, Chunk.content))).all()
        index = BM25Index(settings.bm25_k1, settings.bm25_b)
        await asyncio.to_thread(index.build, [(row[0], row[1]) for row in rows])
        _bm25 = index
        _bm25_built_version = _bm25_version
        return index


# ---------------------------------------------------------------------------
# 两路召回
# ---------------------------------------------------------------------------


def _vector_search_sync(query: str, k: int) -> list[tuple[int, float]]:
    vector = encode_query(query)
    store = FaissStore(settings.faiss_index_file, dim=vector.shape[1])
    ids, scores = store.search(vector, k)
    return list(zip(ids, scores))


async def _vector_candidates(query: str, k: int) -> list[tuple[int, float]]:
    return await asyncio.to_thread(_vector_search_sync, query, k)


async def _bm25_candidates(
    db: AsyncSession, query: str, k: int
) -> list[tuple[int, float]]:
    index = await _get_bm25(db)
    return await asyncio.to_thread(index.search, query, k)


async def _hydrate(db: AsyncSession, chunk_ids: list[int]) -> dict[int, dict]:
    """按 id 回 MySQL 取原文、页码、文档名。"""
    if not chunk_ids:
        return {}
    rows = (
        await db.execute(
            select(
                Chunk.id,
                Chunk.doc_id,
                Chunk.page,
                Chunk.content,
                Document.filename,
            )
            .join(Document, Document.id == Chunk.doc_id)
            .where(Chunk.id.in_(chunk_ids))
        )
    ).all()
    return {
        row[0]: {
            "chunk_id": row[0],
            "doc_id": row[1],
            "page": row[2],
            "content": row[3],
            "doc_name": row[4],
        }
        for row in rows
    }


# ---------------------------------------------------------------------------
# 对外入口
# ---------------------------------------------------------------------------


async def search(
    db: AsyncSession,
    query: str,
    *,
    mode: str | None = None,
    top_k: int | None = None,
    recall_k: int | None = None,
) -> list[Hit]:
    """检索并返回 top_k 条。"""
    query = (query or "").strip()
    if not query:
        return []

    mode = (mode or settings.retrieval_mode).lower()
    if mode not in MODES:
        raise ValueError(f"mode 只能是 {', '.join(MODES)}")

    top_k = top_k or settings.top_k
    recall_k = recall_k or settings.recall_k

    candidates: dict[str, list[tuple[int, float]]] = {}
    if mode in ("vector", "hybrid"):
        candidates["vector"] = await _vector_candidates(query, recall_k)
    if mode in ("bm25", "hybrid"):
        candidates["bm25"] = await _bm25_candidates(db, query, recall_k)

    if mode == "hybrid":
        rankings = {
            name: [chunk_id for chunk_id, _ in items]
            for name, items in candidates.items()
        }
        fused = rrf(rankings, settings.rrf_k)[:top_k]
        payload = await _hydrate(db, [item["chunk_id"] for item in fused])

        hits: list[Hit] = []
        for item in fused:
            row = payload.get(item["chunk_id"])
            if row is None:
                # 索引里有、数据库里没有：两库不同步，跳过脏数据
                continue
            hits.append(Hit(**row, score=item["score"], sources=item["sources"]))
        return hits

    # 单路：保留原始分数
    items = candidates[mode][:top_k]
    payload = await _hydrate(db, [chunk_id for chunk_id, _ in items])

    hits = []
    for chunk_id, score in items:
        row = payload.get(chunk_id)
        if row is None:
            continue
        hits.append(Hit(**row, score=score, sources=[mode]))
    return hits
