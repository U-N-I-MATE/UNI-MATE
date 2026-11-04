"""0.447.0: the gate starts a new main chat when no id is given, and lists the brains for pinning.

    python tests/run.py gate_new_chat_0447      (NO network)

Owner, 04/11/2026: `unimate_gate_send_chat` without a chat id starts a new conversation in the main chat of the gate's
pinned brain, titled "Từ ChatGPT: <title>" or "Từ Claude: <title>", then runs the turn as if the owner typed it. The
pack pins a brain because the core's "brain in use" jumps with any activity; `gate_api.list_brains` feeds its picker.
Same real chat loop and fake API engine as test_gate_send_chat_0446.
"""
from _paths import ROOT, SERVER  # noqa: E402,F401
import asyncio
import json
import os
import sys
import tempfile
from pathlib import Path

os.environ["UNIMATE_API_STREAM_TOOLS"] = "0"
_STATE = tempfile.mkdtemp(prefix="unimate-0447-")
os.environ["UNIMATE_STATE_DIR"] = _STATE
_BRAINS = tempfile.mkdtemp(prefix="unimate-0447-brains-")
os.environ["BRAINS_DIR"] = _BRAINS     # this test creates brain folders: never in the real brains/
os.environ["UNIMATE_ALLOWED_HOSTS"] = "testserver"
try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

import main  # noqa: E402
import engine  # noqa: E402
import gate_api as G  # noqa: E402
import plugins_host  # noqa: E402
from chat_runtime import ChatRuntime  # noqa: E402

_fails = []


def check(name, cond, extra=""):
    print(("ok   " if cond else "FAIL ") + name + (("  [" + str(extra)[:300] + "]") if not cond else ""))
    if not cond:
        _fails.append(name)


class _Resp:
    def __init__(self, data):
        self.status_code, self._data, self.text, self.headers = 200, data, json.dumps(data), {}

    def json(self):
        return self._data


DELAY = {"s": 0.02}


class _FakeClient:
    """Like OpenRouter: answers in text, echoing the owner's last line so the test knows which message it answered."""

    def __init__(self, *a, **kw):
        pass

    async def __aenter__(self):
        return self

    async def __aexit__(self, *a):
        return False

    async def post(self, url, headers=None, json=None):
        msgs = (json or {}).get("messages") or []
        last = next((m.get("content") for m in reversed(msgs) if m.get("role") == "user"), "")
        if isinstance(last, list):
            last = " ".join(str(p.get("text") or "") for p in last if isinstance(p, dict))
        await asyncio.sleep(DELAY["s"])
        line = str(last or "").strip().splitlines()[-1] if str(last or "").strip() else ""
        return _Resp({"choices": [{"message": {"content": "DONE: " + line[:120]}}],
                      "usage": {"prompt_tokens": 1, "completion_tokens": 1}})


RUNTIME = ChatRuntime()
main._CHAT_RUNTIME = RUNTIME
_real_gate_active = main.cfgmod.gate_active
main.cfgmod.gate_active = lambda: False
main._chat_provider = lambda _cfg: ("openrouter", "api", "test-key", "test-model")
main._chat_provider_for_session = lambda _cfg, _row: ("openrouter", "api", "test-key", "test-model")
main._reasoning_level = lambda _cfg: "off"
LOG = []
main.log_conversation = lambda brain, u, a: LOG.append((u, a))
main.usage_store.record = lambda *a, **k: None
engine.httpx.AsyncClient = _FakeClient


async def _none(*a, **k):
    return None


async def _false(*a, **k):
    return False
main._schedule_cancel_action = _none
main.compaction.maybe_compact = _false
LEARN = []


async def _learn(brain, sid, u, a):
    LEARN.append((sid, u, a))
main.learn_feature.enqueue = _learn

BRAIN_DIR = str(Path(tempfile.mkdtemp(prefix="brain-0446-")).resolve())
BRAIN = main._brain_key(BRAIN_DIR)
OTHER = main._brain_key(str(Path(tempfile.mkdtemp(prefix="brain-0446-other-")).resolve()))
ss = main.get_store()
WEB = ss.create_session(brain=BRAIN, engine="test", model="test", title="Web bán nước mắm")
ss.append_message(WEB, "user", "Làm trang web bán nước mắm giúp anh")
ss.append_message(WEB, "assistant", "Em đã dựng xong bản nháp trang chủ.")
OLD = ss.create_session(brain=BRAIN, engine="test", model="test", title="Hội thoại cũ", channel="")
AGENT = ss.create_session(brain=BRAIN, engine="test", model="test", title="Cộng sự viết bài", channel="agent:viet-bai")
TG = ss.create_session(brain=BRAIN, engine="test", model="test", title="Qua Telegram", channel="telegram")
BOT = ss.create_session(brain=BRAIN, engine="test", model="test", title="Khách hỏi giá", channel="bot:shop")
TEAM = ss.create_session(brain=BRAIN, engine="test", model="test", title="Team", channel="team:t1")
ELSEWHERE = ss.create_session(brain=OTHER, engine="test", model="test", title="Brain khác")

EVENTS = []


async def _tab(ev):
    EVENTS.append(ev)
RUNTIME.add_client("test-tab", _tab)

loop = asyncio.new_event_loop()
asyncio.set_event_loop(loop)


def run(coro):
    return loop.run_until_complete(coro)


def refused(coro):
    try:
        run(coro)
        return ""
    except G.GateError as e:
        return str(e) or "refused"


# ============================================================
# 1. No id: a new main chat in the given brain, then a normal turn
# ============================================================
EVENTS.clear()
n_before = len(ss.list_sessions(limit=500, brain=[BRAIN], channel="*"))
r = run(G.send_chat("", BRAIN, "Lên danh sách việc tuần này cho anh.", "Claude", title="Việc tuần 45"))
check("no id: a conversation is created and the turn starts", r.get("created") is True and r.get("mode") == "started", r)
row = ss.get_session(r["chat_id"]) or {}
check("titled 'Từ Claude: <title>'", row.get("title") == "Từ Claude: Việc tuần 45", row.get("title"))
check("it is a main-chat conversation (web)", row.get("channel") == "web", row.get("channel"))
check("it belongs to the given brain", row.get("brain") == BRAIN, (row.get("brain"), BRAIN))
res = run(G.chat_result(r["chat_id"], BRAIN, r["after_id"], 10))
check("the new conversation gets its answer", res.get("status") == "done" and "danh sách việc" in res.get("answer", ""), res)
msgs = ss.get_messages(r["chat_id"])
check("the owner message is stored with the source block", msgs and msgs[0]["role"] == "user"
      and G.source_of(msgs[0]["content"]) == "Claude", msgs[:1])
check("the open tab is told (external_message)", any(e.get("type") == "external_message"
                                                      and e.get("session_id") == r["chat_id"] for e in EVENTS))
r2 = run(G.send_chat("", BRAIN, "Tóm tắt giúp anh cuộc họp nhà cung cấp hôm nay, ba ý chính thôi nhé", "chatgpt"))
row2 = ss.get_session(r2["chat_id"]) or {}
check("no title: taken from the message, cut at 60 characters",
      row2.get("title", "").startswith("Từ ChatGPT: Tóm tắt giúp anh") and row2.get("title", "").endswith("..."),
      row2.get("title"))
run(G.chat_result(r2["chat_id"], BRAIN, r2["after_id"], 10))
check("an existing id is used as before (created False)",
      run(G.send_chat(WEB, BRAIN, "Thêm một ý nữa.", "ChatGPT")).get("created") is False)
run(G.chat_result(WEB, BRAIN, 0, 10))

# ============================================================
# 2. A refused new chat leaves nothing behind
# ============================================================
n_mid = len(ss.list_sessions(limit=500, brain=[BRAIN], channel="*"))
check("no id + empty message: refused", refused(G.send_chat("", BRAIN, "   ", "ChatGPT")) != "")
check("no id + too long: refused", refused(G.send_chat("", BRAIN, "a" * (G.SEND_CHARS + 1), "ChatGPT")) != "")
check("no id + no brain: refused", refused(G.send_chat("", "", "x", "ChatGPT")) != "")
check("refused new chats create no conversation", len(ss.list_sessions(limit=500, brain=[BRAIN], channel="*")) == n_mid)
check("only the two new chats were added", n_mid == n_before + 2, (n_before, n_mid))

# ============================================================
# 3. The brain list for the pack's picker
# ============================================================
base = Path(main.BRAINS_DIR)
if base.resolve() != Path(_BRAINS).resolve():
    print(f"FAIL BRAINS_DIR is not the temp folder: {base}. STOP so nothing is written into a real brains folder.")
    sys.exit(1)
(base / "Bonao_Test").mkdir(parents=True, exist_ok=True)
(base / ".hidden").mkdir(parents=True, exist_ok=True)
lst = G.list_brains()
names = [b["name"] for b in lst]
check("list_brains lists the brain folders", "Bonao_Test" in names, names)
check("list_brains skips hidden folders", ".hidden" not in names, names)
check("each entry has name, label, path, default", all({"name", "label", "path", "default"} <= set(b) for b in lst), lst[:2])
check("exactly one default brain at most", sum(1 for b in lst if b["default"]) <= 1, lst)
check("paths point at real folders", all(Path(b["path"]).is_dir() for b in lst))

print()
if _fails:
    print(f"FAIL {len(_fails)}: {_fails}")
    sys.exit(1)
print("OK - test_gate_new_chat_0447: all pass")
