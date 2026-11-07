"""入库总装：PDF → MySQL 文本块 + FAISS 向量。

顺序不能变：先写 MySQL 拿到自增 chunk.id，再用同一批 id 写 FAISS。

数据库会话来源有两种：
- 命令行调用：不传 db，函数自己开一个会话
- API 路由调用：传 FastAPI 注入的会话（Depends(get_database_session)），复用同一个事务

命令行用法：python -m app.ingest.pipeline <pdf路径>
"""

import asyncio
import sys
from pathlib import Path

from sqlalchemy import delete, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.db import AsyncSessionLocal, async_engine
from app.ingest import loader, splitter
from app.ingest.embedder import dimension, encode_passages
from app.models import Chunk, Document
from app.retrieval import invalidate_bm25
from app.vectorstore import FaissStore


async def ingest_file(src: str | Path, db: AsyncSession | None = None) -> dict:
    """入库一个 PDF，返回 {"doc_id", "chunks", "vectors"}。

    失败时抛异常，文档状态记为 failed。
    db 为空时自建会话（命令行）；API 路由把 Depends 注入的会话传进来即可。
    """
    src = Path(src).resolve()
    if not src.exists():
        raise FileNotFoundError(f"文件不存在：{src}")

    if db is not None:
        return await _ingest(src, db)

    async with AsyncSessionLocal() as session:
        return await _ingest(src, session)


async def _ingest(src: Path, db: AsyncSession) -> dict:
    # 先加载索引（同时确定模型维度），避免模型不可用时留下一条 processing 文档
    store = FaissStore(settings.faiss_index_file, dim=dimension())

    doc = Document(filename=src.name, path=str(src), status="processing")
    db.add(doc)
    await db.commit()
    doc_id = doc.id

    added_ids: list[int] = []

    try:
        loaded = loader.load_document(src)
        if not loaded.pages:
            raise ValueError("未抽取到任何文字（扫描版 PDF 或空文档）")

        blocks = splitter.split_pages(
            loaded.pages, settings.chunk_size, settings.chunk_overlap
        )
        if not blocks:
            raise ValueError("切块结果为空")

        chunks = [
            Chunk(doc_id=doc_id, page=b["page"], seq=b["seq"], content=b["text"])
            for b in blocks
        ]
        db.add_all(chunks)
        await db.commit()
        chunk_ids = [c.id for c in chunks]

        vectors = encode_passages([b["text"] for b in blocks])
        store.add(vectors, chunk_ids)
        added_ids = chunk_ids
        store.save()

        await db.execute(
            update(Document)
            .where(Document.id == doc_id)
            .values(
                status="done",
                chunk_count=len(chunk_ids),
                ocr_pages=loaded.ocr_pages,
                error=None,
            )
        )
        await db.commit()

        # 新块进来了，BM25 的内存索引作废，下次检索时重建
        invalidate_bm25()

        return {
            "doc_id": doc_id,
            "chunks": len(chunk_ids),
            "vectors": store.ntotal,
            "ocr_pages": loaded.ocr_pages,
        }

    except Exception as exc:
        # 回滚两处写入：MySQL 块 + FAISS 向量，并把失败原因留在文档行上。
        # 顺序和 try 里相反（先数据库再向量），且向量回滚单独兜底：
        # 索引不可写时也不能让文档状态卡在 processing。
        await db.rollback()
        if added_ids:
            try:
                store.remove(added_ids)
                store.save()
            except Exception:
                pass
        await db.execute(delete(Chunk).where(Chunk.doc_id == doc_id))
        await db.execute(
            update(Document)
            .where(Document.id == doc_id)
            .values(status="failed", error=str(exc)[:500])
        )
        await db.commit()
        raise


async def remove_document(
    doc_id: int,
    remove_file: bool = True,
    db: AsyncSession | None = None,
) -> dict | None:
    """删除一个文档：FAISS 向量 → MySQL 行 → 磁盘文件。

    返回 {"doc_id", "chunks", "vectors", "file_removed"}；文档不存在返回 None。
    db 为空时自建会话（API 直接调），也可以把当前会话传进来复用。

    顺序不能反：向量先删。数据库行一删，chunk.id 就再也查不出来，
    FAISS 里会留下永远搜不到、也删不掉的孤儿向量。
    """
    if db is not None:
        return await _remove(db, doc_id, remove_file)
    async with AsyncSessionLocal() as session:
        return await _remove(session, doc_id, remove_file)


async def _remove(db: AsyncSession, doc_id: int, remove_file: bool) -> dict | None:
    doc = await db.get(Document, doc_id)
    if doc is None:
        return None

    chunk_ids = list(
        (await db.execute(select(Chunk.id).where(Chunk.doc_id == doc_id)))
        .scalars()
        .all()
    )

    if chunk_ids:
        store = FaissStore(settings.faiss_index_file, dim=dimension())
        store.remove(chunk_ids)
        store.save()

    file_path = Path(doc.path)
    await db.delete(doc)  # chunk / citation 由外键 ON DELETE CASCADE 清掉
    await db.commit()

    # 块被删了，BM25 索引作废
    invalidate_bm25()

    # 只删上传目录里的文件；命令行直接入库的外部 PDF 不要动
    file_removed = False
    if remove_file:
        try:
            if file_path.exists() and settings.upload_path in file_path.parents:
                file_path.unlink()
                file_removed = True
        except OSError:
            pass

    return {
        "doc_id": doc_id,
        "chunks": len(chunk_ids),
        "vectors": len(chunk_ids),
        "file_removed": file_removed,
    }


async def _main() -> None:
    try:
        if len(sys.argv) != 2:
            print("用法：python -m app.ingest.pipeline <pdf路径>")
            raise SystemExit(1)
        result = await ingest_file(sys.argv[1])
        print(
            f"入库完成 doc_id={result['doc_id']} "
            f"chunks={result['chunks']} faiss_ntotal={result['vectors']}"
        )
    finally:
        # 必须在同一个事件循环里释放连接池，否则连接关闭回调会打到已关闭的 loop 上
        await async_engine.dispose()


if __name__ == "__main__":
    asyncio.run(_main())
