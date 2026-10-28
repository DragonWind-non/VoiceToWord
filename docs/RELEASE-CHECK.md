# Kiểm chứng VoiceToWord 1.0.0 — 28/10/2026

## Phạm vi thay đổi

- Chuyển package `src` thành `voicetoword`; tách điều phối dịch vụ (`app.py`) khỏi khởi động (`main.py`).
  Cập nhật toàn bộ import, monkeypatch, logger và điểm vào; giữ các sửa lỗi runtime đã có trước đợt refactor.
- Dọn import, chuẩn hóa newline, thêm metadata package, ghim dependency runtime và tách test/build/audit.
- Giữ khóa ngoài Git. `Config` không hiện khóa trong repr, khóa mẫu chưa thay bị từ chối,
  endpoint nhận audio/khóa được cố định tại Groq; lỗi callback chỉ log tên loại lỗi.
- Đưa spec PyInstaller vào Git; build từ `git archive HEAD`, kiểm tra nội dung exe và tạo ZIP/checksum.
- Bổ sung CI quyền `contents: read`, checkout không lưu credential, pin action theo commit;
  kiểm tra mã, test, dependency, bí mật trong lịch sử và build archive trên Windows.
- Chuyển tài liệu kế hoạch/bằng chứng cũ và artifact cũ ra bản sao lưu riêng ngoài repository đang làm việc.
  Không xóa lịch sử phát triển. Email tác giả/committer trong lịch sử được đổi sang GitHub noreply;
  các fixture có dạng khóa thật được thay bằng chuỗi test rõ ràng. Hash commit vì vậy đã thay đổi.

## Kết quả đã quan sát

Môi trường: Windows x64, Python 3.14.7; cài mới môi trường kiểm chứng từ `requirements-dev.txt` thành công.

| Kiểm tra | Kết quả | Giới hạn |
| --- | --- | --- |
| Baseline trước refactor | 173 passed, 5 deselected | Không bao gồm gửi phím foreground |
| Suite sau refactor trên môi trường mới | **186 passed, 5 deselected** | Có GUI Tk, native controls, race/lifecycle và SDK qua transport giả |
| Năm ca gửi phím foreground | **5 skipped** | Windows không cấp foreground focus cho cửa sổ test; không tính là PASS |
| Ruff 0.17.3 | **PASS** | Package, test, script và điểm vào |
| Bandit 1.9.4 | **0 findings** | Package runtime và `run.py`; script build được rà lệnh/path và có test riêng |
| pip check | **PASS** | Môi trường cài mới |
| pip-audit 2.10.1 | **0 known vulnerabilities** | 35 dependency gồm runtime và test/build; truyền cả hai requirements để không bỏ qua file include khi dùng `--disable-pip`; không bỏ qua CVE |
| Gitleaks 8.30.1 | **0 findings** | Toàn bộ lịch sử sau làm sạch và bản xuất mã nguồn; không dùng baseline/allowlist |
| So sánh API key cục bộ | **0 matches** | Blob Git lịch sử, nội dung ZIP, mục exe và module PYZ đã giải nén |
| Quét email/đường dẫn cá nhân | **0 matches** | Email cá nhân và đường dẫn hồ sơ Windows được kiểm tra trong gói công khai |
| PyInstaller 6.22.3 | **PASS** | Onefile Windows x64 GUI, không UPX; build trong thư mục tạm không có `.env` |
| Đối chiếu module ứng dụng | **10/10 khớp** | Bytecode và hằng số đệ quy so với nguồn trong commit; không tính module `__main__` không dùng trong exe |
| Runtime bundle và ZIP | **PASS** | PortAudio, CA certificates, Tcl/Tk và script nhúng trong DLL; ZIP CRC và SHA-256 |
| Khởi động exe giải nén từ ZIP | **PASS** | Hai cửa sổ tray, một Tk overlay, mutex; không có hộp thoại lỗi |
| Dọn tiến trình kiểm tra startup | **PASS** | Chỉ kết thúc cây tiến trình do kiểm tra tạo; không chứng minh thao tác thoát qua tray |

Gitleaks ban đầu báo hai chuỗi giả trong fixture test, không phải khóa thực tế; đã thay chúng cả trong lịch sử
rồi quét lại. `.env` thật vẫn giữ cục bộ, không được theo dõi trong Git hay nằm trong gói phát hành.
Gói Windows chỉ gồm exe, `.env.example`, `README.txt`, `SHA256SUMS.txt`.

## Phần chưa xác minh

- Micro thật → Groq thật → ứng dụng đích trên chính exe, độ chính xác ngôn ngữ/nhiễu và độ trễ thực tế.
- Năm ca cần foreground focus nêu trên; ứng dụng Administrator/UIPI, máy Windows sạch và sử dụng dài hạn.
- Exe chưa ký số. SHA-256 dùng để đối chiếu toàn vẹn, không thay chữ ký số.
- Kiểm tra tự động không chứng minh an toàn tuyệt đối hoặc phát hiện mọi bí mật/lỗ hổng chưa biết.
  [pip-audit](https://github.com/pypa/pip-audit) kiểm tra lỗ hổng dependency đã biết;
  [Gitleaks](https://github.com/gitleaks/gitleaks) tìm bí mật theo bộ quy tắc.

Startup smoke dùng khóa giả và không bấm hotkey; không dùng API key thật để kiểm tra startup,
không mở micro hay gọi Groq trong bài này. Trạng thái CI trên GitHub được xem trực tiếp ở tab Actions.
