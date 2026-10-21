# VoiceToWord 🎙️⚡

Công cụ Desktop chạy ngầm trên Windows chuyển giọng nói thành văn bản siêu tốc bằng **Groq Whisper API**, kích hoạt qua phím tắt nhấn-giữ (**Right Ctrl**), tự động hiển thị badge thông báo nổi không cướp focus và dán thẳng vào con trỏ **PowerShell, CMD, Windows Terminal, VS Code,...**

---

## 🚀 Tính năng nổi bật

- **Tốc độ phản hồi cực nhanh (<0.5 giây):** Sử dụng chip LPU của Groq Cloud (`whisper-large-v3-turbo`) cho kết quả gần như tức thì khi dứt lời.
- **Tiết kiệm tài nguyên tuyệt đối:** Xử lý âm thanh trực tiếp trong RAM (`io.BytesIO`), không ghi file rác I/O ra ổ cứng. Chiếm < 40MB RAM và ~0% CPU khi chạy nền.
- **Push-to-Talk (Nhấn giữ để nói):** Bấm giữ phím `Right Ctrl` (Ctrl bên phải) để thu âm, buông phím là chữ tự động điền vào màn hình.
- **Không cướp tiêu điểm (Focus):** Badge overlay hiển thị ở cạnh dưới màn hình sử dụng thuộc tính Windows `WS_EX_NOACTIVATE`, không làm mất con trỏ chuột/dòng lệnh bạn đang gõ.
- **Tự động làm sạch lệnh CLI:** Tự động loại bỏ dấu chấm câu thừa nếu bạn đọc các câu lệnh lập trình (như `git status`, `docker ps`, `npm run dev`).
- **Bảo toàn Clipboard:** Tự động lưu trữ nội dung clipboard cũ của bạn và phục hồi lại ngay sau khi dán chữ xong.
- **Hỗ trợ khay hệ thống (System Tray):** Biểu tượng nằm gọn ở góc đồng hồ Windows, cho phép kiểm tra trạng thái hoặc thoát app nhanh chóng bằng chuột phải.

---

## 🛠️ Cài đặt & Chuẩn bị

### 1. Lấy Groq API Key (Miễn phí 100%)
1. Truy cập [https://console.groq.com/keys](https://console.groq.com/keys) và đăng nhập bằng tài khoản Google/GitHub.
2. Bấm **Create API Key**, đặt tên bất kỳ và copy mã khóa (dạng `gsk_...`).

### 2. Cấu hình file `.env`
Tạo file `.env` từ file mẫu `.env.example`:
```bash
cp .env.example .env
```
Mở `.env` và dán key của bạn vào:
```env
GROQ_API_KEY=test-key
```

---

## 💻 Cách sử dụng

### Cách 1: Chạy trực tiếp qua Python
- **Chế độ có cửa sổ hiển thị log:**
  ```bash
  python run.py
  ```
- **Chế độ chạy ngầm hoàn toàn (không hiện cửa sổ đen):**
  ```bash
  pythonw run.py
  ```

### Cách 2: Đóng gói thành file `VoiceToWord.exe` độc lập
Bạn có thể đóng gói toàn bộ app thành một file `.exe` duy nhất (không cần cài Python khi mang sang máy khác):
```bash
pip install pyinstaller
pyinstaller --noconsole --onefile --name VoiceToWord run.py
```
File thực thi sẽ nằm tại thư mục `dist/VoiceToWord.exe`. Bạn chỉ cần bấm đúp chuột để chạy hoặc copy vào thư mục `Startup` (`Win + R` -> gõ `shell:startup`) để tự khởi động cùng Windows!

---

## ⌨️ Thao tác
1. Mở bất kỳ cửa sổ nào bạn muốn nhập văn bản (PowerShell, CMD, VS Code, Chat,...).
2. **Bấm và giữ** phím `Right Ctrl` (Ctrl bên phải bàn phím).
3. Biểu tượng **🔴 Đang nghe...** sẽ xuất hiện ở cạnh dưới màn hình.
4. Nói câu bạn muốn nhập (tiếng Việt hoặc tiếng Anh).
5. **Buông phím `Right Ctrl`**: Biểu tượng chuyển sang **⏳ Đang nhận diện...** và văn bản sẽ lập tức được dán ngay vào vị trí con trỏ!

---

## 🧪 Chạy Kiểm thử (Tests)
Toàn bộ mã nguồn được xây dựng theo chuẩn TDD với 20 unit & integration tests:
```bash
python -m pytest -v
```
