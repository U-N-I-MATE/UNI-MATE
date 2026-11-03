"""Regression (0.432.0): "You've hit your 5-hour limit" and the reset time in the owner's time zone.

1. Claude Code's newer wording names the window: "You've hit your 5-hour limit · resets 3pm (UTC)".
   None of the patterns matched it ("5-hour limit reached" needs "reached" after, "hit your limit"
   needs nothing between), so the English line reached chat as if it were the answer, with no
   retry card. The weekly twin was matched only by the Codex pattern and named the wrong plan.
2. The notice printed the reset as HH:MM on the MACHINE clock. A VPS runs on UTC, so a reset at
   15:00 Vietnam time read 08:00. It now follows the time zone chosen in Settings, and adds the
   date when the reset falls on another day.

Run:
    python tests/python/test_limit_5h_wording.py
"""
from _paths import ROOT, SERVER  # noqa: E402,F401  - puts server/ on sys.path (see tests/python/_paths.py)
import sys
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

import limit_learner  # noqa: E402
import localefmt  # noqa: E402
import model_limits  # noqa: E402

fails = []


def check(name, cond):
    print(("ok   " if cond else "FAIL ") + name)
    if not cond:
        fails.append(name)


def utc(*a) -> float:
    return datetime(*a, tzinfo=timezone.utc).timestamp()


NOW = utc(2026, 11, 3, 6, 0)           # 13:00 on 03/11 in Vietnam
FIVE_H = "You've hit your 5-hour limit · resets 8am (UTC)"
WEEKLY = "You've hit your weekly limit · resets Nov 5, 8am (UTC)"

# ── 1. the wording is recognised ──
hit = limit_learner.parse_subscription_limit(FIVE_H, engine_hint="claude-code", now=NOW)
check("5-hour wording is a plan limit", hit is not None)
check("5-hour wording names the 5-hour window", hit is not None and hit.scope == "5 giờ")
check("5-hour wording keeps the caller's engine", hit is not None and hit.engine == "claude-code")
check("5-hour wording has the reset time", hit is not None and hit.reset_epoch == utc(2026, 11, 3, 8, 0))
check("'5 hour' without the hyphen too",
      limit_learner.parse_subscription_limit("You've hit your 5 hour limit", "claude-code", NOW) is not None)
check("the bare provider line dominates the output (chat path catches it)",
      limit_learner.subscription_dominates(FIVE_H))
check("a line quoted inside an article does not dominate",
      not limit_learner.subscription_dominates(
          "Bài viết hôm nay nói về cách dùng AI. " * 20
          + 'Khi thấy câu "You\'ve hit your 5-hour limit" thì nên chờ một lúc rồi hỏi lại. '
          + "Phần tiếp theo bàn về chi phí. " * 20))

wk = limit_learner.parse_subscription_limit(WEEKLY, engine_hint="claude-code", now=NOW)
check("weekly wording names the weekly window", wk is not None and wk.scope == "tuần")
check("weekly wording with a Claude hint is the Claude plan", wk is not None and wk.engine == "claude-code")
no_hint = limit_learner.parse_subscription_limit(WEEKLY, now=NOW)
check("weekly wording without a hint names no plan (never the wrong one)",
      no_hint is not None and no_hint.engine == "")
usage = limit_learner.parse_subscription_limit("You've hit your usage limit", now=NOW)
check("Codex's usage wording still reads as Codex", usage is not None and usage.engine == "codex")

# ── 2. the reset time follows the time zone in Settings ──
_orig_tz = localefmt.tz
try:
    localefmt.tz = lambda: ZoneInfo("Asia/Ho_Chi_Minh")
    check("same-day reset shows the Vietnam clock",
          model_limits._reset_clock_text(utc(2026, 11, 3, 8, 0), NOW) == "15:00")
    check("next-day reset adds the date",
          model_limits._reset_clock_text(utc(2026, 11, 3, 18, 30), NOW) == "01:30 ngày 04/11")
    msg = model_limits.subscription_blocked_hint(hit, (), now=NOW)
    check("notice says 15:00, not the UTC 08:00", "tầm 15:00" in msg and "tầm 08:00" not in msg)
    check("notice names the 5-hour window", "cửa sổ 5 giờ" in msg)

    localefmt.tz = lambda: ZoneInfo("America/New_York")
    check("another zone chosen in Settings is honoured",
          model_limits._reset_clock_text(utc(2026, 11, 3, 8, 0), NOW) == "03:00")

    def _broken():
        raise RuntimeError("settings unreadable")
    localefmt.tz = _broken
    check("a broken settings read still yields a time, never an exception",
          len(model_limits._reset_clock_text(utc(2026, 11, 3, 8, 0), NOW)) >= 5)
finally:
    localefmt.tz = _orig_tz

if fails:
    print(f"FAIL - test_limit_5h_wording: {len(fails)} failed: {fails}")
    sys.exit(1)
print("PASS - test_limit_5h_wording")
