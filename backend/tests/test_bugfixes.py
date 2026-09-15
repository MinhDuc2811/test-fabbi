"""Regression tests for the Tier 1 bugs found in the assessment codebase.

Each test targets one specific bug documented in the PR description. They are
written before the corresponding fix (TDD red -> green) so a failure here is
expected until the matching fix in app/ lands.
"""

from datetime import timedelta

import pytest
from httpx import AsyncClient

from app.core.security import create_access_token, create_refresh_token


async def register(client: AsyncClient, email: str, password: str = "password123") -> dict:
    response = await client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": password},
    )
    assert response.status_code == 201
    return response.json()


# --- Bug: refresh token accepted as access token (deps.py missing type check) ---


@pytest.mark.asyncio
async def test_refresh_token_cannot_access_protected_endpoint(client: AsyncClient):
    tokens = await register(client, "refresh-as-access@example.com")

    response = await client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {tokens['refresh_token']}"},
    )
    assert response.status_code == 401


# --- Bug: verify_exp=False means expired tokens are always accepted ---


@pytest.mark.asyncio
async def test_expired_access_token_rejected(client: AsyncClient):
    tokens = await register(client, "expired@example.com")

    # Mint a token for the same user but already expired.
    me_response = await client.get(
        "/api/v1/auth/me", headers={"Authorization": f"Bearer {tokens['access_token']}"}
    )
    user_id = me_response.json()["id"]

    expired_token = create_access_token(
        data={"sub": user_id}, expires_delta=timedelta(minutes=-5)
    )

    response = await client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {expired_token}"},
    )
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_tampered_token_rejected(client: AsyncClient):
    tokens = await register(client, "tampered@example.com")
    tampered = tokens["access_token"][:-2] + ("aa" if tokens["access_token"][-2:] != "aa" else "bb")

    response = await client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {tampered}"},
    )
    assert response.status_code == 401


# --- Bug: get_todo_by_id has no ownership filter (IDOR) ---


@pytest.mark.asyncio
async def test_cannot_read_other_users_todo(client: AsyncClient):
    tokens_a = await register(client, "idor-a@example.com")
    tokens_b = await register(client, "idor-b@example.com")

    create_resp = await client.post(
        "/api/v1/todos",
        json={"title": "A's private todo"},
        headers={"Authorization": f"Bearer {tokens_a['access_token']}"},
    )
    todo_id = create_resp.json()["id"]

    response = await client.get(
        f"/api/v1/todos/{todo_id}",
        headers={"Authorization": f"Bearer {tokens_b['access_token']}"},
    )
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_cannot_update_other_users_todo(client: AsyncClient):
    tokens_a = await register(client, "idor-upd-a@example.com")
    tokens_b = await register(client, "idor-upd-b@example.com")

    create_resp = await client.post(
        "/api/v1/todos",
        json={"title": "A's todo"},
        headers={"Authorization": f"Bearer {tokens_a['access_token']}"},
    )
    todo_id = create_resp.json()["id"]

    response = await client.put(
        f"/api/v1/todos/{todo_id}",
        json={"title": "Hijacked"},
        headers={"Authorization": f"Bearer {tokens_b['access_token']}"},
    )
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_cannot_delete_other_users_todo(client: AsyncClient):
    tokens_a = await register(client, "idor-del-a@example.com")
    tokens_b = await register(client, "idor-del-b@example.com")

    create_resp = await client.post(
        "/api/v1/todos",
        json={"title": "A's todo"},
        headers={"Authorization": f"Bearer {tokens_a['access_token']}"},
    )
    todo_id = create_resp.json()["id"]

    response = await client.delete(
        f"/api/v1/todos/{todo_id}",
        headers={"Authorization": f"Bearer {tokens_b['access_token']}"},
    )
    assert response.status_code == 404


# --- Bug: partial update wipes description / ignores completed=false ---


@pytest.mark.asyncio
async def test_toggle_completed_false_persists(client: AsyncClient):
    tokens = await register(client, "toggle@example.com")
    headers = {"Authorization": f"Bearer {tokens['access_token']}"}

    create_resp = await client.post(
        "/api/v1/todos", json={"title": "Toggle me"}, headers=headers
    )
    todo_id = create_resp.json()["id"]

    await client.put(f"/api/v1/todos/{todo_id}", json={"completed": True}, headers=headers)
    response = await client.put(
        f"/api/v1/todos/{todo_id}", json={"completed": False}, headers=headers
    )

    assert response.status_code == 200
    assert response.json()["completed"] is False


@pytest.mark.asyncio
async def test_partial_update_preserves_description(client: AsyncClient):
    tokens = await register(client, "partial@example.com")
    headers = {"Authorization": f"Bearer {tokens['access_token']}"}

    create_resp = await client.post(
        "/api/v1/todos",
        json={"title": "Original title", "description": "Keep me"},
        headers=headers,
    )
    todo_id = create_resp.json()["id"]

    response = await client.put(
        f"/api/v1/todos/{todo_id}", json={"title": "New title"}, headers=headers
    )

    assert response.status_code == 200
    data = response.json()
    assert data["title"] == "New title"
    assert data["description"] == "Keep me"


# --- Bug: Redis cache never invalidated on write, and shared across users ---


@pytest.mark.asyncio
async def test_cache_invalidated_on_create(client: AsyncClient):
    tokens = await register(client, "cache-create@example.com")
    headers = {"Authorization": f"Bearer {tokens['access_token']}"}

    first = await client.get("/api/v1/todos", headers=headers)
    assert first.json()["total"] == 0

    await client.post("/api/v1/todos", json={"title": "New"}, headers=headers)

    second = await client.get("/api/v1/todos", headers=headers)
    assert second.json()["total"] == 1


@pytest.mark.asyncio
async def test_cache_invalidated_on_update_and_delete(client: AsyncClient):
    tokens = await register(client, "cache-update@example.com")
    headers = {"Authorization": f"Bearer {tokens['access_token']}"}

    create_resp = await client.post(
        "/api/v1/todos", json={"title": "Before"}, headers=headers
    )
    todo_id = create_resp.json()["id"]

    # warm the cache
    await client.get("/api/v1/todos", headers=headers)

    await client.put(f"/api/v1/todos/{todo_id}", json={"title": "After"}, headers=headers)
    listed = await client.get("/api/v1/todos", headers=headers)
    assert listed.json()["items"][0]["title"] == "After"

    await client.delete(f"/api/v1/todos/{todo_id}", headers=headers)
    listed_after_delete = await client.get("/api/v1/todos", headers=headers)
    assert listed_after_delete.json()["total"] == 0


@pytest.mark.asyncio
async def test_todo_list_cache_is_scoped_per_user(client: AsyncClient):
    tokens_a = await register(client, "cache-scope-a@example.com")
    tokens_b = await register(client, "cache-scope-b@example.com")

    await client.post(
        "/api/v1/todos",
        json={"title": "A only"},
        headers={"Authorization": f"Bearer {tokens_a['access_token']}"},
    )

    # A's list gets cached first.
    await client.get(
        "/api/v1/todos", headers={"Authorization": f"Bearer {tokens_a['access_token']}"}
    )

    response_b = await client.get(
        "/api/v1/todos", headers={"Authorization": f"Bearer {tokens_b['access_token']}"}
    )
    assert response_b.json()["total"] == 0
    assert response_b.json()["items"] == []


# --- Bug: login leaks whether an email is registered via 404 vs 401 ---


@pytest.mark.asyncio
async def test_login_error_does_not_leak_user_existence(client: AsyncClient):
    await register(client, "enum@example.com", password="correct-password")

    wrong_password = await client.post(
        "/api/v1/auth/login",
        json={"email": "enum@example.com", "password": "wrong-password"},
    )
    unknown_email = await client.post(
        "/api/v1/auth/login",
        json={"email": "never-registered@example.com", "password": "whatever"},
    )

    assert wrong_password.status_code == unknown_email.status_code == 401
    assert wrong_password.json()["detail"] == unknown_email.json()["detail"]


# --- Bug: /auth/refresh minted new tokens without checking the user still exists ---


@pytest.mark.asyncio
async def test_refresh_rejects_token_for_deleted_user(client: AsyncClient):
    fake_user_id = "00000000-0000-0000-0000-000000000099"
    forged_refresh_token = create_refresh_token(data={"sub": fake_user_id})

    response = await client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": forged_refresh_token},
    )
    assert response.status_code == 401
