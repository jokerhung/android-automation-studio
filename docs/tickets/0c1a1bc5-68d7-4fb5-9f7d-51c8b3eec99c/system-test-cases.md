Tôi sẽ dùng skill `docs` vì đầu ra là tài liệu Markdown cần lưu trong `docs/`. Tôi sẽ đọc đầy đủ hướng dẫn skill và các tài liệu ticket hiện có, sau đó chỉ soạn system test end-to-end; chưa chạy test, không sửa mã nguồn, không ghi file, không commit/push.Phiên này không có docs connector mà skill yêu cầu, nên tôi dùng phương án dự phòng: đọc trực tiếp các tài liệu Markdown trong workspace và trả nội dung hoàn chỉnh trong chat để hệ thống lưu. Tôi đang đối chiếu yêu cầu, thiết kế và kế hoạch để mỗi test case truy vết được acceptance criteria.# Ticket #2 — System Test Cases: Cài đặt ARTEMIS qua Internet

- **Tài liệu đích:** `docs/tickets/0c1a1bc5-68d7-4fb5-9f7d-51c8b3eec99c/system-test-cases.md`
- **Loại kiểm thử:** System test end-to-end
- **Trạng thái:** Chưa thực thi
- **Phạm vi:** Cài mới, khởi tạo, build, chạy nền, HTTP readiness, URL local/LAN, onboarding, chạy lại, quản lý tiến trình và các luồng lỗi trên Windows, Linux, macOS.
- **Ngoài phạm vi:** Unit test, integration test, kiểm thử từng hàm/module, thay đổi mã nguồn, commit hoặc push.

## 1. Căn cứ

Test case được xây dựng từ:

- `requirements.md`
- `design.md`
- `implementation-plan.md`
- Tiêu chí nghiệm thu trong bàn giao của Leader

`requirements.md` hiện bị ngắt tại US-01 do lỗi model quá tải. Ma trận hệ điều hành, tham số public, timeout và mã thoát dưới đây sử dụng các quyết định đề xuất trong `implementation-plan.md`. Các mục này cần được cập nhật nếu hợp đồng triển khai cuối cùng thay đổi.

## 2. Ma trận nghiệm thu

Mỗi dòng trong ma trận phải được thực thi trên một máy ảo hoặc máy vật lý sạch độc lập.

| Mã môi trường | Hệ điều hành | Kiến trúc | Shell |
|---|---|---|---|
| ENV-WIN-01 | Windows 11 | x64 | Windows PowerShell 5.1 |
| ENV-WIN-02 | Windows 11 | x64 | PowerShell 7 |
| ENV-LNX-01 | Ubuntu 22.04 | x86_64 | Bash |
| ENV-LNX-02 | Ubuntu 24.04 | x86_64 | Bash |
| ENV-MAC-01 | macOS 14 | Intel x86_64 | Bash hệ thống |
| ENV-MAC-02 | macOS 14 | Apple Silicon arm64 | Bash hệ thống |
| ENV-MAC-03 | macOS 15 | Apple Silicon arm64 | Bash hệ thống |

“Môi trường sạch” có hệ điều hành, kết nối HTTPS và công cụ tối thiểu để nhận lệnh đầu tiên:

- Linux/macOS: Bash, `curl`, CA certificate và công cụ giải nén hệ thống.
- Windows: PowerShell có khả năng tải HTTPS và giải nén ZIP.
- Không cài sẵn Git, Python, uv, Node.js, npm, Homebrew hoặc WinGet.
- Chưa có mã nguồn ARTEMIS.
- Chưa cấu hình API key.
- Chưa kết nối thiết bị Android, trừ khi test case quy định khác.

## 3. Lệnh cài đặt chuẩn

### Linux và macOS

```bash
set -o pipefail
curl -fsSL https://raw.githubusercontent.com/jokerhung/android-automation-studio/nextjs/install.sh | bash
```

### Windows

```powershell
& ([scriptblock]::Create((Invoke-RestMethod -Uri 'https://raw.githubusercontent.com/jokerhung/android-automation-studio/nextjs/install.ps1')))
```

Việc kiểm tra URL public chỉ được thực hiện sau khi `install.sh`, `install.ps1` và các file phụ thuộc đã được phát hành cùng revision lên nhánh `nextjs`.

## 4. Acceptance criteria tổng quát

| Mã | Acceptance criteria |
|---|---|
| AC-01 | Có lệnh cài qua Internet cho Bash và PowerShell; không cần clone source trước. |
| AC-02 | Cài thành công trên từng dòng của ma trận hệ điều hành và kiến trúc đã công bố. |
| AC-03 | Máy thiếu Git, Python, uv, Node.js và npm vẫn được chuẩn bị đủ dependency bắt buộc. |
| AC-04 | Cấu hình còn thiếu được khởi tạo; chạy lại không ghi đè cấu hình, khóa API hoặc dữ liệu đã có. |
| AC-05 | Chỉ báo thành công sau khi xác minh đúng ARTEMIS, HTTP hợp lệ, Home, Settings và frontend asset được phục vụ. |
| AC-06 | Hiển thị đúng URL `localhost`, `127.0.0.1` và IPv4 LAN khả dụng với cổng thực tế; không in `0.0.0.0` như URL truy cập. |
| AC-07 | URL LAN truy cập được từ thiết bị thứ hai cùng mạng khi chạy với LAN bind. |
| AC-08 | Không có IP LAN hoặc chạy local-only vẫn hoàn tất truy cập local và thông báo đúng giới hạn. |
| AC-09 | Cổng bị chiếm, tải lỗi, thiếu quyền, dependency lỗi, build lỗi và readiness timeout trả lỗi cùng mã thoát phù hợp. |
| AC-10 | Tiến trình nền tiếp tục chạy sau khi đóng terminal; start, status, stop và restart dùng đúng bản cài và cổng thực tế. |
| AC-11 | Thiếu API key hoặc thiết bị Android không chặn mở Home và Settings. |
| AC-12 | Terminal và log không làm lộ API key, lifecycle token hoặc nội dung bí mật trong `.env`. |
| AC-13 | Chạy lại không tự nâng cấp source, không tạo thêm daemon và không build/sync lại khi đầu vào không đổi. |
| AC-14 | Prompt không đọc từ stdin chứa script; chế độ không tương tác không treo chờ nhập liệu. |
| AC-15 | Lỗi hiển thị công đoạn, nguyên nhân, trạng thái tiến trình, vị trí log và cách chạy lại có thể thực hiện được. |
| AC-16 | Thư mục không rỗng nhưng không phải bản cài ARTEMIS không bị ghi đè. |
| AC-17 | Hai installer không đồng thời thay đổi cùng một bản cài. |
| AC-18 | Các API lifecycle và thao tác quản trị local-only không bị mở rộng quyền khi giao diện bind LAN. |
| AC-19 | Tài liệu có hướng dẫn cài mới, chạy lại, start, status, stop, restart và xử lý sự cố. |
| AC-20 | Output terminal dùng trạng thái chữ rõ ràng, dùng được khi không có màu/Unicode và không hiển thị phần trăm hoặc ETA không có căn cứ. |

## 5. Test case chi tiết

### ST-E2E-001 — Cài mới trên Ubuntu từ máy sạch

**Điều kiện**

- Thực hiện riêng trên ENV-LNX-01 và ENV-LNX-02.
- Không có source, Git, Python, uv, Node.js hoặc npm.
- Có Internet và quyền ghi vào thư mục cài mặc định.
- Cổng `8009` khả dụng.

**Dữ liệu**

- Lệnh Bash chuẩn.
- Thư mục mặc định dự kiến: `$HOME/.local/share/artemis`.
- Cổng mặc định: `8009`.

**Thao tác**

1. Ghi nhận phiên bản OS, kiến trúc và danh sách công cụ đang có.
2. Chạy lệnh Bash chuẩn từ một thư mục không chứa source.
3. Theo dõi toàn bộ output và mã thoát.
4. Đóng terminal sau khi installer báo hoàn tất.
5. Mở terminal mới và truy cập các URL được in.
6. Mở Home, `/settings/?tab=system`, `/settings/?tab=models` và `/settings/?tab=android`.
7. Kiểm tra ít nhất một tài nguyên frontend dưới `_next`.
8. Thực hiện lệnh status được installer in.

**Kết quả mong đợi**

- Source được tải mà không cần Git.
- Python 3.12 tương thích, uv, Node.js/npm và dependency bắt buộc được chuẩn bị.
- Frontend được build và server được chạy nền.
- Installer chỉ báo thành công sau khi Home, Settings và frontend asset hoạt động.
- Mã thoát bằng `0`.
- `localhost:8009` và `127.0.0.1:8009` truy cập được.
- Daemon còn chạy sau khi đóng terminal.
- Status nhận diện đúng bản cài ARTEMIS.

**Acceptance criteria**

- Đạt AC-01, AC-02, AC-03, AC-05, AC-06, AC-10, AC-11 và AC-20.
- Phải lưu bằng chứng riêng cho Ubuntu 22.04 và Ubuntu 24.04.

---

### ST-E2E-002 — Cài mới trên macOS từ máy sạch

**Điều kiện**

- Thực hiện riêng trên ENV-MAC-01, ENV-MAC-02 và ENV-MAC-03.
- Không có Git, Python, uv, Node.js, npm hoặc Homebrew.
- Có Internet và quyền ghi vào thư mục cài mặc định.

**Dữ liệu**

- Lệnh Bash chuẩn.
- Thư mục mặc định dự kiến: `$HOME/.local/share/artemis`.
- Cổng mặc định: `8009`.

**Thao tác**

1. Ghi nhận phiên bản macOS và kiến trúc.
2. Xác nhận Homebrew và các runtime phát triển không có sẵn.
3. Chạy lệnh Bash chuẩn.
4. Theo dõi quá trình tải source, chuẩn bị runtime, build và readiness.
5. Đóng terminal.
6. Truy cập các URL local được in và mở các tab Settings.
7. Chạy lệnh status được cung cấp.

**Kết quả mong đợi**

- Luồng web cốt lõi cài được khi không có Homebrew.
- Công cụ tải về đúng kiến trúc Intel hoặc Apple Silicon.
- Không yêu cầu mở terminal mới để nhận PATH.
- Server chạy nền và tiếp tục hoạt động sau khi terminal đóng.
- Mã thoát bằng `0`; Home, Settings và asset được phục vụ đầy đủ.

**Acceptance criteria**

- Đạt AC-01, AC-02, AC-03, AC-05, AC-06, AC-10 và AC-11.
- Phải lưu bằng chứng riêng cho mỗi dòng macOS/kiến trúc.

---

### ST-E2E-003 — Cài mới trên Windows từ máy sạch

**Điều kiện**

- Thực hiện riêng trên ENV-WIN-01 và ENV-WIN-02.
- Không có Git, Python, uv, Node.js, npm hoặc WinGet.
- PowerShell cho phép tải HTTPS.
- Cổng `8009` khả dụng.

**Dữ liệu**

- Lệnh PowerShell chuẩn.
- Thư mục mặc định dự kiến: `%LOCALAPPDATA%\Programs\Artemis`.
- Cổng mặc định: `8009`.

**Thao tác**

1. Ghi nhận phiên bản Windows, kiến trúc và PowerShell.
2. Chạy lệnh PowerShell chuẩn từ thư mục bất kỳ.
3. Theo dõi mã thoát của từng chương trình native thông qua kết quả toàn luồng.
4. Đóng cửa sổ PowerShell khi installer hoàn tất.
5. Truy cập Home, Settings và frontend asset bằng URL được in.
6. Kiểm tra không xuất hiện cửa sổ console phụ của daemon.
7. Chạy lệnh status được installer cung cấp.

**Kết quả mong đợi**

- Scriptblock tải và thực thi thành công mà không cần clone source.
- Runtime và dependency được cài trong phạm vi hỗ trợ.
- Lỗi native command, nếu có, không bị che bởi `try/catch`.
- Daemon chạy nền, không tạo cửa sổ console phụ và còn sống sau khi đóng PowerShell.
- Mã thoát bằng `0`; giao diện được xác minh bằng HTTP.

**Acceptance criteria**

- Đạt AC-01, AC-02, AC-03, AC-05, AC-06, AC-10 và AC-11.
- Phải lưu bằng chứng riêng cho Windows PowerShell 5.1 và PowerShell 7.

---

### ST-E2E-004 — Cài từ thư mục bất kỳ có dấu cách và Unicode

**Điều kiện**

- Một môi trường đại diện cho từng nhóm Windows, Linux và macOS.
- Chưa có bản cài ARTEMIS.
- Có thư mục làm việc chứa dấu cách và ký tự Unicode.

**Dữ liệu**

- Ví dụ: `C:\QA Data\Cài đặt Artemis` hoặc `$HOME/QA Data/Cài đặt Artemis`.
- Thư mục cài tùy chỉnh cũng chứa dấu cách/Unicode.
- `--install-dir PATH` hoặc `-InstallDir PATH`.

**Thao tác**

1. Chuyển shell vào thư mục làm việc có dấu cách/Unicode.
2. Chạy installer qua Internet với thư mục cài tùy chỉnh.
3. Hoàn tất cài đặt.
4. Sao chép và chạy nguyên văn các lệnh start, status, stop và restart được in.
5. Truy cập các URL được in.

**Kết quả mong đợi**

- Installer không suy ra sai vị trí từ CWD, `$BASH_SOURCE` hoặc `$PSScriptRoot`.
- Source, runtime và log được tạo đúng thư mục đã chọn.
- Quoting trong lệnh quản lý hoạt động với đường dẫn có dấu cách/Unicode.
- Không có placeholder trong lệnh bàn giao.

**Acceptance criteria**

- Đạt AC-01, AC-05, AC-10 và AC-19.

---

### ST-E2E-005 — Mở giao diện khi chưa có API key và Android

**Điều kiện**

- Cài mới thành công.
- Không có khóa API trong cấu hình.
- `adb devices` không có thiết bị sẵn sàng.

**Dữ liệu**

- `/`
- `/settings/?tab=system`
- `/settings/?tab=models`
- `/settings/?tab=android`

**Thao tác**

1. Mở Home.
2. Mở tab System.
3. Mở tab Models.
4. Mở tab Android.
5. Dùng chức năng kiểm tra lại readiness nếu có.

**Kết quả mong đợi**

- Home và Settings mở bình thường.
- System phân biệt “giao diện đã hoạt động” với “sẵn sàng chạy tác vụ”.
- Models hướng dẫn cấu hình nhà cung cấp/model.
- Android hiển thị trạng thái chưa có thiết bị và hướng dẫn kết nối.
- Không xuất hiện wizard bắt buộc chặn việc duyệt giao diện.
- Thiếu key hoặc Android không làm installer thất bại.

**Acceptance criteria**

- Đạt AC-05 và AC-11.

---

### ST-E2E-006 — Truy cập bằng URL LAN từ thiết bị thứ hai

**Điều kiện**

- ARTEMIS được cài với LAN bind.
- Máy chủ và thiết bị thử thứ hai ở cùng mạng Wi-Fi hoặc Ethernet.
- Firewall cho phép cổng thực tế.
- Máy chủ có ít nhất một IPv4 LAN hợp lệ.

**Dữ liệu**

- URL LAN do installer in.
- URL Home và Settings.
- Một frontend asset thực tế.

**Thao tác**

1. Đối chiếu IP được in với interface đang hoạt động trên máy chủ.
2. Trên thiết bị thứ hai, mở URL LAN.
3. Mở Home và các tab System, Models, Android.
4. Tải lại trang và kiểm tra frontend asset.
5. Thử gọi một API lifecycle hoặc thao tác quản trị được giới hạn local từ thiết bị thứ hai.

**Kết quả mong đợi**

- URL LAN dùng đúng IPv4 và cổng thực tế.
- Home, Settings và asset tải được từ thiết bị thứ hai.
- Output trước đó chỉ ghi IP đã phát hiện, không tuyên bố LAN đã được xác minh trước test này.
- API lifecycle hoặc thao tác quản trị local-only vẫn bị từ chối từ máy khác.
- Không in `0.0.0.0` như URL truy cập.

**Acceptance criteria**

- Đạt AC-06, AC-07 và AC-18.

---

### ST-E2E-007 — Chạy với chế độ local-only

**Điều kiện**

- Cổng được chọn đang khả dụng.
- Máy có IPv4 LAN.

**Dữ liệu**

- Bash: `--local-only`.
- PowerShell: `-LocalOnly`.

**Thao tác**

1. Cài ARTEMIS bằng chế độ local-only.
2. Truy cập `localhost` và `127.0.0.1`.
3. Thử truy cập IP LAN từ thiết bị thứ hai.
4. Kiểm tra output hoàn tất.

**Kết quả mong đợi**

- Server bind loopback.
- Hai URL local truy cập được.
- URL LAN không được quảng bá là có thể dùng.
- Truy cập từ thiết bị thứ hai không thành công.
- Installer vẫn hoàn tất với mã `0`.

**Acceptance criteria**

- Đạt AC-05, AC-06, AC-08 và AC-18.

---

### ST-E2E-008 — Không có IPv4 LAN khả dụng

**Điều kiện**

- Tắt hoặc cô lập mọi interface Wi-Fi/Ethernet có IPv4 LAN.
- Giữ loopback và khả năng cung cấp source theo cơ chế kiểm thử phù hợp.
- Cổng local khả dụng.

**Dữ liệu**

- Luồng cài đặt mặc định.

**Thao tác**

1. Chạy installer.
2. Chờ readiness hoàn tất.
3. Kiểm tra danh sách URL và thông báo mạng.
4. Truy cập hai URL local.

**Kết quả mong đợi**

- Installer hoàn tất với mã `0`.
- `localhost` và `127.0.0.1` được in và truy cập được.
- Có thông báo rõ chưa tìm thấy IPv4 LAN.
- Không in loopback, unspecified, link-local hoặc IP rỗng trong nhóm URL LAN.
- Không coi thiếu LAN là lỗi cài đặt.

**Acceptance criteria**

- Đạt AC-06 và AC-08.

---

### ST-E2E-009 — Liệt kê nhiều interface, VPN và địa chỉ trùng

**Điều kiện**

- Máy có Wi-Fi hoặc Ethernet, một interface VPN/ảo và địa chỉ trùng có thể kiểm soát.
- ARTEMIS chạy với LAN bind.

**Dữ liệu**

- Danh sách interface và IPv4 thực tế của máy.

**Thao tác**

1. Chạy installer hoặc lệnh hiển thị lại thông tin truy cập.
2. Đối chiếu từng URL LAN với interface hệ thống.
3. Kiểm tra nhãn interface VPN/ảo.
4. Kiểm tra địa chỉ trùng, link-local và loopback.

**Kết quả mong đợi**

- IPv4 hợp lệ được liệt kê theo interface và không bị trùng.
- Interface VPN/ảo có nhãn riêng khi nhận diện được.
- Không mặc định coi VPN là mạng LAN phù hợp.
- Loại loopback, unspecified và link-local khỏi danh sách LAN.

**Acceptance criteria**

- Đạt AC-06 và AC-08.

---

### ST-E2E-010 — Chạy lại và bảo toàn cấu hình, khóa và dữ liệu

**Điều kiện**

- Có bản cài khỏe và đang chạy.
- Đã thêm một API key kiểm thử, cấu hình model, file JSONC và dữ liệu ứng dụng nhận diện được.
- Đã lưu hash của `.env`, JSONC, database và dữ liệu trước khi chạy lại.

**Dữ liệu**

- Cùng lệnh installer đã dùng lần đầu.
- Cùng thư mục và cổng.

**Thao tác**

1. Ghi PID và số tiến trình ARTEMIS hiện tại.
2. Ghi hash các file cấu hình và dữ liệu.
3. Chạy lại installer.
4. Ghi output, mã thoát, PID và số tiến trình sau khi hoàn tất.
5. So sánh hash trước và sau.
6. Kiểm tra source revision và thời điểm build.
7. Mở lại Home và Settings.

**Kết quả mong đợi**

- Installer nhận diện bản cài hiện có và hiển thị `[GIU]`.
- Không in giá trị API key.
- Hash cấu hình và dữ liệu không đổi.
- Không tự tải revision mới đè lên source.
- Không build/sync lại nếu đầu vào không đổi.
- Không tạo thêm daemon và không restart phiên khỏe.
- Web tiếp tục hoạt động trên đúng cổng đã lưu.

**Acceptance criteria**

- Đạt AC-04, AC-12 và AC-13.

---

### ST-E2E-011 — Phục hồi sau lần cài bị gián đoạn

**Điều kiện**

- Có một lần cài trước bị hủy sau khi tải source hoặc trong lúc chuẩn bị dependency.
- Không có cấu hình người dùng bị hỏng.
- Cổng mục tiêu khả dụng.

**Dữ liệu**

- Cùng lệnh installer và cùng thư mục cài.

**Thao tác**

1. Kiểm tra trạng thái staging và metadata còn lại.
2. Chạy lại installer.
3. Theo dõi bước kiểm tra artifact trước khi tiếp tục.
4. Hoàn tất cài đặt và mở giao diện.

**Kết quả mong đợi**

- Installer không tin mù trạng thái “đã xong” của lần trước.
- Artifact dở dang được nhận diện và xử lý an toàn.
- Cấu hình đã có được giữ nguyên.
- Không dùng frontend artifact dở dang để báo thành công.
- Lần chạy lại hoàn tất và giao diện được xác minh.

**Acceptance criteria**

- Đạt AC-04, AC-05, AC-13 và AC-15.

---

### ST-E2E-012 — Quản lý vòng đời start, status, stop và restart

**Điều kiện**

- Cài đặt thành công.
- Có các lệnh quản lý thực tế do installer in.

**Dữ liệu**

- Lệnh start, status, stop, restart và đường dẫn log.
- Host và cổng thực tế.

**Thao tác**

1. Chạy status khi server đang hoạt động.
2. Chạy stop.
3. Xác nhận server ngừng và URL không còn phục vụ.
4. Chạy start.
5. Xác nhận server sẵn sàng bằng HTTP.
6. Chạy restart.
7. Xác nhận server hoạt động lại trên cùng host/cổng.
8. Theo dõi để xác định stop/status có chạy lại dependency hoặc build hay không.

**Kết quả mong đợi**

- Status nhận diện đúng bản cài và trạng thái.
- Stop chỉ dừng tiến trình ARTEMIS đã xác minh.
- Start và restart dùng interpreter của bản cài.
- Mọi lệnh giữ đúng host/cổng.
- Stop/status không chạy lại cài dependency hoặc build.
- Lệnh có thể sao chép và chạy trực tiếp.

**Acceptance criteria**

- Đạt AC-10 và AC-19.

---

### ST-E2E-013 — Cổng mặc định bị dịch vụ khác chiếm trong terminal tương tác

**Điều kiện**

- Một dịch vụ không phải ARTEMIS đang nghe tại `8009`.
- Có terminal tương tác.
- Có ít nhất một cổng thay thế khả dụng.

**Dữ liệu**

- Cổng bị chiếm: `8009`.
- Cổng thay thế dự kiến: `8010` hoặc cổng được installer tìm thấy.

**Thao tác**

1. Khởi động dịch vụ khác trên `8009`.
2. Chạy installer.
3. Kiểm tra prompt và chọn cổng thay thế được đề xuất.
4. Hoàn tất cài đặt.
5. Truy cập mọi URL được in.
6. Xác nhận dịch vụ ban đầu trên `8009` vẫn chạy.

**Kết quả mong đợi**

- Installer không dừng dịch vụ khác.
- Prompt cho biết cổng bị chiếm và cung cấp lựa chọn rõ ràng.
- Cổng đề xuất đã được kiểm tra là khả dụng.
- Tất cả URL và lệnh quản lý dùng nhất quán cổng thay thế.
- Chỉ báo thành công sau HTTP readiness trên cổng thay thế.

**Acceptance criteria**

- Đạt AC-05, AC-06, AC-09 và AC-15.

---

### ST-E2E-014 — Cổng bị chiếm trong chế độ không tương tác

**Điều kiện**

- Một dịch vụ không phải ARTEMIS chiếm `8009`.
- Installer chạy không có TTY hoặc với `--non-interactive`/`-NonInteractive`.

**Dữ liệu**

- Cổng mặc định `8009`.

**Thao tác**

1. Chạy installer ở chế độ không tương tác.
2. Theo dõi thời gian chạy, output và mã thoát.
3. Kiểm tra dịch vụ đang chiếm cổng.

**Kết quả mong đợi**

- Installer không treo chờ nhập liệu.
- Không âm thầm đổi cổng.
- Dịch vụ đang chạy không bị dừng.
- Output hướng dẫn chạy lại với `--port` hoặc `-Port`.
- Trả mã lỗi nhóm cổng/readiness, dự kiến `8`.

**Acceptance criteria**

- Đạt AC-09, AC-14 và AC-15.

---

### ST-E2E-015 — Chỉ định cổng tùy chỉnh

**Điều kiện**

- Cổng tùy chỉnh hợp lệ và khả dụng.

**Dữ liệu**

- Bash: `--port 8123`.
- PowerShell: `-Port 8123`.

**Thao tác**

1. Cài đặt với cổng `8123`.
2. Kiểm tra output hoàn tất.
3. Truy cập URL local và LAN.
4. Chạy status, stop, start và restart.

**Kết quả mong đợi**

- Installer sử dụng chính xác `8123`.
- Mọi URL và lệnh quản lý dùng `8123`.
- Không xuất hiện `8000` hoặc `8009` trong thông tin bàn giao trừ nội dung giải thích.
- Chạy lại tiếp tục ưu tiên cổng đã lưu.

**Acceptance criteria**

- Đạt AC-05, AC-06, AC-10 và AC-13.

---

### ST-E2E-016 — Sai tham số hoặc cổng không hợp lệ

**Điều kiện**

- Chưa có bản cài hoặc có bản cài không bị ảnh hưởng.

**Dữ liệu**

- Cổng `0`, `65536`, chuỗi không phải số.
- Tham số không tồn tại.
- Thư mục cài bị thiếu giá trị.

**Thao tác**

1. Chạy installer riêng với từng bộ dữ liệu sai.
2. Ghi output và mã thoát.
3. Kiểm tra filesystem và tiến trình.

**Kết quả mong đợi**

- Dừng trước khi tải hoặc thay đổi bản cài.
- Hiển thị cách dùng và giá trị hợp lệ.
- Không tạo daemon.
- Trả mã môi trường/tham số không hợp lệ, dự kiến `2`.

**Acceptance criteria**

- Đạt AC-09 và AC-15.

---

### ST-E2E-017 — Lỗi tải source hoặc archive không hợp lệ

**Điều kiện**

- Có thể chặn truy cập máy chủ tải xuống hoặc chuyển hướng nguồn tới archive lỗi.
- Không có bản cài hoàn chỉnh tại thư mục đích.

**Dữ liệu**

- Mất mạng, lỗi DNS, HTTP lỗi, tải dở hoặc archive thiếu cấu trúc bắt buộc.

**Thao tác**

1. Chạy installer với từng dạng lỗi tải.
2. Theo dõi retry và timeout.
3. Kiểm tra mã thoát.
4. Kiểm tra thư mục cài và staging.

**Kết quả mong đợi**

- Retry có giới hạn; không lặp vô hạn.
- Archive thiếu `pyproject.toml`, `uv.lock`, `artemis/`, `apps/` hoặc package bắt buộc bị từ chối.
- Không đưa source lỗi vào vị trí chính thức.
- Không báo ứng dụng sẵn sàng.
- Output có nguồn tải, nguyên nhân, log và cách chạy lại.
- Trả mã tải/checksum/archive, dự kiến `4`.

**Acceptance criteria**

- Đạt AC-09 và AC-15.

---

### ST-E2E-018 — Thiếu quyền ghi hoặc từ chối quyền quản trị

**Điều kiện**

- Chọn thư mục người dùng hiện tại không có quyền ghi.
- Có tình huống thành phần cần quyền quản trị.
- Có thể từ chối UAC hoặc xác thực hệ điều hành.

**Dữ liệu**

- `--install-dir`/`-InstallDir` trỏ tới thư mục bị hạn chế.

**Thao tác**

1. Chạy installer.
2. Kiểm tra thông báo trước khi yêu cầu quyền.
3. Từ chối quyền quản trị.
4. Theo dõi fallback cài trong tài khoản hiện tại, nếu được hỗ trợ.
5. Ghi mã thoát và kiểm tra thư mục đích.

**Kết quả mong đợi**

- Installer giải thích thành phần và thay đổi cần quyền.
- Không yêu cầu nhập mật khẩu vào trường riêng của ARTEMIS.
- Nếu có phương án user-local, installer dùng phương án đó.
- Nếu không thể tiếp tục, installer dừng với hướng dẫn chọn vị trí khác.
- Không ghi dở vào thư mục bị hạn chế.
- Trả mã quyền/thư mục, dự kiến `3`.

**Acceptance criteria**

- Đạt AC-09 và AC-15.

---

### ST-E2E-019 — Thư mục đích không rỗng và không phải ARTEMIS

**Điều kiện**

- Thư mục đích tồn tại, có dữ liệu người dùng và không có metadata ARTEMIS.

**Dữ liệu**

- `--install-dir`/`-InstallDir` trỏ tới thư mục trên.

**Thao tác**

1. Lưu hash và danh sách file trong thư mục.
2. Chạy installer.
3. Ghi output và mã thoát.
4. So sánh nội dung trước và sau.

**Kết quả mong đợi**

- Installer dừng trước khi ghi đè.
- Yêu cầu chọn vị trí khác.
- Dữ liệu và hash không đổi.
- Không tạo daemon.
- Trả mã nhóm thư mục/khóa cài đặt, dự kiến `3`.

**Acceptance criteria**

- Đạt AC-09, AC-15 và AC-16.

---

### ST-E2E-020 — Hai installer chạy đồng thời trên cùng thư mục

**Điều kiện**

- Chưa có bản cài hoàn chỉnh.
- Có hai terminal độc lập.

**Dữ liệu**

- Cùng thư mục cài và cùng cổng.

**Thao tác**

1. Khởi động installer thứ nhất.
2. Khi installer thứ nhất đang tải hoặc chuẩn bị dependency, khởi động installer thứ hai.
3. Theo dõi cả hai tiến trình.
4. Kiểm tra source, metadata, môi trường và daemon sau khi kết thúc.

**Kết quả mong đợi**

- Chỉ một installer được phép thay đổi bản cài tại một thời điểm.
- Installer còn lại chờ có kiểm soát hoặc dừng với thông báo khóa rõ ràng.
- Không có source, metadata hoặc môi trường bị trộn.
- Không sinh hai daemon.
- Nếu dừng do khóa, trả mã dự kiến `3`.

**Acceptance criteria**

- Đạt AC-10, AC-15 và AC-17.

---

### ST-E2E-021 — Dependency bắt buộc không tương thích hoặc cài thất bại

**Điều kiện**

- Có thể mô phỏng Python/Node không tương thích, checksum sai hoặc lỗi tải dependency.
- Chưa có server ARTEMIS đang chạy.

**Dữ liệu**

- Node dưới `20.9.0`.
- Python không thuộc nhánh được hỗ trợ.
- Lỗi `uv sync --locked` hoặc `npm ci`.

**Thao tác**

1. Chạy installer cho từng dạng lỗi.
2. Theo dõi cách xử lý runtime quá cũ.
3. Ghi output, log và mã thoát.
4. Kiểm tra `uv.lock` và tiến trình.

**Kết quả mong đợi**

- Installer dùng runtime tương thích do bản cài quản lý hoặc báo lỗi rõ ràng.
- Không nâng cấp lặp lại thành phần đã đạt yêu cầu.
- `uv.lock` không bị sửa.
- Lỗi dependency bắt buộc chặn bước build/start.
- Không báo thành công.
- Trả mã dependency, dự kiến `5`.

**Acceptance criteria**

- Đạt AC-03, AC-09 và AC-15.

---

### ST-E2E-022 — Cấu hình hiện có không hợp lệ

**Điều kiện**

- Có bản cài nhận diện được.
- Một file cấu hình ARTEMIS bị lỗi cú pháp.
- Có bản sao và hash file lỗi trước test.

**Dữ liệu**

- `.env` hoặc JSONC lỗi cú pháp nhưng vẫn chứa dữ liệu cần bảo toàn.

**Thao tác**

1. Chạy lại installer.
2. Theo dõi bước khởi tạo/phục hồi cấu hình.
3. Ghi mã thoát.
4. So sánh file trước và sau.

**Kết quả mong đợi**

- Installer chỉ rõ file cấu hình lỗi.
- Không tự reset hoặc ghi đè file.
- Không in nội dung bí mật.
- Không báo giao diện sẵn sàng nếu runtime không thể đọc cấu hình.
- Trả mã cấu hình, dự kiến `6`.

**Acceptance criteria**

- Đạt AC-04, AC-09, AC-12 và AC-15.

---

### ST-E2E-023 — Build frontend thất bại hoặc artifact dở dang

**Điều kiện**

- Có thể làm `npm ci`/`npm run build` thất bại hoặc tạo artifact thiếu route/asset.
- Chưa có phiên ARTEMIS khỏe cần được giữ nguyên.

**Dữ liệu**

- Thiếu hoặc sai `package-lock.json`.
- Thiếu `out/index.html`, route Settings hoặc `_next` asset.
- Artifact còn lại từ lần build lỗi.

**Thao tác**

1. Chạy installer với từng tình huống.
2. Theo dõi bước build.
3. Ghi mã thoát và log.
4. Kiểm tra tiến trình server và output thành công.

**Kết quả mong đợi**

- Không fallback từ `npm ci` sang `npm install` khi lockfile lỗi hoặc thiếu.
- Artifact dở dang không được chấp nhận.
- Không báo cài xong hoặc sẵn sàng.
- Không khởi động server bằng frontend không hoàn chỉnh.
- Trả mã build/artifact, dự kiến `7`.

**Acceptance criteria**

- Đạt AC-05, AC-09 và AC-15.

---

### ST-E2E-024 — Dịch vụ khác trả HTTP 200 trên cổng mục tiêu

**Điều kiện**

- Một web server không phải ARTEMIS đang chạy trên cổng mục tiêu.
- Web server trả HTTP 200 cho `/`, có thể trả nội dung giống trang fallback.

**Dữ liệu**

- Cổng `8009`.

**Thao tác**

1. Khởi động web server giả trên `8009`.
2. Chạy installer với cổng này trong chế độ không tương tác.
3. Ghi output, mã thoát và trạng thái web server giả.

**Kết quả mong đợi**

- Installer không coi TCP mở hoặc HTTP 200 là ARTEMIS sẵn sàng.
- Xác minh danh tính ARTEMIS thất bại.
- Dịch vụ giả không bị dừng.
- Output báo xung đột cổng hoặc sai danh tính.
- Trả mã nhóm cổng/readiness, dự kiến `8`.

**Acceptance criteria**

- Đạt AC-05, AC-09 và AC-15.

---

### ST-E2E-025 — HTTP readiness timeout

**Điều kiện**

- Backend có thể khởi động tiến trình nhưng không hoàn tất readiness.
- Có thể mô phỏng Home, Settings hoặc asset không phản hồi.

**Dữ liệu**

- Readiness tối đa dự kiến: 120 giây.
- Request timeout dự kiến: 2 giây.
- Poll dự kiến: khoảng 1 giây.

**Thao tác**

1. Chạy installer trong điều kiện readiness không thể đạt.
2. Đo thời gian và theo dõi thông báo chờ.
3. Ghi trạng thái tiến trình sau timeout.
4. Ghi mã thoát và đường dẫn log.

**Kết quả mong đợi**

- Installer poll có giới hạn và không treo vô hạn.
- Không báo thành công chỉ vì tiến trình hoặc cổng tồn tại.
- Khi hết hạn, thông báo công đoạn, nguyên nhân, trạng thái tiến trình và log.
- Trả mã nhóm daemon/readiness, dự kiến `8`.

**Acceptance criteria**

- Đạt AC-05, AC-09 và AC-15.

---

### ST-E2E-026 — Home trả 200 nhưng frontend chưa được build đầy đủ

**Điều kiện**

- Backend trả trang fallback “Not Built” hoặc nội dung tương đương với HTTP 200.
- Settings hoặc frontend asset không tồn tại.

**Dữ liệu**

- `/`
- `/settings/`
- Một `_next` asset thực tế.

**Thao tác**

1. Chạy installer hoặc luồng readiness.
2. Theo dõi kết quả kiểm tra HTTP.
3. Ghi output và mã thoát.

**Kết quả mong đợi**

- Trang fallback không được chấp nhận là giao diện sẵn sàng.
- Readiness yêu cầu đồng thời Home, Settings và asset hợp lệ.
- Không in thông báo hoàn tất.
- Trả mã build hoặc readiness phù hợp.

**Acceptance criteria**

- Đạt AC-05 và AC-09.

---

### ST-E2E-027 — Hủy bằng Ctrl+C và chạy lại

**Điều kiện**

- Installer đang ở bước tải, dependency hoặc build.
- Có thể gửi Ctrl+C.

**Dữ liệu**

- Lệnh cài chuẩn.

**Thao tác**

1. Khởi động installer.
2. Gửi Ctrl+C trong một công đoạn đang chạy.
3. Ghi output, mã thoát và trạng thái tiến trình.
4. Kiểm tra cấu hình hoặc bản cài có trước.
5. Chạy lại installer tới khi hoàn tất.

**Kết quả mong đợi**

- Output dùng trạng thái `[HUY]`, chỉ rõ công đoạn dở dang.
- Trả mã `130` khi hệ điều hành cho phép bắt sự kiện hủy.
- Không xóa hoặc ghi đè cấu hình có trước.
- Không để daemon không nhận diện được.
- Lần chạy lại kiểm tra artifact thực tế và phục hồi an toàn.

**Acceptance criteria**

- Đạt AC-04, AC-09, AC-13 và AC-15.

---

### ST-E2E-028 — Không lộ bí mật trong terminal và log

**Điều kiện**

- Có bản cài với API key kiểm thử duy nhất, dễ nhận diện.
- Có lifecycle token.
- Có thể chạy lại, status, stop, start và tạo một lỗi có log.

**Dữ liệu**

- API key kiểm thử.
- Lifecycle token.
- Nội dung bí mật trong `.env`.

**Thao tác**

1. Chạy lại installer.
2. Chạy status, stop, start và restart.
3. Gây một lỗi readiness hoặc cấu hình.
4. Tìm giá trị bí mật trong terminal, log installer, log server và metadata.
5. Kiểm tra URL và browser storage liên quan.

**Kết quả mong đợi**

- Không có API key hoặc lifecycle token ở terminal, log, URL hay metadata không bảo mật.
- Output chỉ hiển thị trạng thái “đã cấu hình” khi cần.
- Trường API key để trống không tự xóa key đã lưu.
- Lifecycle token vẫn được dùng nội bộ để xác minh.

**Acceptance criteria**

- Đạt AC-04, AC-12 và AC-18.

---

### ST-E2E-029 — Tự mở trình duyệt thất bại không làm cài đặt thất bại

**Điều kiện**

- Cài đặt chạy với tùy chọn mở trình duyệt.
- Mô phỏng không có browser mặc định hoặc lệnh mở browser thất bại.

**Dữ liệu**

- Bash: `--open`.
- PowerShell: `-Open`.

**Thao tác**

1. Chạy installer với tùy chọn mở browser.
2. Làm thao tác mở browser thất bại.
3. Ghi mã thoát và output.
4. Mở thủ công URL được in.

**Kết quả mong đợi**

- Installer vẫn trả mã `0` nếu HTTP readiness đã đạt.
- Output thông báo không thể tự mở browser và cung cấp URL để mở thủ công.
- Server tiếp tục chạy.
- URL thủ công truy cập được.

**Acceptance criteria**

- Đạt AC-05, AC-06 và AC-15.

---

### ST-E2E-030 — Chế độ không TTY và output chuyển hướng vào file

**Điều kiện**

- Có thể chạy installer trong CI hoặc shell không có TTY.
- Output được chuyển hướng vào file.
- Không có quyết định bắt buộc cần người dùng chọn.

**Dữ liệu**

- `--non-interactive` hoặc `-NonInteractive`.
- Thư mục, cổng và các giá trị cần thiết được truyền rõ ràng.

**Thao tác**

1. Chạy installer không có TTY và chuyển output vào file.
2. Theo dõi thời gian để phát hiện treo.
3. Mở file output sau khi hoàn tất.
4. Truy cập URL được ghi.

**Kết quả mong đợi**

- Installer không đọc lựa chọn từ stdin chứa script.
- Không treo chờ nhập.
- Không có animation, mã màu hoặc thao tác ghi đè dòng trong file.
- Trạng thái `[OK]`, `[DANG]`, `[CHO]`, `[GIU]`, `[CAN]`, `[LOI]` hoặc `[HUY]` vẫn đọc được.
- URL và lệnh quản lý giữ nguyên để sao chép.
- Cài đặt hoàn tất hoặc dừng rõ ràng khi cần quyết định bắt buộc.

**Acceptance criteria**

- Đạt AC-14, AC-15 và AC-20.

---

### ST-E2E-031 — Môi trường ngoài ma trận hỗ trợ

**Điều kiện**

- Máy hoặc VM thuộc một cấu hình chưa cam kết, ví dụ Windows ARM64, Linux ARM64 hoặc Linux musl.

**Dữ liệu**

- Lệnh cài tương ứng hệ điều hành.

**Thao tác**

1. Chạy installer.
2. Ghi thông tin môi trường được phát hiện.
3. Ghi mã thoát và thay đổi filesystem.

**Kết quả mong đợi**

- Installer dừng sớm.
- Hiển thị rõ OS, kiến trúc và lý do chưa hỗ trợ.
- Không tuyên bố môi trường được hỗ trợ.
- Không tạo bản cài dở dang hoặc daemon.
- Trả mã môi trường không hỗ trợ, dự kiến `2`.

**Acceptance criteria**

- Đạt AC-02, AC-09 và AC-15.

---

### ST-E2E-032 — Tài liệu cài đặt và xử lý sự cố có thể thực hiện được

**Điều kiện**

- README và tài liệu cài đặt của revision cần nghiệm thu đã hoàn chỉnh.
- Có một bản cài thành công trên mỗi nhóm Windows, Linux và macOS.

**Dữ liệu**

- Lệnh cài mới.
- Lệnh chạy lại.
- Start, status, stop, restart.
- Hướng dẫn cổng bị chiếm, thiếu quyền, lỗi mạng và không có LAN.

**Thao tác**

1. Thực hiện cài mới chỉ theo tài liệu.
2. Thực hiện chạy lại.
3. Thực hiện start, status, stop và restart.
4. Làm theo hướng dẫn xử lý một lỗi mạng và một lỗi cổng.
5. Kiểm tra hướng dẫn cấu hình Models và Android.

**Kết quả mong đợi**

- Lệnh trong tài liệu chạy được khi sao chép nguyên văn.
- Tài liệu nêu đúng shell, ma trận hỗ trợ, thư mục, cổng và hành vi chạy lại.
- Có hướng dẫn dùng `pipefail` cho Bash.
- Có hướng dẫn local/LAN, firewall và ý nghĩa “IP đã phát hiện nhưng chưa xác minh”.
- Có hướng dẫn mở Settings khi thiếu API key hoặc Android.
- Không có placeholder hoặc lệnh dùng đường dẫn/cổng sai.

**Acceptance criteria**

- Đạt AC-01, AC-08, AC-11, AC-14, AC-15 và AC-19.

## 6. Bằng chứng cần lưu khi thực thi

Mỗi lần chạy test case phải lưu:

- ID test case và mã môi trường.
- Ngày giờ, OS, kiến trúc và shell.
- Revision source thực tế.
- Phiên bản Python, uv, Node.js và npm sau cài đặt.
- Lệnh đã chạy, đã che dữ liệu bí mật.
- Toàn bộ output installer và mã thoát.
- Đường dẫn cài đặt và log.
- Ảnh hoặc bản ghi HTTP của Home, Settings và frontend asset.
- PID/trạng thái daemon trước và sau chạy lại.
- Hash cấu hình và dữ liệu trước/sau đối với test bảo toàn.
- Danh sách URL được in.
- Bằng chứng truy cập LAN từ thiết bị thứ hai.
- Bằng chứng API lifecycle vẫn bị giới hạn local.
- Kết quả cuối: `ĐẠT`, `CHƯA ĐẠT` hoặc `BLOCKED`.
- Lý do và liên kết tới artifact tương ứng.

## 7. Quy tắc kết luận

- **ĐẠT:** Tất cả bước hoàn tất và toàn bộ acceptance criteria của test case được đáp ứng.
- **CHƯA ĐẠT:** Có ít nhất một kết quả thực tế khác kết quả mong đợi.
- **BLOCKED:** Không thể thực hiện do thiếu môi trường, installer chưa được phát hành, URL public chưa tồn tại hoặc phụ thuộc ngoài phạm vi không khả dụng.
- Không kết luận ĐẠT chỉ từ kiểm tra source, TCP mở, HTTP 200 đơn lẻ hoặc việc tiến trình tồn tại.
- Ticket chỉ đủ điều kiện kết luận **ĐẠT** khi toàn bộ ma trận bắt buộc và các test case ưu tiên nghiệm thu đã ĐẠT, không còn lỗi làm mất cấu hình, lộ bí mật, báo readiness giả hoặc ngăn truy cập local/LAN theo phạm vi công bố.