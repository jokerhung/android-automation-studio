# Đặc tả: Tab Remote Phone — chọn thiết bị bằng combo box và điều khiển điện thoại qua trình duyệt

Ngày: 2026-11-01
Trạng thái: Đã triển khai MVP; còn giới hạn đã ghi ở §11.
Phạm vi khảo sát: đã kiểm tra thiết bị QV770X1KE9 (A204SO, Android 14); tap ADB khoảng 110 ms, 10 lần screencap khoảng 3.48 s (~2.88 FPS).

## 1. Mục tiêu

Thêm một **tab Remote Phone** vào thanh điều hướng chính để người dùng:

1. Chọn điện thoại Android đang kết nối bằng **combo box** (danh sách thả xuống có tìm kiếm).
2. Xem màn hình điện thoại trực tiếp trong trình duyệt.
3. Điều khiển điện thoại bằng **chuột** (click, long-press, kéo để swipe) và **bàn phím** (gõ chữ, phím đặc biệt, tổ hợp phím).

Tab này độc lập với phiên tác vụ: nó điều khiển thiết bị hiện tại, không phải replay một session.

### Không thuộc phạm vi MVP

- Âm thanh, ghi hình, multi-touch/pinch hai ngón, chuyển file, cài/gỡ ứng dụng, đồng bộ clipboard.
- Điều khiển thiết bị khi đang có tác vụ ARTEMIS chạy trên chính thiết bị đó (xem §6).
- Điều khiển nhiều thiết bị cùng lúc trong một khung hình.
- scrcpy/H.264 qua WebSocket. Đây là giai đoạn sau, chỉ mở nếu MJPEG không đạt mục tiêu độ trễ (§3.3).

## 2. Hiện trạng đã xác minh trong source

| Thành phần | Hiện trạng | Hệ quả cho triển khai |
| --- | --- | --- |
| `apps/showcase_next/src/components/navigation.tsx` | 4 mục: `/`, `/workspace/`, `/task-schedule/`, `/settings/` | Thêm mục thứ 5; icon `lucide-react` đã có sẵn |
| `apps/admin_console/server.py` `_NEXT_ROUTES` | Danh sách route tĩnh cố định; route lạ trả 404 | **Bắt buộc** thêm `"remote": "remote/index.html"`, nếu không trang 404 dù build thành công |
| `apps/showcase_next/next.config.ts` | `output: 'export'`, `trailingSlash: true` | Trang mới là `src/app/remote/page.tsx` → `out/remote/index.html` |
| `apps/admin_console/routers/stream.py` | `GET /api/stream/device-live`, `/device-state`; không nhận `device_serial` | Cần endpoint riêng cho remote, không phá contract cũ |
| `apps/admin_console/services/device_stream_service.py` | Buffer/frame toàn cục, một capture loop, `exec-out screencap -p`, gửi part `image/png` dù khai báo MJPEG | Phải làm registry theo serial + JPEG thật trước khi dùng cho remote |
| `artemis/drivers/android/adb_driver.py` | Có `tap`, `swipe`, `press_key`, `ANDROID_KEYCODE_MAP`, `_escape_for_adb_text` | Tái dùng logic thay vì viết lại; nhưng driver gắn với instance thiết bị |
| `artemis/drivers/android/input_ime.py` | `type_text` ASCII qua `input text`, non-ASCII qua UIAutomator/ADBKeyboard | Unicode có thể thất bại; phải báo lỗi rõ cho người dùng |
| `artemis/runtime/device_pool.py` | `list_devices_async()` → `DeviceStatus` gồm `serial`, `state`, `model`, `is_busy`, `active_session_id` | Nguồn dữ liệu cho combo box và trạng thái busy |
| `artemis/runtime/device_lock.py` | `DeviceExecutionLock.get_active_owners()` | Cách phát hiện thiết bị đang bị tác vụ chiếm |
| `apps/admin_console/core/security.py` | Chặn Host/Origin lạ, `no-store` cho `/api/`; comment nêu rõ "ai vào được cổng là operator" | POST điều khiển hợp lệ về CSRF, nhưng LAN vẫn là rủi ro thật (§7) |
| `apps/showcase_next/src/components/ui/` | Chưa có `select`; `tabs.tsx` đã dùng package `radix-ui` | Thêm `ui/select.tsx` từ `radix-ui`, không thêm dependency mới |
| `apps/showcase_next/src/features/workspace/components/workspace-panels.tsx` | `DeviceViewer` hard-code `/api/stream/device-live` trong `<img>` | Giữ nguyên; remote dùng component riêng, không refactor viewer workspace trong MVP |
| `apps/showcase_next/scripts/serve-acceptance.py` | Có stub `/api/stream/device-live` cho Playwright | Cần thêm stub cho các endpoint `/api/remote/*` |

## 3. Quyết định thiết kế

### 3.1 Vị trí: route riêng `/remote/`, không phải tab trong Workspace

Lý do: điều khiển cần khung hình lớn và vùng bắt chuột/bàn phím riêng. Cột viewer trong Workspace chỉ rộng `--device-pane` và đã dành cho replay phiên. Route riêng cũng tránh mọi thay đổi hành vi Workspace hiện có.

Navigation: chèn `['/remote/', 'nav.remote', Smartphone]` giữa Workspace và Task Schedule.

### 3.2 Transport MVP: MJPEG cho hình, REST cho điều khiển

- Hình: `GET /api/remote/stream?device_serial=<serial>` → `multipart/x-mixed-replace` với part **JPEG thật** (`Content-Type: image/jpeg`).
- Điều khiển: `POST /api/remote/input/*` (JSON, same-origin, `credentials: same-origin`).
- Lý do chọn REST thay vì WebSocket cho MVP: `SameOriginBoundaryMiddleware` đã xử lý cả scope `websocket`, nhưng chưa có endpoint WS nào trong repo; REST dùng lại `apiRequest` ở `src/lib/api/client.ts`, dễ test và dễ rollback. WebSocket chỉ đáng làm khi cần giảm overhead per-command hoặc chuyển sang H.264.
- Hệ quả cần chấp nhận: mỗi thao tác chuột là một HTTP round-trip (~5–20 ms LAN, ~1–5 ms loopback) cộng với `adb shell input` (~50–150 ms USB). Không phù hợp cho game/scroll mượt; đủ cho thao tác UI thông thường.

### 3.3 Một producer hình cho mỗi serial

Chuyển `DeviceStreamService` sang registry `dict[serial, DeviceProducer]`:

- Mỗi producer: capture task, `subscriber_count`, `latest_frame`, `frame_sequence`, `captured_at` (monotonic), `last_error`, `screen_size`, `rotation`.
- Hai browser xem cùng serial dùng chung producer; browser chậm chỉ nhận frame mới nhất.
- Chỉ capture khi có subscriber; subscriber cuối rời → cancel **và await** task, reap subprocess, xóa frame.
- Mọi lệnh ADB chỉ định `-s <serial>`; discovery cache ngắn hạn, không gọi `adb devices` mỗi frame.
- Endpoint cũ `/api/stream/device-live` và `/api/stream/device-state` giữ nguyên hành vi (tự chọn một thiết bị) để Workspace không hồi quy.

Chuẩn hóa frame: `screencap -p` trả PNG; encode sang JPEG (quality 70, cạnh dài ≤ 960 px) ngoài event loop. Mục tiêu: 5 FPS, first-frame p95 ≤ 3 s, frame age p95 ≤ 1 s trên USB local. Đây là mục tiêu cần đo, không phải cam kết.

## 4. Contract API

Tất cả endpoint dưới `/api/remote/`, đều yêu cầu `device_serial` và đều trả `Cache-Control: no-store`.

| Endpoint | Body/Query | Kết quả |
| --- | --- | --- |
| `GET /api/remote/devices` | – | `{ "devices": [{ "serial", "model", "state", "is_busy", "busy_session_id", "screen_width", "screen_height", "controllable", "uncontrollable_reason" }] }` |
| `GET /api/remote/state` | `device_serial` | `{ "serial", "state", "frame_sequence", "frame_age_ms", "screen_width", "screen_height", "rotation", "controllable", "reason", "stream_url" }` |
| `GET /api/remote/stream` | `device_serial` | `multipart/x-mixed-replace; boundary=frame`, part JPEG |
| `POST /api/remote/input/tap` | `{ device_serial, x, y, duration_ms? }` | `{ "ok": true, "sequence": n }` |
| `POST /api/remote/input/swipe` | `{ device_serial, x1, y1, x2, y2, duration_ms }` | `{ "ok": true, "sequence": n }` |
| `POST /api/remote/input/text` | `{ device_serial, text, clear_existing?: false }` | `{ "ok": true, "mode": "ascii" \| "ime" }` |
| `POST /api/remote/input/key` | `{ device_serial, key }` | `{ "ok": true }` |

### Quy tắc xác thực input (server-side, bắt buộc)

1. `device_serial` phải khớp chính xác một `DeviceStatus.serial` từ `device_pool.try_list_devices_async()`; ngược lại `404`. Không suy đoán, không lấy thiết bị đầu tiên.
2. `x`, `y`, `x1…y2` phải là số nguyên, `0 ≤ value < screen_size` tương ứng. Ngoài biên → `422`.
3. `duration_ms` trong `[0, 5000]`; mặc định tap 100 ms, swipe 400 ms.
4. `text` ≤ 2000 ký tự; chạy qua `_escape_for_adb_text` khi là ASCII; non-ASCII đi qua `AndroidInputIME`.
5. `key` phải là tên trong danh sách trắng ở §4.1. Không nhận số keycode thô từ browser.
   Lưu ý: `ANDROID_KEYCODE_MAP` hiện chỉ có 8 mục (`home` 3, `back` 4, `enter` 66, `delete` 67,
   `power` 26, `app_switch` 187, `volume_up` 24, `volume_down` 25), nên remote cần **map riêng**
   trong `device_input_service.py`; không sửa map dùng chung của driver để tránh ảnh hưởng agent.
6. Lệnh ADB dựng bằng **argv list**, không nối shell string: `[adb, "-s", serial, "shell", "input", "tap", str(x), str(y)]`. Riêng `input text` cần chuỗi đã escape vì `adb shell` parse trên thiết bị.
7. Không nhận `adb host/port`, đường dẫn output, URL, hay tên package từ browser.

### Mã lỗi ổn định để UI phân biệt

| HTTP | `code` | Ý nghĩa |
| --- | --- | --- |
| 404 | `device_not_found` | Serial không còn trong danh sách |
| 409 | `device_busy` | Đang có tác vụ ARTEMIS giữ thiết bị |
| 409 | `device_unauthorized` | `state != "device"` |
| 409 | `control_disabled` | Remote bị tắt bởi cấu hình (§7) |
| 422 | `invalid_coordinate` / `invalid_key` / `invalid_text` | Vi phạm quy tắc ở trên |
| 503 | `capture_unavailable` | ADB screencap lỗi liên tiếp |

### 4.1 Danh sách trắng phím và keycode

`ANDROID_KEYCODE_MAP` trong `artemis/drivers/android/adb_driver.py` chỉ có 8 mục, nên remote
định nghĩa bảng riêng `REMOTE_KEYCODES` trong `device_input_service.py`:

| `key` | Keycode | Ghi chú |
| --- | --- | --- |
| `back` | 4 | |
| `home` | 3 | |
| `enter` | 66 | |
| `delete` | 67 | Backspace |
| `tab` | 61 | |
| `escape` | 111 | Phím ESC của Android, **không** phải Back |
| `move_home` / `move_end` | 122 / 123 | Đầu/cuối dòng |
| `dpad_up` / `dpad_down` / `dpad_left` / `dpad_right` | 19 / 20 / 21 / 22 | |
| `volume_up` / `volume_down` | 24 / 25 | |
| `power` | 26 | |
| `app_switch` | 187 | |
| `copy` / `cut` / `paste` | 278 / 277 / 279 | Android 7+ |

`select_all` không có trong MVP vì Android không có keycode tương ứng ổn định trên mọi phiên bản
(`input keycombination` chỉ có từ Android 13). Không dùng `input keyevent --meta 1 29`: meta 1 là
Shift, không phải Ctrl.

## 5. Giao diện

### 5.1 Bố cục `/remote/`

```
┌──────────────────────────────────────────────────────────────┐
│ Remote Phone            [combo box: device ▾]  [↻]  [⛶]      │
├───────────────────────────────────────────┬──────────────────┤
│                                           │ Trạng thái       │
│            khung hình điện thoại          │ serial / model   │
│         (giữ tỉ lệ, nền tối, không méo)   │ FPS, frame age   │
│                                           │ Nguồn phím       │
│                                           │ ─────────────    │
│                                           │ Hàng phím tắt:   │
│                                           │ ◀ ⬤ ▶  ⟲  ⌨     │
├───────────────────────────────────────────┴──────────────────┤
│ Gợi ý: Click = tap · Giữ 500 ms = long-press · Kéo = swipe    │
└──────────────────────────────────────────────────────────────┘
```

Responsive: dưới 900 px, cột trạng thái xuống dưới khung hình; khung hình dùng `max-height: 72dvh`.

### 5.2 Combo box chọn thiết bị

- Component mới `src/components/ui/select.tsx` (adapt từ shadcn `new-york-v4`, dùng `radix-ui` như `tabs.tsx`).
- Nội dung mỗi dòng: `model` (fallback `serial`) + serial nhỏ bên dưới + badge trạng thái (`device` / `unauthorized` / `offline` / `busy`).
- Ô tìm kiếm lọc theo serial hoặc model, không phân biệt hoa thường.
- Thiết bị `state != "device"` hiển thị nhưng **disabled**, kèm lý do.
- Danh sách làm mới mỗi 5 s khi tab đang hiển thị; dừng poll khi `document.hidden`.
- Lựa chọn lưu trong `localStorage` key `aas.remote.device` **chỉ là gợi ý**: nếu serial không còn, xóa và yêu cầu chọn lại; không tự chuyển sang thiết bị khác.
- Có đúng một thiết bị hợp lệ và chưa có lựa chọn đã lưu → tự chọn. Nhiều thiết bị → bắt buộc người dùng chọn.

### 5.3 Ánh xạ chuột → lệnh thiết bị

Khung hình là `<img>` trong một `<div>` có `role="application"`, `tabIndex={0}`, `aria-label`.

```
scale = image.naturalWidth / rect.width            // px thiết bị trên px CSS
dx    = round((event.clientX - rect.left) * scale)
dy    = round((event.clientY - rect.top)  * scale)
```

Bỏ qua sự kiện nằm ngoài `rect` (khi `object-fit: contain` có letterbox).

| Cử chỉ | Điều kiện | Lệnh |
| --- | --- | --- |
| Click | `pointerdown` → `pointerup` ≤ 400 ms, di chuyển < 8 px CSS | `tap(x, y, 100)` |
| Long-press | giữ ≥ 500 ms, di chuyển < 8 px | `tap(x, y, 1000)` |
| Kéo | di chuyển ≥ 8 px | `swipe(start, end, max(100, min(2000, duration)))` |
| Wheel | `deltaY` | `swipe` dọc 40 % chiều cao, 300 ms, hướng theo dấu |

- Chỉ gửi `swipe` ở `pointerup` (không stream từng `move`) để tránh dồn lệnh.
- Throttle `pointermove` 16 ms chỉ để vẽ vệt kéo cục bộ, không gửi mạng.
- `pointerdown` trên khung hình tự focus container để bật chế độ bắt phím.
- Lệnh gửi đi có `sequence` tăng dần; response đến muộn bị bỏ qua.

### 5.4 Bàn phím

Chỉ bắt phím khi container đang focus **và** người dùng đã bật "Keyboard capture" (mặc định bật sau lần click đầu vào khung hình). Hiển thị chỉ báo rõ khi đang bắt phím, kèm nút tắt — tránh nuốt phím của giao diện trang.

| Phím | Lệnh |
| --- | --- |
| Ký tự in được | Gom vào buffer, gửi `input/text` sau 300 ms im lặng hoặc khi gặp phím đặc biệt |
| `Enter` | `key: enter` (keycode 66) |
| `Backspace` | `key: delete` (67) |
| `Tab` | `key: tab` (61) |
| `Escape` | `key: escape` (111, phím ESC của Android — không phải Back) |
| `ArrowUp/Down/Left/Right` | `key: dpad_*` |
| `Home` / `End` | `key: move_home` / `move_end` |
| `Ctrl+A/C/X/V` | `copy` / `cut` / `paste`; `Ctrl+A` không map ở MVP (§4.1) |
| `Ctrl+Enter` | Không map; dành cho giao diện |
| `Paste` (`paste` event) | `input/text` với nội dung clipboard — dùng sự kiện paste, **không** gọi Clipboard API |

- Không gọi `preventDefault` cho `F5`, `F11`, `F12`, `Ctrl+Shift+I`, `Ctrl+R` — giữ phím trình duyệt hoạt động.
- Khi mất focus: xóa buffer, hiện "Bàn phím đã tắt".
- Non-ASCII: server trả `mode: "ime"`; nếu IME không khả dụng, hiển thị cảnh báo "Thiết bị chưa cài ADBKeyboard; ký tự Unicode có thể không gõ được" và không giả vờ thành công.

### 5.5 Trạng thái UI

`NoDevice` · `SelectDevice` · `Unauthorized` · `Busy` · `Connecting` · `Live` · `ControlDisabled` · `Reconnecting` · `Disconnected` · `Error`

- Chỉ hiện `Live` sau khi có frame mới và `frame_age_ms` trong ngưỡng.
- Mất kết nối: giữ frame cuối với lớp phủ "Mất kết nối · frame cũ N s" và làm mờ (không xóa) khung hình.
- Đổi serial: dừng stream cũ, xóa frame ngay, reset buffer phím, bắt đầu nguồn mới với `generation` id; mọi response đến muộn của nguồn cũ bị bỏ.
- Pause/ẩn tab/chuyển route: ngắt `<img src>`, dừng poll, hủy mọi lệnh đang chờ.
- Reconnect backoff 1/2/4/8 s, tối đa 5 lần rồi yêu cầu bấm Retry.

## 6. Tương tác với tác vụ ARTEMIS

Điều khiển bằng chuột/bàn phím chèn input trực tiếp vào thiết bị, có thể phá một tác vụ Flash/Pro đang chạy.

Quy tắc MVP:

1. Server kiểm tra `DeviceExecutionLock.get_active_owners()` cho serial. Nếu có owner → mọi lệnh input trả `409 device_busy`; stream vẫn xem được (chỉ xem).
2. UI hiện banner "Thiết bị đang được tác vụ &lt;id&gt; sử dụng — chỉ xem", khóa con trỏ và bàn phím, không có nút ép ghi đè.
3. Không được tự dừng tác vụ để giành quyền điều khiển. Người dùng phải dừng tác vụ ở Workspace rồi quay lại.
4. Remote **không** lấy `DeviceExecutionLock` cho riêng nó: nếu lấy, remote sẽ chiếm khóa và chặn tác vụ một cách âm thầm. Thay vào đó remote chỉ đọc trạng thái khóa. Đánh đổi: có khe hở race giữa lúc kiểm tra và lúc gửi lệnh (tác vụ vừa khởi động) — chấp nhận trong MVP, ghi nhận ở §11.
5. Remote không kill scrcpy/ADB, không restart ADB server, không đổi màn hình khi người dùng chưa thao tác.

## 7. Bảo mật

Đây là bề mặt nguy hiểm nhất từng thêm vào console: một HTTP POST có thể gõ vào bất kỳ trường nào trên điện thoại.

- **Bắt buộc** giữ `SameOriginBoundaryMiddleware`; mọi endpoint mới nằm dưới `/api/` nên đã có `no-store`.
- Origin guard chỉ chặn request *có* `Origin`. Một POST form cross-site vẫn có `Origin` nên bị chặn; nhưng để chắc chắn, mọi endpoint input yêu cầu `Content-Type: application/json` (không parse form-urlencoded) và từ chối khi thiếu header đó.
- **Remote control mặc định chỉ bật trên loopback.** Nếu request đến từ địa chỉ client không phải loopback, trả `409 control_disabled` trừ khi đặt `ARTEMIS_REMOTE_CONTROL_ALLOW_LAN=1`. Xem màn hình vẫn cho phép; chỉ chặn *điều khiển*. Lý do: console không có tài khoản, bất kỳ ai trong LAN mở được cổng là điều khiển được điện thoại.
- Khi `ARTEMIS_REMOTE_CONTROL_ALLOW_LAN=1`, trang hiển thị cảnh báo thường trực và ghi log mỗi lần bật.
- Không log nội dung `text` người dùng gõ (có thể là mật khẩu). Log chỉ `serial`, loại lệnh, toạ độ, độ dài text.
- Không gửi frame ra ngoài máy; không đưa vào LLM.
- `x-frame-options: DENY` đã có → không nhúng được vào iframe bên thứ ba.

## 8. Cấu trúc mã nguồn dự kiến

```
apps/admin_console/routers/remote.py                  # router mới, đăng ký trong server.py
apps/admin_console/services/device_input_service.py   # validate + dựng argv ADB + gọi input
apps/admin_console/services/device_stream_service.py  # registry theo serial (refactor)

apps/showcase_next/src/app/remote/page.tsx
apps/showcase_next/src/components/ui/select.tsx
apps/showcase_next/src/features/remote/
  types.ts            # DeviceInfo, RemoteState, InputCommand
  api.ts              # gọi /api/remote/*, dùng apiRequest
  input-mapping.ts    # toạ độ CSS ↔ thiết bị, keymap, gom buffer (hàm thuần, dễ test)
  use-device-stream.ts# lifecycle stream + state poll + generation
  remote-page.tsx
  device-picker.tsx   # combo box
  remote-screen.tsx   # <img> + pointer handlers
  keyboard-capture.ts
  remote.css
```

Điểm cần sửa ngoài thư mục trên:

- `apps/admin_console/server.py`: `include_router(remote.router)`, thêm `"remote": "remote/index.html"` vào `_NEXT_ROUTES`.
- `apps/showcase_next/src/components/navigation.tsx`: mục `/remote/`.
- `apps/showcase_next/src/lib/i18n/catalogs.ts`: key `nav.remote` và nhóm `remote.*` cho **cả** `en` và `vi`.
- `apps/showcase_next/scripts/serve-acceptance.py`: stub `/api/remote/devices`, `/api/remote/state`, `/api/remote/stream`, `/api/remote/input/*`.
- `.env.example`: `ARTEMIS_REMOTE_CONTROL_ALLOW_LAN` kèm comment cảnh báo.

## 9. Kế hoạch triển khai

- [x] **P0 — Xác minh baseline.** Chạy `adb devices -l`; nếu nhiều thiết bị, hỏi người dùng chọn serial trước khi khám phá. Dùng ARTEMIS xác minh tương tác Android thật (tap, swipe, gõ text ASCII và Unicode, phím Back/Home) trước khi viết test. Đo `adb shell input tap` round-trip và FPS `screencap` để chốt ngưỡng §3.3.
- [x] **P1 — Backend stream.** Refactor `DeviceStreamService` thành registry theo serial, JPEG thật, timeout/cancel/reap, endpoint `/api/remote/stream` + `/api/remote/state` + `/api/remote/devices`. Giữ endpoint cũ hoạt động.
- [x] **P2 — Backend input.** `remote.py` + `device_input_service.py` với toàn bộ quy tắc §4; kiểm tra busy qua `DeviceExecutionLock`; giới hạn loopback (§7).
- [x] **P3 — UI.** Route `/remote/`, combo box, khung hình, ánh xạ chuột, bắt bàn phím, trạng thái, i18n en/vi.
- [x] **P4 — Kiểm thử & nghiệm thu** (§10).
- [x] **P5 — Tài liệu.** README (mục Remote Phone), `docs/installation.md` nếu có env mới, ghi rõ giới hạn độ trễ và cảnh báo LAN.

Kết quả P0: thiết bị `QV770X1KE9` (A204SO, Android 14) đã được ARTEMIS khám phá. Tap trung tính ở `[500,600]` và swipe ngắn `[500,700]→[500,640]` không đổi màn hình; Back giữ nguyên prompt; Home đưa về launcher. Không có ô nhập an toàn trên màn hình khám phá nên không thực hiện gõ ASCII/Unicode. Đo host: `adb shell input tap` khoảng 110 ms; 10 lần `screencap` khoảng 3.48 s (~2.88 FPS), thấp hơn mục tiêu 5 FPS và cần lưu ý khi dùng cho UI động.

## 10. Kiểm thử và tiêu chí nghiệm thu

### Backend (`pytest`, mock ADB)

`tests/unit/admin_console/test_remote_input.py`, `test_remote_router.py`, mở rộng `test_security_boundary.py`, `test_device_stream_service.py`.

| Nhóm | Ca bắt buộc |
| --- | --- |
| Chọn thiết bị | 0/1/2 thiết bị; serial lạ → 404; `unauthorized`/`offline` → 409; không tự lấy thiết bị đầu tiên |
| Toạ độ | Biên 0 và `w-1`/`h-1` hợp lệ; `-1`, `w`, số thực, `NaN`, chuỗi → 422 |
| Lệnh | argv đúng thứ tự, **không** nối shell string; serial chứa `;`/`$(...)` không thành lệnh; key ngoài danh sách trắng → 422 |
| Text | ASCII escape đúng (`%s` cho space, `\"`, `$`…); text > 2000 ký tự → 422; non-ASCII đi nhánh IME |
| Busy | Có lock owner → 409 `device_busy`; hết lock → cho phép lại |
| Bảo mật | Sai `Origin` → 403; `Content-Type: text/plain` → 415; request từ IP không loopback khi chưa bật env → 409 `control_disabled` |
| Stream | Hai viewer/1 producer; đổi serial không lộ frame cũ; cancel khi subscriber cuối rời; shutdown không rò subprocess |

### Frontend (`vitest`)

`tests/remote/input-mapping.test.ts`, `tests/remote/remote-page.test.tsx`.

- Quy đổi toạ độ với letterbox `object-fit: contain` (scale và offset đúng ở 3 tỉ lệ cửa sổ).
- Phân loại cử chỉ: click / long-press / drag theo ngưỡng thời gian và khoảng cách.
- Gom buffer bàn phím: 300 ms im lặng, flush khi gặp phím đặc biệt, xóa buffer khi blur.
- `preventDefault` **không** áp dụng cho F5/F11/F12/Ctrl+R.
- Đổi serial xóa frame và buffer; response đến muộn của generation cũ bị bỏ.
- Combo box: thiết bị unauthorized bị disable; lựa chọn đã lưu không còn thì yêu cầu chọn lại.

### Acceptance (`playwright`, dùng `serve-acceptance.py`)

`tests/acceptance/remote-phone.spec.mjs`: mở `/remote/`, chọn thiết bị từ combo box, thấy khung hình, click sinh đúng một request `tap`, gõ chữ sinh `text`, mất kết nối hiện lớp phủ đúng.

### Mobile/E2E trên thiết bị thật

Chỉ viết sau khi khám phá bằng ARTEMIS. Ghi lại serial, độ phân giải, phiên bản Android và chuỗi trạng thái đã xác minh. Dùng dynamic locator trước, coordinate fallback chỉ khi đã xác minh. Nếu ARTEMIS báo lỗi, gọi `mobile_diagnose` trước, không chạy lại tác vụ thử để đoán.

### Tiêu chí nghiệm thu

1. Mở `/remote/`, combo box liệt kê đúng thiết bị đang kết nối kèm trạng thái; chọn được bằng chuột và bằng bàn phím.
2. Click trên khung hình mở đúng ứng dụng tại đúng vị trí (sai số ≤ 1 px thiết bị ở 3 kích thước cửa sổ).
3. Kéo trên khung hình cuộn danh sách; giữ 1 s kích hoạt long-press (xác minh trên một app có menu ngữ cảnh).
4. Gõ ASCII vào ô tìm kiếm của một app có kết quả đúng; Enter gửi; Backspace xóa; nút Back trong hàng phím tắt quay lại màn hình trước.
5. Đổi sang thiết bị B không còn frame của A; rời trang dừng capture trong ≤ 3 s.
6. Trong khi tác vụ đang chạy trên thiết bị, mọi lệnh input trả 409 và UI khóa điều khiển.
7. Truy cập từ IP LAN không bật env: xem được hình, điều khiển bị chặn với thông báo rõ.
8. Không hồi quy: `/workspace/` live view, replay, log, task, schedule, settings vẫn hoạt động.

## 11. Rủi ro và quyết định mở

| Rủi ro | Giảm thiểu |
| --- | --- |
| `screencap` mỗi frame chậm → hình giật, cảm giác trễ khi điều khiển | Đo ở P0; nếu frame age p95 > 1 s, xem xét scrcpy `--no-playback` + H.264/WebSocket ở giai đoạn sau |
| Race giữa kiểm tra busy và gửi lệnh | Chấp nhận ở MVP; nếu thành vấn đề, thêm khóa ngắn hạn (lease) chỉ cho remote |
| Unicode không gõ được nếu thiếu ADBKeyboard | Cảnh báo rõ trong UI; không báo thành công giả |
| LAN mở điều khiển = ai trong LAN cũng điều khiển được điện thoại | Mặc định chặn điều khiển ngoài loopback; env opt-in + cảnh báo thường trực |
| Hai nguồn capture cùng serial (Workspace + Remote) | Registry dùng chung theo serial nên chỉ một producer |
| Route mới quên khai báo `_NEXT_ROUTES` → 404 | Có test acceptance mở `/remote/` |
| Bundle wheel đóng gói asset cũ | Build lại `out/` và đóng gói lại; không sửa tay file build |

Quyết định cần chốt ở P0: ngưỡng FPS/độ phân giải; có cần pinch/zoom hai ngón không; có cần bàn phím ảo tiếng Việt (Telex/VNI) không; có cần điều khiển qua Tailscale được không.

## 12. Build, rollout và rollback

1. Chạy `pytest` các test backend liên quan bằng `.venv`; `npm test` và `npm run typecheck` trong `apps/showcase_next`.
2. `npm run build --prefix apps/showcase_next`; xác nhận `out/remote/index.html` tồn tại.
3. Đợi tác vụ đang chạy kết thúc, rồi `.\.venv\Scripts\artemis.exe restart --port 8009 --no-open`.
4. Mở `http://localhost:8009/remote/`, hard refresh, kiểm tra asset version.
5. Rollback: gỡ mục nav và route `remote` khỏi `_NEXT_ROUTES`, khôi phục bundle trước đó, tắt router `remote`. Endpoint `/api/stream/*` cũ giữ nguyên nên Workspace không bị ảnh hưởng. Không xóa session, traces hay cấu hình người dùng.


