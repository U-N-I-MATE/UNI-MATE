"""0.452.0: one of the owner's machines runs the schedules (owner 2026-11-16, VPS by default).

    python tests/run.py may_chay_lich_0452

Home PC and VPS share the brains through GitHub, so before this release every reminder, loop and habit reminder fired
on both and a Mộc Tử post went out twice. Checks:
  - server/may_chay_lich.py: stable machine id, who runs (newest choice, VPS default, a lone machine always runs),
    pins, the link code, the ledger (first machine wins, the holder may claim again, offline claims wait for the VPS);
  - every place that runs on a schedule asks it: reminders, loops, habit reminders, customer bots (Telegram pollers
    do not run on the other machine), outside actions of a scheduled run (once_ledger);
  - the brain sync merges reminders.json and loop-state.json entry by entry instead of "newer file wins";
  - the routes, the public link endpoints behind the link key, the schedule tool, the Settings card, the Tasks page.
"""
from _paths import ROOT, SERVER  # noqa: E402,F401
import asyncio
import json
import os
import re
import sys
import tempfile
import time
from pathlib import Path

STATE = tempfile.mkdtemp(prefix="unimate-mcl-")
os.environ["UNIMATE_STATE_DIR"] = STATE
os.environ.pop("UNIMATE_MACHINE_KIND", None)
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


def read(rel):
    return (ROOT / rel).read_text(encoding="utf-8")


def fresh(kind):
    d = Path(tempfile.mkdtemp(prefix="mcl-"))
    M.configure(state_file=d / "state.json", ledger_file=d / "ledger.sqlite3")
    os.environ["UNIMATE_MACHINE_KIND"] = kind
    return d


brain1 = Path(tempfile.mkdtemp(prefix="brainA-"))
brain2 = Path(tempfile.mkdtemp(prefix="brainB-"))
M.wire(lambda: [brain1, brain2])

# ---------------------------------------------------------------- identity
home_dir = fresh("home")
me = M.machine()
check("machine id made once and kept", re.fullmatch(r"[0-9a-f]{16}", me["id"]) and M.machine()["id"] == me["id"]
      and json.loads((home_dir / "state.json").read_text())["id"] == me["id"])
check("kind from UNIMATE_MACHINE_KIND", me["kind"] == "home")
check("pins: aliases map to vps/home, anything else follows the general choice",
      M.norm_pin("may_nha") == "home" and M.norm_pin("VPS") == "vps" and M.norm_pin("x") == "" and M.norm_pin(None) == "")

# ---------------------------------------------------------------- who runs
check("a lone machine runs its schedules even though the default is VPS",
      M.effective_runner() == "vps" and M.should_run("") is True)
n = M.publish_self()
check("each machine announces itself in every brain (one file per machine)",
      n == 2 and (brain1 / "UniMate" / "may" / f"{me['id']}.json").is_file()
      and (brain2 / "UniMate" / "may" / f"{me['id']}.json").is_file())
check("announcing again the same day writes nothing", M.publish_self() == 0)

# a VPS appears in the brains (as the sync would bring it)
vps_rec = {"id": "aaaaaaaaaaaaaaaa", "kind": "vps", "label": "jin.unihq.vn", "seen": time.strftime("%Y-%m-%d")}
(brain1 / "UniMate" / "may" / "aaaaaaaaaaaaaaaa.json").write_text(json.dumps(vps_rec), encoding="utf-8")
M._forget_cache()
check("home sees the VPS through the brains", [p["label"] for p in M.peers()] == ["jin.unihq.vn"])
check("home with a known VPS and the default choice does not run schedules", M.should_run("") is False)
check("a schedule pinned to home still runs at home", M.should_run("home") is True)
check("a schedule pinned to the VPS does not run at home", M.should_run("vps") is False)
old = dict(vps_rec, seen="2020-01-01")
(brain1 / "UniMate" / "may" / "aaaaaaaaaaaaaaaa.json").write_text(json.dumps(old), encoding="utf-8")
M._forget_cache()
check("a machine not heard of for 45 days no longer counts", M.should_run("") is True)
(brain1 / "UniMate" / "may" / "aaaaaaaaaaaaaaaa.json").write_text(json.dumps(vps_rec), encoding="utf-8")
M._forget_cache()

st = M.set_runner("home")
check("choosing home: written here and into every brain, home now runs",
      json.loads((brain2 / "UniMate" / "may_chay_lich.json").read_text())["runner"] == "home"
      and st["is_runner"] is True and M.should_run("") is True)
(brain1 / "UniMate" / "may_chay_lich.json").write_text(json.dumps({"runner": "vps", "updated_at": time.time() + 5}),
                                                     encoding="utf-8")
M._forget_cache()
check("the newest choice wins (another machine picked VPS later)", M.effective_runner() == "vps" and not M.should_run(""))

# the VPS side
vps_dir = fresh("vps")
M.wire(lambda: [brain1, brain2])
check("on the VPS with VPS chosen: runs", M.should_run("") is True)
check("on the VPS a job pinned home is left to the home PC it knows", M.should_run("home") is False)

# ---------------------------------------------------------------- link code
code = M.make_pair_code("https://jin.unihq.vn")
url, key = M.parse_code(code)
check("link code carries the VPS address and a fresh key, only the hash stays",
      code.startswith("unimate-may:") and url == "https://jin.unihq.vn" and key not in (vps_dir / "state.json").read_text())
check("the VPS recognises its own key, not a wrong one", M.check_pair(key) and not M.check_pair(key + "x")
      and not M.check_pair(""))
for bad in ("", "abc", "unimate-may:!!!", M.CODE_PREFIX + "e30"):
    try:
        M.parse_code(bad)
        ok = False
    except ValueError:
        ok = True
    check(f"a bad code is refused ({bad[:16]!r})", ok)
check("revoking drops every key", M.revoke_pairs() == 1 and not M.check_pair(key))

# ---------------------------------------------------------------- ledger
ok1, _ = M.local_claim("lich:reminder:r_1:100", "m1", "home")
ok2, holder = M.local_claim("lich:reminder:r_1:100", "m2", "vps")
ok3, _ = M.local_claim("lich:reminder:r_1:100", "m1", "home")
check("ledger: first machine holds the key, the other is refused, the holder may claim again",
      ok1 and not ok2 and holder == "home" and ok3)
check("VPS side of a claim answers ok/holder", M.remote_claim("k2", "m9", "pc")["ok"] is True
      and M.remote_claim("k2", "m8", "x") == {"ok": False, "holder": "pc"})
check("remote_register records a linked machine as a peer",
      M.remote_register({"id": "bbbbbbbbbbbbbbbb", "kind": "home", "label": "nguyen-huan"})["ok"]
      and any(p["id"] == "bbbbbbbbbbbbbbbb" and p["via"] == "link" for p in M.peers()))

# linked home, VPS unreachable
fresh("home")
M.wire(lambda: [brain1, brain2])
M.machine()
st0 = json.loads(Path(M.STATE_FILE).read_text())
st0["link"] = {"url": "https://vps.example", "key": "k" * 24}
Path(M.STATE_FILE).write_text(json.dumps(st0))


async def boom(*a, **k):
    raise RuntimeError("down")

M._http = boom
check("linked home, VPS down: a job it was told to run goes ahead and waits to be sent",
      asyncio.run(M.claim("lich:x:1")) is True and M.status()["pending"] == 1)
check("linked home, VPS down: a claim that must be confirmed is refused",
      asyncio.run(M.claim("lich:x:2", offline_ok=False)) is False)
check("linked home counts the VPS as known (the link itself says it exists)", M._other_known("vps"))


async def taken(method, path, body=None, link=None):
    return {"ok": False, "holder": "jin.unihq.vn"}

M._http = taken
check("linked home: a key the VPS says is taken is skipped, and not asked about again",
      asyncio.run(M.claim("lich:x:3")) is False and "lich:x:3" in M._taken)

# a schedule made on the linked home PC is handed to the VPS at once (sync, then ask the VPS to pull)
calls = []


async def rec_http(method, path, body=None, link=None):
    calls.append(path)
    return {"ok": True}

M._http = rec_http
M._sync_fn = lambda: calls.append("sync") or {"ok": True}
asyncio.run(M._nudge_run(delay=0, retry_s=()))
check("linked home: a schedule change syncs the brains then asks the VPS to pull",
      calls == ["sync", "/may-chay-lich/remote/sync"], calls)
M._sync_fn = None
check("no backup configured: nothing to nudge", M.nudge_sync_soon() is None)
check("reminder and loop saves nudge the sync",
      "may_chay_lich.nudge_sync_soon()" in read("server/reminders.py")
      and "may_chay_lich.nudge_sync_soon({" in read("server/self_improve.py"))

# a schedule made at home that cannot reach the VPS is reported, never silent (owner 16/11 11:22)
told = []


async def tell(chat_id, text, brain):
    told.append((chat_id, text))

M.wire(lambda: [brain1, brain2], lambda: {"ok": True}, lambda: sync_on["v"], tell)
sync_on = {"v": False}
check("sync off on a linked home PC: said right when a VPS schedule is made", "không tới" in M.warn_new("")
      or "not reach" in M.warn_new(""), M.warn_new(""))
check("pinned to the home PC: nothing to say", M.warn_new("home") == "")
sync_on["v"] = True
check("sync on: nothing to say", M.warn_new("") == "")


async def down(*a, **k):
    raise RuntimeError("VPS down")

M._http = down
M._nudge["items"].clear()
now = time.time()
M.nudge_sync_soon({"key": "r_soon", "title": "Đăng Mộc Tử", "due_at": now + 600, "chat_id": "web:s1", "brain": "b",
                   "pin": ""})
M.nudge_sync_soon({"key": "r_late", "title": "Báo cáo tuần", "due_at": now + 86400, "chat_id": "web:s2", "brain": "b",
                   "pin": ""})
M.nudge_sync_soon({"key": "r_home", "title": "AdsPower", "due_at": now + 60, "chat_id": "web:s3", "brain": "b",
                   "pin": "home"})
check("only schedules that run on the VPS wait for the hand-over", set(M._nudge["items"]) == {"r_soon", "r_late"})
t = M._nudge.get("task")
if t is not None:
    t.cancel()
told.clear()
err = asyncio.run(M._nudge_run(delay=0, retry_s=(0, 0)))
chats = [c for c, _ in told]
check("VPS unreachable: retried, then each schedule is reported in the chat that made it, once",
      err and chats.count("web:s1") == 1 and chats.count("web:s2") == 1 and "web:s3" not in chats, told)
check("the report names the schedule and says it cannot run yet",
      "Đăng Mộc Tử" in told[0][1] and ("chưa tới được VPS" in told[0][1] or "has not reached" in told[0][1]))
st_un = M.status()
check("the Settings card lists what has not reached the VPS and why", len(st_un["unsent"]) == 2 and st_un["unsent_error"])
told.clear()
seq = []


async def due_soon_only(method, path, body=None, link=None):
    seq.append(path)
    raise RuntimeError("VPS down")

M._http = due_soon_only
M._nudge["items"].clear()
M.nudge_sync_soon({"key": "r_now", "title": "Nhắc 30 phút", "due_at": time.time() + 1800, "chat_id": "web:a",
                   "brain": "b", "pin": ""})
M.nudge_sync_soon({"key": "r_week", "title": "Việc tuần", "due_at": time.time() + 7 * 86400, "chat_id": "web:b",
                   "brain": "b", "pin": ""})
t = M._nudge.get("task")
if t is not None:
    t.cancel()


async def first_try_only():
    task = asyncio.ensure_future(M._nudge_run(delay=0, retry_s=(5, 5)))
    await asyncio.sleep(0.2)
    first = list(told)
    task.cancel()
    return first

first = asyncio.run(first_try_only())
check("due within the hour: reported at the first failure, a later one waits for the retries",
      [c for c, _ in first] == ["web:a"], first)
told.clear()


async def back_up(method, path, body=None, link=None):
    return {"ok": True}

M._http = back_up
res = asyncio.run(M.push_now())
check("Send to the VPS button: works once the VPS is back, and the chats told before hear it got there",
      res["ok"] and not M._nudge["items"] and any("đã tới VPS" in x or "reached the VPS" in x for _, x in told), (res, told))
rm = read("server/reminders.py")
check("reminders made or changed at home name themselves for the hand-over; the create answer carries the warning",
      rm.count("self._ve_vps(brain, ") == 2 and '"canh_bao_may": may_chay_lich.warn_new(' in rm)
pl2 = read("system/plugins/unimate-schedule/plugin.py")
check("schedule tool: tells the model to say the warning, loops made by the tool are handed over too",
      'CẢNH BÁO, nói rõ cho user' in pl2 and 'may_chay_lich.nudge_sync_soon({"key": f"loop:{slug}"' in pl2)
check("button route", '@app.post("/may-chay-lich/push")' in read("server/main.py"))
M._sync_fn = None

# ---------------------------------------------------------------- schedule stores merged entry by entry
import git_brain  # noqa: E402
B = {"reminders": [{"id": "a", "due_at": 1}, {"id": "b"}, {"id": "c", "label": "x"}], "updated": 1}
O = {"reminders": [{"id": "a", "due_at": 2, "fired_at": 9}, {"id": "b"}, {"id": "c", "label": "x"},
                   {"id": "home-new"}], "updated": 9}
T = {"reminders": [{"id": "a", "due_at": 1}, {"id": "c", "label": "y", "updated_at": 5}, {"id": "vps-new"}],
     "updated": 7}
out = json.loads(git_brain.merge_json_store("Brain/UniMate/reminders.json", json.dumps(B).encode(),
                                            json.dumps(O).encode(), json.dumps(T).encode()))
ids = [r["id"] for r in out["reminders"]]
check("reminders.json: both sides' new entries kept, a deletion on one side stays deleted",
      set(ids) == {"a", "c", "home-new", "vps-new"} and "b" not in ids, ids)
check("reminders.json: each side's own edit kept (a fired at home, c renamed on the VPS)",
      next(r for r in out["reminders"] if r["id"] == "a")["fired_at"] == 9
      and next(r for r in out["reminders"] if r["id"] == "c")["label"] == "y" and out["updated"] == 9)
both = json.loads(git_brain.merge_json_store(
    "X/UniMate/reminders.json", json.dumps({"reminders": [{"id": "a"}]}).encode(),
    json.dumps({"reminders": [{"id": "a", "updated_at": 3}]}).encode(),
    json.dumps({"reminders": [{"id": "a", "updated_at": 8, "label": "vps"}]}).encode()))
check("both sides edited one entry: the newer edit wins", both["reminders"][0].get("label") == "vps")
ls = json.loads(git_brain.merge_json_store(
    "X/UniMate/loop-state.json", b"", json.dumps({"a": {"last_run": 5}}).encode(),
    json.dumps({"a": {"last_run": 9}, "b": {"last_run": 1}}).encode()))
check("loop-state.json merges per loop (newer run wins, new loop kept)", ls == {"a": {"last_run": 9}, "b": {"last_run": 1}})
check("other files and broken JSON fall back to the usual rule",
      git_brain.merge_json_store("X/notes.md", b"", b"a", b"b") is None
      and git_brain.merge_json_store("X/UniMate/reminders.json", b"", b"{", b"{}") is None)
gb = read("server/git_brain.py")
check("the sync merge calls it before the whole-file rule, with the common base",
      'merge_json_store(p, base.stdout if base.returncode == 0 else b""' in gb and '"show", f":1:{p}"' in gb)

# ---------------------------------------------------------------- the places that run on a schedule
rem = read("server/reminders.py")
check("reminders: tick skips what the other machine runs and claims the slot before firing",
      'if not may_chay_lich.should_run(rem.get("chay_tren")):' in rem
      and rem.count("await self._claim_slot(rem)") == 2 and '"lich:" + ledger_job(' in rem)
check("reminders: chay_tren on create, update, POST, form and view; updated_at on every owner edit",
      "chay_tren=str(p.get(\"chay_tren\") or \"\")" in rem and "chay_tren: str = Form(None)" in rem
      and '"chay_tren": r.get("chay_tren", "")' in rem and rem.count('["updated_at"] = _now()') >= 4)
si = read("server/self_improve.py")
check("loops: pick skips other-machine loops and taken slots, tick claims the slot, chay_tren kept on save",
      'may_chay_lich.should_run(lp.get("chay_tren"))' in si and 'await may_chay_lich.claim("lich:" + key)' in si
      and '"chay_tren": old.get("chay_tren", "") if old else ""' in si and 'def set_chay_tren(' in si and '@app.post("/loops/chay-tren")' in read("server/main.py"))
check("system loops keep the owner's pin across updates", '"chay_tren"}' in read("server/system_sync.py"))
check("habit reminders only on the schedule machine", "may_chay_lich.should_run(\"\")" in read("server/my_tasks.py"))

# loops parse the field
import self_improve  # noqa: E402
lf = self_improve.LoopFeature.__new__(self_improve.LoopFeature)  # noqa: E501
nl = lf._norm_loop({"name": "x", "chay_tren": "may_nha"}, "body", "x")
check("a loop file's chay_tren is read and normalised", nl["chay_tren"] == "home")

# once_ledger: outside actions of a scheduled run
import once_ledger  # noqa: E402
import turn_context  # noqa: E402
once_ledger.configure(Path(tempfile.mkdtemp()) / "once.sqlite3")
called = []


async def call(a):
    called.append(a)
    return "posted"


async def no_claim(key, offline_ok=True):
    no_claim.keys.append(key)
    return False
no_claim.keys = []

real_claim = M.claim
M.claim = no_claim
try:
    r1 = asyncio.run(once_ledger.run("fb_post", {"page_id": "p1", "message": "hi"}, call, job="reminder:r_1:100"))
    r2 = asyncio.run(once_ledger.run("fb_post", {"page_id": "p1"}, call, job="kanban:7"))
finally:
    M.claim = real_claim
check("a scheduled run's outside action already done by the other machine is not done again",
      r1 == once_ledger.OTHER_MACHINE_NOTE and no_claim.keys[0] == "tacvu:reminder:r_1:100:fb_post:p1")
check("a Kanban job (lives on one machine) does not ask the shared ledger", r2 == "posted" and len(no_claim.keys) == 1)

# customer bots
cr = read("server/chatbot_runtime.py")
check("bots: the other machine logs the message to its inbox and stays silent",
      'if not may_chay_lich.should_run(cfg.get("chay_tren")):' in cr and "ghi_tin_khach(cfg, meta or {}, text)" in cr)
check("bots: one customer message is answered once across machines (channel + chat + message id)",
      'await may_chay_lich.claim(f"bot:{kenh}:{meta.get(\'chat_id\') or \'\'}:{mid}")' in cr
      and "if not await _may_nay_tra_loi(cfg, meta or {}):" in cr)
check("bots: a Telegram poller is not started on the machine that does not answer (409 otherwise)",
      'if kenh == "telegram" and not may_chay_lich.should_run(cfg.get("chay_tren")):' in cr)
import chatbot_runtime  # noqa: E402
os.environ["UNIMATE_MACHINE_KIND"] = "home"
fresh("home")
(brain1 / "UniMate" / "may_chay_lich.json").write_text(json.dumps({"runner": "vps", "updated_at": time.time() + 9}),
                                                     encoding="utf-8")
M._forget_cache()
check("bots: home with the VPS chosen does not answer",
      asyncio.run(chatbot_runtime._may_nay_tra_loi({"id": "bot_1"}, {"chat_id": "c", "message_id": "9"})) is False)
check("bots: pinned to home, it answers", asyncio.run(chatbot_runtime._may_nay_tra_loi(
    {"id": "bot_1", "chay_tren": "home"}, {"chat_id": "c", "message_id": "9"})) is True)
cs = read("server/chatbot_store.py")
check("bots: chay_tren is a field the owner can set", '"chay_tren")' in cs and 'b["chay_tren"] = pin' in cs)

# ---------------------------------------------------------------- routes and wiring
mn = read("server/main.py")
pub = mn[mn.index("_AUTH_PUBLIC_EXACT"):mn.index("_AUTH_PUBLIC_EXACT") + 4000]
check("link endpoints are public paths (no cookie from the other machine)",
      all(p in pub for p in ('"/may-chay-lich/remote/runner"', '"/may-chay-lich/remote/claim"',
                             '"/may-chay-lich/remote/register"', '"/may-chay-lich/remote/sync"')))
remote = mn[mn.index('@app.get("/may-chay-lich/remote/runner")'):]
check("every link endpoint checks the link key first",
      remote.count("if not _pair_ok(request):") == 5 and "may_chay_lich.check_pair(request.headers.get(may_chay_lich.HEADER" in mn)
check("owner routes behind the sign-in wall (not public)",
      all(f'@app.{m}("/may-chay-lich{p}")' in mn for m, p in (("get", ""), ("post", "/runner"), ("post", "/pair-code"),
                                                              ("post", "/link"), ("post", "/unlink"), ("post", "/pair-revoke")))
      and '"/may-chay-lich/link"' not in pub and '"/may-chay-lich/pair-code"' not in pub)
check("started with the scheduler, brains wired, bots restart when this machine starts or stops answering",
      "asyncio.create_task(may_chay_lich.run_forever())" in mn and "may_chay_lich.on_change(_bots_theo_may)" in mn)
check("a bot moved to this machine is started when saved",
      '("chay_tren" in form and (chatbot_store.get_bot(bot_id) or {}).get("enabled"))' in mn)

# schedule tool
sys.path.insert(0, str(ROOT / "system" / "plugins" / "unimate-schedule"))
pl = read("system/plugins/unimate-schedule/plugin.py")
check("unimate_schedule: chay_tren in the schema, on create (reminder and loop file) and update",
      '"chay_tren": {"type": "string", "enum": ["", "vps", "home"]' in pl and 'payload["chay_tren"] = _chay_tren(args)' in pl
      and 'f"chay_tren: {chay_tren}\\n"' in pl and 'payload["chay_tren"] = pin' in pl)

# dashboard
idx = read("dashboard/index.html")
check("Settings block and its script", 'id="mclBox"' in idx and "/static/may-chay-lich.js?v=3" in idx
      and 'data-i18n="mcl.title"' in idx)
tj = read("dashboard/tasks.js")
check("Tasks page: banner when this machine does not run schedules, per-job picker once a second machine exists",
      'tw("mcl.banner"' in tj and "data-runon" in tj and "S.mcl.peers && S.mcl.peers.length" in tj
      and '"/loops/chay-tren"' in tj)
mj = read("dashboard/may-chay-lich.js")
check("link code field is a password field, the code is shown once, never stored by the page",
      'type="password" autocomplete="off"' in mj and "mcl.code_once" in mj and "localStorage" not in mj)
for lang in ("vi", "en"):
    d = json.loads(read(f"dashboard/i18n/{lang}.json"))
    need = sorted(set(re.findall(r'"(mcl\.[a-z_]+)"', mj + tj + idx)) | {"cb.chay_tren"})
    miss = [k for k in need if k not in d]
    check(f"i18n {lang}: every mcl.* key the pages use", not miss, miss)

print()
if fails:
    print(f"FAIL {len(fails)}: " + " | ".join(fails))
    sys.exit(1)
print("OK - test_may_chay_lich_0452: all pass")
