"""Phần nối của việc chạy nền vào main.py: báo xong đúng kênh, mở lượt nối tiếp, có trần (0.64.66).

0.453.0: lượt nối tiếp không còn mở thẳng từ đây mà qua sổ noi_tiep_nen (gộp theo đợt, trần 3 lượt liên tiếp và 10
lượt mỗi giờ, sống qua lần khởi động lại; xem test_noi_tiep_nen_0453.py). Ở đây kiểm phần báo xong và việc ghi sổ.

    python tests/run.py tien_trinh_nen_main
"""
import os
import tempfile
import time

from _paths import ROOT, SERVER  # noqa: E402,F401

os.environ.setdefault("UNIMATE_STATE_DIR", tempfile.mkdtemp(prefix="unimate-ttnm-"))
import asyncio  # noqa: E402

import main  # noqa: E402
import tien_trinh_nen as T  # noqa: E402

fails = []


def check(name, cond, extra=""):
    print(("ok   " if cond else "FAIL ") + name + (f"  [{extra}]" if extra and not cond else ""))
    if not cond:
        fails.append(name)


bao = []


async def gia_notify(owner, text, **kw):
    bao.append((owner, text, kw))
    return True, ""

main._notify_owner = gia_notify

chay_tiep = []


async def runner(text, do_sau):
    chay_tiep.append((text, do_sau))

brain_root = tempfile.mkdtemp(prefix="unimate-ttnm-brain-")
os.makedirs(os.path.join(brain_root, "exports"))
video = os.path.join(brain_root, "exports", "gioi-thieu.mp4")
open(video, "w").close()


def viec(**kw):
    v = {"id": "j1", "pgid": 1, "mo_ta": "ffmpeg -i in.mp4 out.mp4", "cwd": brain_root,
         "brain_root": brain_root, "chat_id": "web:s1", "bat_dau": time.time() - 250,
         "ket_thuc": time.time(), "trang_thai": "xong", "sau_khi_xong": "ghép tiếng, gửi video",
         "noi_tiep": True, "do_sau": 0, "file_moi": [video]}
    v.update(kw)
    return v


async def chay(v):
    await main._khi_tien_trinh_xong(v)
    await asyncio.sleep(0.05)      # lượt nối tiếp đi bằng create_task

main._NOI_TIEP_WEB["s1"] = runner
import noi_tiep_nen as N  # noqa: E402
LUOT = {"dot": "turn-a", "chuoi": "turn-a", "do_sau": 0}

# 1. Việc do lượt chat của chủ giao (đã ghi sổ), xong: báo, KHÔNG mở thẳng runner, sổ mở đợt
N.dang_ky("web:s1", "job", "j1", "ffmpeg -i in.mp4 out.mp4", brain=brain_root, luot=LUOT)
asyncio.run(chay(viec()))
check("báo xong về đúng khung chat đã giao", bao and bao[-1][0] == "web:s1")
kw = bao[-1][2] if bao else {}
check("báo xong mang thẻ việc chạy nền (kind job, done)",
      (kw.get("viec") or {}).get("kind") == "job" and (kw.get("viec") or {}).get("status") == "done")
check("báo xong có link file mới, đường dẫn tương đối trong brain",
      bool(bao) and "[gioi-thieu.mp4](exports/gioi-thieu.mp4)" in bao[-1][1], bao[-1][1] if bao else "")
check("báo xong nói thời gian chạy", bool(bao) and "4 phút" in bao[-1][1], bao[-1][1] if bao else "")
check("báo xong nói UNI MATE tự làm tiếp", bool(bao) and "tự xem kết quả rồi làm tiếp" in bao[-1][1])
check("không mở thẳng lượt nối tiếp từ đây (sổ noi_tiep_nen lo)", chay_tiep == [])
d = [x for x in N.dot_san_sang() if x["dot"] == "turn-a"]
check("sổ có đợt sẵn sàng, kết quả mang lời dặn",
      len(d) == 1 and "Lời dặn khi xong: ghép tiếng, gửi video" in d[0]["viec"][0]["noi_dung"], d)
if d:
    N.nhan(d[0])

# 2. Việc không ghi sổ mà model đã dặn: chỉ báo, mời nhắn "làm tiếp"
bao.clear(); chay_tiep.clear()
asyncio.run(chay(viec(id="j2")))
check("việc ngoài sổ thì mời nhắn 'làm tiếp'", bool(bao) and "làm tiếp" in bao[-1][1] and chay_tiep == [])

# 3. Không dặn, không hứa, ngoài sổ: chỉ báo
bao.clear(); chay_tiep.clear()
asyncio.run(chay(viec(id="j3", noi_tiep=False, sau_khi_xong="")))
check("không dặn không hứa thì chỉ báo, không mở lượt", len(bao) == 1 and chay_tiep == []
      and "làm tiếp" not in bao[-1][1])

# 4. Telegram: việc ghi sổ thì cũng tự làm tiếp (0.453.0)
bao.clear(); chay_tiep.clear()
N.dang_ky("12345", "job", "j4", "build", luot={"dot": "turn-b", "chuoi": "turn-b", "do_sau": 0})
asyncio.run(chay(viec(id="j4", chat_id="12345")))
check("Telegram: báo về đúng chat_id", bool(bao) and bao[-1][0] == "12345")
check("Telegram: báo tự làm tiếp, đợt vào sổ",
      chay_tiep == [] and "tự xem kết quả" in bao[-1][1] and any(x["dot"] == "turn-b" for x in N.dot_san_sang()))

# 5. Bị dừng: báo 'đã dừng', không nối tiếp
bao.clear(); chay_tiep.clear()
N.dang_ky("web:s1", "job", "j5", "sleep", luot={"dot": "turn-c", "chuoi": "turn-c", "do_sau": 0})
asyncio.run(chay(viec(id="j5", trang_thai="huy")))
check("bị dừng thì thẻ cancelled và không nối tiếp",
      (bao[-1][2].get("viec") or {}).get("status") == "cancelled" and chay_tiep == []
      and not any(x["dot"] == "turn-c" for x in N.dot_san_sang()))

# 6. Câu báo nhận theo dõi: không có gì chạy ngầm thì rỗng
cau = asyncio.run(main._nhan_nuoi_tien_trinh("chat:khong-co:1", "brain", "web:s9", "xong"))
check("không có gì chạy ngầm thì không báo gì", cau == "")

# 7. Khối xử lý Telegram không tự hứa làm tiếp
src = (SERVER / "main.py").read_text(encoding="utf-8")
check("Telegram nhận theo dõi với tu_lam_tiep=False", "tu_lam_tiep=False" in src)

if fails:
    raise SystemExit(f"\nFAIL - test_tien_trinh_nen_main: {len(fails)} lỗi")
print("\nOK - test_tien_trinh_nen_main: tất cả pass")
