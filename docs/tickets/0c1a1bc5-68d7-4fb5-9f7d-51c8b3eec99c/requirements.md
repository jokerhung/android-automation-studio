Tôi sẽ đọc cấu trúc dự án, các script cài đặt và luồng khởi động để viết tài liệu yêu cầu có căn cứ từ mã nguồn. Tôi chỉ đọc trong workspace, không sửa file và không chạy git.
Mã nguồn hiện có script cài dependency và khởi động từ thư mục dự án, nhưng chưa thấy `install.sh`/`install.ps1` ở gốc để bootstrap qua Internet. Tôi cũng thấy các điểm cần đưa vào tiêu chí nghiệm thu: cổng mặc định giữa các luồng chưa thống nhất, server mặc định bind loopback, và luồng daemon Windows kiểm tra cổng TCP thay vì xác nhận giao diện bằng HTTP.
# Ticket #2 — Cài đặt ARTEMIS qua Internet trên Windows, Linux và macOS

## 1. Mục tiêu

Cung cấp quy trình cài đặt bằng một lệnh trên máy chưa có mã nguồn hoặc bộ công cụ phát triển. Installer tự tải dự án, chuẩn bị dependency, khởi tạo cấu hình, build frontend, khởi động ứng dụng và hiển thị URL truy cập local/LAN.

Người dùng có thể mở giao diện cấu hình ngay cả khi chưa có khóa API hoặc chưa kết nối thiết bị Android.

Tài liệu này đặc tả tính năng mới và các kịch bản nghiệm thu; không coi những khoảng trống hiện tại là lỗi đã tái hiện.

## 2. Căn cứ và giới hạn xác minh

Đã đọc mã nguồn trong `C:\hungnm\artemis`. Không sửa file, không chạy git, không chạy installer hoặc ứng dụng.

Chưa thấy thư mục tài liệu ticket tại đường dẫn được cung cấp. Các kết luận dưới đây dựa trên kiểm tra tĩnh; chưa có bằng chứng cài đặt thực tế trên ba hệ điều hành.

| File/thành phần | Hiện trạng xác minh từ mã nguồn | Ý nghĩa đối với yêu cầu |
|---|---|---|
| `scripts/install_deps.sh`, `scripts/install_deps.ps1` | Có cài dependency, tạo `.env` nếu thiếu, build frontend; xác định thư mục gốc từ vị trí script | Có thể tái sử dụng sau khi tải mã nguồn; chưa thay thế bootstrap từ Internet |
| `start.sh` | Chuẩn bị môi trường, đồng bộ dependency, build và chạy UI; cổng mặc định `8009` | Tận dụng luồng khởi động, truyền cổng nhất quán |
| `start.bat`, `scripts/start.ps1` | Windows có chế độ daemon, dừng server; cổng mặc định `8009` | Tận dụng quản lý tiến trình; nhánh daemon trong script đang kiểm tra TCP |
| `pyproject.toml`, `uv.lock` | Python yêu cầu `>=3.12`; có dependency và workspace package nội bộ | Phải tải đủ cấu trúc dự án và đồng bộ môi trường Python |
| `apps/showcase_next/package.json` | Node.js yêu cầu `>=20.9.0`; build bằng `npm run build` | Installer cần chuẩn bị Node.js/npm để build |
| `apps/showcase_next/next.config.ts` | Frontend dùng static export | Không cần duy trì một Next.js server riêng sau build |
| `apps/admin_console/server.py` | Backend phục vụ ứng dụng; giá trị mặc định của entry point là loopback, cổng `8000` | Installer phải truyền host/cổng rõ ràng để đáp ứng LAN |
| `artemis/interfaces/cli/commands/server_lifecycle.py` | Có restart/status/stop, kiểm tra danh tính ARTEMIS; mặc định loopback, cổng `8000` | Không dùng mặc định của từng entry point một cách ngầm định |
| `artemis/runtime/server_lifecycle.py` | Có xác minh HTTP qua `/api/system/lifecycle-identity` | Có cơ sở phân biệt ARTEMIS với dịch vụ khác trên cùng cổng |
| `apps/showcase_next/src/app/settings/page.tsx`, `apps/admin_console/routers/system.py` | Có màn hình Settings và API cấu hình khóa | Dùng làm điểm tiếp tục cấu hình sau cài đặt |
| `install.sh`, `install.ps1` tại gốc | Chưa thấy trong workspace | Cần bổ sung entry point cài đặt từ xa |

Lưu ý: script Bash cài dependency hiện kiểm tra Node.js tương thích nhưng luồng tự cài Node.js đầy đủ hơn nằm trong `start.sh`. Việc tái sử dụng cần bao phủ cả hai phần, tránh gọi riêng script dependency rồi thiếu công cụ build.

## 3. User stories

### US-01 — Cài mới

Là người dùng mới, tôi muốn chạy một lệnhSelected model is at capacity. Please try a different model.