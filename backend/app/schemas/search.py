"""检索接口的响应模型。"""

from pydantic import BaseModel, ConfigDict, Field, field_serializer


class SearchHit(BaseModel):
    """一条命中结果，字段与 retrieval.Hit 一一对应。"""

    model_config = ConfigDict(from_attributes=True)

    chunk_id: int
    doc_id: int
    doc_name: str
    page: int
    content: str
    score: float = Field(description="余弦相似度，0~1，越大越相关")

    @field_serializer("score")
    def _round_score(self, value: float) -> float:
        """输出时保留 4 位小数，避免 JSON 里出现 0.5773600339889526 这种长串。"""
        return round(value, 4)


class SearchResult(BaseModel):
    """检索接口的整体响应。"""

    query: str
    total: int
    hits: list[SearchHit]
