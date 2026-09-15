import json
import uuid
from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_redis
from app.core.redis import RedisClient
from app.db.session import get_db
from app.models.user import User
from app.schemas.tag import TagResponse
from app.schemas.todo import (
    BulkStatusUpdate,
    TodoCreate,
    TodoListResponse,
    TodoResponse,
    TodoUpdate,
)
from app.services.tag_service import get_tag_by_id
from app.services.todo_service import (
    attach_tag,
    bulk_update_status,
    create_todo,
    delete_todo,
    detach_tag,
    get_todo_by_id,
    get_todos,
    update_todo,
)

router = APIRouter()

CACHE_TTL = 300  # 5 minutes


async def _todos_cache_key(
    redis: RedisClient,
    user_id: uuid.UUID,
    page: int,
    size: int,
    status: str | None = None,
    tag_id: uuid.UUID | None = None,
    keyword: str | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
) -> str:
    """Build a per-user, per-page, per-filter cache key that includes a version stamp.

    Every filter parameter is part of the key so that distinct filter
    combinations never share a cache entry. Bumping the version (see
    invalidate_todos_cache) makes every previously cached page/filter
    combination for that user unreachable in one write, without needing a
    Redis SCAN/pattern-delete to enumerate them.
    """
    version = await redis.get(f"todos:list-version:{user_id}") or "0"
    filters = f"{status or ''}:{tag_id or ''}:{keyword or ''}:{date_from or ''}:{date_to or ''}"
    return f"todos:list:{user_id}:{version}:{page}:{size}:{filters}"


async def invalidate_todos_cache(redis: RedisClient, user_id: uuid.UUID) -> None:
    version_key = f"todos:list-version:{user_id}"
    current_version = int(await redis.get(version_key) or "0")
    await redis.set(version_key, str(current_version + 1))


@router.get("", response_model=TodoListResponse)
async def list_todos(
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1),
    status: str | None = Query(None, description="'active' or 'completed'; omit for all"),
    tag_id: uuid.UUID | None = Query(None),
    keyword: str | None = Query(None, description="Matches against title or description"),
    date_from: date | None = Query(None),
    date_to: date | None = Query(None),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    redis: RedisClient = Depends(get_redis),
):
    """Get paginated, optionally filtered list of todos."""
    skip = (page - 1) * size

    cache_key = await _todos_cache_key(
        redis, current_user.id, page, size, status, tag_id, keyword, date_from, date_to
    )

    # Try to get from cache
    cached = await redis.get(cache_key)
    if cached:
        cached_data = json.loads(cached)
        return TodoListResponse(**cached_data)

    todos, total = await get_todos(
        db,
        user_id=current_user.id,
        skip=skip,
        limit=size,
        status=status,
        tag_id=tag_id,
        keyword=keyword,
        date_from=date_from,
        date_to=date_to,
    )

    # get_todos already filters by current_user.id, so every todo in this
    # page belongs to current_user - no need to look its email up again.
    items = [
        TodoResponse(
            id=todo.id,
            title=todo.title,
            description=todo.description,
            completed=todo.completed,
            user_id=todo.user_id,
            created_at=todo.created_at,
            updated_at=todo.updated_at,
            user_email=current_user.email,
            tags=[TagResponse.model_validate(tag) for tag in todo.tags],
        )
        for todo in todos
    ]

    response = TodoListResponse(
        items=items,
        total=total,
        page=page,
        size=size,
    )

    # Cache the response
    await redis.set(cache_key, response.model_dump_json(), ex=CACHE_TTL)

    return response


@router.post("", response_model=TodoResponse, status_code=status.HTTP_201_CREATED)
async def create_new_todo(
    todo_data: TodoCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    redis: RedisClient = Depends(get_redis),
):
    """Create a new todo item."""
    todo = await create_todo(db, todo_data, current_user.id)
    await invalidate_todos_cache(redis, current_user.id)
    return todo


@router.patch("/bulk-status")
async def bulk_update_todo_status(
    payload: BulkStatusUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    redis: RedisClient = Depends(get_redis),
):
    """Bulk mark todos completed/active. Only affects todos owned by the caller."""
    updated = await bulk_update_status(db, payload.todo_ids, payload.completed, current_user.id)
    await invalidate_todos_cache(redis, current_user.id)
    return {"updated": updated}


@router.get("/{todo_id}", response_model=TodoResponse)
async def get_todo(
    todo_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get a specific todo by ID."""
    todo = await get_todo_by_id(db, todo_id, current_user.id)
    if not todo:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Todo not found",
        )

    return todo


@router.put("/{todo_id}", response_model=TodoResponse)
async def update_existing_todo(
    todo_id: uuid.UUID,
    todo_data: TodoUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    redis: RedisClient = Depends(get_redis),
):
    """Update a todo item."""
    todo = await get_todo_by_id(db, todo_id, current_user.id)
    if not todo:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Todo not found",
        )

    update_data = todo_data.model_dump(exclude_unset=True)

    updated_todo = await update_todo(db, todo, update_data)
    await invalidate_todos_cache(redis, current_user.id)

    return updated_todo


@router.delete("/{todo_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_existing_todo(
    todo_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    redis: RedisClient = Depends(get_redis),
):
    """Delete a todo item."""
    todo = await get_todo_by_id(db, todo_id, current_user.id)
    if not todo:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Todo not found",
        )

    await delete_todo(db, todo)
    await invalidate_todos_cache(redis, current_user.id)

    return None


@router.post("/{todo_id}/tags/{tag_id}", status_code=status.HTTP_204_NO_CONTENT)
async def attach_tag_to_todo(
    todo_id: uuid.UUID,
    tag_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    redis: RedisClient = Depends(get_redis),
):
    """Attach one of the caller's own tags to one of the caller's own todos."""
    todo = await get_todo_by_id(db, todo_id, current_user.id)
    if not todo:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Todo not found")

    tag = await get_tag_by_id(db, tag_id, current_user.id)
    if not tag:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tag not found")

    await attach_tag(db, todo.id, tag.id)
    await invalidate_todos_cache(redis, current_user.id)
    return None


@router.delete("/{todo_id}/tags/{tag_id}", status_code=status.HTTP_204_NO_CONTENT)
async def detach_tag_from_todo(
    todo_id: uuid.UUID,
    tag_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    redis: RedisClient = Depends(get_redis),
):
    """Detach a tag from one of the caller's own todos."""
    todo = await get_todo_by_id(db, todo_id, current_user.id)
    if not todo:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Todo not found")

    await detach_tag(db, todo.id, tag_id)
    await invalidate_todos_cache(redis, current_user.id)
    return None
