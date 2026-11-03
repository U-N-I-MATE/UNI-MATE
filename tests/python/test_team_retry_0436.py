"""0.436.0: a team turn retries a passing engine hiccup on its own, and never sends or posts twice.

    python tests/run.py team_retry_0436

Before: one 503 or dropped connection failed the step and blocked the whole job until the owner pressed Run again.
Fake engines only, no model call, no real waiting (the runner's sleep is replaced).
"""
from _paths import ROOT, SERVER  # noqa: E402,F401
import asyncio
import json
import os
import random
import tempfile
from pathlib import Path

os.environ["UNIMATE_STATE_DIR"] = tempfile.mkdtemp(prefix="unimate-team-retry-")
STATE = Path(os.environ["UNIMATE_STATE_DIR"])

import sessions  # noqa: E402
import task_store  # noqa: E402
import team_retry as RT  # noqa: E402
import team_runner as TR  # noqa: E402
import team_store  # noqa: E402

fails = []


def check(name, cond, extra=""):
    print(("ok   " if cond else "FAIL ") + name + (f"  {str(extra)[:300]}" if extra and not cond else ""))
    if not cond:
        fails.append(name)


def run(coro):
    return asyncio.run(coro)


def err(text, **kw):
    return dict({"status": "error", "error": text, "detail": text}, **kw)


# ───────────── 1. classify: what is worth a retry ─────────────
for t in ("HTTP 503 Service Unavailable", "API Error: 529 overloaded_error", "Connection reset by peer",
          "stream disconnected before completion", "Request timed out", "429 Too Many Requests"):
    check(f"transient: {t}", RT.classify(err(t)) == "transient", RT.classify(err(t)))
for t in ("Claude AI usage limit reached|1762200000", "You've hit your 5-hour limit", "insufficient_quota",
          "429 resource_exhausted: quota"):
    check(f"plan limit, not retried: {t}", RT.classify(err(t)) == "plan")
for t in ("401 Unauthorized", "invalid_api_key", "400 invalid_request: prompt is too long", "model_not_found"):
    check(f"fatal, not retried: {t}", RT.classify(err(t)) == "fatal")
check("an unknown error is not retried", RT.classify(err("engine gọi công cụ trong lượt chỉ chữ")) == "")
check("our own wall-clock timeout is not retried", RT.classify(err("quá 15 phút", reason="timeout")) == "fatal")
check("a login error is not retried", RT.classify(err("503", reason="auth")) == "fatal")
check("a success is not an error", RT.classify({"status": "done"}) == "")

# ───────────── 2. wait: bounded, growing, honours a short retry-after ─────────────
rng = random.Random(1)
w1, w2 = RT.wait_s(err("503"), 1, rng), RT.wait_s(err("503"), 2, rng)
check("retry 1 waits about 6 s", 6 <= w1 <= 6 * 1.25, w1)
check("retry 2 waits longer", w2 > w1 and w2 <= RT.MAX_WAIT_S, w2)
check("no retry 3", RT.wait_s(err("503"), RT.MAX_RETRIES + 1) is None)
check("retry-after 3 seconds is honoured", RT.wait_s(err("429 rate limit, retry after 3 seconds"), 1) == 3.0)
check("retry-after 2 minutes means not now", RT.wait_s(err("overloaded, please try again in 2 minutes"), 1) is None)
check("every wait stays under a third of the job lease", RT.MAX_WAIT_S < TR.JOB_LEASE_S / 3)

# ───────────── 3. never a second send or post ─────────────
acted = err("503 Service Unavailable", tool_turn=True)
check("a tool step that reached the model is never retried", RT.wait_s(acted, 1) is None and RT.may_have_acted(acted))
check("and its failure says why, so the owner checks before Run again", "hai lần" in RT.not_retried_note(acted))
check("a tool step that failed BEFORE the model is safe to retry",
      RT.wait_s(err("503", tool_turn=True, before_engine=True), 1) is not None)
check("a text turn is safe to retry (nothing is posted until it succeeds)", RT.wait_s(err("503"), 1) is not None)

# ───────────── 4. the runner: chat replies and job steps ─────────────
AGENTS = {"ag_lan": ("lan", "Lan"), "ag_minh": ("minh", "Minh")}


class Fake:
    def __init__(self):
        self.script, self.calls = {}, []

    def say(self, agent, role, *answers):
        self.script.setdefault((agent, role), []).extend(answers)

    def engine_for(self, team, agent_key, role):
        async def go(req):
            self.calls.append((agent_key, role, bool(req.get("tool_turn"))))
            q = self.script.get((agent_key, role)) or []
            ans = q.pop(0) if q else f"{agent_key} {role} xong"
            if isinstance(ans, Exception):
                raise ans
            return {"text": ans, "tokens_in": 3, "tokens_out": 2}
        return "fake", "fake-model", go


def world(name):
    d = STATE / name
    d.mkdir()
    ss = sessions.SessionStore(db_path=d / "sessions.db")
    ts = task_store.TaskStore(d / "kanban.sqlite3")
    tm = team_store.TeamStore(d / "team.sqlite3")
    fake = Fake()
    r = TR.TeamRunner(teams=tm, tasks=ts, sessions=ss, engine_for=fake.engine_for,
                      agent_info=lambda b, k: ({"slug": AGENTS[k][0], "name": AGENTS[k][1], "system": "x"}
                                               if k in AGENTS else None),
                      publish=lambda ev: None, notify=lambda team_id, text: None)
    waits = []

    async def no_sleep(s):
        waits.append(s)
    r.retry_sleep = no_sleep
    tid = team_store.new_team_id()
    sid = ss.create_session(brain="B", channel=f"team:{tid}", title=name)
    tm.create_team("B", name, "mô tả", sid, team_id=tid)
    for k in AGENTS:
        tm.add_member(tid, k, AGENTS[k][0])
    tm.set_leader(tid, "ag_lan")
    return ss, ts, tm, fake, r, waits, tm.get(tid)


def agent_msgs(ss, team):
    return [m for m in ss.get_team_messages_page(team["session_id"], limit=200)["messages"]
            if m["author_kind"] == "agent"]


# A chat reply hits one 503, then answers: one message, one retry, the reply row ends done.
ss, ts, tm, fake, r, waits, T = world("reply")
fake.say("ag_lan", "leader_reply", RuntimeError("API Error: 503 Service Unavailable"), "Chào anh, em đây")
sub = r.submit(T["team_id"], "Chào nhóm", client_msg_id="c1")
run(r.run_replies(sub))
msgs = agent_msgs(ss, T)
check("reply: the 503 is retried once and the answer is posted", len(fake.calls) == 2 and len(waits) == 1
      and len(msgs) == 1 and msgs[0]["content"] == "Chào anh, em đây", (fake.calls, waits, len(msgs)))
row = tm.reply(T["team_id"], sub["message_id"], "ag_lan")
check("reply: the status row ends done, not error", row and row["status"] == "done", row)
turns = tm.turns(T["team_id"])
check("reply: each attempt is a real, settled turn (counts against the caps)",
      sorted(t["status"] for t in turns) == ["error", "ok"], [t["status"] for t in turns])

# A plan limit is NOT retried: one call, the error stays for the owner.
fake.calls.clear()
waits.clear()
fake.say("ag_lan", "leader_reply", RuntimeError("Claude AI usage limit reached"))
sub = r.submit(T["team_id"], "Còn đó không", client_msg_id="c2")
run(r.run_replies(sub))
row = tm.reply(T["team_id"], sub["message_id"], "ag_lan")
check("reply: a plan limit is not retried", len(fake.calls) == 1 and not waits and row["status"] == "error", row)

# Three transient errors in a row: two retries, then the error, saying it already retried.
fake.calls.clear()
waits.clear()
fake.say("ag_lan", "leader_reply", *[RuntimeError("overloaded_error")] * 3)
sub = r.submit(T["team_id"], "Thử lại nhé", client_msg_id="c3")
run(r.run_replies(sub))
row = tm.reply(T["team_id"], sub["message_id"], "ag_lan")
check("reply: bounded, at most MAX_RETRIES extra attempts", len(fake.calls) == 1 + RT.MAX_RETRIES
      and len(waits) == RT.MAX_RETRIES, (fake.calls, waits))
check("reply: the final error says it already retried", row["status"] == "error" and "đã tự thử lại 2 lần"
      in (row.get("detail") or "") + str(row), row)

# A job: the plan step (text) retries; a Work step WITH TOOLS that reached the model does not.
ss, ts, tm, fake, r, waits, T = world("job")
fake.say("ag_lan", "plan", RuntimeError("Connection reset by peer"),
         "Chia việc.\n<!-- UNIMATE_TEAM: " + json.dumps({"op": "assign", "agent": "ag_minh", "brief": "Gửi thư"}) + " -->")
fake.say("ag_minh", "work", RuntimeError("HTTP 503 Service Unavailable"), "đã gửi thư lần hai")
job = r.submit(T["team_id"], "Gửi thư cho khách", as_job=True, client_msg_id="j1")
run(r.dispatch_once(wait=True))
plans = [c for c in fake.calls if c[1] == "plan"]
works = [c for c in fake.calls if c[1] == "work"]
check("job: the text plan step retried the dropped connection", len(plans) == 2 and len(waits) == 1, fake.calls)
check("job: the Work step is a tool turn", works and works[0][2] is True, works)
check("job: a tool step that failed after reaching the model is NOT re-run (no second send)", len(works) == 1, works)
task = ts.get_task(job["task_id"])
step = [s for s in tm.steps(job["task_id"]) if s["kind"] == "work"][0]
check("job: the job waits for the owner instead of guessing", task["status"] == "team_blocked", task["status"])
check("job: the failed step tells the owner why it was not retried", "hai lần" in (step.get("note") or ""), step)

# The switch turns it off.
ss, ts, tm, fake, r, waits, T = world("off")
r.retry_transient = False
fake.say("ag_lan", "leader_reply", RuntimeError("503"), "không tới")
sub = r.submit(T["team_id"], "Chào", client_msg_id="c1")
run(r.run_replies(sub))
check("UNIMATE_TEAM_RETRY=0 turns it off", len(fake.calls) == 1 and not waits)

# The chat shows the retry while it happens.
js = (ROOT / "dashboard" / "teams.js").read_text(encoding="utf-8")
vi = json.loads((ROOT / "dashboard" / "i18n" / "vi.json").read_text(encoding="utf-8"))
en = json.loads((ROOT / "dashboard" / "i18n" / "en.json").read_text(encoding="utf-8"))
check("team chat shows 'retrying' on the reply row", 'x.reason === "retrying"' in js
      and "{n}" in vi.get("teams.reply.auto_retry", "") and "{n}" in en.get("teams.reply.auto_retry", ""))

if fails:
    print(f"\nFAIL - test_team_retry_0436: {len(fails)}")
    raise SystemExit(1)
print("\nOK - test_team_retry_0436: all pass")
