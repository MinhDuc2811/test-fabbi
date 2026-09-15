# Technical Specification: Todo List Sharing

## 1. Overview & Objective

- **Feature Summary**: A user (the **Owner**) can share their entire todo list with another
  registered user (the **Collaborator**) as either a **Viewer** (read-only) or an **Editor**
  (can create/update/toggle/delete todos in that list). The Owner can change a Collaborator's
  permission or revoke access at any time.
- **Problem Statement**: Today a todo list is private to exactly one account. Users who want a
  partner, assistant, or manager to see or help manage their tasks have no way to do so without
  sharing their login credentials, which bypasses per-user data isolation and auditability
  entirely.
- **Target Audience / Roles**:
  - **Owner** — the user who created the todos; always has full control (read/write/delete todos,
    manage who has access).
  - **Editor** — a Collaborator granted read+write access to the Owner's list.
  - **Viewer** — a Collaborator granted read-only access to the Owner's list.

## 2. User Stories & Acceptance Criteria

### User Story 1: Share a list
- **As an** Owner
- **I want to** share my todo list with another registered user as Viewer or Editor
- **So that** they can see or help manage my tasks without using my account
- **Acceptance Criteria**:
  - [ ] Sharing requires the target user's email; the target must already have an account.
  - [ ] A user cannot share a list with themselves.
  - [ ] Sharing the same list with the same user twice returns a clear "already shared" error
        instead of creating a duplicate grant.
  - [ ] The Collaborator sees the shared list under "Shared with me" immediately after being
        granted access (no waiting for a cache TTL).

### User Story 2: Revoke access
- **As an** Owner
- **I want to** revoke a Collaborator's access at any time
- **So that** I stay in control of who can see or change my tasks
- **Acceptance Criteria**:
  - [ ] After revocation, the very next request the ex-Collaborator makes for that list is
        rejected (403/404), even if they had a cached page open.
  - [ ] Revoking one Collaborator does not affect any other Collaborator's access to the same list.
  - [ ] Only the Owner can revoke; a Collaborator (even an Editor) cannot revoke another
        Collaborator's access or their own.

### User Story 3: Change permission level
- **As an** Owner
- **I want to** upgrade a Viewer to Editor or downgrade an Editor to Viewer without removing and
  re-adding them
- **So that** I can adjust collaboration as needs change
- **Acceptance Criteria**:
  - [ ] Changing permission takes effect on the Collaborator's next request.
  - [ ] Downgrading an Editor to Viewer immediately blocks further writes from that user, even if
        writes were possible seconds earlier.

### User Story 4: View a shared list (Viewer)
- **As a** Viewer
- **I want to** see the Owner's todos in read-only mode
- **So that** I can track progress without risk of accidentally changing anything
- **Acceptance Criteria**:
  - [ ] A Viewer can list and read individual todos in the shared list.
  - [ ] Any create/update/delete/toggle attempt by a Viewer on that list returns 403.

### User Story 5: Collaborate on a shared list (Editor)
- **As an** Editor
- **I want to** create, update, toggle, and delete todos in a list shared with me
- **So that** I can actively help manage the Owner's tasks
- **Acceptance Criteria**:
  - [ ] An Editor can perform every todo operation the Owner can, scoped to that one shared list.
  - [ ] Todos an Editor creates in the shared list still belong to the Owner (`user_id` = Owner's
        id) — ownership of data never transfers to a Collaborator.
  - [ ] An Editor cannot manage sharing (cannot invite further Collaborators, change permissions,
        or revoke anyone, including themselves).

### User Story 6: See everything shared with me
- **As a** User
- **I want to** see a single list of every todo list that has been shared with me and at what
  permission level
- **So that** I can navigate between my own list and lists others have shared with me
- **Acceptance Criteria**:
  - [ ] The list shows the Owner's email and my permission (Viewer/Editor) for each entry.
  - [ ] The list only shows grants that are currently active (revoked grants disappear immediately).

## 3. Scope

- **In-Scope**:
  - Sharing a user's *entire* todo list (not individual todo items) with one or more registered
    users.
  - Two permission levels: Viewer (read-only) and Editor (read/write).
  - Owner-initiated: invite by email, change permission, revoke.
  - A "shared with me" view (API + data model; UI wiring follows the same pattern as the existing
    todo list screen).
  - Immediate (non-cached) enforcement of revocation and permission downgrades.
- **Out-of-Scope** (explicitly deferred to keep this release lean):
  - Sharing individual todo items instead of the whole list.
  - Public/link-based sharing that doesn't require the recipient to have an account.
  - Email/push notifications when a share is created, changed, or revoked.
  - Re-sharing by a Collaborator (only the Owner can manage who has access).
  - Ownership transfer (an Editor can never become the Owner of the list or of todos in it).
  - An audit/activity log of who created/edited/deleted which todo in a shared list.
  - Real-time (WebSocket) live updates when a Collaborator changes something — standard REST +
    the existing polling/refetch-on-mutation pattern is sufficient for v1.
  - Share expiration dates or scheduled auto-revocation.

## 4. Database Design

### New Table: `todo_list_shares`

| Column | Type | Constraints |
|---|---|---|
| `id` | UUID | Primary Key, default `gen_random_uuid()` |
| `owner_id` | UUID | `NOT NULL`, FK -> `users(id)` `ON DELETE CASCADE` |
| `shared_with_user_id` | UUID | `NOT NULL`, FK -> `users(id)` `ON DELETE CASCADE` |
| `permission` | VARCHAR(10) | `NOT NULL`, `CHECK (permission IN ('viewer', 'editor'))` |
| `created_at` | TIMESTAMPTZ | `NOT NULL`, default `now()` |
| `updated_at` | TIMESTAMPTZ | `NOT NULL`, default `now()`, updated on permission change |

**Constraints & Indexes**:
- `UNIQUE (owner_id, shared_with_user_id)` — one active grant per (owner, collaborator) pair;
  this is also what makes the duplicate-invite check race-safe (see §6) and what the API relies on
  to distinguish "create a new share" (`POST`) from "change permission" (`PATCH`).
- `CHECK (owner_id <> shared_with_user_id)` — DB-level backstop against self-sharing, in addition
  to the API-level check in §6.
- Index on `shared_with_user_id` (needed for `GET /shares/shared-with-me`, which is the
  high-frequency query — every Collaborator's dashboard load checks this).
- `owner_id` is already the leading column of the unique constraint above, so `GET /shares`
  (list of grants an Owner has given out) is already indexed.
- Both foreign keys `ON DELETE CASCADE`: deleting a user account removes every share where they
  are the Owner or the Collaborator. **Dependency note**: `todos.user_id` currently has no
  `ON DELETE` behavior defined (see Tier 1 findings) — when implementing this feature, add
  `ON DELETE CASCADE` there too, so deleting a user also cleans up their todos consistently with
  how their shares are cleaned up.

No changes to the existing `todos` table are required — a shared list is simply "the set of todos
where `user_id = owner_id`", scoped by an authorization check against `todo_list_shares` rather
than by `user_id = current_user.id`.

## 5. API Contracts & Endpoints

| Method | Endpoint | Description | Auth Required |
|---|---|---|---|
| POST | `/api/v1/shares` | Owner grants a Viewer/Editor share of their list | Yes |
| GET | `/api/v1/shares` | List shares the current user has granted (as Owner) | Yes |
| PATCH | `/api/v1/shares/{share_id}` | Owner changes a grant's permission | Yes |
| DELETE | `/api/v1/shares/{share_id}` | Owner revokes a grant | Yes |
| GET | `/api/v1/shares/shared-with-me` | Lists shared with the current user, as Collaborator | Yes |
| GET | `/api/v1/todos?owner_id={owner_id}` | Read a list (own or shared); defaults to own list | Yes |
| POST/PUT/DELETE `/api/v1/todos...?owner_id={owner_id}` | Write to a list (own, or shared as Editor) | Yes |

The existing todo endpoints gain an optional `owner_id` query parameter (defaults to
`current_user.id`, preserving today's behavior exactly). When `owner_id != current_user.id`, the
request is authorized against `todo_list_shares` instead of the simple ownership check added in
Tier 1: read operations require any active grant (Viewer or Editor); write operations require an
Editor grant. Todos created this way are still inserted with `user_id = owner_id`.

**Request Body & Validation Schema**

```jsonc
// POST /api/v1/shares
{
  "email": "collaborator@example.com",
  "permission": "viewer" // or "editor"
}

// PATCH /api/v1/shares/{share_id}
{
  "permission": "editor"
}
```

```jsonc
// Response shape for POST/GET /shares (as Owner)
{
  "id": "uuid",
  "owner_id": "uuid",
  "shared_with_user_id": "uuid",
  "shared_with_email": "collaborator@example.com",
  "permission": "viewer",
  "created_at": "2026-01-01T00:00:00Z",
  "updated_at": "2026-01-01T00:00:00Z"
}

// Response shape for GET /shares/shared-with-me (as Collaborator)
{
  "id": "uuid",
  "owner_id": "uuid",
  "owner_email": "owner@example.com",
  "permission": "editor",
  "created_at": "2026-01-01T00:00:00Z"
}
```

**Responses & Error Codes**

| Code | When |
|---|---|
| 200 | Successful `GET`/`PATCH` |
| 201 | Share created |
| 204 | Share deleted (revoked) |
| 400 | Self-share attempt, or invalid `permission` value |
| 401 | Missing/invalid access token |
| 403 | Acting user is not the Owner of the share being modified, or lacks the permission required for the requested todo operation |
| 404 | `email` in `POST /shares` does not belong to any registered user; or `share_id` does not exist / does not belong to the caller as Owner; or `owner_id` in a todos request has no active share granting the caller access (same 404 used for "doesn't exist" and "you can't see it", to avoid leaking which owner_ids are valid — consistent with the Tier 1 fix for todo IDOR) |
| 409 | A share already exists for this (owner, collaborator) pair — use `PATCH` instead |
| 422 | Malformed request body |

## 6. Business Logic & Security Considerations

**Authorization & Permission Matrix**

| Action | Owner | Editor | Viewer |
|---|---|---|---|
| Read todos in the list | Yes | Yes | Yes |
| Create/update/toggle/delete todos in the list | Yes | Yes | No |
| Invite a new Collaborator / change permissions / revoke | Yes | No | No |
| Delete the list itself (i.e. the Owner's account) | Yes | No | No |

- **Self-sharing prevention**: rejected at the API layer (400, checked before any DB write) and
  backstopped by the `CHECK (owner_id <> shared_with_user_id)` constraint.
- **Duplicate invites**: the API first tries the insert; on a unique-constraint violation it
  returns 409 with a message pointing the caller at `PATCH` instead. Relying on the DB constraint
  (not just an app-level `SELECT` then `INSERT`) avoids the same check-then-act race already
  identified for user registration in the Tier 1 findings.
- **Concurrent permission updates**: two `PATCH` requests changing the same share's permission
  race at the DB row level; Postgres serializes the two `UPDATE`s and the second one wins
  (last-write-wins). This is acceptable for a non-financial, single-owner-controlled setting — no
  optimistic-locking/version column is introduced for v1.
- **Owner revokes access mid-request**: authorization is re-checked on every request against the
  database (see §7 — it is deliberately *not* cached with a TTL long enough to outlive a revoke).
  A read that already passed its authorization check before the `DELETE /shares/{id}` commits is
  allowed to finish (standard check-then-use semantics); the Collaborator's *next* request is
  denied. There is no forced termination of in-flight requests.
- **Self-sharing prevention for Editors**: an Editor is a Collaborator, not an Owner, so all
  `/shares` management endpoints are 403 for anyone who is not the Owner of that specific share —
  an Editor cannot invite others, change permissions, or revoke access, including their own.

## 7. Caching & Invalidation Strategy

- **Todo list cache**: unchanged from the Tier 1 fix — cache key
  `todos:list:{owner_id}:{version}:{page}:{size}`, where `{owner_id}` is now the *list owner*
  (not necessarily `current_user.id`) and `{version}` is bumped on every write to that owner's
  list. Since Viewers/Editors read and write through the same `owner_id`-scoped key and
  invalidation path already built for Tier 1, no separate per-Collaborator cache entry is needed
  and no additional invalidation logic is required here.
- **Authorization is not cached with a TTL that could outlive a revoke.** The
  `todo_list_shares` lookup backing every cross-user todos request is a single indexed query
  (`WHERE owner_id = ? AND shared_with_user_id = ?`), cheap enough to run on every request
  uncached. If a future optimization introduces a cache for it (e.g. `share:{owner_id}:{grantee_id}`
  -> permission), it must be invalidated *synchronously inside* the `PATCH`/`DELETE /shares/{id}`
  handlers — the same "invalidate in the mutation handler, don't rely on passive expiry" pattern
  already established for the todos cache — never a passive TTL alone, since that would let a
  revoked Collaborator keep read/write access until the TTL lapses.
- Revoking a share (or changing its permission) also invalidates that Collaborator's
  `shared-with-me` view and the Owner's `shares` list the same way: synchronous invalidation in the
  handler that made the change, not a background/TTL-based expiry.
