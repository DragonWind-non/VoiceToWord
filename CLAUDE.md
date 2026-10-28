# VoiceToWord - Speech to Text Utility for Windows & Terminal

Công cụ chạy ngầm trên Windows chuyển giọng nói thành văn bản siêu tốc bằng Groq Whisper API, kích hoạt qua phím tắt nhấn-giữ (Right Ctrl), hiển thị icon trạng thái nổi không cướp tiêu điểm và dán trực tiếp vào con trỏ CLI/PowerShell/CMD/IDE.

## Kiến trúc dự án
- `voicetoword/config.py`: Đọc cấu hình từ `.env` (Groq API Key, hotkey, language, audio settings).
- `voicetoword/audio_recorder.py`: Thu âm micro trực tiếp vào bộ nhớ RAM (`io.BytesIO`), không tạo file rác ra đĩa.
- `voicetoword/transcriber.py`: Gửi audio stream tới Groq Whisper Cloud API (`whisper-large-v3-turbo`), tự động chuẩn hóa chuỗi lệnh CLI.
- `voicetoword/injector.py`: Gõ Unicode trực tiếp vào cửa sổ hiện hành, không thay đổi clipboard.
- `voicetoword/overlay.py`: Hiển thị icon/pill trạng thái ghi âm nổi ở cạnh dưới màn hình với cờ Win32 `WS_EX_NOACTIVATE` để không cướp focus.
- `voicetoword/tray.py`: Quản lý icon ở System Tray (khay hệ thống) cạnh đồng hồ để bật/tắt hoặc thoát app.
- `voicetoword/hotkey_listener.py`: Lắng nghe sự kiện nhấn/nhả `Right Ctrl` toàn cục không làm ảnh hưởng phím khác.
- `voicetoword/app.py`: Điều phối các dịch vụ. `voicetoword/main.py`: Khởi động và chặn mở trùng.
- `run.py`: Script khởi chạy nhanh không hiện màn hình console đen (hoặc đóng gói `.exe`).

## Lệnh thực thi & Kiểm thử
- Chạy toàn bộ test: `python -m pytest`
- Chạy từng test: `python -m pytest tests/test_config.py -v`
- Khởi chạy app ở chế độ phát triển: `python run.py`
- Cấu hình: Tạo file `.env` từ `.env.example` và điền `GROQ_API_KEY`.
