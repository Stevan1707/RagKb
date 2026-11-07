"""问答接口的请求 / 响应模型。"""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_serializer


class ChatRequest(BaseModel):
    """提问请求。"""

    question: str = Field(min_length=1, max_length=500, description="你的问题")
    conversation_id: int | None = Field(
        default=None, description="不传则新建会话；传了就在该会话里继续"
    )
    top_k: int = Field(default=3, ge=1, le=10, description="喂给模型的资料条数")
    mode: str | None = Field(
        default=None,
        description="检索模式：hybrid（默认）/ vector / bm25，不传则用配置里的默认值",
    )


class SourceOut(BaseModel):
    """答案引用的来源，rank 对应正文里的 [1][2]。"""

    rank: int
    chunk_id: int
    doc_id: int
    doc_name: str
    page: int
    content: str
    score: float

    @field_serializer("score")
    def _round_score(self, value: float) -> float:
        return round(value, 4)


class ChatResponse(BaseModel):
    """一次问答的结果。"""

    conversation_id: int
    message_id: int
    answer: str
    sources: list[SourceOut]


class ConversationOut(BaseModel):
    """会话概要，用于侧栏列表。"""

    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    created_time: datetime
    updated_time: datetime


class ConversationListOut(BaseModel):
    items: list[ConversationOut]


class MessageOut(BaseModel):
    """一条历史消息，assistant 的消息会带引用。"""

    model_config = ConfigDict(from_attributes=True)

    id: int
    role: str
    content: str
    status: str
    created_time: datetime
    sources: list[SourceOut] = Field(default_factory=list)


class ConversationDetailOut(BaseModel):
    """会话详情：会话信息 + 按时间顺序的全部消息。"""

    conversation: ConversationOut
    messages: list[MessageOut]
