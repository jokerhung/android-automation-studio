# Plan: ARTEMIS System Tray trên Windows

Ngày: 2026-09-14  
Trạng thái: Đã triển khai đầy đủ trong mã nguồn: tray, single-instance, identity metadata theo workspace/port/PID creation time, fail-closed lifecycle, drain task/scheduler/email, startup/CLI orchestration và kiểm thử mock. Chưa tự thay đổi registry hoặc điều khiển tiến trình thật trong kiểm thử.

## 1. Mục tiêu và phạm vi

Khi ARTEMIS chạy nền trên Windows, hiển thị icon trong system tray với menu:

1. **Start**
2. **Stop**
3. **Open homepage**
4. **Exit**

MVP dành cho Windows desktop trong phiên người dùng đã đăng nhập. ARTEMIS hiện là background
daemon, không phải Windows Service chạy dưới Service Control Manager. Không chuyển thành
Windows Service, không yêu cầu Administrator, không tạo Windows Task Scheduler job.
Tray không thay thế Web UI, không truy cập màn hình Android hay gửi thêm email.

## 2. Hiện trạng và điểm tích hợp

| Source hiện tại | Kết quả khảo sát / việc cần làm |
| --- | --- |
| `artemis/runtime/daemon_client.py` | `spawn_daemon()` chạy server detached, lưu log, không có tray; có `is_artemis_daemon()` để kiểm tra identity |
| `artemis/runtime/server_lifecycle.py` | Metadata PID/port/lifecycle token, graceful shutdown và stop; cần xác minh identity trước mọi thao tác |
| `artemis/interfaces/cli/commands/server_lifecycle.py` | CLI restart/stop/status; nơi tích hợp high-level background launch |
| `artemis/interfaces/cli/commands/ui.py` | Luồng Web UI/foreground/build; không tự bật thêm tray cho mọi dev-server |
| `artemis/runtime/windows_startup.py` | Registry Run gọi launcher bằng `pythonw.exe`, dùng cổng đã lưu; hiện exit khi cổng có listener |
| `apps/admin_console/routers/system.py` | Endpoint server status/lifecycle và startup setting; bảo vệ loopback/lifecycle token hiện có |
| `apps/admin_console/server.py`, `core/state.py` | Quản lý shutdown, task/queue; cần phối hợp drain thay vì chỉ kill process |
| Scheduler/email services hiện có | Stop server dừng cả lịch và email worker; phải thể hiện rõ khi xác nhận |
| `docs/windows-startup.md` | Tài liệu Start with Windows cần cập nhật sau triển khai |
| `pyproject.toml` | Đã có Pillow; chưa thấy dependency tray chuyên biệt trong phần đã khảo sát |

Khảo sát bằng source, chưa xác minh Windows tray API, icon asset đóng gói và restart Explorer.
Không coi `is_daemon_running()` hoặc việc cổng mở là đủ xác nhận tiến trình thuộc ARTEMIS:
probe này có fallback chấp nhận response từ ứng dụng khác.

## 3. Hành vi menu

### Start

- Enabled khi server đã dừng hoặc crash và không có lifecycle operation đang chạy.
- Khởi động server nền trên cổng cấu hình, ví dụ `8009`; không mở browser/terminal.
- Kiểm tra trước: nếu đúng ARTEMIS đã chạy thì attach và cập nhật Running, không spawn trùng.
- Nếu cổng do app khác giữ: báo Port conflict, không kill app đó, không tự chuyển cổng.
- Chỉ báo Running sau khi identity/readiness xác nhận; startup timeout đề xuất 60 giây.
- Lỗi giữ icon và hiển thị thông báo an toàn cùng vị trí log; cho phép Start thử lại.

### Stop

- Dừng server nền nhưng **giữ icon tray**; sau đó có thể bấm Start.
- Dừng server đồng nghĩa scheduler và email worker cũng ngừng cho tới khi Start lại.
- Idle: graceful shutdown bằng API/helper có lifecycle token và identity đã xác minh.
- Có task/queue hoặc email đang xử lý: hiện hộp xác nhận native:
  - **Wait until finished**: vào trạng thái Stopping/Draining, ngừng nhận task/claim schedule mới,
    chờ các task đã nhận, flush logs/media và email đang gửi trong giới hạn đã công bố.
  - **Stop now**: xác nhận rõ sẽ hủy task chưa hoàn tất qua cơ chế Stop task hiện có,
    rồi graceful shutdown; không hard-kill mặc định.
  - **Cancel**: giữ server chạy.
- Nếu drain gặp task paused hoặc timeout, hỏi lại thay vì tự chuyển sang force kill.
- Không tắt Start with Windows, không xóa schedule/traces hoặc SMTP credentials.

### Open homepage

- Mở browser mặc định đến `http://localhost:<port>/`; không hard-code `8000`/`8009`.
- Nếu server Stopped, hỏi “Start ARTEMIS and open homepage?”; chỉ mở sau khi Start thành công.
- Nếu Starting/Stopping, hiển thị trạng thái hoặc disable để tránh request trùng.
- Double-click icon có thể tương đương Open homepage; right-click mở bốn mục menu.
- URL lấy từ target server đã xác minh, không lấy URL tùy ý từ log/LLM/response không tin cậy.

### Exit

- **Dừng server rồi thoát tiến trình tray**, không chỉ ẩn icon trong khi server tiếp tục chạy.
- Dùng cùng chính sách task/queue/email và xác nhận như Stop.
- Server chưa dừng được: giữ icon, báo lỗi; không hiển thị đã Exit trong khi daemon còn chạy.
- Server đã Stopped: thoát tray ngay. Release mutex và IPC, đóng icon/thread/handles.
- Exit không xóa registry Start with Windows; đăng nhập Windows lần tới vẫn tự chạy nếu ON.
- Nếu cần “Quit tray only” trong tương lai, đó là menu riêng ngoài MVP, không làm Exit mơ hồ.

## 4. Trạng thái icon và UI

| Trạng thái | Tooltip ví dụ | Start | Stop | Open homepage | Exit |
| --- | --- | --- | --- | --- | --- |
| Stopped | ARTEMIS — Stopped · 8009 | Có | Không | Hỏi Start | Có |
| Starting | ARTEMIS — Starting… · 8009 | Không | Không | Không | Hủy startup an toàn rồi thoát |
| Running | ARTEMIS — Running · 8009 | Không | Có | Có | Có |
| Draining/Stopping | ARTEMIS — Waiting for tasks / Stopping… | Không | Không | Không | Không, tránh thao tác trùng |
| Error | ARTEMIS — Server unavailable · 8009 | Có nếu đã xác định stopped | Chỉ khi xác minh được daemon | Theo trạng thái | Có nếu không còn daemon |

- Dùng icon ARTEMIS có các kích thước phù hợp DPI (16/20/24/32/48); thêm indicator trạng thái,
  không chỉ dựa vào màu. Cần kiểm tra taskbar sáng/tối và scale 100/125/150/200%.
- Windows có thể đưa icon vào vùng **Show hidden icons**; không hứa icon luôn nằm ngoài overflow
  hoặc tự sửa preference taskbar của người dùng.
- Poll health đề xuất mỗi 2 giây, timeout mỗi request ≤ 1 giây. Lỗi ngắn không spam balloon;
  cần vài lần liên tiếp trước khi báo unavailable, thao tác menu có phản hồi ngay.
- Notification chỉ cho chuyển trạng thái quan trọng/lỗi cần xử lý; không bật browser khi tự startup.
- Sau Explorer restart, tray phải đăng ký lại icon; kiểm thử trước khi chốt thư viện.

## 5. Kiến trúc đề xuất

Tách hai tiến trình để tray vẫn tồn tại khi server Stopped:

```text
CLI background / Windows sign-in launcher
                │
                ▼
      Tray controller (pythonw, interactive user)
                │ local lifecycle client
                ▼
      ARTEMIS daemon (detached, loopback)
                ├─ Task queue / device execution
                ├─ Scheduler
                └─ Email worker
```

### Module

- `artemis/runtime/tray_app.py`: entry point và native menu/icon adapter.
- `artemis/runtime/tray_controller.py`: state machine, start/stop/open/exit;
  test được bằng fake process/browser/network, không phụ thuộc UI loop.
- `artemis/runtime/tray_instance.py`: single-instance mutex và attach IPC.
- Tray assets trong `artemis/resources/`, đọc qua resource API và đóng gói vào wheel.
- Log riêng `tray-<port>.log`, không ghi lifecycle token, secrets, goal hay SMTP payload.

Ưu tiên thư viện tray nhỏ hoặc adapter Win32 sẵn có, **chốt ở P0 sau khi kiểm tra compatibility**
với Python 3.14 và Windows. Candidate có thể là pystray + Pillow; không coi đó là dependency
đã quyết định hay đã hỗ trợ trước khi thử. Không thêm Qt/Electron chỉ để có icon và bốn mục menu.

### Thread và process

- Native message loop giữ thread UI; HTTP/ADB/readiness/start/stop ở worker thread/async controller.
- Callback menu chỉ dispatch action; mọi update icon/menu/dialog quay lại UI thread đúng API.
- Serialize lifecycle actions bằng operation lock/generation ID để double-click không spawn hai daemon.
- Khởi động tray bằng `pythonw.exe` hoặc process flag ẩn; dùng tuyệt đối executable/module/CWD
  và `subprocess` argv, không ghép command string tùy ý, không mở PowerShell console.
- Tray crash không tự kill daemon; mở lại tray sẽ attach nếu daemon vẫn chạy.
- Daemon crash: tray hiện Error/Stopped; MVP không tự restart vòng lặp vô hạn.

## 6. Tích hợp các đường chạy nền và Start with Windows

- Tạo entry orchestration chung `ensure_background_runtime(...)`: bảo đảm tray rồi bảo đảm daemon,
  trả trạng thái hiện có; CLI background và Windows launcher dùng chung.
- Giữ `spawn_daemon()` là primitive chỉ tạo server. Tray gọi primitive này không được recursively
  spawn tray thêm lần nữa. Không khởi tạo icon trong module import/FastAPI worker reload.
- Các đường CLI `restart --daemon`, auto-start daemon từ Web/MCP/SDK cần khảo sát và đi qua
  orchestration phù hợp khi đang trong phiên Windows interactive.
- Nếu process chạy non-interactive/không có desktop session, vẫn cho daemon hoạt động và log
  “tray unavailable”; không lặp tạo GUI. Foreground/dev mode giữ hành vi hiện tại trừ khi user chọn tray.
- Windows sign-in launcher: không return chỉ vì cổng mở. Nếu daemon ARTEMIS đã chạy, vẫn bảo đảm
  tray tồn tại; nếu cổng là app khác, icon hiện lỗi thay vì dừng process kia.
- Giữ registry value `Artemis` và Start with Windows ON/OFF semantics; thay implementation launcher
  tương thích command cũ. Không tự bật startup cho người chưa bật.
- Khi Stop từ tray, một request ngoài (CLI/MCP/SDK) có thể start lại daemon theo hành vi sản phẩm
  hiện có; document rõ và tray attach lại. Stop không phải “cấm mọi nguồn khởi động”.

## 7. Single instance, identity và nhiều daemon

- Single tray instance theo Windows user + canonical workspace/installation path + port.
  Launch cùng target nhiều lần: attach/tái dùng, không xuất hiện icon trùng.
- Nếu thực sự chạy nhiều port, mỗi target một icon có port trong tooltip; menu chỉ quản lý target đó.
- Named mutex với ACL current-user; IPC attach chỉ nhận action trong whitelist và target đã bind,
  không nhận shell command hoặc path/URL tùy ý. Named pipe có ACL current-user là lựa chọn đề xuất.
- Metadata stale/PID reuse: xác minh port, command identity, process creation time và lifecycle token
  trước Stop; không kill chỉ dựa trên số PID hoặc listener cổng.
- Khi metadata chưa đủ xác minh: fail closed, báo lỗi/cho reload status. Không bypass token hoặc
  dùng kill-all-python/kill-all-port để làm menu Stop hoạt động.
- Nếu metadata hiện chỉ lưu một server, phải thiết kế per-target metadata trước hỗ trợ multi-port;
  không dùng metadata cổng khác để gửi shutdown.

## 8. Drain, scheduler và email khi shutdown

- P0 kiểm tra shutdown hiện có đáp ứng tới đâu; bổ sung admission/drain contract dùng chung nếu thiếu.
- Khi chọn Wait: chặn **mọi ingress** task mới, dừng claim schedule, giữ queue đã nhận và task đang chạy;
  UI/API trả trạng thái draining rõ ràng thay vì nhận job rồi làm mất nó.
- Email worker: ngừng claim mới; chờ send đang chạy theo SMTP timeout. Nếu bị ngắt ở điểm không rõ
  server SMTP đã nhận chưa, giữ `delivery_unknown`, không đánh dấu failed rồi tự gửi trùng.
- Flush/persist terminal state, logs, report/media; release device locks, scheduler/send leases đúng owner.
- Chỉ đóng tray sau khi daemon của target đã kết thúc; timeout phải hiển thị lựa chọn xử lý tiếp.
- Khi Windows sign-out/shutdown: xử lý session-ending event best-effort trong deadline Windows,
  không cố chặn shutdown vô hạn. Khi đăng nhập lại dùng recovery/reconciliation hiện có.

## 9. Kế hoạch triển khai

- [ ] **P0 — Prototype và contract:** chọn tray API tương thích Python/Windows, kiểm tra DPI/dark mode,
  Explorer restart, inventory entry points, multi-port metadata và graceful drain hiện tại.
- [ ] **P1 — Controller:** state machine + fake lifecycle adapters, polling, serialized operations,
  port conflict và identity-safe start/stop, native confirmation contract.
- [ ] **P2 — Tray shell:** icon/menu/tooltip, error feedback, Open homepage, single-instance mutex,
  worker/UI thread separation và logging.
- [ ] **P3 — Lifecycle:** tích hợp daemon CLI/background và Windows sign-in launcher;
  giữ Start with Windows state, không mở terminal/browser tự động.
- [ ] **P4 — Shutdown coordination:** drain/stop-now, scheduler/email recovery, interrupted startup,
  server crash và controller reconnect.
- [ ] **P5 — QA/package/docs:** kiểm thử native, tài nguyên wheel, hướng dẫn hidden icons,
  cập nhật `docs/windows-startup.md` và rollback.

## 10. Kiểm thử và nghiệm thu

Unit tests với fake clock/process/network/tray/registry/browser; không thực sự bật startup,
gửi email hoặc dừng task người dùng để chạy test. Files dự kiến:
`tests/unit/runtime/test_tray_controller.py`, `test_tray_instance.py`,
`test_windows_startup.py`, lifecycle/security tests và packaging resource tests.

| Nhóm | Ca bắt buộc |
| --- | --- |
| Menu | Start/Stop enable đúng trạng thái; double-click/repeated clicks; Open homepage không đổi port |
| Startup | CLI daemon, Windows launcher, pythonw path có dấu/khoảng trắng, non-interactive session |
| Identity | ARTEMIS có sẵn, port bị app khác giữ, PID reuse, stale/missing token, nhiều port |
| Stop/Exit | Idle, task running/paused, pending queue, email sending, user Cancel, drain timeout |
| Recovery | Tray crash daemon còn chạy; daemon crash tray còn; Explorer restart; sleep/resume |
| UI native | Theme/DPI, overflow tray, menu bằng bàn phím, tooltip không chứa secrets |
| Lifecycle | Không leak process/thread/mutex/pipe; không recursive spawn; registry không bị đổi ngoài ý muốn |

Manual Windows test chỉ dùng workload vô hại và target rõ ràng. Có thể kiểm tra launcher bằng
chạy đúng command đăng nhập mà không reboot; logoff/login dùng để xác minh end-to-end khi người dùng
đồng ý. Không tự sign out/restart Windows trong quá trình triển khai.

Tiêu chí nghiệm thu:

- Chạy nền trong phiên Windows interactive có một icon/target; không cần mở Web UI.
- Stop → daemon dừng, icon còn; Start → daemon hoạt động lại, đúng port.
- Open homepage mở đúng trang khi Running; khi Stopped hỏi trước khi Start.
- Exit dừng daemon an toàn và biến mất icon; Start with Windows vẫn giữ lựa chọn trước đó.
- Không kill app khác hoặc mất dữ liệu task/email vì xử lý tray.
- Không có terminal bật lên ở sign-in; resources hoạt động từ source và bản đóng gói.

## 11. Build, rollout và rollback

- Plan không cần build/restart. Triển khai tray chủ yếu thay Python/dependency/resources,
  không cần build Angular nếu không sửa Settings UI.
- Cài dependency theo quy trình dự án, chạy tests, đóng gói icon; không build frontend lúc Windows login.
- Đợi task hiện tại xong trước cập nhật/restart daemon. Rollout trước với cổng thử riêng và task vô hại;
  không tự bật Start with Windows hoặc tự tạo startup entry mới.
- Rollback orchestration về launcher daemon-only, dừng tray đúng target, giữ registry command tương thích,
  giữ mọi schedule/log/credentials. Nếu cần tắt startup, để người dùng chọn OFF trong Settings.

## 12. Quyết định MVP được đề xuất

- Stop giữ tray; Exit dừng cả daemon và tray.
- Task/queue/email đang hoạt động phải có xác nhận và lựa chọn chờ; không force kill mặc định.
- Một tray cho mỗi user/workspace/port; không tự ghép nhiều daemon vào một menu.
- Không có auto-restart daemon sau crash trong MVP; chỉ update trạng thái và cho Start thủ công.
- Cổng lấy từ cấu hình/target thực tế; ví dụ môi trường hiện tại là 8009, không dùng hằng số cho mọi máy.
