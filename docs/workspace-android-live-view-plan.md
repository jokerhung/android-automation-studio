# Kế hoạch: Android Live View trong tab Workspace

Ngày: 2026-09-14  
Trạng thái: Đề xuất triển khai — chưa thay đổi tính năng.  
Phạm vi khảo sát: đọc mã nguồn hiện tại; chưa đo FPS, độ trễ hoặc xác minh stream trên thiết bị thật.

## 1. Mục tiêu và phạm vi

Thêm tab **Android Live** bên cạnh **Activity** trong vùng nội dung chính của `/workspace`.
Người dùng xem màn hình Android hiện tại ngay trong Workspace, không cần mở cửa sổ scrcpy riêng.
Giữ sidebar **Task Queue / Notes & Plans**, thanh nhập tác vụ và khả năng xem log hiện có.

MVP là **chỉ xem**. Không thêm tap, swipe, nhập bàn phím, điều khiển nguồn, ghi hình,
tự mở khóa hoặc cài ứng dụng lên điện thoại. Không gửi frame tới LLM hay dịch vụ bên ngoài.
Điều khiển từ xa, WebRTC/H.264 và nhiều màn hình đồng thời là các giai đoạn riêng nếu có yêu cầu.

## 2. Hiện trạng đã xác minh trong source

| Thành phần | Hiện trạng | Hệ quả cho triển khai |
| --- | --- | --- |
| `apps/showcase_ui/src/app/pages/workspace/workspace.component.{ts,html,scss}` | Main panel render trực tiếp `app-agent-stream`; sidebar render `app-chat-interface`; có floating player | Thêm tab ở main panel, không thay đổi sidebar |
| `apps/showcase_ui/src/app/components/floating-video-player/` | Đã có nhánh live dùng `<img>` với `/api/stream/device-live`, nhánh replay riêng | Tách viewer dùng chung; không nhân đôi logic live/reconnect |
| `apps/admin_console/routers/stream.py` | Có `GET /api/stream/device-live` và `/api/stream/device-state`, chưa nhận serial | Cần contract chọn thiết bị rõ ràng |
| `apps/admin_console/services/device_stream_service.py` | Một capture loop/buffer toàn cục; chọn thiết bị `device` đầu tiên từ `adb devices`; chụp bằng `exec-out screencap -p` | Chưa an toàn cho multi-device hoặc đổi session |
| Stream hiện tại | Hàm đặt tên MJPEG nhưng gửi part `image/png`; chưa có subprocess timeout và metadata freshness cho UI | Không mặc định coi là MJPEG chuẩn hoặc đã đạt độ trễ thấp |
| `apps/showcase_ui/src/app/core/models/session.model.ts` | Có `device_serial` và `device_id` tùy chọn | Có thể gắn session với thiết bị; phải xác minh ngữ nghĩa `device_id` trước khi dùng làm ADB serial |
| `apps/admin_console/server.py`, `core/security.py` | Stream router đã đăng ký; có Host/Origin boundary và no-store cho API | Giữ bảo vệ hiện tại, kiểm tra thêm cross-site embedding của ảnh |
| `apps/showcase_ui/package.json`, `angular.json` | Có `npm run build`, `npm test`; output `dist/frontend` | Khi thực hiện sẽ phải build frontend, không chỉ restart Python |

Docstring của service nói WebSocket/không can thiệp tác vụ, nhưng phần source khảo sát mới có
HTTP multipart và ADB capture. Không coi các tuyên bố đó là kết quả đã kiểm chứng.

## 3. UX và quy tắc chọn thiết bị

### Vị trí tab

- Main panel: `Activity | Android Live`. Mặc định giữ `Activity` để không thay đổi luồng hiện tại.
- `Activity` giữ log, lịch sử và vị trí scroll khi chuyển tab.
- `Android Live` hiển thị tên thiết bị, serial, trạng thái, màn hình và các nút Pause/Resume,
  Reconnect, Fit/Fullscreen. Dùng `object-fit: contain`, không kéo méo hoặc cắt màn hình.
- Tab có `role=tablist/tab/tabpanel`, `aria-selected`, focus và điều hướng bàn phím.
- Sidebar và thanh nhập không che màn hình; responsive phải kiểm tra cả điện thoại xoay ngang.
- Có thể lưu tab đã chọn trong trạng thái UI; không lưu frame vào localStorage/cache.

### Chọn nguồn hình ảnh

1. Session đang chọn có serial đã xác minh: đề xuất thiết bị đó và hiển thị danh tính trước khi stream.
2. Chưa chọn session nhưng có đúng một thiết bị authorized: hiển thị thiết bị đó;
   chỉ bắt đầu capture khi người dùng mở tab Android Live.
3. Có nhiều thiết bị và không xác định được từ session: bắt buộc chọn thiết bị; không lấy thiết bị đầu tiên.
4. Không có thiết bị hoặc unauthorized/offline: hiển thị hướng dẫn tương ứng; không tự đổi sang thiết bị khác.
5. Chuyển session/serial: đóng subscription cũ, xóa frame cũ, tạo nguồn mới;
   bỏ mọi response đến muộn của nguồn cũ bằng generation ID/cancellation.

Live view không bắt buộc có session. Khi đang chọn session đã kết thúc, ghi rõ
**“Màn hình thiết bị hiện tại — không phải video của phiên này”**; chỉ stream sau khi người dùng
chọn xem trực tiếp. Replay lịch sử vẫn ở player hiện có. Không tự gắn màn hình hiện tại
với thời điểm thực thi của phiên cũ.

### Trạng thái UI

`No device / Select device / Unauthorized / Connecting / Live / Paused / Reconnecting / Disconnected / Error`.

- Chỉ hiển thị Live sau khi có frame mới và tình trạng capture còn healthy.
- Frame cũ không được giữ nhãn Live. Khi đổi serial phải xóa ngay; khi mất kết nối có thể
  giữ hình cuối với lớp phủ “Mất kết nối” và tuổi frame.
- Không dựa riêng vào sự kiện `<img onload/onerror>` để phát hiện stream multipart bị treo.
- Pause hoặc ẩn tab Workspace, chuyển route, ẩn browser document: ngắt nguồn ảnh/subscription.
- Resume chỉ khôi phục nếu người dùng chưa chủ động Pause. Không khôi phục bằng response cũ.

## 4. Kiến trúc MVP đề xuất

### Backend: một producer cho mỗi thiết bị

Tái sử dụng `DeviceStreamService`, thay buffer/counter toàn cục bằng registry theo serial:

- Mỗi serial có capture task, subscriber count, frame mới nhất, sequence, thời điểm capture
  và lỗi gần nhất. Không lưu toàn bộ lịch sử frame.
- Hai browser xem cùng serial dùng chung producer; browser chậm chỉ nhận frame mới nhất,
  không tạo hàng đợi vô hạn. Thiết bị khác có producer riêng với giới hạn tổng số producer.
- Chỉ capture khi có subscriber. Khi subscriber cuối rời đi, cancel **và await** task;
  terminate/reap subprocess do service tạo, xóa frame, giải phóng registry an toàn với race reconnect.
- Discovery được cache ngắn hạn/refresh theo trạng thái, không chạy `adb devices` trước mỗi frame.
- Mọi lệnh capture chỉ định `-s <serial>`; dùng cấu hình ADB host/port hiện có của ARTEMIS.
  Không chạy shell-string, restart ADB, chiếm khóa thực thi độc quyền hoặc thay đổi màn hình điện thoại.
- Có timeout riêng cho discovery/capture; cancellation phải thu hồi cả child process.
  Shutdown daemon dọn tất cả producer trước khi hoàn tất.
- Xóa frame khi disconnect/đổi nguồn; dùng monotonic clock để đo freshness/timeout.

Transport MVP: HTTP multipart MJPEG qua `<img>`, tiếp tục endpoint hiện có để giảm thay đổi.
Chuẩn hóa PNG từ ADB thành JPEG, đúng `Content-Type`, boundary và content length; encode ngoài
event loop. Thử nghiệm trên Chrome/Edge trước khi chốt. Không thêm WebSocket chỉ vì docstring cũ nhắc tới.

Mục tiêu ban đầu, **cần benchmark mới xác nhận**: 3 FPS, cạnh dài tối đa 960 px, JPEG quality 70,
thời gian tới frame đầu p95 ≤ 3 giây, tuổi frame khi hoạt động p95 ≤ 2 giây trên USB local.
Capture timeout 3 giây, stale threshold 5 giây; giới hạn FPS thay vì tăng tải ADB không kiểm soát.
Nếu không đạt, giảm FPS/resolution và ghi số đo; đánh giá scrcpy/H.264 ở giai đoạn sau.

### Contract API đề xuất

| Endpoint | Input | Output/hành vi |
| --- | --- | --- |
| `GET /api/stream/device-state` | `device_serial` tùy chọn | Giữ các field cũ `connected`, `serial`, `live_stream_url`; bổ sung danh sách thiết bị, `state`, `frame_sequence`, `frame_age_ms`, kích thước, mã lỗi an toàn |
| `GET /api/stream/device-live` | `device_serial` | Multipart JPEG của đúng serial; xác minh thiết bị trước khi gửi response headers |

Thiếu serial: chỉ tự resolve khi có đúng một thiết bị hợp lệ. Nhiều thiết bị trả lỗi yêu cầu chọn
(đề xuất HTTP 409). Serial không tồn tại trả 404; unauthorized/offline/capture unavailable trả
mã lỗi ổn định để UI phân biệt. Lỗi phát sinh sau khi stream bắt đầu: cập nhật state và đóng
stream; không cố trả JSON giữa multipart. Khi chưa có frame, UI dùng state để biết đang kết nối.
Query phải encode serial; không nhận command, output path, ADB host hay URL tùy ý từ browser.

Giữ endpoint không-query cho tương thích một thiết bị; cập nhật floating player để truyền serial
và xử lý trường hợp phải chọn thiết bị. Kiểm tra consumers cũ trước khi thay response schema.

### Frontend

- Tạo component `android-live-view` chỉ lo hiển thị, trạng thái, chọn thiết bị và lifecycle.
- Tạo `DeviceStreamService` phía Angular + typed DTO, dùng URL tương đối `/api/...`, không hard-code
  port 8000/8009. Tab thuộc `WorkspaceComponent`, không trộn logic stream vào `AgentService` lớn.
- Poll state khoảng 2 giây khi viewer hiện; teardown poll/stream khi ẩn. Reconnect có backoff
  1/2/4/8 giây, tối đa 5 lần rồi yêu cầu Retry; không polling dày khi unauthorized/no-device.
- Dùng state sequence/freshness để nhận diện stream treo; reset retry budget khi có frame tiến triển.
- Không gán URL ảnh có timestamp mới mỗi lần Angular change detection chạy.
- Tái sử dụng viewer trong floating player; khi Workspace tab đã xem cùng nguồn, không mở thêm
  live viewer nổi. Replay vẫn độc lập và không bị đóng bởi việc chọn tab.
- Khi ẩn Activity, giữ component/log subscription và scroll theo nhu cầu hiện tại;
  riêng capture live phải thực sự ngắt, không chỉ CSS `display:none`.

## 5. Bảo mật và tài nguyên

- Live screen có thể chứa thông tin riêng tư: chỉ bật theo thao tác người dùng, không lưu ảnh,
  không log nội dung frame/token, không gửi qua cloud.
- Giữ loopback mặc định, no-store và Host/Origin checks. Không mở CORS `*`, không tắt origin guard.
- Bổ sung kiểm tra cross-origin `<img>`/Fetch Metadata hoặc CORP thích hợp: request ảnh có thể
  không có Origin. Cho phép same-origin console và cấu hình tunnel hợp lệ đã có.
- Reconnect không được đổi serial ngầm. Không truy cập màn hình thiết bị khác khi session biến mất.
- Viewer không kill scrcpy/ADB hoặc tác vụ đang chạy. Chỉ dọn subprocess capture do chính nó tạo.

## 6. Các bước triển khai

- [ ] **P0 — Xác minh baseline:** đọc consumers và startup/shutdown; xác minh serial mapping,
  ADB remote-host support, stream hiện tại, hành vi screenshot khi thiết bị khóa/rotation.
  Chạy `adb devices -l`; nếu nhiều thiết bị, hỏi người dùng chọn serial trước khi khám phá.
  Dùng ARTEMIS để xác minh tương tác Android trước khi viết mobile/E2E test; nếu lỗi thì
  `mobile_diagnose` trước, không chạy tác vụ thử lặp lại để đoán.
- [ ] **P1 — Backend:** registry per-device, contract state, stream JPEG, timeout/cancellation,
  fan-out, cleanup và security. Chốt benchmark với một thiết bị trước khi nối UI.
- [ ] **P2 — UI:** tab Activity/Android Live, viewer + service, device selector, states,
  Pause/Resume/reconnect/visibility và responsive; nối vào session selection.
- [ ] **P3 — Tích hợp player:** dùng chung viewer, ngăn kết nối trùng, giữ replay và log state.
- [ ] **P4 — Kiểm chứng:** unit/integration/frontend tests, thiết bị thật, kiểm tra cạnh tranh với
  task/recording, build bundle và smoke test trên cổng 8009.
- [ ] **P5 — Tài liệu/release:** hướng dẫn sử dụng, giới hạn FPS, xử lý lỗi, benchmark và rollback.

## 7. Kế hoạch kiểm thử và tiêu chí nghiệm thu

Backend tests dự kiến: `tests/unit/admin_console/test_device_stream_service.py`,
`test_stream_router.py`; mở rộng `test_security_boundary.py`.
Frontend tests đặt cạnh component/service mới và `workspace.component.spec.ts`.

| Nhóm | Ca bắt buộc |
| --- | --- |
| Nguồn thiết bị | 0/1/2 thiết bị, unauthorized/offline, serial của session, session cũ không có serial, đổi A→B không lộ frame A |
| Stream | First-frame timeout, ADB nonzero, PNG lỗi, JPEG đúng format, rotation, stream treo nhưng socket còn mở |
| Lifecycle | 2 viewers/1 producer; viewer chậm; ngắt giữa capture; unsubscribe/resubscribe race; tab ẩn; route đổi; shutdown không rò subprocess |
| UI | Default Activity; giữ log scroll; keyboard tabs; retry hết hạn; pause không tự resume; không đổi nhãn Live khi frame stale |
| Session/replay | Xem live không có task; task kết thúc vẫn phân biệt live/replay; xem session cũ trong khi task khác chạy |
| Bảo mật | Sai Host/Origin, cross-site image embed, no-store, query serial bất thường không thành shell command |
| Đồng thời | Task Flash/Pro + live view + recording; không thay đổi helper/ADB lock hoặc ngắt recorder |

Mobile/E2E tests chỉ được viết sau khám phá ARTEMIS; ghi serial, độ phân giải, phiên bản Android,
chuỗi trạng thái đã xác minh. Dùng dynamic locator trước, coordinate fallback chỉ khi đã xác minh.
Dùng explicit waits và deadline hữu hạn; không hard-code sleep dài cho thao tác giao diện.
Unit test routing/encoding/lifecycle có thể mock ADB và không cần thiết bị.

Nghiệm thu: mở tab thấy đúng thiết bị; reconnect và rotation hoạt động; đóng tab dừng capture
trong ≤ 3 giây; không có frame nhầm nguồn; không tăng producer theo số browser; API/task/log/replay
không hồi quy. So sánh ít nhất 3 lượt workload ngắn giống nhau khi bật/tắt viewer, ghi CPU,
băng thông, frame age và thời gian thao tác; mục tiêu tăng p95 latency thao tác không quá 10%.
Các ngưỡng là mục tiêu thử nghiệm, không phải cam kết đã đạt.

## 8. Build, rollout và rollback

Khi triển khai thật có sửa Angular nên **cần build lại Web UI**:

1. Chạy backend tests có liên quan bằng Python `.venv`; frontend tests bằng npm test với
   browser headless phù hợp môi trường.
2. Tại `apps/showcase_ui`, chạy `npm run build`; kiểm tra output `dist/frontend/browser`
   và đường dẫn static mà server thực tế chọn. Bản đóng gói wheel cần cập nhật bundled assets
   theo quy trình packaging, không chỉnh trực tiếp file JS build.
3. Đợi tác vụ đang chạy kết thúc trước khi restart:
   `.\.venv\Scripts\artemis.exe restart --port 8009 --no-open` từ thư mục repo.
4. Mở `http://localhost:8009/workspace`, kiểm tra tab mới và asset version; hard refresh nếu cần.
5. Chỉ rollout sau P4. Nếu lỗi, tắt điểm mount tab/viewer mới và khôi phục bundle/backend tương ứng;
   giữ endpoint tương thích để player cũ vẫn dùng được. Không xóa session, traces hoặc cấu hình người dùng.

## 9. Giới hạn và các quyết định cần ghi lại ở P0

- MVP là live view kiểu ảnh cập nhật, không phải video 30/60 FPS.
- Xác minh trình duyệt mục tiêu và workload thực tế trước khi tăng tốc độ capture.
- Kiểm tra package resource/source copies để tránh sửa một nơi nhưng chạy bundle ở nơi khác.
- Nếu session model có `device_id` không phải ADB serial, bổ sung mapping backend, không suy đoán.
- Chưa có yêu cầu điều khiển thiết bị bằng chuột trong tab; không đưa tính năng này vào MVP.
