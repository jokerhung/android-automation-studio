# Plan: Language và Theme trong Settings → General

Ngày: 2026-09-14  
Trạng thái: Đề xuất — chỉ thêm tài liệu, chưa triển khai hai tính năng.

## 1. Yêu cầu và phạm vi

Thêm hai thiết lập trong tab **General**, bên cạnh thiết lập Start with Windows hiện có:

| Thiết lập | Giá trị hiển thị | Giá trị lưu |
| --- | --- | --- |
| Language / Ngôn ngữ | English, Tiếng Việt | `en`, `vi` |
| Theme / Giao diện | Light / Sáng, Dark / Tối | `light`, `dark` |

“Vietnam” trong yêu cầu được hiểu là ngôn ngữ tiếng Việt; dùng nhãn **Tiếng Việt** thay vì tên quốc gia.
Không thêm lựa chọn System/Auto ở MVP. Mặc định **English + Light** để giữ giao diện hiện tại.
Đổi lựa chọn có hiệu lực ngay, giữ sau refresh, không cần Save & restart và không restart service.

Phạm vi là **Web UI ARTEMIS**: Home, Workspace, Task Schedule, Settings, dialog, dropdown,
thông báo frontend, tooltip, nhãn trợ năng và các control live view/replay.
Không đổi ngôn ngữ/theme của Android, Windows, system tray, CLI hoặc email đã gửi.
Không tự dịch task instructions, tên lịch, model/provider ID, URL, key, kết quả LLM hoặc log lịch sử.

## 2. Hiện trạng đã khảo sát

| Source | Nội dung / điểm tích hợp |
| --- | --- |
| `apps/showcase_ui/src/app/pages/home/home.component.{ts,html}` | General là một tab Settings; hiện chứa Start with Windows |
| `apps/showcase_ui/src/app/pages/home/settings-layout.scss` | Bố cục Settings hai cột, màu Light đang viết trực tiếp |
| `apps/showcase_ui/src/app/components/windows-startup/` | Công tắc xanh/xám hiện có; giữ hành vi hệ điều hành, chỉ cập nhật nhãn/style theo UI preference |
| `apps/showcase_ui/src/app/components/email-settings/` | Email notifications hiện đã có toggle cùng kiểu Start with Windows; không cần đổi hành vi gửi mail |
| `apps/showcase_ui/src/app/app.component.ts`, `app.config.ts` | Root/bootstrap, vị trí khởi tạo preference services một lần |
| `apps/showcase_ui/src/index.html`, `src/styles.scss` | Root document, global style, font/icon/CDK overlay; điểm đặt lang/theme và tokens |
| `apps/showcase_ui/src/app/components/nav-switcher/` | Home / Workspace / Task Schedule / Settings cần dịch nhãn và tooltip |
| `apps/showcase_ui/src/app/services/agent.service.ts` | Quản lý session/live state; đổi UI preference không được khởi tạo lại service này |
| Component templates/SCSS, action/tool formatter utils | Nhiều chuỗi tiếng Anh và màu hard-code; cần inventory toàn bộ trước migration |

Chưa xác minh framework i18n runtime hoặc theme token thống nhất đang tồn tại; không giả định
đổi một thuộc tính trên root là tự động dịch/tô màu đầy đủ tất cả màn hình.

## 3. UX trong General

- Thêm card **Appearance & Language** với hai hàng: tên + mô tả bên trái, control bên phải.
- Language dùng native select hoặc radio/segmented control có nhãn rõ **English / Tiếng Việt**.
  Không dùng quốc kỳ để đại diện ngôn ngữ.
- Theme dùng hai lựa chọn **Light / Dark**, có icon mặt trời/mặt trăng và chữ;
  không chỉ dựa vào icon hoặc màu để biểu thị trạng thái.
- Khi đổi ngôn ngữ, label hiện tại đổi ngay, tên lựa chọn ngôn ngữ vẫn là autonym English/Tiếng Việt.
- Dùng `role=status`/aria-live cho thông báo ngắn như “Đã áp dụng giao diện tối”; không hiện modal.
- Nếu không lưu được vào trình duyệt, vẫn áp dụng trong phiên và báo rõ
  “Đã áp dụng, nhưng không lưu được cho lần truy cập sau”. Không báo Saved giả.
- Giữ focus, scroll, tab hiện tại, dữ liệu form chưa lưu, phiên task đang xem và live stream.
- Trên màn hình nhỏ, hai hàng xếp dọc; control không che chữ dài tiếng Việt.

## 4. Lưu preference và khởi tạo

### Quyết định MVP

Preference thuộc **browser profile + origin**, lưu localStorage có version:

```json
{
  "version": 1,
  "language": "en",
  "theme": "light"
}
```

Key đề xuất: `artemis.ui.preferences.v1`. Không chứa key/API credential/task text.
Đây là thiết lập UI, không ghi `.env` hay `artemis.jsonc`, không gọi restart API.
Nếu sau này cần đồng bộ mọi trình duyệt/máy thì thiết kế backend preference riêng;
không âm thầm đổi phạm vi lưu trong MVP.

- Validate schema/enum khi đọc; thiếu field dùng default, value sai/JSON hỏng không crash app.
- Khi ghi, merge với lựa chọn đang lưu để tab cũ không ghi đè theme/ngôn ngữ vừa đổi ở tab khác.
- Nghe `storage` event để đồng bộ các tab cùng origin; tránh vòng lặp ghi lại sự kiện.
- `localhost:8009` và `127.0.0.1:8009` hoặc cổng khác là origin khác: lựa chọn không tự đồng bộ.
- Bắt SecurityError/QuotaExceededError, môi trường private mode và SSR/test không có window.
- Đọc theme trước paint đầu tiên qua bootstrap nhỏ, cùng key/default/validation với runtime,
  sau đó Angular tiếp quản. Có test đối chiếu để hai bản logic không lệch nhau.
- Không fetch preferences từ API để quyết định theme ban đầu; tránh lóe nền Light khi đã chọn Dark.
- Nếu triển khai inline bootstrap, kiểm tra CSP hiện tại; ưu tiên script local tương thích CSP.

## 5. Kiến trúc frontend

Các file đề xuất:

- `services/ui-preferences.service.ts`: đọc/ghi/validate/storage-event, signals language/theme.
- `services/ui-language.service.ts` + pipe/helper dịch: dictionary lookup, params, fallback.
- `core/i18n/en.ts`, `core/i18n/vi.ts`: catalog key thống nhất, build-time key parity check.
- `components/appearance-settings/`: hai control đặt vào General.
- `styles/theme-tokens.scss`: semantic CSS variables cho Light/Dark.
- Bootstrap theme local trong `public/` hoặc entry phù hợp build; nối từ `index.html`/root.

Chốt dùng thư viện runtime translation hay service/pipe nhỏ sau inventory P0.
Ưu tiên cơ chế runtime có reactive locale; không dùng build tiếng Anh/Việt riêng nếu buộc
reload khi đổi ngôn ngữ. Không gọi dịch máy/LLM bên ngoài để dịch label lúc chạy.

## 6. Ngôn ngữ: quy tắc triển khai

- Catalog key theo chức năng: `nav.home`, `settings.general.title`, `schedule.save`,
  `task.status.completed`, `action.click`, `errors.connection_failed`.
- Không ghép câu bằng các đoạn dịch riêng lẻ; dùng template params có kiểm tra tên biến.
- Đồng bộ key và placeholders EN/VI; CI fail khi thiếu bản dịch hoặc sai placeholders.
- Fallback về English cho key còn thiếu, chỉ cảnh báo key ở development; không log dữ liệu task.
- Cập nhật `<html lang="en">` hoặc `vi`; cả hai dùng direction LTR.
- Dịch title, placeholder, aria-label, confirmation, empty/loading/error state và action labels.
- Mã API/status/provider lưu như cũ; map code → label, không đổi protocol hoặc nội dung file cấu hình.
- Backend lỗi có safe error code thì dịch phần message UI; lỗi chưa có code hiển thị nguyên văn an toàn
  kèm nhãn đã dịch. Không hứa dịch đầy đủ mọi lỗi SDK/backend ở MVP, không dùng regex dịch câu lỗi.
- Dùng `Intl.DateTimeFormat`/`Intl.NumberFormat` hoặc pipe nhận locale reactive rõ ràng.
  Chỉ đổi `LOCALE_ID` lúc bootstrap là không đủ cho chuyển runtime.
- Cập nhật định dạng ngày/số hiển thị mà không đổi timezone của schedule, giá trị ISO lưu,
  thứ trong tuần hoặc thời điểm thực thi. HH:mm:ss trong form vẫn là giá trị lịch chính xác tới giây.
- “Work”/“Completed” được dịch; nội dung diễn giải và summary phía dưới giữ ngôn ngữ gốc.
- File report/email body hiện có không thay đổi theo lựa chọn của trình duyệt.

## 7. Theme: semantic tokens và migration

Đặt `data-theme="light|dark"` trên `<html>` và CSS `color-scheme` tương ứng.
Tokens tối thiểu: page/surface/raised backgrounds, text primary/secondary/muted,
border/default/strong, accent/on-accent, input background/text/placeholder,
hover/selected/focus, overlay/backdrop, shadow, success/warning/error/info colors.

- Giữ Light sát bản hiện tại; Dark nền trung tính, card rõ cấp, chữ và border đủ tương phản.
- Thay màu hard-code trong component bằng token; ưu tiên Settings/Home trước rồi Workspace,
  Schedule, shared controls và dialogs. Không dùng `filter: invert()` cho cả trang.
- CDK overlay, modal portal và native input/select phải nhận tokens qua document root,
  không chỉ qua class bên trong Settings.
- Start with Windows/Email toggle vẫn xanh khi ON, xám khi OFF; thumb/focus/disabled rõ trên cả hai theme.
- Textbox AI Model giữ chữ sắc nét, caret/placeholder/read-only/disabled không mất nét hoặc chìm nền.
- Không recolor screenshot, live Android frame, video replay, ảnh icon thương hiệu hoặc canvas overlay.
  Theme chỉ đổi khung/player controls, không thay màu nội dung điện thoại.
- Kiểm tra status badge, code block, tables, textarea, toast, scrollbar, selected row,
  hover/focus/error states. Không chỉ kiểm tra nền trang.
- Mục tiêu tương phản: chữ thường ≥ 4.5:1, chữ lớn và ranh giới/control quan trọng ≥ 3:1;
  đo trong QA, không coi là đã đạt trước kiểm tra.
- Tôn trọng prefers-reduced-motion cho transition; không animate cả trang gây giật/nhấp nháy.

## 8. Giai đoạn triển khai

- [ ] **P0 — Inventory:** liệt kê label/màu hard-code, dialogs/overlay, locale formatting,
  localStorage hiện có, CSP/bootstrap và các trang dùng shared state. Chốt catalog/token conventions.
- [ ] **P1 — Preferences:** service/schema, fallback, migration, storage event và bootstrap tránh flash.
- [ ] **P2 — General UI:** Language/Theme controls, áp dụng tức thời, thông báo lưu lỗi,
  keyboard/aria, không ảnh hưởng công tắc startup và model restart.
- [ ] **P3 — Localization:** catalog EN/VI, translate helper/pipe, migration nav/Settings/Home/
  Schedule/Workspace/player; chuyển date/number formatter sang runtime locale.
- [ ] **P4 — Themes:** tokens Light/Dark, thay hard-code và QA các interaction states/overlay.
- [ ] **P5 — Regression/build:** unit + component + browser visual QA bốn tổ hợp ngôn ngữ/theme,
  kiểm tra live session/form draft không mất, production build và hướng dẫn sử dụng.

## 9. Kiểm thử và nghiệm thu

| Nhóm | Ca bắt buộc |
| --- | --- |
| Preference | Fresh browser, lưu/refresh, storage hỏng/không truy cập được, sai version/enum, thiếu window |
| Nhiều tab | Đổi theme/ngôn ngữ ở tab A → B cập nhật; không stale overwrite hoặc write loop |
| Ngôn ngữ | Key parity/params, dấu tiếng Việt, chuỗi dài, fallback key, aria/title/placeholder |
| Formatting | Ngày/số theo locale; schedule timezone và due times không đổi; giây vẫn giữ |
| Theme | Light/Dark, focus/hover/disabled/error, modal/CDK overlay, select/autofill, contrast |
| Media | Screenshot/video/canvas không bị invert/tint; overlay tọa độ vẫn đọc được |
| Runtime | Không reload route, không gọi restart, không reset form/API key draft hoặc đóng live stream |
| Visual | EN-Light, EN-Dark, VI-Light, VI-Dark trên desktop và viewport nhỏ; không tràn nav/sidebar |

Unit tests dùng storage/clock/HTTP mock; component tests kiểm tra accessible names và rendered styles.
Browser QA kiểm tra đổi setting ở runtime và hard refresh để phát hiện flash sai theme.
Không cần tạo task Android thật để kiểm thử hai preference UI; dùng session/mock data vô hại.
Nếu có mobile E2E mới, khám phá qua ARTEMIS trước khi viết test và chọn serial đúng theo quy tắc dự án.

Nghiệm thu: hai control trong General dùng được; đổi ngay và giữ sau refresh; toàn bộ UI trong phạm vi
có EN/VI và Light/Dark nhất quán; không thay đổi task/schedule/backend/OS; báo lỗi lưu trung thực.
Không để label hoặc tooltip mới chỉ có một ngôn ngữ; không có textbox/modal mất tương phản.

## 10. Build và rollout

- Plan này chỉ là tài liệu, không cần build/restart, không đổi preference của người dùng.
- Khi triển khai: chạy frontend tests, `npm run build` tại `apps/showcase_ui`, xác minh bundle mà
  cổng 8009 phục vụ; Ctrl+F5 sau deploy. Không cần restart backend nếu chỉ sửa UI.
- Bản đóng gói cập nhật catalogs, theme tokens và bootstrap assets theo quy trình resources/wheel.
- Rollout mặc định EN-Light; không tự suy đoán tiếng Việt hoặc theme hệ điều hành khi chưa chọn.
- Rollback frontend không được xóa cấu hình model/email/schedule hoặc localStorage khác.
  Các phiên bản cũ có thể bỏ qua key preference mới an toàn.
