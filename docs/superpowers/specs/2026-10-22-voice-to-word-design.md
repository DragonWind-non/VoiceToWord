# VoiceToWord - Thiết kế Công cụ Gõ Giọng Nói Tốc Độ Cao Cho Terminal & Windows

- **Ngày tạo:** 2026-10-22
- **Trạng thái:** Chờ duyệt (Design Review)
- **Tác giả:** Antigravity / Claude Code & Đối tác người dùng

---

## 1. Mục đích và Lý do (Intent & The Why)

Khi lập trình viên hoặc kỹ sư hệ thống làm việc liên tục trong môi trường dòng lệnh (PowerShell, CMD, Windows Terminal, Git Bash, WSL, VS Code), việc gõ các câu lệnh dài, commit message, tài liệu hoặc ghi chú bằng bàn phím mất nhiều thời gian và gây ngắt quãng mạch suy nghĩ. 

Mục tiêu của dự án là xây dựng một công cụ ngầm (background utility) siêu nhẹ, tiết kiệm tài nguyên, độ trễ cực thấp (ultra-low latency), cho phép người dùng bấm giữ một phím để nói và nhả ra là văn bản lập tức được dán thẳng vào vị trí con trỏ dòng lệnh ở bất kỳ ứng dụng nào đang làm việc.

---

## 2. Mục tiêu, Phi mục tiêu và Điều chống lại (Goals, Non-Goals, Anti-Goals)

### Mục tiêu (Goals)
1. **Phản hồi siêu tốc (<0.5 giây):** Từ lúc nhả phím cho đến khi chữ xuất hiện trên màn hình phải diễn ra gần như tức thì.
2. **Tiết kiệm tài nguyên tuyệt đối:** 
   - Ứng dụng chạy nền ở trạng thái nghỉ chiếm ~0% CPU và < 50MB RAM.
   - Xử lý âm thanh trực tiếp trong bộ nhớ (in-memory buffer qua RAM), không ghi file tạm I/O ra ổ cứng để tăng tốc độ và bảo vệ tuổi thọ ổ SSD/bảo mật.
3. **Thao tác tự nhiên (Push-to-Talk):**
   - Phím kích hoạt: `Right Ctrl` (Ctrl bên phải).
   - Nhấn giữ: Bắt đầu thu âm micro.
   - Nhả phím: Ngừng thu, gửi dữ liệu âm thanh đến Groq API, chèn văn bản vào cửa sổ hiện tại.
4. **Chỉ báo trực quan (Visual Indicator):**
   - Một icon/thanh thông báo nhỏ dạng overlay nổi ở giữa cạnh dưới màn hình, trong suốt, tinh tế.
   - Hiển thị hiệu ứng trạng thái: "Đang nghe..." (khi giữ phím) -> "Đang xử lý..." (khi gửi API) -> Tự động biến mất ngay khi văn bản đã dán xong.
   - Đảm bảo **không chiếm tiêu điểm (Focus)** của cửa sổ terminal đang mở.
5. **Độ chính xác cao cho Tiếng Việt & Code:**
   - Sử dụng Groq Whisper API (`whisper-large-v3-turbo`) xử lý mượt mà cả tiếng Việt có dấu và các từ khóa tiếng Anh/lập trình (vd: `git commit`, `docker`, `npm run build`).
6. **Bảo toàn Clipboard:** 
   - Khi dán văn bản vào terminal, tự động lưu lại nội dung clipboard trước đó của người dùng và phục hồi lại sau khi dán xong.

### Phi mục tiêu (Non-Goals)
- Không xây dựng giao diện cài đặt phức tạp hay đồ sộ (không dùng Electron/Web nặng nề).
- Không phục vụ ghi âm dài kỳ (như ghi âm cuộc họp 1-2 tiếng liên tục).
- Không cần quản lý lịch sử ghi âm cục bộ (ưu tiên tính riêng tư và nhẹ máy).

### Điều chống lại (Anti-Goals)
- **Không bao giờ cướp focus cửa sổ:** Khi icon ghi âm hiện lên ở dưới màn hình, con trỏ phím ở PowerShell/Terminal không được bị mất focus (tránh tình trạng dán chữ trượt ra ngoài).
- **Không gây xung đột phím:** Không làm ảnh hưởng đến phím `Ctrl trái` hoặc các tổ hợp `Ctrl+C`, `Ctrl+V` hay bộ gõ Unikey/EVKey.
- **Không treo máy khi mất mạng:** Nếu mất mạng hoặc Groq API trả về lỗi, app phải phát tín hiệu cảnh báo ngắn (nhấp nháy icon hoặc notification nhẹ) và quay về trạng thái bình thường mà không bị crash hay đơ hệ thống.

---

## 3. Ràng buộc kỹ thuật (Constraints)
- **Hệ điều hành:** Windows 10 / 11 (64-bit).
- **Dịch vụ STT (Speech-to-Text):** Groq Cloud API (mô hình `whisper-large-v3-turbo`). Yêu cầu có Groq API Key (cung cấp qua `GROQ_API_KEY` trong file cấu hình `.env`).
- **Phím bấm kích hoạt:** Mặc định `Right Ctrl`.

---

## 4. Các quyết định đã thống nhất với người dùng (Decided Decisions)
1. **Dùng Cloud API (Groq) thay vì Offline:** Để giữ cho ứng dụng nhẹ nhất có thể (~vài chục MB RAM, không ngốn GPU/CPU khi đang làm việc nặng).
2. **Chọn phím `Right Ctrl`:** Đảm bảo không xung đột với bất kỳ phím tắt phổ biến nào trong terminal và IDE.
3. **Cơ chế Push-to-Talk (Giữ để nói, buông để chèn):** Nhanh và chính xác nhất cho ngữ cảnh dòng lệnh.
4. **Icon ghi âm nổi ở cạnh dưới màn hình:** Báo hiệu người dùng đang thu âm mà không che khuất dòng lệnh đang gõ.

---

## 5. Phần dành cho kỹ sư triển khai (Left to Builder)
- **Ngôn ngữ triển khai:** Python (sử dụng thư viện `sounddevice` + `numpy` để ghi âm RAM buffer, `pynput` để hook bàn phím toàn cục mượt mà, `groq` SDK hoặc `httpx` gọi HTTP/2 siêu tốc, và `tkinter` / Win32 API tạo cửa sổ overlay WS_EX_NOACTIVATE | WS_EX_TOOLWINDOW không bao giờ cướp focus).
- **Cấu trúc dự án:**
  - `main.py`: Điểm khởi chạy app ngầm.
  - `audio_recorder.py`: Thu âm micro vào bộ nhớ (RAM BytesIO buffer).
  - `transcriber.py`: Gửi audio buffer lên Groq API qua `whisper-large-v3-turbo`, trả về text tiếng Việt/Anh chuẩn hóa.
  - `injector.py`: Nhập văn bản vào con trỏ hiện tại (dùng Windows SendInput hoặc Clipboard paste kèm restore).
  - `overlay.py`: Widget overlay ở cạnh dưới màn hình với phong cách tối giản (dark theme pill badge), sử dụng cờ Win32 để hoàn toàn không cướp focus.
  - `config.py` & `.env.example`: Lưu API key và tùy chọn phím tắt.
  - `CLAUDE.md`: Hướng dẫn vận hành và quy chuẩn dự án theo chuẩn repo.
