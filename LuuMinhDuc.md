# Báo cáo tổng hợp — Fabbi Todo App Assessment

Ứng viên: Lưu Minh Đức. Nhánh làm bài: `assessment/DucLM` (đã push lên fork
`https://github.com/MinhDuc2811/test-FABBI.git`). Tổng cộng 25 commit atomic theo Conventional
Commits, bao phủ đủ Tier 1 → Tier 4 (Tier 4 là phần bonus, hoàn thành thêm sau khi xong 3 tier bắt
buộc). Chi tiết từng phần bên dưới; phần cuối cùng ghi lại rõ quy trình/prompt đã dùng với AI theo
đúng yêu cầu công khai của README.

---

## Tier 1 — Các lỗi đã tìm ra & sửa

Tổng cộng 12 lỗi đã sửa (10 backend, 2 frontend), cộng thêm 4 mục nhỏ chỉ ghi chú chứ chưa sửa
(liệt kê ở cuối). Format theo đúng cấu trúc README yêu cầu: Vị trí / Mức độ / Nguyên nhân / Đề xuất sửa.

---

### 1. Refresh token dùng được thẳng như access token

- **Vị trí**: `backend/app/api/deps.py`, hàm `get_current_user()` (dòng 16-51)
- **Mức độ**: Critical
- **Nguyên nhân**: Hàm decode bearer token và lấy `sub` ra dùng, nhưng không hề kiểm tra claim
  `type` của token. `create_access_token`/`create_refresh_token` trong
  `backend/app/core/security.py` đều có gắn field `"type"` (`"access"` hoặc `"refresh"`), nhưng
  không có chỗ nào enforce nó. Vì vậy refresh token — sống 7 ngày (`REFRESH_TOKEN_EXPIRE_DAYS`),
  so với access token chỉ 30 phút — có thể dùng thẳng để gọi **bất kỳ** endpoint nào cần xác thực,
  chứ không chỉ riêng `POST /auth/refresh`. Điều này kéo dài đáng kể thời gian một refresh token bị
  lộ vẫn còn giá trị sử dụng, làm mất hết ý nghĩa của việc dùng access token ngắn hạn.
- **Đề xuất sửa**: Trong `get_current_user`, sau khi decode xong, trả về 401 nếu
  `payload.get("type") != "access"`.

### 2. JWT không bao giờ kiểm tra hết hạn

- **Vị trí**: `backend/app/core/security.py`, hàm `verify_token()` (dòng 49-60)
- **Mức độ**: Critical
- **Nguyên nhân**: `jwt.decode(..., options={"verify_exp": False})` tắt hẳn việc kiểm tra hết hạn.
  Mọi access token và refresh token do app cấp ra đều có hiệu lực vĩnh viễn, bất kể claim `exp` là
  gì — logout, hết phiên, hay chính sách access token 30 phút chỉ mang tính hình thức, không có
  tác dụng thật.
- **Đề xuất sửa**: Bỏ option `verify_exp: False` đi; khối `except JWTError` sẵn có đã đủ để bắt
  `ExpiredSignatureError` (vốn kế thừa từ `JWTError`).

### 3. Lỗ hổng phân quyền theo object (IDOR) trên todos

- **Vị trí**: `backend/app/services/todo_service.py`, hàm `get_todo_by_id()` (dòng 42-44); được
  gọi từ `backend/app/api/v1/todos.py` ở `get_todo` (dòng 95), `update_existing_todo` (dòng 114),
  và `delete_existing_todo` (dòng 145)
- **Mức độ**: Critical
- **Nguyên nhân**: Câu query là `SELECT * FROM todos WHERE id = :todo_id`, không hề kiểm tra quyền
  sở hữu. Bất kỳ user nào đã đăng nhập cũng có thể đọc, sửa, hoặc xoá todo của người khác chỉ bằng
  cách đoán hoặc dò UUID.
- **Đề xuất sửa**: Lọc thêm điều kiện `(id = :todo_id AND user_id = :current_user_id)`. Khi không
  khớp thì trả về 404 thay vì 403, để không lộ thông tin resource đó có tồn tại hay không.

### 4. Redis cache dùng chung cho mọi user & không bao giờ bị xoá khi ghi dữ liệu

- **Vị trí**: `backend/app/api/v1/todos.py` — `list_todos` (dòng 37: `cache_key =
  "todos:list"`), `create_new_todo` (dòng 77-85, thậm chí không có dependency `redis`),
  `update_existing_todo` và `delete_existing_todo` (dòng 111/142 có inject `redis` nhưng không hề
  gọi `.delete()`)
- **Mức độ**: Critical
- **Nguyên nhân**: Một cache key duy nhất dùng chung cho tất cả user và mọi tổ hợp page/size. User
  B có thể thấy được danh sách todo đã cache của User A; các trang phân trang đè lẫn nhau; và vì
  create/update/delete không hề invalidate cache, todo mới tạo sẽ không hiện ra cho tới khi TTL
  5 phút hết hạn.
- **Đề xuất sửa**: Đặt cache key theo từng user, page, size
  (`todos:list:{user_id}:{version}:{page}:{size}`), và duy trì 1 "version" riêng cho từng user,
  tăng version này mỗi khi create/update/delete để vô hiệu hoá toàn bộ cache cũ của user đó chỉ
  bằng 1 lần ghi.

### 5. Logic partial update xoá mất field & bỏ qua `completed: false`

- **Vị trí**: `backend/app/api/v1/todos.py`, hàm `update_existing_todo` (dòng 121-132)
- **Mức độ**: Critical
- **Nguyên nhân**: `todo_data.model_dump()` được gọi mà không có `exclude_unset=True`, nên
  `description` luôn có mặt trong dict kết quả — là `None` nếu client không gửi lên — và bị ghi đè
  lên giá trị cũ, âm thầm xoá mất description khi chỉ update title. Ngoài ra,
  `if todo_data.completed: todo.completed = todo_data.completed` coi `completed: false` là falsy
  nên bỏ qua luôn, khiến 1 todo có thể đánh dấu hoàn thành nhưng không bao giờ đánh dấu lại thành
  chưa hoàn thành được qua API.
- **Đề xuất sửa**: Dùng `model_dump(exclude_unset=True)` và chỉ áp dụng đúng những key thực sự có
  trong request; kiểm tra bằng membership (`"completed" in update_data`) thay vì truthiness.

### 6. Lộ thông tin user (user enumeration) khi login

- **Vị trí**: `backend/app/api/v1/auth.py`, hàm `login()` (dòng 46-66)
- **Mức độ**: High
- **Nguyên nhân**: Email chưa đăng ký thì trả về `404 "User with this email not found"`, còn email
  đúng nhưng sai password thì trả `401 "Incorrect password"`. Status/message khác nhau này cho
  phép kẻ tấn công dò được email nào đã đăng ký trong hệ thống.
- **Đề xuất sửa**: Cả 2 trường hợp đều trả về cùng `401 "Incorrect email or password"`.

### 7. `/auth/refresh` không kiểm tra user còn tồn tại hay không

- **Vị trí**: `backend/app/api/v1/auth.py`, hàm `refresh_token()` (dòng 77-99)
- **Mức độ**: Medium
- **Nguyên nhân**: Endpoint lấy thẳng `sub` từ refresh token đã decode rồi cấp token mới, không hề
  kiểm tra xem user đó có còn tồn tại trong database không — khác với `get_current_user` là có làm
  bước này. Một token của tài khoản đã bị xoá vẫn sẽ tiếp tục hoạt động vô thời hạn.
- **Đề xuất sửa**: Tra user theo id; trả về 401 nếu không tìm thấy, trước khi cấp token mới.

### 8. Cấu hình CORS sai

- **Vị trí**: `backend/app/main.py`, phần cấu hình `CORSMiddleware` (dòng 29-35)
- **Mức độ**: Medium
- **Nguyên nhân**: `allow_origins=["*"]` kết hợp với `allow_credentials=True` là tổ hợp không hợp
  lệ/không an toàn — trình duyệt sẽ từ chối wildcard origin đi kèm credentials, và nếu tổ hợp này
  thực sự được áp dụng thì coi như mở toang CORS cho 1 API có dùng Authorization header.
- **Đề xuất sửa**: Giới hạn `allow_origins` về đúng danh sách `CORS_ORIGINS` lấy từ env (mặc định
  là origin của frontend).

### 9. Phân trang không có thứ tự xác định

- **Vị trí**: `backend/app/services/todo_service.py`, hàm `get_todos()` (dòng 31)
- **Mức độ**: Medium
- **Nguyên nhân**: Query không có `ORDER BY`, nên Postgres không đảm bảo thứ tự ổn định giữa trang
  1 và trang 2 của cùng 1 danh sách — có thể có dòng xuất hiện ở cả 2 trang hoặc không xuất hiện ở
  trang nào cả.
- **Đề xuất sửa**: `.order_by(Todo.created_at.desc(), Todo.id.desc())` để có thứ tự ổn định, có
  tiêu chí phân định rõ ràng khi trùng `created_at`.

### 10. Query N+1 cho từng todo

- **Vị trí**: `backend/app/api/v1/todos.py`, hàm `list_todos()` (dòng 49, trong vòng lặp build response)
- **Mức độ**: Low (hiệu năng)
- **Nguyên nhân**: Với mỗi todo trong trang, code lại query bảng `users` để lấy `user_id` của todo
  đó — dù `get_todos` đã lọc theo `current_user.id` từ trước, nghĩa là mọi dòng trong trang đều
  thuộc về đúng 1 user đã có sẵn thông tin trong bộ nhớ rồi.
- **Đề xuất sửa**: Dùng thẳng `current_user.email`; bỏ hẳn query lặp lại trong vòng lặp.

### 11. Logout không xoá cache React Query ở frontend

- **Vị trí**: `frontend/src/features/auth/api/auth.ts` (`useLogout`, dòng 46-56),
  `frontend/src/features/auth/hooks/useAuth.ts` (dòng 23-35), `frontend/src/lib/api.ts`
  (interceptor 401, dòng 27-37)
- **Mức độ**: Critical
- **Nguyên nhân**: Cả 3 luồng logout (nút logout, nhánh lỗi của nó, và interceptor 401 của axios)
  đều chỉ xoá token trong localStorage chứ không hề xoá cache của React Query. Vì `["todos"]` và
  `["currentUser"]` không được gắn theo user id, nên một người khác đăng nhập vào cùng trình duyệt
  ngay sau đó có thể thấy thoáng qua dữ liệu todo/profile đã cache của người dùng trước.
- **Đề xuất sửa**: Gọi `queryClient.clear()` ở cả 3 nơi trên, trước khi redirect về `/login`.

### 12. Optimistic update của todo không rollback khi lỗi

- **Vị trí**: `frontend/src/features/todos/api/todos.ts`, hàm `useUpdateTodo()` (dòng 76-101)
- **Mức độ**: Medium
- **Nguyên nhân**: `onMutate` có lưu lại `previousTodos` để phục vụ rollback, nhưng `onError` lại
  bỏ qua context này và không hề khôi phục lại — khi update/toggle thất bại, trạng thái optimistic
  (sai) vẫn hiển thị trên UI cho tới lần refetch thành công tiếp theo.
- **Đề xuất sửa**: Trong `onError`, gọi `queryClient.setQueryData(["todos"], context.previousTodos)`.

---

### Đã ghi nhận nhưng chưa sửa (mức độ nhỏ, ghi lại để minh bạch)

- `backend/requirements.txt`: có 2 package thừa/không rõ nguồn gốc `fastar==0.11.0` và
  `detect-installer==0.1.0`; dùng dư thừa 2 thư viện JWT cùng lúc (`python-jose` và `PyJWT`, nhưng
  code chỉ import `jose`).
- `backend/app/schemas/user.py`: schema `UserLogin` được định nghĩa nhưng không dùng tới (`login`
  đang tái sử dụng `UserCreate`).
- `backend/app/schemas/user.py`: chưa có ràng buộc độ dài/độ phức tạp tối thiểu cho `password`.
- `frontend/src/features/todos/components/TodoList.tsx`: danh sách đang dùng `key={index}` thay vì
  `key={todo.id}` — đã sửa luôn vì chỉ là 1 dòng đơn giản (không tính vào 5 lỗi bắt buộc vì đây chỉ
  là vấn đề thẩm mỹ/best-practice, không ảnh hưởng chức năng).

### Đề xuất tối ưu kiến trúc frontend (chưa áp dụng)

- **Endpoint đang khai báo rải rác trực tiếp trong từng file gọi API**: hiện tại các đường dẫn API
  (`"/todos"`, `"/tags"`, `` `/todos/${id}/tags/${tagId}` ``, `"/auth/login"`, `"/todos/bulk-status"`,
  ...) được hard-code thẳng bên trong từng hook ở `features/todos/api/todos.ts`,
  `features/tags/api/tags.ts`, `features/auth/api/auth.ts` — mỗi lần cần đổi path (vd nâng version
  API `/api/v1` → `/api/v2`, hoặc đổi tên route) phải tìm và sửa ở nhiều file khác nhau, dễ sót/gõ
  sai chuỗi.
- **Đề xuất**: tạo 1 file cấu hình tập trung (vd `frontend/src/lib/endpoints.ts`) khai báo hết toàn
  bộ endpoint dưới dạng hằng số/hàm dựng path (vd `ENDPOINTS.todos.list`,
  `ENDPOINTS.todos.tags(todoId, tagId)`), rồi các file `api/*.ts` chỉ import và dùng từ đây thay vì
  gọi chuỗi trực tiếp trong code. Lợi ích: 1 nguồn sự thật duy nhất cho toàn bộ API surface, dễ rà
  soát/đổi đồng loạt, tránh lệch path giữa các chỗ gọi cùng 1 endpoint.
- Chưa áp dụng trong bài này vì không nằm trong phạm vi các tier yêu cầu — ghi chú lại để làm sau.

---

## Tier 2 — Testing Strategy & Implementation

### 2A. Backend pytest

- File: `backend/tests/test_bugfixes.py` (mới, 13 test) + `backend/tests/test_tags.py` (mới, 13
  test cho Tier 4) + `test_auth.py`/`test_todos.py` (gốc, 9 test) = **35 test, tất cả pass**.
- Viết theo kiểu TDD: mỗi bug ở Tier 1 đều có 1 test viết **trước**, chạy xác nhận FAIL (đỏ) trên
  code gốc, rồi mới sửa code và chạy lại xác nhận PASS (xanh). Bao phủ đủ 5/5 kịch bản README gợi ý
  (JWT hết hạn/giả mạo, authorization boundary, boolean toggle, partial update, cache invalidation)
  — dư so với yêu cầu tối thiểu "≥3".
- Sửa luôn `tests/conftest.py`: đổi Redis mock từ `MagicMock` (luôn trả `None`, khiến toàn bộ logic
  cache không thể test được) thành 1 `FakeRedis` lưu dữ liệu thật trong dict, để test cache có
  nghĩa.

### 2B. Playwright E2E

Setup từ đầu tại thư mục `e2e/` (chưa hề có trong repo gốc). 5 spec file:

1. `full-journey.spec.ts` — register → tạo todo → toggle hoàn thành (cả 2 chiều) → logout.
2. `cross-user-isolation.spec.ts` — 2 kịch bản: (a) 2 browser context riêng biệt, (b) logout/login
   user khác **trên cùng 1 trình duyệt** (kịch bản này mới thật sự test được bug cache-clear ở
   frontend).
3. `tags-and-filters.spec.ts` — tạo tag, gắn tag, lọc theo tag, bulk-select + mark complete (Tier 4).
4. `create-with-tags.spec.ts` — chọn tag ngay lúc tạo todo (Tier 4).

**Điểm đặc biệt**: chạy **baseline trên code gốc chưa sửa** bằng cách tạo 1 `git worktree` riêng
tại commit gốc trên `main`, dựng Docker stack ở đó, chạy Playwright → kết quả **0/3 pass**, cả 3
test đều fail đúng ở bug cache global (bug #4). Đây là bằng chứng "trước khi sửa" thực tế, không
phải suy đoán. Sau khi sửa hết Tier 1, chạy lại trên code đã fix → xanh hết, ổn định qua nhiều lần
chạy lặp lại.

### 2C. Manual Test Plan

`docs/TEST_PLAN.md`, theo đúng `templates/TEST_PLAN_TEMPLATE.md`: 13 test case (TC-01 → TC-13) bao
phủ mọi bug đã sửa + bug cold-boot Docker, kèm 1 mục **Test Execution Log** ghi lại đầy đủ
**thời điểm chạy + lệnh + kết quả** cho từng lần chạy pytest/Playwright/Alembic từ baseline đỏ cho
tới final regression xanh — kể cả 2 lần bắt được lỗi trong chính bộ test (không phải app) khi đang
viết test cho Tier 4, ghi lại rõ nguyên nhân và cách sửa.

---

## Tier 3 — Advanced Engineering Skills

### 3A. Technical Specification (Todo Sharing)

`docs/TODO_SHARING_SPEC.md`, theo `templates/SPEC_TEMPLATE.md`. Thiết kế chia sẻ **toàn bộ danh
sách todo** (không phải từng todo lẻ) cho user khác với quyền Viewer (đọc) hoặc Editor (đọc+ghi):
bảng `todo_list_shares` (unique theo cặp owner/collaborator, chặn tự share bằng CHECK constraint),
API endpoints đầy đủ, ma trận phân quyền, và đặc biệt là chiến lược cache — tái dùng đúng cơ chế
version-stamp đã xây ở Tier 1 để đảm bảo thu hồi quyền có hiệu lực ngay lập tức, không phải chờ TTL.

### 3B. Docker & Infrastructure Optimization

Làm cả 5/5 hạng mục gợi ý (yêu cầu chỉ ≥3):

1. Healthcheck cho `postgres`/`redis` + `depends_on: condition: service_healthy` cho backend —
   **verify thật**: code gốc bị crash-loop khi cold boot (`ConnectionRefusedError` vì Postgres chưa
   kịp sẵn sàng), sau khi sửa thì lên `healthy` ngay từ lần đầu, kể cả từ volume hoàn toàn trống.
2. `backend/Dockerfile` chuyển sang multi-stage, chạy bằng non-root user, thêm `HEALTHCHECK`.
3. `.dockerignore` cho cả `backend/` và `frontend/`.
4. `docker-compose.prod.yml`: không expose port Postgres/Redis ra host, bắt buộc secret qua
   `${VAR:?...}` (fail-fast thay vì âm thầm dùng giá trị mặc định không an toàn của bản dev).
5. Redis yêu cầu password (`--requirepass`), không còn mở tự do trên mạng.

### 3C. Database Performance & Indexing

Seed thật **10,000 user / 1,000,000 todo**. Chạy `EXPLAIN ANALYZE` trước/sau khi thêm composite
index `todos(user_id, completed, created_at)` + unique constraint `users(email)`:

| Query | Trước (Seq Scan) | Sau (Index Scan) | Tăng tốc |
|---|---|---|---|
| List phân trang | 34.69 ms | 0.75 ms | ~46x |
| Đếm theo user | 27.98 ms | 0.11 ms | ~262x |
| Đếm theo trạng thái | 28.94 ms | 0.09 ms | ~329x |

Chi tiết đầy đủ + phân tích trade-off (write latency, ~48MB storage overhead, khuyến nghị
`CREATE INDEX CONCURRENTLY` cho bảng production thật) tại `docs/DB_PERFORMANCE_BENCHMARK.md`.

---

## Tier 4 (Bonus) — Todo Tags, Filtering & Bulk Actions

Hoàn thành thêm sau khi xong Tier 1-3, theo tinh thần "tối đa tái sử dụng code cũ, chỉ sửa đúng chỗ
bị ảnh hưởng":

- **DB**: bảng `tags` (unique tên theo user, **case-insensitive** qua functional index
  `lower(name)`) + bảng liên kết `todo_tags`, cả 2 khai báo cascade delete.
- **Backend**: CRUD tag đầy đủ (tái dùng đúng pattern ownership-check của Tier 1), mở rộng
  `GET /todos` với filter `status/tag_id/keyword/date_from/date_to` (thêm tham số optional, không
  phá vỡ code/test cũ), endpoint `PATCH /todos/bulk-status` (chạy trong 1 transaction, tự loại bỏ
  todo không thuộc về mình), `POST/DELETE /todos/{id}/tags/{tag_id}` (kiểm tra sở hữu cả todo lẫn
  tag). 13 test mới, toàn bộ 4 hook mutation cũ ở frontend **không cần sửa gì** vì cơ chế
  invalidate theo prefix đã đúng sẵn từ Tier 1.
- **Frontend**: module `features/tags/` mới, `FilterBar`/`BulkActionsBar` mới, `TodoItem`/`TodoForm`
  mở rộng để hiển thị và gắn/gỡ tag — hỗ trợ chọn tag **cả lúc tạo lẫn lúc sửa** todo.
- **Verify thật bằng Playwright + screenshot** trên Docker: trong lúc viết test cho tính năng mới,
  bắt được đúng 3 lỗi nằm **trong chính test** (chọn nhầm dòng todo do trùng substring tên, locator
  không scope đúng dialog) — đã sửa và xác nhận lại bằng ảnh chụp thật, không phải giả định.

---

## Git Workflow & Submission

- Nhánh `assessment/DucLM`, tạo từ `main`, **25 commit atomic** theo Conventional Commits, khớp
  `.commitlintrc.json` (`feat|fix|docs|style|refactor|perf|test|build|ci|chore|revert`).
- Đã fork `FabbiDevelopment/test` → `MinhDuc2811/test-FABBI` và push nhánh lên đó
  (`git push -u fork assessment/DucLM`) — xác nhận bằng `git push --dry-run` trước khi push thật.
- PR chưa mở (cần thao tác thủ công trên GitHub UI): mở tại
  `https://github.com/MinhDuc2811/test-FABBI/pull/new/assessment/DucLM`, nhắm `assessment/DucLM` →
  `main` trong chính fork.

---

## Khai báo sử dụng AI & Prompt Log

Theo đúng yêu cầu công khai của README ("If AI coding assistants were used, disclose them and
include any prompt logs or configurations"), toàn bộ phần code/test/docs trong bài này được thực
hiện với **Claude Code (Claude Sonnet 5)**, quy trình cụ thể như sau:

1. **Phân tích yêu cầu**: yêu cầu Claude đọc `README.md` và phân tích chi tiết từng tier, chấm điểm
   ước lượng theo từng mục.
2. **Lên kế hoạch (Plan Mode)**: yêu cầu Claude tự đọc toàn bộ codebase (dùng nhiều agent con khảo
   sát song song backend/frontend/infra), xác định chính xác các bug, rồi trình bày kế hoạch thực
   hiện Tier 1→3 + Git. Kế hoạch được duyệt qua vài vòng góp ý trực tiếp (đổi ngôn ngữ sang tiếng
   Việt, yêu cầu quét kỹ thêm bug, đổi thứ tự ưu tiên để viết Playwright test trước rồi mới sửa bug
   theo kiểu TDD, thêm bước tối ưu song song hoá công việc).
3. **Chạy tự động qua `/loop`**: sau khi thống nhất kế hoạch, từ đó Claude tự kích hoạt skill `/loop` (chế độ tự định nhịp — dynamic mode) để tự chạy nhiều
   vòng lặp liên tục **không cần hỏi lại giữa chừng** cho toàn bộ phần việc cục bộ: sửa bug backend
   theo TDD (viết test đỏ → sửa → xanh), sửa bug frontend, setup Playwright, viết spec Tier 3A, cấu
   hình lại Docker (3B), seed 1 triệu dòng + đánh index + benchmark thật (3C), viết tài liệu test
   plan, và tự commit atomic theo từng bước. Vòng lặp tự dừng khi đạt điều kiện hoàn thành đã đề ra
   trong kế hoạch (test xanh hết, docs/docker/migration đầy đủ, đã commit hết) — **toàn bộ Tier 1
   đến hết Tier 3 được Claude tự thực hiện xuyên suốt trong 1 lần chạy loop này**, người dùng chỉ
   xác nhận kế hoạch ban đầu và không can thiệp vào từng bước nhỏ bên trong.
4. **Tier 4 (bonus)**: sau khi loop hoàn tất Tier 1-3, tiếp tục hỏi Claude phân tích riêng Tier 4, rà lại để tối đa tái sử dụng code cũ. Claude tự viết
   toàn bộ code, tự test bằng Playwright thật trên Docker (bắt được và tự sửa cả bug trong chính
   test lẫn bổ sung tính năng chọn tag lúc tạo todo khi được hỏi thêm).
5. **Vai trò của người làm bài**: định hướng phạm vi và thứ tự ưu tiên ở từng bước (ví dụ: yêu cầu
   ưu tiên test trước khi sửa bug, yêu cầu quét sâu thêm bug, yêu cầu tối ưu tái sử dụng code cho
   Tier 4), duyệt kế hoạch trước khi cho code, và **tự tay review lại toàn bộ output + test thủ
   công trên trình duyệt** sau khi Claude báo cáo hoàn thành — không tự tay gõ code cho phần
   logic nghiệp vụ.

