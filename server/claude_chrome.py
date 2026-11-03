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

0.431.0 adds two things, both driven by device ids the owner saves on the Claude Code card of the Models page
(settings model.claude_chrome.chat_device / job_device; env UNIMATE_CHROME_CHAT_DEVICE / _JOB_DEVICE win):
- Pinning. With two browsers connected (the owner's PC and a Chromium on the VPS) Claude in Chrome asks which one
  to use at the start of every session. A saved device id is the owner's standing choice, so the run is told to call
  select_browser with it before its first browser action. The pairing Claude Code persists is global and shared
  across concurrent runs, so the pin is per run, through the system prompt, never by editing .claude.json.
- Schedules. A reminder whose owner switched on "Dùng Chrome" (rem["chrome"]) runs with `--chrome` pinned to the job
  device only. No job device saved = no Chrome for any schedule, so a background run can never land in the
  owner's own signed-in Chrome by accident. Same plan-login and binary gates as chat; the reminder must run at the
  full level (allowed_tools None), since a whitelisted lighter run has no browser tools anyway.
"""
from __future__ import annotations

import json
import os
import re
from pathlib import Path

ENV = "UNIMATE_CLAUDE_CHROME"
_OFF = ("0", "false", "off", "no")
_ON = ("1", "true", "on", "yes")


ENV_CHAT_DEVICE = "UNIMATE_CHROME_CHAT_DEVICE"
ENV_JOB_DEVICE = "UNIMATE_CHROME_JOB_DEVICE"
# Device ids are UUIDs today; accept any short id of hex digits and dashes, nothing else reaches the prompt.
_DEVICE_RE = re.compile(r"^[0-9A-Za-z][0-9A-Za-z-]{3,63}$")
JOB_ATTR = "chrome_job"   # set on a reminder's engine when that reminder has its Chrome switch on


def clean_device(value) -> str:
    """A device id as saved: trimmed, or "" when it is not a plausible id (so junk never reaches the prompt)."""
    v = str(value or "").strip()
    return v if _DEVICE_RE.match(v) else ""


def devices(settings: dict | None = None) -> dict:
    """{"chat_device", "job_device"} from env first, then settings. Never raises."""
    out = {"chat_device": "", "job_device": ""}
    try:
        if settings is None:
            import config as _cfg
            settings = _cfg.read_settings()
        saved = ((settings or {}).get("model") or {}).get("claude_chrome") or {}
    except Exception:  # noqa: BLE001
        saved = {}
    for key, env in (("chat_device", ENV_CHAT_DEVICE), ("job_device", ENV_JOB_DEVICE)):
        out[key] = clean_device(os.environ.get(env)) or clean_device(saved.get(key))
    return out


def pin_text(device: str, job: bool = False) -> str:
    """The run-level instruction that pins Claude in Chrome to one device (prompt text stays Vietnamese)."""
    lines = [
        "",
        "## Trình duyệt Chrome của lượt này",
        f"- Chủ đã chọn sẵn trình duyệt trong Cài đặt: deviceId `{device}`. Trước thao tác trình duyệt ĐẦU TIÊN, "
        f"gọi `select_browser` với đúng deviceId này. Không hỏi lại chủ chọn trình duyệt nào.",
        "- Chỉ dùng trình duyệt này. Không có nó trong danh sách trình duyệt đang kết nối thì nói đúng như vậy "
        "và bỏ phần việc cần trình duyệt; TUYỆT ĐỐI không chuyển sang trình duyệt khác.",
    ]
    if job:
        lines.append("- Đây là việc chạy nền theo lịch: chỉ được dùng Chrome riêng của máy chủ ở trên, "
                     "không bao giờ dùng Chrome trên máy cá nhân của chủ.")
    return "\n".join(lines) + "\n"


def _is_job(engine) -> bool:
    return (str(getattr(engine, "tag", "") or "").startswith("reminder:")
            and getattr(engine, JOB_ATTR, False) is True)


def _append_prompt(opts, text: str) -> bool:
    """Append `text` to whatever carries the system prompt of these options. True when it landed."""
    extra = getattr(opts, "extra_args", None) or {}
    path = extra.get("append-system-prompt-file")
    if path:
        with open(path, "a", encoding="utf-8") as f:
            f.write(text)
        return True
    sp = getattr(opts, "system_prompt", None)
    if isinstance(sp, str):
        opts.system_prompt = sp + text
        return True
    if isinstance(sp, dict):
        opts.system_prompt = {**sp, "append": (sp.get("append") or "") + text}
        return True
    return False


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
        job = _is_job(engine)
        if not job and not str(getattr(engine, "tag", "") or "").startswith("chat:"):
            return False
        if getattr(engine, "allowed_tools", None) or getattr(engine, "trial_profile", None) is not None:
            return False
        if job and not devices().get("job_device"):
            return False   # a schedule never gets Chrome without a dedicated job browser
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
        if override in _ON or job:
            return True   # a schedule's own switch is the owner's explicit opt-in
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
            try:
                job = _is_job(self)
                dev = devices().get("job_device" if job else "chat_device")
                if dev:
                    _append_prompt(opts, pin_text(dev, job=job))
            except Exception:  # noqa: BLE001 - the pin is a nicety, the turn must still run
                pass
        return opts

    _options._unimate_chrome = True
    _options.__wrapped__ = orig
    ClaudeSDK._options = _options
    return True
