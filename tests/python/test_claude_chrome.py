"""Claude in Chrome for the owner's web chat (0.430.3, server/claude_chrome.py).

    python tests/run.py claude_chrome

No Claude CLI or login needed: the CLI lookups are stubbed. Checks every gate of `--chrome`, that the flag
reaches the SDK options of a web chat turn (merged with the system prompt file), that background runs never
get it, and that claude_sdk_engine.py itself stays untouched (it is pinned by the native qualification).
"""
from _paths import ROOT, SERVER  # noqa: E402,F401
import copy
import json
import os
import sys
import tempfile

os.environ.setdefault("UNIMATE_STATE_DIR", tempfile.mkdtemp(prefix="unimate-chrometest-"))
os.environ.pop("UNIMATE_CLAUDE_CHROME", None)
os.environ.pop("ANTHROPIC_API_KEY", None)

_fails = []


def check(name, cond):
    print(("ok  " if cond else "FAIL ") + name)
    if not cond:
        _fails.append(name)


import claude_cli  # noqa: E402
import claude_chrome  # noqa: E402
from claude_sdk_engine import ClaudeSDK  # noqa: E402

_on = tempfile.mkdtemp(prefix="chrome-on-")
with open(os.path.join(_on, ".claude.json"), "w", encoding="utf-8") as f:
    json.dump({"claudeInChromeDefaultEnabled": True}, f)
_off = tempfile.mkdtemp(prefix="chrome-off-")
with open(os.path.join(_off, ".claude.json"), "w", encoding="utf-8") as f:
    json.dump({"claudeInChromeDefaultEnabled": False}, f)

claude_cli.co_co = lambda flag: True
claude_cli.find_claude_cli = lambda: "/bin/claude"


class _Opts:
    def __init__(self, cli="/bin/claude", env=None):
        self.cli_path, self.env, self.extra_args = cli, env if env is not None else {"CLAUDE_CONFIG_DIR": _on}, {}


def _eng(tag="chat:abc:01", **kw):
    return ClaudeSDK(system_prompt="x", tag=tag, **kw)


W = claude_chrome.wanted
check("setting file: on / off / missing", claude_chrome.default_enabled(_on)
      and not claude_chrome.default_enabled(_off) and not claude_chrome.default_enabled(tempfile.mkdtemp()))
check("owner web chat with the setting on -> on", W(_eng(), _Opts()))
check("loop, reminder, Telegram or bot tag -> off",
      not any(W(_eng(t), _Opts()) for t in ("loop:x", "reminder:1", "telegram:1", "bot:shop", "chat")))
check("whitelisted safe run -> off", not W(_eng(allowed_tools=["Read"]), _Opts()))
_trial = _eng()
_trial.trial_profile = object()
check("improvement trial -> off", not W(_trial, _Opts()))
check("API key login -> off", not W(_eng(), _Opts(env={"CLAUDE_CONFIG_DIR": _on, "ANTHROPIC_API_KEY": "k"})))
check("bundled or another binary -> off", not W(_eng(), _Opts(cli="/x/_bundled/claude")) and not W(_eng(), _Opts(cli=None)))
claude_cli.co_co = lambda flag: False
check("CLI without --chrome -> off", not W(_eng(), _Opts()))
claude_cli.co_co = lambda flag: True
check("setting off -> off", not W(_eng(), _Opts(env={"CLAUDE_CONFIG_DIR": _off})))
_acct = _eng()
_acct.claude_config_dir = _off
check("second plan account reads its own .claude.json", not W(_acct, _Opts()))
os.environ["UNIMATE_CLAUDE_CHROME"] = "0"
check("UNIMATE_CLAUDE_CHROME=0 -> off", not W(_eng(), _Opts()))
os.environ["UNIMATE_CLAUDE_CHROME"] = "1"
check("UNIMATE_CLAUDE_CHROME=1 skips only the setting", W(_eng(), _Opts(env={"CLAUDE_CONFIG_DIR": _off}))
      and not W(_eng("loop:x"), _Opts()) and not W(_eng(), _Opts(env={"ANTHROPIC_API_KEY": "k"})))
os.environ.pop("UNIMATE_CLAUDE_CHROME", None)

# Wired into real SDK options through the factory, merged with the system prompt file.
_saved = claude_chrome.wanted
claude_chrome.wanted = lambda engine, opts: str(engine.tag).startswith("chat:")
check("install is idempotent", claude_chrome.install() and claude_chrome.install()
      and getattr(ClaudeSDK._options, "_unimate_chrome", False)
      and not getattr(getattr(ClaudeSDK._options, "__wrapped__", None), "_unimate_chrome", False))
_big = "Bạn là UNI MATE.\n" + ("- một dòng hướng dẫn dài. " * 2000)
_chat = claude_cli.claude_engine(system_prompt=_big, tag="chat:abc:02")
_ea = getattr(_chat._options(), "extra_args", None) or {}
check("web chat options carry --chrome", "chrome" in _ea and _ea["chrome"] is None)
check("flag merges with the system prompt file", "append-system-prompt-file" in _ea)
_ea_copy = getattr(copy.copy(_chat)._options(), "extra_args", None) or {}
check("an engine copy (background work) keeps the flag", "chrome" in _ea_copy)
_chat._cleanup_tmp()
_loop = claude_cli.claude_engine(system_prompt="x", tag="loop:y")
check("a background run never gets the flag", "chrome" not in (getattr(_loop._options(), "extra_args", None) or {}))
claude_chrome.wanted = _saved

# 0.431.0: device ids (chat pin, schedule-only Chrome).
CHAT_ID, JOB_ID = "9b3b586d-991d-46b6-bc1b-478e46e9e148", "43cb6235-2c88-4488-b247-8b3caf39cffe"
check("clean_device keeps an id, drops junk",
      claude_chrome.clean_device(f"  {CHAT_ID} ") == CHAT_ID and claude_chrome.clean_device("a`b; rm -rf") == ""
      and claude_chrome.clean_device("") == "" and claude_chrome.clean_device(None) == "")
_st = {"model": {"claude_chrome": {"chat_device": CHAT_ID, "job_device": "bad id!"}}}
check("devices reads settings, junk becomes empty",
      claude_chrome.devices(_st) == {"chat_device": CHAT_ID, "job_device": ""})
os.environ[claude_chrome.ENV_JOB_DEVICE] = JOB_ID
check("env wins over settings", claude_chrome.devices(_st)["job_device"] == JOB_ID
      and claude_chrome.devices({})["chat_device"] == "")
os.environ.pop(claude_chrome.ENV_JOB_DEVICE, None)
check("pin text names the device; job variant forbids the owner's PC",
      CHAT_ID in claude_chrome.pin_text(CHAT_ID) and "select_browser" in claude_chrome.pin_text(CHAT_ID)
      and "máy cá nhân" in claude_chrome.pin_text(JOB_ID, job=True)
      and "máy cá nhân" not in claude_chrome.pin_text(CHAT_ID))


class _P:
    def __init__(self, sp=None, path=None):
        self.system_prompt, self.extra_args = sp, ({"append-system-prompt-file": path} if path else {})


_fd, _fp = tempfile.mkstemp()
os.close(_fd)
with open(_fp, "w", encoding="utf-8") as f:
    f.write("base")
_a, _b, _c = _P(path=_fp), _P(sp="s"), _P(sp={"type": "preset", "append": "p"})
check("_append_prompt: file, str and preset dict",
      claude_chrome._append_prompt(_a, "+X") and open(_fp, encoding="utf-8").read() == "base+X"
      and claude_chrome._append_prompt(_b, "+X") and _b.system_prompt == "s+X"
      and claude_chrome._append_prompt(_c, "+X") and _c.system_prompt["append"] == "p+X"
      and not claude_chrome._append_prompt(_P(), "+X"))
os.remove(_fp)


def _job(**kw):
    e = _eng("reminder:r1", **kw)
    e.chrome_job = True
    return e


check("reminder with Chrome on but no job device -> off", not W(_job(), _Opts(env={"CLAUDE_CONFIG_DIR": _off})))
os.environ[claude_chrome.ENV_JOB_DEVICE] = JOB_ID
check("reminder with Chrome on + job device -> on, even with the PC setting off",
      W(_job(), _Opts(env={"CLAUDE_CONFIG_DIR": _off})))
check("reminder without its switch -> off", not W(_eng("reminder:r1"), _Opts()))
check("chrome_job on a non-reminder tag does nothing", not W(_eng("loop:x"), _Opts()) and not (
    lambda e: (setattr(e, "chrome_job", True), W(e, _Opts()))[1])(_eng("telegram:1")))
check("reminder at a lighter level -> off", not W(_job(allowed_tools=["Read"]), _Opts()))
check("reminder on an API key -> off", not W(_job(), _Opts(env={"ANTHROPIC_API_KEY": "k"})))
os.environ["UNIMATE_CLAUDE_CHROME"] = "0"
check("UNIMATE_CLAUDE_CHROME=0 turns schedules off too", not W(_job(), _Opts()))
os.environ.pop("UNIMATE_CLAUDE_CHROME", None)

# The pin lands in the real system prompt file of a run, the right device for each kind of run.
# The CLI gates are covered above; here only the pin, so it holds on CI without a claude binary.
_saved = claude_chrome.wanted
claude_chrome.wanted = lambda engine, opts: str(engine.tag).startswith("chat:") or claude_chrome._is_job(engine)
os.environ[claude_chrome.ENV_CHAT_DEVICE] = CHAT_ID
_ch = claude_cli.claude_engine(system_prompt="hello", tag="chat:abc:03")
_o = _ch._options()
_txt = open(_o.extra_args["append-system-prompt-file"], encoding="utf-8").read()
check("chat run is pinned to the chat device", "chrome" in _o.extra_args and CHAT_ID in _txt and JOB_ID not in _txt)
_ch._cleanup_tmp()
_jb = claude_cli.claude_engine(system_prompt="hello", tag="reminder:r2")
_jb.chrome_job = True
_o = _jb._options()
_txt = open(_o.extra_args["append-system-prompt-file"], encoding="utf-8").read()
check("schedule run is pinned to the job device only", "chrome" in _o.extra_args and JOB_ID in _txt and CHAT_ID not in _txt)
_jb._cleanup_tmp()
claude_chrome.wanted = _saved
os.environ.pop(claude_chrome.ENV_JOB_DEVICE, None)
_ch = claude_cli.claude_engine(system_prompt="hello", tag="chat:abc:04")
_ch._options()
_jb = claude_cli.claude_engine(system_prompt="hello", tag="reminder:r3")
_jb.chrome_job = True
check("no job device: schedule gets no Chrome", "chrome" not in (getattr(_jb._options(), "extra_args", None) or {}))
os.environ.pop(claude_chrome.ENV_CHAT_DEVICE, None)
_ch._cleanup_tmp()
_jb._cleanup_tmp()

# The pinned engine file must not be edited for this feature.
_src = (ROOT / "server" / "claude_sdk_engine.py").read_text(encoding="utf-8")
check("claude_sdk_engine.py has no chrome code (pinned file)", "chrome" not in _src.lower())

if _fails:
    print(f"\nFAIL - {len(_fails)} test: {_fails}")
    sys.exit(1)
print("\nOK - test_claude_chrome: all pass")
