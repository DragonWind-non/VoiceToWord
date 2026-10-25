# VoiceToWord Stability Repair Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking. Thực hiện tuần tự; không tự chia subagent, commit hoặc đóng gói.

**Goal:** Phân biệt đúng nơi làm sai văn bản, bỏ qua bản thu im lặng trước Groq, và kiểm chứng luồng giữ phím → thu âm → phiên âm → nhập chữ ổn định trên Windows.

**Architecture:** Giữ các module Python hiện tại và các giao diện `AudioRecorder.stop() -> tuple[io.BytesIO, float]`, `Transcriber.transcribe(audio_buffer) -> str`, `TextInjector.paste_text(text) -> bool`. Thêm quan sát tại ranh giới có lỗi, lọc năng lượng âm thanh bằng NumPy sẵn có, rồi sửa vòng đời tài nguyên/tác vụ; chỉ thay cơ chế nhập chữ nếu đối chiếu thực tế chứng minh lỗi ở đó.

**Tech Stack:** Windows x64; Python; sounddevice/PortAudio; NumPy; Groq Whisper; pynput; ctypes/Win32; tkinter; pystray; pytest. Không thêm dependency ở vòng sửa đầu.

**Spec:** Yêu cầu và thứ tự ưu tiên của người dùng ngày 2026-10-22 là nguồn quyết định cho kế hoạch này. [Thiết kế ban đầu](../specs/2026-10-22-voice-to-word-design.md) là tài liệu tham chiếu; các mục tiêu cũ về độ trễ/RAM và cơ chế clipboard không phải bằng chứng đã đạt hoặc yêu cầu đổi lại runtime hiện tại.

## Global Constraints

- Chỉ lập kế hoạch trong lượt audit này; chưa sửa `src`, `tests`, `.env`, dependency hoặc `.exe`.
- Giữ nguyên thay đổi có sẵn trong `src/injector.py` và `tests/test_injector.py`; đọc lại diff trước khi triển khai để không ghi đè công việc khác.
- Giữ âm thanh trong RAM; mặc định không ghi transcript hay bản thu xuống đĩa. Chế độ xem transcript chỉ bật có chủ đích trên console cục bộ.
- Không log API key, nội dung `.env`, HTTP headers hoặc toàn bộ lỗi/response SDK có thể chứa dữ liệu riêng tư.
- Không dùng danh sách cấm câu; lời nói thật có nội dung “Hãy subscribe…” vẫn phải được giữ.
- Giữ clipboard, không tự Enter, không tự chạy lệnh, không tự nâng quyền và không cướp focus.
- Không đổi model, prompt, ngôn ngữ và injector cùng một lượt thử; mỗi phép đối chiếu chỉ đổi một biến.
- Chưa đóng gói bản `.exe` mới cho đến khi bản Python vượt qua các bước nghiệm thu.

## Review Focus

1. Giọng nhỏ hoặc nói một câu sau khoảng im lặng dài: bộ lọc không được đánh mất tiếng nói; Task 2–3.
2. Thoát app đúng lúc API sắp trả kết quả: không bắt đầu nhập chữ sau khi app đã chuyển sang dừng; Task 4b.
3. API mất mạng/chậm/401/429: báo lỗi an toàn, bỏ kết quả lỗi, trả trạng thái rảnh để lượt tiếp theo hoạt động; Task 4b.
4. Micro không mở được, bị rút hoặc báo overflow: đóng tài nguyên, nhận biết bản thu có vấn đề và không mắc kẹt trạng thái; Task 3, 4b.
5. Unicode, bộ gõ, focus và quyền cửa sổ: phải kiểm tra văn bản thực sự xuất hiện; số sự kiện `SendInput` thành công không tự chứng minh chữ đúng; Task 1, 5.

## Kết quả quét ngày 2026-10-22

Đã đọc các module `src`, 7 tệp test, entry point, README, CLAUDE.md, cấu hình mẫu, Git diff, thiết kế/kế hoạch cũ và metadata build. Không tìm thấy AGENTS.md cục bộ; áp dụng hướng dẫn người dùng đã cung cấp. Kho Git hiện có, HEAD `b407462`.

| Phát hiện | Bằng chứng hiện tại | Hệ quả |
| --- | --- | --- |
| Chưa quan sát được transcript gốc | `src/transcriber.py:77–78` nhận `.text` rồi lập tức `clean_transcription()`; không có log raw/cleaned | Cần phân biệt Groq, làm sạch và nhập chữ |
| Chỉ chặn bản thu quá ngắn | `src/main.py:80–95`; không có kiểm tra năng lượng trong recorder | Một giây PCM bằng 0 vẫn gọi transcriber, đã tái hiện bằng giả lập |
| Ngôn ngữ mặc định và cấu hình bản build là `vi` | `src/config.py:12,28`; kiểm tra riêng các trường cấu hình an toàn trong `dist/.env` | Chưa có phép đối chiếu tiếng Anh hoặc chế độ auto |
| Micro dùng thiết bị mặc định | `src/audio_recorder.py:34–39` không truyền `device`; callback bỏ qua `status` | Chưa biết thiết bị thực và mức nhiễu/giọng nhỏ |
| Stream không được đóng ở một số đường lỗi | `src/audio_recorder.py:41–44,76–83` | Đã tái hiện `close()` không được gọi khi `start()` hoặc `stop()` của stream ném lỗi |
| Worker không kiểm tra trạng thái dừng trước nhập chữ | `src/main.py:97–114,126–133` | Đã tái hiện lời gọi injector sau `app.stop()` khi giải phóng phản hồi giả lập bị trì hoãn |
| Chưa đặt timeout/retry riêng cho tương tác giữ phím | `src/transcriber.py:52` | Phụ thuộc mặc định SDK; chưa xác định phiên bản SDK của bản exe đang chạy |
| Cấu hình số chưa kiểm tra miền giá trị | `src/config.py:31–39` chỉ bắt lỗi chuyển đổi | Số âm, 0 hoặc NaN có thể đi vào logic thu/lọc |
| Môi trường Python chưa sẵn sàng chạy test | `python` là 3.14.7 x64, thiếu toàn bộ dependency trong requirements và pytest | Lệnh pytest dừng với `No module named pytest`; chưa có baseline toàn bộ test |
| Cấu hình Python và exe khác vị trí | `.env` gốc không có, `dist/.env` có key; process hiện tại không đặt key | Chạy `python run.py` lúc này sẽ không có cấu hình key như bản exe |

`dist` có `VoiceToWord.exe` và `VoiceToWord-typing-fix.exe`. Quan sát tiến trình cho thấy bản `typing-fix` có PID cha 9084 và con 3056, cùng đường dẫn. Quan hệ này phù hợp mô hình PyInstaller one-file; không kết luận chạy trùng chỉ vì thấy hai PID. Chưa kiểm tra chữ ký/chi tiết bootloader để khẳng định sâu hơn, và không dừng tiến trình.

Metadata build ghi Python 3.12.10 và đường dẫn Python312 cũ; interpreter đó không được tìm thấy ở đường dẫn đã ghi trong môi trường hiện tại. Không lấy kết quả test hoặc build cũ làm bằng chứng cho checkout hôm nay.

Kiểm tra đã làm, đều không mở micro, gửi audio hoặc nhập chữ thật:

- AST parse đạt cho 17 tệp Python gồm source, test và entry point.
- Giả lập `SendInput`: tiếng Việt, emoji ngoài BMP, thứ tự nhấn/nhả và chuyển newline/tab thành dấu cách đạt; `INPUT` trên máy x64 có kích thước 40 byte.
- Kiểm chứng logic thật của main với các ranh giới giả lập đã tái hiện đường im lặng và phản hồi sau dừng nêu trên; kiểm chứng recorder thật với stream giả lập đã tái hiện thiếu `close()`.
- `.env` và `dist/.env` không nằm trong danh sách tệp Git theo dõi; không xuất key.

## Task 0: Chuẩn bị môi trường kiểm chứng

**Files:** Không đổi runtime. Chuẩn bị `.venv`/`.env` bị Git ignore khi bắt đầu triển khai; đọc `requirements.txt` và `README.md`.

**Interfaces:** Giữ `load_config() -> Config`; source đọc `.env` gốc, bản frozen đọc `.env` cạnh executable, biến môi trường được ưu tiên theo hiện trạng.

- [ ] Dùng Python x64 trong `.venv` riêng. Ưu tiên tái lập Python 3.12 như metadata build để giảm biến số; nếu dùng 3.14, xác nhận các dependency cài được và ghi rõ phiên bản, không mặc định coi tương đương bản build.
- [ ] Cài đúng `requirements.txt` trong môi trường đó khi triển khai. Chưa cài hoặc sửa dependency ở lượt audit. Không thay đổi Python toàn cục để làm test chạy.
- [ ] Chạy baseline trước khi tạo `.env` gốc, bằng `.\.venv\Scripts\python.exe -m pytest -q -k "not types_vietnamese_into_real_text_window"`; ghi số pass/fail/skip và nguyên nhân. Test GUI có thật được tách sang Task 5 vì nó đổi focus và gửi phím.
- [ ] Chuẩn bị `.env` gốc cục bộ, đối chiếu các trường không bí mật với `dist/.env`; không in, đưa vào tài liệu hoặc commit key. Task 1 phải cô lập `load_dotenv` trong test cấu hình giả trước khi chạy lại test với `.env` thật; test vị trí env của executable vẫn đọc file giả trong `tmp_path`.

**Đạt khi:** Import đủ dependency, chỉ rõ interpreter/config đang dùng, và có baseline test có thể tái lập. Không coi thiếu dependency là lỗi hành vi app.

## Task 1: Tách lỗi Groq, làm sạch và nhập chữ

**Files:** `src/config.py`, `src/transcriber.py`, `src/main.py`, `src/injector.py` chỉ thêm chẩn đoán nếu cần; `.env.example`, `README.md`; `tests/test_config.py`, `tests/test_transcriber.py`, `tests/test_integration.py`, `tests/test_injector.py`.

**Interfaces:** Giữ nguyên các kiểu trả về hiện có. Thêm `Config.debug_transcript: bool = False`, ánh xạ `DEBUG_TRANSCRIPT=0|1`; không thêm lớp kết quả hay hệ thống lịch sử.

- [ ] Viết test `test_transcript_diagnostics_are_opt_in`: raw/cleaned/input không xuất hiện trong log mặc định, kể cả khi API hoặc injector lỗi. Test `test_diagnostics_preserve_raw_and_cleaned_text`: response giả `"  git status.  "` phải quan sát được raw chính xác, cleaned `"git status"` và đúng chuỗi chuyển tới injector khi bật chẩn đoán.
- [ ] Chạy các test mới để xác nhận đang thiếu hành vi. Ghi raw trước `clean_transcription()`, cleaned sau làm sạch, chuỗi cuối sau chuẩn hóa whitespace của injector và kết quả nhập. Dùng biểu diễn escape như `%r` để transcript không tự tạo dòng log/điều khiển console.
- [ ] Khởi tạo logging trong entry point; chỉ bật DEBUG cho logger ứng dụng khi được yêu cầu. Không bật DEBUG toàn bộ SDK/HTTP, không tạo file log transcript. Ghi thời điểm, model, language, duration và loại lỗi an toàn để đối chiếu.
- [ ] Với response giả chứa key sentinel trong lỗi, khẳng định sentinel không lọt vào log/thông báo. Ngay trong task này, tạo `TranscribeError` từ loại lỗi/status an toàn thay vì nhúng exception body. Task 4b bổ sung timeout và kiểm tra phục hồi sau các lỗi này.
- [ ] Cô lập `load_dotenv` trong test cấu hình giả để không đọc `.env` thật; giữ phép kiểm tra env cạnh executable trên `tmp_path`. Giữ các test khởi động không có console hiện có; chẩn đoán không được khiến `pythonw` lỗi vì thiếu stdout/stderr.
- [ ] Test injector thuần Win32 giả lập: Unicode tiếng Việt, dạng dấu tổ hợp, emoji, newline/tab, zero và số sự kiện trả về thiếu. Thiếu sự kiện phải trả `False`, không tự gửi lại cả chuỗi gây trùng chữ. Giữ `paste_text() -> bool`.
- [ ] Chạy `.\.venv\Scripts\python.exe -m pytest tests/test_config.py tests/test_transcriber.py tests/test_integration.py tests/test_injector.py -q -k "not types_vietnamese_into_real_text_window"`.

**Đạt khi:** Một câu lỗi có đủ dữ liệu phân loại: raw sai → điều tra audio/ngôn ngữ/Groq; raw đúng nhưng cleaned sai → sửa làm sạch; chuỗi cuối đúng nhưng cửa sổ sai → điều tra injector/IME/focus. Chưa đổi backend injector chỉ vì câu nhận diện sai.

## Task 2: Bỏ qua im lặng trước khi gọi Groq

**Files:** `src/audio_recorder.py`, `src/main.py`, `src/config.py`, `.env.example`; `tests/test_audio_recorder.py`, `tests/test_integration.py`, `tests/test_config.py`.

**Interfaces:** Giữ `stop()` trả hai phần tử. Thêm `AudioRecorder.is_silent(threshold_dbfs: float) -> bool` trên các frame vừa thu và `Config.silence_threshold_dbfs: float`, env `SILENCE_THRESHOLD_DBFS`. Các fake recorder trong integration test phải đặt rõ `is_silent.return_value`, không để MagicMock tự truthy.

- [ ] Viết `test_digital_silence_skips_cloud_and_injection`: WAV mono int16 16 kHz dài 1 giây, toàn số 0 → `transcribe.assert_not_called()`, `paste_text.assert_not_called()`, overlay ẩn, `_busy == False`.
- [ ] Viết `test_short_speech_inside_long_silence_is_kept` và `test_int16_extremes_do_not_overflow_energy`: tín hiệu trên ngưỡng nằm trong một đoạn ngắn không bị RMS toàn bản thu làm loãng; mẫu -32768/32767 không bị bình phương tràn số. Giữ test dưới 0,3 giây hiện có.
- [ ] Tính năng lượng trên frame 20 ms bằng NumPy, chuyển sang số thực trước bình phương. Bỏ bản thu nếu tổng frame trên ngưỡng ít hơn 100 ms; tránh lấy peak của một mẫu hoặc RMS cả bản thu làm tiêu chí duy nhất. Kiểm tra phần frame cuối và buffer rỗng.
- [ ] Dùng -60 dBFS làm giá trị khởi đầu thận trọng để thử, không coi là ngưỡng đã hiệu chỉnh. Giới hạn cấu hình hữu hạn trong [-96, 0] dBFS; giá trị không hợp lệ quay về mặc định và cảnh báo an toàn. Task 3 quyết định ngưỡng dùng thực tế.
- [ ] Đặt gate sau chặn thời lượng, trước tạo tác vụ gửi API. Mọi đường bỏ qua hoặc lỗi phân tích đều giải phóng trạng thái; lỗi phân tích audio báo lỗi, không âm thầm coi là im lặng hoặc gửi buffer hỏng.
- [ ] Test `test_real_subscription_sentence_is_preserved`: khi audio vượt gate và Groq trả lời nói thật có “Hãy subscribe…”, kết quả vẫn được chuyển tiếp. Không thêm blacklist.
- [ ] Chạy `.\.venv\Scripts\python.exe -m pytest tests/test_audio_recorder.py tests/test_config.py tests/test_integration.py -q`.

**Đạt khi:** Im lặng số và nhiễu nền dưới ngưỡng không tạo request, tiếng nói đủ điều kiện vẫn qua. Đây là bộ lọc năng lượng; chưa chứng minh phân biệt được tiếng nói với quạt, nhạc hoặc tiếng gõ lớn. Không quảng bá là VAD nhận diện lời nói.

## Task 3: Kiểm tra micro thật và hiệu chỉnh ngưỡng

**Files:** `src/audio_recorder.py`/`src/main.py` cho metadata và status, `README.md`; `tests/test_audio_recorder.py` cho callback/status. Không thêm màn hình chọn thiết bị.

**Interfaces:** Tiếp tục dùng Windows/default PortAudio input. Chẩn đoán chỉ đọc tên/index, host API, số kênh, sample rate, mức năng lượng và cờ lỗi; không tự thu nền khi chưa giữ phím.

- [ ] Thoát bản app cũ qua tray trước khi mở phiên thử. Kiểm tra cây tiến trình, không đếm PID cha–con one-file thành hai app.
- [ ] Chọn thiết bị đầu vào mong muốn trong Windows; đối chiếu thiết bị thật bằng `sounddevice.query_devices(kind="input")` và kiểm tra hỗ trợ cấu hình 16 kHz/mono/int16. Nếu thiết bị không phù hợp, báo rõ; chỉ thêm lựa chọn thiết bị trong app nếu phép đối chiếu chứng minh default không đáp ứng.
- [ ] Đo tại vị trí sử dụng thật, giữ khoảng cách micro ổn định: im lặng/nhiễu nền, giọng nhỏ, giọng bình thường, và một câu ngắn sau khoảng im lặng. Chỉ lưu số đo/tên mẫu vô hại; bản thu giữ RAM, phát lại cục bộ nếu cần.
- [ ] Chọn ngưỡng từ số đo: thấp hơn mức giọng nhỏ đã quan sát và cao hơn nền đã quan sát. Nếu hai nhóm chồng nhau, không tăng ngưỡng để ép test đạt; kiểm tra micro/gain/môi trường trước, rồi mới cân nhắc VAD chuyên dụng bằng một thay đổi riêng.
- [ ] Xử lý callback status: gom cờ lỗi trong recorder, báo ra ngoài callback; test `test_audio_overflow_is_reported_without_callback_crash`. Không ghi log dồn dập hoặc gọi UI/network ngay từ callback âm thanh.
- [ ] Lặp mỗi mẫu ít nhất 5 lần, thêm bấm nhanh dưới 0,3 giây. Tiêu chí: các lần im lặng không gọi Groq, không bỏ câu giọng nhỏ đã ghi nhận, không mắc kẹt recording/processing, clipboard và focus giữ nguyên. Chỉ kết luận trong điều kiện/micro đã thử.

**Đạt khi:** Có tên thiết bị, cấu hình, khoảng cách, số đo nền/giọng, ngưỡng và kết quả từng mẫu. Chưa chốt ngưỡng phát hành nếu chưa có lượt thử với người dùng nói thật.

## Task 4: Đối chiếu ngôn ngữ có chủ đích

**Files:** `README.md`, `.env.example`; `src/config.py`, `src/transcriber.py`, `tests/test_config.py`, `tests/test_transcriber.py` chỉ khi cần chế độ auto.

**Interfaces:** Giữ mặc định `language="vi"`. Giai đoạn đầu chỉ thay cấu hình cục bộ và khởi động lại từng phiên để đối chiếu, không tự chuyển theo kết quả đoán từ text.

- [ ] Dùng cùng mẫu tiếng Anh không riêng tư, gồm `new titan serum system`, so sánh raw với `LANGUAGE=vi` và `LANGUAGE=en`; giữ model, audio và các tham số khác như nhau. Có thể dùng lại BytesIO trong phiên chẩn đoán, không cần lưu bản thu xuống đĩa.
- [ ] Thử thêm câu Việt ngắn, Anh ngắn và câu Việt–Anh. Chấm theo lời đã nói/từ quan trọng; không chấm bằng chữ đã được injector nhập.
- [ ] Chỉ nếu cách nói xen kẽ cần và phép đối chiếu hữu ích, thêm `LANGUAGE=auto`: lưu giá trị cấu hình rõ ràng và bỏ hẳn tham số `language` trong request. Không gửi chuỗi `"auto"` làm mã ngôn ngữ.
- [ ] Nếu thêm auto, viết `test_auto_omits_language_parameter` với `"language" not in call.kwargs`; test `vi`/`en` giữ đúng giá trị request và không làm thay đổi `temperature=0.0`.
- [ ] Chạy `.\.venv\Scripts\python.exe -m pytest tests/test_config.py tests/test_transcriber.py -q` nếu có thay mã, rồi lặp mẫu thực tế.

**Đạt khi:** Có đối chiếu raw cho các kiểu nói và lựa chọn ngôn ngữ dựa trên kết quả. Không cam kết auto sửa được mọi câu xen kẽ. Groq xác nhận `language` là tùy chọn và việc chỉ định ngôn ngữ phù hợp có thể cải thiện độ chính xác/độ trễ: [Speech to Text](https://console.groq.com/docs/speech-to-text).

## Task 4b: Sửa các đường lỗi vận hành trước nghiệm thu cuối

**Files:** `src/main.py`, `src/audio_recorder.py`, `src/transcriber.py`, `src/config.py`; `tests/test_integration.py`, `tests/test_audio_recorder.py`, `tests/test_transcriber.py`, `tests/test_config.py`. Đọc caller `src/hotkey_listener.py` và `src/tray.py`; chỉ sửa nếu kiểm thử chỉ ra yêu cầu.

**Interfaces:** Giữ API công khai. Dùng cờ dừng được bảo vệ bằng lock hiện có, không xây hàng đợi/tầng điều phối mới. Một worker xử lý mỗi lần như hiện trạng.

- [ ] Viết regression `test_stop_discards_inflight_transcription` bằng `threading.Event`, không dùng sleep cố định: chặn response → `stop()` → thả response → worker kết thúc → `paste_text.assert_not_called()`. Bảo vệ kiểm tra dừng và bắt đầu nhập bằng cùng cơ chế đồng bộ để không tạo race mới; một lần nhập đã bắt đầu không thể thu hồi các ký tự đã gửi.
- [ ] Thêm `test_worker_start_failure_releases_busy`: thread không khởi động được → `_busy == False`, có lỗi an toàn, lần giữ phím sau hoạt động. Sau dừng, callback hotkey không mở bản thu mới; dừng lặp lại không lỗi.
- [ ] Viết `test_failed_stream_start_closes_stream`, `test_failed_stream_stop_still_closes_stream`: resource đã mở phải được đóng trong `finally`, kể cả khi thao tác trước thất bại. Nếu recorder cleanup lỗi, overlay/tray/hotkey vẫn được dọn; không nuốt lỗi làm bản thu hỏng trông như thành công.
- [ ] Đặt timeout I/O có chủ đích cho Groq, điểm bắt đầu `timeout=15.0, max_retries=0`; thông báo timeout/offline/401/429 ngắn và không chứa response body/key. Đây không phải cam kết deadline tổng chính xác 15 giây. Không gửi lại tự động kết quả có thể bị nhập trùng. Test từng loại lỗi và một lượt thành công ngay sau lỗi.
- [ ] Kiểm tra `sample_rate > 0`, `min_duration` hữu hạn và không âm; giá trị cấu hình số không hợp lệ dùng mặc định/cảnh báo như cách xử lý hiện có. Test NaN, Infinity, số âm và sample rate 0. Cô lập env trong test để `.env` thật không làm đổi kết quả.
- [ ] Chặn phiên thứ hai trong entry point bằng named mutex Win32 trong session (`Local\VoiceToWord`), dùng ctypes sẵn có, khai báo đúng kiểu HANDLE/argtypes/restype x64. Giữ handle suốt vòng đời, đóng trong `finally`; lỗi tạo guard không được âm thầm mở thêm listener. Python và exe dùng cùng tên. Test lỗi/already-exists/release qua Win32 giả lập; Task 5 kiểm tra thực tế.
- [ ] Chạy `.\.venv\Scripts\python.exe -m pytest -q -k "not types_vietnamese_into_real_text_window"` và đọc exit code. Chỉ sửa lỗi liên quan, không refactor toàn bộ UI hoặc đổi hotkey mặc định.

**Đạt khi:** Dừng không để response muộn bắt đầu nhập; lỗi stream/thread/API không khóa lượt tiếp theo; phiên thứ hai không đăng ký thêm hotkey. [Groq Python SDK](https://github.com/groq/groq-python#retries) hiện tài liệu hóa retry mặc định 2 lần và timeout mặc định 1 phút; đây là tham chiếu SDK công khai, chưa xác minh phiên bản trong exe đang chạy.

## Task 5: Nghiệm thu Python trước, exe sau

**Files:** `README.md` ghi kết quả/cách chạy đã kiểm tra. Chỉ cập nhật packaging nếu sau đó có yêu cầu tạo bản mới; không đưa `.env` vào spec hoặc bundle.

**Interfaces:** Chỉ một phiên app nhận hotkey. Đầu ra đúng là văn bản quan sát được tại ứng dụng đích, không chỉ mock hoặc giá trị trả về `SendInput`.

- [ ] Thoát app cũ qua tray, xác nhận cây tiến trình rồi chạy `.\.venv\Scripts\python.exe run.py` với chẩn đoán transcript bật trong phiên thử có chủ đích.
- [ ] Mở Notepad thường, giữ focus trong lúc chờ; đối chiếu raw → cleaned → chuỗi cuối → chữ hiển thị cho bốn mẫu chính: Việt, Anh, Việt–Anh, im lặng. Thử thêm giọng nhỏ, dấu tổ hợp, emoji, câu có newline/tab từ response giả, và lời “Hãy subscribe…” nói thật.
- [ ] Chạy test GUI riêng trong desktop có thể quan sát: `.\.venv\Scripts\python.exe -m pytest tests/test_injector.py::test_injector_types_vietnamese_into_real_text_window -v`. Test bị skip vì không lấy được foreground không được tính là đạt. Quan sát overlay khi đang ghi/xử lý để kiểm tra focus; test Tk hiện tại không thay thế thử Notepad/IME.
- [ ] Thử bộ gõ tiếng Việt bật/tắt; nếu chuỗi cuối đúng mà chữ sai, tái hiện bằng chuỗi cố định bỏ qua Groq, rồi mới sửa Win32/IME. Chỉ thêm đường nhập khác nếu có bằng chứng backend hiện tại không đáp ứng.
- [ ] Thử PowerShell/CMD/Windows Terminal/VS Code theo nơi dùng hằng ngày: không Enter, không đổi clipboard, không cướp focus. Cửa sổ khác mức quyền được ghi thành ranh giới riêng; không tự nâng quyền để che lỗi.
- [ ] Thử bấm nhanh/lặp, mất mạng, thoát khi đang thu/đang chờ, rút micro, chạy phiên thứ hai và mở lại sau khi thoát. Ghi rõ tình huống phục hồi được và tình huống chưa hỗ trợ; không đặt ngưỡng hiệu năng nếu chưa đo.
- [ ] Chạy ít nhất 20 lượt dùng liên tiếp theo bộ mẫu trên, ghi số request, số lần chữ khác chuỗi cuối, số lần loại nhầm giọng nhỏ và trạng thái phục hồi. Ghi phiên bản Python/dependency và Git diff dùng để thử, không ghi nội dung riêng tư.
- [ ] Chỉ khi các kiểm chứng Python đạt và có yêu cầu đóng gói tiếp, tạo exe mới từ đúng source đã kiểm tra, rồi lặp các đường dùng quan trọng với chính file exe đó và `.env` cạnh nó. Không suy từ Python pass ra exe pass, không phát hành dựa trên file cũ trong `dist`.

**Đạt khi:** Có bảng kết quả thực tế; không lặp chữ hoặc gõ sau dừng, im lặng đã hiệu chỉnh không gọi Groq, các mẫu nói có kiểm soát không bị lọc nhầm và chữ hiển thị khớp chuỗi cuối. Các ranh giới quyền/IME/thiết bị chưa thử được ghi rõ. Độ chính xác STT được báo theo mẫu đã thử, không hứa chính xác tuyệt đối.

## Phạm vi bàn giao

Triển khai từng task, đọc diff và chạy kiểm tra gần nhất trước khi sang task sau. Không tự commit/stage, sửa AGENTS.md/CLAUDE.md, đổi kiến trúc hoặc bổ sung UI/lịch sử/ghi âm nền. Chỉ cân nhắc VAD mới, lựa chọn thiết bị trong app, prompt hoặc backend injector khác khi kết quả đo thực tế chứng minh cần thiết.

Sau lượt audit này, thay đổi duy nhất được tạo là tài liệu kế hoạch này. Các kiểm tra giả lập chứng minh những đường điều khiển đã nêu, không chứng minh micro thật, dịch vụ Groq, Notepad, IME hoặc bản exe đã ổn định.
