"""Facebook Page comments (0.448.0): comments under a Page's posts, read into the inbox on a timer by `fb_pages`.

Read only: there is no `gui`, so the inbox offers no reply box and no bot can stand on it. The account is a Page the
owner connected with the Facebook login on the Connections page; one conversation per post. Pages are listed by the
module itself (`tai_khoan`), like personal Zalo, and `bat` is the "record to the inbox" switch.
"""
from __future__ import annotations

from channels import KenhSpec

SPEC = KenhSpec(
    id="facebook", nhan="Bình luận Facebook", kind="account", logo="facebook", mau="#1877F2",
    tom_tat=("Bình luận dưới bài đăng của Fanpage, đọc 3 phút một lần. Chỉ đọc, chưa trả lời từ UNI MATE. "
             "Chưa được Meta duyệt thì không có tên người bình luận."),
    nang_luc={"nhom": False, "gui_chu": False, "gui_file": False},
    en={"nhan": "Facebook comments",
        "tom_tat": ("Comments under your Facebook Page's posts, read every 3 minutes. Read only, no replies from UNI MATE "
                    "yet. Until Meta approves the app, commenters show without a name.")},
)


def tai_khoan():
    import fb_pages
    return fb_pages.accounts()


def bat(account_id: str, on: bool) -> dict:
    import fb_pages
    return fb_pages.set_watch(account_id, on)
