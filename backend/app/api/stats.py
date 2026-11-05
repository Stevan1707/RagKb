"""系统状态：两库是否同步。

为什么专门做一个接口：chunk 写在 MySQL、向量写在 FAISS，两边靠 id 对齐。
只要有入库中途失败、或者删除只清了一边，就会出现「块数 ≠ 向量数」。
前端拿它当徽标，开发时拿它当体温计。
"""

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.db import get_database_session
from app.models import Chunk, Document
from app.schemas.stats import StatsOut
from app.vectorstore import index_ntotal

router = APIRouter(tags=["stats"])


@router.get("/stats", response_model=StatsOut)
async def get_stats(db: AsyncSession = Depends(get_database_session)) -> StatsOut:
    """返回文档数、块数、向量数，以及两个库是否同步。"""
    documents = (
        await db.execute(select(func.count()).select_from(Document))
    ).scalar_one()
    chunks = (await db.execute(select(func.count()).select_from(Chunk))).scalar_one()
    vectors = index_ntotal(settings.faiss_index_file)

    return StatsOut(
        documents=documents,
        chunks=chunks,
        vectors=vectors,
        synced=chunks == vectors,
    )
