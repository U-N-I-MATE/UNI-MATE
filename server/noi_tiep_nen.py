"""Việc nền giao từ khung chat xong thì UNI MATE tự mở một lượt tiếp trong đúng khung chat đó (0.453.0).

Vì sao có file này
==================
Chủ dự án báo 16/11/2026: giao việc nền xong (lệnh chạy ngầm, việc Kanban, việc giao Nhóm, quy trình chạy qua Kanban),
việc chạy xong thì UNI MATE chỉ dán kết quả vào khung chat rồi đứng im. Anh phải nhắn "việc nền đã xong, kiểm tra đi"
thì UNI MATE mới đọc kết quả và làm bước tiếp theo. Trước bản này chỉ lệnh chạy ngầm trên Linux/Mac, ở khung chat web,
khi AI đã dặn trước hay lỡ hứa mới có lượt tiếp, và khởi động lại máy chủ là mất.

Cách làm
========
1. Lúc việc được giao TRONG một lượt chat của chủ (web, Telegram), nơi giao việc gọi `dang_ky`. Việc mang khoá của
   lượt đã giao nó (`dot`, đợt) và chuỗi lượt tiếp nó thuộc về (`chuoi`, `do_sau`). Việc do lịch tự chạy (nhắc hẹn,
   loop), do một việc Kanban hay một bước của Nhóm giao thì không đăng ký: không ai đang chờ ở khung chat.
2. Việc kết thúc (xong, chờ duyệt, bị chặn, dừng) thì nơi báo kết quả gọi `xong`.
3. Vòng của máy chủ hỏi `dot_san_sang`: một đợt sẵn sàng khi lượt đã giao nó kết thúc VÀ mọi việc của đợt đã xong, hoặc
   việc đầu tiên đã xong được 30 phút (khi đó mở với những việc đã xong; việc xong sau thành đợt tiếp theo).
4. `quyet` xét trần (chủ duyệt 16/11): tối đa 3 lượt tiếp liên tiếp cho một chuỗi, 10 lượt tiếp mỗi giờ cho một khung
   chat. Quá trần thì chỉ báo, mời chủ nhắn "làm tiếp".
5. `nhan` đánh dấu đã dùng TRƯỚC khi mở lượt: một đợt không bao giờ mở hai lượt, kể cả máy chủ chết giữa chừng.

Mọi thứ nằm trong sqlite ở STATE_DIR nên sống qua lần khởi động lại máy chủ. Module KHÔNG import main: máy chủ cắm
hàm qua `noi` (lượt nào đang chạy, công tắc trong Cài đặt), test cắm hàm giả.
"""
from __future__ import annotations

import sqlite3
import threading
import time
from pathlib import Path
from typing import Callable, Dict, List, Optional

# Chủ duyệt 16/11/2026.
TRAN_CHUOI = 3            # lượt tiếp liên tiếp tối đa của một chuỗi
TRAN_GIO = 10             # lượt tiếp tối đa mỗi giờ của một khung chat
CHO_DOT = 30 * 60         # việc đầu tiên xong được chừng này mà đợt còn việc chạy thì mở với việc đã xong
# Việc đăng ký mà không bao giờ báo xong (máy chủ cũ mất sổ, việc bị xoá tay): sau chừng này thì thôi chờ nó.
TUOI_VIEC_CHAY = 2 * 86400
GIU_LAI = 30 * 86400      # bản ghi đã dùng giữ chừng này để tra lại
TRAN_KET_QUA = 4000       # ký tự kết quả giữ cho mỗi việc
TRAN_MOT_VIEC = 1500      # ký tự kết quả của MỘT việc đưa vào lời nhắc
TRAN_LOI_NHAC = 9000      # trần cả lời nhắc

LOAI = ("job", "task", "team")
KENH_LICH = ("reminder", "kanban", "loop", "team", "schedule")
# Kết cục của việc: mã -> câu cho model đọc.
KET_CUC = {
    "xong": "ĐÃ XONG",
    "cho_duyet": "XONG, ĐANG CHỜ CHỦ DUYỆT",
    "bi_chan": "BỊ CHẶN, CHƯA XONG",
    "huy": "ĐÃ HUỶ",
    "dung": "ĐÃ DỪNG GIỮA CHỪNG",
    "qua_han": "VẪN CHẠY QUÁ LÂU, UNI MATE NGỪNG THEO DÕI",
}
TEN_LOAI = {"job": "Lệnh chạy nền", "task": "Việc Kanban", "team": "Việc giao Nhóm"}

_KHOA = threading.RLock()
_DB: Optional[sqlite3.Connection] = None
_PATH: Optional[Path] = None

# Máy chủ cắm các hàm này (main.py). Mặc định là "không biết", để test và chạy lẻ không nổ.
_LUOT_FN: Callable[[str], Optional[dict]] = lambda chat: None          # chat -> {dot, chuoi, do_sau} của lượt đang chạy
_DANG_CHAY_FN: Callable[[str], bool] = lambda dot: False               # lượt mang khoá này còn chạy không
_BAT_FN: Callable[[], bool] = lambda: True                            # công tắc trong Cài đặt
_KENH_FN: Callable[[], str] = lambda: ""                               # kênh của lượt đang gọi (turn_context)


def noi(luot_fn=None, dang_chay_fn=None, bat_fn=None, kenh_fn=None) -> None:
    global _LUOT_FN, _DANG_CHAY_FN, _BAT_FN, _KENH_FN
    if luot_fn is not None:
        _LUOT_FN = luot_fn
    if dang_chay_fn is not None:
        _DANG_CHAY_FN = dang_chay_fn
    if bat_fn is not None:
        _BAT_FN = bat_fn
    if kenh_fn is not None:
        _KENH_FN = kenh_fn


def configure(path) -> None:
    global _DB, _PATH
    with _KHOA:
        if _DB is not None:
            try:
                _DB.close()
            except Exception:
                pass
        _DB = None
        _PATH = Path(path)


def _conn() -> sqlite3.Connection:
    global _DB
    if _DB is None:
        if _PATH is None:
            raise RuntimeError("noi_tiep_nen chưa configure")
        _PATH.parent.mkdir(parents=True, exist_ok=True)
        _DB = sqlite3.connect(str(_PATH), check_same_thread=False, timeout=10)
        _DB.row_factory = sqlite3.Row
        _DB.execute("""CREATE TABLE IF NOT EXISTS viec(
            khoa TEXT PRIMARY KEY, loai TEXT, ma TEXT, ten TEXT, chat TEXT, brain TEXT,
            dot TEXT, chuoi TEXT, do_sau INTEGER DEFAULT 0, lam_tiep INTEGER DEFAULT 1,
            trang TEXT DEFAULT 'chay', ket TEXT DEFAULT '', noi_dung TEXT DEFAULT '',
            da_dung INTEGER DEFAULT 0, tao REAL, xong_luc REAL DEFAULT 0)""")
        _DB.execute("CREATE INDEX IF NOT EXISTS viec_dot ON viec(dot)")
        _DB.execute("CREATE TABLE IF NOT EXISTS luot(chat TEXT, at REAL, dot TEXT, do_sau INTEGER)")
        _DB.commit()
    return _DB


def bat() -> bool:
    try:
        return bool(_BAT_FN())
    except Exception:
        return True


def chat_ho_tro(chat: str) -> bool:
    """Khung chat mở được lượt tiếp: web của dashboard, hay chat Telegram của chủ (mã số, có thể âm với nhóm)."""
    c = str(chat or "").strip()
    if c.startswith("web:"):
        return len(c) > 4
    return c.lstrip("-").isdigit()


def dang_ky(chat: str, loai: str, ma: str, ten: str = "", brain: str = "", lam_tiep: bool = True,
            luot: Optional[dict] = None, now: float = 0.0) -> bool:
    """Ghi một việc nền vừa giao trong một lượt chat của chủ. True khi đã ghi (việc này sẽ mở lượt tiếp khi xong).

    `luot` = {dot, chuoi, do_sau} của lượt đã giao việc; không truyền thì hỏi máy chủ lượt nào đang chạy ở khung chat
    này. Không có lượt nào chạy (việc do lịch, trang Nhiệm vụ, một việc nền khác giao) thì không ghi."""
    chat, ma = str(chat or "").strip(), str(ma or "").strip()
    if loai not in LOAI or not ma or not chat_ho_tro(chat):
        return False
    try:
        if str(_KENH_FN() or "") in KENH_LICH:
            return False
    except Exception:
        pass
    if luot is None:
        try:
            luot = _LUOT_FN(chat)
        except Exception:
            luot = None
    if not luot or not str(luot.get("dot") or ""):
        return False
    dot = str(luot["dot"])
    with _KHOA:
        c = _conn()
        c.execute("""INSERT OR IGNORE INTO viec(khoa, loai, ma, ten, chat, brain, dot, chuoi, do_sau, lam_tiep, tao)
                     VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
                  (f"{loai}:{ma}", loai, ma, str(ten or "")[:300], chat, str(brain or ""), dot,
                   str(luot.get("chuoi") or dot), int(luot.get("do_sau") or 0), 1 if lam_tiep else 0,
                   float(now or time.time())))
        c.commit()
    return True


def dat_lam_tiep(loai: str, ma: str, on: bool) -> bool:
    """Bật/tắt lượt tiếp cho MỘT việc (tool giao việc nhận `lam_tiep=false`). True khi việc có trong sổ."""
    with _KHOA:
        c = _conn()
        cur = c.execute("UPDATE viec SET lam_tiep=? WHERE khoa=?", (1 if on else 0, f"{loai}:{ma}"))
        c.commit()
        return bool(cur.rowcount)


def co(loai: str, ma: str) -> bool:
    with _KHOA:
        return _conn().execute("SELECT 1 FROM viec WHERE khoa=?", (f"{loai}:{ma}",)).fetchone() is not None


def xong(loai: str, ma: str, ket: str, noi_dung: str = "", now: float = 0.0) -> Optional[dict]:
    """Một việc đã đăng ký vừa kết thúc. Trả bản ghi (None khi việc không do chat giao, hoặc đã báo đúng kết cục này).

    Việc đã dùng cho một lượt tiếp mà đổi kết cục (bị chặn rồi được gỡ và xong) thì được tính lại: lượt tiếp mới
    sẽ đọc kết cục mới."""
    ket = ket if ket in KET_CUC else "xong"
    khoa = f"{loai}:{ma}"
    with _KHOA:
        c = _conn()
        r = c.execute("SELECT * FROM viec WHERE khoa=?", (khoa,)).fetchone()
        if r is None:
            return None
        if r["trang"] == "xong" and r["ket"] == ket:
            return None
        c.execute("UPDATE viec SET trang='xong', ket=?, noi_dung=?, xong_luc=?, da_dung=0 WHERE khoa=?",
                  (ket, str(noi_dung or "")[:TRAN_KET_QUA], float(now or time.time()), khoa))
        c.commit()
        return dict(c.execute("SELECT * FROM viec WHERE khoa=?", (khoa,)).fetchone())


def _don(now: float) -> None:
    c = _conn()
    c.execute("DELETE FROM viec WHERE da_dung=1 AND xong_luc > 0 AND xong_luc < ?", (now - GIU_LAI,))
    c.execute("DELETE FROM viec WHERE trang='chay' AND tao < ?", (now - TUOI_VIEC_CHAY,))
    c.execute("DELETE FROM luot WHERE at < ?", (now - GIU_LAI,))


def dot_san_sang(now: float = 0.0) -> List[dict]:
    """Các đợt mở được lượt tiếp lúc này: {dot, chat, brain, chuoi, do_sau, viec: [...], con_chay}."""
    now = float(now or time.time())
    out: List[dict] = []
    with _KHOA:
        c = _conn()
        _don(now)
        dots = [r["dot"] for r in c.execute(
            "SELECT DISTINCT dot FROM viec WHERE trang='xong' AND da_dung=0").fetchall()]
        for dot in dots:
            try:
                if _DANG_CHAY_FN(dot):
                    continue          # lượt đã giao việc còn chạy: có thể còn giao thêm việc vào đợt này
            except Exception:
                pass
            rows = [dict(r) for r in c.execute("SELECT * FROM viec WHERE dot=? ORDER BY tao", (dot,)).fetchall()]
            cho = [r for r in rows if r["trang"] == "xong" and not r["da_dung"]]
            chay = [r for r in rows if r["trang"] == "chay"]
            if not cho:
                continue
            dau = min(float(r["xong_luc"] or now) for r in cho)
            if chay and now - dau < CHO_DOT:
                continue
            if not any(r["lam_tiep"] and r["ket"] != "huy" for r in cho):
                # Chỉ toàn việc chủ dặn không làm tiếp, hay việc chính người dùng/model đã huỷ: dùng luôn, không mở gì.
                c.executemany("UPDATE viec SET da_dung=1 WHERE khoa=?", [(r["khoa"],) for r in cho])
                c.commit()
                continue
            out.append({"dot": dot, "chat": cho[0]["chat"], "brain": next((r["brain"] for r in cho if r["brain"]), ""),
                        "chuoi": cho[0]["chuoi"], "do_sau": max(int(r["do_sau"] or 0) for r in cho),
                        "viec": cho, "con_chay": len(chay)})
    return out


def nhan(dot: dict) -> List[dict]:
    """Đánh dấu các việc của đợt là đã dùng, TRƯỚC khi mở lượt. Trả các việc giành được (rỗng = nơi khác đã giành)."""
    got = []
    with _KHOA:
        c = _conn()
        for r in dot.get("viec") or []:
            cur = c.execute("UPDATE viec SET da_dung=1 WHERE khoa=? AND da_dung=0 AND trang='xong'", (r["khoa"],))
            if cur.rowcount:
                got.append(r)
        c.commit()
    return got


def so_luot_gio(chat: str, now: float = 0.0) -> int:
    now = float(now or time.time())
    with _KHOA:
        r = _conn().execute("SELECT COUNT(*) FROM luot WHERE chat=? AND at > ?", (str(chat), now - 3600)).fetchone()
    return int(r[0] or 0)


def quyet(dot: dict, now: float = 0.0) -> tuple:
    """("mo", độ sâu lượt tiếp) | ("tat", 0) | ("tran_chuoi", độ sâu) | ("tran_gio", số lượt trong giờ)."""
    if not bat():
        return "tat", 0
    sau = int(dot.get("do_sau") or 0) + 1
    if sau > TRAN_CHUOI:
        return "tran_chuoi", sau - 1
    n = so_luot_gio(dot.get("chat") or "", now)
    if n >= TRAN_GIO:
        return "tran_gio", n
    return "mo", sau


def ghi_luot(chat: str, dot: str, do_sau: int, now: float = 0.0) -> None:
    with _KHOA:
        c = _conn()
        c.execute("INSERT INTO luot(chat, at, dot, do_sau) VALUES (?,?,?,?)",
                  (str(chat), float(now or time.time()), str(dot), int(do_sau)))
        c.commit()


def _cat(s: str, n: int) -> str:
    s = str(s or "").strip()
    return s if len(s) <= n else s[:n].rstrip() + " ... (cắt bớt, xem đủ trong khung chat hoặc trang Nhiệm vụ)"


def mot_dong(r: dict) -> str:
    ten = r.get("ten") or r.get("ma") or ""
    if r.get("loai") == "job":
        dau = f"{TEN_LOAI['job']} `{ten}`"
    else:
        dau = f"{TEN_LOAI.get(r.get('loai'), 'Việc')} \"{ten}\" (mã {r.get('ma')})"
    return f"{dau}: {KET_CUC.get(r.get('ket'), r.get('ket') or 'ĐÃ XONG')}"


def loi_nhac(dot: dict, do_sau: int, da_lam: Optional[List[str]] = None) -> str:
    """Tin mở lượt tiếp. Lưu vào khung chat như một tin có đánh dấu rõ, nên mở lại hội thoại vẫn hiểu vì sao UNI MATE
    tự nói tiếp."""
    viec = list(dot.get("viec") or [])
    dong = [f"[UNI MATE tự làm tiếp: việc nền đã xong, lượt tiếp {do_sau}/{TRAN_CHUOI}]",
            "Các việc nền giao ở lượt trước đã kết thúc:"]
    con = TRAN_LOI_NHAC - 1500
    for i, r in enumerate(viec, 1):
        dong.append(f"{i}. {mot_dong(r)}")
        nd = _cat(r.get("noi_dung") or "", min(TRAN_MOT_VIEC, max(300, con // max(1, len(viec)))))
        if nd:
            dong.append("   Kết quả: " + nd.replace("\n", "\n   "))
    if int(dot.get("con_chay") or 0):
        dong.append(f"Còn {dot['con_chay']} việc của cùng đợt vẫn đang chạy quá 30 phút; xong UNI MATE sẽ mở lượt khác.")
    if da_lam:
        dong.append("Thao tác ra ngoài ĐÃ làm trong chuỗi này (KHÔNG làm lại): " + "; ".join(da_lam[:20]))
    dong += [
        "Việc của bạn bây giờ:",
        "- Đọc kết quả, tự đánh giá từng việc ĐẠT hay CHƯA ĐẠT so với yêu cầu ban đầu của người dùng, nói rõ căn cứ.",
        "- Còn bước tiếp theo trong kế hoạch đã thống nhất thì làm luôn trong lượt này. Không còn bước nào thì tóm tắt "
        "kết quả cuối cùng cho người dùng rồi dừng, không giao thêm việc chỉ để giao.",
        "- Việc đang CHỜ CHỦ DUYỆT: KHÔNG tự duyệt thay chủ. Chỉ làm những bước không phụ thuộc việc duyệt, rồi nhắc "
        "chủ duyệt ở trang Nhiệm vụ.",
        "- Thao tác ra ngoài (gửi tin, đăng bài, tạo đơn, gửi email) đã làm ở lượt trước thì không làm lại.",
        f"- Đây là lượt tự làm tiếp thứ {do_sau}/{TRAN_CHUOI}. Sau lượt thứ {TRAN_CHUOI} UNI MATE dừng tự làm tiếp "
        "và chờ người dùng nhắn.",
    ]
    text = "\n".join(dong)
    return text if len(text) <= TRAN_LOI_NHAC else text[:TRAN_LOI_NHAC]


def cau_khong_mo(ly_do: str, dot: dict, so: int = 0) -> str:
    """Câu báo cho chủ khi đợt đã xong mà KHÔNG mở lượt tiếp (quá trần, công tắc tắt, khung chat không hỗ trợ)."""
    viec = list(dot.get("viec") or [])
    ds = "\n".join(f"- {mot_dong(r)}" for r in viec)
    if ly_do == "tran_chuoi":
        dau = (f"UNI MATE đã tự làm tiếp {TRAN_CHUOI} lượt liên tiếp nên dừng ở đây. "
               "Nhắn \"làm tiếp\" nếu muốn UNI MATE đi tiếp.")
    elif ly_do == "tran_gio":
        dau = (f"Khung chat này đã có {so} lượt tự làm tiếp trong một giờ (trần {TRAN_GIO}), nên UNI MATE chưa tự làm "
               "tiếp. Nhắn \"làm tiếp\" nếu muốn đi tiếp.")
    elif ly_do == "kenh":
        dau = "Kênh này chưa mở được lượt tự làm tiếp. Nhắn \"làm tiếp\" để UNI MATE đọc kết quả và làm bước tiếp theo."
    else:
        return ""
    return dau + ("\n\n" + ds if ds else "")


def xem(chat: str = "", tran: int = 30) -> List[dict]:
    """Các việc gần đây (cho trang chẩn đoán và test)."""
    with _KHOA:
        q = "SELECT * FROM viec" + (" WHERE chat=?" if chat else "") + " ORDER BY tao DESC LIMIT ?"
        args = (chat, tran) if chat else (tran,)
        return [dict(r) for r in _conn().execute(q, args).fetchall()]


def _reset_for_tests() -> Dict[str, int]:
    with _KHOA:
        c = _conn()
        c.execute("DELETE FROM viec")
        c.execute("DELETE FROM luot")
        c.commit()
    return {"ok": 1}
