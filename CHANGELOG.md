# Nhật ký cập nhật

***Tiếng Việt** · [English](CHANGELOG.en.md)*

Lịch sử phiên bản UNI MATE. Bản mới nhất ở trên cùng. Xem ngay trong app tại **Cài đặt → Cập nhật**.

Định dạng: mỗi phiên bản là một khối `## [x.y.z] - ngày`, bên dưới nhóm thay đổi theo `### Thêm mới / Sửa lỗi / Cải thiện / Bảo mật`.

## [0.429.7] - 2026-11-02
### Sửa lỗi
- **Bấm biểu tượng UNI MATE trên Windows khi đã mở sẵn thì chỉ đưa cửa sổ đang mở lên trước** (mở lại nếu đang thu nhỏ), không sinh thêm cửa sổ mới. Bấm bao nhiêu lần cũng chỉ một cửa sổ.

## [0.429.6] - 2026-11-02
### Sửa lỗi
- **Xem timelapse bộ não xong vẫn thu nhỏ được đồ thị.** Trước đây chiếu xong là đồ thị bị khoá ở mức phóng to của vài ghi chú đầu phim.
- **Dòng trạng thái đồng bộ GitHub ghi đúng giờ của bạn**, không còn ghi giờ quốc tế (UTC) khi chạy trên VPS.
- **Đồng bộ bộ não giữa hai máy không còn sinh tệp `.conflict-*` mỗi lượt** từ chỉ mục vận hành `UniMate/index.md`: mỗi máy tự dựng bản của mình.

## [0.429.5] - 2026-11-01
### Cải thiện
- **Đồng bộ bộ não với GitHub đặt được chu kỳ ngắn tới 15 phút** (ô nhập nhận 0,25 giờ). Máy nhà và VPS khớp nhau nhanh hơn; trước đây ngắn nhất 1 giờ.

## [0.429.4] - 2026-11-01
### Cải thiện
- **Kiểm thử tự động bớt báo đỏ oan:** một bộ kiểm vốn chạy vài giây mà hiếm hoi bị treo thì được chạy lại một lần, và log ghi rõ chỗ treo.

## [0.429.3] - 2026-11-01
### Thêm mới
- **Nút "Gửi ngay" cho tin nhắn gửi thêm lúc UNI MATE đang làm:** bấm là dừng việc dở để UNI MATE đọc tin đó trước, đối chiếu với phần đã làm rồi mới làm tiếp hoặc hỏi lại bạn.
- **Trang Cộng sự hiện cả quy trình đang tắt, có công tắc Bật/Tắt ngay trên dòng.** Quy trình tạo từ chat mặc định tắt nên trước đây không thấy để bật.

### Sửa lỗi
- **Bấm Dừng là dừng hẳn:** tin gửi thêm còn chờ không tự chạy sau đó, và quy trình đang chạy trong chat dừng theo chứ không chạy ngầm tiếp.

## [0.429.2] - 2026-11-01
### Sửa lỗi
- **Khung chat giờ hiện tiến trình khi chạy quy trình:** từng bước, từng lệnh đang chạy hiện ngay trong chat, bấm dòng tóm tắt để xem hết. Trước đây chỉ có một dòng trạng thái.
- **Mở lại một chat đang chạy không còn hiện bong bóng trống** và không mất khối tiến trình.
- **Hộp chọn bộ não: dán đường dẫn rồi bấm Enter**, danh sách thư mục luôn cuộn được trên màn hình thấp.
- **Khung "Cấu trúc vault chưa chuẩn" bấm đóng là nhớ** cho bộ não đó, không hiện lại.
- **Hộp cài gói không còn ghi "chỉ có dữ liệu"** cho gói có chạy mã được bật sẵn từ trang Kết nối.
- **Tạo hay sửa agent với màu hoặc dáng UNI MATE không còn báo "Màu đại diện không hợp lệ".** Máy chủ trước đây chưa nhận màu Tím công nghệ và dáng linh vật mới.

### Cải thiện
- **Cổng mặc định của UNI MATE giờ là 8688** ở bản cài mới, Docker, script cài và tài liệu. Máy nào đã đặt cổng riêng trong `.env` thì vẫn giữ cổng đó.
- **Thẻ Tự bật, lời nhắc micro và trang thử giọng hiện đúng cổng đang chạy**, không còn ghi cố định một địa chỉ.
- **Nghe thử giọng ChatGPT Live giờ tự giới thiệu là Uni.** Thu lại cả 9 mẫu giọng.
- **Trang chủ UNI MATE: tech.unihq.vn/unimate.** Dòng "by UNI TECH", nhãn tác giả trên ảnh AI và liên hệ giấy phép thương mại dùng tên miền U.N.I.

### Sửa lỗi
- **Cảnh báo giọng gọi khác giới tính giọng đọc có thêm nút "Giữ nguyên, không nhắc nữa".** Bạn chủ động chọn vậy thì màn hình thôi nhắc lại.

## [0.429.1] - 2026-11-01
### Thêm mới
- **UNI MATE 01: bản đầu tiên của UNI MATE.** Trợ lý AI tự cài trên máy, sản phẩm của UNI TECH, Công ty TNHH Dịch vụ và Thương mại U.N.I.
- **Mã nguồn mở theo giấy phép GNU AGPL-3.0**, kèm giấy phép thương mại của U.N.I cho ai muốn dùng mà không theo nghĩa vụ AGPL. Xem `LICENSE` và `NOTICE.md`.
- **Gọi bằng giọng nói là "Uni"**, tên hiển thị là "UNI MATE". Tai nghe tự sửa các cách nghe nhầm hay gặp như "Diu ni", "Yu ni", "U ni mết".
- **Linh vật UNI MATE mới, cũng là logo và biểu tượng app.** Thân tím, chấm vàng, má hồng, mắt to tròng trắng. Mặc định không có miệng; miệng chỉ hiện lúc đang đọc câu trả lời, lúc xong việc, lúc bạn thả tim và lúc micro bắt được giọng. Có việc nền trả kết quả thì chấm vàng bật lên trên đầu.
- **Giao diện theo bộ nhận diện UNI TECH:** màu nhấn Tím công nghệ, nhấn phụ vàng kim, nền sáng Sương xanh; phông chữ thương hiệu UNI Sans (tự chứa trong app, không gọi Google Fonts).
- **Kho tiện ích riêng `unimate-store`** (377 gói) và **công cụ Zalo riêng `unimate-zalo`**.## [0.430.1] - 2026-11-02
### Cải thiện
- **Nút trình duyệt (quả địa cầu) có ở mọi màn**, ngay cạnh nút Thông báo. Bấm là trình duyệt mở thành cột bên phải màn đang xem: ở màn Hội thoại thì chat bên trái, trình duyệt bên phải. Kéo mép trái của khung để chỉnh rộng hẹp.


