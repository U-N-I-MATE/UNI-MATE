"""0.445.0: VPS nhỏ không đứng hình - các việc nặng ở luồng phụ, thống kê vòng lặp không hỏi đĩa từng ngày, số ghi chú ở ô
chọn não chỉ đếm phần được đồng bộ.

    python tests/run.py vps_khong_dung_hinh_0445      (KHÔNG mạng)

Chủ dự án 04/11/2026: VPS (1 nhân) lúc lúc hiện "404 page not found" của Traefik. Gốc chung: một việc đồng bộ chạy ngay
trên vòng sự kiện thì bước kiểm tra sức khoẻ /health trễ, Docker gắn unhealthy, Traefik gỡ đường. Phép kiểm ở đây:
  1. vòng sự kiện vẫn "thở" (một tác vụ đếm nhịp 10 ms) trong lúc 06 đường xử lý làm một việc giả nặng 0,4 giây;
  2. loop_events với since=0 (saved_total) không hỏi `exists()` cho từng ngày từ 1970, chỉ duyệt tệp đang có;
  3. GET /brains đếm ghi chú bỏ các tệp mỗi máy tự ghi (không đồng bộ), để máy nhà và VPS ra cùng một số;
  4. dashboard/fetch-gop.js rải lần chờ thử lại trong ±30% (tests/js không chạy ở đây, kiểm bằng node nếu có).
Phép kiểm dựa trên khoảng hở nhịp (0,4 giây ngủ so với trần 0,2 giây), không dựa trên tốc độ máy.
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


def check(name, cond, them=""):
    print(("ok   " if cond else "FAIL ") + name + (("  [" + str(them)[:300] + "]") if not cond else ""))
    if not cond:
        _fails.append(name)


import httpx  # noqa: E402
import main  # noqa: E402
import optional_tools  # noqa: E402
import task_stats  # noqa: E402
import tinh_gon  # noqa: E402

BASE = Path(main.BRAINS_DIR)
if BASE.resolve() != Path(_BRAINS).resolve():
    print(f"FAIL BRAINS_DIR không trỏ vào thư mục tạm: {BASE}. DỪNG để khỏi ghi rác vào brain thật.")
    sys.exit(1)

# ---------- 1. vòng sự kiện vẫn thở ----------
NGU = 0.4
TRAN = 0.2


def _nang(*_a, **_k):
    time.sleep(NGU)


async def _do(method, url):
    hop = {"max": 0.0, "dung": False}

    async def nhip():
        t = time.monotonic()
        while not hop["dung"]:
            await asyncio.sleep(0.01)
            n = time.monotonic()
            hop["max"] = max(hop["max"], n - t)
            t = n

    tk = asyncio.create_task(nhip())
    await asyncio.sleep(0.05)
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=main.app), base_url="http://testserver") as c:
        r = await c.request(method, url)
    hop["dung"] = True
    await tk
    return r, hop["max"]


def _tho(ten, url, va):
    """va: list (đối tượng, tên thuộc tính, hàm thay) - vá rồi trả lại sau khi đo."""
    cu = [(o, a, getattr(o, a)) for o, a, _ in va]
    for o, a, f in va:
        setattr(o, a, f)
    try:
        r, gap = asyncio.run(_do("GET", url))
    finally:
        for o, a, f in cu:
            setattr(o, a, f)
    check(f"{ten}: vòng sự kiện vẫn chạy trong lúc làm việc nặng (khoảng hở lớn nhất {gap:.2f}s, trần {TRAN}s)",
          gap < TRAN, gap)
    check(f"{ten}: vẫn trả lời bình thường (HTTP {r.status_code})", r.status_code == 200, r.text[:200])
    return r


st = main.task_stats_feature


def _compute(*_a, **_k):
    _nang()
    return {"ok": True, "ai": {}}


r = _tho("GET /tasks/stats", "/tasks/stats", [(st, "compute", _compute), (st, "saved_total", lambda b: 7)])
check("GET /tasks/stats: vẫn ghép saved_total vào kết quả", (r.json().get("ai") or {}).get("saved_total") == 7, r.json())


def _map(brain):
    _nang()
    return {"bots": [], "jobs": {}}


r = _tho("GET /tasks/bots", "/tasks/bots", [(main.bot_jobs_feature, "map", _map)])
check("GET /tasks/bots: giữ nguyên dạng trả lời", r.json() == {"ok": True, "bots": [], "jobs": {}}, r.json())


def _ds():
    _nang()
    return []


r = _tho("GET /tools/optional", "/tools/optional",
         [(optional_tools, "danh_sach", _ds), (main.cfgmod, "valid_session", lambda t: True)])
check("GET /tools/optional: giữ nguyên dạng trả lời", r.json() == {"ok": True, "tools": []}, r.json())


def _fps(html):
    _nang()
    return {}


r = _tho("GET /app-version", "/app-version", [(main, "_asset_fps", _fps)])
check("GET /app-version: vẫn có phiên bản", bool(r.json().get("version")), r.json())
_tho("GET / (trang chính)", "/", [(main, "_asset_fps", _fps)])

_ban_that = tinh_gon.ban_phuc_vu


def _gon(full, path):
    _nang()
    return _ban_that(full, path)


js = next((p.name for p in sorted(Path(main.DASHBOARD_PATH).glob("*.js"))), None)
if js:
    _tho(f"GET /static/{js} (bản thu gọn)", f"/static/{js}", [(tinh_gon, "ban_phuc_vu", _gon)])
else:
    check("có tệp .js trong dashboard để thử", False)

# ---------- 2. loop_events không hỏi đĩa từng ngày ----------
TZ = timezone(timedelta(hours=7))
brain = Path(tempfile.mkdtemp(prefix="unimate-0445-loop-"))
ld = brain / "UniMate" / "loop-log"
ld.mkdir(parents=True)
(ld / "2026-11-02.md").write_text("\n## [2026-11-02 08:15] don-hop-thu · loop (custom/full) - scheduled\nĐã dọn 3 thư.\n", encoding="utf-8")
(ld / "2026-11-03.md").write_text("\n## [2026-11-03 09:00] don-hop-thu · loop (custom/full) - scheduled\nLỗi: hết hạn mức\n", encoding="utf-8")
(ld / "2025-01-01.md").write_text("\n## [2025-01-01 10:00] cu · loop (custom/full) - scheduled\nok\n", encoding="utf-8")
(ld / "ghi-chu.md").write_text("không phải nhật ký ngày\n", encoding="utf-8")
(ld / "2026-13-40.md").write_text("\n## [2026-12-01 10:00] hong · loop (custom/full) - scheduled\nx\n", encoding="utf-8")

_exists = Path.exists
dem = {"n": 0}


def _exists_dem(self, *a, **k):
    dem["n"] += 1
    return _exists(self, *a, **k)


Path.exists = _exists_dem
try:
    t0 = time.monotonic()
    tat_ca = task_stats.loop_events(str(brain), 0, time.time() + 60, TZ)
    ton = time.monotonic() - t0
finally:
    Path.exists = _exists
check(f"since=0 (saved_total): hỏi exists() {dem['n']} lần (mã cũ ~20.000, một lần mỗi ngày từ 1970)", dem["n"] < 5, dem["n"])
check(f"since=0: xong trong {ton * 1000:.0f} ms", ton < 0.5, ton)
check("since=0: đọc đủ 03 lượt chạy của 03 tệp ngày hợp lệ", len(tat_ca) == 3, tat_ca)
check("bỏ qua tệp không phải ngày và tên ngày sai", all(e["title"] in ("don-hop-thu", "cu") for e in tat_ca), tat_ca)
check("lượt bắt đầu bằng 'Lỗi:' vẫn tính là lỗi", [e["status"] for e in tat_ca if e["ts"] >= datetime(2026, 11, 3, tzinfo=TZ).timestamp()] == ["fail"], tat_ca)
check("thứ tự theo ngày tăng dần", [e["ts"] for e in tat_ca] == sorted(e["ts"] for e in tat_ca), tat_ca)
khoang = task_stats.loop_events(str(brain), datetime(2026, 11, 2, tzinfo=TZ).timestamp(),
                                datetime(2026, 11, 3, tzinfo=TZ).timestamp(), TZ)
check("chỉ khoảng 02/11: đúng 01 lượt (không lấy tệp ngoài khoảng)", [e["title"] for e in khoang] == ["don-hop-thu"], khoang)
check("thư mục chưa có: trả rỗng", task_stats.loop_events(tempfile.mkdtemp(), 0, time.time(), TZ) == [])

# ---------- 3. số ghi chú ở ô chọn não chỉ đếm phần đồng bộ ----------
b = BASE / "Brain_0445"


def _ghi(rel):
    p = b / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text("# x\n", encoding="utf-8")


CHUNG = ["notes/a.md", "notes/b.md", "memory/MEMORY.md", "memory/facts/f.md", "UniMate/loops/l.md", "agents/ag.md",
         "skills/s/SKILL.md"]
RIENG = ["memory/conversations/2026-11-01.md", "UniMate/loop-log/2026-11-01.md", "UniMate/learn-log/2026-11-01.md",
         "UniMate/learn-staging/x.md", "memory/agents/ag/runs/r1.md", "UniMate/index.md"]
for rel in CHUNG + RIENG:
    _ghi(rel)
check("tự đếm thô (mặc định, trang duyệt thư mục giữ như cũ) vẫn ra đủ", main._count_md(str(b), 10_000) == len(CHUNG) + len(RIENG))
check(f"chi_dong_bo=True: chỉ {len(CHUNG)} tệp đồng bộ", main._count_md(str(b), 10_000, chi_dong_bo=True) == len(CHUNG),
      main._count_md(str(b), 10_000, chi_dong_bo=True))
ds = {x["name"]: x for x in main._list_brains_sync()["brains"]}
check("GET /brains: số ghi chú = số tệp được đồng bộ (bỏ nhật ký mỗi máy)", (ds.get("Brain_0445") or {}).get("notes") == len(CHUNG),
      ds.get("Brain_0445"))
# Hai máy cùng phần chung, khác phần nhật ký riêng: phải ra cùng một số.
b2 = BASE / "Brain_0445_vps"
shutil.copytree(b, b2)
shutil.rmtree(b2 / "memory" / "conversations")
(b2 / "memory" / "conversations").mkdir()
for i in range(5):
    (b2 / "memory" / "conversations" / f"2026-10-{i + 1:02d}.md").write_text("x", encoding="utf-8")
check("máy nhà và VPS khác nhật ký riêng vẫn ra cùng một số",
      main._count_md(str(b), 10_000, chi_dong_bo=True) == main._count_md(str(b2), 10_000, chi_dong_bo=True))

# ---------- 4. rải lần chờ thử lại ----------
node = shutil.which("node")
if node:
    ma = ("const g=require(process.argv[1]);let lo=1e9,hi=0;for(let i=0;i<5000;i++){const v=g.rai(1000);lo=Math.min(lo,v);"
          "hi=Math.max(hi,v)}console.log(lo+' '+hi)")
    ra = subprocess.run([node, "-e", ma, str(Path(ROOT) / "dashboard" / "fetch-gop.js")], capture_output=True, text=True,
                        timeout=30)
    try:
        lo, hi = map(int, ra.stdout.split())
    except ValueError:
        lo, hi = -1, -1
    check(f"fetch-gop rai(1000) nằm trong 700..1300 (ra {lo}..{hi})", 700 <= lo and hi <= 1300, ra.stderr[:200])
    check("fetch-gop rai thật sự rải (không cố định một nhịp)", hi - lo > 300, (lo, hi))
else:
    print("skip fetch-gop: không có node")

print()
if _fails:
    print(f"FAIL {len(_fails)}: {_fails}")
    sys.exit(1)
print("OK - test_vps_khong_dung_hinh_0445: all pass")
