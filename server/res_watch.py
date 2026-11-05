"""Resource samples for the server log (0.450.0): CPU and RAM of the machine, the server and its child processes.

Why it exists. On 2026-11-05 the owner's home server stopped answering for about ten minutes while a workflow ran a
claude step, and nobody could tell afterwards whether the machine was overloaded (a child eating the CPU or the RAM)
or the server itself was stuck. The loop watchdog (loop_watch.py) names code that blocks the event loop, but it says
nothing about load. This module fills that gap.

How. A daemon THREAD (never the event loop, so it keeps writing while the loop is frozen) samples every SAMPLE_S:
machine CPU and RAM, the server process, and every descendant (engine CLIs, MCP servers, ffmpeg...). It prints ONE
compact line to stderr (that is server/unimate.log on Windows and Mac) only while something is going on:
- an engine CLI (claude, codex, grok, agy) is running under the server, or
- the server tree uses CPU (TREE_CPU_PCT of the machine or more), or
- the machine is under pressure (CPU or RAM over the PRESSURE thresholds), or
- the event loop is blocked right now (loop_watch);
and for QUIET_TAIL more samples after it calms down, so the end of the episode is visible too. An idle server writes
nothing, so the log does not grow. The last SAMPLES samples are kept in memory for GET /health/loop.

psutil is used when installed (it is in requirements.txt from 0.450.0). Without it Linux reads /proc and Windows reads
the machine's memory through ctypes; per-process numbers then say n/a instead of guessing.
"""
from __future__ import annotations

import os
import sys
import threading
import time
from collections import deque
from typing import Callable, Optional

SAMPLE_S = 30.0
SAMPLES = 40
QUIET_TAIL = 2
TREE_CPU_PCT = 15.0      # share of the WHOLE machine (all cores) used by the server and its children
PRESSURE_CPU = 85.0
PRESSURE_RAM = 90.0
TOP_KIDS = 4
AGENT_NAMES = ("claude", "codex", "grok", "agy")

_samples: deque = deque(maxlen=SAMPLES)
_state = {"started": False, "quiet_left": 0, "prev_tree": {}, "prev_sys": None, "prev_at": 0.0}
_lock = threading.Lock()
LOOP_LAG: Callable[[], Optional[float]] = lambda: None   # set by start(): seconds since the loop last ticked


def _ncpu() -> int:
    return max(1, os.cpu_count() or 1)


# ---------------------------------------------------------------- readers
# Every reader returns plain dicts so the decision and formatting code below is the same on every platform and can be
# tested with made-up numbers.
#   machine: {"cpu_busy": float seconds busy so far | None, "cpu_total": float seconds so far | None,
#             "ram_used": bytes | None, "ram_total": bytes | None}
#   process: {"pid", "ppid", "name", "cpu_s" (user+system seconds), "rss" (bytes), "agent" (bool)}

def _stem(p) -> str:
    return os.path.splitext(os.path.basename(str(p).replace("\\", "/")))[0].lower()


def _is_agent(name: str, cmd: list) -> bool:
    """An engine CLI: claude, codex, grok or agy, run as its own binary or as a node script (claude-code/cli.js)."""
    if _stem(name) in AGENT_NAMES:
        return True
    for c in (cmd or [])[:3]:
        low = str(c).lower().replace("\\", "/")
        if _stem(c) in AGENT_NAMES or "claude-code" in low or "@openai/codex" in low or "/codex/" in low:
            return True
    return False


def _read_psutil(root_pid: int):
    import psutil  # noqa: PLC0415 - optional
    t = psutil.cpu_times()
    idle = getattr(t, "idle", 0.0) + getattr(t, "iowait", 0.0)
    total = sum(t)
    vm = psutil.virtual_memory()
    machine = {"cpu_busy": total - idle, "cpu_total": total, "ram_used": vm.total - vm.available,
               "ram_total": vm.total}
    procs = []
    try:
        root = psutil.Process(root_pid)
        tree = [root] + root.children(recursive=True)
    except psutil.Error:
        tree = []
    for p in tree:
        try:
            with p.oneshot():
                ct = p.cpu_times()
                name = p.name()
                try:
                    cmd = p.cmdline()[:3]
                except psutil.Error:
                    cmd = []
                procs.append({"pid": p.pid, "ppid": p.ppid(), "name": name, "cpu_s": ct.user + ct.system,
                              "rss": p.memory_info().rss, "agent": _is_agent(name, cmd)})
        except psutil.Error:
            continue
    return machine, procs


def _read_proc(root_pid: int, base: str = "/proc"):
    """Linux without psutil. `base` is a parameter so tests can point it at a fake tree."""
    tick = float(os.sysconf("SC_CLK_TCK")) if hasattr(os, "sysconf") else 100.0
    page = float(os.sysconf("SC_PAGE_SIZE")) if hasattr(os, "sysconf") else 4096.0
    machine = {"cpu_busy": None, "cpu_total": None, "ram_used": None, "ram_total": None}
    try:
        with open(f"{base}/stat", encoding="utf-8") as f:
            vals = [float(x) for x in f.readline().split()[1:]]
        idle = vals[3] + (vals[4] if len(vals) > 4 else 0.0)
        machine["cpu_total"] = sum(vals[:8]) / tick
        machine["cpu_busy"] = machine["cpu_total"] - idle / tick
    except (OSError, ValueError, IndexError):
        pass
    try:
        mem = {}
        with open(f"{base}/meminfo", encoding="utf-8") as f:
            for line in f:
                k, _, rest = line.partition(":")
                mem[k] = float(rest.split()[0]) * 1024
        machine["ram_total"] = mem["MemTotal"]
        machine["ram_used"] = mem["MemTotal"] - mem.get("MemAvailable", mem.get("MemFree", 0.0))
    except (OSError, ValueError, KeyError, IndexError):
        pass
    rows = {}
    try:
        names = os.listdir(base)
    except OSError:
        names = []
    for d in names:
        if not d.isdigit():
            continue
        try:
            with open(f"{base}/{d}/stat", encoding="utf-8") as f:
                raw = f.read()
            name = raw[raw.index("(") + 1:raw.rindex(")")]
            rest = raw[raw.rindex(")") + 2:].split()
            # rest[0] = state (field 3), so field N sits at rest[N - 3].
            rows[int(d)] = {"pid": int(d), "ppid": int(rest[1]), "name": name,
                            "cpu_s": (float(rest[11]) + float(rest[12])) / tick, "rss": float(rest[21]) * page}
        except (OSError, ValueError, IndexError):
            continue
    keep = {root_pid} if root_pid in rows else set()
    grew = True
    while grew:
        grew = False
        for pid, r in rows.items():
            if pid not in keep and r["ppid"] in keep:
                keep.add(pid)
                grew = True
    procs = []
    for pid in sorted(keep):
        r = dict(rows[pid])
        cmd = []
        try:
            with open(f"{base}/{pid}/cmdline", "rb") as f:
                cmd = [c.decode("utf-8", "replace") for c in f.read().split(b"\0") if c][:3]
        except OSError:
            pass
        r["agent"] = _is_agent(r["name"], cmd)
        procs.append(r)
    return machine, procs


def _read_windows_basic(root_pid: int):
    """Windows without psutil: machine memory only (ctypes, no install). Per-process numbers stay unknown."""
    machine = {"cpu_busy": None, "cpu_total": None, "ram_used": None, "ram_total": None}
    try:
        import ctypes  # noqa: PLC0415

        class _Mem(ctypes.Structure):
            _fields_ = [("dwLength", ctypes.c_ulong), ("dwMemoryLoad", ctypes.c_ulong),
                        ("ullTotalPhys", ctypes.c_ulonglong), ("ullAvailPhys", ctypes.c_ulonglong),
                        ("ullTotalPageFile", ctypes.c_ulonglong), ("ullAvailPageFile", ctypes.c_ulonglong),
                        ("ullTotalVirtual", ctypes.c_ulonglong), ("ullAvailVirtual", ctypes.c_ulonglong),
                        ("ullAvailExtendedVirtual", ctypes.c_ulonglong)]
        m = _Mem()
        m.dwLength = ctypes.sizeof(_Mem)
        if ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(m)):
            machine["ram_total"] = float(m.ullTotalPhys)
            machine["ram_used"] = float(m.ullTotalPhys - m.ullAvailPhys)
    except Exception:  # noqa: BLE001 - diagnostics only
        pass
    return machine, None


def read_now(root_pid: Optional[int] = None):
    """(machine, procs or None) right now, from the best reader this machine has."""
    pid = root_pid or os.getpid()
    try:
        return _read_psutil(pid)
    except ImportError:
        pass
    except Exception:  # noqa: BLE001 - a broken psutil must not stop the samples
        pass
    if os.path.isdir("/proc"):
        return _read_proc(pid)
    if os.name == "nt":
        return _read_windows_basic(pid)
    return {"cpu_busy": None, "cpu_total": None, "ram_used": None, "ram_total": None}, None


# ---------------------------------------------------------------- one sample
def build_sample(machine: dict, procs, prev_sys, prev_tree: dict, wall_s: float, root_pid: int,
                 ncpu: int, loop_lag: Optional[float], at: Optional[float] = None) -> dict:
    """Turn two readings into one sample (percentages over the last `wall_s` seconds). Pure, for tests."""
    s = {"at": at if at is not None else time.time(), "cpu": None, "ram_pct": None, "ram_used_gb": None,
         "ram_total_gb": None, "server_gb": None, "server_cpu": None, "tree_cpu": None, "kids": None,
         "agents": 0, "top": [], "lag": round(loop_lag, 1) if loop_lag is not None else None}
    busy, total = machine.get("cpu_busy"), machine.get("cpu_total")
    if prev_sys and busy is not None and prev_sys[0] is not None and total is not None and prev_sys[1] is not None:
        d_total = total - prev_sys[1]
        if d_total > 0:
            s["cpu"] = round(max(0.0, min(100.0, (busy - prev_sys[0]) / d_total * 100)), 1)
    if machine.get("ram_total"):
        s["ram_total_gb"] = round(machine["ram_total"] / 1024 ** 3, 1)
        s["ram_used_gb"] = round((machine.get("ram_used") or 0) / 1024 ** 3, 1)
        s["ram_pct"] = round((machine.get("ram_used") or 0) / machine["ram_total"] * 100, 1)
    if procs is None:
        return s
    cap = max(wall_s, 0.001) * max(1, ncpu)

    def pct(p):
        old = prev_tree.get((p["pid"], p["name"]))
        return round(max(0.0, (p["cpu_s"] - old) / cap * 100), 1) if old is not None else 0.0

    kids = []
    tree_cpu = 0.0
    for p in procs:
        c = pct(p)
        tree_cpu += c
        if p["pid"] == root_pid:
            s["server_gb"] = round(p["rss"] / 1024 ** 3, 2)
            s["server_cpu"] = c
        else:
            kids.append({"name": p["name"], "cpu": c, "gb": round(p["rss"] / 1024 ** 3, 2), "agent": p["agent"]})
    s["tree_cpu"] = round(tree_cpu, 1)
    s["kids"] = len(kids)
    s["agents"] = sum(1 for k in kids if k["agent"])
    kids.sort(key=lambda k: (k["cpu"], k["gb"]), reverse=True)
    s["top"] = kids[:TOP_KIDS]
    return s


def worth_logging(s: dict) -> bool:
    """Is something going on that the log should show?"""
    return bool(s.get("agents") or (s.get("tree_cpu") or 0) >= TREE_CPU_PCT
                or (s.get("cpu") or 0) >= PRESSURE_CPU or (s.get("ram_pct") or 0) >= PRESSURE_RAM
                or (s.get("lag") or 0) >= 2.0)


def _n(v, unit="", nd=None):
    if v is None:
        return "n/a"
    return f"{v:g}{unit}" if nd is None else f"{round(v, nd):g}{unit}"


def format_line(s: dict) -> str:
    """One compact log line, e.g.
    [res] 16:10:30 cpu 87% ram 13.1/15.8 GB 83% | server 1.21 GB 4% | 6 children: claude.exe 61% 0.84 GB, ... | lag 0.2s
    """
    clock = time.strftime("%H:%M:%S", time.localtime(s.get("at") or time.time()))
    parts = [f"[res] {clock} cpu {_n(s.get('cpu'), '%')} ram {_n(s.get('ram_used_gb'))}/{_n(s.get('ram_total_gb'))} GB "
             f"{_n(s.get('ram_pct'), '%')}"]
    if s.get("kids") is None:
        parts.append("processes n/a (psutil missing)")
    else:
        parts.append(f"server {_n(s.get('server_gb'))} GB {_n(s.get('server_cpu'), '%')}")
        top = ", ".join(f"{k['name']} {k['cpu']:g}% {k['gb']:g} GB" for k in s.get("top") or [])
        parts.append(f"{s['kids']} children" + (f": {top}" if top else ""))
    if s.get("lag") is not None:
        parts.append(f"lag {s['lag']:g}s")
    return " | ".join(parts)


def sample_once(now: Optional[float] = None, emit: Callable[[str], None] = None) -> dict:
    """Take one sample, keep it, and print it when worth it (or in the quiet tail after an episode)."""
    now = now if now is not None else time.monotonic()
    machine, procs = read_now()
    try:
        lag = LOOP_LAG()
    except Exception:  # noqa: BLE001
        lag = None
    with _lock:
        wall = (now - _state["prev_at"]) if _state["prev_at"] else SAMPLE_S
        s = build_sample(machine, procs, _state["prev_sys"], _state["prev_tree"], wall, os.getpid(), _ncpu(), lag)
        _state["prev_sys"] = (machine.get("cpu_busy"), machine.get("cpu_total"))
        _state["prev_tree"] = {(p["pid"], p["name"]): p["cpu_s"] for p in (procs or [])}
        _state["prev_at"] = now
        _samples.append(s)
        busy = worth_logging(s)
        if busy:
            _state["quiet_left"] = QUIET_TAIL
            show = True
        elif _state["quiet_left"] > 0:
            _state["quiet_left"] -= 1
            show = True
        else:
            show = False
    if show:
        (emit or (lambda line: print(line, file=sys.stderr, flush=True)))(format_line(s))
    return s


def _run() -> None:
    while True:
        try:
            sample_once()
        except Exception:  # noqa: BLE001 - diagnostics must never kill anything
            pass
        time.sleep(SAMPLE_S)


def start(loop_lag: Optional[Callable[[], Optional[float]]] = None) -> bool:
    """Start the sampler thread (call from a startup hook). Idempotent. UNIMATE_RES_WATCH=0 turns it off."""
    global LOOP_LAG
    if _state["started"] or os.environ.get("UNIMATE_RES_WATCH", "1") == "0":
        return False
    if loop_lag is not None:
        LOOP_LAG = loop_lag
    _state["started"] = True
    threading.Thread(target=_run, name="unimate-res-watch", daemon=True).start()
    return True


def report() -> dict:
    """The recent samples, newest first, for GET /health/loop."""
    with _lock:
        items = [dict(s) for s in reversed(_samples)]
    return {"running": bool(_state["started"]), "sample_s": SAMPLE_S, "samples": items}
