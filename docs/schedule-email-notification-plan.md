# Plan: SMTP Settings và email kết quả task theo lịch

Ngày: 2026-09-14  
Trạng thái: Đã triển khai MVP trong mã nguồn; chưa cấu hình SMTP hoặc gửi email thật.

## 1. Yêu cầu và cách hiểu

1. Thêm cấu hình email trong Settings: **SMTP server, email, password/app password key**.
2. Mỗi schedule có tùy chọn gửi email sau khi task kết thúc:
   - Tên người nhận và địa chỉ email người nhận.
   - Tiêu đề do người dùng nhập; có giá trị gợi ý tự điền.
   - Nội dung thư tự động là **summary cuối task**.
   - Một file **`.txt` chứa log tất cả các bước đã thực hiện**.

“stmp” được hiểu là SMTP. “Tự động fill nội dung” được hiểu là body lấy summary,
không đưa toàn bộ summary vào Subject. Form sẽ ghi rõ cách hoạt động này.
MVP hỗ trợ một người nhận mỗi schedule; nhiều người nhận/CC/BCC là yêu cầu riêng.
Tất cả phần gửi mail mặc định OFF; không tự bật cho các schedule đã tồn tại.

## 2. Source hiện có và điểm tích hợp

Khảo sát source, chưa có triển khai SMTP được xác minh trong luồng này.

| Source | Điểm tái sử dụng/mở rộng |
| --- | --- |
| `apps/showcase_ui/src/app/pages/home/home.component.{ts,html}` và `settings-layout.scss` | Settings đang có tab dọc General, AI Model, Android Devices, System & Environment; thêm tab Email |
| `apps/showcase_ui/src/app/pages/task-schedule/task-schedule.component.{ts,html,scss}` | Form New/Edit Schedule, preview và lịch sử; thêm Email notification riêng, không khôi phục Advanced task options đã bỏ |
| `apps/showcase_ui/src/app/core/models/schedule.model.ts`, `services/schedule.service.ts` | DTO lịch, request lưu/sửa, trạng thái history |
| `apps/admin_console/schemas/schedule_schema.py` | ScheduleCreate/Patch và task snapshot; bổ sung notification policy |
| `apps/admin_console/database/repositories/schedule_repository.py` | `update_run_by_session` chuẩn hóa success thành completed và ghi finished_at cho completed/failed/cancelled |
| `apps/admin_console/services/scheduler_service.py` | Tick/lifecycle và lease; email cần worker riêng không block dispatch |
| `apps/admin_console/services/task_queue_service.py`, `services/ipc_service.py` | Cần khảo sát thứ tự session end, worker exit, flush log trước khi chốt hook kết thúc |
| `apps/admin_console/database/repositories/session_repository.py`, `step_repository.py`, `trace_repository.py` | Nguồn session, step và trace; tạo bản export đầy đủ thay vì chỉ lấy log đang hiển thị trên UI |
| `artemis/data_engine/storage.py` | Bootstrap/migration SQLite; sessions cơ bản chưa có cột final_summary chuyên biệt trong đoạn schema đã khảo sát |
| `apps/admin_console/routers/system.py`, `core/security.py`, `server.py` | Boundary local-only/Host/Origin, lifecycle worker, API settings |

Không mặc định dùng cột `steps.summary` làm summary cuối task: đây có thể là summary từng bước.
P0 phải xác định final report Flash/Pro đang được lưu ở đâu và nguồn nào là authoritative.

## 3. UX: Settings → Email

Thêm tab **Email** vào sidebar Settings, không thay đổi thanh Home/Workspace/Task Schedule/Settings.

### Field cấu hình

| Field | Quy tắc |
| --- | --- |
| Email notifications | Công tắc toàn cục; OFF ngăn gửi nhưng không ảnh hưởng task |
| SMTP host | Hostname hoặc IP, không nhận URL/path hoặc shell command |
| SMTP port | Số nguyên 1–65535; gợi ý 587 cho STARTTLS, 465 cho SSL/TLS |
| Security | STARTTLS hoặc SSL/TLS; bắt buộc TLS, không fallback về plaintext |
| Sender email | Địa chỉ From hợp lệ |
| Sender name | Tùy chọn, ví dụ ARTEMIS |
| SMTP username/email | Mặc định bằng Sender email, cho phép khác nếu nhà cung cấp yêu cầu |
| Password / App password | Input password, write-only; hướng dẫn dùng app password nếu nhà cung cấp yêu cầu |
| Test recipient | Địa chỉ nhận email thử, mặc định sender; chỉ gửi khi người dùng bấm Send test email |

- Nút **Save**, **Test connection** và **Send test email** có trạng thái pending/success/error
  ngay trong panel Email. Test connection chỉ TCP/TLS/auth, không gửi mail.
- Test dùng cấu hình đã lưu; nếu form có thay đổi chưa lưu, yêu cầu Save trước để tránh kiểm tra nhầm.
- API đọc chỉ trả `password_configured`, không trả mật khẩu hoặc chuỗi masked có thể bị lưu nhầm.
- Password để trống khi Edit = giữ secret cũ. Nút Clear password là hành động riêng có xác nhận.
- Nếu thay host/username, yêu cầu xác nhận giữ secret hoặc nhập secret mới trước Save/Test;
  không tự gửi mật khẩu cũ tới SMTP host vừa thay đổi.
- Hiển thị thời điểm/lỗi test gần nhất và nhắc cấu hình lưu thành công chưa chứng minh mail đã vào inbox.
- Các request được disable khi đang gửi; lỗi auth/TLS/timeout hiển thị rõ, không chứa secret/server transcript.

## 4. UX: New/Edit Schedule → Email notification

- Công tắc **Send email when task finishes**, mặc định OFF.
- Khi ON: Recipient name (tùy chọn), Recipient email (bắt buộc), Subject (bắt buộc).
- Gợi ý Subject: `ARTEMIS — {schedule_name} — {status}`; sau khi người dùng sửa không tự ghi đè.
  Chỉ hỗ trợ whitelist placeholder `{schedule_name}`, `{status}`, `{finished_at}`; không dùng
  template engine có thể thực thi biểu thức. Người dùng có thể nhập subject tĩnh hoàn toàn.
- Phần body chỉ đọc: “Automatically filled with the task's final summary after completion”.
- Attachment cố định: “Full execution log (.txt), with secrets redacted”.
- Preview next 5 chỉ xem lịch chạy, **không gửi email**. Có thể có preview email riêng bằng dữ liệu
  minh họa ghi rõ là mẫu; summary thật chỉ có khi task kết thúc.
- Email ON nhưng SMTP chưa sẵn sàng: báo ngay trong form, có link Settings → Email;
  không báo lỗi form ở trang danh sách phía sau. Lưu draft thông báo OFF vẫn được.
- Khi Save ON, hiển thị rõ người nhận và cảnh báo summary/log sẽ rời máy qua SMTP đã cấu hình.
  Không tự trích xuất recipient từ task goal, kết quả LLM hoặc nội dung app.
- History thêm trạng thái email: Pending/Sending/Accepted by SMTP/Failed/Unknown/Suppressed,
  thời gian, lỗi an toàn và Retry email khi phù hợp. Retry email không chạy lại task Android.
- Nút Run now của schedule tuân thủ cùng email policy; task chạy trực tiếp ở Home/MCP ngoài
  schedule không tự nhận chính sách gửi email này.

## 5. Trigger, thời điểm và nội dung thư

### Task kết thúc

- Gửi cho các occurrence của schedule có session kết thúc `completed`, `failed`, `cancelled`.
  Thất bại/hủy cũng cần báo kết quả; task failed không bị đổi sang completed vì gửi email thành công.
- Không gửi cho running/paused; pause model không phải hoàn tất.
- Mốc `skipped_misfire`, `skipped_overlap`, `blocked` hoặc `expired` trước khi task chạy
  không có log thực thi: MVP ghi history, không gửi email “task completed”. Có thể bổ sung
  thông báo lỗi scheduler riêng sau này.
- Freeze người nhận/subject/enabled trong notification snapshot của occurrence lúc enqueue.
  Edit lịch không đổi người nhận cho task đã chạy. Pause/Delete lịch không hủy thông báo của
  task đã chuyển giao; công tắc global OFF là cách chặn gửi pending ở bước dispatch cuối.

### Chờ dữ liệu hoàn tất

- Terminal event tạo notification intent, chưa gọi SMTP trực tiếp.
- Chỉ materialize report sau final summary + step/trace persistence barrier.
  Dùng worker exit/flush acknowledgment đã xác minh, không chỉ sleep cố định rồi đoán log đã đầy đủ.
- Recovery scanner tìm terminal runs chưa có notification intent khi server restart hoặc SSE bị mất.
  Hook/reconcile phải dùng cùng unique key để không tạo thêm email cho cùng kết quả.
- Sau crash không có final report: dùng status + lỗi kết thúc đã ghi nhận làm summary dự phòng,
  ghi rõ “No final summary was produced”; không tự suy diễn thành công hoặc gọi thêm LLM để viết lại.
- Nếu không chứng minh log đã flush hoặc bị thiếu, giữ pending tới timeout đề xuất 60 giây;
  sau đó báo `report_incomplete` trong lịch sử để người dùng retry/review, không gửi file thiếu
  mà gọi là full log. Task crash có thể gửi log toàn bộ **các bước đã được ghi nhận**, kèm nhãn
  “Run terminated unexpectedly; unpersisted events may be unavailable”.

### Body

UTF-8 plain text làm chuẩn (HTML escaped có thể bổ sung sau):

```text
Hello <Recipient name>,

Schedule: <schedule name>
Result: <completed / failed / cancelled>
Started: <local time + timezone>
Finished: <local time + timezone>
Session ID: <session ID>

Summary:
<final task summary, secrets redacted>

The attached text file contains the recorded execution steps.
```

Không chèn link localhost làm link xem kết quả cho người nhận trên máy khác.
Subject/header/filename phải chống CRLF injection, có giới hạn chiều dài và encode Unicode đúng.

## 6. File đính kèm: log toàn bộ các bước

Tên đề xuất: `artemis_<session-id>_<YYYYMMDD_HHMMSS>.txt`, không lấy đường dẫn từ người nhận/LLM.
Định dạng UTF-8 (kiểm tra Windows Notepad), newline thống nhất, MIME `text/plain; charset=utf-8`.

Nội dung:

1. Tên schedule, session ID, device, profile/model thực tế, bắt đầu/kết thúc, kết quả.
2. Summary cuối task và trạng thái completeness của report.
3. Startup milestones và các bước theo step index + timestamp ổn định.
4. Mỗi bước: thời gian, action/tool name, tham số, kết quả/lỗi, retry/fallback,
   tool calls con và kết quả kiểm tra có liên quan.
5. Các sự kiện cuối phiên: final report, cancellation/failure, cleanup được ghi nhận.

Nguồn ưu tiên: DB step/trace ledger gốc theo session, không dùng trang UI đang phân trang,
không chỉ lấy compressed context summaries. P0 kiểm tra repository method có giới hạn/clipping
payload hoặc xóa field để xây exporter không bỏ bước. Nếu cần đọc `stdout.log`, chỉ đọc file
trong session directory đã resolve/allowlist; không đính kèm daemon log chung của mọi task.

“Toàn bộ log” nghĩa là đủ các bước/sự kiện thực thi được lưu, **không có mật khẩu/API key,
cookie/token, ảnh/video/base64 hoặc raw internal model reasoning**. Lưu action, kết quả và
thông báo tiến trình user-visible cần thiết; ảnh chỉ ghi tên/tham chiếu nội bộ, không đính kèm ảnh.
Mask secrets trong task instructions, tham số nhập văn bản, tool output, summary và URL có token.
Không giảm report xuống vài dòng summary hay âm thầm cắt bớt bước.

Giới hạn attachment đề xuất 10 MiB, tính thêm overhead MIME/base64 với giới hạn provider.
Nếu vượt ngưỡng: notification `attachment_too_large`, không gửi file bị cắt; UI cho export
local/review và chỉnh policy sau. Chia file/ZIP nằm ngoài yêu cầu một file `.txt` của MVP.

## 7. Kiến trúc và dữ liệu

Luồng: terminal schedule run → durable email outbox → report exporter/redaction → SMTP worker
→ notification status trong Schedule History. Worker độc lập không giữ device lock hoặc chặn queue task.

### Thành phần đề xuất

- `apps/admin_console/schemas/email_schema.py`, `routers/email_settings.py`.
- `services/email_settings_service.py`, `email_notification_service.py`, `smtp_service.py`,
  `task_log_export_service.py`, `notification_redaction.py`.
- `database/repositories/email_notification_repository.py`; migration trong storage hiện có.
- Frontend `components/email-settings/`, email DTO/service và phần Email notification trong form lịch.
- Quản lý worker bằng lifecycle `server.py`; SMTP I/O blocking chạy qua thread/executor có timeout,
  không gọi trực tiếp trên event loop. Không dùng subprocess gửi mail hoặc shell command.

### Settings/secret

- Metadata SMTP không bí mật: host, port, security, username, sender email/name, enabled, version.
- Secret chỉ lưu phía backend: Windows Credential Manager hoặc DPAPI current-user;
  dùng một abstraction secret store, chọn implementation sau khi khảo sát dependency.
- Không lưu plaintext vào DB, repo, `.env.example`, command line hoặc localStorage.
  Không tạo encryption key cạnh ciphertext rồi coi như đã bảo vệ secret.
- Không có secure backend trên OS khác: báo unsupported/required setup hoặc dùng OS keyring
  đã cấu hình; không fallback plaintext. Start with Windows phải đọc được secret dưới cùng tài khoản.

### Schedule snapshot

Thêm `email_enabled`, `recipient_name`, `recipient_email`, `email_subject` vào schedule DTO/storage
và notification snapshot của run. Không nhúng SMTP password trong snapshot.
Run hiện có mặc định notification OFF khi migration; không backfill gửi mail lịch sử.
SMTP configuration version được gắn vào intent; nếu host/account đổi trước khi gửi,
đánh dấu cần review thay vì âm thầm đổi đích cung cấp mail. Credential rotation cùng host/account
có thể dùng secret mới; global OFF luôn được kiểm tra trước gửi.

### Outbox

`task_email_notifications`: UUID, schedule_run_id, session_id, notification_type,
recipient snapshot, rendered_subject/body, report metadata/path/hash, SMTP config version,
status, attempt_count, next_attempt_at, claim_owner/lease, message_id, accepted_at,
safe_error_code/message, created_at/updated_at.

- Unique `(schedule_run_id, notification_type)` ngăn tạo nhiều intent.
- Một active send lease cho notification, kể cả nhiều daemon 8000/8009 cùng DB.
- Chỉ claim/update trong transaction ngắn; build report và SMTP ngoài transaction.
- Report snapshot đã redacted được giữ ổn định qua retries; file tạm có ACL/restricted access,
  cleanup theo retention đề xuất 7 ngày sau terminal email status; không xóa source traces.
- Không expose body/full log trong API danh sách. Download report cần boundary tương đương
  session detail và đường dẫn allowlist theo server, không nhận path tùy ý.

## 8. Retry và chống gửi trùng

- Tối đa 3 lần gửi tổng cộng, backoff đề xuất 30 giây rồi 2 phút cho lỗi tạm thời xác định
  chưa được SMTP chấp nhận, ví dụ connect failure hoặc SMTP 4xx.
- Auth sai, TLS/certificate lỗi, recipient invalid/SMTP 5xx: lỗi terminal có hướng dẫn,
  không loop tới khi khóa tài khoản mail.
- Stable Message-ID theo notification; **Message-ID không đảm bảo SMTP dedup**.
- Nếu mất kết nối sau DATA hoặc process crash sau khi server đã nhận nhưng trước DB commit:
  `delivery_unknown`, không tự retry mù. Retry do người dùng xác nhận có cảnh báo có thể trùng.
- SMTP 250 sau DATA = `accepted_by_smtp`, không phải chứng minh người nhận đã nhận/inbox.
  Bounce/spam filtering ngoài MVP; ghi ngôn ngữ đúng trong UI.
- Tắt global email suppress pending notifications; bật lại không phát lại backlog cũ tự động.
- Gửi email lỗi không sửa kết quả task và không tạo lại task Android.

## 9. API dự kiến

| API | Mục đích |
| --- | --- |
| `GET /api/settings/email` | Metadata + password_configured, không secret |
| `PUT /api/settings/email` | Save config/password thay thế, version check |
| `DELETE /api/settings/email/password` | Xóa secret theo hành động rõ ràng |
| `POST /api/settings/email/test-connection` | Test SMTP/TLS/auth với cấu hình đã lưu |
| `POST /api/settings/email/send-test` | Gửi email thử không chứa task/log, cần recipient rõ ràng |
| Schedule create/update APIs hiện có | Lưu per-schedule email policy |
| `GET /api/schedules/{id}/runs` | Bổ sung trạng thái notification |
| `POST /api/schedules/{id}/runs/{run_id}/email/retry` | Retry đúng notification, không chạy task |
| `GET /api/schedules/{id}/runs/{run_id}/email/report` | Download bản log đã redacted để review |

SMTP config/test endpoints local-only với exact same-origin cho browser; rate limit test/send/retry.
Không dùng cờ remote ADB để vô tình cho phép sửa SMTP từ remote. Allow SMTP nội bộ khi người dùng
cấu hình rõ, nhưng chỉ kết nối đúng host/port đã lưu, không nhận URL/path qua test request.
Địa chỉ email/subject validate phía backend; password không trả về lỗi validation hoặc logs.

## 10. An toàn khi gửi dữ liệu ra ngoài

- Bật email là opt-in riêng mỗi schedule; show recipient/sender và phạm vi summary + full step log.
- Recipient chỉ từ form đã lưu; không làm theo instruction trong log hoặc output LLM để đổi địa chỉ,
  thêm BCC, attach file hay gửi thêm mail.
- Redact cả structured fields và free text; có danh sách secret biết trước trong memory để exact-mask,
  và bộ lọc pattern cho password/token/header. Không log secret lookup.
- Redaction không thể bảo đảm phát hiện mọi thông tin cá nhân. UI phải cảnh báo log vẫn có thể chứa
  dữ liệu app nhạy cảm; cho phép preview/download sanitized report và dùng task vô hại khi test.
- Nếu redaction/exporter lỗi, fail closed: không gửi raw attachment để “bù”.
- Không có screenshot/video/audio đính kèm trong MVP.

## 11. Các bước triển khai

- [ ] **P0 — Trace lifecycle:** xác định nguồn final summary Flash/Pro, complete log export,
  startup/end/flush ordering, cancelled/crashed behavior, secret store Windows và migration strategy.
- [x] **P1 — SMTP Settings:** schema/API/local boundary, secure secret persistence, Email tab,
  Save/Test connection/Send test với lỗi inline và password write-only.
- [ ] **P2 — Schedule form:** opt-in, recipient name/email, subject, validation,
  notification snapshot/version; không tái tạo Advanced task options.
- [ ] **P3 — Report:** deterministic text exporter, final summary extraction/fallback,
  secret redaction, completeness marker, size limit, safe filename/path, Unicode.
- [ ] **P4 — Delivery:** terminal hook + reconcile scanner, outbox/lease, SMTP TLS worker,
  bounded retry/unknown outcome, global kill switch và cleanup.
- [ ] **P5 — History:** notification badge/detail, report review/download và retry riêng,
  không làm thay đổi task status.
- [ ] **P6 — QA/build/docs:** full regression, SMTP sandbox integration, build UI,
  hướng dẫn app password, security warning và rollback.

## 12. Kiểm thử và nghiệm thu

| Nhóm | Ca bắt buộc |
| --- | --- |
| Settings | Password write-only, blank giữ secret, clear rõ ràng, host/account change, unsupported secret store, Start with Windows cùng user |
| Form | Email OFF mặc định, invalid recipient, CRLF subject/name, không có SMTP, lỗi inline New/Edit, Preview 5 không gửi mail |
| Report | Nhiều bước/trace con, retry/fallback, Flash/Pro, summary thật, thiếu summary, crash, tiếng Việt, payload lớn, không thiếu trang/step |
| Redaction | Password trong task goal/tool input/output/summary, Authorization/Cookie, URL token, raw log chứa key, exporter/redactor lỗi không gửi |
| Trigger | completed/failed/cancelled gửi; paused không gửi; skipped/blocked trước thực thi không gửi; Run now đúng policy |
| Idempotency | Duplicate terminal events, restart, hai daemon, timeout trước DATA, mất ack sau DATA, manual retry và request double-click |
| SMTP | SSL/TLS, STARTTLS bắt buộc, cert mismatch/expired, auth failure, 4xx/5xx, attachment limit, accepted không gọi delivered |
| Regression | Task Queue/Schedule/Live view không chậm/block; task success giữ success dù SMTP fail; migration không gửi lại lịch sử |

Unit tests mock SMTP/secret store/fake clock, không ghi credentials thật hoặc gửi tới người nhận thật.
Integration dùng SMTP sandbox local với TLS test certificate được trust rõ ràng; không tắt certificate
verification trong production. UI tests có HttpTestingController để không gây external sends.

Mobile E2E nếu cần: chạy `adb devices -l`, hỏi serial khi nhiều thiết bị, khám phá bằng ARTEMIS trước
khi viết test dựa trên hành vi Android; lỗi dùng `mobile_diagnose` trước. Chọn workflow vô hại,
không gửi log tài khoản cá nhân ra ngoài để kiểm thử. Chỉ gửi email thật khi người dùng xác nhận
cụ thể địa chỉ nhận và nội dung/file sẽ gửi.

Nghiệm thu: nhận đúng một notification intent mỗi run, đúng người nhận snapshot, body chứa final
summary, `.txt` chứa đủ các bước được lưu theo thứ tự sau redaction, email status riêng rõ ràng,
không rò secret hoặc âm thầm bỏ attachment. Những trường hợp delivery unknown phải hiển thị thật.

## 13. Build và rollout

- Plan này không cần build/restart, không thay đổi SMTP/Windows/schedule hiện tại.
- Triển khai thật: migration idempotent + backend tests; frontend tests và `npm run build`
  trong `apps/showcase_ui`; bundle/wheel resources theo quy trình đóng gói hiện có.
- Restart daemon sau khi task đang chạy kết thúc, refresh Settings/Task Schedule.
- Rollout global OFF, cấu hình SMTP trong Email tab, test bằng recipient đã chấp thuận,
  rồi mới opt-in từng schedule. Không tự bật hàng loạt lịch cũ.
- Rollback: tắt global sender/worker, giữ notification history và source traces;
  không xóa SMTP credentials trừ khi người dùng chọn Clear password.
