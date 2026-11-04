# Nhật ký cập nhật

***Tiếng Việt** · [English](CHANGELOG.en.md)*

Lịch sử phiên bản UNI MATE. Bản mới nhất ở trên cùng. Xem ngay trong app tại **Cài đặt → Cập nhật**.

Định dạng: mỗi phiên bản là một khối `## [x.y.z] - ngày`, bên dưới nhóm thay đổi theo `### Thêm mới / Sửa lỗi / Cải thiện / Bảo mật`.

## [0.445.2] - 2026-11-04
### Cải thiện
- Không có thay đổi nào với người dùng. Cập nhật quy ước lập trình: GitHub tự xoá nhánh khi gộp, chỉ ghi lại nhánh nào không đi qua PR; ghi đúng nguồn quy ước viết mã bằng tiếng Anh.

## [0.445.1] - 2026-11-04
### Cải thiện
- Không có thay đổi nào với người dùng. Cập nhật quy ước lập trình: gộp xong thì xoá nhánh luôn, không hỏi lại; giữ nguyên các nhánh gốc.

## [0.445.0] - 2026-11-04
### Sửa lỗi
- **UNI MATE trên VPS nhỏ không còn đứng hình rồi hiện "404 page not found".** Vài trang làm việc nặng ngay trên luồng chính của máy chủ: thống kê trang Việc, danh sách việc của chatbot, danh sách công cụ tuỳ chọn, và lần đầu nén các tệp giao diện sau mỗi lần khởi động. Trên VPS 1 nhân, trong lúc đó máy chủ không kịp trả lời bước kiểm tra sức khoẻ, nên Traefik tạm gỡ đường vào trang. Giờ các việc đó chạy ở luồng phụ, trang khác và bước kiểm tra sức khoẻ không phải chờ.
- **Thống kê trang Việc mở nhanh hơn hẳn.** Ô "thời gian đã đỡ cho anh" trước đây hỏi ổ đĩa cho từng ngày kể từ năm 1970 (khoảng 20.000 lần mỗi lần mở trang) để tìm nhật ký vòng lặp. Giờ chỉ đọc đúng các tệp nhật ký đang có.
- **Số ghi chú ở ô chọn bộ não giờ chỉ đếm phần được đồng bộ.** Trước đây số này đếm cả các tệp mỗi máy tự ghi và không bao giờ đồng bộ (nhật ký hội thoại hằng ngày, nhật ký tự học, nhật ký vòng lặp, nhật ký chạy của trợ lý, mục lục tự sinh), nên máy nhà và VPS luôn lệch vài tệp dù đồng bộ đúng (ví dụ Brain Default 21 so với 17). Giờ hai bên đồng bộ đủ thì hiện cùng một số; còn lệch là có tệp thật chưa sang.
- Khi máy chủ chậm lại, các tab và thiết bị không còn thử lại cùng một nhịp, tránh dồn vào máy chủ đúng lúc nó yếu nhất.

## [0.444.0] - 2026-11-04
### Cải thiện
- **UNI MATE bớt đọc lại tệp cài đặt chỉ để biết múi giờ.** Mọi chỗ hiện giờ, ngày (nhật ký việc, lịch nhắc, mức dùng, tin nhắn...) trước đây mỗi lần đều dựng lại cả tệp cài đặt. Giờ múi giờ được nhớ sẵn và chỉ đọc lại khi tệp cài đặt thật sự đổi: định dạng 720 mốc giờ từ khoảng 105 ms còn khoảng 14 ms. Đổi múi giờ trong Cài đặt vẫn có hiệu lực ngay.

## [0.443.0] - 2026-11-04
### Sửa lỗi
- **Bảng việc ghi bản sao nhanh hơn nhiều, không làm UNI MATE khựng.** Mỗi lần bảng việc đổi, UNI MATE ghi một bản sao vào brain. Trước đây mỗi dòng nhật ký của từng việc đều đọc lại tệp cài đặt để biết múi giờ: 120 việc mất khoảng 105 ms, bảng đầy còn lâu hơn nhiều, và trong lúc đó UNI MATE đứng hình theo. Giờ múi giờ chỉ đọc một lần, cùng bảng đó còn khoảng 10 ms.
- Kiểm tra tự động hết báo đỏ chập chờn ở phép đo bảng việc (bản chính 0.441.0 đỏ lúc 07:30 ngày 04/11 vì đúng chỗ này).

## [0.442.0] - 2026-11-04
### Sửa lỗi
- **Menu chọn não không còn hiện một thư mục hai lần.** Khi một não trong thư mục brains là lối tắt tới thư mục ghi chú ở nơi khác, thư mục ngoài trỏ thẳng tới đó trước đây vẫn hiện thêm ở nhóm "Thư mục ngoài". Giờ UNI MATE nhận ra đó là cùng một thư mục: tự gỡ dòng trùng, và nếu anh đang chọn dòng đó thì chuyển sang chính não ấy. Chọn lại thư mục đó bằng nút mở thư mục cũng chọn thẳng não, không thêm dòng mới.
- **Không còn báo nhầm "Cuộc chat này thuộc brain khác".** Mở một hội thoại của chính bộ não đang chọn (ví dụ trong trang Cộng sự) có lúc hiện dòng "Cuộc chat này thuộc brain Bonao_AI... Chuyển sang Bonao_AI", vì hội thoại lưu đường dẫn thật còn ô chọn não dùng đường dẫn lối tắt. Giờ UNI MATE so theo thư mục thật nên chỉ báo khi đúng là não khác.
- **Nhãn nhóm "Thư mục ngoài" hiện đúng chữ.** Trước đây có lúc hiện mã `app.external_folder` vì nhóm được vẽ trước khi ngôn ngữ nạp xong.

### Thêm mới
- **Nút Gỡ thư mục ngoài** cạnh menu chọn não, chỉ hiện khi đang chọn một thư mục ngoài. Chỉ gỡ khỏi danh sách, không xoá gì trên ổ đĩa. Lúc đó nút Đổi tên và Xoá não được ẩn đi vì không dùng cho thư mục ngoài.

## [0.441.0] - 2026-11-04
### Thêm mới
- **Chuẩn bị cổng cho ChatGPT và Claude bên ngoài.** UNI MATE có sẵn các hàm để gói "UNI MATE trong ChatGPT" đọc hội thoại của anh và ghi lại những gì anh đã chốt bên ChatGPT/Claude thành một hội thoại riêng. Hội thoại với khách hàng, nhóm và Team không bao giờ được đọc. Cần cập nhật gói lên bản mới để dùng.

## [0.440.0] - 2026-11-03
### Cải thiện
- **Team tổng hợp tốn ít token hơn.** Trước đây lượt tổng hợp đọc mỗi kết quả của thành viên hai lần (trong lịch sử nhóm và ở phần đầu vào). Giờ mỗi kết quả chỉ có một lần.
- **Thành viên báo kết quả gọn và thật.** Cuối mỗi bước, thành viên tóm tắt tối đa 3 câu và kể tên file đã ghi. Ai không làm được phần mình thì nói rõ vì sao, việc dừng lại chờ anh quyết, không tốn thêm lượt tổng hợp một kết quả dở. Bấm Chạy lại bước là làm lại đúng phần đó.

## [0.439.0] - 2026-11-03
### Cải thiện
- **Bước của Team chờ đúng phần nó cần.** Trưởng nhóm giờ ghi được phần nào cần kết quả của phần nào. Ví dụ "B viết bài, C làm ảnh, cả hai dựa trên số liệu của A": B và C cùng làm ngay sau A, thay vì lần lượt như trước.
- Phần phải chờ chỉ nhận kết quả của đúng các phần nó chờ làm đầu vào. Việc yêu cầu "làm lần lượt" vẫn chạy như cũ.

## [0.438.0] - 2026-11-03
### Bảo mật
- **UNI MATE tự tắt thống kê gửi về tác giả của skill.** Gói Hyperframes trong Kho cài đặt (bản 1.0.1) gửi email và tên tài khoản HeyGen về máy chủ thống kê của tác giả. Giờ mọi lệnh, skill và engine UNI MATE chạy đều mang sẵn công tắc tắt thống kê, cả bản trên máy lẫn bản VPS, nên không gì được gửi đi.
- Công tắc dùng chung `DO_NOT_TRACK` còn tắt luôn thống kê của nhiều công cụ khác cũng tôn trọng nó.

## [0.437.1] - 2026-11-03
### Sửa lỗi
- **Kiểm tra tự động bớt báo đỏ oan.** Phép đo tốc độ khởi động đôi khi vượt trần chỉ vì máy kiểm tra chạy chậm một nhịp; giờ vượt trần thì đo lại tối đa 3 lượt và lấy số tốt nhất. Ứng dụng không đổi gì.

## [0.437.0] - 2026-11-03
### Cải thiện
- **Mở chat mới bằng Claude Code đỡ tốn hạn mức gói hơn.** Trước đây phần hướng dẫn gửi kèm (khoảng 43.000 ký tự) khác nhau giữa các cuộc chat chỉ vì giờ, mã phiên và mức dùng trong ngày, nên mỗi cuộc mới Claude phải nạp lại từ đầu. Giờ phần này giữ y nguyên nên được đọc lại từ bộ nhớ đệm.
- Giờ hiện tại vẫn đi theo mỗi tin nhắn; mã phiên và mức dùng hôm nay đi theo tin nhắn đầu cuộc chat, nên UNI MATE vẫn biết đủ như cũ.

## [0.436.0] - 2026-11-03
### Cải thiện
- **Team tự thử lại khi engine lỗi thoáng qua.** Gặp lỗi quá tải, 503, 429 hay rớt mạng giữa chừng, bước của Team tự chạy lại tối đa 2 lần sau vài giây, không còn đứng chờ anh bấm Chạy lại. Trong lúc đó khung chat Team hiện "Engine lỗi tạm thời, đang tự thử lại".
- **Không bao giờ gửi hay đăng hai lần.** Bước có dùng công cụ mà đã chạm tới model rồi mới lỗi thì không tự chạy lại, vì có thể nó đã gửi tin, đăng bài hay ghi file. Bước đó dừng kèm ghi chú để anh kiểm tra trước.
- Hết hạn mức gói, lỗi đăng nhập hay yêu cầu sai thì không thử lại, vì chờ thêm vài giây cũng không hết lỗi.

## [0.435.0] - 2026-11-03
### Sửa lỗi
- **Câu trả lời dài không còn làm đơ trang khi chữ đang chảy về.** Trước đây mỗi mẩu chữ vẽ lại toàn bộ câu trả lời, nên câu càng dài càng giật rồi đứng hẳn. Nay chữ được vẽ tối đa một lần mỗi khung hình và tự giãn nhịp khi câu rất dài; áp dụng cả cho cuộc gọi bằng giọng.

## [0.434.0] - 2026-11-03
### Cải thiện
- **Bảng từ 4 cột trở lên hiện rộng hết khung chat**, không còn bị ép trong cột đọc hẹp rồi phải kéo ngang trên màn hình lớn. Chữ quanh bảng vẫn giữ độ rộng dễ đọc; bảng quá rộng so với màn hình vẫn kéo ngang được.

## [0.433.0] - 2026-11-03
### Thêm mới
- **Chọn múi giờ ở Cài đặt → Ngôn ngữ.** Mặc định là Việt Nam (UTC+7); máy đang ở múi khác thì có nút dùng múi giờ của thiết bị. Múi giờ gõ sai bị từ chối thay vì lưu ngầm.

### Sửa lỗi
- **"Hôm nay" theo múi giờ đã chọn, không theo đồng hồ máy chủ.** Trên VPS chạy UTC, từ 0 giờ đến 7 giờ sáng UNI MATE còn tưởng là hôm qua: hạn mức theo ngày của cộng sự và Team, thói quen đã tick, nhật ký và giờ in trong ghi chú đều lệch 7 tiếng. Nay tất cả lấy cùng một mốc ngày.

## [0.432.0] - 2026-11-03
### Sửa lỗi
- **Claude báo "You've hit your 5-hour limit" giờ được nhận ra là hết hạn mức.** Trước đây câu tiếng Anh này hiện ra như câu trả lời và không có thẻ tự chạy lại; giờ chat báo hết lượt trong cửa sổ 5 giờ, có thẻ hẹn chạy lại đúng lúc mở. Câu báo hết hạn mức tuần cũng nhận đúng gói Claude.
- **Giờ mở lại hạn mức tính theo múi giờ trong Cài đặt**, không còn theo đồng hồ máy chủ. Trên VPS trước đây báo 08:00 trong khi thật ra là 15:00 giờ Việt Nam; mở lại vào hôm sau thì có kèm ngày.

## [0.431.0] - 2026-11-03
### Thêm mới
- **Lịch tự động dùng được Chrome riêng trên máy chủ.** Mỗi lịch có công tắc "Dùng Chrome riêng của máy chủ" (mặc định tắt, chỉ ở mức toàn quyền). Bật lên thì lúc tới giờ AI chỉ dùng Chrome của máy chủ, không bao giờ đụng tới Chrome trên máy bạn.
- **Chat tự dùng đúng Chrome trên máy bạn**, không hỏi lại "dùng trình duyệt nào" khi có hai trình duyệt cùng kết nối.
- **Khai mã hai trình duyệt ở thẻ Claude Code (trang Models)**: một mã cho chat, một mã cho lịch. Đổi máy chỉ cần sửa hai ô này. Chưa khai mã cho lịch thì không lịch nào được dùng Chrome.
- Lưu ý: ai vào được dashboard là điều khiển được Chrome đang đăng nhập, nên giữ kỹ mật khẩu dashboard. Bot khách và lịch do bot tạo không bao giờ được dùng Chrome.

## [0.430.3] - 2026-11-03
### Cải thiện
- **Chat trên dashboard điều khiển được Chrome thật của bạn** khi dùng Claude Code bằng gói thuê bao. Cài tiện ích Claude in Chrome, mở Claude Code một lần, gõ `/chrome` và chọn Enabled by default là xong; từ lượt chat sau AI mở tab, đọc trang, bấm và điền giúp bạn. Việc nền, bot khách và chế độ API key không được dùng Chrome.

## [0.430.2] - 2026-11-02
### Thay đổi
- **Gỡ khung trình duyệt (nút quả địa cầu).** Google chặn trình duyệt tự động nên khung không dùng được cho việc chính là vào Google. Lần khởi động đầu sau khi cập nhật, UNI MATE tự tắt trình duyệt chạy ngầm và xoá hồ sơ đăng nhập của khung; thư mục `downloads` trong brain giữ nguyên.

### Cải thiện
- **Thẻ Google Workspace tải được tệp đính kèm trong Gmail** (ví dụ file Excel báo cáo hằng ngày) để lưu lên Google Drive.

## [0.430.1] - 2026-11-02
### Cải thiện
- **Nút trình duyệt (quả địa cầu) có ở mọi màn trừ Đồ thị**, ngay cạnh nút Thông báo. Bấm là trình duyệt mở thành cột bên phải màn đang xem: ở màn Hội thoại thì chat bên trái, trình duyệt bên phải. Kéo mép trái của khung để chỉnh rộng hẹp.

### Sửa lỗi
- **Trình duyệt không còn tự tắt khi vừa mở** lúc có sẵn nhiều tab (ví dụ mở lại các tab của lần trước) rồi đổi cỡ khung.

## [0.430.0] - 2026-11-02
### Thêm mới
- **Khung trình duyệt ngay cạnh khung chat.** Mở trang web, chuyển tab, gõ địa chỉ, bấm và gõ trực tiếp; AI duyệt web trên cùng trình duyệt này nên bạn thấy nó đang làm gì và giành quyền bấm khi cần. Đăng nhập một lần là nhớ, chạy giống nhau trên máy nhà và VPS.

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
- **Kho tiện ích riêng `unimate-store`** (377 gói) và **công cụ Zalo riêng `unimate-zalo`**.
