"""0.437.0: Claude Code gets the same system prompt for every new chat, so it is read from the prompt cache.

Measured 03/11/2026: two new chats built one minute apart differed only in the clock line and three lines with the
session id (plus the usage-today block on a day with usage). One changed character means Claude Code writes the
whole ~43,000-character prompt to the cache again on every new chat. These checks pin the fix.
"""
import os
import sys
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SERVER = ROOT / "server"
sys.path.insert(0, str(SERVER))
os.environ.setdefault("UNIMATE_STATE_DIR", tempfile.mkdtemp(prefix="unimate-pc0437-"))

import channel_context  # noqa: E402
import cli_prompt_cache as PC  # noqa: E402
import context_compiler  # noqa: E402
import main  # noqa: E402

_fails = []


def check(name, cond, info=""):
    print(("ok   " if cond else "FAIL ") + name + ("" if cond else f"  -> {str(info)[:300]}"))
    if not cond:
        _fails.append(name)


brain = tempfile.mkdtemp(prefix="unimate-pc0437-brain-")
SID_A, SID_B = "a" * 32, "b" * 32


def full(sid, minute, usage):
    when = datetime(2026, 11, 3, 18, minute, tzinfo=timezone(timedelta(hours=7)))
    orig_clock, orig_summary = context_compiler._bay_gio, main.usage_store.summary
    context_compiler._bay_gio = lambda: when
    main.usage_store.summary = lambda: {"today": {"total": usage}}
    try:
        return main.build_system_prompt(brain, session_id=sid) + channel_context.build_channel_block(
            "dashboard", {"session_id": sid}, telegram_running=False, port=8688, brain_root=main._brain_root(brain))
    finally:
        context_compiler._bay_gio, main.usage_store.summary = orig_clock, orig_summary


a = full(SID_A, 26, {"in": 1200, "out": 300, "turns": 2})
b = full(SID_B, 27, {"in": 99000, "out": 4100, "turns": 9})
check("CANARY: the raw prompts of two chats differ (clock, session id, usage)", a != b)
check("CANARY: the raw prompt carries the session id and the usage numbers", SID_A in a and "1,200" in a)

sa, sb = PC.stable_prompt(a, SID_A), PC.stable_prompt(b, SID_B)
check("the stable prompts of two new chats are identical", sa == sb,
      [x for x in zip(sa.splitlines(), sb.splitlines()) if x[0] != x[1]][:3])
check("no session id is left in it", SID_A not in sa and SID_B not in sb)
check("no clock value is left in it", "18:26" not in sa and "18:27" not in sb)
check("no usage number is left in it", "1,200" not in sa and "99,000" not in sb)
check("the rules stay: the clock header now points at the message line", "# === BÂY GIỜ ===" in sa and PC.CLOCK_NOTE in sa)
check("the channel contract still tells where the session id goes", "web:" + PC.SESSION_REF in sa)
check("only the values moved: the stable prompt is about as long as the raw one", abs(len(sa) - len(a)) < 600,
      (len(a), len(sa)))
check("idempotent: stabilising twice changes nothing", PC.stable_prompt(sa, SID_A) == sa)
check("an empty prompt passes through", PC.stable_prompt("", SID_A) == "")
check("no em dash in what the model reads", "—" not in PC.CLOCK_NOTE + PC.USAGE_NOTE + PC.SESSION_REF)

line = PC.session_line(SID_A, {"in": 1200, "out": 300, "turns": 2})
check("the first message carries the session id", SID_A in line and line.startswith("[Phiên chat:"), line)
check("and today's usage", "1,200" in line and "300" in line, line)
check("no usage today: the line has the id only", "token" not in PC.session_line(SID_A, {}), PC.session_line(SID_A, {}))
check("no id and no usage: no line at all", PC.session_line("", {}) == "")

SRC = (SERVER / "main.py").read_text(encoding="utf-8")
check("the dashboard Claude Code branch stabilises its prompt",
      'sysprompt = cli_prompt_cache.stable_prompt(sysprompt, conv_sid or "")' in SRC)
check("the Telegram Claude Code branch too",
      'cli.system_prompt = cli_prompt_cache.stable_prompt(sysprompt, conv_sid or "")' in SRC)
check("both branches pass the session id to the message header",
      SRC.count('session_id=conv_sid or "")') >= 2)

print()
if _fails:
    print(f"FAIL {len(_fails)}: {_fails}")
    sys.exit(1)
print("OK - test_prompt_cache_0437: all pass")
