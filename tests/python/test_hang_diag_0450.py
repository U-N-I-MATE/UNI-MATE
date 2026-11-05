"""0.450.0: tracing a server that stops answering (owner 05/11/2026, approved items A, B, D, E).

    python tests/run.py hang_diag_0450

On 05/11/2026 the home server stopped answering for about ten minutes while a workflow ran a claude step. The log of
that run was gone (every start overwrote server/unimate.log), the chat showed the turn's clock as if it were the time
offline, and clicking the icon twice started two servers. Checks:
  A. The previous log is kept as unimate.prev.log on every restart path that overwrote it (Windows vbs, update.sh);
     CPU and RAM of the machine, the server and its children are logged while work runs, compact and only then,
     from a thread (so the samples go on while the event loop is stuck), and shown in GET /health/loop.
  B. The lost-connection note counts the time offline, not the turn's age, and the turn's clock comes back after.
  D. A second click while the server is starting neither stops nor starts anything (start lock); the server clears
     the lock once up and the updater clears it before its own start.
  E. An update left on "restarting" is closed by the new server once it runs the target version.
"""
from _paths import ROOT, SERVER  # noqa: E402,F401
import asyncio
import os
import sys
import tempfile
import threading
import time
from pathlib import Path

os.environ["UNIMATE_STATE_DIR"] = tempfile.mkdtemp(prefix="unimate-hang-diag-")
try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

import res_watch  # noqa: E402
import update_state  # noqa: E402

fails = []


def check(name, cond, extra=""):
    print(("ok   " if cond else "FAIL ") + name + ("" if cond or not extra else f"  [{extra}]"))
    if not cond:
        fails.append(name)


def read(rel):
    return (ROOT / rel).read_text(encoding="utf-8")


GB = 1024 ** 3

# ---------------------------------------------------------------- A. resource samples
check("engine CLI by its own binary (Windows)", res_watch._is_agent("claude.exe", []))
check("engine CLI as a node script (Windows path)",
      res_watch._is_agent("node.exe", ["node", r"C:\Users\x\AppData\Roaming\npm\node_modules\@anthropic-ai\claude-code\cli.js"]))
check("codex, grok and agy count as engines too",
      all(res_watch._is_agent(n, []) for n in ("codex", "grok", "agy.exe")))
check("the server itself and an MCP server are not engines",
      not res_watch._is_agent("python.exe", ["python", r"server\main.py"])
      and not res_watch._is_agent("node.exe", ["npx", "-y", "unimate-zalo", "mcp", "start"]))

prev_sys = (100.0, 1000.0)
machine = {"cpu_busy": 100.0 + 87.0, "cpu_total": 1000.0 + 100.0, "ram_used": 13.1 * GB, "ram_total": 15.8 * GB}
procs = [
    {"pid": 10, "ppid": 1, "name": "python.exe", "cpu_s": 52.0, "rss": 1.21 * GB, "agent": False},
    {"pid": 11, "ppid": 10, "name": "claude.exe", "cpu_s": 30.0 + 0.61 * 30 * 4, "rss": 0.84 * GB, "agent": True},
    {"pid": 12, "ppid": 10, "name": "node.exe", "cpu_s": 5.0, "rss": 0.12 * GB, "agent": False},
]
prev_tree = {(10, "python.exe"): 52.0 - 0.04 * 30 * 4, (11, "claude.exe"): 30.0, (12, "node.exe"): 5.0}
s = res_watch.build_sample(machine, procs, prev_sys, prev_tree, 30.0, 10, 4, 0.2, at=time.time())
check("machine CPU over the interval", s["cpu"] == 87.0, s["cpu"])
check("machine RAM in GB and percent", (s["ram_used_gb"], s["ram_total_gb"]) == (13.1, 15.8) and s["ram_pct"] == 82.9,
      (s["ram_used_gb"], s["ram_total_gb"], s["ram_pct"]))
check("server process RAM and CPU share of the whole machine", s["server_gb"] == 1.21 and s["server_cpu"] == 4.0,
      (s["server_gb"], s["server_cpu"]))
check("children counted, engine CLIs counted", s["kids"] == 2 and s["agents"] == 1, (s["kids"], s["agents"]))
check("busiest child first", s["top"][0]["name"] == "claude.exe" and s["top"][0]["cpu"] == 61.0, s["top"])
check("a process seen for the first time counts 0% (no made-up number)",
      res_watch.build_sample(machine, procs, prev_sys, {}, 30.0, 10, 4, None)["tree_cpu"] == 0.0)
line = res_watch.format_line(s)
check("one compact line with machine, server, children and loop lag",
      line.startswith("[res] ") and "cpu 87%" in line and "ram 13.1/15.8 GB" in line and "server 1.21 GB 4%" in line
      and "2 children: claude.exe 61% 0.84 GB" in line and "lag 0.2s" in line and "\n" not in line, line)
check("the line stays short", len(line) < 260, len(line))
no_ps = res_watch.build_sample(machine, None, prev_sys, {}, 30.0, 10, 4, None)
check("without per-process numbers the line says n/a instead of guessing",
      "processes n/a" in res_watch.format_line(no_ps) and no_ps["kids"] is None)

idle = {"cpu": 3.0, "ram_pct": 40.0, "tree_cpu": 1.0, "agents": 0, "lag": 0.1}
check("idle server: nothing to log", not res_watch.worth_logging(idle))
check("an engine CLI running: log", res_watch.worth_logging({**idle, "agents": 1}))
check("the server tree busy: log", res_watch.worth_logging({**idle, "tree_cpu": 20.0}))
check("machine CPU or RAM under pressure: log",
      res_watch.worth_logging({**idle, "cpu": 90.0}) and res_watch.worth_logging({**idle, "ram_pct": 93.0}))
check("event loop blocked right now: log", res_watch.worth_logging({**idle, "lag": 5.0}))

# The episode, then the quiet tail, then silence.
seq = [("busy", True)] * 2 + [("idle", False)] * 4
it = iter(seq)


def fake_read(_pid=None):
    kind, _ = next(it)
    p = [{"pid": os.getpid(), "ppid": 1, "name": "python", "cpu_s": 1.0, "rss": GB, "agent": False}]
    if kind == "busy":
        p.append({"pid": 99, "ppid": os.getpid(), "name": "claude", "cpu_s": 1.0, "rss": GB, "agent": True})
    return {"cpu_busy": None, "cpu_total": None, "ram_used": GB, "ram_total": 8 * GB}, p


old_read = res_watch.read_now
res_watch.read_now = fake_read
lines = []
for i in range(len(seq)):
    res_watch.sample_once(now=1000.0 + 30 * i, emit=lines.append)
res_watch.read_now = old_read
check("logs during the episode and QUIET_TAIL samples after, then stops",
      len(lines) == 2 + res_watch.QUIET_TAIL, len(lines))
rep = res_watch.report()
check("samples kept in memory for /health/loop, newest first, bounded",
      len(rep["samples"]) == len(seq) and rep["samples"][0]["at"] >= rep["samples"][-1]["at"]
      and res_watch.SAMPLES <= 60)

# Linux without psutil: a fake /proc tree.
fake = Path(tempfile.mkdtemp(prefix="fakeproc-"))
(fake / "stat").write_text("cpu  100 0 50 800 50 0 0 0 0 0\n", encoding="utf-8")
(fake / "meminfo").write_text("MemTotal:       8000000 kB\nMemFree:  1000000 kB\nMemAvailable:   2000000 kB\n",
                              encoding="utf-8")


def mkproc(pid, ppid, name, ut, st, rss_pages, cmd):
    d = fake / str(pid)
    d.mkdir()
    fields = ["S", str(ppid)] + ["0"] * 9 + [str(ut), str(st)] + ["0"] * 8 + [str(rss_pages)]
    (d / "stat").write_text(f"{pid} ({name}) " + " ".join(fields) + "\n", encoding="utf-8")
    (d / "cmdline").write_bytes(b"\0".join(c.encode() for c in cmd) + b"\0")


mkproc(500, 1, "python3", 300, 100, 25000, ["python3", "main.py"])
mkproc(501, 500, "node", 50, 10, 10000, ["node", "/usr/lib/node_modules/@anthropic-ai/claude-code/cli.js"])
mkproc(502, 501, "rg", 5, 1, 100, ["rg", "x"])
mkproc(600, 1, "sshd", 9, 9, 100, ["sshd"])
m, ps = res_watch._read_proc(500, base=str(fake))
tick = float(os.sysconf("SC_CLK_TCK"))
check("/proc reader: machine RAM from MemAvailable", round(m["ram_used"] / 1024) == 6000000 and m["ram_total"] > 0,
      m["ram_used"])
check("/proc reader: machine CPU counters", abs(m["cpu_total"] - 1000 / tick) < 1e-6 and
      abs(m["cpu_busy"] - 150 / tick) < 1e-6, (m["cpu_total"], m["cpu_busy"]))
check("/proc reader: only the server and its descendants (grandchild included, stranger left out)",
      sorted(p["pid"] for p in ps) == [500, 501, 502], [p["pid"] for p in ps])
check("/proc reader: the node claude-code process is an engine",
      [p["agent"] for p in sorted(ps, key=lambda p: p["pid"])] == [False, True, False])

check("sampler runs in its own thread (keeps writing while the event loop is stuck)",
      "threading.Thread(target=_run" in read("server/res_watch.py") and "asyncio" not in read("server/res_watch.py"))
check("sampler started with the loop watchdog and given the loop lag",
      "res_watch.start(loop_lag=loop_watch.lag)" in read("server/main.py"))
check("GET /health/loop carries the samples", '"resources": res_watch.report()' in read("server/main.py"))
check("loop_watch.lag() answers from any thread", "def lag()" in read("server/loop_watch.py"))
check("psutil in requirements with a range", "\npsutil>=6.0,<8\n" in read("requirements.txt") + "\n")

# ---------------------------------------------------------------- A. previous log kept
vbs = read("start-unimate.vbs")
i_stop = vbs.find("stop-unimate.bat\"\" > server\\stop-last.log")
i_rot = vbs.find('fso.MoveFile logF, prevF')
i_run = vbs.find("server\\main.py > server\\unimate.log")
check("Windows: the old log moves to unimate.prev.log AFTER the old server is stopped and BEFORE the new one writes",
      0 < i_stop < i_rot < i_run, (i_stop, i_rot, i_run))
check("Windows: an empty log does not wipe a useful previous one", "If fso.GetFile(logF).Size > 0 Then" in vbs)
check("Windows: a file still held is copied instead", "fso.CopyFile logF, prevF, True" in vbs)
up_sh = read("update.sh")
check("update.sh (nohup restart) keeps the previous log too",
      0 < up_sh.find("mv -f server/unimate.log server/unimate.prev.log") < up_sh.find("> unimate.log 2>&1"))
check("the previous log stays out of git", "server/*.log" in read(".gitignore"))

# ---------------------------------------------------------------- D. one server per start
i_lock = vbs.find("If DateDiff(\"s\", fso.GetFile(lockF).DateLastModified, Now) < 60 Then dangKhoi = True")
i_if = vbs.find("If Not dangKhoi Then")
i_end = vbs.find("End If", i_run)
i_open = vbs.find('If LCase(WScript.Arguments(0)) = "/open" Then MoDashboard')
check("a fresh start lock (under 60 s) is read before anything is stopped", 0 < i_lock < i_if < i_stop, (i_lock, i_if))
check("stop and start both sit inside 'If Not dangKhoi'", i_if < i_stop < i_run < i_end, (i_if, i_stop, i_run, i_end))
check("the lock is written before the stop", i_if < vbs.find("fso.CreateTextFile(lockF, True)") < i_stop)
check("a second click still opens the dashboard (/open after the guarded block)", i_end < i_open)
check("new vbs lines are ASCII (wscript reads ANSI)",
      all(ord(c) < 128 for c in vbs[vbs.find("' 0.450.0 (chu repo"):vbs.find("If Not dangKhoi")])
      and all(ord(c) < 128 for c in vbs[vbs.find("  ' 0.450.0: GIU NHAT KY CU"):vbs.find("  ' Ch")]))
main_src = read("server/main.py")
check("the server clears the lock once it is up", '(PROJECT_ROOT / "server" / "start.lock").unlink(missing_ok=True)' in main_src)
upd = read("server/updater.py")
check("the updater clears the lock before its own start (an update is never blocked)",
      0 < upd.find('(ROOT / "server" / "start.lock").unlink(missing_ok=True)') < upd.find('str(ROOT / "start-unimate.vbs")]'))
check("the lock stays out of git", "server/start.lock" in read(".gitignore"))

# ---------------------------------------------------------------- B. offline clock
app = read("dashboard/app.js")
check("the chip clock counts from the drop while offline", "(Date.now() - (activityDownT0 || activityT0))" in app)
check("the drop time is the moment the socket fell, not 2.5 s later",
      "const dropAt = Date.now();" in app and "markOffline(dropAt);" in app)
check("the held-message note counts offline time too", "markOffline();\n  showActivity(Icons.warn(window.t(\"app.ws_giu_tin\")))" in app)
check("hiding the chip clears the offline clock", "function hideActivity() {\n  activityDownT0 = 0;" in app)
check("the running turn gets its own clock back after the reconnect",
      "if (_turnT0BeforeDrop) activityT0 = _turnT0BeforeDrop;" in app and "_turnT0BeforeDrop = activityT0" in app)
check("dashboard loads the new app.js", "/static/app.js?v=158" in read("dashboard/index.html"))

# ---------------------------------------------------------------- E. update status settles
NOW = "2026-11-05T16:40:00"
stuck = {"phase": "restarting", "old_version": "0.448.0", "target_version": "0.449.0", "started_at": "2026-11-05T13:25:00"}
p = update_state.settle_patch(stuck, "0.449.0", NOW)
check("the VPS case: 'restarting' since 13:25 while 0.449.0 runs -> done, success",
      p == {"phase": "done", "result": "success", "finished_at": NOW, "settled_on_boot": True}, p)
check("a later version also closes it", update_state.settle_patch(stuck, "0.450.0", NOW) is not None)
check("still on the old version: left alone (the update may still be going)",
      update_state.settle_patch(stuck, "0.448.0", NOW) is None)
check("health_check left behind is closed the same way",
      update_state.settle_patch({**stuck, "phase": "health_check"}, "0.449.0", NOW) is not None)
check("finished, idle or rolling back: never touched",
      all(update_state.settle_patch({**stuck, "phase": ph}, "0.449.0", NOW) is None
          for ph in ("done", "idle", "rolling_back", "preparing", "installing")))
check("no target recorded: decided by the old version",
      update_state.settle_patch({"phase": "restarting", "old_version": "0.448.0"}, "0.449.0", NOW) is not None
      and update_state.settle_patch({"phase": "restarting"}, "0.449.0", NOW) is None)
check("startup hook: Docker settles at once, a git install waits past the updater's 90 s health check",
      '_UPDATE_SETTLE_WAIT_S = {"docker": 5.0}' in main_src and "_UPDATE_SETTLE_WAIT_DEFAULT_S = 150.0" in main_src
      and "async def _start_update_settle" in main_src)
check("a new update started meanwhile is never overwritten",
      'if st.get("started_at") != first.get("started_at"):' in main_src)

# The hook itself, on a real state file, without the rest of the server.
src = main_src[main_src.index("async def _settle_update_state"):main_src.index('@app.on_event("startup")\nasync def _start_update_settle')]
ns = {"update_state": update_state, "_read_update_state": update_state.read_state,
      "_write_update_state": update_state.write_state, "_read_version": lambda: "0.449.0"}
exec(src, ns)  # noqa: S102 - our own source, to run the hook without importing main
update_state.write_state(stuck)
done = asyncio.run(ns["_settle_update_state"](0.01))
st = update_state.read_state()
check("the hook writes done/success on the state file", done and st["phase"] == "done" and st["result"] == "success"
      and st["started_at"] == stuck["started_at"], st)


async def race():
    update_state.write_state({**stuck, "phase": "restarting", "result": None, "finished_at": None})
    t = asyncio.create_task(ns["_settle_update_state"](0.2))
    await asyncio.sleep(0.05)
    update_state.write_state({"phase": "preparing", "started_at": "2026-11-05T16:39:00"})
    return await t

check("an update started during the wait is left alone",
      asyncio.run(race()) is False and update_state.read_state()["phase"] == "preparing")

print()
if fails:
    print(f"FAIL {len(fails)}: " + " | ".join(fails))
    sys.exit(1)
print("OK - test_hang_diag_0450: all pass")
