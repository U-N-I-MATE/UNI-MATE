"""0.440.0: Team members report briefly, a summary reads each result once, and "could not do it" stops the job.

    python tests/python/test_team_bao_gon_0440.py        (fake engines, scratch stores)

Idea from Javis OS 0.436.0, written fresh: a summary turn used to read every member result twice (team history and
"Đầu vào"); a member that could not do its part had no way to say so, and the leader summarised a broken result.
"""
from _paths import ROOT, SERVER  # noqa: E402,F401
import asyncio
import json
import os
import tempfile
from pathlib import Path

os.environ["UNIMATE_STATE_DIR"] = tempfile.mkdtemp(prefix="unimate-team-gon-")
STATE = Path(os.environ["UNIMATE_STATE_DIR"])

import sessions  # noqa: E402
import task_store  # noqa: E402
import team_store  # noqa: E402
import team_runner as TR  # noqa: E402

fails = []


def check(name, cond, extra=""):
    print(("ok   " if cond else "FAIL ") + name + (f"  {extra!r}" if not cond else ""))
    if not cond:
        fails.append(name)


def directive(**op):
    return f"\n<!-- UNIMATE_TEAM: {json.dumps(op, ensure_ascii=False)} -->"


AGENTS = {"ag_lan": ("lan", "Lan"), "ag_minh": ("minh", "Minh"), "ag_hoa": ("hoa", "Hoa")}


class Fake:
    def __init__(self):
        self.script = {}
        self.calls = []
        self.live = 0
        self.peak = 0
        self.parallel_agents = set()
        self.parallel_started = set()
        self.parallel_ready = None

    def expect_parallel(self, *agents):
        self.parallel_agents = set(agents)
        self.parallel_ready = asyncio.Event()

    def say(self, agent, role, *answers):
        self.script.setdefault((agent, role), []).extend(answers)

    def engine_for(self, team, agent_key, role):
        async def run(req):
            self.calls.append(req)
            self.live += 1
            self.peak = max(self.peak, self.live)
            try:
                if role == "work" and agent_key in self.parallel_agents:
                    self.parallel_started.add(agent_key)
                    if self.parallel_started == self.parallel_agents:
                        self.parallel_ready.set()
                    # A timeout reports broken concurrency without hanging the suite.
                    await asyncio.wait_for(self.parallel_ready.wait(), timeout=5)
                else:
                    await asyncio.sleep(0)
                queue = self.script.get((agent_key, role)) or []
                ans = queue.pop(0) if queue else f"{agent_key} {role} xong"
                if callable(ans):
                    ans = await ans(req)
            finally:
                self.live -= 1
            return {"text": ans, "tokens_in": 1, "tokens_out": 1}
        return "fake", "fake-model", run

    def order(self):
        return [(c["agent_key"], c["role"]) for c in self.calls]


def world(name, leader="ag_hoa"):
    d = STATE / name
    d.mkdir()
    ss = sessions.SessionStore(db_path=d / "sessions.db")
    ts = task_store.TaskStore(d / "kanban.sqlite3")
    tm = team_store.TeamStore(d / "team.sqlite3")
    fake = Fake()

    def agent_info(brain, key):
        slug, nm = AGENTS[key]
        return {"slug": slug, "name": nm, "system": f"Bạn là {nm}."}

    r = TR.TeamRunner(teams=tm, tasks=ts, sessions=ss, engine_for=fake.engine_for, agent_info=agent_info,
                      publish=lambda e: None, notify=lambda team_id, text: None)
    tid = team_store.new_team_id()
    sid = ss.create_session(brain="B", channel=f"team:{tid}", title=name)
    tm.create_team("B", name, "mô tả", sid, team_id=tid)
    for k in AGENTS:
        tm.add_member(tid, k, AGENTS[k][0])
    tm.set_leader(tid, leader)
    return ss, ts, tm, fake, r, tm.get(tid)


def run(coro):
    return asyncio.run(coro)


# ================================================================
# 1. A summary reads each result once
# ================================================================
ss, ts, tm, fake, r, T = world("once", leader="ag_hoa")
fake.say("ag_hoa", "plan", "Chia." + directive(op="assign", agent="ag_lan", brief="phần A")
         + directive(op="assign", agent="ag_minh", brief="phần B"))
fake.say("ag_lan", "work", "KẾT QUẢ A: ba điểm chính")
fake.say("ag_minh", "work", "KẾT QUẢ B: hai rủi ro")
fake.say("ag_hoa", "synthesize", "TỔNG HỢP")
job = r.submit(T["team_id"], "Hai phần", as_job=True, client_msg_id="j1")
run(r.dispatch_once(wait=True))
synth = next((c["prompt"] for c in fake.calls if c["role"] == "synthesize"), "")
check("once: each result appears once in the summary prompt",
      synth.count("KẾT QUẢ A: ba điểm chính") == 1 and synth.count("KẾT QUẢ B: hai rủi ro") == 1,
      (synth.count("KẾT QUẢ A"), synth.count("KẾT QUẢ B")))
check("once: the history keeps a pointer to the input instead", "(nội dung ở phần Đầu vào bên dưới)" in synth)
check("once: the job closes with the summary", ts.get_task(job["task_id"])["status"] == "done")

# A result longer than an input's cap stays in full in the history (the input copy is cut).
ss, ts, tm, fake, r, T = world("long", leader="ag_hoa")
LONG = "DÀI " + "x" * (TR.INPUT_CHARS + 50) + " ĐUÔI"
fake.say("ag_hoa", "plan", "Chia." + directive(op="assign", agent="ag_lan", brief="phần A")
         + directive(op="assign", agent="ag_minh", brief="phần B"))
fake.say("ag_lan", "work", LONG)
fake.say("ag_minh", "work", "ngắn")
job = r.submit(T["team_id"], "Hai phần", as_job=True, client_msg_id="j1")
run(r.dispatch_once(wait=True))
synth = next((c["prompt"] for c in fake.calls if c["role"] == "synthesize"), "")
check("long: the tail of a long result is not lost", "ĐUÔI" in synth)

# ================================================================
# 2. A member that could not do its part stops the job for the owner
# ================================================================
ss, ts, tm, fake, r, T = world("not_done", leader="ag_hoa")
fake.say("ag_hoa", "plan", "Chia." + directive(op="assign", agent="ag_lan", brief="phần A")
         + directive(op="assign", agent="ag_minh", brief="phần B"))
fake.say("ag_lan", "work", "Không mở được file số liệu." + directive(op="not_done", reason="thiếu file số liệu"))
fake.say("ag_minh", "work", "KẾT QUẢ B")
job = r.submit(T["team_id"], "Hai phần", as_job=True, client_msg_id="j1")
run(r.dispatch_once(wait=True))
task = ts.get_task(job["task_id"])
check("not_done: the job stops for the owner, no summary turn",
      task["status"] == "team_blocked" and ("ag_hoa", "synthesize") not in fake.order(), (task["status"], fake.order()))
check("not_done: the reason names the member and why", "Lan" in (task.get("block_reason") or "")
      and "thiếu file số liệu" in task["block_reason"], task.get("block_reason"))
_lan = next(s for s in tm.steps(job["task_id"]) if s["agent_key"] == "ag_lan")
_minh = next(s for s in tm.steps(job["task_id"]) if s["agent_key"] == "ag_minh")
check("not_done: that step is failed (Run the step again reruns it)", _lan["status"] == "failed", _lan["status"])
check("not_done: the good sibling result is kept", _minh["status"] == "done" and _minh["applied"], _minh["status"])

fake.say("ag_lan", "work", "KẾT QUẢ A sau khi có file")
fake.say("ag_hoa", "synthesize", "TỔNG HỢP ĐỦ")
_ok = r.unblock(job["task_id"], "retry")
run(r.dispatch_once(wait=True))
task = ts.get_task(job["task_id"])
check("not_done: running the step again finishes the job", task["status"] == "done" and "TỔNG HỢP ĐỦ" in (task.get("result") or ""),
      (_ok, task["status"], task.get("block_reason"), fake.order()))

check("work prompt asks for a short summary and explains not_done",
      any("tối đa 3 câu" in c["prompt"] and '"op": "not_done"' in c["prompt"] for c in fake.calls if c["role"] == "work"))

print()
if fails:
    print(f"{len(fails)} FAIL")
    raise SystemExit(1)
print("ALL PASS")
