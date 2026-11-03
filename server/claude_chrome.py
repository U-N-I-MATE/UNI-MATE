"""Claude in Chrome for the owner's dashboard chat (0.430.3).

UNI MATE runs Claude Code headless through claude-agent-sdk, and headless Claude Code ignores the user's own
`/chrome -> Enabled by default` switch, so the browser tools never loaded in a UNI MATE chat even with the
extension installed and connected. The fix is the real `--chrome` flag, passed only when that switch is on.

claude_sdk_engine.py is pinned by the native qualification evidence (see plan_limits.cai_vao_claude_sdk), so this
wraps `ClaudeSDK._options` at class level instead of editing it. Class level, not per instance: plan_accounts wraps
the class method per instance for a second account, and background work copies engines with copy.copy, so both
keep this flag without any extra wiring.

Gates, all required:
- the owner's web chat only (tag "chat:"); never a loop, reminder, team step, Telegram or customer bot, a
  whitelisted safe run, or an improvement trial. The extension acts in the owner's real, signed-in Chrome.
- a subscription login: Claude Code turns Chrome off on an API key.
- the machine's own `claude` binary, and that binary knows `--chrome` (an unknown flag kills the whole turn).
- the user's switch `claudeInChromeDefaultEnabled` in `.claude.json` (in CLAUDE_CONFIG_DIR when set, else home).
UNIMATE_CLAUDE_CHROME=0 turns it off; =1 skips only the last gate.
"""
from __future__ import annotations

import json
import os
from pathlib import Path

ENV = "UNIMATE_CLAUDE_CHROME"
_OFF = ("0", "false", "off", "no")
_ON = ("1", "true", "on", "yes")


def default_enabled(config_dir: str | None = None) -> bool:
    """The user's own Claude Code switch `claudeInChromeDefaultEnabled`. Missing or unreadable file = off."""
    try:
        d = (config_dir or os.environ.get("CLAUDE_CONFIG_DIR") or "").strip()
        p = (Path(d) if d else Path.home()) / ".claude.json"
        with open(p, encoding="utf-8") as f:
            return json.load(f).get("claudeInChromeDefaultEnabled") is True
    except Exception:  # noqa: BLE001
        return False


def wanted(engine, opts) -> bool:
    """Should this run get `--chrome`? See the module docstring for every gate. Never raises."""
    try:
        if not str(getattr(engine, "tag", "") or "").startswith("chat:"):
            return False
        if getattr(engine, "allowed_tools", None) or getattr(engine, "trial_profile", None) is not None:
            return False
        override = (os.environ.get(ENV) or "").strip().lower()
        if override in _OFF:
            return False
        env = getattr(opts, "env", None) or os.environ
        if (env.get("ANTHROPIC_API_KEY") or "").strip():
            return False
        from claude_cli import co_co, find_claude_cli
        cli = getattr(opts, "cli_path", None)
        if not cli or str(cli) != find_claude_cli() or not co_co("--chrome"):
            return False
        if override in _ON:
            return True
        # A second plan account (plan_accounts) keeps its own .claude.json in its config folder.
        return default_enabled(getattr(engine, "claude_config_dir", None) or env.get("CLAUDE_CONFIG_DIR"))
    except Exception:  # noqa: BLE001 - a lookup failure must never break a chat turn
        return False


def install() -> bool:
    """Wrap ClaudeSDK._options once so a qualifying run carries `--chrome`. Idempotent; False without the SDK."""
    try:
        from claude_sdk_engine import ClaudeSDK
    except Exception:  # noqa: BLE001
        return False
    orig = ClaudeSDK.__dict__.get("_options")
    if orig is None:
        return False
    if getattr(orig, "_unimate_chrome", False):
        return True

    def _options(self, *a, **k):
        opts = orig(self, *a, **k)
        if hasattr(opts, "extra_args") and wanted(self, opts):
            opts.extra_args = {**(getattr(opts, "extra_args", None) or {}), "chrome": None}
        return opts

    _options._unimate_chrome = True
    _options.__wrapped__ = orig
    ClaudeSDK._options = _options
    return True
