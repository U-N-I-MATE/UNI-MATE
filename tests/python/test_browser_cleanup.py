"""Gỡ khung trình duyệt (0.430.2) phải dọn sạch thứ nó để lại trên máy đã dùng.

    python tests/run.py browser_cleanup

Chủ repo gỡ tính năng 02/11/2026. Hồ sơ Chromium cũ chứa cookie đăng nhập thật (Gmail công ty...), không dọn thì nằm mãi trên
đĩa mà không còn giao diện nào để xoá. Test này dựng một hồ sơ giả (cổng DevTools đã chết) rồi kiểm dọn xong không còn gì, và
máy chưa từng dùng thì không bật luồng nào.
"""
from _paths import ROOT, SERVER  # noqa: E402,F401
import os
import sys
import tempfile
from pathlib import Path

os.environ["UNIMATE_STATE_DIR"] = tempfile.mkdtemp(prefix="unimate-bpclean-")

_fails = []


def check(ten, cond, them=""):
    print(("ok   " if cond else "FAIL ") + ten + (("  [" + str(them) + "]") if them and not cond else ""))
    if not cond:
        _fails.append(ten)


sys.path.insert(0, str(ROOT / "server"))
import browser_cleanup  # noqa: E402
import config as cfgmod  # noqa: E402

goc = Path(cfgmod.STATE_DIR)
check("máy chưa từng dùng khung: không bật luồng dọn", (browser_cleanup.chay_nen() or True)
      and not any(t.name == "don-trinh-duyet-cu" for t in __import__("threading").enumerate()))

ho_so = goc / "browser-profile"
(ho_so / "Default").mkdir(parents=True)
(ho_so / "Default" / "Cookies").write_bytes(b"cookie that")
(ho_so / "DevToolsActivePort").write_text("1\n/devtools/browser/x\n", encoding="utf-8")
(goc / "browser-pane.log").write_text("log", encoding="utf-8")
browser_cleanup.don()
check("hồ sơ (cookie đăng nhập) đã xoá", not ho_so.exists())
check("tệp nhật ký đã xoá", not (goc / "browser-pane.log").exists())

MAIN = (ROOT / "server" / "main.py").read_text(encoding="utf-8")
check("main gọi dọn lúc khởi động", "browser_cleanup.chay_nen()" in MAIN)
for f in ("server/browser_pane.py", "server/browser_ai.py", "server/routes/browser.py", "dashboard/browser-pane.js"):
    check(f"đã gỡ {f}", not (ROOT / f).exists())
HTML = (ROOT / "dashboard" / "index.html").read_text(encoding="utf-8")
check("giao diện không còn nút quả địa cầu / khung trình duyệt", "browserPaneBtn" not in HTML and "browserPane" not in HTML)

print()
if _fails:
    print(f"{len(_fails)} test HỎNG: " + ", ".join(_fails))
    sys.exit(1)
print("Tất cả test browser_cleanup đã qua.")
