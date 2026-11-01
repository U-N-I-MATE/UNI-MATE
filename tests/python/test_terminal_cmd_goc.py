"""Terminal tab Code mở ở HOME (cmd gốc của máy) + PATH đủ để gõ `agy` chạy được.

    python tests/run.py terminal_cmd_goc     (KHÔNG mạng)

Báo cáo 16/08: nhiều máy cài Antigravity rồi mà "không đăng nhập được trên UNI MATE, đăng
nhập trong cmd của UNI MATE cũng rất khó". Ba bệnh chồng nhau:
1. Shell của tab Code mở ở GỐC BRAIN - agy coi thư mục đang đứng là project của nó nên
   đăng nhập trong brain vừa trục trặc vừa vấy file cấu hình vào vault. Chủ chốt: mở ở
   HOME như cmd gốc của máy.
2. PATH của server (systemd/Docker) cụt, thiếu ~/.local/bin - đúng chỗ installer thả
   `agy`. Gõ `agy` trong terminal của UNI MATE ra "command not found", tưởng cài hỏng.
3. Đăng nhập qua SSH bằng USER KHÁC (vd root) thì UNI MATE (user riêng) không thấy gì -
   lời hướng dẫn phải nói thẳng và chỉ vào trang Code của chính UNI MATE.
"""
from _paths import ROOT, SERVER  # noqa: E402,F401
import os
import sys
import tempfile
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

_fails = []


def check(name, cond):
    print(("ok   " if cond else "FAIL ") + name)
    if not cond:
        _fails.append(name)


import main      # noqa: E402
import terminal  # noqa: E402

# ---- 1. cwd mặc định = HOME, không còn là gốc brain ----
cu = os.environ.pop("UNIMATE_TERMINAL_CWD", None)
try:
    check("CANARY: terminal mở ở HOME của user chạy UNI MATE (cmd gốc của máy)",
          main._terminal_cwd("brain") == str(Path.home()))
    with tempfile.TemporaryDirectory() as td:
        os.environ["UNIMATE_TERMINAL_CWD"] = td
        check("UNIMATE_TERMINAL_CWD vẫn ghi đè được (ai muốn brain thì tự đặt)",
              main._terminal_cwd("brain") == td)
finally:
    os.environ.pop("UNIMATE_TERMINAL_CWD", None)
    if cu is not None:
        os.environ["UNIMATE_TERMINAL_CWD"] = cu

# ---- 2. PATH của shell được bù ngăn ~/.local/bin ----
lb = Path.home() / ".local" / "bin"
lb.mkdir(parents=True, exist_ok=True)   # tồn tại là điều kiện để được bù
env = terminal._env()
parts = env.get("PATH", "").split(os.pathsep)
check("CANARY: ~/.local/bin nằm trong PATH của terminal (gõ `agy` là thấy lệnh)",
      str(lb) in parts)
check("không nhân đôi ngăn đã có", parts.count(str(lb)) == 1)
env2 = terminal._env()
check("gọi lại vẫn không phình PATH", env2.get("PATH", "").split(os.pathsep).count(str(lb)) == 1)

# ---- 3. Biến UNIMATE_BRAIN đi vào env của shell ----
check("_env nhận extra (UNIMATE_BRAIN...)",
      terminal._env({"UNIMATE_BRAIN": "/duong/brain"}).get("UNIMATE_BRAIN") == "/duong/brain")
src = (SERVER / "main.py").read_text(encoding="utf-8")
check("WS terminal truyền UNIMATE_BRAIN cho shell (cd \"$UNIMATE_BRAIN\" là về brain)",
      '"UNIMATE_BRAIN": str(_brain_root(brain))' in src)
src_t = (SERVER / "terminal.py").read_text(encoding="utf-8")
check("Phien nhận extra_env và trộn vào env lúc mở shell",
      "extra_env" in src_t and "_env(self.extra_env)" in src_t)

# ---- 4. Hướng dẫn agy nói thẳng chuyện ĐÚNG USER ----
import antigravity_cli  # noqa: E402
hd = antigravity_cli.login_huong_dan()
check("hướng dẫn chỉ vào trang Code NGAY TRONG UNI MATE", "NGAY TRONG UNI MATE" in hd["ghi_chu"])
check("cảnh báo đăng nhập bằng user khác (root) là UNI MATE không thấy",
      "root" in hd["ghi_chu"])
src_a = (SERVER / "antigravity_cli.py").read_text(encoding="utf-8")
check("auth_status lúc chưa đăng nhập cũng nói đúng bệnh đúng-user",
      "ĐÚNG user đang chạy UNI MATE" in src_a)

if _fails:
    print(f"\nFAIL {len(_fails)} muc: " + ", ".join(_fails))
    sys.exit(1)
print("\nOK - test_terminal_cmd_goc: tat ca pass")
