# Android Automation Studio

**Tự động hóa Android bằng AI với giao diện web chạy trên máy của bạn.**

[English](README.md) · **Tiếng Việt**

## Giới thiệu

Android Automation Studio là bản tùy chỉnh được phát triển độc lập, **clone từ [dự án ARTEMIS của Google](https://github.com/google/artemis)**. Mã nguồn và kiến trúc ARTEMIS ban đầu được ghi nhận cho Google cùng các tác giả đóng góp. Repository này không phải bản phát hành chính thức và không tuyên bố được Google bảo trợ.

Bạn mô tả tác vụ bằng ngôn ngữ tự nhiên, chạy trên điện thoại Android hoặc emulator đã được cấp quyền, rồi theo dõi quá trình thực hiện trong trình duyệt. Backend Python/FastAPI xử lý tự động hóa; frontend **Next.js/TypeScript và shadcn/ui** cung cấp giao diện. Bản Angular đã được loại bỏ.

- **Repository bản tùy chỉnh:** [jokerhung/android-automation-studio](https://github.com/jokerhung/android-automation-studio).
- **Dự án gốc:** [google/artemis](https://github.com/google/artemis).
- **Giấy phép:** [Apache 2.0](LICENSE), giữ các thông báo bản quyền upstream. Mã nguồn kế thừa còn có đóng góp từ [Minitap, Inc.](https://github.com/minitap-ai/mobile-use); thành phần bên thứ ba giữ giấy phép riêng.

Chỉ sử dụng trên thiết bị và tài khoản bạn có quyền điều khiển. Task có thể thay đổi dữ liệu ứng dụng; nội dung yêu cầu và quan sát thiết bị có thể được gửi đến nhà cung cấp AI đã cấu hình. Hãy kiểm tra hướng dẫn trước khi chạy.

## Cách build và run

### Yêu cầu

- Git.
- Python **3.12+**, quản lý bằng [uv](https://docs.astral.sh/uv/).
- Node.js **20.9+** và npm để build frontend; CI của repository dùng Node **22.22.3**.
- Điện thoại Android đã bật **USB debugging và cấp quyền kết nối**, hoặc emulator đang chạy.
- ADB để kết nối thiết bị; scrcpy/FFmpeg cho các chức năng ghi hình.
- Thông tin xác thực của nhà cung cấp AI muốn sử dụng.
- Kết nối mạng khi cài dependency lần đầu và khi gọi AI trên cloud.

Script khởi động tìm hoặc thử cài các công cụ còn thiếu, tạo `.env` nếu chưa có, đồng bộ Python dependencies và build frontend khi cần. Việc cài đặt có thể cần cấp quyền hoặc không thành công trên môi trường chưa hỗ trợ. Đọc kỹ các lời nhắc, kể cả bước tích hợp IDE/MCP không bắt buộc.

### Windows — PowerShell

**Chạy nhanh:**

```powershell
git clone https://github.com/jokerhung/android-automation-studio.git
cd android-automation-studio
.\start.bat
```

**Build và run thủ công**, sau khi đã cài công cụ cần thiết:

```powershell
if (-not (Test-Path .env)) { Copy-Item .env.example .env }
uv sync --locked
npm.cmd ci --prefix apps/showcase_next
npm.cmd run build --prefix apps/showcase_next
uv run python -m artemis ui --port 8009 --open
```

Đổi port hoặc không tự mở trình duyệt:

```powershell
.\start.bat -Port 8010 -NoOpen
```

### macOS

Cài các công cụ cần thiết, kết nối thiết bị đã được cấp quyền, rồi chạy:

```bash
git clone https://github.com/jokerhung/android-automation-studio.git
cd android-automation-studio
bash start.sh
```

Build và run thủ công:

```bash
[ -f .env ] || cp .env.example .env
uv sync --locked
npm ci --prefix apps/showcase_next
npm run build --prefix apps/showcase_next
uv run python -m artemis ui --port 8009 --open
```

Script có thể dùng Homebrew nếu có sẵn. Khởi động cùng Windows, Windows system tray và kho mật khẩu email Windows DPAPI không áp dụng cho macOS.

### Linux

Cài các công cụ cần thiết, bảo đảm tài khoản hệ điều hành có quyền truy cập thiết bị USB Android, rồi chạy:

```bash
git clone https://github.com/jokerhung/android-automation-studio.git
cd android-automation-studio
bash start.sh
```

Build và run thủ công:

```bash
[ -f .env ] || cp .env.example .env
uv sync --locked
npm ci --prefix apps/showcase_next
npm run build --prefix apps/showcase_next
uv run python -m artemis ui --port 8009 --open
```

Script có thể dùng trình quản lý gói hoặc phương án cài trong thư mục người dùng nếu được hỗ trợ. Quyền USB/udev có thể cần cấu hình thủ công. Với máy không có giao diện desktop hoặc khi muốn đổi port:

```bash
bash start.sh --port 8010 --no-open
```

### Mở ứng dụng và cấu hình lần đầu

Script khởi động mặc định tại **[http://localhost:8009/](http://localhost:8009/)**. Các lệnh CLI quản lý dịch vụ có thể có port mặc định khác; hãy ghi rõ `--port 8009`.

1. Vào **Cài đặt → Mô hình**, nhập provider, model mặc định/dự phòng, API key và custom URL nếu cần. Xem thông báo xác nhận trước khi lưu và restart.
2. Vào **Cài đặt → Android** để kiểm tra kết nối thiết bị.
3. Kiểm tra điều kiện chạy trong **Hệ thống & Môi trường**.
4. Về **Trang chủ**, nhập yêu cầu và chọn **Flash** hoặc **Pro**.

Không ghi đè `.env` hiện có khi nâng cấp. Không đưa khóa API hay mật khẩu thật vào Git, ảnh chụp hoặc issue công khai.

Frontend production là **static export** tại `apps/showcase_next/out`, được FastAPI phục vụ cùng origin với API. Không cần chạy riêng Next.js/Node server. Sau khi sửa frontend, build lại rồi tải lại trình duyệt bằng **Ctrl + F5** hoặc tải lại bỏ cache tương ứng trên macOS.

### Build package và chạy kiểm tra

Tại thư mục gốc, sau khi đã build frontend:

```bash
uv build --package artemis-client --wheel
uv build --package artemis --wheel --sdist
```

Kết quả nằm trong `dist/`. Package ARTEMIS chứa frontend đã build; đây là gói Python, không phải bộ cài desktop native.

```bash
npm run lint --prefix apps/showcase_next
npm run typecheck --prefix apps/showcase_next
npm test --prefix apps/showcase_next
npm run budget:check --prefix apps/showcase_next
```

Xem [ghi chú chuyển hẳn sang Next.js](docs/nextjs-only-cutover.md) để biết thêm về đóng gói. Hướng dẫn trên mô tả quy trình cho từng nền tảng, không khẳng định mọi tổ hợp hệ điều hành/thiết bị đã được kiểm thử.

## Những tính năng cơ bản và màn hình minh họa

Các ảnh dưới đây được chụp từ ứng dụng đang chạy thật tại **http://localhost:8009/** ngày **16/09/2026**, với ngôn ngữ tiếng Anh và theme tối. Các vùng màu xám được che để bảo vệ dữ liệu tác vụ, tài khoản và thiết bị; không phải trạng thái đang tải. Không chạy task hay thay đổi cài đặt backend để tạo ảnh.

### Trang chủ — khởi chạy tác vụ

Nhập mục tiêu bằng ngôn ngữ tự nhiên hoặc chọn tác vụ gợi ý.

- **Flash:** vòng lặp phản ứng nhanh cho thao tác ứng dụng trực tiếp.
- **Pro:** lập kế hoạch và xác minh cho luồng phức tạp; có cấu hình kết quả mong đợi và mức kiểm tra.
- Kiểm tra điều kiện tiên quyết trước khi cho phép chạy.

![Trang chủ với ô nhập tác vụ và các gợi ý](docs/assets/screenshots/home.png)

### Workspace — theo dõi và phát lại

Bố cục ba cột giữ nhật ký, màn hình thiết bị và danh sách task trên cùng một trang.

- **Bên trái:** thẻ thao tác dễ đọc, hoạt động/kết quả, ghi chú, kế hoạch và mức sử dụng. Khi task đang chạy, Logs tự cuộn theo nội dung mới; header và tabs đứng yên.
- **Ở giữa:** live view, ảnh chụp từng bước hoặc video phát lại, có thanh tua thời gian và tốc độ phát.
- **Bên phải:** hàng đợi đang hoạt động và lịch sử.
- Dừng/tiếp tục task khi trạng thái phiên cho phép.

Ảnh dưới là một phiên đã hoàn tất; nội dung cá nhân và màn hình bản ghi đã được che.

![Workspace ba cột, dữ liệu riêng tư đã được che](docs/assets/screenshots/workspace.png)

### Lịch tác vụ — tự động hóa định kỳ

Tạo lịch **theo khoảng phút**, **hằng ngày**, hoặc **hằng tuần** với các ngày được chọn. Cấu hình giờ/phút/giây và múi giờ.

- Xem trước năm lần chạy tiếp theo trước khi lưu.
- Tạm dừng/tiếp tục, chạy ngay, xem lịch sử hoặc xóa bằng các nút icon gọn.
- Mô tả dài cuộn trong vùng có chiều cao cố định.
- Khi SMTP đã cấu hình và nền tảng hỗ trợ, gửi summary sau task cùng tệp nhật ký thực thi dạng văn bản.

Máy tính và backend ARTEMIS phải đang hoạt động; thiết bị đích phải khả dụng. Scheduler không tự đánh thức hoặc bật nguồn máy tính.

![Danh sách lịch tác vụ, tên và thông tin riêng tư đã được che](docs/assets/screenshots/task-schedule.png)

<details>
<summary>Màn hình tạo lịch mới</summary>

Biểu mẫu được mở để chụp ảnh, không lưu lịch hoặc chạy task.

![Biểu mẫu tạo lịch tác vụ](docs/assets/screenshots/new-schedule.png)

</details>

### Cài đặt — giao diện, mô hình và thiết bị

- **Chung:** tiếng Anh/tiếng Việt, theme sáng/tối, khởi động cùng Windows khi được hỗ trợ.
- **Mô hình:** provider, model mặc định/dự phòng, thông tin xác thực và custom URL; xác nhận trước khi lưu/restart.
- **Email:** SMTP, kiểm tra kết nối và gửi email thử khi người dùng yêu cầu.
- **Android:** ADB cục bộ/từ xa, chọn thiết bị và quản lý emulator đã cài.
- **Hệ thống & Môi trường:** kiểm tra dependency và trạng thái sẵn sàng.

![Cài đặt ngôn ngữ, theme và khởi động cùng Windows](docs/assets/screenshots/settings.png)

### Khác biệt theo hệ điều hành

| Tính năng | Windows | macOS / Linux |
| --- | --- | --- |
| Next.js Web UI và backend Python | Có | Có; cần cấu hình công cụ/thiết bị phù hợp |
| Lịch tác vụ | Backend phải đang chạy | Backend phải đang chạy |
| Start with Windows và Windows system tray | Có tích hợp Windows | Không áp dụng |
| Lưu mật khẩu SMTP | Windows DPAPI | Secret-store hiện chưa triển khai |

Không mặc định email hoạt động trên macOS/Linux chỉ vì giao diện có tab Email.

### Tích hợp IDE

MCP server kế thừa từ ARTEMIS cung cấp khả năng tự động hóa cho trợ lý AI tương thích. Script khởi động có bước cài tích hợp không bắt buộc; chỉ bật nếu bạn muốn thay đổi cấu hình IDE. Không cần tích hợp này để sử dụng Web UI.

Tài liệu kỹ thuật nằm trong [docs](docs/). Báo lỗi của bản tùy chỉnh tại [Issues của repository](https://github.com/jokerhung/android-automation-studio/issues); nhớ loại bỏ thông tin bí mật khỏi log và ảnh chụp.
