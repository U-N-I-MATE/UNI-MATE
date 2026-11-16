"""0.453.2: Settings texts of the schedule machine (home PC + VPS).

    python tests/run.py chu_mcl_0453_2

The owner's test of 0.452.0 on 16/11/2026: the home PC banner read "Lịch đang chạy ở VPS (VPS)" (the VPS record synced
through GitHub had not arrived, so its name was empty), and the texts said GitHub sync is set in "Cài đặt, Sao lưu
GitHub" while it lives on the Self-learning page. Checks the name of the machine that runs schedules and the wording.
"""
from _paths import ROOT, SERVER  # noqa: E402,F401
import os
import sys
import tempfile
from pathlib import Path

os.environ["UNIMATE_STATE_DIR"] = tempfile.mkdtemp(prefix="unimate-mcl2-")
try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

import may_chay_lich as M  # noqa: E402

fails = []


def check(name, cond, extra=""):
    print(("ok   " if cond else "FAIL ") + name + ("" if cond or not extra else f"  [{extra}]"))
    if not cond:
        fails.append(name)


home = {"id": "b", "kind": "home", "label": "Nguyen-Huan"}
vps = {"id": "a", "kind": "vps", "label": "jin.unihq.vn"}
link = {"url": "https://jin.unihq.vn"}
check("linked home PC: the VPS is named by the address the code came from",
      M._runner_label("vps", home, link, None, home) == "jin.unihq.vn")
M._remote["vps"] = {"label": "srv-12"}
check("not linked: the VPS record it heard from", M._runner_label("vps", home, None, None, home) == "srv-12")
M._remote.pop("vps", None)
check("not linked, nothing heard: the synced record", M._runner_label("vps", home, None, vps, home) == "jin.unihq.vn")
check("nothing known: empty (the banner then shows the kind once)", M._runner_label("vps", home, None, None, home) == "")
check("on the VPS itself: its own name", M._runner_label("vps", vps, None, None, None) == "jin.unihq.vn")
check("home runs: the home PC's name", M._runner_label("home", vps, None, vps, home) == "Nguyen-Huan")

srcs = {p: (Path(ROOT) / p).read_text(encoding="utf-8") for p in
        ("server/may_chay_lich.py", "server/main.py", "CHANGELOG.md", "CHANGELOG.en.md",
         "docs/08-viec-dinh-ky.md", "docs/en/08-recurring-jobs.md")}
check("no text points to 'Cài đặt, Sao lưu GitHub' any more",
      not any("Cài đặt, Sao lưu GitHub" in s or "Settings, GitHub backup" in s for s in srcs.values()))
check("the warning names the Self-learning page", "trang Tự học, mục Đồng bộ brain với GitHub" in srcs["server/may_chay_lich.py"])
check("docs say where GitHub sync is set", "mục **⇅ Đồng bộ brain với GitHub (2 chiều)**" in srcs["docs/08-viec-dinh-ky.md"]
      and "**⇅ Sync brains with GitHub (two-way)**" in srcs["docs/en/08-recurring-jobs.md"])

print()
if fails:
    print(f"FAIL {len(fails)}: " + " | ".join(fails))
    sys.exit(1)
print("OK - test_chu_mcl_0453_2: tất cả pass")
