"""Sửa chữ nghe nhầm theo ngữ cảnh (nghe_sua.sua) và gợi ý hotwords cho Whisper.

    python tests/run.py nghe_sua

Vì sao file này tồn tại (0.59.24): người dùng nói lẫn Việt - Anh, máy nghe chép tên gọi "Uni" thành
chữ gần âm ("Ưu ni", "Yu ni"...) rồi UNI MATE trả lời bám nghĩa đen. Lớp này sửa theo ÂM và NGỮ
CẢNH trước khi câu đi vào bộ não. Ranh giới quan trọng: không đổi tên người thứ ba ("nhắn cho
David"), không đổi tên riêng hai chữ ("David Beckham"), không đụng câu không liên quan, và
không sửa gì thì trả y nguyên.
"""
from _paths import ROOT, SERVER  # noqa: E402,F401

import nghe_sua  # noqa: E402

_fails = []


def check(name, cond):
    print(("ok   " if cond else "FAIL ") + name)
    if not cond:
        _fails.append(name)


TV = ["Uni"]
S = lambda s, tv=TV: nghe_sua.sua(s, tv)   # noqa: E731

# Tên GỌI trợ lý là "Uni" (quy ước UNI MATE: tên hiển thị UNI MATE, tên gọi bằng giọng nói Uni).
# ---- 1. Khoá âm: cách máy hay chép "Uni" về cùng một khoá ----
for w in ("Uni", "Ưu ni", "UNI"):
    check(f"khoá âm của {w!r} trùng Uni", nghe_sua.khoa_am(w) == nghe_sua.khoa_am("Uni"))
for w in ("university", "union", "Unicode", "uống"):
    check(f"{w!r} KHÔNG trùng khoá Uni", nghe_sua.khoa_am(w) != nghe_sua.khoa_am("Uni"))

# ---- 2. Gần âm ở vị trí GỌI tên thì sửa thành Uni ----
check("Ưu ni ơi -> Uni ơi", S("Ưu ni ơi, tóm tắt email") == "Uni ơi, tóm tắt email")
check("hey Yu ni -> hey Uni", S("hey Yu ni, doanh thu hôm nay") == "hey Uni, doanh thu hôm nay")
check("cảm ơn Iu ni -> cảm ơn Uni", S("cảm ơn Iu ni") == "cảm ơn Uni")

# ---- 3./4. Không sửa bừa: từ có chứa "uni", người thứ ba, câu không liên quan ----
GIU = [
    "học university với anh Nam",
    "unit test chạy chưa",
    "Union Pay lỗi rồi",
    "mở file unicode.txt",
    "đọc file README.md và mở https://github.com/x",
    "doanh thu tháng này bao nhiêu",
    "",
]
for s in GIU:
    check(f"giữ nguyên: {s[:40]!r}", S(s) == s)
check("không có gì sửa thì trả CÙNG đối tượng", S("xin chào") == "xin chào")
check("đã đúng Uni thì không đổi gì", S("Uni ơi mở lịch") == "Uni ơi mở lịch")
check("chạy hai lần ra cùng kết quả (idempotent)",
      S(S("Ưu ni ơi Yu ni nghe không")) == S("Ưu ni ơi Yu ni nghe không"))
TV3 = ["Uni", "UNI MATE"]
check("Diu ni ơi (giọng miền Nam) -> Uni ơi", S("Diu ni ơi mở lịch", TV3) == "Uni ơi mở lịch")
check("U ni mết (tên đầy đủ) sửa ở mọi vị trí", S("mở u ni mết lên", TV3) == "mở UNI MATE lên")
check("U ni mết ơi (gọi tên đầy đủ) -> UNI MATE ơi", S("U ni mết ơi mở lịch", TV3) == "UNI MATE ơi mở lịch")
check("dịu nhỉ (không phải gọi tên) giữ nguyên", S("dịu nhỉ trời hôm nay", TV3) == "dịu nhỉ trời hôm nay")
check("người thứ ba: nhắn cho Diu ni giữ nguyên", S("nhắn cho Diu ni nhé", TV3) == "nhắn cho Diu ni nhé")
check("bộ từ vựng rỗng: trả y nguyên", nghe_sua.sua("Ưu ni ơi", []) == "Ưu ni ơi")

# ---- 5. Từ vựng người dùng khai: nhiều từ, cụm hai tiếng ----
TV2 = ["Uni", "OpenRouter", "Pancake"]
check("Open Router (tách) -> OpenRouter",
      S("đổi bộ não sang open router đi", TV2) == "đổi bộ não sang OpenRouter đi")
check("Pan cake -> Pancake", S("xem đơn trên pan cake", TV2) == "xem đơn trên Pancake")
check("Bánh kếp không thành Pancake", S("ăn bánh kếp", TV2) == "ăn bánh kếp")

# ---- 6. Rút bộ từ vựng từ settings + gợi ý cho Whisper ----
cfg = {"voice": {"hotwords": "OpenRouter, Pancake\n uni ; Zalo,, Pancake"}}
tv = nghe_sua.tu_vung(cfg)
check("Uni luôn đứng đầu, không nhân đôi dù người dùng gõ 'uni'", tv[0] == "Uni" and tv.count("Uni") == 1
      and not any(t.lower() == "uni" for t in tv[1:]))
check("tách bằng phẩy, chấm phẩy, xuống dòng; bỏ trùng", tv == ["Uni", "UNI MATE", "OpenRouter", "Pancake", "Zalo"])
check("không có cài đặt vẫn có Uni và UNI MATE", nghe_sua.tu_vung({}) == ["Uni", "UNI MATE"])
check("gợi ý Whisper là danh sách ngăn phẩy, khép dấu chấm",
      nghe_sua.goi_y_whisper(tv, ky_thuat=()) == "Uni, UNI MATE, OpenRouter, Pancake, Zalo.")
check("gợi ý rỗng khi không có từ", nghe_sua.goi_y_whisper([], ky_thuat=()) == "")

# ---- 7. Mồi thêm từ tiếng Anh hay nói xen (0.64.67: "GitHub Actions" thành "huyết áp Action") ----
gy = nghe_sua.goi_y_whisper(tv)
check("mặc định mồi kèm từ tiếng Anh thông dụng", "GitHub Actions" in gy and "deploy" in gy)
check("từ người dùng khai đứng CUỐI (Whisper chỉ giữ phần cuối prompt)",
      gy.endswith("Uni, UNI MATE, OpenRouter, Pancake, Zalo."))
gy2 = nghe_sua.goi_y_whisper(["Uni", "github"])
check("không nhân đôi từ người dùng đã khai (không phân biệt hoa thường)",
      [x.strip(" .").lower() for x in gy2.split(",")].count("github") == 1 and gy2.endswith("Uni, github."))
dai = ["Tu%02d dai dai dai dai" % i for i in range(20)]      # ~460 ký tự, chừa chỗ cho vài từ mồi
gy3 = nghe_sua.goi_y_whisper(dai)
check("quá trần thì bỏ bớt từ mồi chung, giữ nguyên từ người dùng",
      gy3.endswith(", ".join(dai) + ".") and len(gy3) <= nghe_sua.MAX_GOI_Y
      and gy3.startswith("GitHub") and "email" not in gy3)
check("vừa trần thì nằm trong MAX_GOI_Y", len(nghe_sua.goi_y_whisper(tv)) <= nghe_sua.MAX_GOI_Y)
check("từ mồi chung KHÔNG đi vào lớp sửa mờ", "GitHub" not in nghe_sua.tu_vung(cfg))

if _fails:
    print("\nFAIL:", len(_fails), _fails)
    raise SystemExit(1)
print("\nOK - nghe_sua")
