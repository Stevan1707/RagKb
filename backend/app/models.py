"""ORM 映射，严格对应 backend/sql/schema.sql 中的五张表。"""

from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, Index, String, UniqueConstraint, func, text
from sqlalchemy.dialects import mysql
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class Document(Base):
    """上传的文档"""

    __tablename__ = "document"
    __table_args__ = (Index("idx_created", "created_time"),)

    id: Mapped[int] = mapped_column(mysql.INTEGER(unsigned=True), primary_key=True, autoincrement=True)
    filename: Mapped[str] = mapped_column(String(255), nullable=False, comment="原始文件名")
    path: Mapped[str] = mapped_column(String(500), nullable=False, comment="落盘路径")
    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="pending",
        server_default=text("'pending'"),
        comment="pending/processing/done/failed",
    )
    chunk_count: Mapped[int] = mapped_column(
        mysql.INTEGER(unsigned=True),
        nullable=False,
        default=0,
        server_default=text("0"),
        comment="切出的块数",
    )
    error: Mapped[str | None] = mapped_column(String(500), nullable=True, comment="失败原因")
    created_time: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.now()
    )

    # 删除文档时由数据库 ON DELETE CASCADE 清理子表，passive_deletes 避免 ORM 逐条加载
    chunks: Mapped[list["Chunk"]] = relationship(
        back_populates="document", cascade="all, delete-orphan", passive_deletes=True
    )


class Chunk(Base):
    """文本块，id 与 FAISS 向量 id 一一对应"""

    __tablename__ = "chunk"
    __table_args__ = (
        UniqueConstraint("doc_id", "seq", name="uk_doc_seq"),
        Index("idx_doc", "doc_id"),
    )

    id: Mapped[int] = mapped_column(mysql.BIGINT(unsigned=True), primary_key=True, autoincrement=True)
    doc_id: Mapped[int] = mapped_column(
        mysql.INTEGER(unsigned=True),
        ForeignKey("document.id", ondelete="CASCADE", name="fk_chunk_doc"),
        nullable=False,
    )
    page: Mapped[int] = mapped_column(mysql.INTEGER, nullable=False, default=1, server_default=text("1"))
    seq: Mapped[int] = mapped_column(mysql.INTEGER, nullable=False, comment="文档内块序号，从 0 起")
    content: Mapped[str] = mapped_column(mysql.MEDIUMTEXT, nullable=False, comment="块原文")

    document: Mapped["Document"] = relationship(back_populates="chunks")


class Conversation(Base):
    """会话（一次对话的容器）"""

    __tablename__ = "conversation"
    __table_args__ = (Index("idx_updated", "updated_time"),)

    id: Mapped[int] = mapped_column(mysql.INTEGER(unsigned=True), primary_key=True, autoincrement=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    created_time: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.now()
    )
    updated_time: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.now()
    )

    messages: Mapped[list["Message"]] = relationship(
        back_populates="conversation", cascade="all, delete-orphan", passive_deletes=True
    )


class Message(Base):
    """会话中的一条消息，用户提问与模型回答共用此表，靠 role 区分"""

    __tablename__ = "message"
    __table_args__ = (Index("idx_conv", "conversation_id", "id"),)

    id: Mapped[int] = mapped_column(mysql.BIGINT(unsigned=True), primary_key=True, autoincrement=True)
    conversation_id: Mapped[int] = mapped_column(
        mysql.INTEGER(unsigned=True),
        ForeignKey("conversation.id", ondelete="CASCADE", name="fk_msg_conv"),
        nullable=False,
    )
    role: Mapped[str] = mapped_column(
        mysql.ENUM("user", "assistant"), nullable=False
    )
    content: Mapped[str] = mapped_column(mysql.MEDIUMTEXT, nullable=False)
    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="done",
        server_default=text("'done'"),
        comment="streaming/done/stopped/failed",
    )
    created_time: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.now()
    )

    conversation: Mapped["Conversation"] = relationship(back_populates="messages")
    citations: Mapped[list["Citation"]] = relationship(
        back_populates="message", cascade="all, delete-orphan", passive_deletes=True
    )


class Citation(Base):
    """答案与片段的引用关系，rank_no 对应正文中的 [1][2]"""

    __tablename__ = "citation"
    __table_args__ = (
        UniqueConstraint("message_id", "rank_no", name="uk_msg_rank"),
        Index("idx_chunk", "chunk_id"),
    )

    id: Mapped[int] = mapped_column(mysql.BIGINT(unsigned=True), primary_key=True, autoincrement=True)
    message_id: Mapped[int] = mapped_column(
        mysql.BIGINT(unsigned=True),
        ForeignKey("message.id", ondelete="CASCADE", name="fk_cit_msg"),
        nullable=False,
    )
    chunk_id: Mapped[int] = mapped_column(
        mysql.BIGINT(unsigned=True),
        ForeignKey("chunk.id", ondelete="CASCADE", name="fk_cit_chunk"),
        nullable=False,
    )
    rank_no: Mapped[int] = mapped_column(
        mysql.SMALLINT(unsigned=True), nullable=False, comment="对应正文 [1][2]，从 1 起"
    )
    score: Mapped[float | None] = mapped_column(Float, nullable=True, comment="检索得分，用于评估")

    message: Mapped["Message"] = relationship(back_populates="citations")
    chunk: Mapped["Chunk"] = relationship()
