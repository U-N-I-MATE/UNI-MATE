"""Which machine runs the schedules when one owner has two UNI MATE (0.452.0).

The owner runs UNI MATE at home (Windows) and on a VPS. The brains sync through GitHub, so every
reminder, loop and habit reminder exists on both machines, and before this module both fired: a
Mộc Tử post went out twice. The owner decided (2026-11-16) that ONE machine runs the schedules, the
VPS by default; the other machine keeps chatting normally.

Pieces, all in this file so the rule lives in one place:

1. **Identity.** Each machine makes a random id once and keeps it in its own state folder
   (`STATE_DIR/may_chay_lich.json`: `/data` on Docker, survives updates and a recreated container;
   `server/` at home, never touched by an update). Its kind is "vps" (Docker, or a Linux server) or
   "home" (Windows, macOS); `UNIMATE_MACHINE_KIND` overrides it.
2. **Who runs.** `UniMate/may_chay_lich.json` in every brain holds the choice ("vps" | "home") with
   its time, and each machine announces itself in `UniMate/may/<id>.json` (one file per machine, so
   two machines never edit the same file). The newest choice wins.
3. **Link.** Brain sync runs every few hours, too slow for "change who runs". The VPS makes a link
   code (its address + a random key, only a hash of the key is kept); the owner pastes it at home
   once. Home then asks the VPS who runs every minute, registers itself, and claims runs there.
4. **Ledger.** Before a scheduled run, an outside action of a scheduled run, or a customer bot reply,
   the machine claims a key (schedule id + slot, or channel + message). The VPS holds the ledger; a
   key already held by another machine is skipped. Home that cannot reach the VPS keeps going only
   for what it was told to run, writes the claim locally and sends it later.

`should_run(pin)` is the one question the scheduler asks. A machine whose kind is not chosen still
runs when no machine of the chosen kind is known (a user with one machine is never left with no
schedules at all).
"""
from __future__ import annotations

import asyncio
import base64
import hashlib
import hmac
import json
import os
import secrets
import socket
import sqlite3
import sys
import threading
import time
from pathlib import Path
from typing import Callable, Iterable, List, Optional

from config import STATE_DIR

KINDS = ("vps", "home")
PIN_ALIASES = {"vps": "vps", "may_chu": "vps", "server": "vps",
               "home": "home", "may_nha": "home", "nha": "home", "local": "home"}
STATE_FILE = Path(STATE_DIR) / "may_chay_lich.json"
LEDGER_FILE = Path(STATE_DIR) / "lich_da_chay.sqlite3"
SYNC_RUNNER = ("UniMate", "may_chay_lich.json")
SYNC_MACHINES = ("UniMate", "may")
HEADER = "X-UniMate-Pair"
CODE_PREFIX = "unimate-may:"
SEEN_DAYS = 45                # a machine not heard of for this long no longer counts
REMOTE_FRESH_S = 600          # the VPS answer about who runs is trusted this long
TICK_S = 60
HTTP_TIMEOUT_S = 6
KEEP_S = 40 * 86400           # ledger rows kept this long
MAX_PAIR_CODES = 5
MAX_TAKEN_CACHE = 5000

_lock = threading.RLock()
_brains_fn: Callable[[], Iterable] = lambda: []
_listeners: List[Callable[[], None]] = []
_remote = {"runner": "", "updated_at": 0.0, "ok_at": 0.0, "error": "", "vps": {}}
_taken: set = set()
_db: Optional[sqlite3.Connection] = None
_last_should = {"v": None}
_published = {}               # brain root -> what was last written there
_cache = {}                   # short-lived reads of the brain files: (time, value)
CACHE_S = 20


# ---------------------------------------------------------------- local state
def _load() -> dict:
    try:
        d = json.loads(STATE_FILE.read_text(encoding="utf-8"))
        return d if isinstance(d, dict) else {}
    except (OSError, ValueError):
        return {}


def _save(d: dict) -> None:
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    tmp = STATE_FILE.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(d, ensure_ascii=False, indent=1), encoding="utf-8")
    tmp.replace(STATE_FILE)


def configure(state_file=None, ledger_file=None) -> None:
    """Point the module at other files (tests)."""
    global STATE_FILE, LEDGER_FILE, _db
    with _lock:
        if state_file is not None:
            STATE_FILE = Path(state_file)
        if ledger_file is not None:
            if _db is not None:
                _db.close()
            _db = None
            LEDGER_FILE = Path(ledger_file)
        _taken.clear()
        _published.clear()
        _cache.clear()
        _remote.update({"runner": "", "updated_at": 0.0, "ok_at": 0.0, "error": "", "vps": {}})
        _last_should["v"] = None


def wire(brains_fn: Callable[[], Iterable]) -> None:
    """`brains_fn()` returns the root folders of the brains whose schedules this machine runs."""
    global _brains_fn
    _brains_fn = brains_fn


def on_change(fn: Callable[[], None]) -> None:
    """Called when this machine starts or stops being the one that runs schedules (bots resync)."""
    _listeners.append(fn)


def _roots() -> List[Path]:
    out, seen = [], set()
    try:
        for r in _brains_fn() or []:
            p = Path(r)
            k = str(p.resolve()) if p.exists() else str(p)
            if k not in seen and p.is_dir():
                seen.add(k)
                out.append(p)
    except Exception as e:  # noqa: BLE001
        print(f"[may_chay_lich] brains: {type(e).__name__}: {e}", file=sys.stderr)
    return out


# ---------------------------------------------------------------- identity
def _kind() -> str:
    env = str(os.getenv("UNIMATE_MACHINE_KIND") or "").strip().lower()
    if env in KINDS:
        return env
    try:
        import deploy_info
        mode = deploy_info.deploy_mode()
    except Exception:  # noqa: BLE001
        mode = "windows" if os.name == "nt" else "native"
    if mode == "docker":
        return "vps"
    if mode == "windows" or sys.platform == "darwin":
        return "home"
    return "vps"


def _label(kind: str) -> str:
    if kind == "vps":
        dom = str(os.getenv("DOMAIN_NAME") or "").split()
        if dom:
            return dom[0][:80]
    try:
        return (socket.gethostname() or kind)[:80]
    except Exception:  # noqa: BLE001
        return kind


def machine() -> dict:
    """{"id", "kind", "label"} of this machine. The id is made once and kept."""
    with _lock:
        st = _load()
        if not st.get("id"):
            st["id"] = secrets.token_hex(8)
            st["created"] = time.time()
            _save(st)
        kind = _kind()
        return {"id": st["id"], "kind": kind, "label": _label(kind)}


def norm_pin(v) -> str:
    """"vps" | "home" | "" (follow the general setting)."""
    return PIN_ALIASES.get(str(v or "").strip().lower(), "")


# ---------------------------------------------------------------- synced files in the brains
def _read_json(p: Path) -> dict:
    try:
        d = json.loads(p.read_text(encoding="utf-8"))
        return d if isinstance(d, dict) else {}
    except (OSError, ValueError):
        return {}


def _write_json(p: Path, d: dict) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_name(p.name + ".tmp")
    tmp.write_text(json.dumps(d, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    tmp.replace(p)


def publish_self() -> int:
    """Write `UniMate/may/<id>.json` into every brain. Content changes once a day at most (the date),
    so the GitHub sync carries one small commit per machine per day. Returns files written."""
    me = machine()
    rec = {"id": me["id"], "kind": me["kind"], "label": me["label"], "seen": time.strftime("%Y-%m-%d")}
    n = 0
    for root in _roots():
        p = root.joinpath(*SYNC_MACHINES) / f"{me['id']}.json"
        key = str(p)
        if _published.get(key) == rec:
            continue
        if _read_json(p) != rec:
            try:
                _write_json(p, rec)
                n += 1
            except OSError as e:
                print(f"[may_chay_lich] {p}: {e}", file=sys.stderr)
                continue
        _published[key] = rec
    return n


def _seen_ok(rec: dict) -> bool:
    s = rec.get("seen")
    try:
        ts = float(s) if isinstance(s, (int, float)) else time.mktime(time.strptime(str(s)[:10], "%Y-%m-%d"))
    except (TypeError, ValueError):
        return False
    return time.time() - ts <= SEEN_DAYS * 86400


def _cached(name: str, fn):
    hit = _cache.get(name)
    if hit and time.time() - hit[0] < CACHE_S:
        return hit[1]
    v = fn()
    _cache[name] = (time.time(), v)
    return v


def _forget_cache() -> None:
    _cache.clear()


def peers() -> List[dict]:
    """Other machines heard of: from the brains and from the VPS registry (machines that linked here)."""
    return [dict(p) for p in _cached("peers", _peers_now)]


def _peers_now() -> List[dict]:
    me = machine()["id"]
    out = {}
    for root in _roots():
        d = root.joinpath(*SYNC_MACHINES)
        if not d.is_dir():
            continue
        for f in d.glob("*.json"):
            rec = _read_json(f)
            if rec.get("id") and rec.get("id") != me and rec.get("kind") in KINDS and _seen_ok(rec):
                out[rec["id"]] = {"id": rec["id"], "kind": rec["kind"], "label": str(rec.get("label") or "")[:80],
                                  "seen": rec.get("seen"), "via": "brain"}
    for pid, rec in (_load().get("peers") or {}).items():
        if pid != me and isinstance(rec, dict) and rec.get("kind") in KINDS and _seen_ok(rec):
            out[pid] = {"id": pid, "kind": rec["kind"], "label": str(rec.get("label") or "")[:80],
                        "seen": rec.get("seen"), "via": "link"}
    return sorted(out.values(), key=lambda r: (r["kind"], r["label"]))


def _synced_runner() -> dict:
    return dict(_cached("runner", _synced_runner_now))


def _synced_runner_now() -> dict:
    best = {}
    for root in _roots():
        rec = _read_json(root.joinpath(*SYNC_RUNNER))
        if norm_pin(rec.get("runner")) and float(rec.get("updated_at") or 0) > float(best.get("updated_at") or 0):
            best = {"runner": norm_pin(rec.get("runner")), "updated_at": float(rec.get("updated_at") or 0)}
    return best


# ---------------------------------------------------------------- link (home -> VPS)
def _link() -> dict:
    """{"url", "key"} when this machine is linked to a VPS, else {}."""
    ln = _load().get("link") or {}
    if not (isinstance(ln, dict) and ln.get("url") and ln.get("key")):
        return {}
    key = ln["key"]
    try:
        import secrets_store
        key = secrets_store.decrypt(key) if str(key).startswith("enc:") else key
    except Exception:  # noqa: BLE001
        pass
    return {"url": str(ln["url"]).rstrip("/"), "key": key} if key else {}


def linked() -> bool:
    return bool(_link())


def make_pair_code(base_url: str) -> str:
    """A code the owner pastes on the other machine: this machine's address and a fresh key. Only the
    key's hash stays here; the code itself is shown once and never stored."""
    base = str(base_url or "").strip().rstrip("/")
    if not base.startswith(("http://", "https://")):
        raise ValueError("base_url")
    secret = secrets.token_urlsafe(24)
    with _lock:
        st = _load()
        pair = [p for p in (st.get("pair") or []) if isinstance(p, dict) and p.get("h")]
        pair.append({"h": hashlib.sha256(secret.encode()).hexdigest(), "at": time.time()})
        st["pair"] = pair[-MAX_PAIR_CODES:]
        _save(st)
    raw = json.dumps({"u": base, "k": secret}, separators=(",", ":")).encode()
    return CODE_PREFIX + base64.urlsafe_b64encode(raw).decode().rstrip("=")


def parse_code(code: str) -> tuple:
    c = str(code or "").strip()
    if not c.startswith(CODE_PREFIX):
        raise ValueError("code")
    body = c[len(CODE_PREFIX):]
    try:
        d = json.loads(base64.urlsafe_b64decode(body + "=" * (-len(body) % 4)))
    except (ValueError, TypeError) as e:
        raise ValueError("code") from e
    url, key = str(d.get("u") or "").rstrip("/"), str(d.get("k") or "")
    if not url.startswith(("http://", "https://")) or len(key) < 16:
        raise ValueError("code")
    return url, key


def check_pair(secret: str) -> bool:
    """Is this the key of a link code this machine issued?"""
    if not secret:
        return False
    h = hashlib.sha256(str(secret).encode()).hexdigest()
    return any(hmac.compare_digest(h, str(p.get("h") or "")) for p in (_load().get("pair") or [])
               if isinstance(p, dict))


def revoke_pairs() -> int:
    with _lock:
        st = _load()
        n = len(st.get("pair") or [])
        st["pair"] = []
        _save(st)
    return n


async def _http(method: str, path: str, body: Optional[dict] = None, link: Optional[dict] = None) -> dict:
    import httpx
    ln = link or _link()
    if not ln:
        raise RuntimeError("not linked")
    async with httpx.AsyncClient(timeout=HTTP_TIMEOUT_S) as c:
        r = await c.request(method, ln["url"] + path, json=body, headers={HEADER: ln["key"]})
    if r.status_code != 200:
        raise RuntimeError(f"HTTP {r.status_code}")
    d = r.json()
    if not isinstance(d, dict):
        raise RuntimeError("bad answer")
    return d


async def link(code: str) -> dict:
    """Save a link code after one successful call to the VPS."""
    url, key = parse_code(code)
    ans = await _http("GET", "/may-chay-lich/remote/runner", link={"url": url, "key": key})
    if (ans.get("vps") or {}).get("id") == machine()["id"]:
        raise ValueError("self")
    stored = key
    try:
        import secrets_store
        stored = secrets_store.encrypt(key) or key
    except Exception:  # noqa: BLE001
        pass
    with _lock:
        st = _load()
        st["link"] = {"url": url, "key": stored, "at": time.time()}
        _save(st)
    _remember_remote(ans)
    await _register_remote()
    _check_change()
    return status()


def unlink() -> None:
    with _lock:
        st = _load()
        st.pop("link", None)
        _save(st)
    _remote.update({"runner": "", "updated_at": 0.0, "ok_at": 0.0, "error": "", "vps": {}})
    _check_change()


def _remember_remote(ans: dict) -> None:
    r = norm_pin(ans.get("runner"))
    if r:
        _remote.update({"runner": r, "updated_at": float(ans.get("updated_at") or 0), "ok_at": time.time(),
                        "error": "", "vps": ans.get("vps") or {}})


async def _register_remote() -> None:
    me = machine()
    try:
        await _http("POST", "/may-chay-lich/remote/register", {"id": me["id"], "kind": me["kind"], "label": me["label"]})
    except Exception as e:  # noqa: BLE001
        _remote["error"] = f"{type(e).__name__}: {e}"[:200]


# ---------------------------------------------------------------- who runs
def effective_runner() -> str:
    """"vps" | "home": the VPS answer when linked and fresh, else the newest choice in the brains or here."""
    me = machine()
    if linked() and me["kind"] != "vps" and _remote.get("runner") and time.time() - _remote["ok_at"] <= REMOTE_FRESH_S:
        return _remote["runner"]
    cands = [_synced_runner()]
    loc = _load().get("runner") or {}
    if norm_pin(loc.get("value")):
        cands.append({"runner": norm_pin(loc["value"]), "updated_at": float(loc.get("updated_at") or 0)})
    if _remote.get("runner"):
        cands.append({"runner": _remote["runner"], "updated_at": float(_remote.get("updated_at") or 0)})
    best = max((c for c in cands if c.get("runner")), key=lambda c: c["updated_at"], default=None)
    return best["runner"] if best else "vps"


def _other_known(kind: str) -> bool:
    if kind == "vps" and linked():
        return True
    return any(p["kind"] == kind for p in peers())


def should_run(pin="") -> bool:
    """May THIS machine run a schedule (or answer a customer) pinned to `pin` ("" = the general choice)?"""
    target = norm_pin(pin) or effective_runner()
    me = machine()["kind"]
    if target == me:
        return True
    return not _other_known(target)


def where(pin="") -> str:
    """"vps" | "home": which kind of machine a schedule with this pin runs on."""
    return norm_pin(pin) or effective_runner()


def set_runner(value: str, *, updated_at: Optional[float] = None) -> dict:
    """Record the choice here and in every brain (the brains carry it to machines that are not linked)."""
    v = norm_pin(value)
    if not v:
        raise ValueError("runner")
    ts = float(updated_at or time.time())
    with _lock:
        st = _load()
        st["runner"] = {"value": v, "updated_at": ts}
        _save(st)
    rec = {"runner": v, "updated_at": ts, "by": machine()["id"]}
    for root in _roots():
        try:
            _write_json(root.joinpath(*SYNC_RUNNER), rec)
        except OSError as e:
            print(f"[may_chay_lich] {root}: {e}", file=sys.stderr)
    if _remote.get("runner"):
        _remote.update({"runner": v, "updated_at": ts})
    _forget_cache()
    _check_change()
    return status()


async def set_runner_everywhere(value: str) -> dict:
    """The owner's choice from the Settings page. A linked home machine tells the VPS first (it decides)."""
    v = norm_pin(value)
    if not v:
        raise ValueError("runner")
    if linked() and machine()["kind"] != "vps":
        ans = await _http("POST", "/may-chay-lich/remote/runner", {"runner": v})
        _remember_remote(ans)
        return set_runner(v, updated_at=float(ans.get("updated_at") or time.time()))
    return set_runner(v)


def _check_change() -> None:
    try:
        now = should_run("")
    except Exception:  # noqa: BLE001
        return
    before, _last_should["v"] = _last_should["v"], now
    if before is not None and before != now:
        for fn in list(_listeners):
            try:
                fn()
            except Exception as e:  # noqa: BLE001
                print(f"[may_chay_lich] listener: {type(e).__name__}: {e}", file=sys.stderr)


# ---------------------------------------------------------------- ledger
def _conn() -> sqlite3.Connection:
    global _db
    if _db is None:
        LEDGER_FILE.parent.mkdir(parents=True, exist_ok=True)
        _db = sqlite3.connect(str(LEDGER_FILE), check_same_thread=False, timeout=10)
        _db.row_factory = sqlite3.Row
        _db.execute("CREATE TABLE IF NOT EXISTS claims (key TEXT PRIMARY KEY, machine TEXT NOT NULL, "
                    "label TEXT DEFAULT '', at REAL NOT NULL, pending INTEGER DEFAULT 0)")
        _db.commit()
    return _db


def local_claim(key: str, machine_id: str, label: str = "", pending: bool = False) -> tuple:
    """(ok, holder label). The first machine to claim a key holds it; the holder may claim it again."""
    now = time.time()
    with _lock:
        c = _conn()
        row = c.execute("SELECT machine, label FROM claims WHERE key=?", (key,)).fetchone()
        if row is not None:
            return row["machine"] == machine_id, row["label"] or ""
        c.execute("INSERT INTO claims(key, machine, label, at, pending) VALUES (?,?,?,?,?)",
                  (key, machine_id, str(label or "")[:80], now, 1 if pending else 0))
        c.execute("DELETE FROM claims WHERE at < ?", (now - KEEP_S,))
        c.commit()
    return True, str(label or "")


def _remember_taken(key: str) -> None:
    if len(_taken) > MAX_TAKEN_CACHE:
        _taken.clear()
    _taken.add(key)


async def claim(key: str, *, offline_ok: bool = True) -> bool:
    """True when this machine may go ahead with `key`. Linked home asks the VPS; the VPS (and a machine
    with no link) keeps the ledger itself. Unreachable VPS: go ahead only when `offline_ok`, and the
    claim is written here and sent to the VPS later."""
    key = str(key or "")[:400]
    if not key:
        return True
    if key in _taken:
        return False
    me = machine()
    if linked() and me["kind"] != "vps":
        try:
            ans = await _http("POST", "/may-chay-lich/remote/claim", {"key": key, "machine": me["id"], "label": me["label"]})
            ok = bool(ans.get("ok"))
            if ok:
                await asyncio.to_thread(local_claim, key, me["id"], me["label"])
        except Exception as e:  # noqa: BLE001
            _remote["error"] = f"{type(e).__name__}: {e}"[:200]
            if not offline_ok:
                return False
            ok, _ = await asyncio.to_thread(local_claim, key, me["id"], me["label"], True)
    else:
        ok, _ = await asyncio.to_thread(local_claim, key, me["id"], me["label"])
    if not ok:
        _remember_taken(key)
    return ok


def remote_claim(key: str, machine_id: str, label: str = "") -> dict:
    """VPS side of `claim`."""
    key = str(key or "")[:400]
    if not key or not machine_id:
        return {"ok": False, "error": "key"}
    ok, holder = local_claim(key, str(machine_id)[:40], label)
    return {"ok": ok, "holder": holder}


def remote_register(info: dict) -> dict:
    """VPS side: a linked machine says who it is."""
    pid = str((info or {}).get("id") or "")[:40]
    kind = norm_pin((info or {}).get("kind"))
    if not pid or not kind:
        return {"ok": False}
    with _lock:
        st = _load()
        ps = st.get("peers") if isinstance(st.get("peers"), dict) else {}
        ps[pid] = {"kind": kind, "label": str((info or {}).get("label") or "")[:80], "seen": time.time()}
        st["peers"] = ps
        _save(st)
    _forget_cache()
    _check_change()
    return {"ok": True}


def remote_runner() -> dict:
    loc = _load().get("runner") or {}
    syn = _synced_runner()
    ts = max(float(loc.get("updated_at") or 0), float(syn.get("updated_at") or 0))
    return {"runner": effective_runner(), "updated_at": ts, "vps": machine()}


def _pending() -> list:
    with _lock:
        return [dict(r) for r in _conn().execute("SELECT key, machine, label FROM claims WHERE pending=1 LIMIT 200")]


async def _flush_pending() -> int:
    n = 0
    for row in await asyncio.to_thread(_pending):
        try:
            ans = await _http("POST", "/may-chay-lich/remote/claim",
                              {"key": row["key"], "machine": row["machine"], "label": row["label"]})
        except Exception:  # noqa: BLE001
            break
        if not ans.get("ok"):
            print(f"[may_chay_lich] run done here while offline was also done by {ans.get('holder')}: {row['key']}",
                  file=sys.stderr)
        with _lock:
            _conn().execute("UPDATE claims SET pending=0 WHERE key=?", (row["key"],))
            _conn().commit()
        n += 1
    return n


# ---------------------------------------------------------------- the minute tick
async def tick() -> None:
    await asyncio.to_thread(publish_self)
    if linked() and machine()["kind"] != "vps":
        try:
            _remember_remote(await _http("GET", "/may-chay-lich/remote/runner"))
            await _register_remote()
            await _flush_pending()
        except Exception as e:  # noqa: BLE001
            _remote["error"] = f"{type(e).__name__}: {e}"[:200]
    _check_change()


async def run_forever() -> None:
    while True:
        try:
            await tick()
        except Exception as e:  # noqa: BLE001
            print(f"[may_chay_lich] {type(e).__name__}: {e}", file=sys.stderr)
        await asyncio.sleep(TICK_S)


def status() -> dict:
    """What the Settings card and the Tasks banner draw."""
    me = machine()
    ln = _link()
    runner = effective_runner()
    ps = peers()
    vps = next((p for p in ps if p["kind"] == "vps"), None)
    if me["kind"] == "vps":
        vps = me
    home = next((p for p in ps if p["kind"] == "home"), None) or (me if me["kind"] == "home" else None)
    try:
        pend = len(_pending())
    except Exception:  # noqa: BLE001
        pend = 0
    return {
        "machine": me, "runner": runner, "is_runner": should_run(""),
        "runner_label": ((vps or {}).get("label") if runner == "vps" else (home or {}).get("label")) or "",
        "linked": bool(ln), "link_url": ln.get("url", "") if ln else "",
        "link_ok": bool(ln) and bool(_remote.get("ok_at")) and time.time() - _remote["ok_at"] <= REMOTE_FRESH_S,
        "link_error": _remote.get("error", "") if ln else "",
        "last_ok": _remote.get("ok_at", 0.0),
        "peers": ps, "pair_codes": len(_load().get("pair") or []), "pending": pend,
    }
