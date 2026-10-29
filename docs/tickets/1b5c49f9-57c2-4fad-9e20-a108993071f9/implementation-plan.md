Tôi sẽ đối chiếu requirements, implementation plan và mã runtime/frontend hiện tại để xác định guard “local-only”, rồi viết kế hoạch Markdown đầy đủ cho developer; không sửa mã nguồn hay commit/push.# Implementation Plan — Ticket #3: Internet Installer và truy cập Model Settings qua LAN

## 1. Mục tiêu

Triển khai hai entry point ở thư mục gốc:

```bash
curl -fsSL https://raw.githubusercontent.com/jokerhung/android-automation-studio/nextjs/install.sh | bash
```

```powershell
irm https://raw.githubusercontent.com/jokerhung/android-automation-studio/nextjs/install.ps1 | iex
```

Installer phải cài được hệ thống trên máy mới, build giao diện quản trị, khởi động daemon nền, kiểm tra readiness và in URL/lệnh quản lý.

Ngoài phạm vi installer, cần sửa lỗi đã xác nhận:

> Khi server bind LAN, trang Settings → Models vẫn trả `403 Model settings are local-only` cho client truy cập bằng IP LAN.

Chỉ giữ một testcase nghiệm thu E2E là `TC-INSTALL-001`. Các unit/integration test bổ sung bên dưới là kiểm thử hỗ trợ, không tạo testcase nghiệm thu mới.

---

## 2. Bằng chứng và nguyên nhân hiện tại

| Thành phần | Hiện trạng |
|---|---|
| `install.sh` | Đã tồn tại, bootstrap source, uv, Python và gọi runtime installer |
| `install.ps1` | Đã tồn tại, hỗ trợ PowerShell 5.1/7 và pipeline `irm \| iex` |
| `scripts/install_runtime.py` | Quản lý dependency, frontend build, metadata, daemon, readiness và lifecycle |
| `scripts/bootstrap_common.sh` / `.ps1` | Bootstrap uv và toolchain |
| `apps/admin_console/routers/model_settings.py` | `authorize()` luôn gọi `_require_loopback_request()` |
| `apps/admin_console/routers/system.py` | `_require_loopback_request()` từ chối mọi TCP peer không phải loopback |
| `apps/admin_console/core/security.py` | Đã cho phép Host là IP literal và kiểm tra same-origin |
| `scripts/install_runtime.py` | Bind mặc định `0.0.0.0`; `--local-only`/`-LocalOnly` dùng `127.0.0.1` |
| `ModelSettingsPanel` | Đã gọi API same-origin; không cần màn hình mới |

Nguyên nhân trực tiếp:

```python
# apps/admin_console/routers/model_settings.py
def authorize(request):
    _require_loopback_request(request, "Model settings are local-only.")
```

Khi client truy cập từ `192.168.x.x`, `request.client.host` không phải loopback nên GET/PUT Model Settings bị từ chối, dù server đang bind `0.0.0.0` và request đã đi qua same-origin middleware.

---

## 3. Quyết định bảo mật

### 3.1. Chính sách mới cho Model Settings

- Nếu server bind loopback (`127.0.0.1`, `::1`, `localhost`), Model Settings chỉ cho phép request loopback.
- Nếu server bind LAN/wildcard (`0.0.0.0`, địa chỉ IPv4 LAN hoặc `::`), cho phép Model Settings từ cùng-origin LAN.
- Vẫn bắt buộc kiểm tra same-origin.
- Không tin `X-Forwarded-For` hoặc header do client tự gửi.
- Không nới quyền cho lifecycle, Windows startup, SMTP hoặc các API quản trị vốn đang local-only.
- `--local-only` và `-LocalOnly` tiếp tục giới hạn server vào loopback; không quảng bá khả năng truy cập LAN.
- Không bổ sung hệ thống đăng nhập trong ticket này. README phải cảnh báo rằng bind LAN mở console không có tài khoản mặc định.

### 3.2. Bảo vệ vẫn giữ nguyên

- `SameOriginBoundaryMiddleware` tiếp tục kiểm tra Host/Origin.
- Host không hợp lệ hoặc origin khác host vẫn trả `403`.
- API key không được trả về response hoặc ghi vào log.
- Lifecycle token không được expose.
- Các endpoint thao tác daemon vẫn yêu cầu loopback và token hiện hữu.

---

## 4. Có cần thiết kế màn hình mới không?

Không.

`apps/showcase_next/src/features/settings/general-model-panels.tsx` đã có form Model Settings. Sửa lỗi nằm ở authorization backend. Chỉ cập nhật nội dung hướng dẫn trong README và tài liệu cài đặt để mô tả đúng hành vi LAN/local-only.

---

## 5. File và module cần sửa

| File | Thay đổi |
|---|---|
| `install.sh` | Giữ bootstrap độc lập với checkout, tham số, staging, lock, archive validation, checksum, cleanup và gọi runtime |
| `install.ps1` | Giữ hành vi tương đương Bash, tương thích PowerShell 5.1/7 và `iex` |
| `scripts/bootstrap_common.sh` | Bootstrap uv, retry, checksum và PATH |
| `scripts/bootstrap_common.ps1` | Bootstrap uv tương đương PowerShell |
| `scripts/install_runtime.py` | Dependency, frontend build, metadata, cấu hình bind, daemon và readiness |
| `apps/admin_console/core/security.py` | Thêm helper xác định bind loopback nếu cần dùng chung |
| `apps/admin_console/routers/model_settings.py` | Thay guard loopback tuyệt đối bằng guard phụ thuộc bind mode + same-origin |
| `tests/unit/admin_console/test_model_settings.py` | Kiểm tra LAN được phép khi bind LAN, local-only vẫn bị chặn, same-origin vẫn bắt buộc |
| `tests/unit/admin_console/test_security_boundary.py` | Bổ sung regression cho Host/Origin IP literal nếu cần |
| `README.md` | Cập nhật lệnh cài, bind mặc định, local-only và cấu hình model qua LAN |
| `docs/installation.md` | Cập nhật hành vi truy cập, recovery, rerun, bảo mật và giới hạn kiểm chứng |
| `docs/tickets/.../test-report.md` | Tester cập nhật sau khi có bản public và bằng chứng `TC-INSTALL-001` |

Không cần sửa `general-model-panels.tsx` trừ khi muốn thay thông báo lỗi hoặc thêm hướng dẫn hiển thị.

---

## 6. Thiết kế authorization cho Model Settings

### 6.1. Helper bind policy

Có thể thêm vào `apps/admin_console/core/security.py`:

```python
def is_loopback_bind(host: str | None) -> bool:
    """Return True when the configured server bind is local-only."""
```

Quy tắc:

- `127.0.0.1`, `::1`, `localhost`: `True`
- `0.0.0.0`, `::`, IPv4 LAN cụ thể: `False`
- Giá trị rỗng hoặc không hợp lệ: xử lý fail-closed như local-only
- Không thay đổi `host_is_allowed()` hoặc `origin_is_allowed()` hiện có

### 6.2. Authorization flow

Trong `apps/admin_console/routers/model_settings.py`:

```python
def authorize(request: Request) -> None:
    configured_host = getattr(state, "host", None)

    if is_loopback_bind(configured_host):
        _require_loopback_request(
            request,
            "Model settings are local-only.",
        )

    origin = request.headers.get("origin")
    host = request.headers.get("host", "")

    if origin and urlsplit(origin).netloc.lower() != host.lower():
        raise HTTPException(
            403,
            "Use the same-origin Artemis console.",
        )
```

`GET /api/settings/model` và `PUT /api/settings/model` tiếp tục gọi cùng một `authorize()`.

Không dùng `request.client.host` để cấm mọi remote request khi server bind LAN. `request.client.host` chỉ được dùng cho nhánh local-only.

### 6.3. Restart sau khi lưu

Không đổi luồng hiện tại:

1. Xác thực payload.
2. Kiểm tra server idle.
3. Lưu cấu hình nguyên tử.
4. Khởi động lại bằng `state.host` và `state.port`.
5. Đóng server cũ.
6. Frontend polling `server-status` để kết nối lại.

Khi bind LAN, restart phải giữ nguyên host LAN; không tự chuyển về loopback.

---

## 7. Luồng installer

### Bước 1 — Parse và preflight

`install.sh: main()` và `install.ps1` phải:

- Parse thư mục, port, local-only, non-interactive, open.
- Chuẩn hóa đường dẫn tuyệt đối.
- Hỗ trợ đường dẫn có khoảng trắng.
- Kiểm tra OS/architecture được hỗ trợ.
- Kiểm tra quyền ghi.
- Kiểm tra công cụ bootstrap tối thiểu.
- Không phụ thuộc `$BASH_SOURCE`, `$PSScriptRoot` hoặc checkout hiện tại.
- Không yêu cầu Git, Python, uv hoặc Node/npm cài sẵn.

### Bước 2 — Lock và staging

- Tạo staging riêng cạnh thư mục cài.
- Dùng lock để ngăn hai installer ghi cùng một instance.
- Không xóa checkout, trace, log hoặc dữ liệu người dùng.
- Nếu thư mục không rỗng nhưng không có metadata hợp lệ, dừng với lỗi rõ ràng.
- Khi lỗi/hủy, chỉ dọn staging và tài nguyên do lượt chạy hiện tại tạo.

### Bước 3 — Tải và kiểm tra source

Linux:

- Tải tarball branch `nextjs` qua HTTPS.
- Kiểm tra đường dẫn archive, một root duy nhất, không symlink/special file.
- Kiểm tra checksum SHA-256.
- Kiểm tra file bắt buộc:
  - `pyproject.toml`
  - `uv.lock`
  - `artemis/`
  - `apps/admin_console/`
  - `apps/showcase_next/`
  - `package-lock.json`
  - `config/artemis.jsonc`
  - `.env.example`
  - runtime/bootstrap helper
- Kiểm tra `BOOTSTRAP_VERSION`.

Windows:

- Tải ZIP branch `nextjs`.
- Kiểm tra archive root, đường dẫn, link/special file.
- Tính SHA-256.
- Kiểm tra cùng danh sách file bắt buộc.
- Không giả định `$PSScriptRoot` tồn tại khi chạy bằng `iex`.

### Bước 4 — Bootstrap runtime

Tái sử dụng:

- `bootstrap_uv()` trong `scripts/bootstrap_common.sh`
- `Initialize-BootstrapUv` trong `scripts/bootstrap_common.ps1`

Chuẩn bị:

- uv phiên bản đã pin và checksum.
- Python 3.12.
- Node/npm tương thích; dùng Node portable nếu máy không có bản phù hợp.
- PATH chỉ cập nhật trong tiến trình và lệnh quản lý của instance.

### Bước 5 — Dependency và frontend

` scripts/install_runtime.py`:

1. Chạy `uv sync --locked --python 3.12 --no-dev`.
2. Không fallback sang cài dependency không khóa.
3. Kiểm tra OpenCV/system library trên Ubuntu; lỗi phải chỉ rõ gói cần cài.
4. Chạy `npm ci --no-audit --no-fund`.
5. Chạy `npm run build`.
6. Xác minh:
   - `apps/showcase_next/out/index.html`
   - `out/settings/index.html`
   - asset được tham chiếu thật
7. Không đánh dấu thành công nếu build lỗi hoặc artifact thiếu.

### Bước 6 — Cấu hình và bảo toàn dữ liệu

- Tạo `.env` từ `.env.example` chỉ khi chưa tồn tại.
- Giữ nguyên `.env`, JSONC, database, traces và API key hiện có.
- Lưu `.artemis-install.json` với:
  - schema
  - source/ref
  - bootstrap version
  - archive checksum
  - directory
  - host/port
  - runtime environment
  - dependency/frontend fingerprint
  - stage/status
- Không ghi secret vào metadata hoặc log.

### Bước 7 — Bind, daemon và readiness

`install_runtime.py` phải:

- Mặc định bind `0.0.0.0`.
- Với `--local-only`/`-LocalOnly`, bind `127.0.0.1`.
- Giữ port 8009 nếu không override.
- Không tự chọn port khác khi port chỉ định bị chiếm.
- Nhận diện đúng instance ARTEMIS trước khi stop/restart.
- Không kill process chỉ vì process đang chiếm port.
- Dùng lifecycle adapter hiện hữu.
- Chạy daemon nền sau khi terminal installer đóng.
- Poll readiness có deadline tối đa 120 giây.
- Xác minh đồng thời:
  - đúng daemon instance
  - `/`
  - `/settings/`
  - ít nhất một asset thực
  - đúng port
- Không coi TCP mở hoặc HTTP 200 trang fallback là thành công.

### Bước 8 — Output và lệnh quản lý

In:

- `http://localhost:<port>`
- `http://127.0.0.1:<port>`
- URL IPv4 LAN nếu bind LAN
- `/settings/?tab=system`
- `/settings/?tab=models`
- `/settings/?tab=android`
- thư mục cài
- installer log
- server log
- lệnh `start`, `status`, `stop`, `restart`

Khi bind LAN:

```text
LAN access is enabled for same-origin console requests.
Use --local-only / -LocalOnly to restrict the server to this computer.
```

Khi local-only:

```text
Local-only bind; LAN access is disabled.
```

Không in `0.0.0.0` như URL truy cập.

---

## 8. Chạy lại và phục hồi

- Nhận diện instance bằng `.artemis-install.json`.
- Nếu fingerprint và artifact còn hợp lệ, bỏ qua sync/build không cần thiết.
- Không tự nâng cấp source.
- Không restart daemon đang hoạt động trừ khi người dùng gọi restart rõ ràng.
- Không đổi bind mode ngầm.
- Nếu muốn chuyển LAN ↔ local-only khi daemon đang chạy, yêu cầu stop rõ ràng trước.
- Nếu cài dở, báo stage và log cần kiểm tra.
- Không tự xóa lock nếu chưa xác nhận installer khác không còn chạy.

---

## 9. Kiểm thử tự động

### 9.1. Installer/runtime

Chạy:

```powershell
python -m pytest tests/unit/test_install_runtime.py tests/integration/installer
```

Kiểm tra:

- tham số sai
- port ngoài phạm vi
- archive lỗi
- archive thiếu file
- archive có symlink/path traversal
- checksum
- lock
- đường dẫn có khoảng trắng
- rerun
- giữ nguyên cấu hình
- port conflict
- readiness timeout
- đúng instance
- daemon còn chạy sau khi terminal đóng

### 9.2. Backend Model Settings

Chạy:

```powershell
python -m pytest tests/unit/admin_console/test_model_settings.py
```

Các trường hợp bắt buộc:

1. Loopback bind + loopback client → GET/PUT được phép.
2. LAN bind `0.0.0.0` + client LAN + Host/Origin cùng origin → GET được phép.
3. LAN bind `0.0.0.0` + client LAN + PUT hợp lệ → đi qua authorization và được xử lý.
4. LAN bind + origin khác host → `403`.
5. LAN bind + Host không được security boundary chấp nhận → `403`.
6. Local-only bind + client remote → `403 Model settings are local-only`.
7. Lifecycle API từ remote vẫn `403`.
8. SMTP/Windows startup/ADB local-only không bị mở rộng.
9. API key không xuất hiện trong response hoặc log.

### 9.3. Security boundary

Chạy:

```powershell
python -m pytest tests/unit/admin_console/test_security_boundary.py
```

Nếu cần bổ sung test:

- Host IP literal hợp lệ.
- Origin cùng IP và port hợp lệ.
- Cross-origin bị từ chối.
- DNS rebinding bị từ chối.
- Security headers vẫn có.
- API response vẫn `no-store`.

### 9.4. Shell và parser

Linux/macOS shell:

```bash
bash -n install.sh scripts/bootstrap_common.sh
```

PowerShell:

```powershell
$null = [System.Management.Automation.Language.Parser]::ParseFile(
  (Resolve-Path .\install.ps1),
  [ref]$null,
  [ref]$null
)
```

Python:

```powershell
python -m compileall scripts/install_runtime.py apps/admin_console
```

Frontend nếu có thay đổi UI:

```powershell
npm --prefix apps/showcase_next test
npm --prefix apps/showcase_next run build
```

---

## 10. Một testcase nghiệm thu duy nhất

### TC-INSTALL-001 — Cài qua Internet vào thư mục mới và mở web quản trị

Không tạo testcase E2E khác.

#### Linux

```bash
set -o pipefail
curl -fsSL https://raw.githubusercontent.com/jokerhung/android-automation-studio/nextjs/install.sh \
  | bash -s -- --install-dir "$PWD/artemis" --port 8009 --non-interactive
```

Kiểm tra:

1. OS, architecture, shell và công cụ trước cài.
2. Thư mục đích mới/rỗng.
3. Installer tải source, cài runtime, sync dependency, build frontend và start daemon.
4. Exit code bằng `0`.
5. `.venv`, metadata, `.env`, static export và log tồn tại.
6. Readiness đúng instance.
7. Mở Home.
8. Mở `/settings/?tab=system`.
9. Mở `/settings/?tab=models`.
10. Nếu dùng bind LAN, mở Models bằng IP LAN và xác nhận không còn lỗi `Model settings are local-only`.
11. Kiểm tra asset trả đúng nội dung.
12. Đóng terminal installer, reload trình duyệt và xác nhận web vẫn hoạt động.

#### Windows

```powershell
& ([scriptblock]::Create((Invoke-RestMethod -Uri 'https://raw.githubusercontent.com/jokerhung/android-automation-studio/nextjs/install.ps1'))) `
  -InstallDir (Join-Path (Get-Location).Path 'artemis') `
  -Port 8009 -NonInteractive
```

Thực hiện cùng các bước và bằng chứng như Linux.

Nếu chạy với `--local-only`/`-LocalOnly`, chỉ xác nhận truy cập local; không kết luận truy cập LAN.

#### Bằng chứng phải lưu

- OS/version/architecture/shell
- trạng thái công cụ trước cài
- command, thời gian và exit code
- revision/source URL
- log installer và daemon
- runtime version
- identity daemon
- HTTP/static asset checks
- screenshot Home, System, Models
- reload sau khi đóng terminal
- không đính kèm `.env`, API key hoặc lifecycle token

---

## 11. Acceptance criteria

| ID | Tiêu chí |
|---|---|
| AC-01 | Có `install.sh`, `install.ps1` chạy được qua hai one-liner |
| AC-02 | Máy sạch không cần Git, Python, uv, Node/npm cài sẵn |
| AC-03 | Snapshot đầy đủ source, lockfile, template, helper và runtime |
| AC-04 | Dependency sync và frontend build hoàn tất, lỗi không bị che |
| AC-05 | Tạo cấu hình thiếu, giữ nguyên cấu hình có sẵn |
| AC-06 | Daemon chạy nền, đúng instance, port, Home, Settings và asset |
| AC-07 | Có URL và lệnh quản lý chính xác, hỗ trợ path có khoảng trắng |
| AC-08 | Rerun, lock, interrupted install và port conflict đúng business rules |
| AC-09 | README và `docs/installation.md` phản ánh đúng bind LAN/local-only |
| AC-10 | `TC-INSTALL-001` có bằng chứng Linux và Windows sạch/public |
| D-01 | Model Settings cho phép same-origin LAN khi server bind LAN |
| D-02 | Model Settings vẫn loopback-only khi bind local-only |
| D-03 | Cross-origin, Host không hợp lệ và DNS rebinding vẫn bị chặn |
| D-04 | Lifecycle, SMTP, Windows startup và ADB local-only không bị mở rộng |
| D-05 | Không làm lộ API key, lifecycle token hoặc secret trong response/log |

---

## 12. Rủi ro và giới hạn

- Bind LAN hiện không có hệ thống tài khoản; README phải khuyến nghị `--local-only`, SSH tunnel hoặc mạng tin cậy khi cần bảo vệ console.
- Không tin kết quả chỉ từ HTTP 200 hoặc TCP mở.
- Workspace hiện tại có cache, `.venv` và build nên không thay thế máy sạch.
- URL public trên branch `nextjs` phải trỏ đúng revision đã review trước khi chạy nghiệm thu.
- Chưa được đánh dấu PASS khi thiếu bằng chứng Linux sạch, Windows sạch hoặc browser evidence.

---

## 13. Thứ tự bàn giao

1. Developer triển khai installer và authorization policy.
2. Developer chạy lint, parser, unit/integration và local runtime smoke.
3. Người có quyền phát hành revision lên branch `nextjs`.
4. Tester chạy đúng `TC-INSTALL-001` trên Linux sạch và Windows sạch.
5. Tester cập nhật `test-report.md`.
6. Chỉ kết luận PASS khi toàn bộ bằng chứng E2E đầy đủ.

Planner không sửa mã nguồn, không commit và không push.