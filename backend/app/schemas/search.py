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
    score: float = Field(
        description="hybrid 下是 RRF 融合分，vector 下是余弦相似度，bm25 下是 BM25 分；不同模式不可直接比较"
    )
    sources: list[str] = Field(
        default_factory=list, description="这条结果来自哪几路召回，如 ['vector', 'bm25']"
    )

    @field_serializer("score")
    def _round_score(self, value: float) -> float:
        """输出时保留 4 位小数，避免 JSON 里出现 0.5773600339889526 这种长串。"""
        return round(value, 4)


class SearchResult(BaseModel):
    """检索接口的整体响应。"""

    query: str
    mode: str
    total: int
    hits: list[SearchHit]
