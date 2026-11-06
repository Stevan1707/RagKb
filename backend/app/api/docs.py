"""文档管理接口：上传（增）→ 列表/详情（查）→ 改名（改）→ 删除（删）。

另外多给一个「查看切块」的接口：调 CHUNK_SIZE 时靠它判断切得好不好。

路由一览：
    POST   /docs/upload            上传文档（pdf/txt/md/docx），同步完成入库
    GET    /docs                   分页列表，可按状态、文件名筛选
    GET    /docs/{doc_id}          单个文档详情
    PATCH  /docs/{doc_id}          改名（只改展示名，不动磁盘文件）
    DELETE /docs/{doc_id}          删除：FAISS 向量 + MySQL 行 + 磁盘文件
    GET    /docs/{doc_id}/chunks   查看切块结果

注意 /docs/{doc_id} 必须定义在 /docs/upload 之后，否则 "upload" 会被当成 doc_id。
"""

from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.db import get_database_session
from app.ingest.loader import SUPPORTED_EXTENSIONS
from app.ingest.pipeline import ingest_file, remove_document
from app.models import Chunk, Document
from app.schemas.document import (
    ChunkListOut,
    DeleteResult,
    DocumentListOut,
    DocumentOut,
    DocumentUpdate,
    UploadResult,
)

router = APIRouter(prefix="/docs", tags=["docs"])

MAX_UPLOAD_BYTES = 50 * 1024 * 1024
PDF_MAGIC = b"%PDF"
ZIP_MAGIC = b"PK\x03\x04"  # docx 本质是 zip，用它挡掉改名的假文件
PNG_MAGIC = b"\x89PNG"
JPEG_MAGIC = b"\xff\xd8\xff"
DOC_STATUSES = ("pending", "processing", "done", "failed")


# ---------------------------------------------------------------------------
# 小工具
# ---------------------------------------------------------------------------


def _unique_path(directory: Path, filename: str) -> Path:
    """同名文件不覆盖，依次尝试 name.pdf、name_1.pdf、name_2.pdf"""
    dest = directory / filename
    stem, suffix = dest.stem, dest.suffix
    i = 1
    while dest.exists():
        dest = directory / f"{stem}_{i}{suffix}"
        i += 1
    return dest


def _chunk_to_dict(chunk: Chunk) -> dict:
    return {
        "id": chunk.id,
        "doc_id": chunk.doc_id,
        "page": chunk.page,
        "seq": chunk.seq,
        "length": len(chunk.content),
        "content": chunk.content,
    }


async def _get_doc_or_404(db: AsyncSession, doc_id: int) -> Document:
    doc = await db.get(Document, doc_id)
    if doc is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=f"文档不存在：{doc_id}"
        )
    return doc


# ---------------------------------------------------------------------------
# 增：上传
# ---------------------------------------------------------------------------


@router.post(
    "/upload", status_code=status.HTTP_201_CREATED, response_model=UploadResult
)
async def upload_document(
    file: UploadFile,
    db: AsyncSession = Depends(get_database_session),
) -> UploadResult:
    """上传文档并同步完成入库，返回 doc_id、块数与索引总向量数。

    支持 pdf / txt / md / docx；按扩展名交给 loader.load_document 分派。
    现在是同步的：请求会等到解析、切块、向量化全部跑完才返回。
    """
    filename = Path(file.filename or "").name  # 只取文件名，丢掉客户端传来的目录部分
    suffix = Path(filename).suffix.lower()
    if suffix not in SUPPORTED_EXTENSIONS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"只支持 {', '.join(sorted(SUPPORTED_EXTENSIONS))} 文件",
        )

    data = await file.read()
    if not data:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="文件为空"
        )
    if len(data) > MAX_UPLOAD_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"文件超过 {MAX_UPLOAD_BYTES // 1024 // 1024}MB",
        )

    # 只给二进制格式做魔数校验：txt / md 是纯文本，没有固定文件头
    if suffix == ".pdf" and not data.startswith(PDF_MAGIC):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="不是有效的 PDF 文件"
        )
    if suffix == ".docx" and not data.startswith(ZIP_MAGIC):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="不是有效的 Word 文档"
        )
    if suffix == ".png" and not data.startswith(PNG_MAGIC):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="不是有效的 PNG 图片"
        )
    if suffix in (".jpg", ".jpeg") and not data.startswith(JPEG_MAGIC):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="不是有效的 JPEG 图片"
        )

    upload_dir = settings.upload_path
    upload_dir.mkdir(parents=True, exist_ok=True)
    dest = _unique_path(upload_dir, filename)
    dest.write_bytes(data)

    try:
        result = await ingest_file(dest, db)
    except Exception as exc:
        # 管线内部已经把文档标成 failed，并回滚了块与向量；这里只负责翻译成 HTTP 错误。
        # 顺便把 doc_id 带回去，方便前端在列表里看到这条失败记录。
        failed = (
            await db.execute(
                select(Document)
                .where(Document.path == str(dest.resolve()))
                .order_by(Document.id.desc())
            )
        ).scalars().first()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "message": "入库失败",
                "doc_id": failed.id if failed else None,
                "reason": str(exc),
            },
        ) from exc

    return UploadResult(
        doc_id=result["doc_id"],
        filename=dest.name,
        status="done",
        chunks=result["chunks"],
        vectors=result["vectors"],  # 索引里的总向量数，不是本次新增数
        ocr_pages=result["ocr_pages"],
    )


# ---------------------------------------------------------------------------
# 查：列表 / 详情 / 切块
# ---------------------------------------------------------------------------


@router.get("", response_model=DocumentListOut)
async def list_documents(
    doc_status: str | None = Query(
        None,
        alias="status",
        description="按状态筛选：pending / processing / done / failed",
    ),
    keyword: str | None = Query(None, max_length=100, description="按文件名模糊搜索"),
    page: int = Query(1, ge=1, description="页码，从 1 开始"),
    page_size: int = Query(20, ge=1, le=100, description="每页条数"),
    db: AsyncSession = Depends(get_database_session),
) -> DocumentListOut:
    """文档列表，按 id 倒序（最新上传的在前）。"""
    if doc_status is not None and doc_status not in DOC_STATUSES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"status 只能是 {DOC_STATUSES} 之一",
        )

    base = select(Document)
    if doc_status:
        base = base.where(Document.status == doc_status)
    if keyword:
        base = base.where(Document.filename.contains(keyword.strip()))

    total = (
        await db.execute(select(func.count()).select_from(base.subquery()))
    ).scalar_one()

    rows = (
        (
            await db.execute(
                base.order_by(Document.id.desc())
                .offset((page - 1) * page_size)
                .limit(page_size)
            )
        )
        .scalars()
        .all()
    )

    return DocumentListOut(
        total=total,
        page=page,
        page_size=page_size,
        items=[DocumentOut.model_validate(doc) for doc in rows],
    )


@router.get("/{doc_id}", response_model=DocumentOut)
async def get_document(
    doc_id: int,
    db: AsyncSession = Depends(get_database_session),
) -> DocumentOut:
    """单个文档详情（前端轮询处理状态也用这个）。"""
    return await _get_doc_or_404(db, doc_id)


@router.get("/{doc_id}/chunks", response_model=ChunkListOut)
async def list_document_chunks(
    doc_id: int,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    with_content: bool = Query(True, description="false 时只返回元信息，不返回正文"),
    db: AsyncSession = Depends(get_database_session),
) -> ChunkListOut:
    """查看某个文档切出来的块，按 seq 升序。

    调 CHUNK_SIZE / CHUNK_OVERLAP 时，用它看块边界切得是否合理。
    """
    await _get_doc_or_404(db, doc_id)

    total = (
        await db.execute(
            select(func.count()).select_from(Chunk).where(Chunk.doc_id == doc_id)
        )
    ).scalar_one()

    rows = (
        (
            await db.execute(
                select(Chunk)
                .where(Chunk.doc_id == doc_id)
                .order_by(Chunk.seq)
                .offset((page - 1) * page_size)
                .limit(page_size)
            )
        )
        .scalars()
        .all()
    )

    items = []
    for chunk in rows:
        item = _chunk_to_dict(chunk)
        if not with_content:
            item.pop("content")
        items.append(item)

    return ChunkListOut(
        doc_id=doc_id,
        total=total,
        page=page,
        page_size=page_size,
        items=items,
    )


# ---------------------------------------------------------------------------
# 改：改名
# ---------------------------------------------------------------------------


@router.patch("/{doc_id}", response_model=DocumentOut)
async def update_document(
    doc_id: int,
    payload: DocumentUpdate,
    db: AsyncSession = Depends(get_database_session),
) -> DocumentOut:
    """改文件名（展示名）。

    只改数据库里的 filename，磁盘上的 path 不变，所以不会影响已入库的块和向量。
    想改切块参数只能删掉重新上传——旧块是按旧参数切的。
    """
    doc = await _get_doc_or_404(db, doc_id)

    new_name = Path(payload.filename).name.strip()
    if not new_name or new_name in (".", ".."):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="文件名不合法"
        )

    doc.filename = new_name
    await db.commit()
    return doc


# ---------------------------------------------------------------------------
# 删：两个库一起清
# ---------------------------------------------------------------------------


@router.delete("/{doc_id}", response_model=DeleteResult)
async def delete_document(
    doc_id: int,
    remove_file: bool = Query(True, description="是否同时删除磁盘上的原始 PDF"),
) -> DeleteResult:
    """删除文档：向量、数据行、磁盘文件一起清。

    具体怎么删（顺序、回滚、孤儿向量）都在 pipeline.remove_document() 里，
    接口层只负责翻译结果：删掉了返回统计，没这条记录返回 404。
    """
    try:
        result = await remove_document(doc_id, remove_file=remove_file)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"删除失败，文档未删除：{exc}",
        ) from exc

    if result is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=f"文档不存在：{doc_id}"
        )

    return DeleteResult(
        doc_id=doc_id,
        deleted=True,
        removed_vectors=result["vectors"],
        file_removed=result["file_removed"],
    )
