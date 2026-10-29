Tôi sẽ đọc cấu trúc mã nguồn và hướng dẫn cài đặt trong workspace để soạn đặc tả cho planner, gồm đúng một testcase end-to-end. Tôi chỉ đọc file, không chạy git; nội dung Markdown sẽ được trả về để hệ thống lưu.
README đã nêu hai lệnh cài qua Internet, nhưng workspace hiện thiếu cả `install.sh` và `install.ps1` ở thư mục gốc. Các helper bootstrap và runtime đã có; tôi sẽ ghi rõ phần có thể tái sử dụng và phân biệt yêu cầu nghiệm thu với trạng thái chưa kiểm thử.
# Ticket #3 — Đặc tả cài đặt hệ thống qua Internet

- **Vai trò:** Business Analyst.
- **Workspace khảo sát:** `C:\hungnm\artemis`.
- **Tài liệu bàn giao:** `docs/tickets/1b5c49f9-57c2-4fad-9e20-a108993071f9/requirements.md`.
- **Trạng thái:** Đã khảo sát mã nguồn; chưa triển khai, chưa chạy installer hoặc kiểm thử end-to-end.
- **Giới hạn thực hiện:** Chỉ đọc file trong workspace, không sửa file, không chạy git.

## 1. Mục tiêu

Người dùng trên máy mới có kết nối Internet chạy một lệnh phù hợp hệ điều hành để tải hệ thống, chuẩn bị dependency, tạo cấu hình còn thiếu, build giao diện và khởi động web quản trị.

**Linux:**

```bash
curl -fsSL https://raw.githubusercontent.com/jokerhung/android-automation-studio/nextjs/install.sh | bash
```

**Windows:**

```powershell
irm https://raw.githubusercontent.com/jokerhung/android-automation-studio/nextjs/install.ps1 | iex
```

Cài đặt chỉ được báo thành công khi web quản trị của bản vừa cài thực sự sẵn sàng.

## 2. Hiện trạng và bằng chứng khảo sát

| File/thành phần | Quan sát từ workspace | Ý nghĩa |
| --- | --- | --- |
| `install.sh`, `install.ps1` | Không tìm thấy ở thư mục gốc | Thiếu hai entry point mà ticket yêu cầu |
| `README.md` | Đã hướng dẫn hai lệnh Internet và URL mặc định `http://localhost:8009/` | Tài liệu đang mô tả khả năng chưa đầy đủ trong checkout |
| `docs/installation.md` | Đã mô tả môi trường, tùy chọn, quyền, chạy lại, mã lỗi và quản lý tiến trình | Tận dụng làm hợp đồng triển khai; cập nhật theo kết quả thực tế |
| `scripts/bootstrap_common.sh`, `scripts/bootstrap_common.ps1` | Có bootstrap uv `0.12.13`, kiểm tra SHA-256 | Có thể tái sử dụng |
| `scripts/install_runtime.py` | Có chuẩn bị dependency, Node portable, build, cấu hình, quản lý daemon và kiểm tra HTTP | Ưu tiên tích hợp thay vì viết lại |
| `pyproject.toml`, `uv.lock` | Python `>=3.12`, workspace package `artemis-client` cùng dependency backend | Phải tải đầy đủ source và lockfile |
| `apps/showcase_next/package.json` | Next.js, React, TypeScript; Node khai báo `>=20.9.0`; có script build | Cần Node/npm để build |
| `scripts/install_runtime.py` | Dùng Node có sẵn `>=22.12.0` hoặc portable `22.22.3` | Yêu cầu Node của installer chặt hơn mức tối thiểu frontend |
| `apps/showcase_next/next.config.ts` | `output: 'export'`, `trailingSlash: true` | Frontend production là static export |
| `apps/admin_console/server.py` | Phục vụ frontend từ `apps/showcase_next/out` | Backend và frontend dùng chung origin, không cần Next.js server riêng |
| `.env.example`, `config/artemis.jsonc` | Có template môi trường và cấu hình hệ thống | Khởi tạo phần còn thiếu, bảo toàn cấu hình đã có |
| `start.sh`, `scripts/start.ps1` | Nhận diện `.artemis-install.json`, chuyển sang runtime manager | Installer cần tạo metadata tương thích |
| `scripts/check_installer_release.py` | Kiểm tra public entry point, helper, lockfile và source archive | Công cụ hỗ trợ kiểm tra phát hành; không thay thế E2E |

`docs/installation.md` ghi nhận trạng thái phát hành chưa đầy đủ tại ngày 2026-10-28. Đây là thông tin lịch sử trong tài liệu, **không phải kết quả kiểm tra Internet ở bước BA này**.

Không có bằng chứng runtime để kết luận hai lệnh Internet hiện thành công hay thất bại.

## 3. Phạm vi

### 3.1. Trong phạm vi

1. Tạo hai entry point ở gốc repository.
2. Hỗ trợ chạy trực tiếp từ pipeline, không yêu cầu checkout có sẵn.
3. Tải snapshot của `jokerhung/android-automation-studio`, branch `nextjs`.
4. Chuẩn bị Python, uv, Node/npm và dependency ứng dụng.
5. Tạo môi trường, cấu hình, metadata và log cần thiết.
6. Build frontend và khởi động backend phục vụ web quản trị.
7. Kiểm tra readiness trước khi thông báo thành công.
8. Cập nhật README và hướng dẫn cài đặt.
9. Đúng **một định nghĩa testcase E2E**, dùng cho hai nền tảng.

### 3.2. Ranh giới nghiệm thu

“Cài toàn bộ hệ thống” trong ticket được nghiệm thu ở mức backend, frontend và dependency cần để mở web quản trị.

API key, thiết bị Android được cấp quyền, ADB và công cụ media quyết định khả năng chạy automation. Thiếu các thành phần này phải được thể hiện trong hướng dẫn/System & Environment; không được làm mất khả năng mở web quản trị.

Không yêu cầu tạo màn hình mới, chạy tác vụ Android, cấu hình IDE/MCP, đăng ký tự chạy khi đăng nhập hoặc kiểm thử truy cập từ thiết bị LAN thứ hai. Không tự commit, push hoặc phát hành repository.

## 4. Input và output

### 4.1. Input

| Input | Bash | PowerShell | Quy tắc |
| --- | --- | --- | --- |
| Thư mục cài | `--install-dir PATH` | `-InstallDir PATH` | Đường dẫn tuyệt đối sau chuẩn hóa; hỗ trợ khoảng trắng |
| Cổng | `--port N` | `-Port N` | Số nguyên 1–65535; mặc định lần đầu 8009 |
| Chỉ truy cập local | `--local-only` | `-LocalOnly` | Bind `127.0.0.1` |
| Không tương tác | `--non-interactive` | `-NonInteractive` | Không chờ nhập liệu |
| Mở trình duyệt | `--open` | `-Open` | Chỉ mở sau khi readiness thành công |
| Trợ giúp | `--help` | `-Help` | Không bắt đầu cài đặt |

Giữ tương thích mặc định đã được mô tả trong `docs/installation.md`:

- Linux: `$HOME/.local/share/artemis`.
- Windows: `%LOCALAPPDATA%\Programs\Artemis`.
- Bind mặc định: `0.0.0.0`; README phải nói rõ khả năng truy cập qua mạng và tùy chọn local-only.
- Khi chạy lại, dùng cấu hình host/port đã lưu nếu không có override hợp lệ.

Thư mục hiện hành không được mặc nhiên coi là thư mục chứa mã nguồn installer. Với `iex`, không được giả định `$PSScriptRoot` tồn tại.

### 4.2. Output

- Source snapshot đầy đủ và nhất quán.
- uv riêng và Python được quản lý; `.venv`.
- Node portable khi Node/npm sẵn có không phù hợp.
- Python dependencies theo `uv.lock`.
- Frontend dependencies theo `package-lock.json`.
- Static export `apps/showcase_next/out`.
- `.env` được tạo từ template nếu chưa tồn tại, cấu hình tại đường dẫn mà ứng dụng thực sự sử dụng.
- `.artemis-install.json` tương thích runtime manager.
- `logs/install.log` và đường dẫn log server.
- Server chạy nền.
- URL thực tế và lệnh `status`, `start`, `stop`, `restart` có quoting đúng.

Không được in hoặc lưu API key vào log cài đặt.

## 5. Môi trường và dependency

### 5.1. Nền tảng bắt buộc

| Nền tảng | Kiến trúc | Shell |
| --- | --- | --- |
| Ubuntu 22.04/24.04 dùng glibc | x86_64 | Bash |
| Windows 11 | x64 | Windows PowerShell 5.1 hoặc PowerShell 7 |

macOS đã xuất hiện trong tài liệu/helper hiện hữu. Planner phải giữ tính tương thích nếu tái sử dụng, nhưng không được tuyên bố macOS đã nghiệm thu qua testcase của ticket này.

### 5.2. Điều kiện bootstrap

Máy mới không cần cài trước Git, Python, uv, Node/npm hoặc Docker.

Các điều kiện tối thiểu phải được công bố:

- Kết nối HTTPS đến GitHub/codeload, nguồn tải uv/Python, Node và package registry.
- Linux có Bash, `curl`, CA certificates, `tar`, `mktemp`, công cụ SHA-256.
- Windows có PowerShell và `Expand-Archive`.
- Tài khoản có quyền ghi thư mục đích.
- Có trình duyệt để nghiệm thu giao diện.

Nếu hệ điều hành tối giản thiếu công cụ tải ban đầu, README phải có lệnh chuẩn bị rõ ràng; không được mô tả là zero-prerequisite tuyệt đối.

### 5.3. Chuỗi dependency ứng dụng

1. Bootstrap uv theo helper hiện hữu.
2. Chuẩn bị Python 3.12.
3. Chạy `uv sync --locked --python 3.12 --no-dev`.
4. Tái sử dụng Node/npm phù hợp hoặc cài portable theo runtime hiện hữu.
5. Chạy `npm ci` và `npm run build` trong `apps/showcase_next`.
6. Xác nhận static export đầy đủ.
7. Khởi động server bằng cơ chế lifecycle hiện hữu.

Không fallback sang cài đặt làm thay đổi lockfile để che lỗi dependency.

Ubuntu tối giản có thể cần `libgl1`, `libglib2.0-0` cho OpenCV. Khi thiếu quyền cài, báo chính xác gói và lệnh khắc phục.

## 6. Business rules và luồng cài đặt

### BR-01 — Bootstrap độc lập

Hai lệnh pipeline phải hoạt động từ thư mục bất kỳ. Không yêu cầu người dùng tự clone repository hoặc chép helper trước.

### BR-02 — Kiểm tra trước khi thay đổi

Kiểm tra tham số, OS/architecture, công cụ bootstrap, quyền ghi và trạng thái thư mục đích. Môi trường không hỗ trợ phải dừng với thông báo cụ thể.

### BR-03 — Tải source an toàn và nhất quán

- Dùng HTTPS, không tắt kiểm tra chứng chỉ.
- Tải vào staging riêng của lần chạy.
- Chỉ chấp nhận archive có cấu trúc và các file bắt buộc.
- Không cho phép đường dẫn giải nén thoát khỏi staging.
- Không trộn helper và source từ các revision không tương thích.
- Kiểm tra checksum uv/Node theo nguồn phát hành.
- Không coi file tải dở hoặc HTML báo lỗi là archive hợp lệ.

### BR-04 — Quyền cài đặt

Ưu tiên cài trong phạm vi tài khoản người dùng.

Không tự yêu cầu quyền quản trị cho toàn bộ installer. Khi cần thư viện hệ thống, dùng quyền đã có hoặc hướng dẫn người dùng cấp quyền và chạy lại.

Không đọc mật khẩu hoặc câu trả lời từ stdin chứa mã script. Chế độ không tương tác phải dừng rõ ràng khi cần quyết định.

Không tự đổi firewall, execution policy toàn máy, cấu hình IDE hoặc shell profile.

### BR-05 — Bảo toàn dữ liệu

- Chỉ tạo `.env` khi chưa có.
- Không ghi đè API key hoặc cấu hình hiện hữu.
- Cấu hình sai cú pháp: báo đường dẫn và dừng, không reset.
- Từ chối thư mục không rỗng không nhận diện được là bản cài hợp lệ.
- Không xóa source checkout, traces, logs hoặc dữ liệu người dùng.

### BR-06 — Chạy lại

- Nhận diện bản cài bằng metadata hợp lệ.
- Tái sử dụng dependency/build khi fingerprint và artifact còn hợp lệ.
- Tái sử dụng server đúng bản cài nếu đang chạy tốt.
- Không tự nâng cấp source hoặc khởi động lại server đang hoạt động.
- Nếu cần sửa dependency/build của server đang chạy, yêu cầu dừng rõ ràng trước.
- Có cơ chế ngăn hai installer sửa cùng thư mục đồng thời.
- Lần chạy bị gián đoạn phải có hướng dẫn phục hồi, không báo hoàn tất giả.

### BR-07 — Cổng và tiến trình

- Không kill tiến trình chỉ vì đang chiếm cổng.
- Phải nhận diện đúng instance ARTEMIS trước khi quản lý lifecycle.
- Cổng chỉ định bị chiếm: báo lỗi, không âm thầm chọn cổng khác.
- Nếu hỗ trợ hỏi cổng thay thế ở chế độ tương tác, đọc từ terminal riêng.
- Server chạy nền và tiếp tục hoạt động sau khi terminal cài đặt đóng.

### BR-08 — Điều kiện thành công

Phải đồng thời xác nhận:

1. Daemon thuộc đúng bản cài.
2. `/` trả nội dung Home của static export.
3. `/settings/` trả nội dung Settings của static export.
4. Asset được tham chiếu trả đúng nội dung, không phải HTML fallback.
5. URL thông báo sử dụng đúng cổng đang chạy.

Chỉ TCP mở hoặc HTTP 200 là chưa đủ. Không chấp nhận trang “frontend chưa build” làm kết quả thành công.

### BR-09 — Giới hạn thời gian và lỗi

Tận dụng hợp đồng hiện hữu:

- Tải xuống có số lần thử hữu hạn, tối đa ba lần.
- Timeout tải mỗi request tối đa 10 phút.
- Dependency command tối đa 30 phút.
- Build tối đa 20 phút.
- Readiness tối đa 120 giây, polling có deadline.

Thông báo lỗi phải có giai đoạn thất bại, nguyên nhân có thể hành động, mã lỗi và đường dẫn log.

| Mã | Nhóm lỗi |
| --- | --- |
| 2 | Tham số hoặc môi trường không hỗ trợ |
| 3 | Quyền, thư mục đích, metadata hoặc lock |
| 4 | Download, archive hoặc checksum |
| 5 | Dependency |
| 6 | Cấu hình |
| 7 | Build hoặc frontend artifact |
| 8 | Cổng, daemon hoặc readiness |
| 130 | Hủy khi bắt được tín hiệu |

PowerShell phải truyền lỗi tới caller; không để lỗi native command bị bỏ qua rồi in thành công.

## 7. Yêu cầu cập nhật README

README phải có:

1. Hai lệnh Internet đúng repository và branch.
2. Nền tảng hỗ trợ và điều kiện bootstrap tối thiểu.
3. Thư mục cài mặc định, cách chọn thư mục mới và cổng.
4. URL mặc định, bind address và tùy chọn local-only.
5. Quyền có thể cần khi cài thư viện hệ thống.
6. Các bước installer thực hiện.
7. Cách chạy lại, xem log và quản lý server.
8. Cách cấu hình model và kết nối Android sau khi web mở.
9. Phân biệt cài web thành công với sẵn sàng chạy automation.
10. Trạng thái kiểm chứng thực tế.

Ví dụ Bash nên bổ sung `set -o pipefail` để lỗi tải ở đầu pipeline không bị che khuất.

Không xóa cảnh báo phát hành chưa hoàn tất chỉ dựa trên việc đã tạo file local. Không tuyên bố các URL public hoạt động nếu chưa có bằng chứng.

## 8. Acceptance criteria

| ID | Tiêu chí nghiệm thu |
| --- | --- |
| AC-01 | Có `install.sh`, `install.ps1` ở gốc và chạy được theo hai cú pháp pipeline |
| AC-02 | Máy mới trong matrix không cần cài trước Git, Python, uv hoặc Node/npm |
| AC-03 | Snapshot chứa đủ backend, frontend, workspace package, template và lockfile |
| AC-04 | Dependency và frontend build hoàn tất; lỗi không bị bỏ qua |
| AC-05 | Cấu hình thiếu được tạo, cấu hình có sẵn được giữ nguyên |
| AC-06 | Server chạy nền, đúng instance, đúng cổng; Home, Settings và asset sẵn sàng |
| AC-07 | Có URL và lệnh quản lý sử dụng được, kể cả đường dẫn có khoảng trắng |
| AC-08 | Chạy lại và xử lý thư mục/cổng xung đột tuân thủ business rules |
| AC-09 | README phản ánh đúng hành vi và giới hạn thực tế |
| AC-10 | Testcase E2E duy nhất có bằng chứng thực thi; không dùng kết quả chưa chạy làm PASS |

Các edge case là yêu cầu triển khai/review, không tạo thêm testcase trong phạm vi bàn giao này.

## 9. Testcase E2E duy nhất

### TC-INSTALL-001 — Cài qua Internet vào thư mục mới và mở web quản trị

**Loại:** E2E nghiệm thu thủ công.

**Trạng thái hiện tại:** `NOT RUN`.

Một testcase dùng hai bộ dữ liệu môi trường Linux/Windows. Báo cáo kết quả từng lượt chạy trong cùng ID; một nền tảng PASS không chứng minh nền tảng còn lại PASS.

### Điều kiện tiên quyết

- Máy/VM sạch thuộc matrix; không có bản ARTEMIS đang chạy.
- Chưa cài Git, Python, uv, Node/npm; ghi nhận trạng thái ban đầu.
- Có công cụ bootstrap và Internet như mục 5.
- Hai entry point và source/helper đã được phát hành công khai, nhất quán trên `nextjs`.
- Thư mục đích mới, rỗng hoặc chưa tồn tại, dưới thư mục kiểm thử được phép.
- Cổng 8009 trống.
- Không cần API key hoặc Android để mở web.

Môi trường workspace hiện tại đã có `.venv`, cache và build nên **không đại diện máy mới**.

### Lệnh thực hiện

Để xác minh rõ thư mục đích, dùng biến thể truyền tham số của cùng entry point.

**Linux — tại thư mục kiểm thử mới:**

```bash
set -o pipefail
curl -fsSL https://raw.githubusercontent.com/jokerhung/android-automation-studio/nextjs/install.sh \
  | bash -s -- --install-dir "$PWD/artemis" --port 8009 --local-only --non-interactive
```

**Windows — tại thư mục kiểm thử mới:**

```powershell
& ([scriptblock]::Create((Invoke-RestMethod -Uri 'https://raw.githubusercontent.com/jokerhung/android-automation-studio/nextjs/install.ps1'))) `
  -InstallDir (Join-Path (Get-Location).Path 'artemis') `
  -Port 8009 -LocalOnly -NonInteractive
```

Hai lệnh không tham số ở mục 1 vẫn là hợp đồng bắt buộc. Các lệnh trên dùng cùng script với tùy chọn thư mục để kiểm tra tiêu chí thư mục mới.

### Các bước và kết quả mong đợi

| Bước | Thực hiện | Kết quả mong đợi |
| --- | --- | --- |
| 1 | Ghi OS, kiến trúc, shell, công cụ có sẵn và trạng thái thư mục đích | Có bằng chứng môi trường sạch |
| 2 | Chạy lệnh phù hợp; thu output, thời gian và trạng thái kết thúc | Tải source, chuẩn bị runtime, cấu hình, dependency, build và start hoàn tất |
| 3 | Kiểm tra thư mục cài và log | Có metadata, `.venv`, cấu hình và static export; không cần sửa tay để chạy |
| 4 | Kiểm tra kết quả readiness | Đúng instance ARTEMIS; Home, Settings và asset hợp lệ |
| 5 | Mở `http://localhost:8009/`, sau đó `/settings/?tab=system` | Giao diện hiển thị và tương tác được; không trắng trang, không hiện lỗi thiếu build |
| 6 | Đóng terminal cài đặt, tải lại trang bằng trình duyệt | Web vẫn hoạt động |
| 7 | Ghi báo cáo và bằng chứng | Kết luận theo từng môi trường đã chạy |

Không chờ một khoảng cố định rồi mặc định thành công. Installer phải chờ readiness có deadline; thao tác trình duyệt xác nhận khả năng hiển thị thực tế.

### Bằng chứng cần thu thập

- OS/version/architecture/shell.
- Trạng thái công cụ và thư mục trước cài.
- Lệnh thực thi, thời gian bắt đầu/kết thúc, kết quả lỗi hoặc thành công.
- Log installer và đường dẫn log daemon.
- Phiên bản runtime thực tế.
- Kết quả nhận diện instance và kiểm tra HTTP/static asset.
- Screenshot Home và Settings với URL.
- Kết quả tải lại sau khi đóng terminal.
- Không đính kèm secret, `.env` có khóa hoặc token lifecycle.

### Kết quả thực tế

Chưa chạy. Chưa có log cài đặt, HTTP response hoặc screenshot nghiệm thu.

### Quy tắc kết luận

- **PASS:** Hoàn thành toàn bộ bước với bằng chứng.
- **FAIL:** Có bước thực thi không đạt kết quả mong đợi.
- **BLOCKED:** Không thể bắt đầu/hoàn thành vì điều kiện ngoài triển khai, chẳng hạn chưa phát hành public.
- **NOT RUN:** Chưa thực thi.

## 10. Bàn giao planner

1. Tích hợp hai entry point với helper/runtime hiện hữu; xác định chính xác schema metadata và trình tự gọi.
2. Rà soát bootstrap để hoạt động khi không có script path hoặc checkout.
3. Giữ nhất quán source snapshot, helper và lockfile.
4. Thiết kế phục hồi sau cài dở và bảo toàn cấu hình.
5. Tận dụng lifecycle/readiness hiện có; không tạo cơ chế kill theo cổng.
6. Cập nhật tài liệu theo triển khai và bằng chứng thực tế.
7. Không cần chuyển designer vì không tạo màn hình mới.
8. Việc phát hành lên `nextjs` thuộc người có quyền phát hành; bước BA này không thực hiện.
9. Chưa có quyết định bắt buộc cần hỏi thêm để planner lập kế hoạch theo hợp đồng hiện hữu. Nếu triển khai cần thay đổi phạm vi hoặc mặc định đó, phải đưa quyết định cụ thể về Orchestrator.

**Kết luận:** Có đủ ngữ cảnh để lập kế hoạch. Hai entry point còn thiếu; nền tảng hỗ trợ cài đặt đã tồn tại một phần. Chưa có căn cứ đánh dấu ticket hoặc testcase PASS.