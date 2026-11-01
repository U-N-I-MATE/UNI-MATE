# Nhật ký cập nhật

***Tiếng Việt** · [English](CHANGELOG.en.md)*

Lịch sử phiên bản UNI MATE. Bản mới nhất ở trên cùng. Xem ngay trong app tại **Cài đặt → Cập nhật**.

Định dạng: mỗi phiên bản là một khối `## [x.y.z] - ngày`, bên dưới nhóm thay đổi theo `### Thêm mới / Sửa lỗi / Cải thiện / Bảo mật`.

## [0.429.2] - 2026-11-01
### Cải thiện
- **Cổng mặc định của UNI MATE giờ là 8688** ở bản cài mới, Docker, script cài và tài liệu. Máy nào đã đặt cổng riêng trong `.env` thì vẫn giữ cổng đó.
- **Thẻ Tự bật, lời nhắc micro và trang thử giọng hiện đúng cổng đang chạy**, không còn ghi cố định một địa chỉ.
- **Nghe thử giọng ChatGPT Live giờ tự giới thiệu là Uni.** Thu lại cả 9 mẫu giọng.

### Sửa lỗi
- **Cảnh báo giọng gọi khác giới tính giọng đọc có thêm nút "Giữ nguyên, không nhắc nữa".** Bạn chủ động chọn vậy thì màn hình thôi nhắc lại.

## [0.429.1] - 2026-11-01
### Thêm mới
- **UNI MATE 01: bản đầu tiên của UNI MATE.** Trợ lý AI tự cài trên máy, sản phẩm của UNI TECH, Công ty TNHH Dịch vụ và Thương mại U.N.I.
- **Mã nguồn mở theo giấy phép GNU AGPL-3.0**, kèm giấy phép thương mại của U.N.I cho ai muốn dùng mà không theo nghĩa vụ AGPL. Xem `LICENSE` và `NOTICE.md`.
- **Gọi bằng giọng nói là "Uni"**, tên hiển thị là "UNI MATE". Tai nghe tự sửa các cách nghe nhầm hay gặp như "Diu ni", "Yu ni", "U ni mết".
- **Linh vật UNI MATE mới, cũng là logo và biểu tượng app.** Thân tím, chấm vàng, má hồng, mắt to tròng trắng. Mặc định không có miệng; miệng chỉ hiện lúc đang đọc câu trả lời, lúc xong việc, lúc bạn thả tim và lúc micro bắt được giọng. Có việc nền trả kết quả thì chấm vàng bật lên trên đầu.
- **Giao diện theo bộ nhận diện UNI TECH:** màu nhấn Tím công nghệ, nhấn phụ vàng kim, nền sáng Sương xanh; phông chữ thương hiệu UNI Sans (tự chứa trong app, không gọi Google Fonts).
- **Kho tiện ích riêng `unimate-store`** (377 gói) và **công cụ Zalo riêng `unimate-zalo`**.
