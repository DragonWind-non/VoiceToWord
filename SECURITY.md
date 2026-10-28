# Bảo mật và quyền riêng tư

Không gửi API key, `.env`, bản thu hoặc transcript riêng tư vào issue, pull request hay log công khai.
Nếu phát hiện lỗ hổng, dùng mục Security → Report a vulnerability của repository nếu có.
Không đính kèm bí mật để chứng minh lỗi.

## Dữ liệu của ứng dụng

- Chỉ thu micro khi giữ phím push-to-talk; đóng luồng khi nhả phím hoặc thoát.
- Âm thanh được xử lý trong RAM và gửi qua HTTPS đến `https://api.groq.com` để phiên âm.
  Việc xử lý/lưu giữ phía dịch vụ chịu chính sách Groq.
- Ứng dụng không tự ghi âm thanh hay transcript ra file. Kết quả chưa nhập gần nhất ở RAM;
  xóa khi nhập thành công, bị thay bởi kết quả mới hoặc khi thoát. RAM vẫn chịu cơ chế swap/dump của Windows.
- Mặc định `DEBUG_TRANSCRIPT=0`. Khi bật, console có nội dung nhận diện; chuyển hướng console ra file
  sẽ tạo log chứa nội dung đó. Chỉ dùng dữ liệu mẫu và tắt chẩn đoán sau khi thử.
- `.env` là file văn bản thuần trên máy bạn. Giữ quyền truy cập phù hợp và không chia sẻ file đó.
- Không tự thực thi lệnh terminal hay nhấn Enter. Kết quả được nhập vào cửa sổ đang có focus khi API trả về.

## Quy trình phát hành

`scripts/release.py` xuất nguồn từ commit Git, kiểm tra đường dẫn, đóng gói từ thư mục tạm không có `.env`,
đối chiếu bytecode các module ứng dụng trong exe với nguồn, rồi kiểm tra CRC và tạo SHA-256.
CI chạy test, Ruff, Bandit, pip-audit và Gitleaks trên lịch sử đầy đủ; công cụ quét có giới hạn,
không chứng minh phần mềm không thể có lỗ hổng.

Khi khóa đã bị lộ, thu hồi/đổi khóa trước. Chỉ xóa file hoặc sửa lịch sử Git không làm khóa cũ hết hiệu lực.
Nguồn: [GitHub — removing sensitive data](https://docs.github.com/en/authentication/keeping-your-account-and-data-secure/removing-sensitive-data-from-a-repository).
