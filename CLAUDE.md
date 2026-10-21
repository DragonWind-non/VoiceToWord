# VoiceToWord - Speech to Text Utility for Windows & Terminal

Công cụ chạy ngầm trên Windows chuyển giọng nói thành văn bản siêu tốc bằng Groq Whisper API, kích hoạt qua phím tắt nhấn-giữ (Right Ctrl), hiển thị icon trạng thái nổi không cướp tiêu điểm và dán trực tiếp vào con trỏ CLI/PowerShell/CMD/IDE.

## Kiến trúc dự án
- `src/config.py`: Đọc cấu hình từ `.env` (Groq API Key, hotkey, language, audio settings).
- `src/audio_recorder.py`: Thu âm micro trực tiếp vào bộ nhớ RAM (`io.BytesIO`), không tạo file rác ra đĩa.
- `src/transcriber.py`: Gửi audio stream tới Groq Whisper Cloud API (`whisper-large-v3-turbo`), tự động chuẩn hóa chuỗi lệnh CLI.
- `src/injector.py`: Nhập văn bản an toàn vào cửa sổ hiện hành qua Clipboard kèm cơ chế tự khôi phục nội dung cũ và mô phỏng phím `Ctrl+V`.
- `src/overlay.py`: Hiển thị icon/pill trạng thái ghi âm nổi ở cạnh dưới màn hình với cờ Win32 `WS_EX_NOACTIVATE` để không cướp focus.
- `src/tray.py`: Quản lý icon ở System Tray (khay hệ thống) cạnh đồng hồ để bật/tắt hoặc thoát app.
- `src/hotkey_listener.py`: Lắng nghe sự kiện nhấn/nhả `Right Ctrl` toàn cục không làm ảnh hưởng phím khác.
- `src/main.py`: Điểm kết nối điều phối toàn bộ các thành phần.
- `run.py`: Script khởi chạy nhanh không hiện màn hình console đen (hoặc đóng gói `.exe`).

## Lệnh thực thi & Kiểm thử
- Chạy toàn bộ test: `pytest`
- Chạy từng test: `pytest tests/test_config.py -v`
- Khởi chạy app ở chế độ phát triển: `python run.py`
- Cấu hình: Tạo file `.env` từ `.env.example` và điền `GROQ_API_KEY`.
