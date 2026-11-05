"""查询侧入口：问题 → 片段。

这一步只做「向量召回」一条路：
    问题文字 → encode_query → (1, 512) 向量
    → FAISS 找最相近的 top_k 个 chunk.id
    → 按这些 id 回 MySQL 取原文、页码、文档名

为什么非要回表：FAISS 里只有向量，没有文字。文字的唯一真相存放在 MySQL，
这样即使索引重建、向量删改，也不会出现「两份文字对不上」的问题。
"""

import asyncio
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.ingest.embedder import encode_query
from app.models import Chunk, Document
from app.vectorstore import FaissStore


@dataclass
class Hit:
    """一条检索结果，也是最终返回给前端的 source 结构。"""

    chunk_id: int
    doc_id: int
    doc_name: str
    page: int
    content: str
    score: float

    def to_dict(self) -> dict:
        return {
            "chunk_id": self.chunk_id,
            "doc_id": self.doc_id,
            "doc_name": self.doc_name,
            "page": self.page,
            "content": self.content,
            "score": round(self.score, 4),
        }


async def search(
    db: AsyncSession,
    query: str,
    top_k: int | None = None,
) -> list[Hit]:
    """按语义相似度取回最相关的片段，按相关度从高到低。"""
    query = (query or "").strip()
    if not query:
        return []

    top_k = top_k or settings.top_k

    # 编码是 CPU 密集操作，丢到线程池，别堵住事件循环
    vector = await asyncio.to_thread(encode_query, query)

    def _vector_search() -> tuple[list[int], list[float]]:
        # FaissStore 每次都会从磁盘读一份索引；维度直接用向量的列数，省一次模型调用
        store = FaissStore(settings.faiss_index_file, dim=vector.shape[1])
        return store.search(vector, top_k)

    ids, scores = await asyncio.to_thread(_vector_search)
    if not ids:
        return []

    # 回表：一次 IN 查询取回所有原文
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
            .where(Chunk.id.in_(ids))
        )
    ).all()
    by_id = {row[0]: row for row in rows}

    # 按 FAISS 的排名组装，不能用 IN 查询返回的顺序
    hits: list[Hit] = []
    for chunk_id, score in zip(ids, scores):
        row = by_id.get(chunk_id)
        if row is None:
            # 索引里有、数据库里没有：两库不同步（入库中途失败或删除不干净）
            # 直接跳过，别让检索因为一条脏数据整体失败
            continue
        hits.append(
            Hit(
                chunk_id=row[0],
                doc_id=row[1],
                page=row[2],
                content=row[3],
                doc_name=row[4],
                score=score,
            )
        )
    return hits
