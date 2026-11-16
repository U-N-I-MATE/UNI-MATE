"""0.453.2: Settings texts of the schedule machine (home PC + VPS).

    python tests/run.py chu_mcl_0453_2

The owner's test of 0.452.0 on 16/11/2026: the home PC banner read "Lịch đang chạy ở VPS (VPS)" (the VPS record synced
through GitHub had not arrived, so its name was empty), and the texts said GitHub sync is set in "Cài đặt, Sao lưu
GitHub" while it lives on the Self-learning page. Checks the name of the machine that runs schedules and the wording.

Also (owner approved 16/11 13:48): a linked home PC reads done / next run of what the VPS runs from the VPS itself (a
13:35 reminder the VPS had fired still showed pending at home with a ▷ button); ▷ on the machine that does not run a
schedule is refused; the bell read "Nhắc bạn: Nhắc anh: ..." and now shows the reminder as written.
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

# ---- state of what the VPS runs, on a linked home PC ----
import asyncio  # noqa: E402
import json  # noqa: E402
import time  # noqa: E402

ROOTB = Path(tempfile.mkdtemp(prefix="unimate-mcl2-brain-")) / "Brain Default"
(ROOTB / "UniMate").mkdir(parents=True)
(ROOTB / "UniMate" / "reminders.json").write_text(json.dumps({"reminders": [
    {"id": "r1", "status": "done", "due_at": 100, "fired_at": 101, "result": "Đã nhắc", "text": "x", "chay_tren": ""},
    {"id": "r2", "status": "pending", "due_at": 200, "chay_tren": "home"}]}), encoding="utf-8")
(ROOTB / "UniMate" / "loop-state.json").write_text(json.dumps({"dang-bai": {"last_run": 555, "last_status": "ok"}}),
                                                    encoding="utf-8")
M.wire(lambda: [str(ROOTB)], lambda: {"ok": True}, lambda: True, None)
st = M.remote_lich()
check("VPS side: reminder and loop state per brain folder",
      st["brains"]["Brain Default"]["reminders"]["r1"]["status"] == "done"
      and st["brains"]["Brain Default"]["loops"]["dang-bai"]["last_run"] == 555, st)

# Home PC linked, VPS runs the schedules.
M._load_orig = M._load
M._link = lambda: {"url": "https://jin.unihq.vn", "key": "k"}
M.linked = lambda: True
M.effective_runner = lambda: "vps"
M.machine = lambda: dict(home)


async def fake_http(method, path, body=None, link=None):
    assert path == "/may-chay-lich/remote/lich"
    return st


M._http = fake_http
check("home PC fetches the VPS state", asyncio.run(M.pull_lich(force=True)) is True)
mine = {"id": "r1", "status": "pending", "due_at": 100, "chay_tren": "", "text": "x"}
seen = M.theo_may_chay(str(ROOTB), mine)
check("a reminder the VPS runs shows as the VPS sees it (done, its result)",
      seen["status"] == "done" and seen["fired_at"] == 101 and seen["result"] == "Đã nhắc" and seen["text"] == "x", seen)
pinned = {"id": "r2", "status": "pending", "chay_tren": "home"}
check("a reminder pinned to this home PC keeps its own state", M.theo_may_chay(str(ROOTB), pinned) is pinned)
ls = M.loop_state_theo_may_chay(str(ROOTB), {"dang-bai": {"last_run": 1, "enabled": True}}, {"dang-bai": ""})
check("a loop the VPS runs shows the VPS's last run", ls["dang-bai"]["last_run"] == 555 and ls["dang-bai"]["enabled"])
check("a loop pinned here keeps its own state",
      M.loop_state_theo_may_chay(str(ROOTB), {"dang-bai": {"last_run": 1}}, {"dang-bai": "home"})["dang-bai"]["last_run"] == 1)
M._lich["at"] = time.time() - M.LICH_MAX_AGE_S - 1
check("a stale copy from the VPS is not used", M.theo_may_chay(str(ROOTB), mine) is mine)
check("the name used in a refusal", M.ten_may_chay("") == "VPS (jin.unihq.vn)", M.ten_may_chay(""))

src_r = (Path(SERVER) / "reminders.py").read_text(encoding="utf-8")
src_l = (Path(SERVER) / "self_improve.py").read_text(encoding="utf-8")
src_m = (Path(SERVER) / "main.py").read_text(encoding="utf-8")
check("▷ on a reminder this machine does not run is refused, naming the machine that runs it",
      'if not may_chay_lich.should_run(cur.get("chay_tren")):' in src_r and '"other_machine": True' in src_r)
check("▷ on a loop this machine does not run is refused", 'if not may_chay_lich.should_run(lp.get("chay_tren")):' in src_l
      and '"other_machine": True' in src_l)
check("the reminder list and the Tasks page read the VPS state", "await may_chay_lich.pull_lich()" in src_r
      and "await may_chay_lich.pull_lich()" in src_m and "loop_state_theo_may_chay(" in src_m)
check("the VPS route is behind the link key and public only on its exact path",
      '"/may-chay-lich/remote/lich")' in src_m and 'def may_chay_lich_remote_lich(request: Request):' in src_m)

# ---- the reminder wording ----
import reminders as R  # noqa: E402
check("a reminder that already says it goes out as written", R._cau_nhac("Nhắc anh: thử máy chạy lịch")
      == "⏰ Nhắc anh: thử máy chạy lịch")
check("any other gets a lead that names nobody", R._cau_nhac("Uống thuốc") == "⏰ Nhắc hẹn: Uống thuốc")
check("no more 'Nhắc bạn:' lead", "Nhắc bạn: " not in src_r.split("def _nhan_kw")[0].split("_DA_NHAC_RE")[1])

print()
if fails:
    print(f"FAIL {len(fails)}: " + " | ".join(fails))
    sys.exit(1)
print("OK - test_chu_mcl_0453_2: tất cả pass")
