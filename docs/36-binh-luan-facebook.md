# 36 - Bình luận Facebook (Fanpage)

***Tiếng Việt** · [English](en/36-facebook-comments.md)*

Từ 0.448.0 UNI MATE đưa **bình luận dưới bài đăng của Fanpage** vào Hộp thư, mỗi trang là một tài khoản riêng, mỗi bài đăng là một cuộc hội thoại. Bản này **chỉ đọc**: chưa trả lời bình luận từ UNI MATE.

## Cách đọc

- Ứng dụng Facebook để ở **chế độ phát triển**, không cần Meta duyệt. Ở chế độ này Meta không tự đẩy bình luận của khách về, nên UNI MATE **tự đọc 3 phút một lần**.
- Đọc bài đăng **30 ngày gần nhất** và các **bài theo dõi thêm** (bài cũ hơn đang chạy quảng cáo, dán đường dẫn bài vào thẻ trang). Trang mới nối lấy bình luận 7 ngày gần nhất.
- Quảng cáo chạy bằng **bài đã đăng** (nút Quảng cáo bài viết, hoặc "Dùng bài viết có sẵn" trong Trình quản lý quảng cáo) thì bình luận dồn về bài gốc và được đọc như bài thường.
- **Chưa có tên người bình luận:** ở chế độ phát triển Meta ẩn tên người không có vai trò trên ứng dụng. Hộp thư ghi "Khách Facebook" kèm nút "Mở trên Facebook". Khi Meta duyệt tính năng Business Asset User Profile Access, bình luận mới tự có tên và bình luận của các bài trong 30 ngày được điền tên.
- Mỗi trang tốn khoảng 530 lượt gọi một ngày, khoảng 11% hạn mức tối thiểu của Meta. Chạm 80% hạn mức thì UNI MATE tự đọc chậm lại; Facebook báo giới hạn thì nghỉ đúng thời gian Facebook nói.

## Tạo ứng dụng Facebook (một lần)

1. Vào developers.facebook.com bằng tài khoản quản trị các trang, tạo ứng dụng với trường hợp sử dụng **"Quản lý mọi thứ trên Trang"**. Để nguyên chế độ phát triển.
2. Vào **Trường hợp sử dụng > Tùy chỉnh**, bấm **"Thêm"** cho `pages_read_engagement` và `pages_read_user_content`. Ứng dụng mới chỉ có sẵn `pages_show_list`; thiếu bước này thì Facebook không cho cấp hai quyền kia.
3. Trong cài đặt Đăng nhập Facebook của ứng dụng, dán **Địa chỉ quay về** (hiện trong thẻ Bình luận Facebook của UNI MATE) vào mục "URI chuyển hướng OAuth hợp lệ".
4. Bật **"Require App Secret"** (Yêu cầu khoá ứng dụng) ở Cài đặt ứng dụng > Nâng cao. UNI MATE ký mọi lần gọi bằng App Secret, nên lộ khoá truy cập thì người khác cũng không dùng được.

## Nối trang trong UNI MATE

1. Mở UNI MATE bằng **tên miền HTTPS** (VPS). Facebook không cho đăng nhập qua địa chỉ không có HTTPS.
2. Trang **Kết nối > Có sẵn > Bình luận Facebook**, bấm Kết nối. Dán **App ID** và **App Secret** (Cài đặt ứng dụng > Thông tin cơ bản), bấm Lưu. App Secret được mã hoá và không hiện lại.
3. Bấm **Đăng nhập Facebook**. Khi Facebook hỏi, chọn đúng trang cần đọc (ví dụ **"chỉ Trang hiện tại"**) và cho phép.
4. UNI MATE hiện danh sách trang: tick trang, bấm **Nối các trang đã chọn**. Bình luận về Hộp thư trong vài phút (bấm Đọc ngay để đọc liền).

**Thêm trang sau** (ví dụ trang Excel, trang slide): bấm **Thêm trang**, đăng nhập lại và tick trang mới. Trang đã nối giữ nguyên bình luận; tick lại trang cũ chỉ làm mới đăng nhập của nó.

## Dữ liệu cá nhân

- Bình luận giữ **12 tháng** (chỉnh 1 đến 24 tháng trong thẻ cài đặt), quá hạn thì tự xoá mỗi ngày.
- **Ngắt trang** xoá sạch bình luận, cuộc hội thoại và khoá truy cập của trang đó (bấm hai lần, lần đầu báo số bình luận sẽ xoá).
- Tên người bình luận chỉ hiện trong Hộp thư, không đi vào thông báo hay nhật ký máy chủ. Khoá truy cập và App Secret không bao giờ hiện ra giao diện.

## Khi nào phải đăng nhập lại

Khoá của trang không tự hết hạn, nhưng mất hiệu lực khi đổi mật khẩu Facebook, mất quyền quản trị trang hoặc gặp kiểm tra bảo mật. Ngoài ra Meta có hạn cho phép đọc dữ liệu khoảng 90 ngày. Thẻ trang báo **"Cần đăng nhập lại"** hoặc **"Sắp cần đăng nhập lại"** (trước 14 ngày): bấm Thêm trang, đăng nhập và tick lại trang đó.
