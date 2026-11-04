"""0.433.0: "today" follows the time zone chosen in Settings, not the machine clock.

A VPS runs on UTC. Before this, daily caps, habit ticks and printed clocks there used the
machine's zone, so between 00:00 and 07:00 Vietnam time UNI MATE still thought it was yesterday.
"""
import os
import sys
from datetime import datetime, timezone

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "server"))
import _paths  # noqa: F401,E402

import localefmt  # noqa: E402
import agent_budget  # noqa: E402

ok = 0


def check(cond, msg):
    global ok
    assert cond, msg
    ok += 1
    print("ok  ", msg)


ZONE = {"name": "Asia/Ho_Chi_Minh"}
localefmt.ten_tz = lambda: ZONE["name"]

# 2026-11-03 19:30 UTC is 2026-11-04 02:30 in Vietnam: the owner's "today" is the 4th.
ts = datetime(2026, 11, 3, 19, 30, tzinfo=timezone.utc).timestamp()
check(localefmt.day_tag(ts) == "2026-11-04", "day_tag reads the owner's calendar day, not UTC")
d0 = localefmt.day_start(ts)
check(datetime.fromtimestamp(d0, localefmt.tz()).strftime("%Y-%m-%d %H:%M") == "2026-11-04 00:00",
      "day_start is local midnight in the chosen zone")
check(ts - d0 == 2.5 * 3600, "day_start is 2h30 before 02:30")
check(localefmt.clock(ts) == "2026-11-04 02:30", "clock prints the owner's time")
check(localefmt.clock(ts, "%H:%M") == "02:30", "clock accepts a pattern")

check(agent_budget.day_tag(ts) == "2026-11-04", "agent_budget daily key follows the chosen zone")
check(agent_budget.day_start(ts) == d0, "agent_budget daily window starts at the owner's midnight")

ZONE["name"] = "America/New_York"
localefmt._CACHE.clear()   # 0.444.0: tz() memoizes the zone by the settings.json signature; this test fakes ten_tz without writing to disk
check(localefmt.day_tag(ts) == "2026-11-03", "another zone moves the day boundary with it")
check(agent_budget.day_tag(ts) == "2026-11-03", "and agent_budget follows the change at once")

check(localefmt.hop_le_tz("Asia/Ho_Chi_Minh"), "a real IANA zone is accepted")
check(localefmt.hop_le_tz("UTC"), "UTC is accepted")
check(not localefmt.hop_le_tz("Asia/Saigonn"), "a typo is rejected")
check(not localefmt.hop_le_tz(""), "an empty name is rejected")
check(not localefmt.hop_le_tz("../../etc/passwd"), "a path is rejected")

# The settings endpoint must refuse an unknown zone instead of saving it and reporting success.
src = open(os.path.join(os.path.dirname(__file__), "..", "..", "server", "main.py"), encoding="utf-8").read()
i = src.index('if "tz" in patch:')
check("hop_le_tz" in src[i:i + 600] and "status_code=400" in src[i:i + 600],
      "POST /settings locale.tz rejects an unknown zone with 400")

# The dashboard has a picker wired to locale.tz.
js = open(os.path.join(os.path.dirname(__file__), "..", "..", "dashboard", "console.js"), encoding="utf-8").read()
check('id="vpTz"' in js and 'saveSetting("locale", { tz: zone })' in js, "Settings has a time zone picker that saves locale.tz")

print(f"PASS - test_tz_today_0433 ({ok} checks)")
