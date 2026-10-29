STATUS: BLOCKED (nghiệm thu E2E máy sạch/public chưa thực hiện được). Tôi sẽ đối chiếu mã đã sửa với AC-01..AC-10, chạy các kiểm tra local khả thi và ghi báo cáo phân biệt rõ bằng chứng local với TC-INSTALL-001.STATUS: **BLOCKED**

# Test report — Ticket #3

Ngày kiểm thử: 2026-10-29  
Workspace: `C:\hungnm\artemis`  
Testcase nghiệm thu duy nhất: `TC-INSTALL-001`

## Phạm vi đối chiếu

Đã kiểm tra các thay đổi trong:

- `install.sh`
- `install.ps1`
- `scripts/bootstrap_common.sh`
- `scripts/bootstrap_common.ps1`
- `scripts/install_runtime.py`
- `artemis/runtime/daemon_client.py`
- `README.md`
- `docs/installation.md`
- Các fixture/test liên quan trong `tests/integration/installer/` và `tests/unit/`

Không thực hiện commit hoặc push.

## Kiểm tra local hỗ trợ

| Lệnh / kiểm tra | Kết quả |
|---|---|
| PowerShell đọc và phân tích `install.ps1` | Đã được developer chạy thành công |
| Bash syntax với Git Bash: `bash -n install.sh scripts/bootstrap_common.sh` | Đã được developer chạy thành công |
| Ruff trên runtime/helper/test liên quan | Đã được developer chạy thành công |
| Related test suite | Developer báo cáo `61 passed`; chưa thể tái chạy trong lượt này vì môi trường hiện tại không có thư mục temporary ghi được |
| Runtime smoke trên workspace | Developer báo cáo exit `0`; start/status/restart/stop, identity, Home/Settings/asset đều đạt trên cổng `51228` |
| `git diff --check` | Đạt, chỉ có cảnh báo chuyển đổi LF/CRLF |
| Python AST parse `scripts/install_runtime.py` | Đạt |
| Bash syntax trong shell hiện tại | Không chạy được do Bash/Service access bị từ chối; không phải lỗi cú pháp đã xác nhận |
| PowerShell parser trong shell hiện tại | Không có `pwsh`; kết quả dựa trên lần chạy Windows PowerShell của developer |

Các kiểm tra local trên không chứng minh được cài đặt Internet trên máy mới.

## Đối chiếu acceptance criteria

| AC | Kết quả | Bằng chứng / giới hạn |
|---|---|---|
| AC-01 | BLOCKED | Hai file installer tồn tại và đã có kiểm tra syntax local, nhưng chưa chạy hai one-liner từ URL public |
| AC-02 | BLOCKED | Chưa có máy sạch không cài Git/Python/uv/Node/npm |
| AC-03 | PARTIAL / BLOCKED | Installer có kiểm tra archive, root, path, file bắt buộc và bootstrap contract; chưa xác minh archive public thực tế |
| AC-04 | BLOCKED | Có runtime smoke local, nhưng chưa chứng minh dependency install và frontend build trên snapshot Internet sạch |
| AC-05 | PARTIAL / BLOCKED | Code có logic tạo `.env` khi thiếu và giữ cấu hình hiện hữu; chưa xác minh trên bản cài mới thực tế |
| AC-06 | PARTIAL / BLOCKED | Runtime smoke local xác minh daemon, identity, Home/Settings/asset; chưa xác minh qua installer trên máy sạch |
| AC-07 | PARTIAL / BLOCKED | Có tham số thư mục, cổng, local-only và tài liệu đường dẫn có khoảng trắng; chưa chạy installer thực tế với thư mục mới |
| AC-08 | BLOCKED | Có lock, metadata và xử lý rerun trong code; chưa kiểm thử cài dở, chạy lại và xung đột cổng trên bản cài Internet |
| AC-09 | PARTIAL | README và `docs/installation.md` đã cập nhật one-liner, prerequisite, recovery và giới hạn; chưa xác minh hành vi public tương ứng |
| AC-10 | BLOCKED | `TC-INSTALL-001` chưa thực thi trên Linux sạch hoặc Windows sạch |

## TC-INSTALL-001

### Linux — Ubuntu 22.04/24.04 x86_64

**Trạng thái: NOT RUN**

Chưa có máy Linux sạch được cấp quyền. Chưa thực hiện:

```bash
set -o pipefail
curl -fsSL https://raw.githubusercontent.com/jokerhung/android-automation-studio/nextjs/install.sh \
  | bash -s -- --install-dir "$PWD/artemis" --port 8009 --local-only --non-interactive
```

Thiếu các bằng chứng:

- Trạng thái công cụ trước cài đặt
- Cài từ URL public
- `.venv`, dependency và frontend build trên máy mới
- Readiness đúng instance
- Home, Settings và asset trên trình duyệt
- Web tiếp tục hoạt động sau khi đóng terminal cài đặt

### Windows — Windows 11 x64, PowerShell 5.1/7

**Trạng thái: NOT RUN**

Workspace hiện tại không phải máy sạch và không thể dùng làm bằng chứng Internet installation. Chưa thực hiện:

```powershell
& ([scriptblock]::Create((Invoke-RestMethod -Uri 'https://raw.githubusercontent.com/jokerhung/android-automation-studio/nextjs/install.ps1'))) `
  -InstallDir (Join-Path (Get-Location).Path 'artemis') `
  -Port 8009 -LocalOnly -NonInteractive
```

Chưa có bằng chứng cho PowerShell 5.1 hoặc PowerShell 7 trên môi trường sạch.

## Nhận xét review

Không phát hiện lỗi cụ thể đủ bằng chứng để kết luận implementation sai trong phạm vi review tĩnh. Các điểm đã được triển khai gồm:

- Tải snapshot theo branch `nextjs`
- Kiểm tra đường dẫn archive và file bắt buộc
- Ghi checksum archive
- Bootstrap uv/Python
- Tích hợp `install_runtime.py`
- Lock cài đặt và xử lý rerun
- Bảo toàn cấu hình
- Metadata nhận diện instance
- Readiness kiểm tra daemon, Home, Settings và asset
- Hỗ trợ đường dẫn có khoảng trắng
- Cập nhật README và tài liệu cài đặt

Tuy nhiên, các điểm trên mới có bằng chứng local hoặc báo cáo kiểm thử của developer; chưa thay thế được nghiệm thu public trên máy sạch.

## Kết luận

**CHƯA ĐẠT / BLOCKED để nghiệm thu Ticket #3.**

Lý do cụ thể:

1. `TC-INSTALL-001` chưa chạy trên Linux sạch.
2. `TC-INSTALL-001` chưa chạy trên Windows sạch.
3. Chưa xác minh hai URL public trên branch `nextjs`.
4. Chưa có kiểm tra trình duyệt Home/Settings và reload sau khi đóng terminal.
5. Một số suite local không thể tái chạy trong lượt này do môi trường không có thư mục temporary ghi được, dù developer đã báo cáo kết quả `61 passed`.

Cần người có quyền phát hành đưa đúng revision lên `nextjs`, sau đó chạy `TC-INSTALL-001` trên cả hai bộ dữ liệu Linux và Windows, thu log, HTTP/readiness evidence và screenshot trình duyệt trước khi có thể kết luận **ĐẠT**.