Tôi sẽ đọc tài liệu ticket và đối chiếu các luồng cài đặt, khởi tạo, khởi động hiện có để lập kế hoạch theo file/module và tiêu chí nghiệm thu. Tôi chỉ đọc trong workspace, trả đầy đủ Markdown trong câu trả lời, không ghi file hay commit/push.
Tài liệu yêu cầu bị ngắt ở US-01, nhưng `design.md` có đầy đủ luồng terminal và onboarding. Kế hoạch sẽ ghi rõ các quyết định đề xuất để bù phần còn thiếu, đặc biệt là ma trận hệ điều hành, cách chạy lại và chọn cổng.
Có hai chi tiết ảnh hưởng trực tiếp đến kế hoạch: endpoint xác minh ARTEMIS yêu cầu token nội bộ và chỉ nhận kết nối loopback; lệnh `restart` hiện dừng phiên đang chạy trước khi khởi động lại. Installer cần dùng cơ chế xác minh sẵn có và có nhánh tái sử dụng phiên hiện tại. Tôi cũng sẽ giữ nguyên giới hạn local-only của các API quản trị khi bổ sung truy cập LAN.
# Ticket #2 — Implementation Plan: Cài đặt ARTEMIS qua Internet

- **Tài liệu đích:** `docs/tickets/0c1a1bc5-68d7-4fb5-9f7d-51c8b3eec99c/implementation-plan.md`
- **Workspace:** `C:\hungnm\artemis`
- **Trạng thái:** Kế hoạch triển khai; chưa sửa code, chạy installer hoặc kiểm thử thực tế.
- **Ràng buộc:** Không commit/push. Các đường dẫn bổ sung bên dưới là đề xuất.

## 1. Mục tiêu và căn cứ

Cung cấp `install.sh` cho Linux/macOS và `install.ps1` cho Windows, cho phép người dùng chạy từ Internet khi chưa có mã nguồn, Python, uv hoặc Node.js.

Quy trình phải tải dự án, chuẩn bị công cụ, khởi tạo cấu hình, build frontend, khởi động nền, xác minh ứng dụng và hiển thị URL local/LAN cùng hướng dẫn quản lý.

Đã đối chiếu:

- `requirements.md` và `design.md` trong thư mục ticket.
- Các script cài dependency và khởi động.
- Cấu hình Python, frontend, đường dẫn dữ liệu.
- Cơ chế lifecycle, static hosting và giới hạn truy cập API.
- Settings và các bộ kiểm thử liên quan.

`requirements.md` bị ngắt tại US-01 bởi thông báo model quá tải. Vì vậy, các lựa chọn chưa được BA chốt được ghi là **đề xuất triển khai**, dựa trên yêu cầu gốc, tiêu chí Leader và thiết kế. Chưa có bằng chứng xác nhận cài mới thành công trên ba hệ điều hành.

## 2. Hiện trạng ảnh hưởng đến triển khai

| File/module | Hiện trạng đã đọc | Hướng xử lý |
|---|---|---|
| `install.sh`, `install.ps1` tại gốc | Chưa có | Thêm bootstrap độc lập với vị trí script và thư mục hiện hành |
| `scripts/install_deps.sh` | Cài công cụ, `uv sync`, tạo `.env`, build; chỉ kiểm tra hoặc dùng Node có sẵn | Bổ sung tự cài Node; chuẩn hóa chế độ chạy không tương tác |
| `scripts/install_deps.ps1` | Có fallback portable cho một số công cụ; dùng `uv sync` | Tái sử dụng, kiểm tra rõ mã thoát và thống nhất lockfile |
| `start.sh` | Có logic cài Node, build và chạy foreground; mặc định cổng `8009` | Chia sẻ logic chuẩn bị, bổ sung quản lý bản cài mà không lặp build |
| `scripts/start.ps1`, `start.bat` | Có daemon/stop; daemon kiểm tra TCP; chưa có tham số bind host trong PowerShell | Truyền host rõ ràng, thay điều kiện thành công bằng xác minh HTTP |
| `pyproject.toml`, `uv.lock` | Python `>=3.12`; dependency workspace tại `packages/artemis-client` | Tải đầy đủ source và đồng bộ theo lockfile |
| `apps/showcase_next/package.json` | Node `>=20.9.0`; có npm lockfile | Cài phiên bản Node đã kiểm chứng, dùng `npm ci` |
| `apps/showcase_next/next.config.ts` | Static export, trailing slash | Backend phục vụ frontend; không cần Next.js server riêng |
| `artemis/interfaces/cli/commands/init.py` | Wizard tương tác, bắt nhập API key và ghi `.env` | Không gọi tự động trong installer |
| `artemis/config/paths.py` | Phân biệt source checkout và user data; có override đường dẫn | Khởi tạo theo đường dẫn thực sự được runtime sử dụng |
| `artemis/runtime/server_lifecycle.py` | Metadata theo workspace/cổng; xác minh process và HTTP bằng token | Tái sử dụng, không viết lại cơ chế xác minh bằng PID hoặc TCP |
| `artemis/runtime/background_runtime.py` | Có `ensure_background_runtime()` để gắn vào phiên hiện có hoặc khởi động | Dùng cho cài mới/chạy lại |
| `artemis/interfaces/cli/commands/server_lifecycle.py` | `restart` chủ động dừng phiên ARTEMIS hiện tại | Không gọi `restart` vô điều kiện khi chạy lại installer |
| `apps/admin_console/server.py` | Khi thiếu frontend có thể trả trang “Not Built” với HTTP thành công | Kiểm tra HTTP 200 đơn thuần chưa đủ |
| `apps/admin_console/routers/system.py` | Endpoint lifecycle cần token và kết nối loopback | Kiểm tra danh tính từ local; giữ nguyên giới hạn này |
| `apps/admin_console/core/security.py` | Kiểm tra Host/Origin; có mô hình không yêu cầu đăng nhập | Không nới middleware để làm LAN hoạt động |
| `.github/workflows/ci.yml` | Có kiểm tra Python/Next.js nhưng chưa chứng minh bootstrap trên máy sạch | Bổ sung kiểm thử installer và nghiệm thu VM |

## 3. Hợp đồng triển khai đề xuất

### 3.1. Ma trận hỗ trợ ban đầu

Đề xuất ma trận nghiệm thu dưới đây; chỉ công bố “được hỗ trợ” sau khi vượt qua kiểm thử:

| Hệ điều hành | Kiến trúc | Shell |
|---|---|---|
| Windows 11 | x64 | Windows PowerShell 5.1; kiểm tra thêm PowerShell 7 |
| Ubuntu 22.04 và 24.04 | x86_64 | Bash |
| macOS 14 và 15 | Intel x86_64, Apple Silicon arm64 | Bash mặc định của hệ thống |

Các bản Linux khác, Windows ARM64, Linux ARM64 và Linux dùng musl chưa thuộc cam kết ban đầu. Installer phải phát hiện và báo rõ môi trường ngoài ma trận.

“Máy sạch” vẫn cần hệ điều hành, kết nối HTTPS và công cụ để nhận lệnh đầu tiên:

- Linux/macOS: Bash, `curl`, chứng chỉ CA và công cụ giải nén.
- Windows: PowerShell với khả năng tải HTTPS và giải nén ZIP.
- Tài liệu có hướng dẫn chuẩn bị nếu thiếu công cụ tải ban đầu.

Không giả định đã có Git, Python, uv, Node.js, npm, Homebrew hoặc WinGet.

### 3.2. Chính sách mặc định

| Nội dung | Quyết định đề xuất |
|---|---|
| Nguồn | `jokerhung/android-automation-studio`, nhánh `nextjs` |
| Tải source | Archive qua HTTPS; không bắt buộc Git |
| Thư mục Windows | `%LOCALAPPDATA%\Programs\Artemis` |
| Thư mục Linux/macOS | `$HOME/.local/share/artemis` |
| Python | Nhánh Python 3.12 đã kiểm chứng, do uv quản lý |
| Node.js | Phiên bản 22.x cụ thể đã kiểm chứng với lockfile; không dùng `latest` |
| Cổng lần đầu | `8009` |
| Bind lần đầu | `0.0.0.0` để đáp ứng local/LAN; hỗ trợ lựa chọn chỉ local |
| Chạy ứng dụng | Nền, không tự đăng ký chạy cùng hệ điều hành |
| Mở trình duyệt | Tùy chọn; thất bại không làm installer thất bại |
| Chạy lại | Kiểm tra/phục hồi cùng bản cài; không tự nâng cấp, reset hoặc restart |
| API key và Android | Không phải điều kiện để mở web |
| MCP cho IDE | Không tự sửa cấu hình IDE; cung cấp hướng dẫn riêng |

Cần ghi rõ trong hướng dẫn rằng bind LAN cho phép các máy có kết nối mạng tới server truy cập giao diện. Không tự mở firewall hoặc thay đổi các API vốn chỉ được gọi từ local.

### 3.3. Tham số public

Các tham số sau là giao diện cần triển khai, chưa phải khả năng hiện có:

| Bash | PowerShell | Ý nghĩa |
|---|---|---|
| `--install-dir PATH` | `-InstallDir PATH` | Chọn vị trí cài |
| `--port N` | `-Port N` | Chọn cổng cụ thể |
| `--local-only` | `-LocalOnly` | Bind `127.0.0.1` |
| `--non-interactive` | `-NonInteractive` | Không chờ nhập liệu |
| `--open` | `-Open` | Mở trình duyệt sau xác minh |
| `--help` | `-Help` | In cách dùng và mặc định |

Quy tắc chọn cổng:

1. Chạy lại ưu tiên cổng đã lưu của bản cài.
2. Nếu đúng phiên ARTEMIS của bản cài đang hoạt động, xác minh và tái sử dụng.
3. Nếu cổng bị dịch vụ khác chiếm, không dừng dịch vụ đó.
4. Trong terminal tương tác, đề xuất cổng khả dụng hoặc cho nhập cổng.
5. Không có terminal: thoát với hướng dẫn truyền cổng khác; không âm thầm đổi cổng.
6. Nếu người dùng chỉ định cổng, phải dùng đúng cổng hoặc báo lỗi.

## 4. Kiến trúc và phân công file

| File/module | Thay đổi dự kiến |
|---|---|
| `install.sh` — mới | Bootstrap Bash: tham số, preflight, tải source, khóa cài đặt, điều phối |
| `install.ps1` — mới | Bootstrap PowerShell tương đương, chạy được qua scriptblock từ Internet |
| `scripts/install_deps.sh`, `scripts/install_deps.ps1` | Chuẩn hóa công đoạn công cụ, Python, cấu hình và build; chế độ không tương tác |
| `scripts/bootstrap_common.sh`, `scripts/bootstrap_common.ps1` — mới | Hàm dùng chung cho dependency/start: tải có retry, PATH, phiên bản công cụ, thông báo lỗi |
| `scripts/install_runtime.py` — mới | Điều phối sau khi Python sẵn sàng: cấu hình, state bản cài, start/status/stop/restart, kiểm tra web và in URL |
| `artemis/runtime/network_urls.py` — mới | Liệt kê IPv4/interface bằng `psutil`, lọc và tạo URL |
| `start.sh`, `scripts/start.ps1`, `start.bat` | Tích hợp host/cổng, chế độ đã chuẩn bị, daemon và HTTP readiness; giữ hành vi dùng trực tiếp |
| `artemis/runtime/background_runtime.py`, `server_lifecycle.py` | Tái sử dụng; chỉ bổ sung API nhỏ nếu cần, giữ kiểm tra danh tính |
| Settings và i18n hiện có | Bổ sung hướng dẫn onboarding còn thiếu trong phạm vi mục 5.7 |
| `tests/unit/`, `tests/integration/installer/` | Kiểm thử hợp đồng, lỗi và tích hợp installer |
| `.github/workflows/installer.yml` — mới | Kiểm tra Bash/PowerShell và smoke test ba hệ điều hành |
| `README.md`, `README_VI.md`, `docs/installation.md` — mới | Lệnh cài, ma trận hỗ trợ, quản lý và xử lý lỗi |

Các bootstrap tại gốc phải tự chứa phần cần thiết trước khi source được tải. Không `source`/dot-source một helper chưa tồn tại trên máy.

Không thêm dependency Python chỉ để dò IP: dự án đã có `psutil`.

## 5. Các bước triển khai

### 5.1. Bước 1 — Chốt hợp đồng và nguồn công cụ

**Phụ thuộc:** Phần yêu cầu và thiết kế hiện có.

**Công việc:**

- Ghi ma trận OS/kiến trúc, tham số, thư mục, cổng và hành vi chạy lại vào tài liệu cài đặt.
- Chọn phiên bản uv, Python, Node cùng nguồn binary phù hợp từng nền tảng.
- Phân loại dependency:
  - Bắt buộc cho web: runtime Python, dependency backend, Node/npm trong giai đoạn build.
  - Cần cho thao tác Android: ADB.
  - Phụ thuộc tính năng: scrcpy, FFmpeg và thành phần liên quan.
- Xác định thư viện hệ điều hành cần cho các Python wheel trên máy sạch, đặc biệt import OpenCV trên Linux.
- Chọn cách tải có xác minh checksum khi nguồn phát hành cung cấp checksum.

**Hoàn thành khi:**

- Có bảng công cụ, phiên bản và phương án cài cho từng hàng ma trận.
- Không còn giả định phải có sẵn Git, Homebrew, WinGet hoặc runtime phát triển.
- Thiếu thành phần tùy chọn được báo riêng, không bị đánh dấu là đã cài thành công.

### 5.2. Bước 2 — Bootstrap và tải source an toàn

**File:** `install.sh`, `install.ps1`.

**Công việc:**

1. Parse tham số, phát hiện OS/kiến trúc, kiểm tra quyền ghi.
2. Không suy ra thư mục cài từ `$BASH_SOURCE`, `$PSScriptRoot` hoặc CWD khi chạy qua pipe/scriptblock.
3. Tạo thư mục staging riêng và khóa theo đường dẫn bản cài để tránh hai installer cùng ghi.
4. Tải archive với retry giới hạn; giải nén trong staging.
5. Kiểm tra cấu trúc cần thiết: `pyproject.toml`, `uv.lock`, `artemis/`, `apps/`, `packages/artemis-client`, các script và cấu hình.
6. Chỉ đưa source vào vị trí chính thức khi archive hợp lệ.
7. Lưu metadata không chứa bí mật tại `.artemis-install.json`: nguồn, revision nếu xác định được, đường dẫn, phiên bản schema và trạng thái công đoạn.
8. Với thư mục không rỗng nhưng không nhận diện được bản cài: dừng, không ghi đè.
9. Với bản cài đã nhận diện: dùng source hiện có; không tải nhánh mới đè lên.
10. Khi lỗi/hủy, chỉ dọn staging và tài nguyên do lần chạy này tạo.

Prompt Bash đọc từ `/dev/tty`; PowerShell kiểm tra khả năng tương tác trước khi hỏi. Không dùng stdin chứa script để đọc lựa chọn.

Tổ chức bootstrap để chỉ bắt đầu công việc sau khi đã đọc đủ phần khai báo và lời gọi entry point cuối script.

**Hoàn thành khi:**

- Chạy được từ thư mục bất kỳ, kể cả đường dẫn có dấu cách.
- Archive lỗi hoặc tải dở không được nhận là bản cài hoàn chỉnh.
- Hai installer không đồng thời sửa cùng bản cài.
- Chạy lại không thay mã nguồn hoặc dữ liệu người dùng.

### 5.3. Bước 3 — Chuẩn bị công cụ và dependency

**File:** `scripts/install_deps.*`, `scripts/bootstrap_common.*`, phần liên quan trong `start.*`.

**Công việc:**

- Tách các hàm đang trùng giữa install/start vào helper theo shell.
- Giữ công cụ có phiên bản tương thích; bổ sung bản do installer quản lý khi thiếu hoặc quá cũ.
- Bổ sung tự cài Node cho Bash, không chỉ kiểm tra Node có sẵn.
- Ưu tiên cài trong tài khoản người dùng; chỉ dùng quyền quản trị cho thành phần thực sự cần.
- Hỗ trợ macOS không có Homebrew cho luồng web cốt lõi.
- Cập nhật PATH trong tiến trình hiện tại và lệnh quản lý để dùng được ngay, không yêu cầu mở terminal mới.
- Chọn Python rõ ràng; chạy `uv sync --locked`.
- Windows kiểm tra `$LASTEXITCODE` sau từng chương trình native, không dựa riêng vào `try/catch`.
- Các lỗi bắt buộc phải dừng; lỗi công cụ tùy chọn phải có thông báo và bước khắc phục.
- Không tự cấu hình MCP hoặc chạy wizard nhập API key.

**Hoàn thành khi:**

- Máy chưa có Python/uv/Node tạo được môi trường Python và chạy được npm.
- Dependency lỗi không bị che bởi thông báo thành công.
- `uv.lock` không bị thay đổi trong quá trình cài.
- Không cài hoặc nâng cấp lặp khi thành phần đã đạt yêu cầu.

### 5.4. Bước 4 — Khởi tạo cấu hình và phục hồi

**File:** `scripts/install_runtime.py`, `scripts/install_deps.*`; dùng `artemis/config/paths.py`.

**Công việc:**

- Dùng quy tắc runtime để xác định `.env` và dữ liệu; không hardcode một file mà ứng dụng không đọc.
- Tạo `.env` từ template khi chưa tồn tại.
- Dùng cơ chế cấu hình mặc định hiện có; chỉ bổ sung file còn thiếu nếu runtime cần.
- Không gọi `artemis init`: lệnh này yêu cầu key và ghi cấu hình.
- Không thay `.env`, cấu hình JSONC, database, traces hoặc khóa đã lưu khi chạy lại.
- Lưu host/cổng và các đường dẫn công cụ cần để khởi động lại trong metadata bản cài, tách khỏi bí mật.
- Sau công đoạn lỗi, kiểm tra lại artifact thực tế; không tin hoàn toàn dấu “đã xong”.
- Nếu bản cài đang chạy và cần sửa dependency/build, yêu cầu dừng có chủ đích; không sửa môi trường đang phục vụ ngầm.

**Hoàn thành khi:**

- Không có key hoặc Android vẫn tiếp tục tới bước mở web.
- Hash cấu hình và nội dung dữ liệu không đổi sau lần chạy lại bình thường.
- Cấu hình lỗi được báo đúng file; không reset tự động.
- Không ghi API key hoặc lifecycle token ra terminal/log.

### 5.5. Bước 5 — Build frontend

**File:** `scripts/install_deps.*`, helper dùng chung; frontend hiện có.

**Công việc:**

- Dùng `npm ci` theo `package-lock.json`, sau đó `npm run build`.
- Không fallback sang `npm install` khi lockfile của source tải về bị thiếu.
- Kiểm tra `out/index.html`, route Settings và tài nguyên `_next`.
- Tránh build hai lần khi installer tiếp tục gọi luồng start.
- Chạy lại bản cài hoàn chỉnh không build nếu đầu vào không đổi.
- Không nhận artifact dở dang từ lần build lỗi là hợp lệ.

**Hoàn thành khi:**

- Build lỗi trả mã thất bại và không công bố ứng dụng sẵn sàng.
- Có đầy đủ static export phục vụ Home và Settings.
- Không cần tiến trình Next.js riêng sau cài đặt.

### 5.6. Bước 6 — Khởi động, HTTP readiness và URL

**File:** `scripts/install_runtime.py`, `artemis/runtime/network_urls.py`, `start.*`; tái sử dụng runtime lifecycle.

**Công việc:**

1. Dùng `ensure_background_runtime()` và lifecycle adapter để tái sử dụng hoặc khởi động đúng bản cài.
2. Truyền host/cổng rõ ràng, không phụ thuộc mặc định `8000` của CLI.
3. Nếu phiên hiện tại chỉ bind loopback, không quảng bá rằng LAN dùng được; đưa lựa chọn restart có chủ đích để đổi bind.
4. Windows khởi động nền không tạo cửa sổ console phụ, giữ cơ chế phù hợp đang có.
5. Xác minh danh tính qua cơ chế metadata/process/HTTP token hiện hữu.
6. Kiểm tra `/`, `/settings/` và ít nhất một tài nguyên frontend thực tế.
7. Loại trường hợp trang fallback “Not Built” dù HTTP trả 200.
8. Chỉ công bố thành công sau khi cả danh tính và giao diện đạt.
9. Liệt kê IPv4 từ interface đang hoạt động; loại loopback, unspecified, link-local và địa chỉ trùng.
10. Gắn nhãn riêng interface VPN/ảo khi nhận diện được; không dùng kết nối Internet bên ngoài làm cách duy nhất để tìm IP.

Output cuối phải chứa:

- `http://localhost:<port>`
- `http://127.0.0.1:<port>`
- URL IPv4 LAN theo interface nếu bind cho phép.
- Link Settings System, Models và Android.
- Thư mục cài, log, lệnh start/status/stop/restart với đường dẫn và cổng thực tế.
- Trạng thái “IP đã phát hiện; chưa xác minh truy cập từ thiết bị khác”.

Không in `0.0.0.0` như URL truy cập. Không có LAN vẫn được hoàn tất local.

Lệnh quản lý dùng interpreter của bản cài và helper đã tạo, có quoting đúng; stop/status không chạy lại cài dependency hoặc build.

**Hoàn thành khi:**

- Dịch vụ khác trên cùng cổng không thể tạo kết quả thành công giả.
- Đóng terminal không làm daemon ngừng.
- Chạy lại không sinh thêm daemon hoặc tự dừng phiên hiện tại.
- Tất cả URL và lệnh quản lý dùng đúng cổng thực tế.
- Các API lifecycle vẫn chỉ được phép từ local và có token.

### 5.7. Bước 7 — Hoàn thiện terminal và onboarding

**File:**

- Các bootstrap/helper.
- `apps/showcase_next/src/features/settings/android-system-panels.tsx`
- `apps/showcase_next/src/features/settings/general-model-panels.tsx`
- `apps/showcase_next/src/lib/i18n/catalogs.ts`
- Route Settings và kiểm thử liên quan nếu cần.

**Công việc:**

- Thống nhất sáu bước terminal theo `design.md`.
- Dùng trạng thái ASCII `[OK]`, `[DANG]`, `[CHO]`, `[GIU]`, `[CAN]`, `[LOI]`, `[HUY]`.
- Không dùng phần trăm hoặc ETA giả; khi chuyển output vào file, tắt animation/màu.
- Mỗi lỗi có công đoạn, nguyên nhân, log, trạng thái tiến trình và cách chạy lại.
- Giữ PowerShell source tương thích quy tắc ASCII hiện có.
- Tận dụng Settings System/Models/Android; bổ sung phần hướng dẫn còn thiếu, không tạo wizard mới.
- Phân biệt loading, lỗi kiểm tra, thiếu model, không có thiết bị, unauthorized/offline và readiness đạt.
- Nếu refresh lỗi nhưng còn dữ liệu cũ, giữ dữ liệu và gắn nhãn chưa cập nhật.
- Không coi trường key để trống là yêu cầu xóa key; không lưu key vào URL hoặc browser storage.
- Với thao tác chỉ local, hiển thị hướng dẫn mở URL local thay vì nới quyền backend.

**Hoàn thành khi:**

- Các trạng thái T1–T4 trong thiết kế đều có nội dung tương ứng.
- Mở Settings được khi chưa cấu hình model và chưa kết nối Android.
- Các thay đổi web dùng cơ chế Việt/Anh, bàn phím và trạng thái truy cập hiện có.

## 6. Timeout, retry và mã thoát

Các giá trị sau là đề xuất ban đầu, cần điều chỉnh theo số đo nghiệm thu:

| Công đoạn | Chính sách |
|---|---|
| Tải file | Connect timeout 15 giây; tối đa 10 phút/lần; tổng tối đa 3 lần, backoff |
| Cài dependency | Deadline 30 phút/công đoạn; log tiến độ; không tự lặp lỗi quyền hoặc phiên bản |
| Build frontend | Deadline 20 phút; không retry mù |
| HTTP readiness | Tổng 120 giây, request timeout 2 giây, poll khoảng 1 giây |
| Graceful stop | Tái sử dụng timeout lifecycle; không kill process không xác minh |
| Chờ nhập liệu | Chỉ khi có terminal; non-interactive phải kết thúc rõ ràng |

Phải xử lý race khi cổng bị chiếm giữa preflight và lúc bind. Không công bố thành công chỉ vì cổng từng trống.

| Mã thoát đề xuất | Ý nghĩa |
|---|---|
| `0` | Giao diện đã được xác minh; có thể còn thành phần tùy chọn cần cấu hình |
| `2` | Tham số hoặc môi trường không hỗ trợ |
| `3` | Quyền ghi, thư mục đích hoặc khóa cài đặt |
| `4` | Tải xuống, checksum hoặc archive |
| `5` | Dependency bắt buộc |
| `6` | Cấu hình không hợp lệ |
| `7` | Build/artifact |
| `8` | Cổng, daemon hoặc HTTP readiness |
| `130` | Người dùng hủy khi có thể bắt sự kiện hủy |

Với Bash, tài liệu cần nêu cách dùng `pipefail` để lỗi tải của `curl` không bị che bởi mã thoát của `bash`.

## 7. Kế hoạch kiểm thử

### 7.1. Kiểm thử tự động

| Nhóm | Nội dung |
|---|---|
| Parser và shell | Bash syntax/ShellCheck; PowerShell parser trên 5.1/7; tham số sai; pipe/scriptblock |
| Bootstrap | Không có source, đường dẫn có dấu cách/Unicode, archive lỗi, tải dở, thư mục lạ, hai lần cài đồng thời |
| Công cụ | Thiếu uv/Python/Node; Node cũ; PATH chưa refresh; không có WinGet/Homebrew; native command trả lỗi |
| Cấu hình | Tạo khi thiếu; giữ hash `.env`/JSONC; tôn trọng override đường dẫn; không lộ bí mật |
| Rerun | Không tự nâng cấp source, không rebuild/sync không cần thiết, không restart phiên khỏe |
| Lifecycle | Sai server, token sai, metadata cũ, ARTEMIS từ workspace khác, timeout, server chết giữa poll |
| Frontend | HTTP 200 fallback, thiếu asset, Settings không tải được, artifact dở |
| IP | Nhiều interface, IP trùng, VPN, không LAN, link-local, local-only |
| Quản lý | Start/status/stop/restart giữ host/cổng và nhận diện đúng bản cài |
| Hồi quy web | Settings thiếu key/device, loading/error/stale, giữ key, điều hướng tab |

Mở rộng các bộ hiện có khi phù hợp:

- `tests/unit/test_bootstrap_scripts_encoding.py`: bao phủ PowerShell tại gốc và helper mới.
- `tests/unit/test_install_paths.py`
- `tests/unit/runtime/test_background_runtime.py`
- `tests/unit/runtime/test_server_process_lifecycle.py`
- `tests/unit/admin_console/test_static_hosting.py`
- `tests/unit/admin_console/test_security_boundary.py`
- `apps/showcase_next/tests/settings*.test.tsx`

Test shell phải thực thi hành vi với dependency giả lập; không chỉ tìm chuỗi trong script.

### 7.2. Nghiệm thu trên môi trường sạch

Thực hiện trên từng hàng ma trận:

1. Bắt đầu từ snapshot không có source, uv, Python, Node và npm.
2. Chạy entry point qua HTTP bằng Bash pipe hoặc PowerShell scriptblock.
3. Xác nhận toàn bộ luồng tới Home và Settings.
4. Không cung cấp key và không cắm Android; giao diện vẫn mở được.
5. Đóng terminal, kiểm tra daemon còn hoạt động.
6. Chạy lại; cấu hình giữ nguyên, không có daemon trùng.
7. Chiếm cổng `8009` bằng dịch vụ khác; xác nhận prompt/lỗi và cổng thay thế.
8. Kiểm tra lỗi mạng, thiếu quyền, dependency lỗi, build lỗi và readiness timeout.
9. Thực hiện các lệnh quản lý được installer in ra.
10. Truy cập URL LAN từ thiết bị thứ hai cùng mạng, kiểm tra Home, Settings và static assets.

GitHub-hosted runner có sẵn nhiều công cụ, vì vậy smoke test CI không thay thế bằng chứng “từ con số 0” trên VM sạch.

Ở bước lập kế hoạch này không viết test hoặc điều khiển Android. Nếu giai đoạn triển khai bổ sung kiểm thử hành vi trên Android, phải khám phá ứng dụng bằng ARTEMIS trước khi viết test, kiểm tra `adb devices -l` và tuân thủ quy tắc chọn thiết bị trong hướng dẫn dự án.

### 7.3. Bằng chứng cần lưu

- OS, kiến trúc, shell, phiên bản công cụ và revision source.
- Log installer đã loại bí mật, mã thoát.
- Kết quả HTTP và ảnh Home/Settings.
- Hash cấu hình trước/sau chạy lại.
- Bằng chứng daemon còn sống sau khi đóng terminal.
- Bằng chứng truy cập từ thiết bị LAN thứ hai.
- Kết quả từng kịch bản lỗi.

## 8. Phụ thuộc và thứ tự bàn giao

| Mốc | Phụ thuộc | Đầu ra |
|---|---|---|
| M1 — Hợp đồng installer | Tài liệu ticket | Ma trận, tham số, phiên bản, chính sách quyền và chạy lại |
| M2 — Bootstrap | M1 | Tải source và nhận diện bản cài |
| M3 — Dependency/cấu hình | M2 | Môi trường chạy được, cấu hình bảo toàn |
| M4 — Build | M3 | Static export hoàn chỉnh |
| M5 — Lifecycle/URL | M3, M4 | Daemon được xác minh, URL và lệnh quản lý |
| M6 — Terminal/onboarding | M1, M5 | Trải nghiệm theo thiết kế |
| M7 — Nghiệm thu | M2–M6 | Bằng chứng máy sạch, rerun, lỗi và LAN |

Có thể xây dựng logic liệt kê IP, kiểm thử lifecycle và nội dung tài liệu sau M1 trong khi hoàn thiện bootstrap. Nghiệm thu toàn luồng chỉ bắt đầu khi M2–M6 được tích hợp.

## 9. Rủi ro và biện pháp

| Rủi ro | Biện pháp |
|---|---|
| Yêu cầu BA chưa hoàn chỉnh | Ghi rõ quyết định đề xuất; hoàn thiện yêu cầu trước khi công bố ma trận hỗ trợ |
| Phiên bản binary khác giữa OS/kiến trúc | Chốt phiên bản và checksum, chạy trên từng môi trường cam kết |
| Python wheel cần thư viện hệ thống | Kiểm tra import/backend trên VM sạch; bổ sung dependency bắt buộc có căn cứ |
| Prompt bị treo khi pipe | Đọc terminal riêng; non-interactive fail rõ khi thiếu lựa chọn |
| Cài lại làm mất cấu hình hoặc ảnh hưởng phiên chạy | Không overwrite/upgrade ngầm; kiểm tra trước khi sửa môi trường đang dùng |
| TCP hoặc HTTP fallback gây thành công giả | Xác minh lifecycle và frontend artifact/route/assets |
| LAN bị firewall hoặc mạng chặn | Tách phát hiện IP khỏi kiểm chứng kết nối; hướng dẫn đúng interface và cổng |
| Bind LAN mở rộng phạm vi truy cập ứng dụng không yêu cầu đăng nhập | Công bố hành vi, có local-only, giữ Host/Origin và API local-only |
| Lặp logic giữa installer/start | Chia sẻ helper và dùng runtime lifecycle hiện có |
| PowerShell encoding/quoting | Giữ source ASCII, kiểm tra PowerShell 5.1, đường dẫn Unicode/dấu cách |
| Thay đổi nhánh `nextjs` trong lúc cài | Dùng cùng một snapshot source; lưu revision khi xác định được |
| CI không phải máy sạch | Nghiệm thu bổ sung bằng snapshot VM và thiết bị LAN thật |

## 10. Definition of Done

- [ ] Có `install.sh` và `install.ps1` chạy từ Internet, không yêu cầu clone trước.
- [ ] Công bố ma trận OS/kiến trúc có bằng chứng kiểm thử.
- [ ] Máy sạch tự chuẩn bị đủ dependency để build và mở web.
- [ ] Bootstrap hoạt động khi chạy qua pipe/scriptblock và không có TTY.
- [ ] Tải lỗi, thiếu quyền, dependency lỗi, build lỗi và xung đột cổng trả mã thoát đúng.
- [ ] Chạy lại giữ nguyên cấu hình, khóa API và dữ liệu; không tự nâng cấp hoặc restart.
- [ ] Chỉ báo thành công sau khi xác minh đúng ARTEMIS và giao diện thực tế.
- [ ] URL localhost, loopback và LAN dùng đúng cổng/bind thực tế.
- [ ] Có bằng chứng truy cập từ thiết bị cùng LAN; không có LAN vẫn hoàn tất local.
- [ ] Daemon tồn tại sau khi đóng terminal; lệnh quản lý hoạt động.
- [ ] Thiếu key hoặc Android vẫn mở được Settings.
- [ ] Không lộ API key/lifecycle token, không nới giới hạn API local-only.
- [ ] Có tài liệu cài mới, chạy lại, dừng, khởi động lại và xử lý sự cố.
- [ ] Kiểm thử liên quan và hồi quy đạt; lưu bằng chứng trong thư mục ticket.
- [ ] Entry point và helper được phát hành cùng revision trước khi kiểm tra lệnh public cuối cùng.

Việc đưa file lên nhánh `nextjs` là bước phát hành riêng của người có quyền. Kế hoạch này không thực hiện commit/push hoặc coi URL public đã hoạt động.