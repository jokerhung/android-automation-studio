Tôi sẽ đọc tài liệu ticket và giao diện Settings hiện có để đặc tả trải nghiệm cài đặt trong terminal và bước cấu hình trên web. Tôi chỉ đọc trong workspace, rồi trả toàn bộ nội dung `design.md` bằng Markdown, không sửa code hay ghi file.
# Ticket #2 — Thiết kế trải nghiệm cài đặt ARTEMIS qua Internet

- **Tài liệu:** `docs/tickets/0c1a1bc5-68d7-4fb5-9f7d-51c8b3eec99c/design.md`
- **Phạm vi:** Terminal installer trên Windows, Linux, macOS và bước tiếp tục cấu hình trong giao diện web.
- **Trạng thái:** Đặc tả thiết kế, chưa triển khai hoặc kiểm thử thực tế.
- **Ràng buộc:** Không sửa code, không commit/push.

## 1. Căn cứ thiết kế

Đã đọc `requirements.md`, các script cài dependency/khởi động và mã nguồn giao diện Home, Settings trong workspace.

`requirements.md` hiện bị ngắt ở US-01, kết thúc bằng thông báo model quá tải. Thiết kế này dựa trên phần yêu cầu còn đọc được, nội dung bàn giao Leader/BA và mã nguồn; các quyết định bổ sung được ghi rõ là đề xuất.

### Hiện trạng liên quan

| Thành phần | Hiện trạng | Hướng thiết kế |
|---|---|---|
| Installer | Có `scripts/install_deps.*`; chưa thấy bootstrap ở gốc | Bổ sung trải nghiệm chạy từ Internet |
| Khởi động | Các entry point có mặc định cổng khác nhau | Luôn hiển thị cổng thực tế |
| Settings | Có General, Models, Email, Android, System | Tận dụng các tab hiện có |
| Home | Có cảnh báo readiness và liên kết mở cấu hình | Phân biệt ứng dụng đã chạy với khả năng chạy tác vụ |
| Kiểm tra server | Có endpoint xác minh danh tính ARTEMIS | Chỉ công bố thành công sau kiểm tra HTTP |

Chưa xác minh giao diện bằng ứng dụng đang chạy. Wireframe bên dưới là thiết kế đề xuất dựa trên cấu trúc hiện có.

## 2. Mục tiêu trải nghiệm

Sau một lệnh cài đặt, người dùng biết:

1. Máy có được hỗ trợ không.
2. Installer đang thực hiện bước nào.
3. Khi nào cần thao tác hoặc cấp quyền.
4. Ứng dụng đã mở được hay chưa.
5. URL truy cập trên máy và từ thiết bị cùng mạng.
6. Cách cấu hình tiếp, dừng và khởi động lại.

Hai trạng thái cần tách biệt:

- **Giao diện đã sẵn sàng:** Server và trang web hoạt động.
- **Sẵn sàng chạy tác vụ:** Cấu hình model hợp lệ và có thiết bị Android đáp ứng yêu cầu.

Thiếu API key hoặc thiết bị không được ngăn mở Settings.

## 3. Cấu trúc trải nghiệm

```text
Hướng dẫn cài đặt
  └─ Chọn Windows / Linux / macOS
      └─ Sao chép và chạy lệnh
          ├─ Kiểm tra môi trường
          ├─ Tải mã nguồn
          ├─ Chuẩn bị công cụ và dependency
          ├─ Khởi tạo cấu hình
          ├─ Build giao diện
          └─ Khởi động và kiểm tra HTTP
              ├─ Thành công → URL → Settings
              └─ Thất bại → Nguyên nhân + bước khôi phục

Settings
  ├─ Models → Cấu hình nhà cung cấp/model
  ├─ Android → Kết nối thiết bị
  └─ System → Xem và kiểm tra lại readiness
```

Không bổ sung wizard bắt buộc. Người dùng tiếp tục trong hệ thống Settings hiện có.

## 4. Điểm bắt đầu — Hướng dẫn cài đặt

Đây là khối nội dung dùng trong tài liệu cài đặt; không yêu cầu tạo landing page mới.

### Wireframe

```text
Cài đặt ARTEMIS

Tải, cài đặt và khởi động bằng một lệnh.
Cần kết nối Internet.

[Windows] [Linux] [macOS]

Mở PowerShell và chạy:

┌──────────────────────────────────────────────┐
│ <lệnh cài đặt tương ứng hệ điều hành>        │
└──────────────────────────────────────────────┘
[Sao chép lệnh]

Installer sẽ:
• Tải ARTEMIS và chuẩn bị các công cụ cần thiết
• Giữ cấu hình đã có khi chạy lại
• Khởi động và hiển thị URL local/LAN

[Hệ điều hành được hỗ trợ] [Xử lý sự cố]
```

### Nội dung lệnh dự kiến

**Linux và macOS — Bash:**

```bash
curl -fsSL https://raw.githubusercontent.com/jokerhung/android-automation-studio/nextjs/install.sh | bash
```

**Windows — PowerShell:**

```powershell
& ([scriptblock]::Create((Invoke-RestMethod -Uri 'https://raw.githubusercontent.com/jokerhung/android-automation-studio/nextjs/install.ps1')))
```

Đây là entry point dự kiến của tính năng mới; chưa được xác minh hoạt động trong workspace hiện tại.

### Quy tắc

- Ghi rõ shell cần sử dụng.
- Không yêu cầu clone repo trước.
- Hiển thị ma trận OS/kiến trúc do BA/Developer chốt; không tự tuyên bố hỗ trợ mọi phiên bản.
- Nút sao chép báo “Đã sao chép lệnh”; nếu clipboard thất bại, cho phép chọn và sao chép thủ công.
- Trường hợp môi trường thiếu công cụ tải ban đầu phải có hướng dẫn riêng theo OS, không giả định installer đã chạy.

## 5. Terminal T1 — Kiểm tra và cài đặt

### Wireframe

```text
ARTEMIS — Cài đặt

Hệ điều hành : Windows / x64
Nguồn        : jokerhung/android-automation-studio
Nhánh        : nextjs
Thư mục      : <đường dẫn thực tế>

[OK]    1/6 Kiểm tra môi trường
[OK]    2/6 Tải mã nguồn
[DANG]  3/6 Chuẩn bị công cụ và dependency
             Đang đồng bộ môi trường Python...
[CHO]   4/6 Khởi tạo cấu hình
[CHO]   5/6 Build giao diện
[CHO]   6/6 Khởi động và kiểm tra HTTP

Đã chạy: 01:42
Nhật ký: <đường dẫn thực tế>
```

### Thành phần và quy tắc hiển thị

| Thành phần | Nội dung |
|---|---|
| Header | Tên ứng dụng và mục đích |
| Tóm tắt | OS, kiến trúc, nguồn, thư mục đích |
| Bước hiện tại | Số bước, tên công việc, trạng thái |
| Chi tiết | Công cụ đang tải/cài/kiểm tra |
| Nhật ký | Đường dẫn log để tra cứu khi cần |
| Kết quả | Thành công, cần thao tác, lỗi hoặc đã hủy |

Quy ước trạng thái:

- `[OK]`: hoàn thành và đã kiểm tra.
- `[DANG]`: đang thực hiện.
- `[CHO]`: chưa bắt đầu.
- `[GIU]`: giữ tài nguyên hoặc cấu hình hiện có.
- `[CAN]`: cần người dùng thao tác.
- `[LOI]`: thất bại.
- `[HUY]`: bị hủy.

Không dùng màu hoặc emoji làm dấu hiệu duy nhất. Terminal không hỗ trợ Unicode vẫn đọc được.

### Loading

- Chỉ hiển thị phần trăm khi biết tổng dung lượng hoặc tổng số mục.
- Với build và đồng bộ dependency, hiển thị tên thao tác và thời gian đã chạy.
- Đề xuất cập nhật dòng chờ mỗi 10 giây nếu chưa có tiến độ mới.
- Không đưa ETA giả hoặc đánh dấu hoàn tất dựa trên thời gian chờ.
- Không xóa lịch sử lỗi khỏi terminal.

## 6. Terminal T2 — Quyền và lựa chọn cần thiết

Luồng mặc định tự động thực hiện các bước thông thường. Chỉ yêu cầu lựa chọn khi quyết định ảnh hưởng đến khả năng tiếp tục.

### Thiếu quyền

```text
[CAN] Cần quyền quản trị để cài <tên thành phần>.

Thao tác: <mô tả ngắn thay đổi cần thực hiện>
Hệ điều hành có thể hiển thị yêu cầu cấp quyền.
```

- Dùng hộp thoại UAC hoặc cơ chế xác thực của hệ điều hành.
- Không yêu cầu nhập mật khẩu vào trường riêng của ARTEMIS.
- Nếu người dùng từ chối: sử dụng phương án cài trong tài khoản hiện tại nếu được hỗ trợ; nếu không, dừng với hướng dẫn rõ ràng.

### Cổng bị chiếm

```text
[CAN] Cổng 8009 đang được ứng dụng khác sử dụng.

[1] Dùng cổng khả dụng 8010
[2] Nhập cổng khác
[3] Hủy cài đặt

Chọn [1]:
```

- Cổng đề xuất phải được kiểm tra trước khi hiển thị.
- Không tự dừng tiến trình khác.
- Nếu xác minh được ARTEMIS đang chạy từ cùng bản cài, đề nghị sử dụng phiên hiện có.
- Cổng thay thế phải xuất hiện nhất quán trong mọi URL và hướng dẫn sau đó.

### Chạy qua pipe hoặc không có terminal tương tác

- Prompt phải đọc từ terminal điều khiển riêng, không đọc từ luồng chứa script.
- Nếu không có terminal tương tác, không treo chờ nhập liệu.
- Áp dụng mặc định đã công bố cho thao tác thông thường.
- Nếu bắt buộc có quyết định, thoát với lý do và cú pháp chạy lại có tham số thực tế được hỗ trợ.
- Tên tham số CLI do Developer chốt và đồng bộ vào tài liệu.

## 7. Terminal T3 — Hoàn tất và bàn giao URL

### Wireframe

```text
[OK] ARTEMIS đã khởi động
[OK] Đã xác minh HTTP và giao diện

TRUY CẬP TRÊN MÁY NÀY
http://localhost:8009
http://127.0.0.1:8009

TRUY CẬP TỪ THIẾT BỊ CÙNG MẠNG
Wi-Fi      http://192.168.1.25:8009
Ethernet   http://192.168.10.8:8009

Địa chỉ LAN đã được phát hiện.
Chưa xác minh truy cập từ thiết bị khác.

CẤU HÌNH TIẾP
http://localhost:8009/settings/?tab=system

Bạn có thể mở giao diện ngay.
Cấu hình model và kết nối Android trong Settings.

QUẢN LÝ ỨNG DỤNG
Thư mục      : <đường dẫn thực tế>
Khởi động lại: <lệnh thực tế của bản cài>
Dừng         : <lệnh thực tế của bản cài>
Nhật ký      : <đường dẫn thực tế>

Ứng dụng đang chạy nền.
Bạn có thể đóng terminal.
```

Các địa chỉ và cổng trên chỉ là dữ liệu minh họa.

### Quy tắc URL

- Mỗi URL nằm trên một dòng, không có dấu chấm hoặc dấu câu ở cuối.
- Không in `0.0.0.0` như địa chỉ để truy cập.
- In cả `localhost` và `127.0.0.1`, kèm cổng thực tế.
- Liệt kê các IPv4 LAN khả dụng theo interface, loại trùng.
- Interface ảo/VPN nếu được liệt kê phải có nhãn riêng, không mặc định coi là mạng LAN phù hợp.
- Khi không phát hiện LAN:

```text
[CAN] Chưa tìm thấy địa chỉ IPv4 LAN.
Bạn vẫn có thể truy cập bằng URL trên máy này.
Kết nối Wi-Fi/Ethernet và kiểm tra lại địa chỉ mạng.
```

### Điều kiện công bố thành công

Phải xác nhận được:

1. Server là ARTEMIS.
2. HTTP phản hồi hợp lệ.
3. Trang giao diện được phục vụ.

Cổng TCP mở chưa đủ để hiển thị “đã khởi động”.

Chỉ hiển thị “Có thể đóng terminal” khi tiến trình nền đã được xác minh. Nếu chạy foreground, phải ghi “Giữ terminal này mở; nhấn Ctrl+C để dừng”.

Không bắt buộc tự mở trình duyệt; lỗi mở trình duyệt không làm mất kết quả cài đặt.

## 8. Terminal T4 — Lỗi, chạy lại và hủy

### Wireframe lỗi

```text
[LOI] Không thể tải mã nguồn
Bước: 2/6 — Tải mã nguồn

Nguyên nhân: Không kết nối được tới máy chủ tải xuống.
Đã giữ nguyên cấu hình hiện có.
Ứng dụng chưa được khởi động.

Tiếp theo:
1. Kiểm tra kết nối Internet hoặc proxy.
2. Chạy lại lệnh cài đặt.

Nhật ký: <đường dẫn thực tế>
Mã lỗi: <mã lỗi ổn định>
```

Thông báo phải phản ánh trạng thái thực tế; không luôn khẳng định “chưa khởi động” nếu đã có phiên chạy từ trước.

### Ma trận trạng thái

| Tình huống | Hiển thị và hành động |
|---|---|
| OS/kiến trúc chưa hỗ trợ | Dừng sớm; ghi rõ môi trường phát hiện và liên kết ma trận hỗ trợ |
| Tải xuống thất bại | Nêu bước, nguồn tải và cách chạy lại; retry có giới hạn |
| Dependency không tương thích | Hiển thị phiên bản hiện có và yêu cầu; thông báo phương án thay thế |
| Thiếu quyền ghi | Nêu thư mục không ghi được và cách chọn vị trí khác |
| Thư mục đích chứa dữ liệu không nhận diện được | Dừng, yêu cầu chọn vị trí khác; không ghi đè |
| Build thất bại | Không báo cài xong; dẫn tới log và cách chạy lại |
| HTTP chưa sẵn sàng | Hiển thị đang chờ và thời gian; hết hạn thì báo lỗi có giới hạn |
| Sai danh tính server | Báo xung đột cổng, không nhận dịch vụ khác là ARTEMIS |
| Không có LAN | Hoàn tất local, thông báo trạng thái LAN riêng |
| Thiếu API key/Android | Hoàn tất cài đặt; hướng dẫn mở Settings |
| Ctrl+C | Báo đã hủy, bước dở dang và trạng thái tiến trình còn chạy |

### Chạy lại

```text
[GIU] Phát hiện bản cài hiện có: <đường dẫn>
[GIU] Giữ nguyên cấu hình và khóa API đã lưu
[OK]  Kiểm tra lại các thành phần cần thiết
```

- Không tự hiểu “chạy lại installer” là đồng ý reset hoặc nâng cấp.
- Không in giá trị khóa API hoặc nội dung `.env`.
- Sau lỗi/hủy, kiểm tra lại đầu ra của bước dở dang trước khi tiếp tục.
- In lệnh quản lý có thể sao chép trực tiếp; bản triển khai không được để placeholder.

## 9. Web W1 — Tiếp tục cấu hình trong Settings

Tận dụng route hiện có:

| Mục đích | Route |
|---|---|
| Tổng quan readiness | `/settings/?tab=system` |
| Cấu hình model | `/settings/?tab=models` |
| Kết nối Android | `/settings/?tab=android` |

### Wireframe desktop

```text
┌──────────────────────────────────────────────────────────┐
│ ARTEMIS                                      [Ngôn ngữ] │
├───────────────┬──────────────────────────────────────────┤
│ Settings      │ Hoàn tất cấu hình                        │
│               │ Giao diện đã hoạt động.                  │
│ General       │ Kiểm tra các mục để bắt đầu tác vụ.      │
│ Models        │                                          │
│ Email         │ Model AI                 [Cần cấu hình]  │
│ Android       │ [Mở cấu hình model]                      │
│ System ●      │                                          │
│               │ Android                  [Chưa kết nối]  │
│               │ [Mở kết nối Android]                     │
│               │                                          │
│               │ [Kiểm tra lại]                           │
│               │ [Về trang chủ]                           │
└───────────────┴──────────────────────────────────────────┘
```

Đây là cách trình bày đề xuất trong tab System. Giữ các khả năng chẩn đoán hiện có.

### Trạng thái

| Trạng thái | Nội dung |
|---|---|
| Loading | “Đang kiểm tra cấu hình…”; chưa kết luận thiếu cấu hình |
| Chưa cấu hình model | Liên kết tới Models; vẫn cho phép duyệt giao diện |
| Không có Android | Hướng dẫn kết nối và cấp quyền USB debugging |
| Thiết bị unauthorized | “Mở khóa điện thoại và chấp nhận yêu cầu USB debugging” |
| Thiết bị offline | Ghi rõ offline; không gộp vào “không có thiết bị” |
| Lỗi kiểm tra | “Không thể kiểm tra trạng thái” và nút “Thử lại” |
| Readiness đạt | “Sẵn sàng chạy tác vụ” và liên kết về Home |
| Dữ liệu cũ khi refresh lỗi | Giữ dữ liệu, gắn “Chưa cập nhật được” và thời điểm kiểm tra |

Không coi lỗi API kiểm tra là bằng chứng chắc chắn rằng cấu hình bị thiếu.

## 10. Web W2 — Models và Android

### Models

Tận dụng form hiện có, bổ sung hoặc thống nhất nội dung trợ giúp:

- Nhà cung cấp.
- Model chính và các trường liên quan theo nhà cung cấp.
- API key khi nhà cung cấp yêu cầu.
- Thông báo lưu và lỗi ngay trong form.

Quy tắc:

- Khóa đã lưu chỉ biểu thị “Đã cấu hình”.
- Trường khóa để trống không mang nghĩa xóa khóa.
- Không yêu cầu API key với nhà cung cấp không cần khóa.
- Đang lưu: nút hiển thị “Đang lưu…”, ngăn gửi trùng.
- Lưu thất bại: giữ draft trong phiên hiện tại.
- “Đã lưu” không đồng nghĩa “Đã xác minh kết nối”.
- Nếu cần restart theo luồng hiện có, giải thích trước khi thực hiện và hiển thị trạng thái kết nối lại.

### Android

- Không có thiết bị: hiển thị hướng dẫn ngắn và nút kiểm tra lại.
- Có nhiều thiết bị: yêu cầu chọn thiết bị trước khi chạy tác vụ.
- Hiển thị model, serial và trạng thái để phân biệt.
- Có thiết bị nhưng chưa được cấp quyền: chỉ rõ thao tác trên điện thoại.
- Cho phép cấu hình sau; không chặn truy cập Settings.

## 11. Luồng tương tác chính

### Cài mới

```text
Chạy lệnh
→ Kiểm tra môi trường
→ Tải và cài thành phần
→ Tạo cấu hình còn thiếu
→ Build
→ Khởi động
→ Xác minh HTTP
→ In URL
→ Mở System
→ Cấu hình Models/Android nếu cần
→ Về Home
```

### Chạy lại

```text
Chạy lại lệnh
→ Nhận diện bản cài
→ Giữ cấu hình
→ Kiểm tra thành phần
→ Nhận diện ARTEMIS đang chạy hoặc khởi động lại theo lựa chọn
→ Xác minh HTTP
→ In URL thực tế
```

### Truy cập LAN thất bại

```text
Mở URL LAN trên thiết bị khác
→ Không truy cập được
→ Kiểm tra URL local trên máy chủ
→ Kiểm tra cùng mạng, interface, bind và firewall
→ Thử lại URL LAN
```

Không gắn nhãn “LAN đã hoạt động” chỉ vì phát hiện được IP. Việc kiểm chứng từ thiết bị khác thuộc nghiệm thu.

## 12. Responsive

### Terminal

- Ưu tiên bố cục một cột, đọc được ở khoảng 60–80 ký tự.
- Không dùng bảng nhiều cột cho URL, lỗi hoặc lệnh quản lý.
- URL và lệnh dài giữ nguyên để sao chép; terminal có thể tự xuống dòng.
- Khi chuyển output vào file hoặc không có TTY: bỏ animation, mã màu và thao tác ghi đè dòng.

### Web

| Kích thước | Bố cục |
|---|---|
| Từ 1024 px | Navigation Settings bên trái, nội dung bên phải |
| 768–1023 px | Giảm khoảng cách, giữ nội dung form dễ đọc |
| Dưới 768 px | Một cột; tab Settings cuộn ngang có dấu hiệu còn mục |
| 320 px / zoom lớn | Form và nút xuống dòng; không cuộn ngang toàn trang |

Không cắt serial, lỗi hoặc thông tin quan trọng bằng dấu `…` nếu không có cách xem đầy đủ.

## 13. Accessibility và ngôn ngữ

- Tái sử dụng component, theme và cơ chế Việt/Anh hiện có.
- Dùng cấu trúc heading rõ ràng.
- Mọi input có label; lỗi liên kết với trường tương ứng.
- Trạng thái web dùng `aria-live="polite"`; lỗi chặn thao tác dùng thông báo phù hợp.
- Không đọc lại toàn bộ tiến trình theo mỗi nhịp cập nhật.
- Tab và nút hoạt động bằng bàn phím, focus nhìn rõ.
- Sau dialog, focus trở về phần tử mở dialog.
- Không tự chuyển focus khi readiness cập nhật nền.
- Tương phản văn bản tối thiểu 4.5:1; trạng thái có chữ bên cạnh màu/icon.
- Vùng tương tác chính tối thiểu 44 × 44 px.
- Tôn trọng tùy chọn giảm chuyển động.
- Không lưu API key vào URL, clipboard tự động hoặc bộ nhớ trình duyệt để khôi phục draft.
- Terminal dùng thông báo ngắn, không phụ thuộc emoji hoặc ký tự trang trí.

## 14. Tiêu chí nghiệm thu thiết kế

- [ ] Có hướng dẫn lệnh riêng cho PowerShell và Bash.
- [ ] Hiển thị nguồn, OS, kiến trúc và thư mục cài thực tế.
- [ ] Tiến độ phản ánh công việc, không dùng phần trăm giả.
- [ ] Prompt không xung đột với stdin khi chạy qua pipe.
- [ ] Không treo chờ nhập khi không có terminal tương tác.
- [ ] Quyền cần cấp được giải thích trước.
- [ ] Chạy lại giữ cấu hình và khóa API.
- [ ] Lỗi có nguyên nhân, trạng thái hiện tại và bước phục hồi.
- [ ] Chỉ báo thành công sau xác minh ARTEMIS qua HTTP và giao diện.
- [ ] URL local/LAN dùng cùng cổng thực tế; không dùng `0.0.0.0`.
- [ ] Không có IP LAN vẫn hoàn tất truy cập local.
- [ ] Phân biệt IP được phát hiện với LAN đã kiểm chứng.
- [ ] Có lệnh thực tế để dừng, khởi động lại và xem log.
- [ ] Phân biệt chạy nền với foreground.
- [ ] Thiếu API key/Android vẫn mở được Settings.
- [ ] Web có loading, empty, error và trạng thái dữ liệu cũ.
- [ ] Terminal không màu và web dùng bàn phím vẫn sử dụng được.

## 15. Điểm bàn giao cần chốt

| Nội dung | Bên chốt | Ảnh hưởng |
|---|---|---|
| Ma trận OS/kiến trúc | BA/Developer | Hướng dẫn và lỗi môi trường chưa hỗ trợ |
| Thư mục cài mặc định | Developer | Tóm tắt, log và hướng dẫn quản lý |
| Chính sách chọn cổng | BA/Developer | Prompt và URL cuối cùng |
| Cú pháp tham số không tương tác | Developer | Cách chạy lại khi không có TTY |
| Chế độ chạy nền và lệnh quản lý | Developer | Nội dung hoàn tất |
| Timeout/retry từng bước | Planner/Developer | Loading và thông báo lỗi |
| Phạm vi thay đổi web | Planner | Bổ sung nội dung trong Settings hiện có |

Các nội dung chưa chốt không làm thay đổi nguyên tắc trải nghiệm: **cài đặt có tiến độ rõ ràng, xác minh trước khi báo thành công, cung cấp URL đúng và cho phép cấu hình tiếp ngay trên web.**