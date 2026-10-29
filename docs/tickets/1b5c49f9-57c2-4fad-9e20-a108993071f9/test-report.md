STATUS: BLOCKED. Tôi sẽ kiểm tra trực tiếp giao diện web tại VM bằng Browser Worker theo đúng TC-INSTALL-001, tập trung Home, Settings/system, Settings/models và asset; không dùng SSH để suy đoán thay cho bằng chứng trình duyệt.STATUS: **BLOCKED**

# Test report — Ticket #3

Ngày kiểm thử: 2026-10-29  
Workspace: `C:\hungnm\artemis`  
Testcase nghiệm thu duy nhất: `TC-INSTALL-001`

## Phạm vi đối chiếu

Đã đối chiếu triển khai và báo cáo hiện có cho:

- `install.sh`
- `install.ps1`
- `scripts/bootstrap_common.sh`
- `scripts/bootstrap_common.ps1`
- `scripts/install_runtime.py`
- `artemis/runtime/daemon_client.py`
- `README.md`
- `docs/installation.md`
- Các fixture/test liên quan trong `tests/integration/installer/` và `tests/unit/`

Không thực hiện commit hoặc push. Không sửa mã nguồn ứng dụng.

## Bằng chứng local đã có

| Kiểm tra | Kết quả |
|---|---|
| Parser PowerShell cho `install.ps1` | Đạt theo báo cáo developer |
| Bash syntax cho installer/helper | Đạt theo báo cáo developer |
| Ruff/lint liên quan | Đạt theo báo cáo developer |
| Test suite liên quan | Developer báo cáo `61 passed` |
| Runtime smoke local | Đạt theo báo cáo developer: start/status/restart/stop, identity, Home/Settings/asset trên cổng `51228` |
| `git diff --check` | Đạt, chỉ có cảnh báo LF/CRLF |
| Python AST parse | Đạt |

Các kết quả trên chỉ kiểm chứng workspace local, không thay thế nghiệm thu cài đặt Internet trên máy mới.

## Kiểm tra Browser Worker

Đã thử khởi tạo trình duyệt để kiểm tra URL VM `http://10.201.21.19:8009`.

Kết quả: **không thể bắt đầu phiên trình duyệt** vì Browser Worker trả lỗi:

```text
Codex auth token is unavailable
```

Do đó chưa thể thu thập bằng chứng trình duyệt cho:

- Home
- `/settings/?tab=system`
- `/settings/?tab=models`
- Static asset
- Reload sau khi đóng terminal cài đặt

Không dùng SSH hoặc thông tin đăng nhập được cung cấp để thay thế bằng chứng UI trình duyệt.

## Đối chiếu acceptance criteria

| AC | Kết quả | Bằng chứng / giới hạn |
|---|---|---|
| AC-01 | BLOCKED | Hai installer tồn tại và đã có kiểm tra syntax local; chưa xác minh hai one-liner từ URL public |
| AC-02 | BLOCKED | Chưa có bằng chứng máy Linux hoặc Windows sạch không cài sẵn Git/Python/uv/Node/npm |
| AC-03 | PARTIAL / BLOCKED | Code có kiểm tra archive, root, path, file bắt buộc và bootstrap contract; chưa xác minh snapshot public |
| AC-04 | BLOCKED | Chưa chứng minh dependency install và frontend build từ Internet trên máy sạch |
| AC-05 | PARTIAL / BLOCKED | Code có logic tạo `.env` khi thiếu và giữ cấu hình hiện hữu; chưa chạy xác nhận trên bản cài mới |
| AC-06 | PARTIAL / BLOCKED | Runtime smoke local đạt; chưa xác minh qua installer public và chưa có screenshot/UI evidence |
| AC-07 | PARTIAL / BLOCKED | Có tham số thư mục, cổng, local-only và hỗ trợ đường dẫn có khoảng trắng; chưa chạy đầy đủ testcase |
| AC-08 | BLOCKED | Có logic lock, metadata và rerun; chưa kiểm thử cài dở, chạy lại và xung đột cổng trên máy sạch |
| AC-09 | PARTIAL | README và `docs/installation.md` đã cập nhật; hành vi public chưa được xác minh |
| AC-10 | BLOCKED | `TC-INSTALL-001` chưa hoàn thành trên Linux sạch và Windows sạch |

## TC-INSTALL-001

### Linux — Ubuntu 22.04/24.04 x86_64

**Trạng thái: BLOCKED / PARTIAL OBSERVATION**

Người tạo ticket báo cáo VM Linux đã mở được:

```text
http://10.201.21.19:8009/settings/?tab=models
```

Tuy nhiên chưa có bằng chứng kiểm thử đủ điều kiện:

- OS, architecture, shell
- Trạng thái Git/Python/uv/Node/npm trước cài
- Thư mục đích mới và rỗng
- Lệnh installer thực tế từ URL public
- Output, exit code và thời gian cài
- Log installer/daemon
- Readiness đúng instance
- Home
- `/settings/?tab=system`
- Static asset
- Reload sau khi đóng terminal cài đặt

Vì Browser Worker không khởi tạo được, báo cáo trên không thể được xác minh độc lập.

### Lỗi “Model settings are local-only”

Người tạo ticket báo cáo trang models hiển thị:

```text
Model settings are local-only
```

Với tùy chọn cài đặt `--local-only`, thông báo này có thể là hành vi được thiết kế để ngăn cấu hình model từ máy remote. Hiện chưa đủ bằng chứng để kết luận đây là lỗi installer hoặc lỗi runtime.

Thông báo này không tự chứng minh web cài đặt thất bại, nhưng cần đối chiếu với yêu cầu sản phẩm và kiểm tra thêm bằng trình duyệt trên đúng instance. Không sửa code dựa trên thông báo này.

### Windows — Windows 11 x64

**Trạng thái: NOT RUN**

Chưa có bằng chứng chạy:

```powershell
& ([scriptblock]::Create((Invoke-RestMethod -Uri 'https://raw.githubusercontent.com/jokerhung/android-automation-studio/nextjs/install.ps1'))) `
  -InstallDir (Join-Path (Get-Location).Path 'artemis') `
  -Port 8009 -LocalOnly -NonInteractive
```

Chưa có máy Windows sạch, output installer, readiness hoặc UI evidence.

## Kết luận

**CHƯA ĐẠT — BLOCKED để nghiệm thu Ticket #3.**

Lý do cụ thể:

1. `TC-INSTALL-001` chưa hoàn thành trên Linux sạch.
2. Bằng chứng Linux hiện chỉ là báo cáo URL đã mở; chưa có log, điều kiện máy sạch, Home, system settings, asset và reload.
3. Browser Worker không chạy được vì thiếu Codex auth token, nên không thể xác minh UI trực tiếp.
4. Windows sạch/public chưa được kiểm thử.
5. Chưa có bằng chứng hai URL public trên branch `nextjs` trỏ đúng revision đã review.

Cần khắc phục quyền truy cập Browser Worker hoặc cung cấp bằng chứng trình duyệt tương đương, sau đó chạy đầy đủ `TC-INSTALL-001` trên Linux sạch và Windows sạch trước khi kết luận **ĐẠT**.