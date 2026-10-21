# VoiceToWord Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Xây dựng công cụ chạy ngầm trên Windows giúp chuyển giọng nói thành văn bản siêu tốc bằng phím tắt nhấn-giữ (Right Ctrl), nhận diện tiếng Việt và thuật ngữ lập trình qua Groq Whisper API, hiển thị icon trạng thái nổi ở cạnh dưới màn hình không chiếm focus, và dán trực tiếp vào con trỏ terminal.

**Architecture:** Ứng dụng gồm các module tách biệt: `hotkey_listener` bắt sự kiện nhấn/nhả `Right Ctrl`, điều phối `audio_recorder` thu âm trực tiếp vào bộ nhớ RAM (`io.BytesIO`), kích hoạt `overlay` hiển thị trạng thái động không cướp tiêu điểm (dùng cờ `WS_EX_NOACTIVATE`), gửi audio tới `transcriber` (Groq API) và chuyển kết quả cho `injector` để dán an toàn vào cửa sổ terminal hiện hành đồng thời phục hồi clipboard cũ.

**Tech Stack:** Python 3.10+, `sounddevice`, `numpy`, `scipy`, `pynput`, `groq`, `tkinter` / Win32 API (`ctypes`), `python-dotenv`.

**Spec:** `docs/superpowers/specs/2026-10-22-voice-to-word-design.md`

## Global Constraints

- Chạy trên hệ điều hành Windows 10/11 (64-bit).
- Độ trễ phản hồi từ khi nhả phím đến khi chữ xuất hiện < 0.5s.
- Không ghi file âm thanh tạm ra ổ cứng; toàn bộ âm thanh xử lý trực tiếp trong RAM buffer (`io.BytesIO`).
- Phím kích hoạt mặc định: `Right Ctrl`.
- Tuyệt đối không cướp focus cửa sổ terminal đang hoạt động khi hiển thị overlay.
- Tự động lưu và khôi phục nội dung Clipboard của người dùng sau khi dán văn bản.

## Review Focus

1. **Vô tình chạm phím Right Ctrl trong thời gian cực ngắn (<0.3s):** App phải hủy thu âm không gửi API để tránh tốn request và tránh dán chuỗi rỗng.
2. **Mất kết nối mạng hoặc lỗi Groq API Key:** App không được crash, báo trạng thái lỗi trên overlay trong 1 giây rồi tự ẩn.
3. **Terminal chạy quyền Administrator:** Khuyến nghị và hướng dẫn khởi chạy tool với quyền tương ứng để tránh bị Windows UIPI chặn mô phỏng phím `Ctrl+V`.
4. **Chuẩn hóa lệnh CLI:** Loại bỏ dấu chấm cuối câu (`.`) nếu nội dung phiên âm là câu lệnh dòng lệnh phổ biến.
5. **Ký tự đặc biệt và dấu tiếng Việt:** Đảm bảo clipboard xử lý chuẩn UTF-8 không bị lỗi font khi dán vào PowerShell/CMD.

---

### Task 1: Khởi tạo dự án, Git & Module Cấu hình (Config)

**Files:**
- Create: `requirements.txt`
- Create: `.env.example`
- Create: `src/config.py`
- Create: `CLAUDE.md`
- Test: `tests/test_config.py`

**Interfaces:**
- Produces: `Config` dataclass hoặc object cung cấp:
  - `groq_api_key: str`
  - `model_name: str` (mặc định `"whisper-large-v3-turbo"`)
  - `sample_rate: int` (mặc định `16000`)
  - `min_duration: float` (mặc định `0.3` giây)
  - `language: str` (mặc định `"vi"`)

- [ ] **Step 1: Khởi tạo Git repository và file CLAUDE.md theo tiêu chuẩn**
- [ ] **Step 2: Viết failing test cho `test_config.py` kiểm tra load cấu hình từ env**
- [ ] **Step 3: Chạy test để xác nhận FAIL**
- [ ] **Step 4: Cài đặt `requirements.txt`, `.env.example` và cài đặt `src/config.py`**
- [ ] **Step 5: Chạy test để xác nhận PASS**
- [ ] **Step 6: Commit code**

---

### Task 2: Module Thu Âm Trong Bộ Nhớ (Audio Recorder)

**Files:**
- Create: `src/audio_recorder.py`
- Test: `tests/test_audio_recorder.py`

**Interfaces:**
- Consumes: `Config` (sample_rate, channels)
- Produces:
  - `AudioRecorder.start()`: Bắt đầu thu âm luồng âm thanh từ microphone vào RAM buffer.
  - `AudioRecorder.stop() -> Tuple[io.BytesIO, float]`: Dừng thu và trả về stream WAV trong RAM cùng thời lượng (duration tính bằng giây).

- [ ] **Step 1: Viết failing test cho AudioRecorder (test ghi âm giả lập dữ liệu numpy và xuất ra buffer WAV hợp lệ)**
- [ ] **Step 2: Chạy test để xác nhận FAIL**
- [ ] **Step 3: Triển khai `src/audio_recorder.py` dùng `sounddevice` và `scipy.io.wavfile` hoặc `wave` module chuẩn**
- [ ] **Step 4: Chạy test để xác nhận PASS**
- [ ] **Step 5: Commit code**

---

### Task 3: Module Phiên Âm Groq Whisper & Chuẩn Hóa Lệnh (Transcriber)

**Files:**
- Create: `src/transcriber.py`
- Test: `tests/test_transcriber.py`

**Interfaces:**
- Consumes: `Config`, `io.BytesIO` từ `AudioRecorder`
- Produces:
  - `Transcriber.transcribe(audio_buffer: io.BytesIO) -> str`: Gửi buffer lên Groq Whisper API và trả về chuỗi văn bản đã được làm sạch (loại bỏ dấu chấm cuối câu nếu là lệnh CLI).

- [ ] **Step 1: Viết failing test cho `Transcriber` (mock client Groq, kiểm tra post-processing loại bỏ trailing period cho lệnh code/CLI)**
- [ ] **Step 2: Chạy test để xác nhận FAIL**
- [ ] **Step 3: Triển khai `src/transcriber.py` sử dụng thư viện `groq` SDK hoặc `httpx`**
- [ ] **Step 4: Chạy test để xác nhận PASS**
- [ ] **Step 5: Commit code**

---

### Task 4: Module Dán Văn Bản An Toàn Vào Con Trỏ (Injector)

**Files:**
- Create: `src/injector.py`
- Test: `tests/test_injector.py`

**Interfaces:**
- Consumes: `text: str`
- Produces:
  - `TextInjector.paste_text(text: str)`: Lưu clipboard hiện tại, nạp text mới vào clipboard, mô phỏng nhấn phím `Ctrl+V` (hoặc `Shift+Insert`), sau đó khôi phục lại clipboard cũ.

- [ ] **Step 1: Viết failing test kiểm tra logic lưu và khôi phục clipboard**
- [ ] **Step 2: Chạy test để xác nhận FAIL**
- [ ] **Step 3: Triển khai `src/injector.py` với Win32 SendInput / ctypes hoặc `pynput.keyboard.Controller`**
- [ ] **Step 4: Chạy test để xác nhận PASS**
- [ ] **Step 5: Commit code**

---

### Task 5: Widget Icon Ghi Âm Nổi Không Cướp Focus (Overlay)

**Files:**
- Create: `src/overlay.py`
- Test: `tests/test_overlay.py`

**Interfaces:**
- Produces:
  - `OverlayIndicator.show_recording()`: Hiển thị icon/pill màu đỏ nhấp nháy "Đang nghe...".
  - `OverlayIndicator.show_processing()`: Chuyển sang màu vàng/xanh "Đang xử lý...".
  - `OverlayIndicator.show_error(msg: str)`: Hiển thị lỗi trong 1 giây.
  - `OverlayIndicator.hide()`: Ẩn overlay.

- [ ] **Step 1: Viết test kiểm tra trạng thái và logic hiển thị của Overlay**
- [ ] **Step 2: Chạy test để xác nhận FAIL**
- [ ] **Step 3: Triển khai `src/overlay.py` dùng `tkinter` với thuộc tính Windows `WS_EX_NOACTIVATE | WS_EX_TOOLWINDOW` để đảm bảo 100% không cướp focus của terminal**
- [ ] **Step 4: Chạy test để xác nhận PASS**
- [ ] **Step 5: Commit code**

---

### Task 6: Module Lắng Nghe Phím Tắt Toàn Cục (Hotkey Listener)

**Files:**
- Create: `src/hotkey_listener.py`
- Test: `tests/test_hotkey_listener.py`

**Interfaces:**
- Consumes: callbacks `on_press()`, `on_release()`
- Produces:
  - `HotkeyListener.start()`: Khởi chạy thread lắng nghe phím `Right Ctrl`.
  - `HotkeyListener.stop()`: Dừng listener an toàn.

- [ ] **Step 1: Viết failing test cho `HotkeyListener` kiểm tra gọi đúng callback khi nhấn và nhả phím**
- [ ] **Step 2: Chạy test để xác nhận FAIL**
- [ ] **Step 3: Triển khai `src/hotkey_listener.py` dùng `pynput.keyboard`**
- [ ] **Step 4: Chạy test để xác nhận PASS**
- [ ] **Step 5: Commit code**

---

### Task 7: Tích Hợp Điều Phối Toàn Bộ Ứng Dụng (Main App & E2E)

**Files:**
- Create: `src/main.py`
- Create: `run.py`
- Test: `tests/test_integration.py`

**Interfaces:**
- Điều phối toàn bộ luồng:
  `Right Ctrl Press` -> `overlay.show_recording()` + `recorder.start()`
  `Right Ctrl Release` -> `duration, audio = recorder.stop()` -> (nếu duration >= 0.3s: `overlay.show_processing()` -> `text = transcriber.transcribe(audio)` -> `injector.paste_text(text)`) -> `overlay.hide()`

- [ ] **Step 1: Viết integration test giả lập toàn bộ vòng đời từ phím bấm -> ghi âm -> phiên âm -> dán chữ**
- [ ] **Step 2: Chạy test để xác nhận FAIL**
- [ ] **Step 3: Triển khai `src/main.py` kết nối các module với nhau chạy đa luồng an toàn**
- [ ] **Step 4: Chạy test để xác nhận PASS**
- [ ] **Step 5: Tạo script chạy nhanh `run.py` và hướng dẫn chạy ngầm**
- [ ] **Step 6: Commit code và cập nhật `CLAUDE.md`**
