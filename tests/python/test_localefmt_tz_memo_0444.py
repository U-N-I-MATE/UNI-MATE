"""0.444.0: localefmt.tz() memoizes the zone object by the settings.json signature (path, mtime_ns, size).

    python tests/run.py localefmt_tz_memo_0444      (NO network)

Owner, 2026-11-04, after the root of test_kanban_snapshot (0.443.0): `clock`/`at`/`now` call `tz()`, and `tz()` re-read
the settings every time (a read_settings cache hit still rebuilds the whole config from JSON). The checks here COUNT
reads instead of timing them, so they do not flake with machine speed.
"""
from _paths import ROOT, SERVER  # noqa: E402,F401
import os
import sys
import tempfile
from pathlib import Path

os.environ["UNIMATE_STATE_DIR"] = tempfile.mkdtemp(prefix="unimate-0444-")
try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

_fails = []


def check(name, cond, extra=""):
    print(("ok   " if cond else "FAIL ") + name + (("  [" + str(extra)[:300] + "]") if not cond else ""))
    if not cond:
        _fails.append(name)


import config as cfgmod  # noqa: E402
import localefmt as L  # noqa: E402

_real_read = cfgmod.read_settings
reads = {"n": 0}


def _counting_read():
    reads["n"] += 1
    return _real_read()


cfgmod.read_settings = _counting_read

cfgmod.update_settings({"locale": {"tz": "Asia/Tokyo"}})
reads["n"] = 0
ts = 1793700000
out = [L.clock(ts + i) for i in range(1000)] + [L.at(ts).isoformat() for _ in range(200)]
for _ in range(200):
    L.now()
    L.tz()
check(f"1,600 clock/at/now/tz calls read the settings {reads['n']} time(s) (must be 1)", reads["n"] == 1, reads["n"])
check("zone matches the config (Asia/Tokyo, UTC+9)", L.at(ts).utcoffset().total_seconds() == 9 * 3600, L.at(ts))
check("output is identical to the unmemoized computation",
      out[0] == __import__("datetime").datetime.fromtimestamp(ts, L._tu_ten("Asia/Tokyo")).strftime("%Y-%m-%d %H:%M"))

# Writing the settings -> takes effect on the next call (signature changed), and is re-read exactly once.
cfgmod.update_settings({"locale": {"tz": "Europe/Paris"}})
reads["n"] = 0
z = [L.tz() for _ in range(300)][-1]
check("zone changed in settings: the next call already uses the new zone", str(z) == "Europe/Paris", z)
check(f"after the change, 300 calls re-read {reads['n']} time(s) (must be 1)", reads["n"] == 1, reads["n"])

# The settings file moves (tests, another machine's state folder) -> a different signature, the old zone is not reused.
old_path = cfgmod.SETTINGS_PATH
new_path = Path(tempfile.mkdtemp(prefix="unimate-0444-b-")) / "settings.json"
cfgmod.SETTINGS_PATH = new_path
try:
    cfgmod._SETTINGS_CACHE["sig"] = None
    cfgmod.update_settings({"locale": {"tz": "America/New_York"}})
    check("settings file elsewhere: that file is followed", str(L.tz()) == "America/New_York", L.tz())
finally:
    cfgmod.SETTINGS_PATH = old_path
    cfgmod._SETTINGS_CACHE["sig"] = None
check("back to the old file: the old file's zone again", str(L.tz()) == "Europe/Paris", L.tz())

# A transient read failure (Windows file lock): return the default but do NOT memoize it, or it would stick until
# the next write.
L._CACHE.pop(L._MEMO_KEY, None)


def _broken():
    raise cfgmod.SettingsUnreadable("transient lock")


cfgmod.read_settings = _broken
z = L.tz()
check("read failure: default zone, no exception", z is L._tu_ten(L.TEN_TZ_MAC_DINH), z)
cfgmod.read_settings = _counting_read
check("read failure is not memoized: the next good read gives the real zone", str(L.tz()) == "Europe/Paris", L.tz())

# A read from the .bak copy: not memoized, just like read_settings.
L._CACHE.pop(L._MEMO_KEY, None)


def _from_bak():
    c = _real_read()
    cfgmod._DOC_TU_BAK[0] = True
    return c


cfgmod.read_settings = _from_bak
L.tz()
check("read from .bak: not memoized", L._MEMO_KEY not in L._CACHE)
cfgmod._DOC_TU_BAK[0] = False
cfgmod.read_settings = _counting_read
L.tz()
check("real file read again: memoized as usual", L._MEMO_KEY in L._CACHE)

# The way older tests signal "config just changed" without writing to disk (patch read_settings, then
# _CACHE.clear()) still works.
_orig = cfgmod.read_settings


def _fake():
    c = _orig()
    c.setdefault("locale", {})["tz"] = "Asia/Seoul"
    return c


cfgmod.read_settings = _fake
L._CACHE.clear()
check("patched read_settings + _CACHE.clear(): the fake config applies at once", str(L.tz()) == "Asia/Seoul", L.tz())
cfgmod.read_settings = _orig
L._CACHE.clear()
check("patch removed + _CACHE.clear(): back to the real zone", str(L.tz()) == "Europe/Paris", L.tz())

# No settings file yet (new machine): no signature to memoize by, still the default zone.
cfgmod.SETTINGS_PATH = Path(tempfile.mkdtemp(prefix="unimate-0444-c-")) / "settings.json"
try:
    check("no settings file yet: default zone Asia/Ho_Chi_Minh", str(L.tz()) == L.TEN_TZ_MAC_DINH, L.tz())
finally:
    cfgmod.SETTINGS_PATH = old_path
cfgmod.read_settings = _real_read

print()
if _fails:
    print(f"FAIL {len(_fails)}: {_fails}")
    sys.exit(1)
print("OK - test_localefmt_tz_memo_0444: all pass")
