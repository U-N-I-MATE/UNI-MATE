"""0.445.0: a small VPS no longer stalls - heavy work on worker threads, loop stats stop probing the disk day by day, and
the brain picker's note count only counts what syncs.

    python tests/run.py small_vps_no_stall_0445      (NO network)

Owner, 2026-11-04: the 1-core VPS now and then showed Traefik's "404 page not found". Common root: blocking work run
right on the event loop delays the /health check, Docker marks the container unhealthy and Traefik drops the route.
Checks here:
  1. the event loop keeps "breathing" (a 10 ms heartbeat task) while 06 routes do a fake 0.4 second heavy job;
  2. loop_events with since=0 (saved_total) does not ask `exists()` for every day since 1970, it lists existing files;
  3. GET /brains counts notes without the files each machine writes for itself (never synced), so home and VPS agree;
  4. dashboard/fetch-gop.js spreads retry waits within ±30% (tests/js does not run here, checked with node if present).
The checks rely on the heartbeat gap (0.4 second sleep vs a 0.2 second ceiling), not on machine speed.
"""
from _paths import ROOT, SERVER  # noqa: E402,F401
import asyncio
import os
import shutil
import subprocess
import sys
import tempfile
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

_STATE = tempfile.mkdtemp(prefix="unimate-0445-")
os.environ["UNIMATE_STATE_DIR"] = _STATE
_BRAINS = tempfile.mkdtemp(prefix="unimate-0445-brains-")
os.environ["BRAINS_DIR"] = _BRAINS
os.environ["UNIMATE_ALLOWED_HOSTS"] = "testserver"
try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

_fails = []


def check(name, cond, extra=""):
    print(("ok   " if cond else "FAIL ") + name + (("  [" + str(extra)[:300] + "]") if not cond else ""))
    if not cond:
        _fails.append(name)


import httpx  # noqa: E402
import main  # noqa: E402
import optional_tools  # noqa: E402
import task_stats  # noqa: E402
import tinh_gon  # noqa: E402

BASE = Path(main.BRAINS_DIR)
if BASE.resolve() != Path(_BRAINS).resolve():
    print(f"FAIL BRAINS_DIR does not point at the temp folder: {BASE}. STOP so nothing is written into a real brain.")
    sys.exit(1)

# ---------- 1. the event loop keeps breathing ----------
SLEEP = 0.4
CEILING = 0.2


def _heavy(*_a, **_k):
    time.sleep(SLEEP)


async def _measure(method, url):
    gap = {"max": 0.0, "stop": False}

    async def heartbeat():
        t = time.monotonic()
        while not gap["stop"]:
            await asyncio.sleep(0.01)
            n = time.monotonic()
            gap["max"] = max(gap["max"], n - t)
            t = n

    task = asyncio.create_task(heartbeat())
    await asyncio.sleep(0.05)
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=main.app), base_url="http://testserver") as c:
        r = await c.request(method, url)
    gap["stop"] = True
    await task
    return r, gap["max"]


def _breathes(label, url, patches):
    """patches: list of (object, attribute name, replacement) - applied, then restored after measuring."""
    saved = [(o, a, getattr(o, a)) for o, a, _ in patches]
    for o, a, f in patches:
        setattr(o, a, f)
    try:
        r, gap = asyncio.run(_measure("GET", url))
    finally:
        for o, a, f in saved:
            setattr(o, a, f)
    check(f"{label}: the event loop keeps running during the heavy work (largest gap {gap:.2f}s, ceiling {CEILING}s)",
          gap < CEILING, gap)
    check(f"{label}: still answers normally (HTTP {r.status_code})", r.status_code == 200, r.text[:200])
    return r


st = main.task_stats_feature


def _compute(*_a, **_k):
    _heavy()
    return {"ok": True, "ai": {}}


r = _breathes("GET /tasks/stats", "/tasks/stats", [(st, "compute", _compute), (st, "saved_total", lambda b: 7)])
check("GET /tasks/stats: saved_total is still merged into the result", (r.json().get("ai") or {}).get("saved_total") == 7,
      r.json())


def _map(brain):
    _heavy()
    return {"bots": [], "jobs": {}}


r = _breathes("GET /tasks/bots", "/tasks/bots", [(main.bot_jobs_feature, "map", _map)])
check("GET /tasks/bots: response shape unchanged", r.json() == {"ok": True, "bots": [], "jobs": {}}, r.json())


def _tool_list():
    _heavy()
    return []


r = _breathes("GET /tools/optional", "/tools/optional",
              [(optional_tools, "danh_sach", _tool_list), (main.cfgmod, "valid_session", lambda t: True)])
check("GET /tools/optional: response shape unchanged", r.json() == {"ok": True, "tools": []}, r.json())


def _fps(html):
    _heavy()
    return {}


r = _breathes("GET /app-version", "/app-version", [(main, "_asset_fps", _fps)])
check("GET /app-version: still has a version", bool(r.json().get("version")), r.json())
_breathes("GET / (main page)", "/", [(main, "_asset_fps", _fps)])

_real_minify = tinh_gon.ban_phuc_vu


def _slow_minify(full, path):
    _heavy()
    return _real_minify(full, path)


js = next((p.name for p in sorted(Path(main.DASHBOARD_PATH).glob("*.js"))), None)
if js:
    _breathes(f"GET /static/{js} (minified copy)", f"/static/{js}", [(tinh_gon, "ban_phuc_vu", _slow_minify)])
else:
    check("the dashboard has a .js file to try", False)

# ---------- 2. loop_events does not probe the disk day by day ----------
TZ = timezone(timedelta(hours=7))
brain = Path(tempfile.mkdtemp(prefix="unimate-0445-loop-"))
ld = brain / "UniMate" / "loop-log"
ld.mkdir(parents=True)
# Log text is data as UNI MATE writes it ("Lỗi:" marks a failed run), so it stays as is.
(ld / "2026-11-02.md").write_text("\n## [2026-11-02 08:15] clean-inbox · loop (custom/full) - scheduled\nĐã dọn 3 thư.\n",
                                  encoding="utf-8")
(ld / "2026-11-03.md").write_text("\n## [2026-11-03 09:00] clean-inbox · loop (custom/full) - scheduled\nLỗi: hết hạn mức\n",
                                  encoding="utf-8")
(ld / "2025-01-01.md").write_text("\n## [2025-01-01 10:00] old · loop (custom/full) - scheduled\nok\n", encoding="utf-8")
(ld / "note.md").write_text("not a daily log\n", encoding="utf-8")
(ld / "2026-13-40.md").write_text("\n## [2026-12-01 10:00] broken · loop (custom/full) - scheduled\nx\n", encoding="utf-8")

_exists = Path.exists
calls = {"n": 0}


def _counting_exists(self, *a, **k):
    calls["n"] += 1
    return _exists(self, *a, **k)


Path.exists = _counting_exists
try:
    t0 = time.monotonic()
    every = task_stats.loop_events(str(brain), 0, time.time() + 60, TZ)
    took = time.monotonic() - t0
finally:
    Path.exists = _exists
check(f"since=0 (saved_total): exists() asked {calls['n']} time(s) (old code ~20,000, once per day since 1970)",
      calls["n"] < 5, calls["n"])
check(f"since=0: done in {took * 1000:.0f} ms", took < 0.5, took)
check("since=0: reads all 03 runs from the 03 valid daily files", len(every) == 3, every)
check("skips files that are not dates and invalid date names", all(e["title"] in ("clean-inbox", "old") for e in every), every)
check("a run starting with 'Lỗi:' still counts as failed",
      [e["status"] for e in every if e["ts"] >= datetime(2026, 11, 3, tzinfo=TZ).timestamp()] == ["fail"], every)
check("sorted by day ascending", [e["ts"] for e in every] == sorted(e["ts"] for e in every), every)
window = task_stats.loop_events(str(brain), datetime(2026, 11, 2, tzinfo=TZ).timestamp(),
                                datetime(2026, 11, 3, tzinfo=TZ).timestamp(), TZ)
check("only 2026-11-02: exactly 01 run (files outside the range are skipped)", [e["title"] for e in window] == ["clean-inbox"],
      window)
check("no folder yet: empty", task_stats.loop_events(tempfile.mkdtemp(), 0, time.time(), TZ) == [])

# ---------- 3. the brain picker's note count only counts what syncs ----------
b = BASE / "Brain_0445"


def _write(rel):
    p = b / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text("# x\n", encoding="utf-8")


SHARED = ["notes/a.md", "notes/b.md", "memory/MEMORY.md", "memory/facts/f.md", "UniMate/loops/l.md", "agents/ag.md",
          "skills/s/SKILL.md"]
PRIVATE = ["memory/conversations/2026-11-01.md", "UniMate/loop-log/2026-11-01.md", "UniMate/learn-log/2026-11-01.md",
           "UniMate/learn-staging/x.md", "memory/agents/ag/runs/r1.md", "UniMate/index.md"]
for rel in SHARED + PRIVATE:
    _write(rel)
check("raw count (default, the folder browser is unchanged) still counts everything",
      main._count_md(str(b), 10_000) == len(SHARED) + len(PRIVATE))
check(f"synced_only=True: only the {len(SHARED)} synced files", main._count_md(str(b), 10_000, synced_only=True) == len(SHARED),
      main._count_md(str(b), 10_000, synced_only=True))
ds = {x["name"]: x for x in main._list_brains_sync()["brains"]}
check("GET /brains: note count = synced files (each machine's private logs left out)",
      (ds.get("Brain_0445") or {}).get("notes") == len(SHARED), ds.get("Brain_0445"))
# Two machines with the same shared part and different private logs must show the same number.
b2 = BASE / "Brain_0445_vps"
shutil.copytree(b, b2)
shutil.rmtree(b2 / "memory" / "conversations")
(b2 / "memory" / "conversations").mkdir()
for i in range(5):
    (b2 / "memory" / "conversations" / f"2026-10-{i + 1:02d}.md").write_text("x", encoding="utf-8")
check("home machine and VPS with different private logs show the same number",
      main._count_md(str(b), 10_000, synced_only=True) == main._count_md(str(b2), 10_000, synced_only=True))

# ---------- 4. retry waits are spread ----------
node = shutil.which("node")
if node:
    code = ("const g=require(process.argv[1]);let lo=1e9,hi=0;for(let i=0;i<5000;i++){const v=g.jitter(1000);"
            "lo=Math.min(lo,v);hi=Math.max(hi,v)}console.log(lo+' '+hi)")
    res = subprocess.run([node, "-e", code, str(Path(ROOT) / "dashboard" / "fetch-gop.js")], capture_output=True,
                         text=True, timeout=30)
    try:
        lo, hi = map(int, res.stdout.split())
    except ValueError:
        lo, hi = -1, -1
    check(f"fetch-gop jitter(1000) stays within 700..1300 (got {lo}..{hi})", 700 <= lo and hi <= 1300, res.stderr[:200])
    check("fetch-gop jitter really spreads (not one fixed beat)", hi - lo > 300, (lo, hi))
else:
    print("skip fetch-gop: no node")

print()
if _fails:
    print(f"FAIL {len(_fails)}: {_fails}")
    sys.exit(1)
print("OK - test_small_vps_no_stall_0445: all pass")
