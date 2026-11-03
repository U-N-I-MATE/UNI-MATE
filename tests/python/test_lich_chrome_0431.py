"""A schedule may drive the server's own Chrome only when its owner switches it on (0.431.0).

Owner, 03/11/2026: two browsers are connected to Claude in Chrome, the owner's PC and a Chromium on the VPS. Expected:
  - every reminder has a "Dùng Chrome" switch, off by default, kept only for a task run (not notify/script);
  - a chatbot-made reminder (bot_id) never gets it, on create or on a later edit;
  - the view says why a switched-on reminder will still run without a browser (lighter level, no job device);
  - the reminder run marks its engine (chrome_job) only at the full level, so claude_chrome pins it to the job device;
  - unimate_schedule forwards the switch on create and update, never for a notify-only reminder or a loop.

Run:
    python tests/python/test_lich_chrome_0431.py
"""
from _paths import ROOT, SERVER  # noqa: E402,F401
import asyncio
import importlib.util
import os
import sys
import tempfile
from pathlib import Path
from types import SimpleNamespace

os.environ.setdefault("UNIMATE_STATE_DIR", tempfile.mkdtemp(prefix="unimate-lichchrome-"))
for _k in ("UNIMATE_CHROME_JOB_DEVICE", "UNIMATE_CHROME_CHAT_DEVICE"):
    os.environ.pop(_k, None)

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

import claude_chrome  # noqa: E402
import reminders as R  # noqa: E402

fails = []
JOB_ID = "43cb6235-2c88-4488-b247-8b3caf39cffe"


def check(name, cond, info=""):
    print(("ok   " if cond else "FAIL ") + name + ("" if cond or not info else f"  [{info}]"))
    if not cond:
        fails.append(name)


vault = Path(tempfile.mkdtemp(prefix="unimate-lichchrome-v-"))
store = {"reminders": []}
rf = R.RemindersFeature.__new__(R.RemindersFeature)
rf.deps = SimpleNamespace(brain_root=lambda b: str(vault))
rf._dang_chay = set()
rf._load = lambda brain: store
rf._save = lambda brain, data: None
rf._register = lambda brain: None
rf.notify_status = lambda: (True, "")

# ---- create ----
plain = rf._create("b", "Đọc tin", delay_min=5, mode="task")
on = rf._create("b", "Quét nhóm", delay_min=5, mode="task", chrome=True)
notify = rf._create("b", "Nhắc", delay_min=5, mode="notify", chrome=True)
bot = rf._create("b", "Việc bot", delay_min=5, mode="task", chrome=True, bot_id="bot_vu")
check("off by default", plain["chrome"] is False and rf._view(plain)["chrome"] is False)
check("a task reminder keeps the switch", on["chrome"] is True and rf._view(on)["chrome"] is True)
check("a notify-only reminder never gets it", notify["chrome"] is False)
check("a chatbot-made reminder never gets it", bot["chrome"] is False)

# ---- why it may still run without a browser ----
os.environ.pop(claude_chrome.ENV_JOB_DEVICE, None)
check("no job device: the view says so", "Claude Code" in rf._view(on)["chrome_note"], rf._view(on)["chrome_note"])
os.environ[claude_chrome.ENV_JOB_DEVICE] = JOB_ID
check("job device set: no note", rf._view(on)["chrome_note"] == "")
check("switch off: no note", rf._view(plain)["chrome_note"] == "")
check("a lighter level: the view says Chrome needs full", R.chrome_note(dict(on, muc_quyen="auto")) != "")

# ---- update ----
r = rf.update("b", plain["id"], chrome="true")
check("the switch can be turned on later", r["ok"] and r["reminder"]["chrome"] is True)
r = rf.update("b", plain["id"], chrome="false")
check("and off again", r["ok"] and r["reminder"]["chrome"] is False)
rf.update("b", plain["id"], chrome="true")
r = rf.update("b", plain["id"], mode="notify")
check("switching to notify drops it", r["ok"] and r["reminder"]["chrome"] is False)
r = rf.update("b", bot["id"], chrome="true")
check("a chatbot's reminder cannot be switched on", r["ok"] and r["reminder"]["chrome"] is False)
r = rf.update("b", on["id"], label="Quét nhóm FB")
check("an unrelated edit keeps it", r["ok"] and r["reminder"]["chrome"] is True)


# ---- the run marks its engine only at the full level ----
class _CLI:
    def __init__(self, **kw):
        self.kw, self.max_wall_s, self.mcp_config, self.mcp_strict, self.disallowed_tools = kw, None, None, False, None

    def is_available(self):
        return True

    async def query(self, prompt):
        yield {"type": "final", "content": "xong"}


class _Deps:
    safe_tools = ["Read", "Write", "Edit"]
    readonly_tools = ["Read", "Glob", "Grep"]
    mcp_allow_patterns = staticmethod(lambda: ["mcp__unimate__*"])
    aux_swap = None
    aux_model = staticmethod(lambda: None)
    brain_root = staticmethod(lambda brain: str(vault))
    build_system_prompt = staticmethod(lambda brain: "sysprompt")
    apply_mcp = staticmethod(lambda cli, mode="full", brain=None: None)


def run(level, chrome):
    made = []

    def fake_engine(**kw):
        made.append(_CLI(**kw))
        return made[-1]

    keep = R.claude_engine
    R.claude_engine = fake_engine
    tok = R._RUN_CHROME.set(chrome)
    try:
        feat = R.RemindersFeature.__new__(R.RemindersFeature)
        feat.deps = _Deps()
        asyncio.run(feat._run_task("brain", "quét nhóm", level))
    finally:
        R._RUN_CHROME.reset(tok)
        R.claude_engine = keep
    return made[-1] if made else None


e = run("full", True)
check("switch on + full: the engine is marked for the job Chrome", e is not None and getattr(e, "chrome_job", False) is True)
e = run("full", False)
check("switch off: the engine is not marked", e is not None and not getattr(e, "chrome_job", False))
e = run("auto", True)
check("switch on + lighter level: not marked", e is not None and not getattr(e, "chrome_job", False))
check("outside a reminder run nothing is marked", R._RUN_CHROME.get() is False)

# ---- unimate_schedule ----
_spec = importlib.util.spec_from_file_location("plugin_unimate_schedule",
                                               ROOT / "system" / "plugins" / "unimate-schedule" / "plugin.py")
sched = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(sched)
sent, upd = {}, {}


async def fake_post(payload, brain_name=""):
    sent.clear()
    sent.update(payload)
    return "ok"


async def fake_update(vault_root, rid, fields):
    upd.clear()
    upd.update(fields)
    return "ok"


sched._post_reminder = fake_post
sched._update_reminder = fake_update
asyncio.run(sched._do_create(str(vault), {"name": "Quét", "prompt": "Quét nhóm", "schedule": "0 7 * * *", "chrome": True}))
check("create forwards the switch", sent.get("chrome") is True and sent.get("mode") == "task", sent)
asyncio.run(sched._do_create(str(vault), {"name": "Nhắc", "prompt": "Nhắc", "schedule": "0 7 * * *", "chrome": True,
                                          "notify_only": True}))
check("a notify-only reminder does not send it", "chrome" not in sent, sent)
asyncio.run(sched._do_create(str(vault), {"name": "Quét 2", "prompt": "Quét", "schedule": "0 7 * * *"}))
check("left out = not sent (server default off)", "chrome" not in sent, sent)
out = asyncio.run(sched._do_update(str(vault), {"id": "r_abc", "chrome": False}))
check("update with only the switch is accepted", out == "ok" and upd.get("chrome") == "false", (out, upd))
loops = sched._loops_dir(str(vault))
loops.mkdir(parents=True, exist_ok=True)
(loops / "quet.md").write_text("---\nname: q\n---\nx\n", encoding="utf-8")
out = asyncio.run(sched._do_update(str(vault), {"id": "quet", "chrome": True}))
check("a loop refuses it with a clear error", out.startswith("ERROR") and "Chrome" in out, out)

os.environ.pop(claude_chrome.ENV_JOB_DEVICE, None)
if fails:
    print(f"\nFAIL - {len(fails)}: {fails}")
    sys.exit(1)
print("\nOK - test_lich_chrome_0431: all pass")
