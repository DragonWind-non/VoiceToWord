# VoiceToWord 🎙️⚡

Công cụ Desktop chạy ngầm trên Windows chuyển giọng nói thành văn bản siêu tốc bằng **Groq Whisper API**, kích hoạt qua phím tắt nhấn-giữ (**Right Ctrl**), tự động hiển thị badge thông báo nổi không cướp focus và dán thẳng vào con trỏ **PowerShell, CMD, Windows Terminal, VS Code,...**

---

## 🚀 Tính năng nổi bật

- **Nhận diện qua Groq Cloud:** Dùng `whisper-large-v3-turbo`; thời gian phản hồi phụ thuộc thời lượng ghi âm, mạng và tải dịch vụ, không cam kết dưới 0,5 giây.
- **Không lưu bản ghi âm xuống đĩa:** Âm thanh được tạo thành WAV trong RAM; RAM/CPU khi chạy nền phụ thuộc môi trường và chưa được đo.
- **Push-to-Talk (Nhấn giữ để nói):** Bấm giữ phím `Right Ctrl` (Ctrl bên phải) để thu âm, buông phím là chữ tự động điền vào màn hình.
- **Không cướp tiêu điểm (Focus):** Badge overlay hiển thị ở cạnh dưới màn hình sử dụng thuộc tính Windows `WS_EX_NOACTIVATE`, không làm mất con trỏ chuột/dòng lệnh bạn đang gõ.
- **Tự động làm sạch lệnh CLI:** Tự động loại bỏ dấu chấm câu thừa nếu bạn đọc các câu lệnh lập trình (như `git status`, `docker ps`, `npm run dev`).
- **Không thay đổi Clipboard:** Gõ Unicode trực tiếp vào cửa sổ đang hoạt động; phím tắt `Right Ctrl` cũng được ứng dụng đích nhận như phím Ctrl thông thường.
- **Nhập tiếng Việt trong Notepad:** Chèn trực tiếp tại con trỏ hoặc thay vùng chọn của control Edit/RichEdit để tránh lỗi Unicode đã tái hiện; các cửa sổ khác tiếp tục dùng `SendInput`.
- **Hỗ trợ khay hệ thống (System Tray):** Biểu tượng nằm gọn ở góc đồng hồ Windows, cho phép kiểm tra trạng thái hoặc thoát app nhanh chóng bằng chuột phải.

---

## 🛠️ Cài đặt & Chuẩn bị

### 1. Lấy Groq API Key (Miễn phí 100%)
1. Truy cập [https://console.groq.com/keys](https://console.groq.com/keys) và đăng nhập bằng tài khoản Google/GitHub.
2. Bấm **Create API Key**, đặt tên bất kỳ và copy mã khóa (dạng `gsk_...`).

### 2. Cấu hình file `.env`
Tạo file `.env` từ file mẫu `.env.example` (PowerShell):
```powershell
Copy-Item .env.example .env
```
Mở `.env` và dán key của bạn vào:
```env
GROQ_API_KEY=test-key
```

---

## 💻 Cách sử dụng

Cài Python 3.10+ và các thư viện bằng `python -m pip install -r requirements.txt`.
Không gửi API key cho người khác; âm thanh sẽ được gửi qua mạng đến Groq để phiên âm.

Để dùng môi trường riêng trên PowerShell:
```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe run.py
```
Nếu `.venv` đã được chuẩn bị, chỉ cần lệnh cuối. Bản sửa trong mã Python không tự cập nhật các file `.exe` cũ trong `dist`; hãy thoát bản cũ qua tray trước khi thử bản Python.

### Cách 1: Chạy trực tiếp qua Python
- **Chế độ có cửa sổ hiển thị log:**
  ```bash
  .\.venv\Scripts\python.exe run.py
  ```
- **Chế độ chạy ngầm hoàn toàn (không hiện cửa sổ đen):**
  ```bash
  .\.venv\Scripts\pythonw.exe run.py
  ```

### Cách 2: Đóng gói thành file `VoiceToWord.exe` độc lập
Bạn có thể đóng gói toàn bộ app thành một file `.exe` duy nhất (không cần cài Python khi mang sang máy khác):
```bash
pip install pyinstaller
pyinstaller --noconsole --onefile --name VoiceToWord run.py
```
File thực thi sẽ nằm tại `dist/VoiceToWord.exe`. Đặt file `.env` **cạnh file `.exe`** (ứng dụng không tự nhúng API key). Bạn có thể tạo lối tắt của `.exe` trong `shell:startup` nếu muốn tự khởi động. Chưa xác nhận bản build `.exe` trên máy này.

---

## ⌨️ Thao tác
1. Mở bất kỳ cửa sổ nào bạn muốn nhập văn bản (PowerShell, CMD, VS Code, Chat,...).
2. **Bấm và giữ** phím `Right Ctrl` (Ctrl bên phải bàn phím).
3. Biểu tượng **🔴 Đang nghe...** sẽ xuất hiện ở cạnh dưới màn hình.
4. Nói câu bạn muốn nhập (tiếng Việt hoặc tiếng Anh).
5. **Buông phím `Right Ctrl`**: Biểu tượng chuyển sang **⏳ Đang nhận diện...**, sau đó ứng dụng gõ kết quả tại vị trí con trỏ đang hoạt động. Hãy giữ focus ở cửa sổ cần nhập trong khi đợi API phản hồi; ứng dụng không tự nhấn Enter để chạy lệnh.

Cửa sổ PowerShell/CMD chạy quyền Administrator có thể chặn thao tác nhập từ ứng dụng chạy quyền thông thường (UIPI); chỉ chạy VoiceToWord với cùng quyền nếu thực sự cần. Chưa kiểm chứng đường đi này trên máy hiện tại.

### Khi nhận diện sai hoặc xuất hiện câu không nói

- Đợi chỉ báo **Đang nghe** xuất hiện rồi mới nói, và giữ focus ở cửa sổ cần nhập đến khi xử lý xong.
- App bỏ bản thu dưới `MIN_DURATION_SECONDS` và bản thu có dưới 100 ms vượt `SILENCE_THRESHOLD_DBFS` trước khi gọi Groq. Mức mặc định `-60` dBFS là điểm bắt đầu; thử cả im lặng và giọng nhỏ trên micro thật trước khi chỉnh. Bộ lọc năng lượng không phân biệt chắc chắn tiếng nói với nhạc hoặc nhiễu lớn.
- App yêu cầu `verbose_json` và bỏ đoạn mà Whisper đánh giá đồng thời có xác suất không có lời nói cao (`no_speech_prob > 0.6`) và độ tin cậy thấp (`avg_logprob < -1.0`). Không có danh sách cấm câu “subscribe”; nội dung được nói thật vẫn được giữ. Xem [quy tắc im lặng của Whisper](https://github.com/openai/whisper/blob/main/whisper/transcribe.py).
- Dùng `LANGUAGE=vi` cho tiếng Việt, `en` để đối chiếu tiếng Anh, hoặc `auto` để không ép ngôn ngữ. Khởi động lại app sau khi sửa `.env`.
- Để xác định lỗi ở Groq, làm sạch hay nhập chữ, đặt `DEBUG_TRANSCRIPT=1` trong `.env`, chạy bản có console và đối chiếu `GROQ_RAW`, `CLEANED`, `INJECTOR_INPUT`, `INJECTOR_FINAL`. Đây là nội dung giọng nói: chỉ dùng câu mẫu không riêng tư, không chia sẻ log chứa thông tin nhạy cảm, và tắt lại khi thử xong. Mặc định app không ghi transcript/bản thu xuống đĩa và không hiển thị key trong lỗi API.
- Lỗi kết nối/timeout không tự gửi lại; app báo lỗi và cho phép thu lượt mới. Lỗi micro/overflow yêu cầu thu lại. Chỉ mở một phiên: bản Python hiện có guard chặn mở trùng, nhưng exe cũ chưa có guard này nên vẫn cần thoát thủ công.

---

## 🧪 Chạy Kiểm thử (Tests)
Chạy các kiểm thử đơn vị và tích hợp:
```bash
.\.venv\Scripts\python.exe -m pytest -v
```

Test `test_injector_types_vietnamese_into_real_text_window` mở cửa sổ riêng và gửi phím thật. Cần desktop đang hoạt động; không chạy lúc đang kiểm thử micro bằng một phiên app khác. Để chạy phần còn lại:
```powershell
.\.venv\Scripts\python.exe -m pytest -q -k "not types_vietnamese_into_real_text_window"
```

Kết quả kiểm chứng và giới hạn: [báo cáo ngày 24/10/2026](docs/2026-10-24-stability-check.md). Bản thử `dist/VoiceToWord-test-2026-10-24.exe` đã được đóng gói và kiểm tra khởi động; hai `.exe` cũ chưa chứa bản sửa này.
