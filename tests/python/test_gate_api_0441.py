"""0.441.0: gate_api, what an outside AI gate (store pack "UNI MATE trong ChatGPT") may read and record.

Owner's decision 03/11/2026: the outside AI reads the owner's own conversations and records what was decided over there
as a conversation of its own; it never touches customer, Zalo group or Team chats, and recording runs no model.
"""
import asyncio
import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SERVER = ROOT / "server"
sys.path.insert(0, str(SERVER))
os.environ["UNIMATE_STATE_DIR"] = tempfile.mkdtemp(prefix="unimate-gate0441-")

_fails = []


def check(name, cond, info=""):
    print(("ok   " if cond else "FAIL ") + name + ("" if cond else f"  -> {str(info)[:300]}"))
    if not cond:
        _fails.append(name)


import main  # noqa: E402
import gate_api as G  # noqa: E402
from sessions import get_store  # noqa: E402

brain = tempfile.mkdtemp(prefix="unimate-gate0441-brain-")
other = tempfile.mkdtemp(prefix="unimate-gate0441-other-")
store = get_store()
key = main._brain_key(brain)


def chat(channel, title, b=key):
    sid = store.create_session(brain=b, title=title, channel=channel)
    store.append_message(sid, "user", f"hỏi {title}")
    store.append_message(sid, "assistant", f"trả lời {title}")
    return sid


s_web = chat("web", "Kế hoạch tháng 11")
s_tg = chat("telegram", "Hỏi qua Telegram")
s_agent = chat("agent:ke-toan", "Với trợ lý kế toán")
s_team = chat("team:t1", "Chat của Team")
s_mate = chat("teammate:t1:a", "Thành viên Team")
s_bot = chat("bot:shop", "Khách hỏi giá")
s_flow = chat("workflow:bao-cao", "Lượt workflow")
s_other = chat("web", "Brain khác", b=main._brain_key(other))

ids = {c["id"] for c in G.list_chats(brain, limit=50)}
check("list: the owner's chats (dashboard, Telegram, partner agent)", {s_web, s_tg, s_agent} <= ids, ids)
check("list: never Team, teammate, customer bot or workflow chats",
      not ({s_team, s_mate, s_bot, s_flow} & ids), ids)
check("list: only the brain that is open", s_other not in ids)
check("list: a query narrows by title", [c["id"] for c in G.list_chats(brain, query="tháng 11")] == [s_web])
check("list: limit is capped", len(G.list_chats(brain, limit=1)) == 1)

r = G.read_chat(s_web, brain)
check("read: messages oldest first", [m["role"] for m in r["messages"]] == ["user", "assistant"]
      and r["messages"][1]["content"] == "trả lời Kế hoạch tháng 11", r)
for bad, why in ((s_team, "Team"), (s_bot, "customer bot"), (s_flow, "workflow"), (s_other, "other brain"),
                 ("khong-co", "missing")):
    try:
        G.read_chat(bad, brain)
        check(f"read: refuses {why}", False)
    except G.GateError as e:
        check(f"read: refuses {why} with one neutral answer", "Không có hội thoại này" in str(e), str(e))

# record_note: a conversation of its own, saved like a normal turn, no model.
called = {}
_orig_enqueue = main.learn_feature.enqueue


async def _spy(b, sid, u, a):
    called["enqueue"] = (sid, u, a)
    return await _orig_enqueue(b, sid, u, a)

main.learn_feature.enqueue = _spy
try:
    out = asyncio.run(G.record_note(brain, "chatgpt", "Kế hoạch Tết",
                                    "Chốt: khuyến mãi 10% từ 20/01, ngân sách 50 triệu.", asked="Lên kế hoạch Tết"))
finally:
    main.learn_feature.enqueue = _orig_enqueue
row = store.get_session(out["session_id"])
check("note: titled 'Từ ChatGPT: ...' (source name normalised)", row["title"] == "Từ ChatGPT: Kế hoạch Tết", row["title"])
check("note: an owner chat in the open brain", row["channel"] == "web" and row["brain"] == key, row)
msgs = store.get_messages(out["session_id"])
check("note: the question and the decision, nothing else", [m["role"] for m in msgs] == ["user", "assistant"]
      and "50 triệu" in msgs[1]["content"] and msgs[0]["content"] == "Lên kế hoạch Tết", msgs)
check("note: it reaches the self-learning queue like a chat turn", called.get("enqueue", ("",))[0] == out["session_id"])
log = list((main._brain_memory_dir(brain) / "conversations").glob("*.md"))
check("note: it is written to the brain's conversation log", log and "50 triệu" in log[0].read_text(encoding="utf-8"))
check("note: listed among the owner's chats", out["session_id"] in {c["id"] for c in G.list_chats(brain)})
for args in (("", "x"), ("x", "")):
    try:
        asyncio.run(G.record_note(brain, "Claude", *args))
        check("note: refuses an empty title or note", False)
    except G.GateError:
        check("note: refuses an empty title or note", True)
check("no em dash in what the outside AI reads", "—" not in (SERVER / "gate_api.py").read_text(encoding="utf-8"))

print()
if _fails:
    print(f"FAIL {len(_fails)}: {_fails}")
    sys.exit(1)
print("OK - test_gate_api_0441: all pass")
