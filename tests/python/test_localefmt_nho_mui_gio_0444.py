"""0.444.0: localefmt.tz() nhớ đối tượng múi giờ theo dấu của settings.json (đường dẫn, mtime_ns, size).

    python tests/run.py localefmt_nho_mui_gio_0444      (KHÔNG mạng)

Chủ dự án 04/11/2026, sau gốc của test_kanban_snapshot (0.443.0): `clock`/`at`/`now` gọi `tz()`, và `tz()` mỗi lần đọc lại
cài đặt (read_settings trúng đệm vẫn dựng lại cả cấu hình từ JSON). Phép kiểm ở đây ĐẾM số lần đọc, không đo thời gian,
nên không chập chờn theo máy.
"""
from _paths import ROOT, SERVER  # noqa: E402,F401
import os
import sys
import tempfile
import time
from pathlib import Path

os.environ["UNIMATE_STATE_DIR"] = tempfile.mkdtemp(prefix="unimate-0444-")
try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

_fails = []


def check(name, cond, them=""):
    print(("ok   " if cond else "FAIL ") + name + (("  [" + str(them)[:300] + "]") if not cond else ""))
    if not cond:
        _fails.append(name)


import config as cfgmod  # noqa: E402
import localefmt as L  # noqa: E402

_doc_that = cfgmod.read_settings
dem = {"n": 0}


def _doc_dem():
    dem["n"] += 1
    return _doc_that()


cfgmod.read_settings = _doc_dem

cfgmod.update_settings({"locale": {"tz": "Asia/Tokyo"}})
dem["n"] = 0
ts = 1793700000
ra = [L.clock(ts + i) for i in range(1000)] + [L.at(ts).isoformat() for _ in range(200)]
for _ in range(200):
    L.now()
    L.tz()
check(f"1.600 lần clock/at/now/tz chỉ đọc cài đặt {dem['n']} lần (phải là 1)", dem["n"] == 1, dem["n"])
check("múi giờ đúng cấu hình (Asia/Tokyo, UTC+9)", L.at(ts).utcoffset().total_seconds() == 9 * 3600, L.at(ts))
check("giờ ra giống hệt cách tính không nhớ",
      ra[0] == __import__("datetime").datetime.fromtimestamp(ts, L._tu_ten("Asia/Tokyo")).strftime("%Y-%m-%d %H:%M"))

# Ghi cài đặt -> có hiệu lực ngay lần gọi kế tiếp (dấu đổi), và chỉ đọc lại đúng một lần.
cfgmod.update_settings({"locale": {"tz": "Europe/Paris"}})
dem["n"] = 0
z = [L.tz() for _ in range(300)][-1]
check("đổi múi giờ trong cài đặt: lần gọi kế tiếp đã theo múi mới", str(z) == "Europe/Paris", z)
check(f"sau khi đổi chỉ đọc lại {dem['n']} lần cho 300 lần gọi (phải là 1)", dem["n"] == 1, dem["n"])

# Đổi chỗ tệp cài đặt (test, máy khác thư mục state) -> dấu khác, không dùng nhầm múi giờ cũ.
cu = cfgmod.SETTINGS_PATH
moi = Path(tempfile.mkdtemp(prefix="unimate-0444-b-")) / "settings.json"
cfgmod.SETTINGS_PATH = moi
try:
    cfgmod._SETTINGS_CACHE["sig"] = None
    cfgmod.update_settings({"locale": {"tz": "America/New_York"}})
    check("tệp cài đặt ở chỗ khác: theo đúng tệp đó", str(L.tz()) == "America/New_York", L.tz())
finally:
    cfgmod.SETTINGS_PATH = cu
    cfgmod._SETTINGS_CACHE["sig"] = None
check("quay về tệp cũ: lại đúng múi của tệp cũ", str(L.tz()) == "Europe/Paris", L.tz())

# Đọc lỗi thoáng qua (Windows khoá tệp): trả mặc định nhưng KHÔNG nhớ, kẻo kẹt mặc định tới lần ghi sau.
L._TZ_NHO["dau"] = None


def _hong():
    raise cfgmod.SettingsUnreadable("khoá thoáng qua")


cfgmod.read_settings = _hong
z = L.tz()
check("đọc lỗi: dùng múi mặc định, không ném lỗi", z is L._tu_ten(L.TEN_TZ_MAC_DINH), z)
cfgmod.read_settings = _doc_dem
check("đọc lỗi không bị nhớ: lần sau đọc được thì đúng múi thật", str(L.tz()) == "Europe/Paris", L.tz())

# Đọc từ bản dự phòng .bak: không nhớ, y như read_settings.
L._TZ_NHO["dau"] = None


def _tu_bak():
    c = _doc_that()
    cfgmod._DOC_TU_BAK[0] = True
    return c


cfgmod.read_settings = _tu_bak
L.tz()
check("đọc từ .bak: không nhớ", L._TZ_NHO["dau"] is None)
cfgmod._DOC_TU_BAK[0] = False
cfgmod.read_settings = _doc_dem
L.tz()
check("đọc tệp thật trở lại: nhớ như thường", L._TZ_NHO["dau"] is not None)

# Chưa có tệp cài đặt (máy mới): không có dấu để nhớ, vẫn ra múi mặc định.
cfgmod.SETTINGS_PATH = Path(tempfile.mkdtemp(prefix="unimate-0444-c-")) / "settings.json"
try:
    check("chưa có tệp cài đặt: múi mặc định Asia/Ho_Chi_Minh", str(L.tz()) == L.TEN_TZ_MAC_DINH, L.tz())
finally:
    cfgmod.SETTINGS_PATH = cu
cfgmod.read_settings = _doc_that

print()
if _fails:
    print(f"FAIL {len(_fails)}: {_fails}")
    sys.exit(1)
print("OK - test_localefmt_nho_mui_gio_0444: all pass")
