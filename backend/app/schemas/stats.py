"""系统状态的接口模型。"""

from pydantic import BaseModel, Field


class StatsOut(BaseModel):
    """两库一致性探针。

    chunk 存在 MySQL、向量存在 FAISS，两边靠 id 对齐，
    所以条数必须相等；不等就说明有入库中途失败或者删除只清了一边。
    """

    documents: int
    chunks: int
    vectors: int
    synced: bool = Field(description="chunks == vectors 时为 true")
