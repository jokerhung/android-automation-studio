Tôi sẽ đối chiếu bàn giao BA với mã nguồn bootstrap, runtime và web quản trị để lập kế hoạch theo file/hàm cụ thể. Bước này chỉ trả tài liệu Markdown để hệ thống lưu, chưa viết code hoặc commit/push.
Runtime hiện đã có kiểm tra đúng instance ARTEMIS, đối chiếu nội dung Home/Settings/asset và bảo vệ server đang chạy khi sửa dependency. Phần còn thiếu chủ yếu là hai entry point tải source; kế hoạch sẽ tập trung vào pipeline bootstrap, metadata để phục hồi cài dở và truyền lỗi. Các test hiện có dùng toolchain giả nên chưa chứng minh cài được trên máy sạch.
# Ticket #3 — Kế hoạch triển khai installer qua Internet

- **Tài liệu:** `docs/tickets/1b5c49f9-57c2-4fad-9e20-a108993071f9/implementation-plan.md`
- **Nguồn yêu cầu:** `requirements.md` cùng thư mục và bàn giao BA.
- **Workspace:** `C:\hungnm\artemis`.
- **Trạng thái:** Đã khảo sát mã nguồn; chưa triển khai, chưa chạy installer hoặc testcase.
- **Bàn giao tiếp:** Developer. Không cần Designer vì không tạo màn hình mới.
- **Giới hạn:** Không commit/push, không phát hành repository. Bước planner chỉ trả nội dung tài liệu để hệ thống lưu.

## 1. Mục tiêu và phạm vi

Tạo hai script ở gốc repository, hỗ trợ trực tiếp:

```bash
curl -fsSL https://raw.githubusercontent.com/jokerhung/android-automation-studio/nextjs/install.sh | bash
```

```powershell
irm https://raw.githubusercontent.com/jokerhung/android-automation-studio/nextjs/install.ps1 | iex
```

Installer phải tải source, chuẩn bị runtime và dependency, tạo cấu hình thiếu, build frontend, khởi động nền và chỉ báo thành công khi web quản trị của đúng bản cài sẵn sàng.

Theo đặc tả BA, nghiệm thu “toàn bộ hệ thống” ở mức backend và frontend phục vụ web quản trị. API key, Android được cấp quyền, ADB và công cụ media là điều kiện sử dụng automation sau cài đặt; không phải điều kiện mở web.

Không bổ sung chức năng nâng cấp source, cấu hình IDE/MCP, tự khởi động khi đăng nhập hoặc màn hình mới.

## 2. Bằng chứng khảo sát và khoảng trống

| File/module | Hiện trạng đã đọc | Hướng triển khai |
| --- | --- | --- |
| `install.sh`, `install.ps1` | Chưa có ở gốc workspace | Tạo hai entry point |
| `README.md`, `docs/installation.md` | Đã mô tả Internet installer, tùy chọn, mặc định và recovery | Đồng bộ với hành vi thực thi; giữ trạng thái chưa nghiệm thu |
| `scripts/bootstrap_common.sh` | `bootstrap_uv()` tải uv `0.12.13`, kiểm SHA-256 | Tái sử dụng; chuẩn hóa lỗi và kiểm tra binary được tái sử dụng |
| `scripts/bootstrap_common.ps1` | `Initialize-BootstrapUv()` có tải, retry, checksum | Tái sử dụng; bảo đảm lỗi truyền về caller |
| `scripts/install_runtime.py` | Có sync Python, Node portable, build, cấu hình, lifecycle và readiness | Tích hợp; bổ sung phần metadata và recovery cần thiết |
| `artemis/config/paths.py` | Có resolver `.env`, cấu hình, app directory và server metadata | Dùng đúng resolver; không tạo cấu hình ở đường dẫn suy đoán |
| `artemis/runtime/server_lifecycle.py` | Metadata phân biệt workspace/cổng; kiểm PID, process identity, listener và token | Giữ làm nguồn xác minh instance |
| `artemis/runtime/daemon_client.py` | Có identity HTTP và spawn daemon detached, log riêng | Tái sử dụng |
| `artemis/runtime/background_runtime.py` | Có `ensure_background_runtime()` | Dùng luồng hiện hữu |
| `apps/admin_console/server.py` | Phục vụ static export tại `apps/showcase_next/out` | Không cần Next.js server riêng |
| `start.sh`, `scripts/start.ps1` | Nhận diện `.artemis-install.json` rồi chuyển sang runtime manager | Giữ tương thích |
| `scripts/check_installer_release.py` | So sánh file public với checkout; archive mới kiểm tra bằng HEAD | Là kiểm tra phát hành, không chứng minh E2E |
| `tests/integration/installer/test_bootstrap*.py` | Dùng archive/toolchain giả | Chỉ chứng minh hợp đồng bootstrap, không chứng minh máy sạch |
| `tests/unit/test_install_runtime.py` | Có kiểm tra fingerprint, cấu hình, readiness và lifecycle bằng fixture/mock | Tham khảo hợp đồng hiện hữu |

Các điểm cần xử lý trong runtime hiện tại:

- `read_state()` mới kiểm tra `schema` và `source`; cần xác thực thêm kiểu dữ liệu, đường dẫn và trạng thái trước khi tiếp tục bản cài.
- Chưa có entry point tạo metadata ban đầu và kiểm soát tải/chuyển source vào đích.
- `_active` bỏ qua metadata không đọc được ở một số nhánh; không được suy ra “an toàn để sửa” khi trạng thái tiến trình chưa xác định.
- Lỗi thư viện hệ thống có thể dẫn đến gọi `sudo`/`apt-get` không tồn tại; cần thông báo phục hồi cụ thể.
- Fingerprint và `stage` phải phản ánh cài dở; không để trạng thái `ready` cũ đại diện cho lần sửa thất bại.
- Identity HTTP hiện dùng `urlopen()` mặc định, trong khi kiểm tra frontend đã bỏ proxy loopback. Cần thống nhất để proxy không làm sai readiness.
- Chưa có bằng chứng tải public hoặc cài trên máy sạch trong bước planner này.

## 3. Hợp đồng giao diện

| Bash | PowerShell | Hành vi |
| --- | --- | --- |
| `--install-dir PATH` | `-InstallDir PATH` | Chuẩn hóa thành đường dẫn tuyệt đối; hỗ trợ khoảng trắng |
| `--port N` | `-Port N` | Số nguyên 1–65535; không tự đổi cổng được chỉ định |
| `--local-only` | `-LocalOnly` | Bind `127.0.0.1` |
| `--non-interactive` | `-NonInteractive` | Không hỏi đầu vào |
| `--open` | `-Open` | Mở Settings sau readiness thành công |
| `--help` | `-Help` | In hướng dẫn, không tải hoặc cài |

Mặc định giữ theo BA:

- Linux: `$HOME/.local/share/artemis`.
- Windows: `%LOCALAPPDATA%\Programs\Artemis`.
- Lần đầu: cổng `8009`, bind `0.0.0.0`.
- Chạy lại: dùng host/port đã lưu nếu không có override.
- Không có Git, Python, uv hoặc Node/npm cài trước vẫn bootstrap được.
- Linux cần Bash, curl, CA certificates, tar, mktemp và công cụ SHA-256 cùng các tiện ích shell chuẩn.
- Windows cần Windows 11 x64, PowerShell 5.1 hoặc 7 và khả năng giải nén ZIP.
- Giữ khả năng tương thích macOS đã có trong helper; không đánh dấu macOS được nghiệm thu bởi ticket này.

Không dùng thư mục hiện hành làm nguồn script. Với pipeline Bash không dựa vào `BASH_SOURCE` để tìm checkout; với `iex` không dựa vào `$PSScriptRoot`.

## 4. Kiến trúc và luồng xử lý

Luồng chung:

```text
Parse tham số / kiểm môi trường
  → Chuẩn hóa đích / lấy install lock
  → Phân loại đích mới hoặc bản cài hiện hữu
  → Tải và kiểm tra một source snapshot nếu cài mới
  → Đặt source + metadata ban đầu vào đích
  → Bootstrap uv và Python 3.12
  → install_runtime.py install
  → Sync dependency / cấu hình / build
  → Khởi động hoặc dùng lại đúng daemon
  → Identity + HTTP readiness
  → Ghi ready / in URL, log và lệnh quản lý
```

### 4.1. Tải snapshot nhất quán

Chọn tải **một archive hoàn chỉnh** của branch `nextjs`:

- Bash: `https://codeload.github.com/jokerhung/android-automation-studio/tar.gz/refs/heads/nextjs`
- PowerShell: `https://codeload.github.com/jokerhung/android-automation-studio/zip/refs/heads/nextjs`

Quy tắc:

1. Tải vào staging riêng, ưu tiên cùng filesystem với thư mục đích.
2. Chỉ dùng helper, runtime, source và lockfile bên trong archive đó.
3. Không tải helper riêng từ raw branch sau khi đã tải archive.
4. Ghi URL, branch và SHA-256 của archive để truy vết.
5. SHA-256 tính tại máy là định danh nội dung tải được, không phải chữ ký phát hành hoặc bằng chứng commit SHA.
6. Entry point cần hợp đồng bootstrap có version với snapshot. Nếu không tương thích, dừng rõ ràng thay vì tiếp tục ghép các phiên bản.
7. Chạy lại bản cài hợp lệ phải dùng source đã cài, không tải branch mới để ghi đè.

Trước khi giải nén:

- Kiểm archive đọc được, có một thư mục gốc hợp lệ.
- Từ chối đường dẫn tuyệt đối, thành phần `..`, đường dẫn thoát staging.
- Từ chối link hoặc entry đặc biệt có thể ghi ra ngoài staging.
- Windows kiểm cả đường dẫn ổ đĩa, UNC và reparse/link entry.
- Không thực thi helper trước khi hoàn tất kiểm tra archive và cấu trúc source.

Các file/thư mục bắt buộc tối thiểu:

- Hai entry point và helper tương ứng.
- `scripts/install_runtime.py`.
- `pyproject.toml`, `uv.lock`.
- `packages/artemis-client/pyproject.toml` và source package.
- Backend `artemis/`, `apps/admin_console/`.
- `.env.example`, `config/artemis.jsonc`.
- `apps/showcase_next/package.json`, `package-lock.json`, cấu hình build và source frontend.

Chỉ chuyển snapshot sang đích khi kiểm tra thành công. Không chép chồng từng file vào thư mục không xác định.

### 4.2. Bootstrap khi chưa có Python

Hai script thực hiện phần tải source bằng công cụ hệ điều hành, sau đó:

1. Nạp helper từ source đã xác thực.
2. Chuẩn bị uv riêng tại `.tools/uv`.
3. Kiểm phiên bản và checksum binary tải mới.
4. Dùng uv chuẩn bị Python 3.12.
5. Chạy `scripts/install_runtime.py install --uv <absolute-path>` bằng Python được uv quản lý.

Lệnh chạy runtime qua uv phải ở chế độ không tự sync project trước khi `prepare()` tiếp quản, chẳng hạn `uv run --no-project --python 3.12 ...`; developer xác minh cú pháp với uv được pin.

Lý do: kiểm soát cài dở, phát hiện server đang chạy và timeout phải xảy ra trước thao tác sửa dependency.

Không cần Git và không dùng `git clone`. Không thay shell profile hoặc PATH vĩnh viễn.

### 4.3. Đặc thù Bash

Các hàm dự kiến:

| Hàm | Trách nhiệm |
| --- | --- |
| `parse_args()` | Validate tùy chọn trước download |
| `check_platform()` | Kiểm OS/architecture và công cụ bootstrap |
| `resolve_install_dir()` | Chuẩn hóa đường dẫn, kiểm quyền và loại đích |
| `acquire_install_lock()` | Tạo sibling `<install-dir>.install-lock` độc quyền |
| `download_snapshot()` | HTTPS, retry hữu hạn, timeout |
| `validate_extract_snapshot()` | Kiểm archive rồi giải nén staging |
| `initialize_install_state()` | Tạo metadata ban đầu |
| `run_install_runtime()` | Truyền tham số bằng mảng, giữ mã lỗi |
| `cleanup()` | Chỉ dọn staging/lock thuộc lần chạy |
| `main()` | Điều phối và ghi giai đoạn |

Yêu cầu:

- Dùng chế độ lỗi nghiêm ngặt và `pipefail`.
- Bọc luồng chính thành hàm; gọi sau khi shell đã đọc phần định nghĩa.
- Child command nhận stdin rỗng, không lấy mã script làm đầu vào.
- Prompt chỉ qua `/dev/tty`.
- Trap lỗi/hủy phải giữ mã lỗi ban đầu, không để cleanup che lỗi.
- Không đặt biến tác vụ tên `HOME`.
- Không dùng `eval` để dựng lệnh từ đường dẫn/tham số.
- Giữ tương thích Bash 3.2 nếu tiếp tục công bố hỗ trợ macOS.

### 4.4. Đặc thù PowerShell

Các hàm dự kiến tương ứng:

- `Resolve-InstallOptions`
- `Assert-SupportedPlatform`
- `Resolve-InstallDirectory`
- `Enter-InstallLock`
- `Get-SourceSnapshot`
- `Expand-ValidatedSnapshot`
- `Initialize-InstallState`
- `Invoke-CheckedNative`
- `Invoke-ArtemisInstall`

Yêu cầu:

- Script hoạt động dưới cả `iex` và `& ([scriptblock]::Create(...))`.
- Nội dung `.ps1` giữ ASCII theo hợp đồng test encoding hiện hữu.
- Mọi native command phải kiểm `$LASTEXITCODE` ngay sau khi gọi.
- Dùng `try/finally` để đóng file handle lock, phục hồi location và trạng thái session đã thay đổi.
- Lock là sibling file mở với `FileShare.None`.
- Dùng argument array, `-LiteralPath`; không ghép shell command để thao tác file.
- Chỉ bật TLS phù hợp trong phạm vi cần thiết; không tắt xác minh chứng chỉ.
- Không đổi execution policy toàn máy.
- Nếu cần chạy child helper, chạy nền ẩn, không mở console mới.
- Khi gọi bằng `iex`, lỗi phải trở thành terminating error có mã giai đoạn; không in thành công sau lỗi.
- Khi chạy dưới tiến trình `-File`, chuyển mã lỗi installer thành exit code. Không cần đóng terminal tương tác của người dùng để truyền lỗi từ `iex`.

## 5. Metadata, lock và phục hồi

### 5.1. `.artemis-install.json`

Giữ `schema: 1` để tương thích runtime hiện hữu; bổ sung trường theo cách tương thích ngược.

| Trường | Ý nghĩa |
| --- | --- |
| `schema` | Giá trị `1` |
| `source` | `jokerhung/android-automation-studio` |
| `ref` | `nextjs` |
| `directory` | Đường dẫn cài tuyệt đối |
| `archive_sha256` | Định danh archive của lần cài mới |
| `bootstrap_version` | Version hợp đồng entry point/runtime |
| `stage` | `source_ready`, `preparing`, `starting`, `ready` |
| `dependencies` | Fingerprint dependency sau sync và import probe thành công |
| `frontend` | Fingerprint frontend sau build và kiểm artifact thành công |
| `host`, `port` | Giá trị thực tế đã chọn |
| `runtime_env` | Allowlist override đường dẫn/hành vi hiện hữu |
| `server_info_dir` | Vị trí metadata lifecycle do resolver trả về |
| `last_error_code`, `last_error_stage` | Thông tin lỗi đã lọc, nếu có |

Không lưu API key, toàn bộ environment hoặc lifecycle token trong metadata installer.

Ghi JSON qua file tạm rồi replace. Không tự đặt `ready` trước readiness.

Với metadata cũ hợp lệ nhưng thiếu trường mới: đọc tương thích, không bịa `archive_sha256` hoặc tự cập nhật source.

### 5.2. Phân loại đích

| Tình trạng | Hành động |
| --- | --- |
| Chưa tồn tại hoặc rỗng | Cài mới |
| Metadata hợp lệ, source đủ | Tiếp tục hoặc tái sử dụng |
| Metadata hợp lệ, dependency/build dở | Phục hồi sau khi xác nhận không có server cần bảo vệ |
| Metadata hỏng hoặc source thiếu không thể nhận diện an toàn | Dừng mã 3; giữ dữ liệu |
| Thư mục không rỗng không thuộc installer | Dừng mã 3 |
| Có install lock đang giữ | Dừng mã 3 |

Metadata `source_ready` phải có trong snapshot staging trước khi chuyển vào đích để giảm khoảng gián đoạn tạo thư mục không nhận diện được.

Nếu bị ngắt trước bước chuyển source: lần chạy sau dùng staging mới. Không tự xóa staging cũ chưa xác định quyền sở hữu.

### 5.3. Quy tắc lock

- Lấy install lock trước mọi sửa đổi trong đích.
- Runtime manager tiếp tục dùng `.artemis-manager.lock`.
- Không tạo vòng chờ giữa install lock và manager lock.
- Không tự gỡ Bash lock chỉ dựa trên tuổi file.
- Windows OS giải phóng handle khi tiến trình kết thúc; file lock rỗng còn lại không đồng nghĩa đang chạy.
- Cleanup chỉ được xóa đường dẫn staging/lock đã tạo và đã xác minh thuộc lần chạy.

## 6. Tích hợp và chỉnh sửa runtime

### 6.1. Dependency và build

Tái sử dụng:

- `prepare()`
- `dependencies_current()`
- `prepare_node()`
- `frontend_fingerprint()`
- `frontend_assets()`
- `run()`

Luồng:

1. Đọc metadata và khôi phục override đường dẫn đã lưu.
2. Xác định fingerprint, kiểm `.venv` và import probe.
3. Nếu cần sửa dependency/build, kiểm server đang hoạt động trước.
4. Chạy `uv sync --locked --python 3.12 --no-dev`.
5. Kiểm import backend, OpenCV và `artemis_client`.
6. Chuẩn bị cấu hình.
7. Tái sử dụng Node/npm phù hợp hoặc cài Node portable `22.22.3`.
8. Chạy `npm ci --no-audit --no-fund`, sau đó `npm run build`.
9. Kiểm Home, Settings và các asset được tham chiếu.
10. Chỉ lưu fingerprint sau khi bước tương ứng thành công.

Node được tái sử dụng phải đáp ứng mức runtime hiện tại `>=22.12.0` và có npm hoạt động. Không sửa lockfile để né lỗi.

Khi thiếu thư viện OpenCV trên Ubuntu:

- Kiểm `apt-get` và khả năng chạy root hoặc `sudo -n`.
- Chỉ dùng quyền đã có, không chờ password từ pipeline.
- Nếu không thể cài, dừng mã 5 và in tên gói/lệnh khắc phục.
- Không thay đổi package dependency sang biến thể khác để né yêu cầu hệ thống.

### 6.2. Cấu hình

Tái sử dụng `initialize_config()`, `get_env_file()` và `get_config_path()`.

- Tạo `.env` bằng exclusive creation từ `.env.example` khi thiếu.
- Snapshot mới đã chứa `config/artemis.jsonc`.
- Không ghi đè `.env`, JSONC hoặc giá trị do người dùng lưu.
- Cấu hình sai cú pháp: mã 6, chỉ rõ đường dẫn, không in nội dung có secret.
- Với override cấu hình trỏ đến đường dẫn không tồn tại, xử lý rõ ràng; không im lặng dùng cấu hình khác rồi báo thành công.
- Nếu phải tạo cấu hình còn thiếu, chọn đúng đích writable theo resolver và chỉ tạo khi chưa tồn tại.
- Không thay đổi quy tắc resolver toàn hệ thống nếu có thể xử lý trong installer.

### 6.3. Chạy lại và cài dở

- Source hiện hữu không tự nâng cấp.
- Fingerprint đúng và artifact hợp lệ: bỏ qua sync/build.
- Server cùng instance hoạt động tốt: tái sử dụng, không restart.
- Server đang chạy nhưng dependency/build cần sửa: mã 8, in lệnh stop rõ ràng.
- Metadata tiến trình không xác định được: dừng bảo thủ, không coi là stopped.
- Nếu readiness timeout sau spawn: giữ log/metadata, thông báo daemon có thể còn chạy; hướng dẫn `status` và `stop`.
- Lỗi ở bất kỳ bước nào không được in thông báo cài hoàn tất.

### 6.4. Cổng, daemon và readiness

Tái sử dụng `choose_port()`, `manage()`, `wait_ready()` và lifecycle adapter.

Điều kiện thành công đồng thời:

1. Metadata thuộc workspace của bản cài.
2. PID/process identity/listener được xác minh.
3. Lifecycle HTTP trả identity khớp.
4. `/` khớp byte với `out/index.html`.
5. `/settings/` khớp byte với `out/settings/index.html`.
6. Ít nhất một asset được tham chiếu trả đúng byte, không phải HTML fallback.

Không probe địa chỉ `0.0.0.0`; dùng loopback. Kiểm identity và frontend đều phải tránh proxy cho localhost.

Cổng được chỉ định bị chiếm: mã 8. Cổng mặc định bị chiếm chỉ được hỏi cổng thay thế qua terminal khi cho phép tương tác; không có terminal thì dừng.

`--local-only` không được báo thành công bằng cách dùng lại daemon đang bind LAN. Yêu cầu stop rõ ràng trước khi đổi bind.

Dùng cơ chế detached hiện có để daemon sống sau khi terminal đóng. Không tạo cơ chế kill theo cổng.

## 7. File cần tạo/sửa và thứ tự triển khai

| Bước | File/module | Nội dung | Tiêu chí hoàn thành |
| --- | --- | --- | --- |
| 1 | `scripts/install_runtime.py` | Củng cố metadata, stage và phục hồi; quy định hợp đồng bootstrap | Đọc được metadata cũ; metadata lỗi không bị reset |
| 2 | `install.sh` | Entry point Bash, tải archive, staging, lock, uv/Python và gọi runtime | Không phụ thuộc checkout/Git/Python có sẵn; chạy qua pipe |
| 3 | `install.ps1` | Entry point PowerShell tương đương | Chạy qua `iex`/scriptblock, truyền lỗi native đầy đủ |
| 4 | `scripts/bootstrap_common.sh`, `.ps1` | Chuẩn hóa version/checksum/error handling | Binary hỏng hoặc sai hợp đồng không được tái sử dụng im lặng |
| 5 | `scripts/install_runtime.py` | Dependency, config, lỗi hệ thống, `_active`, timeout và logging | Cài dở phục hồi được; không sửa server đang hoạt động |
| 6 | `artemis/runtime/daemon_client.py`; lifecycle module nếu cần | Bảo đảm identity loopback không qua proxy, giữ kiểm instance | Không nhận server khác là bản cài thành công |
| 7 | `start.sh`, `scripts/start.ps1`, `start.bat` | Rà soát đường dẫn tích hợp; chỉ sửa nếu có lệch hợp đồng | Lệnh start của bản cài dùng runtime manager và port đã lưu |
| 8 | `scripts/check_installer_release.py` | Đồng bộ danh sách file; làm rõ phạm vi kiểm archive | Kết quả reachability không bị mô tả là E2E PASS |
| 9 | `README.md`, `docs/installation.md` | Cập nhật theo hành vi thực tế | Hai one-liner, prerequisite, recovery và giới hạn chính xác |
| 10 | `docs/tickets/.../test-report.md` | Tester ghi đúng một testcase và dữ liệu từng môi trường | Có bằng chứng hoặc trạng thái NOT RUN/BLOCKED trung thực |

Không sửa frontend, backend API hoặc lockfile nếu không có lỗi trực tiếp cản trở installer.

## 8. Mã lỗi và giới hạn thời gian

| Mã | Nhóm lỗi |
| --- | --- |
| `0` | Readiness hoàn tất |
| `2` | Tham số hoặc nền tảng không hỗ trợ |
| `3` | Quyền, thư mục đích, metadata hoặc lock |
| `4` | Download, archive hoặc checksum |
| `5` | Python/uv/dependency hoặc thư viện hệ thống |
| `6` | Cấu hình |
| `7` | npm, frontend build hoặc artifact |
| `8` | Cổng, lifecycle hoặc readiness |
| `130` | Hủy khi bắt được tín hiệu |

Giới hạn:

- Download: tối đa 3 lần, tối đa 600 giây mỗi request.
- Dependency, gồm bootstrap Python: tối đa 1.800 giây mỗi command.
- Build: tối đa 1.200 giây.
- Readiness: deadline 120 giây, polling hữu hạn.
- Timeout/hủy chỉ kết thúc cây tiến trình do bước hiện tại tạo; không dừng server khác.

Log phải có giai đoạn, thời điểm, thời lượng, kết quả và mã lỗi. Trước khi có thư mục đích, lỗi ghi ra terminal và log bootstrap tạm có đường dẫn rõ ràng; sau khi có đích, lưu sự kiện tại `logs/install.log`.

Không log toàn bộ environment, `.env` hoặc token lifecycle.

## 9. Cập nhật README và hướng dẫn cài đặt

README cần đưa Internet installer thành luồng rõ ràng, liên kết chi tiết tới `docs/installation.md`:

1. Hai lệnh chính xác theo ticket.
2. Ví dụ Bash có `set -o pipefail` ở shell gọi để không che lỗi curl.
3. Ví dụ truyền thư mục/cổng, gồm đường dẫn có khoảng trắng.
4. Matrix và công cụ bootstrap tối thiểu.
5. Thư mục mặc định, cổng 8009, bind `0.0.0.0`, tùy chọn local-only.
6. Giải thích quyền cài thư viện hệ thống khi cần.
7. Các bước tải runtime, sync, build và start.
8. Lệnh `status`, `start`, `stop`, `restart` dùng interpreter của bản cài.
9. Đường dẫn log, cách chạy lại và xử lý lock/cài dở.
10. Cách mở Settings để cấu hình model và Android.
11. Không yêu cầu API key/Android để chỉ mở giao diện.
12. Trạng thái kiểm chứng public và máy sạch theo bằng chứng thực tế.

Giữ hướng dẫn dành cho developer checkout nhưng phân biệt rõ với bản cài snapshot. Không xóa cảnh báo phát hành chưa hoàn tất chỉ vì hai file đã được tạo local.

## 10. Kiểm thử — đúng một testcase

### TC-INSTALL-001 — Cài vào thư mục mới và truy cập web quản trị

**Trạng thái hiện tại:** `NOT RUN`.

Một định nghĩa testcase, chạy với dữ liệu Linux/Windows. Các lượt chạy không tạo thêm testcase ID.

| Dữ liệu | Môi trường |
| --- | --- |
| Linux | Ubuntu 22.04/24.04, glibc, x86_64, Bash |
| Windows | Windows 11 x64, Windows PowerShell 5.1 hoặc PowerShell 7 |

Báo cáo chính xác OS/shell đã chạy; một lượt PASS không chứng minh các biến thể chưa chạy.

### 10.1. Điều kiện

- Máy/VM sạch, chưa có Git/Python/uv/Node/npm và cache ARTEMIS.
- Có các công cụ bootstrap tối thiểu.
- Thư mục đích mới, rỗng hoặc chưa tồn tại.
- Cổng 8009 trống.
- Internet truy cập được các nguồn dependency.
- Đối với nghiệm thu public, bản triển khai phải được người có quyền phát hành lên `nextjs`.
- Có trình duyệt để kiểm tra hiển thị thực tế.

Không coi workspace hiện tại có `.venv`, cache hoặc build là máy sạch.

### 10.2. Lệnh public

Chạy tại thư mục kiểm thử mới được cho phép.

Linux:

```bash
set -o pipefail
curl -fsSL https://raw.githubusercontent.com/jokerhung/android-automation-studio/nextjs/install.sh \
  | bash -s -- --install-dir "$PWD/artemis" --port 8009 --local-only --non-interactive
```

Windows:

```powershell
& ([scriptblock]::Create((Invoke-RestMethod -Uri 'https://raw.githubusercontent.com/jokerhung/android-automation-studio/nextjs/install.ps1'))) `
  -InstallDir (Join-Path (Get-Location).Path 'artemis') `
  -Port 8009 -LocalOnly -NonInteractive
```

Hai one-liner không tham số vẫn là hợp đồng bắt buộc. Lượt chạy trên dùng cùng entry point với thư mục đích tường minh để thu bằng chứng.

### 10.3. Trình tự và kết quả mong đợi

| Bước | Thực hiện | Kết quả mong đợi |
| --- | --- | --- |
| 1 | Ghi OS, architecture, shell, công cụ và trạng thái đích | Chứng minh điều kiện máy sạch/thư mục mới |
| 2 | Chạy installer, ghi command và thời gian | Không phải clone hoặc cài runtime thủ công |
| 3 | Kiểm tra output và thư mục cài | Có source, `.venv`, cấu hình, metadata, static export và log |
| 4 | Kiểm readiness | Đúng instance, Home/Settings/asset hợp lệ |
| 5 | Mở `/` rồi `/settings/?tab=system` | Giao diện hiển thị, điều hướng được, không trắng trang hoặc “Not Built” |
| 6 | Đóng terminal cài đặt, tải lại trình duyệt | Web tiếp tục hoạt động |
| 7 | Thu bằng chứng và kết luận | Kết quả riêng cho mỗi môi trường thực thi |

Không dùng một khoảng sleep cố định thay thế readiness.

### 10.4. Bằng chứng bắt buộc

- OS/version/architecture/shell và trạng thái runtime trước cài.
- Thư mục đích trước cài.
- Nguồn script/snapshot; checksum archive nếu có.
- Command, thời điểm bắt đầu/kết thúc và trạng thái trả về.
- Log installer đã loại secret; đường dẫn daemon log.
- Phiên bản Python, uv, Node/npm thực dùng.
- Kết quả identity đã lọc token.
- Kết quả HTTP/hash đối chiếu export.
- Screenshot Home và Settings có URL.
- Bằng chứng tải lại thành công sau đóng terminal.

### 10.5. Kiểm chứng local khi chưa được commit/push

Có thể chuẩn bị trước phát hành trong workspace:

- Kiểm syntax Bash/PowerShell.
- Đối chiếu parser, quoting, mã lỗi và cleanup với các test sẵn có.
- Dùng harness hiện hữu hoặc archive fixture đóng từ source local để kiểm đường đi pipeline.
- Mọi staging/artifact local nằm dưới workspace được phép.
- Nếu dùng archive/toolchain giả, báo rõ là kiểm bootstrap với fixture.
- Nếu chạy runtime thật từ snapshot local, báo rõ nguồn local và môi trường thực tế; không gán thành kết quả URL public.

Không thêm testcase nghiệm thu khác. Các kiểm tra syntax/review và suite hiện hữu là bằng chứng hỗ trợ, không thay thế TC-INSTALL-001.

Công cụ `check_installer_release.py` có thể được chạy sau khi có bản public để kiểm file tải được và khớp checkout. Kết quả đó không chứng minh dependency/build hoặc trình duyệt hoạt động.

### 10.6. Quy tắc kết luận

- `PASS`: Đã thực hiện đủ các bước trên môi trường được ghi nhận, có bằng chứng.
- `FAIL`: Có bước thực thi không đạt.
- `BLOCKED`: Bị chặn bởi điều kiện ngoài triển khai, như chưa phát hành hoặc thiếu máy sạch.
- `NOT RUN`: Chưa thực hiện.

Không dùng fixture PASS, kiểm HTTP HEAD, syntax check hoặc một lượt Windows PASS để kết luận cả ticket PASS.

## 11. Phụ thuộc và bàn giao Orchestrator

Không có quyết định cần xác nhận để hoàn thành kế hoạch hoặc bắt đầu triển khai theo đặc tả BA.

Các phụ thuộc trước nghiệm thu cuối:

| Phụ thuộc | Hướng xử lý |
| --- | --- |
| Bản code chưa được phát hành lên `nextjs` | Người có quyền phát hành thực hiện; agent không tự commit/push |
| Chưa có môi trường máy sạch | Orchestrator bố trí môi trường và quyền chạy |
| Môi trường hiện tại hạn chế ghi/network | Developer/tester dùng cơ chế cấp quyền tương ứng khi thực thi |
| URL public chưa được kiểm tra | Ghi chưa xác minh, không suy đoán từ tài liệu lịch sử |

Nếu đến bước nghiệm thu vẫn thiếu điều kiện, Orchestrator cần hỏi cụ thể:

- Ai sẽ phát hành bản triển khai đã review lên branch `nextjs`, và khi nào có thể kiểm tra hai URL?
- Máy/VM Linux và Windows nào được phép dùng để chạy TC-INSTALL-001?

Các câu hỏi này là phụ thuộc ở bước phát hành/kiểm thử, không chặn bàn giao plan cho developer.

**Kết quả bàn giao:** Đủ thiết kế để triển khai hai entry point và tích hợp runtime hiện hữu. Chuyển thẳng Developer; sau đó Tester chạy TC-INSTALL-001 và lập `test-report.md`. Chưa có căn cứ đánh dấu ticket hoặc testcase PASS.