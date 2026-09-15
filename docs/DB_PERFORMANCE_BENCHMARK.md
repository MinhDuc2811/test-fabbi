# Task 3C: Database Performance & Indexing Strategy

## Setup

Seeded via the provided script, into the `postgres` container's own volume (not the pytest
SQLite suite):

```bash
docker compose exec -e SEED_USERS=10000 -e SEED_TODOS=1000000 backend python -m app.db.seed
```

Result: 10,000 users, 1,000,000 todos randomly distributed across them (avg. ~100 todos/user).
All queries below were run against one real sampled user (`29d1c64b-...-8abf9963`, 112 todos)
via `docker compose exec postgres psql -U fabbi -d postgres`, using `EXPLAIN (ANALYZE, BUFFERS)`.

Before state: `todos` had only its primary key (`id`) — no index on `user_id` at all — and
`users.email` had no uniqueness constraint (see Tier 1 findings: this is also what made the
register-endpoint's check-then-insert a real race condition).

## Migration

`backend/alembic/versions/7e82e6b7daa4_add_todo_composite_index_and_unique_.py`, applied with
`alembic upgrade head`:

- `CREATE INDEX ix_todos_user_id_completed_created_at ON todos (user_id, completed, created_at)`
- `ALTER TABLE users ADD CONSTRAINT uq_users_email UNIQUE (email)`

The composite column order (`user_id, completed, created_at`) is chosen over a plain
`(user_id, created_at)` index because Tier 4's `GET /todos?status=&...` filters by `completed` in
addition to ordering by `created_at` — the exact scenario a composite index is for. For *today's*
base query alone (no `completed` filter), a 2-column `(user_id, created_at)` index would be
marginally more efficient to store and maintain, but would need re-indexing again as soon as
status filtering ships; the composite index is the one that already serves the query that's coming
next.

## Benchmark: Before vs After

| Query | Before (Seq Scan) | After (Index Scan) | Speedup |
|---|---|---|---|
| Paginated list: `WHERE user_id = ? ORDER BY created_at DESC, id DESC LIMIT 20` | 34.69 ms — `Parallel Seq Scan` over 1,000,000 rows (2 workers), then top-N sort | 0.75 ms — `Bitmap Index Scan` on the new index, 112 rows fetched, then sort | **~46x** |
| Count: `SELECT count(*) WHERE user_id = ?` | 27.98 ms — `Parallel Seq Scan`, 1,000,000 rows filtered down to 112 | 0.11 ms — `Index Only Scan`, no heap access beyond a few visibility-map fetches | **~262x** |
| Count active: `WHERE user_id = ? AND completed = false` | 28.94 ms — `Parallel Seq Scan` | 0.09 ms — `Index Only Scan` using both `user_id` and `completed` from the composite index | **~329x** |

Raw plans (abridged) are in the PR description; full output was captured via
`EXPLAIN (ANALYZE, BUFFERS)` on the running container. The "before" numbers already benefit from
Postgres parallel workers (2 launched) - a single-threaded query would be slower still; the
"after" numbers use no parallelism at all because they don't need it.

## Index Trade-offs

- **Write latency**: every `INSERT`/`UPDATE`/`DELETE` on `todos` now also maintains one extra
  three-column B-tree entry. For a single interactive request this is sub-millisecond and dwarfed
  by normal request/response overhead, so it is not user-visible. It adds up during bulk loads: the
  seed script's own batches (5,000 rows each) ran in 0.16-0.43s per batch (see seed output) *before*
  this index existed; every additional index on a bulk-insert path adds proportional per-row
  maintenance cost, so expect bulk imports to get somewhat slower after this migration - a
  precise before/after bulk-load number is not quoted here because a fair apples-to-apples
  comparison would require re-running the exact same seed batch twice on an otherwise-identical
  database, which was not done for this exercise.
- **Storage overhead**: `\di+`/`\dt+` on this dataset: `ix_todos_user_id_completed_created_at` is
  **48 MB** for 1,000,000 rows, against a **212 MB** `todos` table heap - about 23% extra on-disk
  size, in line with a three-column btree index at this cardinality. `uq_users_email` is
  negligible at **440 kB** for 10,000 rows.
- **Migration safety on large production tables**: `CREATE INDEX` (and
  `ADD CONSTRAINT ... UNIQUE`, which builds a backing index) takes a `SHARE` lock that blocks
  writes to the table for the duration of the build. On this assessment's dataset the build
  finished in well under a second, so the plain transactional migration above is fine. On a
  production table with real concurrent write traffic, the safe approach is
  `CREATE INDEX CONCURRENTLY` (Postgres builds it without blocking writes, at the cost of a longer
  build and needing a retry if it fails), which **cannot run inside a transaction block** — Alembic
  wraps each migration in a transaction by default, so this specifically requires
  `with op.get_context().autocommit_block():` around the `op.create_index(..., postgresql_concurrently=True)`
  call (and dropping `transaction_per_migration`/using `autocommit_block` appropriately). Left as a
  documented follow-up rather than applied here, since it's unnecessary for this dataset and adds
  migration-runner complexity that isn't exercised by the assessment's own test suite.
- **The new `uq_users_email` constraint** also closes the check-then-insert race noted in the
  Tier 1 write-up (`POST /auth/register` checked for an existing email, then inserted, with no DB
  constraint stopping two concurrent requests from both succeeding). A concurrent duplicate
  registration now gets a DB-level unique-violation instead of silently creating two accounts with
  the same email; wiring that into a friendly 400/409 response instead of a raw 500 is a good
  small follow-up but out of scope for this fix.
