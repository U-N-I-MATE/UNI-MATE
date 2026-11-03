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

# The pinned engine file must not be edited for this feature.
_src = (ROOT / "server" / "claude_sdk_engine.py").read_text(encoding="utf-8")
check("claude_sdk_engine.py has no chrome code (pinned file)", "chrome" not in _src.lower())

if _fails:
    print(f"\nFAIL - {len(_fails)} test: {_fails}")
    sys.exit(1)
print("\nOK - test_claude_chrome: all pass")
