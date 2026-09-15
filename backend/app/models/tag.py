import uuid
from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, ForeignKey, Index, String, Table, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base

todo_tags = Table(
    "todo_tags",
    Base.metadata,
    Column("todo_id", ForeignKey("todos.id", ondelete="CASCADE"), primary_key=True),
    Column("tag_id", ForeignKey("tags.id", ondelete="CASCADE"), primary_key=True),
    Index("ix_todo_tags_tag_id", "tag_id"),
)


class Tag(Base):
    """Tag model.

    Case-insensitive uniqueness of (user_id, name) is enforced by a functional
    unique index created in the Alembic migration (`lower(name)`), not by a
    plain column-level unique constraint, which would only be case-sensitive.
    """

    __tablename__ = "tags"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    name: Mapped[str] = mapped_column(String(50), nullable=False)
    color: Mapped[str | None] = mapped_column(String(20), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    def __repr__(self) -> str:
        return f"<Tag {self.name}>"


# Functional unique index, defined after the class so it can reference the
# fully-built Table/Column objects: enforces "tag name unique per user,
# case-insensitively" at the DB level (a plain unique=True on `name` would
# only be case-sensitive). Declared here (not just in the migration) so
# Base.metadata.create_all() also creates it for the SQLite test database.
Index(
    "uq_tags_user_lower_name",
    Tag.__table__.c.user_id,
    func.lower(Tag.__table__.c.name),
    unique=True,
)
