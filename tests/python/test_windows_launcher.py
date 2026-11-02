"""Windows mở UNI MATE như một app - bản đối xứng của bộ launcher macOS (PR #3).

    python tests/run.py windows_launcher

Không chạy được .bat/.ps1 trên CI Linux nên đây là test TĨNH: canh các bất biến mà
vi phạm là hành vi hỏng thật, không canh câu chữ trang trí.

Bất biến quan trọng nhất: "UNI MATE.bat" phải THĂM DÒ /health TRƯỚC khi gọi
start-unimate.vbs - vì vbs đó LUÔN kill instance cũ trước khi bật. Thiếu bước thăm dò
là double-click lần hai (mở lại cửa sổ) thành restart server, giết sạch việc nền
đang chạy dở. Đó là loại lỗi bấm thấy chạy được ngay nên không ai nghi ngờ.
"""
from _paths import ROOT, SERVER  # noqa: E402,F401
import sys

_fails = []


def check(ten, cond, them=""):
    print(("ok   " if cond else "FAIL ") + ten + (("  [" + str(them) + "]") if them and not cond else ""))
    if not cond:
        _fails.append(ten)


BAT = ROOT / "UNI MATE.bat"
AS_BAT = ROOT / "unimate-autostart.bat"
AS_PS1 = ROOT / "unimate-autostart.ps1"

check("có UNI MATE.bat ở gốc repo (đối xứng UNI MATE.app bên Mac)", BAT.exists())
check("có unimate-autostart.bat + .ps1", AS_BAT.exists() and AS_PS1.exists())

bat = BAT.read_text(encoding="utf-8")
ps1 = AS_PS1.read_text(encoding="utf-8")
as_bat = AS_BAT.read_text(encoding="utf-8")

# ---- UNI MATE.bat ----
i_health = bat.find("/health")
i_vbs = bat.find("wscript //nologo start-unimate.vbs")   # dòng GỌI thật, không phải comment nhắc tên
check("CANARY: thăm dò /health TRƯỚC khi gọi start-unimate.vbs (vbs kill instance cũ - "
      "thiếu bước này là double-click lần hai giết việc nền đang chạy)",
      0 < i_health < i_vbs)
check("tôn trọng UNIMATE_PORT, không hardcode một cổng", "UNIMATE_PORT" in bat)
check("mở dạng cửa sổ app (--app=), không chỉ mở tab trần", "--app=" in bat)
check("có fallback trình duyệt mặc định khi không có Edge/Chrome", 'start "" %URL%' in bat)
check("máy thiếu curl vẫn mở được (Windows cũ)", "where curl" in bat)
check("chờ server lên có GIỚI HẠN, không xoay vô hạn", "gtr 45" in bat or "gtr 40" in bat)
check("cd /d về thư mục script trước (không tin working directory kế thừa - "
      "cùng bài học với start-unimate.vbs)", 'cd /d "%~dp0"' in bat)

# ---- 0.429.7: bấm biểu tượng lần hai chỉ đưa cửa sổ cũ lên, không mở thêm ----
# Chủ repo 02/11/2026: "Khi đã mở sẵn 1 cửa sổ thì dù có bấm lại vào biểu tượng trên màn hình bao
# nhiêu lần thì vẫn sẽ chỉ mở cửa sổ đang bật thôi". Trước đó bước :open luôn gọi Edge --app nên mỗi
# lần bấm thêm một cửa sổ.
FOCUS = ROOT / "focus-unimate.ps1"
check("có focus-unimate.ps1 ở gốc repo", FOCUS.exists())
focus = FOCUS.read_text(encoding="utf-8") if FOCUS.exists() else ""
i_open = bat.find(":open")
i_focus = bat.find("focus-unimate.ps1", i_open)
i_app = bat.find("--app=", i_open)
check("UNI MATE.bat: dò cửa sổ đang mở TRƯỚC khi mở cửa sổ app mới",
      0 < i_open < i_focus < i_app, (i_open, i_focus, i_app))
check("UNI MATE.bat: tìm thấy cửa sổ thì dừng, không mở thêm",
      "if not errorlevel 1 goto :eof" in bat[i_focus:i_app])
check("UNI MATE.bat: thiếu file dò vẫn mở được như cũ (if exist)",
      'if exist "%~dp0focus-unimate.ps1"' in bat)
_vbs = (ROOT / "start-unimate.vbs").read_text(encoding="utf-8")
_i_sub = _vbs.find("Sub MoDashboard()")
_i_f = _vbs.find("focus-unimate.ps1", _i_sub)
_i_c = _vbs.find("cands = Array(", _i_sub)
check("start-unimate.vbs /open: cũng dò cửa sổ đang mở trước khi mở mới",
      0 < _i_sub < _i_f < _i_c and "= 0 Then Exit Sub" in _vbs[_i_f:_i_c], (_i_sub, _i_f, _i_c))
check("focus-unimate.ps1: khớp ĐÚNG tiêu đề (tab VPS trong trình duyệt có đuôi tên trình duyệt, không bị nhầm)",
      "sb.ToString() == tieuDe" in focus and '$Title = "UNI MATE"' in focus)
check("focus-unimate.ps1: chỉ khôi phục khi đang thu nhỏ (cửa sổ phóng to giữ nguyên)",
      "if (IsIconic(h)) ShowWindow(h, 9);" in focus)
check("focus-unimate.ps1: lỗi bất kỳ trả 1 (mở cửa sổ mới), không bao giờ bấm mà không thấy gì",
      "} catch {" in focus and focus.rstrip().endswith("}") and "exit 1" in focus.split("} catch {")[-1])
check("tiêu đề trang dashboard đúng là UNI MATE (ps1 dò theo tiêu đề này)",
      "<title>UNI MATE</title>" in (ROOT / "dashboard" / "index.html").read_text(encoding="utf-8"))

# ---- autostart ----
# 0.306.0: autostart ghi CHUNG một mục với nút trong dashboard (HKCU Run "UniMateOS"), không còn shortcut trong
# Startup: hai mục cùng bật là lúc đăng nhập hai bản UNI MATE giành nhau cổng 8688.
check("autostart ghi HKCU Run (không cần admin), cùng tên với dashboard",
      "CurrentVersion\\Run" in ps1 and '$Name = "UniMateOS"' in ps1)
check("lệnh trỏ wscript + start-unimate.vbs /open (chạy nền rồi mở dashboard)",
      "wscript.exe //nologo" in ps1 and "start-unimate.vbs" in ps1 and '`" /open"' in ps1)
check("có đủ ba việc install/uninstall/status", all(k in ps1 for k in ("install", "uninstall", "status")))
check("uninstall xoá mục Run và dọn shortcut kiểu cũ", "Remove-ItemProperty -Path $RunKey -Name $Name" in ps1 and "Remove-Item $Lnk" in ps1)
check("wrapper .bat gọi ps1 với ExecutionPolicy Bypass (máy user mặc định chặn ps1)",
      "ExecutionPolicy Bypass" in as_bat)

# ---- README hai thứ tiếng đều chỉ tới launcher ----
vi = (ROOT / "docs" / "i18n" / "vi" / "README.md").read_text(encoding="utf-8")
en = (ROOT / "README.md").read_text(encoding="utf-8")
check("README (vi) nhắc UNI MATE.bat", "UNI MATE.bat" in vi and "unimate-autostart.bat" in vi)
check("README (en) nhắc UNI MATE.bat", "UNI MATE.bat" in en and "unimate-autostart.bat" in en)

# ---- không em dash (luật repo, TTS khựng) ----
for ten, s in (("UNI MATE.bat", bat), ("unimate-autostart.ps1", ps1), ("unimate-autostart.bat", as_bat),
                ("focus-unimate.ps1", focus)):
    check(f"{ten} không dùng em dash", "—" not in s)

print()
if _fails:
    print(f"{len(_fails)} test HỎNG: " + ", ".join(_fails))
    sys.exit(1)
print("Tất cả test windows_launcher đã qua.")
