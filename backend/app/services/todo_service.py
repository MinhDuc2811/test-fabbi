import uuid
from datetime import date, timedelta

from sqlalchemy import func, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.tag import Tag, todo_tags
from app.models.todo import Todo
from app.schemas.todo import TodoCreate


async def create_todo(
    db: AsyncSession, todo_data: TodoCreate, user_id: uuid.UUID
) -> Todo:
    todo = Todo(
        title=todo_data.title,
        description=todo_data.description,
        user_id=user_id,
    )
    db.add(todo)
    await db.flush()
    await db.refresh(todo)
    return todo


async def get_todos(
    db: AsyncSession,
    user_id: uuid.UUID,
    skip: int = 0,
    limit: int = 20,
    status: str | None = None,
    tag_id: uuid.UUID | None = None,
    keyword: str | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
) -> tuple[list[Todo], int]:
    """Get todos for a specific user, with optional filtering, paginated."""
    conditions = [Todo.user_id == user_id]

    if status == "active":
        conditions.append(Todo.completed.is_(False))
    elif status == "completed":
        conditions.append(Todo.completed.is_(True))

    if keyword:
        pattern = f"%{keyword}%"
        conditions.append(or_(Todo.title.ilike(pattern), Todo.description.ilike(pattern)))

    if date_from:
        conditions.append(Todo.created_at >= date_from)
    if date_to:
        # date_to is a calendar date; include the whole day it refers to.
        conditions.append(Todo.created_at < date_to + timedelta(days=1))

    query = select(Todo).where(*conditions)
    count_query = select(func.count()).select_from(Todo).where(*conditions)

    if tag_id:
        query = query.join(Todo.tags).where(Tag.id == tag_id)
        count_query = count_query.join(todo_tags, todo_tags.c.todo_id == Todo.id).where(
            todo_tags.c.tag_id == tag_id
        )

    query = query.order_by(Todo.created_at.desc(), Todo.id.desc()).offset(skip).limit(limit)

    result = await db.execute(query)
    todos = list(result.scalars().all())

    total = await db.execute(count_query)

    return todos, total.scalar_one()


async def get_todo_by_id(
    db: AsyncSession, todo_id: uuid.UUID, user_id: uuid.UUID
) -> Todo | None:
    result = await db.execute(
        select(Todo).where(Todo.id == todo_id, Todo.user_id == user_id)
    )
    return result.scalar_one_or_none()


async def update_todo(db: AsyncSession, todo: Todo, update_data: dict) -> Todo:
    for key, value in update_data.items():
        setattr(todo, key, value)
    await db.flush()
    await db.refresh(todo)
    return todo


async def delete_todo(db: AsyncSession, todo: Todo) -> None:
    await db.delete(todo)
    await db.flush()


async def bulk_update_status(
    db: AsyncSession, todo_ids: list[uuid.UUID], completed: bool, user_id: uuid.UUID
) -> int:
    """Set `completed` on the given todos that belong to user_id, in one statement.

    Any id that doesn't exist or doesn't belong to user_id is silently
    excluded from the WHERE clause rather than erroring, the same
    non-leaking ownership pattern used by get_todo_by_id.
    """
    result = await db.execute(
        update(Todo)
        .where(Todo.id.in_(todo_ids), Todo.user_id == user_id)
        .values(completed=completed)
    )
    await db.flush()
    return result.rowcount


async def attach_tag(db: AsyncSession, todo_id: uuid.UUID, tag_id: uuid.UUID) -> None:
    """Attach a tag to a todo, idempotently (no-op if already attached)."""
    existing = await db.execute(
        select(todo_tags).where(todo_tags.c.todo_id == todo_id, todo_tags.c.tag_id == tag_id)
    )
    if existing.first() is None:
        await db.execute(todo_tags.insert().values(todo_id=todo_id, tag_id=tag_id))
        await db.flush()


async def detach_tag(db: AsyncSession, todo_id: uuid.UUID, tag_id: uuid.UUID) -> None:
    """Detach a tag from a todo, idempotently (no-op if not attached)."""
    await db.execute(
        todo_tags.delete().where(
            todo_tags.c.todo_id == todo_id, todo_tags.c.tag_id == tag_id
        )
    )
    await db.flush()
