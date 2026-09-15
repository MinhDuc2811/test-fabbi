import uuid
from datetime import datetime, timezone
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.tag import todo_tags

if TYPE_CHECKING:
    from app.models.tag import Tag
    from app.models.user import User


class Todo(Base):
    """Todo model."""

    __tablename__ = "todos"
    __table_args__ = (
        Index("ix_todos_user_id_completed_created_at", "user_id", "completed", "created_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True,
        default=uuid.uuid4,
    )
    title: Mapped[str] = mapped_column(
        String(200),
        nullable=False,
    )
    description: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )
    completed: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id"),
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    # Relationships
    user: Mapped["User"] = relationship(  # noqa: F821
        "User",
        back_populates="todos",
        lazy="select",
    )
    # lazy="selectin" (not the default "select") so that loading/refreshing a
    # Todo also loads its tags via one batched follow-up query, run inside the
    # same await - accessing a lazy="select" relationship outside of an
    # active await is what breaks under async SQLAlchemy (MissingGreenlet).
    tags: Mapped[list["Tag"]] = relationship(  # noqa: F821
        "Tag",
        secondary=todo_tags,
        lazy="selectin",
    )

    def __repr__(self) -> str:
        return f"<Todo {self.title}>"
