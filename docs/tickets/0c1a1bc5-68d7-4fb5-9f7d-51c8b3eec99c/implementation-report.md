# Ticket #2 — Báo cáo triển khai

## Kết quả

Đã thêm bootstrap qua Internet cho Bash (Ubuntu/macOS) và PowerShell (Windows),
độc lập với thư mục đang mở và không yêu cầu Git/Python/Node có sẵn.

Luồng mới tải snapshot source vào staging, kiểm tra archive, khóa cài đặt,
chuẩn bị uv/Python/Node, khởi tạo cấu hình còn thiếu, build static frontend,
chạy nền, xác minh danh tính ARTEMIS và nội dung HTTP Home/Settings/asset,
rồi hiển thị URL localhost, loopback và IPv4 theo interface.

Chạy lại giữ source/config/data, cổng và đường dẫn dữ liệu đã lưu; không tự
nâng cấp hoặc restart phiên khỏe. Dependency/build được bỏ qua khi fingerprint
và artifact còn hợp lệ. Không sửa môi trường đang phục vụ khi cần repair.

Hướng dẫn đầy đủ: [installation.md](../../installation.md).

## Nguyên nhân và các sửa đổi liên quan

1. Các entry point cũ yêu cầu source checkout, nên chưa bootstrap được từ một
   lệnh tải qua Internet. Bổ sung `install.sh`, `install.ps1` và helper dùng chung.
2. Lifecycle dùng wildcard bind làm địa chỉ xác minh, trong khi kiểm tra danh
   tính chỉ chấp nhận loopback. Giữ bind LAN, chuyển probe sang `127.0.0.1`.
3. Smoke test phát hiện metadata có thể biến mất trước khi socket đóng trong
   graceful shutdown. Adapter giờ tiếp tục quan sát đến khi cổng đóng/deadline;
   không gửi tín hiệu đến tiến trình không được xác minh.
4. Trên Windows, Python redirector có thể mở console phụ. Daemon dùng
   `pythonw.exe` khi có sẵn, với output ghi vào log và chế độ detached.
5. Test security cũ đòi HTML fallback cho đường dẫn traversal. Next static hosting
   trả 404, nên cập nhật test yêu cầu 404 và không trả nội dung workspace.
6. Các comment chứa dấu Unicode trong hai script PowerShell làm hỏng gate ASCII
   hiện có; thay bằng dấu ASCII, không đổi hành vi của rebuild.

## File thêm

- `install.sh`
- `install.ps1`
- `scripts/bootstrap_common.sh`
- `scripts/bootstrap_common.ps1`
- `scripts/install_runtime.py`
- `artemis/runtime/network_urls.py`
- `.github/workflows/installer.yml`
- `docs/installation.md`
- `docs/tickets/0c1a1bc5-68d7-4fb5-9f7d-51c8b3eec99c/implementation-report.md`
- `tests/unit/test_install_runtime.py`
- `tests/unit/runtime/test_network_urls.py`
- `tests/integration/installer/test_bootstrap.py`
- `tests/integration/installer/test_bootstrap_powershell.py`
- `tests/integration/installer/smoke_runtime.py`

## File sửa

- `.gitignore`
- `README.md`
- `README_VI.md`
- `start.sh`
- `scripts/start.ps1`
- `scripts/install_deps.sh`
- `scripts/install_deps.ps1`
- `scripts/rebuild.ps1` — chỉ comment ASCII
- `artemis/runtime/tray_controller.py`
- `artemis/runtime/daemon_client.py`
- `apps/showcase_next/src/features/settings/android-system-panels.tsx`
- `apps/showcase_next/src/lib/i18n/catalogs.ts`
- `tests/unit/test_bootstrap_scripts_encoding.py`
- `tests/unit/runtime/test_daemon_client.py`
- `tests/unit/admin_console/test_security_boundary.py`

`start.bat` tiếp tục chuyển tham số cho `scripts/start.ps1`, không cần sửa.

## Kiểm tra đã chạy

Môi trường thực thi là host Windows hiện có, project Python 3.14.7. Các kiểm thử
bootstrap mô phỏng source tải về và công cụ, không thay thế cài máy sạch.

| Kiểm tra | Kết quả |
| --- | --- |
| Installer/runtime/lifecycle/static hosting/security và bootstrap Bash/PowerShell | 114 passed |
| Settings, locale/theme và tab frontend | 12 passed |
| Ruff lint/format các Python file thay đổi | Đạt |
| Bash syntax các bootstrap/start/dependency script | Đạt |
| PowerShell 5.1 parser và `install.ps1 -Help` | Đạt |
| Frontend ESLint | Đạt |
| Frontend TypeScript | Đạt |
| `npm run build` | Đạt, static export Home và Settings |
| Server thật: detached start/status/restart/stop, identity và HTTP artifact | Đạt |
| Tên binary/checksum uv và Node tại nguồn phát hành | Có đủ cho các kiến trúc mục tiêu |

Smoke server thật dùng cổng trống và dữ liệu riêng trong `.test-tmp`; server test
đã được dừng và chờ thoát. Output của lần đạt lưu tại
`.test-tmp/installer-smoke-output.txt` (artifact tạm, không đưa vào source).

Có cảnh báo deprecation từ Google SDK và cảnh báo React `act(...)` trong bộ test
hiện có; không làm các kiểm tra trên thất bại.

Các lệnh chính để chạy lại trên Windows:

```powershell
.venv/Scripts/python.exe -B -m pytest -q tests/unit/test_install_runtime.py tests/unit/runtime/test_network_urls.py tests/unit/runtime/test_background_runtime.py tests/unit/runtime/test_daemon_client.py tests/unit/runtime/test_tray_controller.py tests/unit/test_bootstrap_scripts_encoding.py tests/integration/installer tests/unit/admin_console/test_static_hosting.py tests/unit/admin_console/test_security_boundary.py tests/unit/runtime/test_server_process_lifecycle.py tests/unit/admin_console/test_server_lifecycle.py --override-ini addopts= -m 'not android' -p no:cacheprovider --basetemp .test-tmp/installer-review
.venv/Scripts/python.exe -B tests/integration/installer/smoke_runtime.py
```

Smoke cần frontend đã build. Chạy các lệnh sau trong `apps/showcase_next`:

```powershell
npm.cmd run lint
npm.cmd run typecheck
npm.cmd test -- --run tests/settings.test.tsx tests/settings-locale-theme.test.tsx tests/settings-tabs.test.ts
npm.cmd run build
```

## Phạm vi chưa xác minh

- Chưa thực hiện toàn bộ ma trận máy sạch Windows 11/Ubuntu 22.04–24.04/macOS
  14–15 và Python 3.12 do installer provision.
- Chưa thực hiện truy cập từ thiết bị LAN thứ hai. Hiển thị IP interface là
  phát hiện địa chỉ, không phải bằng chứng truy cập LAN thành công.
- Chưa kiểm tra lệnh public hoàn chỉnh: các file phải được phát hành cùng nhau
  lên nhánh `nextjs` trước. Phiên này không commit/push/merge/reset.
- Workflow mới cung cấp kiểm tra hợp đồng trên runner các OS; runner có sẵn
  công cụ nên không thay thế các system test máy sạch trong ticket.
- ADB/scrcpy/FFmpeg được phân loại theo tính năng, không phải điều kiện mở web;
  xem Settings System và tài liệu để cài công cụ còn thiếu khi chạy Android.

Không đánh dấu toàn bộ system test của ticket là đạt chỉ từ những kiểm tra trên.
