"""只检索不生成：给调参、验收、排查召回问题用。

示例：
    GET /api/search?q=公民可以自由表达意见吗&top_k=5
    GET /api/search?q=宪法第三十五条&mode=bm25
    GET /api/search?q=宪法第三十五条&mode=hybrid

它和 /api/chat 的区别：这里只返回检索到的原文片段，不调用大模型、不花钱、
不落库。调切块参数、验证某段内容能不能搜到时，都用这个接口。
"""

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.db import get_database_session
from app.retrieval import MODES
from app.retrieval import search as retrieve
from app.schemas.search import SearchHit, SearchResult

router = APIRouter(tags=["search"])


@router.get("/search", response_model=SearchResult)
async def search(
    q: str = Query(..., min_length=1, max_length=500, description="查询语句"),
    top_k: int = Query(settings.top_k, ge=1, le=50, description="返回条数"),
    mode: str = Query(
        settings.retrieval_mode,
        description="hybrid=向量+BM25 融合（默认），vector=只看向量，bm25=只看关键词",
    ),
    db: AsyncSession = Depends(get_database_session),
) -> SearchResult:
    """按相关度返回最相关的片段，按分数从高到低。"""
    mode = mode.lower()
    if mode not in MODES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"mode 只能是 {', '.join(MODES)}",
        )

    hits = await retrieve(db, q, mode=mode, top_k=top_k)
    return SearchResult(
        query=q,
        mode=mode,
        total=len(hits),
        hits=[SearchHit.model_validate(hit) for hit in hits],
    )
