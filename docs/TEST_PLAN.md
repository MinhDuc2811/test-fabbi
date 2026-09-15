# Manual Test Plan: Fabbi Todo App — Tier 1 Regression Scope

## 1. Scope & Objective

- **Mục tiêu kiểm thử**: Xác nhận các lỗi Tier 1 (auth, authorization, cache, partial update,
  infra cold-boot) đã được sửa đúng, và không có hồi quy (regression) so với hành vi hợp lệ hiện có.
- **Phạm vi kiểm thử**: Authentication & Token Handling, Todo CRUD, Authorization/Data Isolation,
  Caching, Frontend Session Handling, Docker Cold Boot.
- **Ngoài phạm vi**: Tier 4 (tags/filter/bulk actions) - chưa triển khai; hiệu năng tải cao
  (load/stress testing) ngoài các con số benchmark đã có ở `docs/DB_PERFORMANCE_BENCHMARK.md`.

## 2. Test Environment & Prerequisites

- Base URL Backend: `http://localhost:8000`
- Base URL Frontend: `http://localhost:3000`
- Chạy toàn bộ stack: `docker compose up -d --build` (từ commit mới nhất trên nhánh
  `assessment/DucLM`).
- Test Accounts: không dùng tài khoản demo cố định cho các case cross-user vì cần 2 tài khoản
  **mới, riêng biệt** mỗi lần chạy (tránh đụng dữ liệu cũ) — xem cột "Test Steps" để biết cách tạo.
  Với các case không cần cross-user, có thể dùng tài khoản demo có sẵn sau khi seed:
  `demo@test.com` / `Demo@123`.

## 3. Test Cases Matrix

| TC ID | Module / Feature | Test Scenario | Preconditions | Test Steps | Expected Result | Priority / Severity | Status |
|---|---|---|---|---|---|---|---|
| TC-01 | Auth | Login thành công với mật khẩu đúng | User đã đăng ký | 1. Nhập email/pass đúng<br>2. Bấm Login | Trả về token, chuyển hướng vào Todo page | High / Blocker | Pass |
| TC-02 | Auth | Login thất bại — không lộ user enumeration | User đã đăng ký | 1. Gọi `POST /auth/login` với email đúng, pass sai<br>2. Gọi lại với email chưa đăng ký, pass bất kỳ | Cả 2 trường hợp trả **401** với cùng message `"Incorrect email or password"` | Medium / Security | Pass (`test_login_error_does_not_leak_user_existence`) |
| TC-03 | Todo Security (IDOR) | User A không thể đọc/sửa/xoá Todo của User B | User A & B đã login, A có 1 todo | 1. User B gọi `GET`/`PUT`/`DELETE /todos/{A's todo id}` bằng token của B | Cả 3 thao tác trả **404 Not Found** (không phải 403, để không lộ sự tồn tại của resource) | High / Critical | Pass (`test_cannot_read/update/delete_other_users_todo`) |
| TC-04 | Todo Logic | Đổi trạng thái todo hoàn thành sang chưa hoàn thành | Todo đang `completed=true` | 1. Gọi `PUT /todos/{id}` với `{"completed": false}`<br>2. `GET` lại todo | `completed` phải là `false` (trước khi fix, `false` bị bỏ qua vì falsy) | Medium / Major | Pass (`test_toggle_completed_false_persists`) |
| TC-05 | Cache | Cập nhật Todo xoá cache lập tức | Todo đã được cache (đã `GET /todos` ít nhất 1 lần) | 1. Sửa title Todo qua `PUT`<br>2. Gọi lại `GET /todos` | Trả về title mới ngay, không phải bản cache cũ; test tương tự cho create/delete | Medium / Major | Pass (`test_cache_invalidated_on_create/update_and_delete`) |
| TC-06 | Partial Update | Sửa chỉ `title` không được xoá `description` | Todo có sẵn `description` | 1. Gọi `PUT /todos/{id}` chỉ với `{"title": "..."}`  (không gửi `description`) | `description` giữ nguyên giá trị cũ, không bị null | High / Major | Pass (`test_partial_update_preserves_description`) |
| TC-07 | Auth (JWT) | Token hết hạn bị từ chối | Có access token đã hết hạn (`exp` trong quá khứ) | 1. Gọi `GET /auth/me` với token hết hạn | Trả về **401** | Critical / Security | Pass (`test_expired_access_token_rejected`) |
| TC-08 | Auth (JWT) | Refresh token không dùng được như access token | Có refresh token hợp lệ | 1. Gọi `GET /auth/me` (hoặc bất kỳ endpoint bảo vệ nào) dùng **refresh token** thay vì access token | Trả về **401** ("Invalid token type") | Critical / Security | Pass (`test_refresh_token_cannot_access_protected_endpoint`) |
| TC-09 | Auth (JWT) | `/auth/refresh` từ chối token của user không tồn tại | Tạo thủ công 1 refresh token với `sub` là UUID không có trong DB | 1. Gọi `POST /auth/refresh` với token đó | Trả về **401** thay vì cấp token mới | Medium / Security | Pass (`test_refresh_rejects_token_for_deleted_user`) |
| TC-10 | Cross-User Isolation (Frontend) | Logout rồi login user khác trên **cùng 1 trình duyệt** không được thấy dữ liệu cũ | 2 tài khoản mới, cùng 1 tab trình duyệt | 1. User A đăng ký, tạo 1 todo riêng<br>2. Logout<br>3. Đăng ký/login User B trên cùng tab | Dashboard của B hiển thị "No todos yet", **không** thấy todo của A dù React Query cache chưa bị GC | Critical / Security | Pass (Playwright `cross-user isolation persists after logout/login on the same browser`) |
| TC-11 | Cross-User Isolation (2 phiên) | User A tạo todo riêng tư; User B ở session/browser context khác không thấy | 2 tài khoản mới, 2 browser context độc lập | 1. User A tạo todo<br>2. User B (context khác) mở dashboard | User B không thấy todo của A | Critical / Security | Pass (Playwright `cross-user data isolation: user B cannot see user A's private todo`) |
| TC-12 | Full User Journey | Đăng ký → tạo todo → toggle → logout hoạt động end-to-end | Chưa có tài khoản | 1. Register<br>2. Tạo todo<br>3. Tick hoàn thành, F5 kiểm tra vẫn giữ<br>4. Bỏ tick, F5 kiểm tra vẫn giữ<br>5. Logout | Mỗi bước đúng như mô tả, không có bước nào lỗi | High / Blocker | Pass (Playwright `full user journey`) |
| TC-13 | Infra / Cold Boot | Backend không crash khi Postgres/Redis chưa sẵn sàng | Volume Docker sạch (`docker compose down -v`) | 1. `docker compose up -d --build`<br>2. Theo dõi `docker compose ps -a` | `backend` đạt trạng thái `healthy` mà không cần restart thủ công | High / Reliability | Pass (trước khi sửa: `backend` exit code 1, `ConnectionRefusedError`; sau khi sửa: lên `healthy` ngay) |

## 4. Defect Tracking & Known Limitations

- **Đã sửa & có test tự động cho tất cả các case trên** (pytest cho TC-01, 02, 03, 04, 05, 06, 07,
  08, 09; Playwright cho TC-10, 11, 12; kiểm tra thủ công qua `docker compose ps` cho TC-13).
- **Chưa cover / để lại làm follow-up** (không chặn release, đã ghi trong PR):
  - Đăng ký trùng email đồng thời (race condition) giờ đã được chặn ở tầng DB
    (`uq_users_email`, xem `docs/DB_PERFORMANCE_BENCHMARK.md`), nhưng vi phạm constraint hiện trả
    về lỗi 500 thô thay vì 400/409 thân thiện — nên bọc lại thành `IntegrityError` handler.
  - Query key React Query (`["todos"]`) chưa gắn theo `user_id` — hiện được che chắn bởi
    `queryClient.clear()` khi logout/401, nhưng chưa phải fix triệt để nếu có code path khác thay
    đổi token mà không qua 2 nơi đó.
  - Chưa có rate-limiting cho `/auth/login` — không nằm trong 5 bug bắt buộc của Tier 1 nhưng đáng
    cân nhắc cho production thật.
  - `key={index}` trong danh sách todo đã đổi sang `key={todo.id}`; `ProtectedRoute` vẫn tự đọc
    `localStorage` thay vì dùng chung `useAuth()` — cosmetic, không ảnh hưởng bảo mật.

## 5. Test Execution Log

| Thời điểm | Loại test | Lệnh chạy | Kết quả | Ghi chú |
|---|---|---|---|---|
| 2026-09-15 (baseline, trước khi sửa bug) | Backend pytest | `pytest tests/ -v` | 9 passed, 0 failed | Bộ test gốc không chạm tới bug nào (JWT type/expiry, IDOR, cache, partial update) vì chưa có test case cho các kịch bản đó. |
| 2026-09-15 (TDD red, trước khi sửa bug) | Backend pytest | `pytest tests/test_bugfixes.py -v` | 1 passed, 11 failed | 11 test mới cho các bug Tier 1 đều FAIL đúng như kỳ vọng (refresh-as-access-token, expired token, IDOR x3, toggle false, partial update xoá description, cache không invalidate x2, cache rò user, user enumeration login). Chỉ `test_tampered_token_rejected` pass sẵn. |
| 2026-09-15 (baseline E2E, code gốc — qua `git worktree` tại commit `c92fd72` trên `main`) | Playwright E2E | `npx playwright test` | 0 passed, 3 failed | Cả 3 test fail ở bước "tạo todo xong phải thấy trong danh sách" do cache global `"todos:list"` dùng chung cho mọi user và không invalidate khi create. Ngoài ra phát hiện `backend` container crash lần khởi động đầu (`ConnectionRefusedError` tới Postgres) do thiếu healthcheck — đúng bug Tier 3B. |
| 2026-09-15 (sau khi sửa hết backend Tier 1) | Backend pytest | `pytest tests/ -v` | 22 passed, 0 failed | Toàn bộ 9 test cũ + 13 test mới đều xanh. `flake8 app/` sạch. |
| 2026-09-15 (sau khi sửa hết Tier 1 backend + frontend) | Playwright E2E | `npx playwright test` | 3 passed, 0 failed | Cả full-journey và 2 kịch bản cross-user-isolation đều xanh. (Lúc này Tier 3B chưa áp dụng nên vẫn phải `docker compose up -d backend` lại 1 lần sau khi Postgres sẵn sàng.) |
| 2026-09-15 (sau khi áp dụng Tier 3B) | Docker cold boot | `docker compose down -v && docker compose up -d --build` | Tất cả 4 service lên `healthy`, không cần can thiệp thủ công | Xác nhận healthcheck + `condition: service_healthy` giải quyết đúng race condition cold-boot. |
| 2026-09-15 (Tier 3C, trước khi đánh index, DB đã seed 10,000 users / 1,000,000 todos) | `EXPLAIN ANALYZE` (Postgres) | 3 câu query cốt lõi (list phân trang, count, count theo `completed`) | Cả 3 đều `Seq Scan`, 27.98-34.69 ms | Xem chi tiết plan đầy đủ tại `docs/DB_PERFORMANCE_BENCHMARK.md`. |
| 2026-09-15 (Tier 3C, sau khi đánh index) | `EXPLAIN ANALYZE` (Postgres) | Cùng 3 câu query, sau `alembic upgrade head` | Cả 3 đều `Index/Bitmap/Index Only Scan`, 0.09-0.75 ms (~46x-329x nhanh hơn) | — |
| 2026-09-15 (final regression, toàn bộ Tier 1-3 đã commit) | Backend pytest | `pytest tests/ -v` | 22 passed, 0 failed | Chạy lại lần cuối trước khi tổng hợp PR. |
| 2026-09-15 (final regression, stack vẫn đang chạy từ trước) | Playwright E2E | `npx playwright test` | 3 passed, 0 failed | Chạy trên stack đã có đầy đủ Tier 3B (healthcheck) + Tier 3C (index) áp dụng. |
| 2026-09-15 (full cold boot lại từ đầu: `docker compose down -v && up -d --build`) | Docker cold boot | `docker compose ps -a` | 4/4 service `healthy`, migration chain chạy đúng từ đầu (xác nhận composite index + unique constraint có mặt qua `\d todos`) | Xác nhận Tier 3B/3C hoạt động đúng trên volume hoàn toàn trống, không chỉ trên DB đã migrate sẵn từ trước. |
| 2026-09-15 (Playwright ngay sau cold boot, DB trống 0 user) | Playwright E2E | `npx playwright test` | **2 passed, 1 failed** | `cross-user isolation persists after logout/login` fail: điền email ngay sau khi click link "Sign up" bị race với React Router client-side navigation, form bị remount làm mất giá trị đã điền → lỗi validate "Invalid email address". Đây là **lỗi trong chính test** (race condition), không phải bug app - đã sửa bằng cách đợi URL chuyển hẳn sang `/register` trước khi điền form. |
| 2026-09-15 (sau khi sửa flaky test) | Playwright E2E | `npx playwright test` (chạy lặp lại 3 lần liên tiếp) | 3 passed, 0 failed cả 3 lần | Xác nhận fix ổn định, không còn flake. |
