# Plan: tab Task Schedule để chạy task theo lịch

Ngày: 2026-09-14  
Trạng thái: Đã triển khai MVP trong mã nguồn; chưa tự tạo lịch chạy thật hoặc chạy kiểm thử trên thiết bị.

## 1. Yêu cầu

Thêm tab **Task Schedule** trên thanh điều hướng chính, ngay bên phải **Workspace**, hỗ trợ:

| Chế độ | Cấu hình bắt buộc | Ví dụ |
| --- | --- | --- |
| Interval | Số phút | Mỗi 15 phút |
| Daily | Giờ, phút, giây | Mỗi ngày lúc 08:30:05 |
| Weekly | Một hoặc nhiều ngày trong tuần + giờ, phút, giây | Thứ Hai, Thứ Tư, Thứ Sáu lúc 09:00:00 |

Mỗi lịch gắn với một bản cấu hình task: nội dung, thiết bị, Flash/Pro và các tùy chọn chạy.
Mỗi lần đến hạn tạo một session riêng, xem tiến độ/kết quả trong Task Queue và lịch sử hiện có.

Không thuộc MVP: cron expression, monthly, ngày lễ, lịch kết thúc tùy chỉnh, tác vụ shell tùy ý,
cloud scheduler, tự bật máy/tự đánh thức Windows, gửi email/SMS hoặc thay thế device lock của ARTEMIS.
Đây là tính năng của ARTEMIS Web UI/backend, không phải automation của ứng dụng Codex.

## 2. Hiện trạng và điểm tích hợp

Khảo sát bằng mã nguồn, chưa xác minh tính năng Schedule trên thiết bị vì chưa có triển khai.

| Source hiện có | Nội dung liên quan |
| --- | --- |
| `apps/showcase_ui/src/app/components/nav-switcher/nav-switcher.component.ts` | Thanh Main Navigation có New / Home và Workspace; thêm Task Schedule ngay sau Workspace |
| `apps/showcase_ui/src/app/app.routes.ts` | Đăng ký trang riêng `/task-schedule`, truy cập trực tiếp và refresh được |
| `apps/showcase_ui/src/app/components/chat-interface/chat-interface.component.{ts,html,scss}` | Sidebar Task Queue / Notes & Plans giữ nguyên; không thêm Schedule ở đây |
| `apps/showcase_ui/src/app/services/agent.service.ts` | Gọi `/api/run`, theo dõi session qua polling/SSE; giữ `activeTab` là `tasks | notes` |
| `apps/showcase_ui/src/app/components/agent-stream/agent-stream.component.{ts,html,scss}` | Giữ menu Task Queue/Notes cho vùng hẹp; đường vào Task Schedule thuộc Main Navigation |
| `apps/admin_console/schemas/task_schema.py` | `RunRequest`: goal/goals, profile, expected_output, device_serial, Pro tuning, ingress, session_id |
| `apps/admin_console/routers/tasks.py` | `/api/run` kiểm tra idempotency, thiết bị và readiness trước enqueue |
| `apps/admin_console/services/task_queue_service.py` | `enqueue_tasks`, worker, queue và per-device dispatch; hỗ trợ session_id do caller cung cấp |
| `apps/admin_console/core/state.py` | Trạng thái queue/runtime trong bộ nhớ; không được giả định một mục đã enqueue chắc chắn sống qua restart |
| `apps/admin_console/database/connection.py` và `artemis/data_engine/storage.py` | SQLite, WAL và bootstrap schema; tái sử dụng migration/transaction theo cấu trúc hiện tại |
| `apps/admin_console/database/repositories/session_repository.py` | Lưu và đọc kết quả session; liên kết với lần chạy lịch |
| `apps/admin_console/server.py` | Startup/shutdown daemon; điểm quản lý vòng đời scheduler |

Trong phạm vi source đã xem chưa có scheduler interval/daily/weekly bền vững để tái sử dụng trực tiếp.
Các tên “scheduler” hiện có chủ yếu chỉ worker/queue, không phải lịch lặp theo thời gian.

## 3. UX tab Task Schedule

Vị trí trên thanh điều hướng chính: `New / Home | Workspace | Task Schedule`.
Task Schedule mở trang riêng `/task-schedule`; không nằm trong sidebar Workspace.
Giữ nguyên sidebar `Task Queue | Notes & Plans`, vùng log và cột live view đã tích hợp.
Trang lịch dùng vùng nội dung riêng cho danh sách/form, có khoảng trống cho thanh điều hướng.
Active state theo route; hỗ trợ truy cập URL trực tiếp, refresh và Back/Forward.
Chuyển trang không dừng scheduler hoặc task đang chạy; chỉ teardown subscription của trang.
Link kết quả từ Task Schedule đưa về `/workspace` và chọn đúng session.

### Danh sách lịch

- Nút **New Schedule**, danh sách lịch Active/Paused, empty state hướng dẫn tạo lịch đầu tiên.
- Mỗi thẻ: tên lịch, mô tả ngắn task, rule dễ đọc, timezone, serial/tên thiết bị,
  lần chạy kế tiếp, lần gần nhất và kết quả.
- Thao tác: Edit, Pause/Resume, Run now, Delete (xác nhận).
- Bấm kết quả mở đúng session trong Workspace. Có lịch sử riêng cho lần bị bỏ qua,
  không enqueue được hoặc đang chờ, kể cả khi chưa có session thực thi.
- Hiển thị scheduler health/last heartbeat và nhắc **“Chỉ chạy khi máy và ARTEMIS server đang hoạt động”**.
- Main Navigation và các nút có aria-label, điều khiển bằng bàn phím; ba mục điều hướng
  không tràn viewport hoặc che nút hành động trên màn hình hẹp.

### Form tạo/sửa

1. Tên lịch, nội dung task không rỗng; có thể điền từ một task lịch sử đã chọn,
   nhưng lưu bản sao nội dung chứ không chạy lại cùng session ID.
2. Chọn thiết bị từ `/api/devices`; MVP bắt buộc lưu `device_serial` cụ thể để chạy không giám sát.
   Nếu nhiều thiết bị, người dùng phải chọn; không tự chọn máy đầu tiên.
3. Chọn Flash/Pro và các tùy chọn đang hỗ trợ: expected output, outputter,
   verification level, explorer mode. Không thêm tùy chọn giả mà worker chưa nhận.
4. Loại lịch Interval/Daily/Weekly và field tương ứng.
5. Timezone IANA, đề xuất timezone trình duyệt; hiển thị rõ và cho sửa.
   Môi trường hiện tại có thể dùng `Asia/Bangkok`; không hard-code UTC+7 cho mọi người dùng.
6. Preview 5 lần chạy tiếp theo từ backend trước khi lưu/kích hoạt.
7. Checkbox Enabled; Save lưu/kích hoạt lịch nhưng **không chạy ngay**. Run now là hành động riêng.

Daily/Weekly dùng ba ô giờ/phút/giây hoặc time input `step=1` đã kiểm tra hỗ trợ trên Chrome/Edge.
UI phải hiển thị và gửi cả giây, kể cả `00`; không để native widget âm thầm làm mất giây.
Weekly hiển thị T2–CN, cho chọn nhiều ngày; backend dùng ISO weekday `1=Monday … 7=Sunday`.

## 4. Ngữ nghĩa lịch — quyết định mặc định cho MVP

### Interval

- `interval_minutes` là số nguyên; giới hạn đề xuất 1–10080 phút, kiểm tra cả frontend/backend.
- First run = thời điểm Enable + N phút; anchor được lưu theo UTC.
- Các lần sau tính `anchor + k × N phút`, không tính từ giờ task kết thúc, tránh trôi lịch.
- Ví dụ Enable 10:00:20, N=15: 10:15:20, 10:30:20, 10:45:20.
- Khi thay số phút hoặc Resume, đặt anchor mới = thời điểm xác nhận; UI báo next run mới.
- Thay tên/nội dung task không reset nhịp interval; mỗi lần đã enqueue giữ snapshot cũ.

### Daily/Weekly

- Diễn giải `HH:mm:ss` theo timezone đã lưu; next run được lưu UTC và hiển thị giờ địa phương.
- Next run phải **sau** thời điểm commit/enable; nếu giờ hôm nay đã qua hoặc đúng thời điểm lưu,
  chọn ngày hợp lệ tiếp theo. Weekly không chọn ngày nào là invalid.
- Calendar calculation dùng timezone-aware datetime, không cộng cố định 86400 giây cho daily.
- DST: giờ không tồn tại thì bỏ ngày đó; giờ lặp hai lần thì chạy lần đầu (`fold=0`) một lần.
  Preview phải dùng cùng policy. Kiểm tra timezone database trên Windows; thiếu dữ liệu thì
  báo lỗi cấu hình, không âm thầm dùng UTC. Bổ sung dependency `tzdata` nếu runtime cần.

### Độ chính xác

- Field giây là thời điểm **đến hạn/đưa vào hàng đợi**, không cam kết chạm màn hình đúng giây.
- Đề xuất scheduler tick ≤ 1 giây; mục tiêu lateness p95 ≤ 2 giây trên máy local nhàn rỗi.
- Thời gian chờ thiết bị, readiness và khởi tạo model được đo riêng bằng `started_at - due_at`.
- UI luôn phân biệt Scheduled / Queued / Running; không hiển thị “đã chạy” chỉ vì đến giờ.
- Đo lateness bằng đồng hồ UTC và timer dùng monotonic; sau sleep/clock jump phải tính lại,
  không tin một timer dài trong browser. Backward clock jump không được chạy trùng occurrence.

### Máy tắt, sleep, restart và missed runs

- Backend daemon giữ lịch; browser đóng vẫn chạy nếu daemon/máy/thiết bị còn hoạt động.
- Nếu trễ ≤ 60 giây: cho dispatch một lần còn trong grace window.
- Nếu trễ > 60 giây: ghi `skipped_misfire`, tính mốc tương lai; không phát lại hàng loạt lịch cũ.
- Nhiều mốc bị lỡ được tổng hợp trong một bản ghi/đếm để không tạo hàng triệu hàng khi offline dài.
- Resume Daily/Weekly tính mốc tương lai, không bù các mốc trong lúc Pause.

### Trùng lịch, task dài và thiết bị bận

- Mỗi schedule tối đa một occurrence chưa kết thúc, tính cả claimed/queued/running/paused.
  Đến mốc tiếp theo khi occurrence cũ còn tồn tại: ghi `skipped_overlap`, không nhân backlog.
- Nhiều schedule khác nhau cùng thiết bị dùng queue/DeviceExecutionLock hiện tại; không chạy song song trên một máy.
- Thiết bị bận bởi task khác: đưa vào queue nếu readiness hợp lệ; hết thời hạn chờ đề xuất
  15 phút từ `due_at` thì đánh dấu `expired` trước khi worker bắt đầu, không hủy task đã chạy.
- Thiết bị mất kết nối/unauthorized/khóa hoặc credentials chưa sẵn sàng: occurrence `blocked`
  kèm lý do an toàn; không tự mở khóa, chọn thiết bị khác hoặc cài phần mềm để vượt qua.
  Lịch tương lai vẫn giữ, không retry vô hạn occurrence bị chặn.
- Run now dùng cùng queue/readiness/overlap policy; không dời next scheduled run.
  Idempotency key cho thao tác này ngăn double-click/request retry tạo task lặp.
- Task thất bại không tự chạy lại ngoài retry sẵn có của task; lần đến hạn tiếp theo vẫn diễn ra.

### Pause/Edit/Delete

- Pause/soft-delete chặn occurrence chưa chuyển giao cho queue; không tự dừng task đã enqueue/running.
  UI ghi rõ và cung cấp link tới nút Stop task hiện tại.
- Race với dispatch được phân xử trong transaction theo schedule version;
  sau khi đã committed enqueue intent, UI coi đó là occurrence đã chuyển giao.
- Edit chỉ áp dụng cho occurrence tương lai; claimed/enqueued occurrence giữ snapshot và version cũ.
- Xóa lịch không xóa session/traces lịch sử. `Clear all tasks/history` không xóa schedule;
  thao tác cleanup phải cảnh báo lịch active có thể tiếp tục sinh task.

## 5. Kiến trúc đề xuất

Luồng: Schedule form → Schedule API → SQLite → backend Scheduler → Admission service
→ TaskQueueService → DeviceExecutionLock/worker → Session → Schedule run history.

### Thành phần mới

- Frontend: `pages/task-schedule/task-schedule.component.{ts,html,scss}`,
  `components/schedule-panel/` nếu cần tách list/form, `services/schedule.service.ts`,
  `core/models/schedule.model.ts`. Thêm link Task Schedule trong `nav-switcher.component.ts`
  và route `/task-schedule` trong `app.routes.ts`; không sửa union tab sidebar của AgentService.
- Backend: `schemas/schedule_schema.py`, `routers/schedules.py`,
  `services/schedule_service.py`, `services/scheduler_service.py`,
  `database/repositories/schedule_repository.py` trong `apps/admin_console`.
- Hàm tính `next_run` thuần, độc lập I/O; dùng discriminated union theo `interval/daily/weekly`.
- Tách admission logic hiện có khỏi route `/api/run` thành service dùng chung nếu cần.
  Scheduler gọi service trong process, không tự HTTP loopback và không bỏ qua readiness.
- Tích hợp scheduler vào lifecycle daemon sau DB/queue initialization; shutdown ngừng claim
  trước, chờ dispatch hữu hạn, lưu trạng thái phục hồi, rồi release lease.
- Không dùng `setInterval` trình duyệt làm đồng hồ thực thi; không tạo Windows Task Scheduler job
  riêng cho từng lịch. MVP dùng loop asyncio + DB repository, chưa cần thêm thư viện cron.

### Lưu trữ

**`task_schedules`**: UUID, name, goal/task snapshot, profile, device_serial, tuning JSON,
schedule_type, interval_minutes, time_of_day (`HH:mm:ss`), weekdays JSON, timezone,
interval_anchor_at UTC, enabled, version, next_run_at UTC, created_at, updated_at, deleted_at.

**`task_schedule_runs`**: UUID, schedule_id, schedule_version, due_at UTC, trigger (`scheduled/manual`),
request/idempotency key, task snapshot, status, deterministic session_id, claim owner/lease,
queued_at, started_at, finished_at, safe_error_code/message, lateness_ms.

- Scheduled occurrence unique key `(schedule_id, due_at)`; manual occurrence có request key riêng.
- Index `(enabled, next_run_at)` và `(schedule_id, due_at DESC)`; paginated history.
- Không copy API keys vào bảng lịch. Task text có thể chứa thông tin đăng nhập nên không log
  toàn bộ payload; list API chỉ trả mô tả rút gọn, không cố “che mật khẩu” bằng regex rồi coi là an toàn.
  Detail cần quyền truy cập console như hiện tại; ưu tiên hướng dẫn dùng secret reference khi được hỗ trợ.
- Runtime model config được resolve lúc chạy và lưu thông tin model thực tế vào session như hiện tại;
  schedule lưu profile/tuning, không đóng băng `.env` hoặc API credentials.

### Bền vững và chống chạy trùng

1. Trong transaction ngắn: xác minh enabled/version, claim due occurrence bằng unique key,
   lưu snapshot/session ID, cập nhật next_run_at và trạng thái dispatch intent.
2. Ngoài transaction: admission/readiness hữu hạn rồi enqueue với chính session ID đã lưu.
3. Worker/session cập nhật run history qua liên kết session; retry dispatch dùng cùng ID.
4. Queue hiện nằm trong memory: phải có **durable outbox/enqueue intent** và recovery scanner.
   Không đánh dấu occurrence đã giao xong chỉ vì `enqueue_tasks` trả thành công.
5. Khi restart: reconcile intent với session, trace store và active worker/device lock.
   Chưa từng chạy thì re-enqueue cùng ID; đã chạy thì gắn lại trạng thái, không chạy lại task.
   Nếu không chứng minh được trạng thái sau crash, đánh dấu `needs_attention`, không đoán rồi tái thực thi.
6. Lease scheduler theo canonical DB path, có heartbeat/fencing generation; hai daemon ở 8000/8009
   dùng chung DB không được dispatch cùng occurrence. Device mutex không đủ chống chạy tuần tự trùng.
7. Không giữ SQLite transaction trong lúc chờ ADB/LLM. Test crash ở từng ranh giới commit/enqueue/start.

Mục tiêu là dispatch idempotent và phục hồi an toàn. Không tuyên bố “exactly once” cho thao tác
trên điện thoại, vì tác động bên ngoài có thể xảy ra trước khi trạng thái được ghi xuống DB.

## 6. API dự kiến

| Method/path | Chức năng |
| --- | --- |
| `GET /api/schedules` | Danh sách và next run, status gần nhất |
| `POST /api/schedules/preview` | Validate rule, trả 5 due times; không lưu/chạy task |
| `POST /api/schedules` | Tạo lịch và tính next run tại thời điểm commit |
| `GET /api/schedules/{id}` | Chi tiết lịch |
| `PATCH /api/schedules/{id}` | Sửa, bật/tắt; expected_version chống ghi đè từ tab cũ |
| `DELETE /api/schedules/{id}` | Soft-delete, giữ lịch sử |
| `POST /api/schedules/{id}/run-now` | Một lần chạy thủ công có idempotency key |
| `GET /api/schedules/{id}/runs` | Lịch sử phân trang và session link |
| `GET /api/schedules/status` | Scheduler health, timezone support, last heartbeat |

Đăng ký `/status` và `/preview` trước `/{id}` hoặc dùng UUID path validation để tránh route shadowing.
Thời điểm API dùng ISO 8601 có timezone/UTC, không dùng chuỗi ngày theo locale.
422 cho rule invalid; 409 cho version conflict/overlap; blocked readiness là kết quả có cấu trúc.
Kế thừa Host/Origin boundary/no-store; không mở CORS rộng hoặc cho browser truyền lệnh shell.
Backend chuẩn hóa `ingress="schedule"`, không tin giá trị caller tự khai để bỏ qua kiểm tra.

## 7. Kế hoạch triển khai theo giai đoạn

- [x] **P0 — Xác minh và chốt contract:** schema migration, lifecycle thực tế, duplicate submission,
  per-device queues, session reconciliation, timezone runtime và hành vi cleanup hiện có.
  Chốt các giá trị mặc định 60 giây grace / 15 phút queue expiry / skip overlap trong UI/docs.
- [x] **P1 — Domain/time engine:** schema ba loại lịch, validation, pure next-run calculation,
  timezone/DST, preview và fake clock tests.
- [x] **P2 — Persistence/API:** tables/index/migrations, CRUD/preview/history, optimistic locking,
  soft-delete và bảo vệ dữ liệu task.
- [x] **P3 — Scheduler/queue:** single leader lease, claim/outbox/reconcile, admission dùng chung,
  overlap/misfire/expiry, ingress metadata và session outcome.
- [x] **P4 — Frontend:** Task Schedule cạnh Workspace, route `/task-schedule`, list/form,
  chọn ngày + HH:mm:ss, timezone/preview,
  Pause/Resume/Run now/Delete, history và trạng thái lỗi; responsive/accessibility.
- [ ] **P5 — E2E và rollout:** kiểm tra thiết bị thật, restart/crash/clock jump,
  đóng browser nhưng lịch vẫn chạy, build frontend và smoke test cổng 8009.

## 8. Kiểm thử và nghiệm thu

| Nhóm | Ca bắt buộc |
| --- | --- |
| Interval | N=1, N lớn, invalid 0/âm/lẻ; anchor có giây; task dài không trôi nhịp; resume/edit |
| Daily | Trước/đúng/sau HH:mm:ss, 23:59:59, qua ngày/tháng/năm, năm nhuận |
| Weekly | T2/CN, nhiều ngày, không chọn ngày, qua tuần, khác timezone |
| DST/clock | Giờ mất/lặp, đổi timezone máy, NTP nhảy tiến/lùi, sleep/wake |
| Queue/device | Task trước chưa xong, thiết bị bận bởi lịch khác, offline/locked/unauthorized, queue expiry |
| Persistence | Restart trước claim/sau claim/sau enqueue/trước ack/sau device action; hai daemon dùng chung DB |
| UI/API | Main Navigation đúng thứ tự; route direct/refresh/Back/Forward; sidebar không đổi; mất mạng khi Save/Run now, double-click, validation giây, edit conflict, pause/delete race, không lộ task text trong list logs |
| Regression | Chạy tay/MCP/SDK như cũ; Stop task không tắt schedule; Clear history không xóa schedule; live view vẫn theo session |

Đề xuất files: `tests/unit/admin_console/test_schedule_repository.py`, `test_schedule_api.py`,
`test_scheduler_service.py`, tests cho pure recurrence calculator; frontend spec cạnh component/service.
Fake clock cho unit tests, không sleep vài phút trong test runner.

Trước khi viết mobile/E2E test: chạy `adb devices -l`; nếu nhiều thiết bị phải hỏi người dùng chọn
serial. Dùng ARTEMIS khám phá app/chuỗi trạng thái trước khi viết test; dynamic locator trước,
coordinate fallback chỉ khi đã xác minh; explicit waits có timeout. Nếu ARTEMIS lỗi,
gọi `mobile_diagnose` trước khi thử lại. Không chạy lịch thật trên tài khoản hoặc app có tác động
khó đảo ngược để kiểm thử scheduler; dùng workflow vô hại đã được chấp thuận.

Tiêu chí nghiệm thu:

- Task Schedule nằm ngay bên phải Workspace; trang `/task-schedule` truy cập trực tiếp được,
  không nằm trong sidebar Task Queue/Notes. Chuyển trang không làm dừng task hoặc scheduler.
- Tạo/sửa/bật/tắt đủ ba loại lịch; preview và backend cùng next-run algorithm.
- Weekly nhiều ngày, Daily/Weekly giữ đủ HH:mm:ss và timezone qua restart.
- Mỗi occurrence được liên kết đúng một session ID; không duplicate dispatch khi hai daemon hoặc retry.
- Skip/blocked/expired/misfire hiển thị lý do, không mất lịch âm thầm hoặc tạo backlog vô hạn.
- Scheduler tiếp tục khi browser đóng, dừng khi daemon/máy tắt và phục hồi theo policy đã công bố.
- Ghi rõ lateness/queued delay; đo đạt mục tiêu giây trên local idle thay vì chỉ kiểm tra UI countdown.
- Tests cũ và mới pass, migration idempotent, không mất session/traces cũ.

## 9. Build, vận hành và rollout

- Plan này không cần build hoặc restart. Khi triển khai thật có đổi Angular: chạy frontend tests
  rồi `npm run build` trong `apps/showcase_ui`; chạy backend tests liên quan.
- Migration chạy idempotent lúc startup; sao lưu DB theo cách nhất quán trước migration production.
- Sau khi task đang chạy kết thúc, restart từ thư mục repo:
  `.\.venv\Scripts\artemis.exe restart --port 8009 --no-open`.
- Verify `/api/schedules/status`, trang `/task-schedule`, lịch thử vô hại; không tự tạo lịch trên môi trường
  người dùng chỉ để chứng minh UI hoạt động.
- Log chỉ schedule/run/session IDs, due time, trạng thái và mã lỗi; metrics gồm scheduler lag,
  due/queued/blocked/skipped counts và leader heartbeat, không chứa credentials/task payload.
- Rollback: dừng scheduler producer/feature, giữ các bảng và lịch sử để khôi phục; không xóa DB.
  Task đã chạy quản lý qua Stop task, không kill daemon để giả lập pause lịch.

## 10. Các giới hạn cần thông báo cho người dùng

- Lịch không tự bật Windows hoặc tự mở khóa Android.
- Giờ-phút-giây là thời điểm đến hạn; thiết bị bận có thể làm task bắt đầu muộn.
- Sau restart dài, mặc định bỏ mốc đã lỡ thay vì chạy dồn.
- Schedule bật đồng nghĩa cho phép chạy lại nội dung đã lưu; cần kiểm tra task có phù hợp tự động lặp
  và có thể gây gửi tin, xóa dữ liệu, chấm công hoặc giao dịch ngoài ý muốn hay không.
- Cấu hình thiết bị và model phải hợp lệ khi chạy; lưu lịch thành công không có nghĩa API key/model
  và kết nối Android chắc chắn sẵn sàng ở thời điểm tương lai.
