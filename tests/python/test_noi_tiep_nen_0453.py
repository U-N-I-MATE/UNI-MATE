"""0.453.0: background work given from a chat opens a follow-up turn in that chat when it ends (owner 2026-11-16).

    python tests/run.py noi_tiep_nen_0453

Before this release a finished background job only dropped its result in the chat; the owner had to write "the job is
done, check it" before UNI MATE read the result and went on. Checks:
  - server/noi_tiep_nen.py: jobs join the batch of the owner turn that gave them; scheduled runs and unsupported chats
    do not; a batch opens once its turn ended and every job ended, or 30 minutes after the first one ended; it opens
    exactly once; caps of 3 follow-ups in a row per chain and 10 per hour per chat; the Settings switch; a job the
    owner cancelled or marked lam_tiep=false opens nothing; the book survives a restart;
  - the prompt: pass/fail per job, never approve for the owner, no outside action twice, the turn number;
  - luot_dang_chay gives the key of the one turn running in a chat;
  - Kanban: created and finish hooks (a job only waiting for an answer, a plan limit or a retry has not ended);
  - shell jobs on Windows: descendants sampled while the engine runs (psutil), tracked by (pid, start time);
  - main.py: the batch runs as a follow-up turn in the chat (web opener, Telegram), caps reported in the chat, team
    reports feed the book, follow-up turns carry a once-only ledger key per chain, the /noi-tiep switch;
  - the Settings block and its texts.
"""
from _paths import ROOT, SERVER  # noqa: E402,F401
import asyncio
import os
import re
import subprocess
import sys
import tempfile
import time
import types
from pathlib import Path

STATE = tempfile.mkdtemp(prefix="unimate-noitiep-")
os.environ["UNIMATE_STATE_DIR"] = STATE
try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

import noi_tiep_nen as N  # noqa: E402
import luot_dang_chay  # noqa: E402

fails = []


def check(name, cond, extra=""):
    print(("ok   " if cond else "FAIL ") + name + ("" if cond or not extra else f"  [{extra}]"))
    if not cond:
        fails.append(name)


DB = Path(STATE) / "nt.sqlite3"
N.configure(DB)
running = set()
kenh = [""]
on = [True]
N.noi(luot_fn=lambda chat: None, dang_chay_fn=lambda dot: dot in running, bat_fn=lambda: on[0],
      kenh_fn=lambda: kenh[0])
T0 = 1_800_000_000.0
L1 = {"dot": "turn-1", "chuoi": "turn-1", "do_sau": 0}

# ---- registering ----
check("a job given in an owner turn of a web chat is registered",
      N.dang_ky("web:s1", "task", "t1", "Viết bài", luot=L1, now=T0))
check("same job twice is one row", N.dang_ky("web:s1", "task", "t1", "Viết bài", luot=L1, now=T0)
      and len([r for r in N.xem() if r["khoa"] == "task:t1"]) == 1)
check("a Telegram owner chat is supported", N.chat_ho_tro("123456") and N.chat_ho_tro("-100200"))
check("a Zalo chat or an empty one is not", not N.chat_ho_tro("zalo:9") and not N.chat_ho_tro("") and not N.chat_ho_tro("web:"))
check("no turn running in the chat -> not registered (Tasks page, a schedule)",
      not N.dang_ky("web:s9", "task", "tx", "x", now=T0))
kenh[0] = "reminder"
check("a job given by a reminder run is not registered (schedules are out of scope)",
      not N.dang_ky("web:s1", "task", "t-rem", "x", luot=L1, now=T0))
kenh[0] = ""
check("unknown kind refused", not N.dang_ky("web:s1", "loop", "l1", "x", luot=L1))
N.dang_ky("web:s1", "job", "j1", "ffmpeg -i a.mp4 b.mp4", luot=L1, now=T0)

# ---- batch readiness ----
running.add("turn-1")
check("first job ends while the turn still runs: nothing opens yet",
      N.xong("task", "t1", "xong", "Bài đã viết xong", now=T0 + 10) is not None and N.dot_san_sang(now=T0 + 11) == [])
running.discard("turn-1")
check("turn ended but the shell job still runs: wait for it", N.dot_san_sang(now=T0 + 60) == [])
d = N.dot_san_sang(now=T0 + 10 + N.CHO_DOT + 1)
check("30 minutes after the first job ended: open with the done one, one still running",
      len(d) == 1 and [r["khoa"] for r in d[0]["viec"]] == ["task:t1"] and d[0]["con_chay"] == 1, d)
got = N.nhan(d[0])
check("claimed once", len(got) == 1 and N.nhan(d[0]) == [] and N.dot_san_sang(now=T0 + 3000) == [])
check("the same outcome reported again does nothing", N.xong("task", "t1", "xong", "again", now=T0 + 3001) is None)
N.xong("job", "j1", "xong", "Video xong", now=T0 + 4000)
d = N.dot_san_sang(now=T0 + 4001)
check("the late job opens its own follow-up when it ends", len(d) == 1 and d[0]["viec"][0]["khoa"] == "job:j1")
N.nhan(d[0])

L2 = {"dot": "turn-2", "chuoi": "turn-2", "do_sau": 0}
N.dang_ky("web:s1", "task", "a", "A", luot=L2, now=T0)
N.dang_ky("web:s1", "team", "b", "B", luot=L2, now=T0)
N.xong("task", "a", "cho_duyet", "Bản nháp", now=T0 + 5)
check("one job of two done (no 30 min yet): wait", N.dot_san_sang(now=T0 + 6) == [])
N.xong("team", "b", "bi_chan", "Thiếu quyền", now=T0 + 7)
d = N.dot_san_sang(now=T0 + 8)
check("both ended: ONE follow-up for the batch", len(d) == 1 and len(d[0]["viec"]) == 2 and d[0]["con_chay"] == 0)
N.nhan(d[0])
check("a job blocked then finished counts again", N.xong("team", "b", "xong", "Đã xong", now=T0 + 9) is not None
      and len(N.dot_san_sang(now=T0 + 10)) == 1)
N.nhan(N.dot_san_sang(now=T0 + 10)[0])

L3 = {"dot": "turn-3", "chuoi": "turn-3", "do_sau": 0}
N.dang_ky("web:s1", "job", "jc", "sleep 99", luot=L3, now=T0)
N.xong("job", "jc", "huy", "Đã dừng", now=T0 + 1)
check("a job the owner/model cancelled opens nothing", N.dot_san_sang(now=T0 + 2) == [])
L4 = {"dot": "turn-4", "chuoi": "turn-4", "do_sau": 0}
N.dang_ky("web:s1", "task", "nf", "Chỉ báo", luot=L4, now=T0)
check("lam_tiep=false on one job", N.dat_lam_tiep("task", "nf", False))
N.xong("task", "nf", "xong", "ok", now=T0 + 1)
check("a lam_tiep=false job opens nothing", N.dot_san_sang(now=T0 + 2) == [])

# ---- caps and the switch ----
dot = {"chat": "web:cap", "do_sau": 0}
check("first follow-up of a chain is turn 1", N.quyet(dot, now=T0) == ("mo", 1))
check("after 3 in a row the chain stops", N.quyet({"chat": "web:cap", "do_sau": 3}, now=T0) == ("tran_chuoi", 3))
for i in range(N.TRAN_GIO):
    N.ghi_luot("web:cap", f"d{i}", 1, now=T0 + i)
check("10 follow-ups in an hour: the 11th waits", N.quyet(dot, now=T0 + 100) == ("tran_gio", 10))
check("an hour later it opens again", N.quyet(dot, now=T0 + 3700)[0] == "mo")
on[0] = False
check("switch off: no follow-up", N.quyet(dot, now=T0)[0] == "tat")
on[0] = True
check("caps text: chain", "3 lượt liên tiếp" in N.cau_khong_mo("tran_chuoi", {"viec": []}) and "làm tiếp" in
      N.cau_khong_mo("tran_chuoi", {"viec": []}))
check("caps text: hour", "trần 10" in N.cau_khong_mo("tran_gio", {"viec": []}, 10))

# ---- the prompt ----
p = N.loi_nhac({"viec": [{"loai": "task", "ma": "a", "ten": "A", "ket": "cho_duyet", "noi_dung": "x" * 5000},
                         {"loai": "job", "ma": "j", "ten": "ffmpeg", "ket": "xong", "noi_dung": "ok"}],
                "con_chay": 1}, 2, ["zalo_send_message tới 123 \"Chào\""])
check("prompt says which follow-up turn this is", "lượt tiếp 2/3" in p and "thứ 2/3" in p)
check("prompt asks for pass/fail per job", "ĐẠT hay CHƯA ĐẠT" in p)
check("prompt forbids approving for the owner", "KHÔNG tự duyệt thay chủ" in p and "CHỜ CHỦ DUYỆT" in p)
check("prompt lists outside actions already done and forbids repeating them",
      "KHÔNG làm lại" in p and "zalo_send_message" in p)
check("prompt trims a long result", len(p) <= N.TRAN_LOI_NHAC and "cắt bớt" in p)
check("prompt mentions jobs still running", "vẫn đang chạy" in p)
check("no em dash in the module", "—" not in (Path(SERVER) / "noi_tiep_nen.py").read_text(encoding="utf-8"))

# ---- restart ----
N.dang_ky("web:s2", "task", "r1", "Sau khởi động lại", luot={"dot": "turn-9", "chuoi": "turn-9", "do_sau": 1}, now=T0)
N.configure(DB)
check("the book survives a restart", N.co("task", "r1"))
N.xong("task", "r1", "xong", "ok", now=T0 + 1)
d = N.dot_san_sang(now=T0 + 2)
check("after a restart the batch still opens, keeping the chain depth", len(d) == 1 and d[0]["do_sau"] == 1)
N.nhan(d[0])

# ---- luot_dang_chay ----
k = luot_dang_chay.bat_dau("web:z", "/tmp")
check("key of the one turn running in a chat", luot_dang_chay.khoa_cua("web:z") == k and luot_dang_chay.con_chay(k))
k2 = luot_dang_chay.bat_dau("web:z", "/tmp")
check("two turns in one chat: no guess", luot_dang_chay.khoa_cua("web:z") == "")
luot_dang_chay.ket_thuc(k)
luot_dang_chay.ket_thuc(k2)
check("ended turn is not running", not luot_dang_chay.con_chay(k) and luot_dang_chay.khoa_cua("web:z") == "")

# ---- Kanban hooks ----
import tasks as tasks_mod  # noqa: E402
seen = []
fake = types.SimpleNamespace(deps=types.SimpleNamespace(finish_hook=seen.append),
                             _cau_hoi_dang_cho=tasks_mod.TasksFeature._cau_hoi_dang_cho)
for st, kind in (("done", ""), ("review", ""), ("blocked", "tool_error"), ("blocked", "needs_input"),
                 ("blocked", "limit"), ("blocked", "transient")):
    tasks_mod.TasksFeature._finish_hook(fake, {"id": f"{st}-{kind}", "status": st, "block_kind": kind})
check("Kanban: done, review and a real block end the job; a question, a plan limit and a retry do not",
      [t["id"] for t in seen] == ["done-", "review-", "blocked-tool_error"], [t["id"] for t in seen])
tsrc = (Path(SERVER) / "tasks.py").read_text(encoding="utf-8")
check("Kanban: the created hook runs for a job with a recipient chat, only when it is new",
      "if chat_id and self.deps.created_hook:" in tsrc and "< 5:" in tsrc)
check("Kanban: the finish hook runs right after the report", "await self._hoc_tu_viec(root, final_task)\n"
      "                self._finish_hook(final_task)" in tsrc)

# ---- shell jobs on Windows (logic run on this machine with psutil) ----
import tien_trinh_nen as TT  # noqa: E402
import psutil  # noqa: E402
eng = subprocess.Popen([sys.executable, "-c",
                        "import subprocess,sys,time;subprocess.Popen([sys.executable,'-c','import time;time.sleep(60)']);"
                        "time.sleep(1.5)"])
old = (TT.POSIX, TT.WINDOWS)
TT.POSIX, TT.WINDOWS = False, True
try:
    TT._NHOM_THEO_TAG["win-tag"] = [eng.pid]
    time.sleep(0.8)
    TT._lay_mau_mot_luot()
    check("Windows: descendants of the engine are sampled while it runs", len(TT._DA_THAY.get("win-tag") or {}) >= 1)
    eng.wait(10)
    ds = TT.nhan_nuoi_theo_tag("win-tag", STATE, "web:w1")
    check("Windows: a child left behind by the engine is adopted as one job with (pid, start time)",
          len(ds) == 1 and ds[0]["pids"] and ds[0]["pgid"] == 0 and "sleep" in ds[0]["mo_ta"], ds)
    v = TT._VIEC[ds[0]["id"]]
    check("Windows: the job is alive while the child runs", TT.viec_con_song(v))
    for pid, _ in v["pids"]:
        try:
            psutil.Process(pid).kill()
        except Exception:
            pass
    time.sleep(0.5)
    xong = TT.kiem_mot_luot()
    check("Windows: the job ends when the child ends", any(x["id"] == ds[0]["id"] and x["trang_thai"] == "xong" for x in xong))
    check("Windows: a reused pid does not count (start time must match)", not TT._win_song(os.getpid(), 1.0))
finally:
    TT.POSIX, TT.WINDOWS = old
    try:
        eng.kill()
    except Exception:
        pass
check("Windows is supported when psutil is there", TT.HO_TRO)
check("the terminal tool tracks background jobs on Windows too",
      "    if chat_id:\n        try:\n            import tien_trinh_nen" in (Path(SERVER) / "coding_terminal.py").read_text(encoding="utf-8"))
check("unimate_job no longer refuses on Windows",
      "HO_TRO" in (Path(ROOT) / "system/plugins/unimate-job/plugin.py").read_text(encoding="utf-8"))

# ---- main.py ----
from fastapi.testclient import TestClient  # noqa: E402
import main  # noqa: E402
src = (Path(SERVER) / "main.py").read_text(encoding="utf-8")
check("main: Kanban hooks wired", "created_hook=lambda t: _noi_tiep_kanban_tao(t)" in src
      and "finish_hook=lambda t: _noi_tiep_kanban_xong(t)" in src)
check("main: team reports go through the follow-up book", "report=_team_core_report))" in src)
check("main: the follow-up loop starts with the server", "asyncio.create_task(_vong_noi_tiep())" in src)
check("main: a web follow-up turn carries the chain's once-only key",
      'job=(globals().get("_noi_tiep_job") or (lambda _c: ""))(WEB_CHAT_PREFIX + conv_sid)))' in src)
check("main: an owner Telegram turn is in the running-turn book",
      "_khoa_tg = (luot_dang_chay.bat_dau(chat_id, _brain_root(brain))" in src)
check("main: shell jobs of a turn register in the book", 'noi_tiep_nen.dang_ky(owner_chat, "job", v["id"]' in src)

# The book in main is the real one (STATE_DIR); drive a batch through _noi_tiep_mot_dot with fakes.
N.noi(luot_fn=main._noi_tiep_luot, dang_chay_fn=lambda dot: False, bat_fn=lambda: True, kenh_fn=lambda: "")
sent, opened = [], []


async def fake_notify(chat, text, **kw):
    sent.append((chat, text, kw))
    return (True, "")


async def fake_runner(text, do_sau, chuoi=None):
    opened.append((text, do_sau, chuoi))


main._notify_owner = fake_notify
main._NOI_TIEP_WEB["s5"] = fake_runner
k = luot_dang_chay.bat_dau("web:s5", STATE)
check("main: a job given in a running web turn takes that turn as its batch",
      main._noi_tiep_luot("web:s5") == {"dot": k, "chuoi": k, "do_sau": 0})
main._noi_tiep_kanban_tao({"id": "k1", "chat_id": "web:s5", "title": "Đăng bài", "brain_root": STATE})
luot_dang_chay.ket_thuc(k)
main._noi_tiep_kanban_xong({"id": "k1", "status": "review", "result": "Bản nháp đã viết"})


async def run_one():
    out = []
    for dot in N.dot_san_sang():
        out.append(await main._noi_tiep_mot_dot(dot))
        await asyncio.sleep(0)
    return out


res = asyncio.run(run_one())
check("main: the batch opens a follow-up turn through the chat's opener", res == ["mo"] and len(opened) == 1, res)
check("main: the follow-up turn is turn 1 of its chain", opened and opened[0][1] == 1 and opened[0][2]["do_sau"] == 1)
check("main: the follow-up text names the job and its review state",
      opened and "Đăng bài" in opened[0][0] and "CHỜ CHỦ DUYỆT" in opened[0][0])
main._NOI_TIEP_CHUOI["web:s5"] = {"chuoi": k, "do_sau": 3}
check("main: a follow-up turn's once-only key is per chain", main._noi_tiep_job("web:s5") == f"noitiep:{k}")
k3 = luot_dang_chay.bat_dau("web:s5", STATE)
main._noi_tiep_kanban_tao({"id": "k2", "chat_id": "web:s5", "title": "Lượt 4", "brain_root": STATE})
luot_dang_chay.ket_thuc(k3)
main._NOI_TIEP_CHUOI.pop("web:s5", None)
main._noi_tiep_kanban_xong({"id": "k2", "status": "done", "result": "ok"})
res = asyncio.run(run_one())
check("main: after 3 follow-ups in a row it stops and says so in the chat",
      res == ["tran_chuoi"] and sent and sent[-1][0] == "web:s5" and "3 lượt liên tiếp" in sent[-1][1], (res, sent[-1:]))


async def team_flow():
    k4 = luot_dang_chay.bat_dau("123456", STATE)
    N.dang_ky("123456", "team", "tm1", "Báo cáo", brain=STATE)
    luot_dang_chay.ket_thuc(k4)
    await main._team_core_report("123456", "Nhóm báo xong", kind="report", dedup="teamcore:tm1:done_pass:x:0")
    return [r for r in N.xem("123456") if r["khoa"] == "team:tm1"][0]


row = asyncio.run(team_flow())
check("main: a team report marks the team job ended", row["trang"] == "xong" and row["ket"] == "xong", row)
check("main: Zalo or unknown chats cannot take a follow-up turn", not main._noi_tiep_mo("zalo:1", "x", "", {}))

cl = TestClient(main.app, base_url="http://127.0.0.1:8080")
r = cl.get("/noi-tiep").json()
check("GET /noi-tiep: on by default with the caps", r.get("enabled") is True and r.get("tran_chuoi") == 3
      and r.get("tran_gio") == 10 and r.get("cho_dot_phut") == 30, r)
check("POST /noi-tiep turns it off and on", cl.post("/noi-tiep", data={"enabled": "0"}).json().get("enabled") is False
      and main._noi_tiep_bat() is False and cl.post("/noi-tiep", data={"enabled": "1"}).json().get("enabled") is True)

# ---- tools and Settings ----
task_src = (Path(ROOT) / "system/plugins/unimate-task/plugin.py").read_text(encoding="utf-8")
check("unimate_task: lam_tiep=false opts one job out", '"lam_tiep": {"type": "boolean"' in task_src
      and 'noi_tiep_nen.dat_lam_tiep("task", tid, False)' in task_src)
team_src = (Path(ROOT) / "system/plugins/unimate-team/plugin.py").read_text(encoding="utf-8")
check("unimate_team dispatch registers the job", 'noi_tiep_nen.dang_ky(got["report_to"], "team"' in team_src)
html = (Path(ROOT) / "dashboard/index.html").read_text(encoding="utf-8")
check("Settings block and script", 'id="ntBox"' in html and "/static/noi-tiep.js?v=2" in html)
import json  # noqa: E402
for lang in ("vi", "en"):
    tr = json.loads((Path(ROOT) / f"dashboard/i18n/{lang}.json").read_text(encoding="utf-8"))
    keys = [k for k in tr if k.startswith("nt.")]
    check(f"i18n {lang}: texts present and short", len(keys) == 6 and all(len(tr[k]) <= 100 for k in keys))
claude_md = (Path(ROOT) / "CLAUDE.md").read_text(encoding="utf-8")
check("system prompt tells the model a follow-up turn comes", "opens a follow-up turn here (at most 3 in a row)" in claude_md)

print()
if fails:
    print(f"FAIL {len(fails)}: " + " | ".join(fails))
    sys.exit(1)
print("OK - test_noi_tiep_nen_0453: tất cả pass")
