# Plan: Chuyển frontend ARTEMIS từ Angular sang Next.js/TypeScript

Ngày: 2026-09-15  
Trạng thái: Đang triển khai — P0/P1 đã bắt đầu; Angular vẫn là mặc định cho đến khi đạt parity.  
Phạm vi: Frontend Web UI và các điểm build/static hosting liên quan. Backend nghiệp vụ vẫn dùng Python/FastAPI.

## 1. Mục tiêu và nguyên tắc

- Chuyển Angular sang Next.js App Router + React + TypeScript strict. Frontend hiện đã dùng TypeScript; đây không phải migration JavaScript sang TypeScript.
- Giữ giao diện, URL và hành vi đã có; không đồng thời thiết kế lại sản phẩm.
- Tiếp tục truy cập qua `http://localhost:8009/`, hỗ trợ port tùy chọn và triển khai Windows/Linux/macOS.
- Không thêm Node server bắt buộc khi vận hành; Node chỉ cần cho phát triển/build frontend.
- Không thay đổi engine Flash/Pro, scheduler, SMTP, schema database, cấu hình model hoặc cơ chế điều khiển Android để phục vụ migration.
- Không đưa API key, SMTP password hoặc lifecycle token vào bundle, `NEXT_PUBLIC_*`, log frontend hoặc localStorage.
- Giữ Angular chạy được trong giai đoạn chuyển đổi và có phương án quay lại bản cũ.

Ngoài phạm vi: build desktop installer, tự cập nhật ứng dụng, thay backend bằng Next API routes, thêm xác thực người dùng mới, thay secret store hoặc sửa các hạn chế nền tảng của SMTP/tray. Các lỗi backend sẵn có phải được ghi riêng, không coi là đã giải quyết nhờ migration UI.

## 2. Hiện trạng đã khảo sát

| Thành phần hiện tại | Tác động khi migration |
| --- | --- |
| `apps/showcase_ui/package.json` | Angular 22, TypeScript, RxJS, Zone.js, Angular CDK; test Jasmine/Karma |
| `src/app/app.routes.ts` trong frontend | Các route `/`, `/workspace`, `/task-schedule`, `/settings`, `/check`; route lạ chuyển về Home |
| `pages/home/` | Home và Settings đang dùng chung component với `homeView`; cần tách thành hai feature |
| `services/agent.service.ts` | Session/task state, SSE `/api/stream`, polling, cache, replay và video; không chuyển nguyên khối vào một React component |
| `services/system.service.ts` | Readiness, ADB/emulator, thiết bị, cấu hình hệ thống |
| `core/models/`, `utils/` | Nhiều types và hàm thuần có thể tái sử dụng sau khi loại phụ thuộc Angular |
| `core/i18n/en.ts`, `vi.ts` | Catalog EN/VI hiện có, giữ key và nội dung; thay pipe/service bằng hook/provider |
| `services/ui-preferences.service.ts` | Storage key `artemis.ui.preferences.v1`, schema version 1; theme/language phải giữ tương thích |
| `apps/admin_console/server.py` | Hiện phục vụ SPA bằng fallback về một `index.html`; chưa phải static host cho từng route Next |
| `setup.py`, `artemis/resources/` | Đóng gói frontend đã build vào Python distribution |
| `start.bat`, `scripts/start.ps1`, `start.sh` | Bootstrap, kiểm tra Node và frontend build; đang gắn với Angular/output layout hiện tại |
| `artemis/interfaces/cli/commands/ui.py`, `doctor.py` | Phát hiện artifact, build/hướng dẫn frontend và readiness |
| `.github/workflows/ci.yml` | Frontend job đang chạy Angular tests/build; cần thêm lane Next trước khi thay thế |

Các đường dẫn `src/...` trong bảng được tính từ `apps/showcase_ui/`.

## 3. Kiến trúc đề xuất

### 3.1. Next.js static export, FastAPI vẫn là runtime duy nhất

Chọn `output: 'export'`, `trailingSlash: true`; đóng gói toàn bộ thư mục `out/`. Next hỗ trợ xuất artifact tĩnh; các tính năng cần server runtime không dùng trong phương án này. Tham chiếu: [Next.js Static Exports](https://nextjs.org/docs/app/guides/static-exports).

Luồng production:

```text
Browser → FastAPI :8009
           ├─ /, /workspace/, /task-schedule/, /settings/, /check/ → HTML đã export
           ├─ /_next/* và public assets → file build
           └─ /api/*, stream, video, replay → backend hiện có
```

- Không dùng Server Actions, runtime SSR, ISR, middleware/proxy Next hoặc rewrites Next để xử lý API trong production export.
- Dữ liệu task/thiết bị/cấu hình được lấy phía client sau khi mount. Build phải thành công khi backend, điện thoại và credentials không có mặt.
- Server Components chỉ làm khung tĩnh; vùng tương tác sử dụng Client Components. `use client` không làm mọi truy cập browser an toàn ở build: chỉ đọc `window`, storage, EventSource trong browser lifecycle. Tham chiếu: [Server and Client Components](https://nextjs.org/docs/app/getting-started/server-and-client-components).
- Với `useSearchParams`, đặt boundary phù hợp/Suspense để route vẫn export được. Không tạo route động theo session ID chưa biết ở build; giữ session trong query/state như contract hiện có.
- Ảnh live/replay dùng URL backend và `<img>` hoặc cấu hình không cần image optimization server. Giữ video HTML/media endpoint hiện tại.
- Dùng font/icon local có license phù hợp; tránh build cần tải Google Fonts mỗi lần.
- Chốt phiên bản Next/React/Node/TypeScript tương thích ở P0 và pin trong lockfile; không mặc định TypeScript 6 của Angular tương thích với mọi bản Next.

### 3.2. Tổ chức source trong giai đoạn chuyển tiếp

Tạo `apps/showcase_next/` song song; chưa đổi tên hoặc xóa `apps/showcase_ui/`.

```text
apps/showcase_next/
  src/app/                   # layout, providers, page, not-found
    workspace/page.tsx
    task-schedule/page.tsx
    settings/page.tsx
    check/page.tsx
  src/features/              # home, settings, schedules, workspace, legacy-check
  src/components/            # navigation, form controls, dialogs, player
  src/lib/api/               # typed HTTP client và API contracts
  src/lib/stream/            # SSE lifecycle, parser, reducer
  src/lib/i18n/              # catalogs, interpolation, provider/hooks
  src/lib/preferences/       # storage schema và bootstrap theme
  src/lib/utils/             # hàm thuần, formatter, timeline
  src/styles/                # theme tokens, global styles, SCSS modules
  tests/                     # unit, integration, browser fixtures
  public/
  next.config.ts
```

Lựa chọn mặc định: fetch + AbortController, React Context/reducer/external store, SCSS Modules và tokens hiện tại. Chỉ thêm thư viện state/form/UI khi có nhu cầu đã chứng minh; không buộc rewrite toàn bộ CSS sang Tailwind.

## 4. Bảng đối chiếu tính năng bắt buộc

| Route/nhóm | Yêu cầu giữ nguyên |
| --- | --- |
| Navigation | Thứ tự Home → Workspace → Task Schedule → Settings; active state, back/forward, refresh và liên kết trực tiếp |
| Home `/` | Nhập goal, Flash/Pro, run/starting/error, readiness, gợi ý tác vụ, expected output, tuning và tooltips; không khôi phục dòng mô tả đã bỏ |
| Settings `/settings` | Tabs General, Models, Email, Android, System & Environment; giữ query `?tab=...`; chỉ tab System có Launch Autonomous Tasks |
| General | Combo ngôn ngữ EN/VI, dark/light, Start with Windows kiểu toggle; capability không hỗ trợ phải hiển thị rõ |
| Models | Provider/default/fallback model, key/URL, validation, save vào backend, thông báo trước restart, chờ kết nối lại; không làm mất focus textbox |
| Email | SMTP, password write-only, bật/tắt, save/test connection/test email; lỗi nằm đúng form, không tự gửi thư trong mount/effect |
| Android/System | Device selection, ADB local/remote, emulator, prerequisites, diagnostics; giữ chọn thiết bị và cảnh báo authorization |
| Schedule `/task-schedule` | Interval theo phút; daily/weekly có giây và timezone; chọn ngày; create/edit/pause/resume/delete/run now/history |
| Schedule modal | Click ngoài không đóng; không có Advanced task options; Preview 5 bắt buộc theo contract; lỗi preview/save ngay trong form |
| Schedule email | Người nhận, tiêu đề, summary cuối task, attachment text dễ đọc giống Workspace, trạng thái gửi/retry; retry email không chạy lại task |
| Workspace `/workspace` | Task queue, history, notes/plans, stream/startup progress, token/usage, stop/resume, lỗi và trạng thái terminal |
| Live view/replay | Màn hình Android nhúng, mở tự động theo hành vi hiện có, reconnect, replay từng bước/video, playback controls và tọa độ đủ tương phản |
| Legacy `/check` | Khảo sát và chuyển tính năng riêng còn dùng; không tự redirect sang Workspace trước khi chứng minh tương đương |
| Admin/debug | `/admin`, `/debug` vẫn phục vụ console backend riêng; không bị Next chiếm route |

Bảng này là checklist parity, không phải yêu cầu phát triển thêm tính năng mới.

## 5. State, API và realtime

- Lập inventory method/path/request/response/error từ services Angular và schemas Python; giữ API contract, encode ID và optimistic version.
- Tách task/session store khỏi component; root provider giữ kết nối xuyên chuyển tab. State form/modal ở cấp feature, không reset vì SSE hoặc đổi theme.
- Một kết nối SSE cho mỗi tab trình duyệt; không mở lại ở mỗi route. React Strict Mode mount/unmount phải cleanup đúng, không nhân đôi stream/poll.
- Port reducer/aggregator và test event trùng, sai thứ tự, partial text/reset, reconnect, task hoàn tất; không dùng polling ghi đè dữ liệu mới hơn.
- Đồng bộ snapshot sau reconnect; bounded backoff, cancel request cũ, bỏ response thuộc session không còn chọn.
- Không retry tự động các mutation run/create schedule/send mail nếu backend không có idempotency contract.
- Backend restart do lưu model: hiển thị trạng thái đang restart, tạm ngừng poll nhiễu, reconnect có deadline và Retry. Không tự gửi lại lệnh save/restart.
- Giữ `artemis.sessions.v1` và `artemis.ui.preferences.v1`; validate schema, chịu được storage bị chặn/hỏng. Không ghi dữ liệu nhạy cảm mới vào cache.
- Chuyển locale/theme không restart backend, không dừng task, không làm mất draft hoặc tạo lại player.

## 6. Theme, i18n và bảo mật

- Tái sử dụng catalog EN/VI, interpolation và fallback; type-check key, kiểm tra key thiếu và hard-coded text trong các trạng thái lỗi/tooltip/modal.
- Giữ theme tokens, đưa selector Angular như `:host` hoặc `app-*` sang component class/module tương ứng; không copy mù toàn bộ dark override.
- Bootstrap theme trước paint; first render/hydration ổn định giữa HTML export và client. Chỉ suppress hydration warning ở thuộc tính root thật sự do bootstrap quản lý, không che lỗi toàn trang.
- Kiểm tra light/dark × EN/VI, contrast tọa độ, focus-visible, dialog focus trap, keyboard navigation và màn hình hẹp.
- Markdown/log/model output là dữ liệu không tin cậy: sanitize HTML, chặn URL scheme nguy hiểm, không render raw HTML chưa kiểm soát.
- Giữ loopback/same-origin/Host validation của FastAPI; không mở CORS wildcard để sửa lỗi dev.
- Backend giữ đọc/ghi secrets; build frontend không được đọc `.env` ở workspace chứa credentials. Dữ liệu mật khẩu form chỉ tồn tại tạm trong memory và được xóa sau thao tác phù hợp.

## 7. Static hosting, bootstrap và packaging

### 7.1. Static host của FastAPI

- Thêm lựa chọn frontend explicit `angular|next` trong cấu hình launcher/hosting (tên cấu hình chốt khi triển khai); mặc định Angular cho đến khi parity đạt.
- Với Next, map `/workspace` và `/workspace/` tới `workspace/index.html`, tương tự các route khác; không trả Home HTML cho mọi đường dẫn.
- Phục vụ nguyên cây `out/`, gồm `/_next/` và các payload navigation do phiên bản Next đã pin sinh ra. Không chỉ copy HTML/JS/CSS hoặc đoán suffix payload.
- Unknown UI route dùng trang 404 có đường về Home. Đây là thay đổi có chủ đích so với wildcard Angular redirect Home; tránh biến route, API hoặc asset lỗi thành HTTP 200.
- Asset không tồn tại trả 404, đúng MIME; giữ chống path traversal và ưu tiên route API/media/admin trước UI.
- Hashed assets cache dài; HTML/manifest có revalidation để tránh bundle cũ sau cập nhật. Xác minh điều hướng client lẫn mở URL trực tiếp trên artifact production.

### 7.2. Dev và production

- Production: build export rồi FastAPI phục vụ cùng origin/port, không `next start` và không Node daemon thứ hai.
- Dev: chuẩn parity dùng export + FastAPI tại cùng origin/port mục tiêu `:8009`. Nếu cần HMR, dev-only gateway nghe `:8009`, proxy UI/HMR tới Next dev và API/media tới FastAPI `:8000`; chỉ forward Host/Origin theo allowlist loopback, hỗ trợ SSE không buffering, video Range và HMR transport. Không ship gateway này như dependency runtime.
- Không đổi backend security middleware toàn cục để phục vụ riêng HMR. Gate P1 phải chứng minh cả production static host và dev path.

### 7.3. Danh sách điểm cần cập nhật đồng bộ

- `start.bat`, `scripts/start.ps1`, `start.sh`: chọn frontend, Node engine mới, khóa dependency, kiểm tra source/artifact, build đúng app và dừng rõ khi build thất bại.
- `artemis/interfaces/cli/commands/ui.py`, `doctor.py`: bỏ giả định Angular cho bản Next; readiness xác minh artifact được chọn, không lấy nhầm `dist` cũ. `ARTEMIS_FRONTEND=angular|next` chọn runtime/build (mặc định `angular`).
- `setup.py`, resource loader và packaging tests: `ARTEMIS_FRONTEND_PACKAGE=angular|next` chọn artifact đóng gói (fallback `ARTEMIS_FRONTEND`, mặc định `angular`), copy đầy đủ cây export vào `resources/showcase_angular` hoặc `resources/showcase_next` cùng `frontend-manifest.json`; wheel đã cài không cần Node.
- `.github/workflows/ci.yml`, `Makefile`, Dockerfile và các script/docs có tham chiếu `ng`, `showcase_ui`, `dist/frontend/browser`: inventory trước cutover, không bỏ sót đường release.
- Manifest build có framework, commit/version và dấu vết inputs/lockfile; tránh quyết định fresh/stale chỉ từ một `index.html` sau đổi framework.
- Stage build vào thư mục riêng; chỉ chuyển active artifact khi kiểm tra đủ file. Không xóa bundle đang phục vụ trước khi build mới thành công.

## 8. Lộ trình thực hiện và điều kiện qua giai đoạn

### P0 — Baseline và contracts

- [x] Chụp baseline route/state, danh sách test và API contract; các rủi ro/lỗi hiện có được ghi tại `docs/nextjs-migration-baseline.md`.
- [x] Chốt phiên bản và static-export proof-of-concept; build chỉ dùng dữ liệu tĩnh và không gọi backend.
- [x] Chốt URL/query, storage, theme/i18n, `/check`, hosting manifest và frontend switch tại `docs/adr-nextjs-static-frontend.md`.
- [x] Đầu ra: checklist parity/baseline, dependency lock và ghi nhận quyết định kỹ thuật; fixtures không chứa secrets.

### P1 — Nền tảng Next và host

- [x] Tạo `apps/showcase_next/`, strict TS, scripts lint/typecheck/test/build và npm lock.
- [x] Layout/navigation, API client, preferences/i18n/theme, form/dialog primitives.
- [x] Static host Next theo từng route; giữ Angular độc lập và kiểm thử chọn bundle.
- [x] Gate: production export không backend build thành công; deep links, query, CSS/assets/cache, reserved routes và 404 đã smoke qua FastAPI artifact.

### P2 — Home và Settings

- [x] Port Home và toàn bộ tabs Settings; giữ gợi ý/tuning và capability gating chính.
- [x] Port model save/restart và email form qua mock tests; không sửa dữ liệu thật trong CI.
- [x] Gate integration: cả 4 tổ hợp EN/VI × light/dark đạt; SMTP textbox/password giữ focus và dirty values qua local/cross-tab preference changes; Email/emulator GET không replay và readiness lifecycle không overlap.

### P3 — Task Schedule

- [x] Port CRUD, recurrence UI, preview, history, email notification/retry và modal behavior.
- [x] Gate: interval/daily/weekly, giây/timezone, version conflict, lỗi form và preview invalidation hoạt động như cũ; interaction/API tests bao phủ ISO weekdays, exact five occurrences và explicit conflict retry.

### P4 — Workspace và legacy

- [x] Port root store/SSE/polling, stream panels, notes/plans, queue/history và live/replay controls cơ bản; chunk coalescing 80/500 ms, reset discard, trace dedupe, timestamp normalization và no-overlap polling đã có pure tests.
- [x] Port `/check` thành route legacy riêng; không redirect sang Workspace.
- [x] Gate integration: root provider giữ state/player qua route-child remount, duy trì đúng một EventSource hoạt động, không phát sinh mutation; stale/foreign session events bị loại và polling không nhân đôi. Managed-browser reconnect smoke vẫn được giữ trong P5 acceptance lane.

### P5 — Đóng gói và cutover

- [x] Cập nhật bootstrap/CLI/doctor/wheel/CI theo cùng artifact contract; container inventory xác nhận không có release touchpoint cần đổi.
- [ ] Smoke artifact đã đạt trên Windows; full Linux Docker runtime build/launch cũng đạt và phục vụ đúng 5 route/404 mà không cần Node. Native Linux/macOS packaged-wheel hosted-runner execution vẫn còn mở.
- [ ] So sánh hiệu năng với baseline: startup, route load, RAM, xử lý log dài/live stream; đặt ngưỡng từ số đo P0, không tuyên bố Next tự động nhanh hơn.
- [ ] Chuyển mặc định sang Next chỉ khi tất cả route parity đạt; lưu Angular release để rollback.

### P6 — Dọn migration

- [ ] Sau khi nghiệm thu bản Next, gỡ Angular/RxJS/Zone/CDK và Karma nếu không còn consumer.
- [x] README/developer guide và CI đã mô tả staged selector, build/test/acceptance/package workflow và rollback; fallback Angular chỉ được bỏ sau release acceptance/cutover.
- [ ] Không xóa database, traces, credentials, schedules, localStorage hoặc startup entry trong quá trình dọn source.

## 9. Chiến lược kiểm thử

- Unit: tái sử dụng test hàm thuần/types/formatters; React component test bằng Vitest + Testing Library (pin phiên bản tương thích).
- Integration: fixtures API/SSE có kiểm soát cho errors, stream reset, retry, race, abort và optimistic version.
- Browser: Playwright trên production export được FastAPI phục vụ; kiểm tra Chromium và thêm Firefox/WebKit để bắt lỗi layout/media phù hợp.
- Hosting/security: route, query, trailing slash, missing asset/API, traversal, MIME, Range, SSE, secret leakage, unsafe markdown.
- Regression: giữ chạy test Angular khi chưa cutover; đối chiếu theo hành vi, không chỉ so số lượng test cũ/mới.
- OS matrix: build/bootstrap Windows/Linux/macOS; các tính năng chỉ hỗ trợ một OS được kiểm tra capability và thông báo, không giả lập thành công.
- Mobile thật: khi viết test tương tác Android, phải khám phá và xác minh bằng ARTEMIS trước, `adb devices -l`, hỏi chọn serial nếu có nhiều thiết bị; dùng wait conditions rõ ràng. Chạy ở lane có thiết bị, không giao task thật/gửi mail thật trong CI thường.
- Test save model/startup/email dùng config tạm và fake lifecycle/SMTP/registry; không restart dịch vụ cá nhân hoặc thay autostart thật ngoài phiên nghiệm thu được cho phép.

## 10. Rollout, rollback và tiêu chí hoàn tất

1. Giữ mặc định Angular trong P0–P4; Next chỉ bật explicit để nghiệm thu.
2. Build và xác minh artifact mới riêng; đổi frontend active một lần sau gate P5.
3. Không tự restart backend đang chạy task để deploy UI; nếu hosting mới cần restart, thông báo và dùng drain/lifecycle hiện có.
4. Khi rollback, chọn artifact Angular đã lưu; giữ cùng origin/port để bảo toàn preferences. Không rollback schema database vì migration này không sửa schema.
5. Giữ asset bản cũ trong thời gian chuyển tiếp hoặc cơ chế báo reload khi chunk cũ mất; tránh tab đang mở trắng trang vì thay artifact.

Hoàn tất khi tất cả route và tính năng trong bảng parity đã nghiệm thu; production dùng Next/TypeScript qua FastAPI :8009; scripts và Python package phục vụ đúng artifact; EN/VI và dark/light nhất quán; stream/live view/schedule/restart không hồi quy; build không cần điện thoại/credentials; rollback đã diễn tập.

Chỉ tạo tài liệu này không cần build frontend, cài dependency hay restart dịch vụ. Việc triển khai phải được thực hiện ở yêu cầu tiếp theo.
