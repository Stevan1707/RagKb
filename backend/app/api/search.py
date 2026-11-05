"""只检索不生成：给调参、验收、排查召回问题用。

示例：
    GET /api/search?q=公民可以自由表达意见吗&top_k=5

它和 /api/chat 的区别：这里只返回检索到的原文片段，不调用大模型、不花钱、
不落库。调切块参数、验证某段内容能不能搜到时，都用这个接口。
"""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.db import get_database_session
from app.retrieval import search as retrieve
from app.schemas.search import SearchHit, SearchResult

router = APIRouter(tags=["search"])


@router.get("/search", response_model=SearchResult)
async def search(
    q: str = Query(..., min_length=1, max_length=500, description="查询语句"),
    top_k: int = Query(settings.top_k, ge=1, le=50, description="返回条数"),
    db: AsyncSession = Depends(get_database_session),
) -> SearchResult:
    """按语义相似度返回最相关的片段，按分数从高到低。"""
    hits = await retrieve(db, q, top_k=top_k)
    return SearchResult(
        query=q,
        total=len(hits),
        hits=[SearchHit.model_validate(hit) for hit in hits],
    )
