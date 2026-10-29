Tôi sẽ dùng skill `docs` để trả lại báo cáo Markdown. Developer xác nhận không có thay đổi và chưa phát hành, nên không có phạm vi system test mới để chạy; tôi giữ nguyên bằng chứng release checker gần nhất và kết quả 2 PASS / 1 FAIL / 29 BLOCKED, không lặp unit/integration hoặc UI.# Ticket #2 — System Test Report

- **Tài liệu đích:** `docs/tickets/0c1a1bc5-68d7-4fb5-9f7d-51c8b3eec99c/system-test-report.md`
- **Ngày cập nhật:** 2026-10-28
- **Loại kiểm thử:** System test end-to-end
- **Kết luận:** **CHƯA ĐẠT**
- **Tổng hợp:** 2 PASS, 1 FAIL, 29 BLOCKED
- **Thay đổi vòng này:** Không có
- **Ràng buộc:** Không sửa mã nguồn, không chạy unit/integration test, không commit/push.

## 1. Kết luận

Không có thay đổi sản phẩm hoặc bản phát hành mới để kiểm thử lại.

Bằng chứng system test gần nhất vẫn cho thấy:

- `install.sh`, `install.ps1` và bốn helper mới trả HTTP `404`.
- Hai file lifecycle công khai khác checkout đang nghiệm thu.
- ZIP và tar.gz của nhánh `nextjs` truy cập được.
- Release checker trả exit `4`.
- Lệnh cài PowerShell công khai thất bại với exit `1`.

Tính năng cốt lõi là cài đặt qua Internet chưa thể bắt đầu. Ticket tiếp tục **FAIL**.

## 2. Bằng chứng gần nhất

### Release checker

```powershell
.venv\Scripts\python.exe -B scripts\check_installer_release.py --timeout 10
```

```text
RELEASE_CHECK_EXIT=4
```

| Tài nguyên | Kết quả |
|---|---|
| `install.sh` | HTTP 404 |
| `install.ps1` | HTTP 404 |
| `scripts/bootstrap_common.sh` | HTTP 404 |
| `scripts/bootstrap_common.ps1` | HTTP 404 |
| `scripts/install_runtime.py` | HTTP 404 |
| `artemis/runtime/network_urls.py` | HTTP 404 |
| `artemis/runtime/tray_controller.py` | HTTP 200, khác checkout |
| `artemis/runtime/daemon_client.py` | HTTP 200, khác checkout |
| Manifest, lockfile và cấu hình được chọn | HTTP 200, khớp checkout |
| ZIP archive `nextjs` | HTTP 200 qua HEAD |
| tar.gz archive `nextjs` | HTTP 200 qua HEAD |

### Lệnh cài công khai

```text
Invoke-RestMethod : 404: Not Found
PUBLIC_INSTALL_EXIT=1
```

### UI thật từ source checkout

Managed Browser Worker đã xác minh:

- Home và Settings mở được.
- Các tab Models, Android và System & Environment hiển thị.
- Nội dung onboarding và các link cấu hình hoạt động.

Host có credential và Android kết nối nên chưa thỏa điều kiện “không API key, không Android”.

### CLI cục bộ

- Cổng `0`, `65536` và `abc` bị từ chối với exit `2`.
- Windows ngoài ma trận bị từ chối với exit `2`.
- Không tạo bản cài hoặc lock khi môi trường bị từ chối.

## 3. Kết quả từng test case

| ID | Kết quả | Bằng chứng hoặc blocker |
|---|---|---|
| ST-E2E-001 | BLOCKED | Không có Ubuntu sạch; installer/helper trả 404. |
| ST-E2E-002 | BLOCKED | Không có macOS sạch; installer/helper trả 404. |
| ST-E2E-003 | BLOCKED | Không có Windows 11; `install.ps1` trả 404. |
| ST-E2E-004 | BLOCKED | Không tạo được bản cài Internet để kiểm tra đường dẫn Unicode. |
| ST-E2E-005 | BLOCKED | UI mở được nhưng host có credential và Android. |
| ST-E2E-006 | BLOCKED | Không có installed instance và thiết bị LAN thứ hai. |
| ST-E2E-007 | BLOCKED | Chưa thể kiểm tra local-only từ thiết bị thứ hai. |
| ST-E2E-008 | BLOCKED | Chưa có môi trường không IPv4 LAN. |
| ST-E2E-009 | BLOCKED | Chưa có môi trường LAN/VPN/ảo kiểm soát. |
| ST-E2E-010 | BLOCKED | Không có bản cài Internet để kiểm tra rerun. |
| ST-E2E-011 | BLOCKED | Không thể tạo lần cài Internet bị gián đoạn. |
| ST-E2E-012 | BLOCKED | Chưa có lệnh quản lý từ installed instance. |
| ST-E2E-013 | BLOCKED | Chưa thể kiểm tra cổng bị chiếm ở terminal tương tác. |
| ST-E2E-014 | BLOCKED | Chưa thể kiểm tra cổng bị chiếm non-interactive. |
| ST-E2E-015 | BLOCKED | Chưa thể kiểm tra cổng tùy chỉnh. |
| ST-E2E-016 | PASS | Cổng sai bị từ chối với exit `2`. |
| ST-E2E-017 | BLOCKED | Lỗi xảy ra trước logic retry/archive validation của installer. |
| ST-E2E-018 | BLOCKED | Chưa có môi trường kiểm soát quyền ghi/UAC. |
| ST-E2E-019 | BLOCKED | Chưa chạy được installer tới kiểm tra thư mục đích. |
| ST-E2E-020 | BLOCKED | Chưa thể chạy đồng thời hai bootstrap công khai. |
| ST-E2E-021 | BLOCKED | Chưa có máy sạch để tạo lỗi dependency thật. |
| ST-E2E-022 | BLOCKED | Chưa có installed instance để kiểm tra cấu hình lỗi. |
| ST-E2E-023 | BLOCKED | Chưa thể tạo lỗi build trong bản cài Internet. |
| ST-E2E-024 | BLOCKED | Chưa thể kiểm tra dịch vụ giả chiếm cổng. |
| ST-E2E-025 | BLOCKED | Chưa thể tạo readiness timeout. |
| ST-E2E-026 | BLOCKED | Chưa thể kiểm tra fallback “Not Built”. |
| ST-E2E-027 | BLOCKED | Chưa thể chạy installer tới bước gửi Ctrl+C. |
| ST-E2E-028 | BLOCKED | Chưa có log/metadata installed instance để kiểm tra bí mật. |
| ST-E2E-029 | BLOCKED | Chưa thể chạy installer với `-Open`. |
| ST-E2E-030 | BLOCKED | Chưa thể chạy bootstrap hoàn chỉnh qua pipe/non-TTY. |
| ST-E2E-031 | PASS | Windows ngoài ma trận bị từ chối với exit `2`. |
| ST-E2E-032 | FAIL | Lệnh cài công khai trong tài liệu chưa thực thi được. |

## 4. Acceptance criteria

| AC | Kết quả | Nhận xét |
|---|---|---|
| AC-01 | FAIL | Hai installer công khai trả 404. |
| AC-02 | BLOCKED | Chưa chạy ma trận máy sạch. |
| AC-03 | BLOCKED | Chưa chạy trên máy thiếu runtime. |
| AC-04 | BLOCKED | Chưa kiểm tra rerun trên bản cài thật. |
| AC-05 | PARTIAL | UI source checkout hoạt động; chưa chứng minh readiness installer. |
| AC-06 | BLOCKED | Chưa có URL từ installer thật. |
| AC-07 | BLOCKED | Chưa kiểm tra thiết bị LAN thứ hai. |
| AC-08 | BLOCKED | Chưa kiểm tra local-only hoặc không có LAN. |
| AC-09 | PARTIAL | Tham số sai trả mã đúng; các lỗi khác chưa chạy. |
| AC-10 | BLOCKED | Chưa kiểm tra quản lý installed instance. |
| AC-11 | BLOCKED | Chưa có môi trường không credential/Android. |
| AC-12 | BLOCKED | Chưa kiểm tra log và metadata bản cài. |
| AC-13 | BLOCKED | Chưa kiểm tra rerun và daemon. |
| AC-14 | BLOCKED | Chưa chạy bootstrap hoàn chỉnh non-TTY. |
| AC-15 | PARTIAL | Lỗi tham số/môi trường có thông báo rõ. |
| AC-16 | BLOCKED | Chưa kiểm tra thư mục lạ không rỗng. |
| AC-17 | BLOCKED | Chưa chạy hai installer đồng thời. |
| AC-18 | BLOCKED | Chưa kiểm tra API local-only từ LAN. |
| AC-19 | PARTIAL | Tài liệu phản ánh blocker nhưng quy trình cài chưa dùng được. |
| AC-20 | BLOCKED | Chưa có output installer hoàn chỉnh. |

## 5. Điều kiện kiểm thử lại

Chỉ chuyển lại Tester sau khi:

1. Phát hành toàn bộ thay đổi Ticket #2 cùng revision lên `nextjs`.
2. Release checker trả exit `0`.
3. Hai lệnh cài công khai tải được installer.
4. Có môi trường sạch cho Windows 11, Ubuntu và macOS.
5. Có thiết bị thứ hai cùng mạng để kiểm tra LAN.
6. Có môi trường không credential và không Android cho ST-E2E-005.

## 6. Quyết định QA

**FAIL — CHƯA ĐẠT.**

Không có thay đổi mới để làm thay đổi kết quả. Blocker phát hành vẫn tồn tại và phần lớn system test chưa thể thực hiện.