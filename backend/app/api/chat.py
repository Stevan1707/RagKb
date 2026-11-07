"""问答接口：检索 → 拼 prompt → 调大模型 → 落库。

一次请求做五件事：
1. 找到或新建会话
2. 存下用户问题
3. 检索最相关的几段资料
4. 把资料和问题交给大模型，拿到完整回答
5. 存 assistant 消息 + 引用关系，返回答案

不做流式：等模型写完一次性返回。这样不用处理事件流和断连，
代价是页面要等几秒（本机 Ollama 实测 5 秒左右）。
"""

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.db import get_database_session
from app.generator import LLMError, build_messages, complete
from app.models import Chunk, Citation, Conversation, Document, Message
from app.retrieval import MODES
from app.retrieval import search as retrieve
from app.schemas.chat import (
    ChatRequest,
    ChatResponse,
    ConversationDetailOut,
    ConversationListOut,
    ConversationOut,
    MessageOut,
    SourceOut,
)

router = APIRouter(tags=["chat"])

# 没有检索到资料时的固定回答：不调模型，避免它凭常识编
EMPTY_ANSWER = "知识库里没有检索到与这个问题相关的内容。换个说法，或者先上传相关文档试试。"


async def _load_history(
    db: AsyncSession, conversation_id: int, turns: int
) -> list[dict]:
    """取该会话最近几轮对话，用来让多轮提问有上下文。

    内容截断到 400 字：历史太长会把 4096 的上下文塞满，
    导致模型看不到本轮的资料。
    """
    if turns <= 0:
        return []
    rows = (
        (
            await db.execute(
                select(Message)
                .where(Message.conversation_id == conversation_id)
                .order_by(Message.id.desc())
                .limit(turns * 2)
            )
        )
        .scalars()
        .all()
    )
    return [
        {"role": m.role, "content": m.content[:400]} for m in reversed(rows)
    ]


@router.post("/chat", response_model=ChatResponse)
async def chat(
    payload: ChatRequest,
    db: AsyncSession = Depends(get_database_session),
) -> ChatResponse:
    """问一个问题，返回带引用的答案。"""
    # 0. 校验检索模式（放在写库之前，坏请求不留垃圾数据）
    mode = (payload.mode or "").lower() or None
    if mode is not None and mode not in MODES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"mode 只能是 {', '.join(MODES)}",
        )

    # 1. 会话
    if payload.conversation_id is not None:
        conversation = await db.get(Conversation, payload.conversation_id)
        if conversation is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"会话不存在：{payload.conversation_id}",
            )
        # 要在存本次问题之前取历史，否则会把自己也算进去
        history = await _load_history(
            db, conversation.id, settings.llm_history_turns
        )
    else:
        conversation = Conversation(title=payload.question[:40])
        db.add(conversation)
        await db.flush()
        history = []

    # 2. 存用户问题
    db.add(
        Message(
            conversation_id=conversation.id,
            role="user",
            content=payload.question,
            status="done",
        )
    )
    await db.commit()

    # 3. 检索
    hits = await retrieve(db, payload.question, mode=mode, top_k=payload.top_k)

    # 4. 生成（没检索到就不调模型）
    if hits:
        messages = build_messages(payload.question, hits, history)
        try:
            answer = await complete(messages)
        except LLMError as exc:
            # 用户问题已经落库了，这里只把错误翻译成 503
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=f"回答生成失败：{exc}",
            ) from exc
    else:
        answer = EMPTY_ANSWER

    # 5. 存回答 + 引用
    assistant = Message(
        conversation_id=conversation.id,
        role="assistant",
        content=answer,
        status="done",
    )
    db.add(assistant)
    await db.flush()  # 先拿到 assistant.id，引用要用

    for rank, hit in enumerate(hits, start=1):
        db.add(
            Citation(
                message_id=assistant.id,
                chunk_id=hit.chunk_id,
                rank_no=rank,
                score=hit.score,
            )
        )

    conversation.updated_time = datetime.now()
    await db.commit()

    return ChatResponse(
        conversation_id=conversation.id,
        message_id=assistant.id,
        answer=answer,
        sources=[
            SourceOut(rank=rank, **hit.to_dict())
            for rank, hit in enumerate(hits, start=1)
        ],
    )


# ---------------------------------------------------------------------------
# 读：会话列表 / 会话详情
# ---------------------------------------------------------------------------


@router.get("/conversations", response_model=ConversationListOut)
async def list_conversations(
    limit: int = Query(50, ge=1, le=200, description="最多返回多少个会话"),
    db: AsyncSession = Depends(get_database_session),
) -> ConversationListOut:
    """会话列表，最近更新的排在前面（前端侧栏用）。"""
    rows = (
        (
            await db.execute(
                select(Conversation)
                .order_by(Conversation.updated_time.desc())
                .limit(limit)
            )
        )
        .scalars()
        .all()
    )
    return ConversationListOut(
        items=[ConversationOut.model_validate(row) for row in rows]
    )


@router.get("/conversations/{conversation_id}", response_model=ConversationDetailOut)
async def get_conversation(
    conversation_id: int,
    db: AsyncSession = Depends(get_database_session),
) -> ConversationDetailOut:
    """会话详情：按时间顺序返回全部消息，assistant 的消息带引用。

    引用要从 citation 表 join 回 chunk 和 document，才能给出
    「哪个文件、第几页、原文是什么」——这正是前端来源卡片需要的三样东西。
    """
    conversation = await db.get(Conversation, conversation_id)
    if conversation is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"会话不存在：{conversation_id}",
        )

    messages = (
        (
            await db.execute(
                select(Message)
                .where(Message.conversation_id == conversation_id)
                .order_by(Message.id)
            )
        )
        .scalars()
        .all()
    )

    sources_by_message: dict[int, list[SourceOut]] = {}
    if messages:
        rows = (
            await db.execute(
                select(Citation, Chunk, Document)
                .join(Chunk, Chunk.id == Citation.chunk_id)
                .join(Document, Document.id == Chunk.doc_id)
                .where(Citation.message_id.in_([m.id for m in messages]))
                .order_by(Citation.rank_no)
            )
        ).all()
        for citation, chunk, document in rows:
            sources_by_message.setdefault(citation.message_id, []).append(
                SourceOut(
                    rank=citation.rank_no,
                    chunk_id=chunk.id,
                    doc_id=document.id,
                    doc_name=document.filename,
                    page=chunk.page,
                    content=chunk.content,
                    score=citation.score or 0.0,
                )
            )

    return ConversationDetailOut(
        conversation=ConversationOut.model_validate(conversation),
        messages=[
            MessageOut(
                id=m.id,
                role=m.role,
                content=m.content,
                status=m.status,
                created_time=m.created_time,
                sources=sources_by_message.get(m.id, []),
            )
            for m in messages
        ],
    )
