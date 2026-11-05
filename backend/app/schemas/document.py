"""文档相关的接口模型。"""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class DocumentOut(BaseModel):
    """文档的响应形状。

    from_attributes=True 让它能直接吃 SQLAlchemy 的 ORM 对象：
    路由里 return doc 就行，不用再手写 to_dict。
    """

    model_config = ConfigDict(from_attributes=True)

    id: int
    filename: str
    status: str = Field(description="pending / processing / done / failed")
    chunk_count: int = Field(description="切出的块数")
    error: str | None = Field(default=None, description="失败原因")
    created_time: datetime


class DocumentListOut(BaseModel):
    """分页列表的响应。"""

    total: int
    page: int
    page_size: int
    items: list[DocumentOut]


class DocumentUpdate(BaseModel):
    """PATCH 的请求体：目前只允许改展示名。"""

    filename: str = Field(
        min_length=1, max_length=255, description="新的文件名（只改展示名，不动磁盘文件）"
    )


class ChunkOut(BaseModel):
    """单个文本块。"""

    id: int
    doc_id: int
    page: int
    seq: int
    length: int = Field(description="字符数，方便判断切块参数")
    content: str | None = Field(default=None, description="with_content=false 时不返回")


class ChunkListOut(BaseModel):
    """切块列表的响应。"""

    doc_id: int
    total: int
    page: int
    page_size: int
    items: list[ChunkOut]


class UploadResult(BaseModel):
    """上传成功的响应。"""

    doc_id: int
    filename: str
    status: str
    chunks: int = Field(description="本次切出的块数")
    vectors: int = Field(description="FAISS 索引里的总向量数，不是本次新增数")


class DeleteResult(BaseModel):
    """删除成功的响应。"""

    doc_id: int
    deleted: bool
    removed_vectors: int
    file_removed: bool
