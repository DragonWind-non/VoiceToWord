# Kiểm chứng bản sửa VoiceToWord — 24/10/2026

Phạm vi ban đầu: sửa bản Python để giảm câu tự sinh khi im lặng, phân biệt lỗi nhận diện với lỗi nhập chữ, và xử lý lỗi tài nguyên/vòng đời. Sau đó người dùng yêu cầu đóng gói `.exe` thử; kết quả nằm ở phần bổ sung cuối báo cáo. Chưa commit/push. Giữ phần thay đổi injector đã tồn tại trước đợt sửa.

## Những phần đã sửa

- Chặn bản thu ngắn hoặc dưới ngưỡng âm lượng trước khi gọi Groq. Đo theo khung 20 ms và yêu cầu tổng cộng 100 ms vượt ngưỡng; không để khoảng im lặng dài làm loãng một câu nhỏ nhưng đủ nghe. Loại thành phần DC và tính trên float để tránh tràn int16.
- Dùng `verbose_json`, chỉ bỏ segment khi đồng thời `no_speech_prob > 0.6` và `avg_logprob < -1.0`. Không dùng danh sách cấm câu quảng cáo; câu kêu gọi đăng ký được nói thật, có độ tin cậy cao vẫn được giữ.
- Có `GROQ_RAW`, `CLEANED`, `INJECTOR_INPUT`, `INJECTOR_FINAL` khi bật `DEBUG_TRANSCRIPT=1`. Mặc định không log transcript; không ghi bản thu ra đĩa. Lỗi API chỉ hiện thông báo an toàn.
- `LANGUAGE=auto` bỏ gợi ý ngôn ngữ khỏi request; `vi`/`en` vẫn dùng được. Cấu hình số không hợp lệ được đưa về mặc định.
- Đóng stream khi lỗi, báo overflow để thu lại, giải phóng trạng thái busy khi tạo worker thất bại, bỏ phản hồi đang chờ sau khi thoát. Client có timeout 15 giây cho thao tác I/O và không tự retry; đây không phải cam kết thời gian tổng của một request.
- Mutex chặn hai bản Python mới chạy cùng lúc. Việc dọn dịch vụ vẫn tiếp tục nếu một dịch vụ lỗi; Tk được giải phóng trên luồng sở hữu và chờ luồng GUI thoát.
- Injector loại ký tự điều khiển và từ chối Unicode không hợp lệ. Với Edit/RichEdit Unicode, dùng `EM_REPLACESEL` tại con trỏ/vùng chọn, có kiểm tra lại focus và timeout. Nếu gửi thất bại không thử gõ lần nữa để tránh chèn trùng. Cửa sổ khác dùng Unicode `SendInput`; không thay clipboard.

## Bằng chứng kiểm thử

| Kiểm tra | Kết quả | Phạm vi chứng minh |
| --- | --- | --- |
| Toàn bộ pytest sau bản sửa cuối | **79 passed**, 9,04 giây, exit 0; không skip | Bao gồm unit, tích hợp SDK qua transport giả, cửa sổ Tk thật và đóng GUI |
| Notepad thật, chuỗi Việt/Anh/emoji | **PASS** | Đọc lại qua UI Automation khớp toàn bộ chuỗi đầu vào |
| Notepad thay vùng chọn 20 lượt, mỗi lượt có số khác nhau | **20/20 khớp chính xác** | Gọi production `TextInjector`; không thể đạt do nội dung cũ tình cờ giữ nguyên |
| Khởi động/thoát hotkey + tray + overlay thật | **PASS**, không còn luồng dịch vụ | Chạy lại ngày 24/10; không mở micro hoặc gọi Groq trong bài này |
| `pip check` | **No broken requirements found**, exit 0 | Môi trường `.venv` hiện có |
| `git diff --check` | **PASS** | Kiểm tra khoảng trắng của diff; Git có cảnh báo chuyển LF/CRLF |

Lần pytest trước đó có **78 passed, 1 failed**: cửa sổ Tk mới nhận phần đầu câu khi bài test đọc sau 200 ms cố định. Đã đổi bài test sang kiểm tra nội dung thực tế với hạn chờ 1 giây và kiểm tra foreground trước mỗi lần nhập; không bỏ hoặc nới tiêu chí so sánh. Sau đó riêng injector đạt 14/14, toàn bộ bộ test đạt 79/79.

Một lỗi riêng trên Notepad đã được tái hiện trước bản sửa native: `SendInput` báo gửi thành công nhưng đọc lại từ cả UI Automation và `WM_GETTEXT` cho thấy Unicode bị hỏng. Chia nhỏ đợt gửi không giải quyết được. Sau khi chuyển Edit/RichEdit sang chèn tại con trỏ, chuỗi khớp chính xác; phép thử thay vùng chọn cũng giữ đúng phần văn bản xung quanh. Chưa xác định chắc chắn nguyên nhân bên trong Windows/IME khiến chuỗi VK_PACKET bị hỏng.

Các kiểm chứng đã có từ lượt trước, không chạy lại để tạo thêm request hoặc bản thu không cần thiết:

- Micro mặc định Realtek, mono int16 16 kHz: thu được 42.848 mẫu (~2,68 giây); mẫu môi trường yên lặng bị bộ lọc chặn. Không lưu hoặc tải mẫu micro này lên mạng. Đây là kiểm chứng trên một môi trường, không phải hiệu chuẩn cho mọi mức nhiễu.
- Groq thật nhận đúng mẫu giọng đọc tổng hợp tiếng Anh với `en`, `vi` và `auto`. Không suy ra độ chính xác cho toàn bộ tiếng Việt từ mẫu tiếng Anh này.
- Người dùng đã thử 9 lượt thu/gửi và xác nhận nhận diện ban đầu ổn. Bộ kiểm tra hiển thị tức thời ghi 7 lượt khớp, 2 lượt không khớp; chưa đủ bằng chứng để quy cả hai lượt đó cho thời gian chờ. Các phép thử nhập chữ độc lập phía trên được thực hiện để kiểm tra riêng injector.
- Cửa sổ Tk thử riêng từng đạt 20/20 chuỗi Unicode; mutex Windows từng vượt 20 vòng tạo/chặn trùng/giải phóng.

Đã tự rà soát mã và test. Lượt reviewer độc lập trước đó không thực hiện được vì giới hạn sử dụng, nên không tính là đã review độc lập.

## Chạy bản đã sửa

Thoát các VoiceToWord cũ qua tray rồi chạy từ thư mục dự án:

```powershell
.\.venv\Scripts\python.exe run.py
```

Dùng `.\.venv\Scripts\pythonw.exe run.py` khi muốn chạy không có console. `.env` hiện có ở thư mục dự án, được Git bỏ qua; không chia sẻ file này. Giữ cửa sổ đích và vị trí con trỏ trong lúc đợi kết quả. Nghe xong rồi thả Right Ctrl; không chạy đồng thời exe cũ và bản Python.

Lệnh kiểm thử đã dùng:

```powershell
.\.venv\Scripts\python.exe -m pytest -q -rs --tb=short -p no:cacheprovider --basetemp=.venv/pytest-temp-final-07
.\.venv\Scripts\python.exe -m pip check
```

Nếu chạy dưới tài khoản/quyền khác, chọn một thư mục `--basetemp` mới để tránh xung đột quyền với thư mục test cũ. Test GUI cần desktop hoạt động và có thể nhận focus.

Các script kiểm chứng Notepad/micro/vòng đời và mẫu tổng hợp được giữ cục bộ trong `.superpowers/sdd/2026-10-22-stability-repair/` (Git bỏ qua). Script Notepad chỉ thao tác tài liệu thử riêng do nó tạo; đối chiếu Unicode chính xác rồi lưu/đóng tab đó.

## Giới hạn còn lại

Bản Python đã đạt các ca đã kiểm tra; chưa có cơ sở cam kết không bao giờ phiên âm sai. Bộ lọc năng lượng không phân biệt chắc chắn tiếng nói với nhạc/nhiễu lớn, và metadata Whisper có thể tự tin vào một câu sai. Giọng quá nhỏ dưới ngưỡng vẫn có thể bị bỏ; mặc định `-60` dBFS cần thử lại khi đổi micro hoặc môi trường.

Chưa kiểm tra dài hạn, mọi IME/ứng dụng đích, cửa sổ Administrator, thiết bị micro khác hoặc tiếng Việt/Anh xen kẽ trên tập mẫu lớn. Hai `.exe` cũ trong `dist` chưa cập nhật. Mutex mới không thể ngăn exe cũ vốn chưa triển khai cùng guard.

## Bổ sung: bản `.exe` thử theo yêu cầu người dùng

- File: `dist/VoiceToWord-test-2026-10-24.exe`, 41.217.869 byte (~41,2 MB), Windows x64, onefile, không console, không UPX.
- Đóng gói bằng PyInstaller 6.22.3, hooks 2026.9, Python 3.14.7 từ `.venv` hiện có. Không sửa thêm mã runtime trong lượt đóng gói.
- SHA-256: `f6d064896f599d5819df251857877289661a50e0eb6a12a10776b469cc776a3d`.
- Kiểm tra archive: PASS; có `_tkinter.pyd` và PortAudio, không chứa `.env`; PE subsystem là Windows GUI.
- Lượt build trong sandbox ban đầu thiếu Tk; phép kiểm tra archive đã phát hiện và không chấp nhận bản đó. Đã build lại ngoài sandbox với Tk đầy đủ và kiểm tra lại đạt trước khi khởi động.
- Mở chính `.exe`: PASS, tìm thấy hai cửa sổ tray và một cửa sổ overlay, mutex hoạt động, không có hộp thoại lỗi của app trong lúc kiểm tra. Để app chạy sẵn cho người dùng thử.
- `.env` đang có trong `dist` được giữ nguyên và được đọc bên ngoài exe. `pip check` sau khi cài công cụ build: PASS.
- Bài kiểm tra khởi động không tự thu micro hoặc gọi Groq. Phần thu âm → Groq → nhập chữ trên chính exe chờ người dùng thử thực tế; không coi kết quả Python trước đó là kết quả end-to-end của exe.

Để mở lần sau, chạy file thử ở trên. Để thoát, bấm chuột phải biểu tượng micro ở khay hệ thống rồi chọn **Thoát (Exit)**. Bản onefile có thể có tiến trình cha/con; điều đó không tự có nghĩa là hai phiên app cùng nghe phím.
