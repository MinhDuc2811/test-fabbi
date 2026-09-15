"""Tier 4 tests: tags, todo filtering, tag attach/detach, bulk status update."""

import pytest
from httpx import AsyncClient


async def register(client: AsyncClient, email: str, password: str = "password123") -> dict:
    response = await client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": password},
    )
    assert response.status_code == 201
    return response.json()


def auth_headers(tokens: dict) -> dict:
    return {"Authorization": f"Bearer {tokens['access_token']}"}


# --- Tag CRUD ---


@pytest.mark.asyncio
async def test_create_tag_success(client: AsyncClient):
    tokens = await register(client, "tag-create@example.com")
    response = await client.post(
        "/api/v1/tags", json={"name": "Work", "color": "#ff0000"}, headers=auth_headers(tokens)
    )
    assert response.status_code == 201
    data = response.json()
    assert data["name"] == "Work"
    assert data["color"] == "#ff0000"


@pytest.mark.asyncio
async def test_duplicate_tag_name_case_insensitive_rejected(client: AsyncClient):
    tokens = await register(client, "tag-dup@example.com")
    headers = auth_headers(tokens)

    await client.post("/api/v1/tags", json={"name": "Work"}, headers=headers)
    response = await client.post("/api/v1/tags", json={"name": "WORK"}, headers=headers)

    assert response.status_code == 409


@pytest.mark.asyncio
async def test_cross_user_tag_access_denied(client: AsyncClient):
    tokens_a = await register(client, "tag-cross-a@example.com")
    tokens_b = await register(client, "tag-cross-b@example.com")

    create_resp = await client.post(
        "/api/v1/tags", json={"name": "Personal"}, headers=auth_headers(tokens_a)
    )
    tag_id = create_resp.json()["id"]

    get_response = await client.patch(
        f"/api/v1/tags/{tag_id}", json={"name": "Hijacked"}, headers=auth_headers(tokens_b)
    )
    delete_response = await client.delete(
        f"/api/v1/tags/{tag_id}", headers=auth_headers(tokens_b)
    )

    assert get_response.status_code == 404
    assert delete_response.status_code == 404


# --- Attach / detach ---


@pytest.mark.asyncio
async def test_attach_own_tag_to_own_todo(client: AsyncClient):
    tokens = await register(client, "attach-own@example.com")
    headers = auth_headers(tokens)

    tag_resp = await client.post("/api/v1/tags", json={"name": "Urgent"}, headers=headers)
    tag_id = tag_resp.json()["id"]
    todo_resp = await client.post("/api/v1/todos", json={"title": "Ship it"}, headers=headers)
    todo_id = todo_resp.json()["id"]

    attach_response = await client.post(
        f"/api/v1/todos/{todo_id}/tags/{tag_id}", headers=headers
    )
    assert attach_response.status_code == 204

    listed = await client.get("/api/v1/todos", headers=headers)
    tags_on_todo = listed.json()["items"][0]["tags"]
    assert len(tags_on_todo) == 1
    assert tags_on_todo[0]["name"] == "Urgent"


@pytest.mark.asyncio
async def test_cannot_attach_another_users_tag(client: AsyncClient):
    tokens_a = await register(client, "attach-a@example.com")
    tokens_b = await register(client, "attach-b@example.com")

    tag_resp = await client.post(
        "/api/v1/tags", json={"name": "A's tag"}, headers=auth_headers(tokens_a)
    )
    tag_id = tag_resp.json()["id"]

    todo_resp = await client.post(
        "/api/v1/todos", json={"title": "B's todo"}, headers=auth_headers(tokens_b)
    )
    todo_id = todo_resp.json()["id"]

    response = await client.post(
        f"/api/v1/todos/{todo_id}/tags/{tag_id}", headers=auth_headers(tokens_b)
    )
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_cannot_attach_tag_to_another_users_todo(client: AsyncClient):
    tokens_a = await register(client, "attach-todo-a@example.com")
    tokens_b = await register(client, "attach-todo-b@example.com")

    tag_resp = await client.post(
        "/api/v1/tags", json={"name": "B's tag"}, headers=auth_headers(tokens_b)
    )
    tag_id = tag_resp.json()["id"]

    todo_resp = await client.post(
        "/api/v1/todos", json={"title": "A's todo"}, headers=auth_headers(tokens_a)
    )
    todo_id = todo_resp.json()["id"]

    response = await client.post(
        f"/api/v1/todos/{todo_id}/tags/{tag_id}", headers=auth_headers(tokens_b)
    )
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_detach_tag(client: AsyncClient):
    tokens = await register(client, "detach@example.com")
    headers = auth_headers(tokens)

    tag_id = (await client.post("/api/v1/tags", json={"name": "Temp"}, headers=headers)).json()["id"]
    todo_id = (await client.post("/api/v1/todos", json={"title": "X"}, headers=headers)).json()["id"]
    await client.post(f"/api/v1/todos/{todo_id}/tags/{tag_id}", headers=headers)

    detach_response = await client.delete(
        f"/api/v1/todos/{todo_id}/tags/{tag_id}", headers=headers
    )
    assert detach_response.status_code == 204

    listed = await client.get("/api/v1/todos", headers=headers)
    assert listed.json()["items"][0]["tags"] == []


# --- Filtering ---


@pytest.mark.asyncio
async def test_filter_todos_by_status(client: AsyncClient):
    tokens = await register(client, "filter-status@example.com")
    headers = auth_headers(tokens)

    active_id = (await client.post("/api/v1/todos", json={"title": "Active"}, headers=headers)).json()["id"]
    done_id = (await client.post("/api/v1/todos", json={"title": "Done"}, headers=headers)).json()["id"]
    await client.put(f"/api/v1/todos/{done_id}", json={"completed": True}, headers=headers)

    active_only = await client.get("/api/v1/todos?status=active", headers=headers)
    completed_only = await client.get("/api/v1/todos?status=completed", headers=headers)

    active_ids = {item["id"] for item in active_only.json()["items"]}
    completed_ids = {item["id"] for item in completed_only.json()["items"]}
    assert active_ids == {active_id}
    assert completed_ids == {done_id}


@pytest.mark.asyncio
async def test_filter_todos_by_tag(client: AsyncClient):
    tokens = await register(client, "filter-tag@example.com")
    headers = auth_headers(tokens)

    tag_id = (await client.post("/api/v1/tags", json={"name": "Home"}, headers=headers)).json()["id"]
    tagged_id = (await client.post("/api/v1/todos", json={"title": "Clean"}, headers=headers)).json()["id"]
    (await client.post("/api/v1/todos", json={"title": "Not tagged"}, headers=headers))
    await client.post(f"/api/v1/todos/{tagged_id}/tags/{tag_id}", headers=headers)

    response = await client.get(f"/api/v1/todos?tag_id={tag_id}", headers=headers)
    items = response.json()["items"]

    assert len(items) == 1
    assert items[0]["id"] == tagged_id


@pytest.mark.asyncio
async def test_filter_todos_by_keyword(client: AsyncClient):
    tokens = await register(client, "filter-keyword@example.com")
    headers = auth_headers(tokens)

    await client.post("/api/v1/todos", json={"title": "Buy milk"}, headers=headers)
    await client.post("/api/v1/todos", json={"title": "Walk the dog"}, headers=headers)

    response = await client.get("/api/v1/todos?keyword=milk", headers=headers)
    items = response.json()["items"]

    assert len(items) == 1
    assert items[0]["title"] == "Buy milk"


# --- Bulk update ---


@pytest.mark.asyncio
async def test_bulk_update_status_marks_own_todos(client: AsyncClient):
    tokens = await register(client, "bulk-own@example.com")
    headers = auth_headers(tokens)

    id1 = (await client.post("/api/v1/todos", json={"title": "One"}, headers=headers)).json()["id"]
    id2 = (await client.post("/api/v1/todos", json={"title": "Two"}, headers=headers)).json()["id"]

    response = await client.patch(
        "/api/v1/todos/bulk-status",
        json={"todo_ids": [id1, id2], "completed": True},
        headers=headers,
    )
    assert response.status_code == 200
    assert response.json()["updated"] == 2

    listed = await client.get("/api/v1/todos", headers=headers)
    assert all(item["completed"] for item in listed.json()["items"])


@pytest.mark.asyncio
async def test_bulk_update_status_ownership_check(client: AsyncClient):
    tokens_a = await register(client, "bulk-a@example.com")
    tokens_b = await register(client, "bulk-b@example.com")

    todo_a = (
        await client.post("/api/v1/todos", json={"title": "A's todo"}, headers=auth_headers(tokens_a))
    ).json()["id"]

    response = await client.patch(
        "/api/v1/todos/bulk-status",
        json={"todo_ids": [todo_a], "completed": True},
        headers=auth_headers(tokens_b),
    )

    assert response.status_code == 200
    assert response.json()["updated"] == 0

    check = await client.get(f"/api/v1/todos/{todo_a}", headers=auth_headers(tokens_a))
    assert check.json()["completed"] is False


# --- Cache invalidation for tag operations ---


@pytest.mark.asyncio
async def test_cache_invalidated_on_attach_tag(client: AsyncClient):
    tokens = await register(client, "cache-attach@example.com")
    headers = auth_headers(tokens)

    tag_id = (await client.post("/api/v1/tags", json={"name": "Cache"}, headers=headers)).json()["id"]
    todo_id = (await client.post("/api/v1/todos", json={"title": "X"}, headers=headers)).json()["id"]

    # warm the cache with the pre-attach state
    await client.get("/api/v1/todos", headers=headers)

    await client.post(f"/api/v1/todos/{todo_id}/tags/{tag_id}", headers=headers)

    listed = await client.get("/api/v1/todos", headers=headers)
    assert listed.json()["items"][0]["tags"][0]["name"] == "Cache"
