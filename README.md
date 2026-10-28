# VoiceToWord

Ứng dụng Windows chuyển giọng nói thành văn bản qua **Groq Whisper**.
Giữ **Right Ctrl**, đợi chỉ báo **Đang nghe**, nói rồi nhả phím; kết quả được nhập vào cửa sổ đang có focus.

## Tải và chạy

Tải `VoiceToWord-1.0.0-win-x64.zip` tại [Releases](https://github.com/DragonWind-non/VoiceToWord/releases).
Giải nén, sao chép `.env.example` thành `.env` cạnh exe, rồi điền `GROQ_API_KEY` của riêng bạn.
Lấy khóa tại [Groq Console](https://console.groq.com/keys); hạn mức và giá theo tài khoản/dịch vụ của bạn.

Mở exe, chọn ô cần nhập, giữ Right Ctrl và đợi chỉ báo trước khi nói. Giữ focus ở cửa sổ đích trong khi
chờ xử lý. App không tự nhấn Enter để thực thi lệnh. Thoát bằng chuột phải icon micro ở khay hệ thống → **Thoát (Exit)**.
Chỉ mở một phiên và thoát phiên cũ trước khi cập nhật.

- Thu âm trong RAM; **âm thanh được gửi đến Groq qua HTTPS**, cần mạng và khóa hợp lệ.
- Overlay hiển thị trạng thái và không chủ động lấy focus.
- Gõ Unicode, không tự thay clipboard. Edit/RichEdit có kiểm tra read-only, giới hạn và vị trí con trỏ.
- Khi nhập thất bại: tray → **Xem kết quả chưa nhập** để tự lấy lại kết quả gần nhất còn trong RAM.
- Xóa dấu chấm cuối ở một số mẫu lệnh như `git status.` và `git --version.`; đây là heuristic,
  không phải parser hiểu mọi câu lệnh. Câu văn và dấu chấm có ý nghĩa được giữ theo các ca hồi quy.

Xem [hướng dẫn gói Windows](docs/USAGE.txt) và [quyền riêng tư](SECURITY.md).

## Chạy từ mã nguồn — PowerShell

Yêu cầu Windows x64, Python **3.12+** có Tkinter. Bản phát hành được xây và thử trên Python **3.14.7 x64**.
Các phiên bản Python khác trong dải yêu cầu chưa được xác minh riêng.

```powershell
git clone https://github.com/DragonWind-non/VoiceToWord.git
cd VoiceToWord
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
Copy-Item .env.example .env
notepad .env
.\.venv\Scripts\python.exe -m voicetoword
```

`python run.py` vẫn là điểm vào cho checkout và PyInstaller. Dùng `.venv/Scripts/pythonw.exe run.py`
để chạy không console. Với checkout, cấu hình đọc cạnh `run.py`; với exe, đọc cạnh exe.
Nếu cài package bằng pip, `.env` đọc từ thư mục làm việc. Biến môi trường có ưu tiên cao hơn `.env`.

## Cấu trúc

```text
voicetoword/        Package ứng dụng
  main.py          Khởi động, thông báo cấu hình, mutex chặn mở trùng
  app.py           Điều phối hotkey → audio → nhận diện → nhập chữ
  config.py        Cấu hình và kiểm tra giá trị
  audio_recorder.py / transcriber.py / injector.py
  hotkey_listener.py / overlay.py / tray.py
tests/             Unit, tích hợp giả lập SDK, native controls và GUI
scripts/release.py Đóng gói từ commit Git và kiểm tra archive
docs/              Hướng dẫn và bằng chứng phát hành
VoiceToWord.spec   Cấu hình PyInstaller được quản lý bằng Git
requirements.txt   Runtime và dependency gián tiếp đã ghim phiên bản
requirements-dev.txt / requirements-check.txt  Test/build và công cụ audit
```

## Kiểm thử và đóng gói

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt -r requirements-check.txt
.\.venv\Scripts\python.exe -m pytest -q -m "not desktop_input"
.\.venv\Scripts\python.exe -m ruff check voicetoword tests scripts run.py
.\.venv\Scripts\python.exe -m bandit -q -r voicetoword run.py
.\.venv\Scripts\python.exe -m pip_audit --no-deps --disable-pip -r requirements.txt -r requirements-dev.txt
.\.venv\Scripts\python.exe scripts/release.py
```

Script phát hành yêu cầu các thay đổi đã commit. Nguồn lấy bằng `git archive HEAD`, build trong thư mục tạm,
kiểm tra module ứng dụng trong exe khớp nguồn, kiểm tra runtime cần thiết và CRC của ZIP, rồi tạo checksum.
Đầu ra trong `dist/`: exe, ZIP Windows, ZIP nguồn và `SHA256SUMS.txt`. Không nhúng `.env` thật vào exe/ZIP.
Gitleaks quét toàn bộ lịch sử Git trong CI, không bỏ qua fixture hoặc dùng baseline che kết quả.

Năm ca `desktop_input` gửi phím thật cần cửa sổ đích có foreground focus. Chạy riêng khi desktop rảnh:

```powershell
.\.venv\Scripts\python.exe -m pytest -q -m desktop_input
```

## Cấu hình và xử lý lỗi

Các giá trị mẫu nằm trong [.env.example](.env.example). Khởi động lại app sau khi thay cấu hình.

- `LANGUAGE=vi`, `en` hoặc `auto`; `auto` không gửi gợi ý ngôn ngữ cho API.
- Bản thu ngắn hơn `MIN_DURATION_SECONDS` hoặc không đủ 100 ms vượt `SILENCE_THRESHOLD_DBFS` bị bỏ trước khi gửi.
  Ngưỡng mặc định `-60` dBFS cần thử bằng im lặng và giọng nhỏ trên micro thật; nhiễu lớn có thể vượt ngưỡng.
- Groq trả `verbose_json`; chỉ bỏ segment khi đồng thời `no_speech_prob > 0.6` và `avg_logprob < -1.0`.
  Không lọc theo danh sách câu cấm. Timeout/kết nối lỗi không tự retry để tránh nhập trùng.
- Nếu nhận diện sai, dùng câu mẫu không riêng tư với `DEBUG_TRANSCRIPT=1` và console để so sánh
  `GROQ_RAW`, `CLEANED`, `INJECTOR_INPUT`, `INJECTOR_FINAL`; tắt lại sau khi kiểm tra.
- Cửa sổ Administrator có thể chặn nhập từ app quyền thường do UIPI. Các ứng dụng đích và cấu hình micro
  khác nhau cần thử thực tế. Exe chưa được ký số.

Khi báo lỗi, mô tả “Tôi nói / App nhập ra / Ứng dụng đích / Hoàn cảnh” bằng dữ liệu mẫu;
không gửi `.env`, API key, bản thu hoặc log riêng tư.
