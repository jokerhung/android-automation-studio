# Next.js-only cutover

Ngày: 2026-09-16

Frontend duy nhất là `apps/showcase_next`, static export `out/`, do FastAPI phục vụ.
Không cần cấu hình `ARTEMIS_FRONTEND`; mặc định là `next`. Các automation cũ vẫn
có thể truyền `next`, nhưng `angular` bị từ chối rõ ràng thay vì âm thầm phục vụ
bundle sai. Không cần Node server trong production.

Đã cập nhật launcher Windows/Linux/macOS, installer, CLI UI/doctor, Makefile,
Dockerfile, CI và Python packaging. Docker copy thêm cấu hình PostCSS của shadcn.
Đã bỏ CI/build target Angular và nguồn/bundle Angular khỏi repository.
Các tham chiếu Angular trong tài liệu migration cũ chỉ còn giá trị lịch sử.
Tên file `angular-parity.css`, `angular-tokens.css`, `angular-copy.ts` và
`angular-suggestions.ts` trong Next là CSS/data độc lập, không import Angular.
Tên diagnostic key `showcase_ui` giữ nguyên để không phá contract CLI/MCP.
Packaging vẫn dọn tên thư mục Angular cũ trong staging để chống artifact tồn dư.

## Bảo toàn dữ liệu

Không thay đổi `.env`, cấu hình model/email, lịch tác vụ, database, traces hoặc
Windows startup. Không tự restart backend hoặc kích hoạt scheduler. Tại lần kiểm
tra cuối, cổng 8009 không có listener; lần khởi động tiếp theo dùng Next mặc định.

Angular có thay đổi chưa commit nên được chuyển ra ngoài repository, có thể phục hồi:

`C:\hungnm\artemis-angular-backup-20260916`

- `source`: cấu hình/build/cache và phần dependency chuyển được ở lần đầu.
- `source-remaining`: source/public/scripts và dependency còn lại; chuyển nguyên
  thư mục bằng rename sau khi PowerShell gặp symlink package manager bị hỏng.
- `bundled-assets`: bundle Angular trước đây ở `artemis/resources/showcase_ui`.

Đã xác minh mọi file Angular được Git theo dõi đều còn trong backup. Để khôi phục
source nếu cần, ghép `source` và `source-remaining` vào thư mục riêng; không ghi đè
Next hoặc dữ liệu runtime. Bản backup không nằm trong Git hay Docker context.

## Kiểm tra

- Next production build, 127 frontend tests.
- 86 Python tests về CLI, hosting, packaging, resource và measurement.
- 8 integration tests cho production artifact.
- Parse PowerShell và `bash -n` cho launcher/installer.
- Build wheel và sdist tại `dist/next-only`; kiểm tra wheel có Next routes,
  không chứa bundle Angular hoặc node_modules.
- Chưa chạy Docker build hoặc khởi động thực tế trên Linux/macOS tại máy Windows này.

Lệnh phát triển: `npm ci --prefix apps/showcase_next`, rồi
`npm run build --prefix apps/showcase_next`. Build package bằng `uv build` sau
khi có frontend export. Khởi động bằng `start.bat` hoặc `bash start.sh`.
