"""0.442.0: the Graph page does not list an external folder that is the same as a connected brain.

    python tests/run.py graph_external_folder_0442      (NO network)

Owner saw it 2026-11-04: the brain menu showed "Bonao_AI · 1136" (the brain) plus an "External folder" group holding
Bonao_AI again. On his PC `brains/Bonao_AI` is a LINK to `D:/9. AI/01. BRAIN PROJECT/Bonao_AI`, and the external folder
points straight there, so the dashboard compared two path strings that never matched. The server now also returns the
real path (`real`, links followed) from GET /brains and GET /path/exists so the dashboard compares the actual folder.
The dashboard side (dedupe, Remove button, group label) is in tests/js/test_brains_ui.mjs.
"""
from _paths import ROOT, SERVER  # noqa: E402,F401
import os
import sys
import tempfile
from pathlib import Path

_STATE = tempfile.mkdtemp(prefix="unimate-0442-")
os.environ["UNIMATE_STATE_DIR"] = _STATE
os.environ["BRAINS_DIR"] = str(Path(_STATE) / "brains")
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


import main  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

cl = TestClient(main.app)
brains = Path(os.environ["BRAINS_DIR"])
brains.mkdir(parents=True, exist_ok=True)
real_dir = Path(tempfile.mkdtemp(prefix="unimate-0442-vault-")) / "Bonao_AI"
real_dir.mkdir()
(real_dir / "note.md").write_text("# x\n", encoding="utf-8")
(brains / "Bonao_AI").symlink_to(real_dir, target_is_directory=True)
(brains / "Private").mkdir()

ds = {b["name"]: b for b in cl.get("/brains").json()["brains"]}
check("GET /brains: a brain that is a link is still listed", "Bonao_AI" in ds, list(ds))
b = ds.get("Bonao_AI") or {}
check("GET /brains: `path` keeps the address inside the brains folder (unchanged)", b.get("path") == str(brains / "Bonao_AI"), b)
check("GET /brains: `real` is the real folder behind the link", b.get("real") == str(real_dir.resolve()), b)
check("GET /brains: a plain brain has `real`", (ds.get("Private") or {}).get("real") == str((brains / "Private").resolve()))

r = cl.get("/path/exists", params={"path": str(real_dir)}).json()
check("GET /path/exists: the real folder returns a `real` equal to the brain's `real`",
      r.get("is_dir") is True and r.get("real") == b.get("real"), r)
r = cl.get("/path/exists", params={"path": str(brains / "Bonao_AI")}).json()
check("GET /path/exists: going through the link gives the same `real`", r.get("real") == b.get("real"), r)
r = cl.get("/path/exists", params={"path": str(real_dir / "missing")}).json()
check("GET /path/exists: a missing folder returns no `real`, the old answer is unchanged",
      r.get("exists") is False and r.get("is_dir") is False and "real" not in r, r)

# Chats store the REAL path (_brain_key follows links); the dashboard must get back the picker's own value, otherwise
# opening a chat of the selected brain still shows "This chat belongs to brain Bonao_AI... [Switch]".
key = main._brain_key(str(brains / "Bonao_AI"))
check("a chat of a linked brain stores the real path", key == str(real_dir.resolve()), key)
main._BRAINS_DIR_MAP["at"] = 0
check("brain_ui of a chat = the picker value (brains folder), not the real path",
      main._brain_ui_value(key) == "path:" + str(brains / "Bonao_AI"), main._brain_ui_value(key))
check("brain_ui: a plain brain is unchanged",
      main._brain_ui_value(str((brains / "Private").resolve())) == "path:" + str(brains / "Private"))
other = tempfile.mkdtemp(prefix="unimate-0442-outside-")
check("brain_ui: an external folder (not in brains) keeps its path", main._brain_ui_value(other) == "path:" + other)
check("brain_ui: the default Brain is still 'brain'", main._brain_ui_value(main._brain_key("brain")) == "brain")
sid = main.get_store().create_session(brain=key, title="x", channel="agent:eco-agent")
r = cl.get(f"/sessions/{sid}").json()
check("GET /sessions/<id>: brain_ui matches the brain picker", r.get("brain_ui") == "path:" + str(brains / "Bonao_AI"),
      r.get("brain_ui"))

print()
if _fails:
    print(f"FAIL {len(_fails)}: {_fails}")
    sys.exit(1)
print("OK - test_graph_external_folder_0442: all pass")
