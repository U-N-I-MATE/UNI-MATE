"""0.446.0: the outside AI gate sends into the owner's MAIN chat, and a mistyped /ext/ address answers 404.

    python tests/run.py gate_send_chat_0446      (NO network)

Owner, 04/11/2026: ChatGPT or Claude.ai may post a message into a UNI MATE conversation as if the owner typed it, only
at the Full level (the pack checks the level), only in the main chat (partner chats stay read-only for now), never in a
customer, group or Team conversation. This file runs the REAL web chat loop (`main._chat_socket`) with a fake API engine
(the provider's HTTP is simulated) and locks:

1. A gate message runs as a normal turn: stored with the source block, answered, logged for self-learning, and the
   open tab gets `external_message` before the answer streams.
2. A chat already answering takes it as a message typed meanwhile (steer), and both get an answer.
3. Only the main chat takes messages; everything else is refused with one message, nothing is stored.
4. A path under /ext/ whose extension does not exist answers 404 before the sign-in wall (owner's Claude.ai connector
   was saved as ".../unimate-trong-chagpt/mcp", and the 401 there led the client into a reconnect loop).
"""
from _paths import ROOT, SERVER  # noqa: E402,F401
import asyncio
import json
import os
import sys
import tempfile
from pathlib import Path

os.environ["UNIMATE_API_STREAM_TOOLS"] = "0"
_STATE = tempfile.mkdtemp(prefix="unimate-0446-")
os.environ["UNIMATE_STATE_DIR"] = _STATE
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
# 1. A gate message runs as a normal turn of the main chat
# ============================================================
EVENTS.clear()
r = run(G.send_chat(WEB, BRAIN, "Anh đã duyệt màu cam. Làm tiếp trang giỏ hàng.", "chatgpt"))
check("send into the main chat: the turn starts", r.get("mode") == "started" and r.get("chat_id") == WEB, r)
res = run(G.chat_result(WEB, BRAIN, r["after_id"], 10))
check("result: UNI MATE answered this very message", res.get("status") == "done"
      and "trang giỏ hàng" in res.get("answer", ""), res)
msgs = ss.get_messages(WEB)
owner_text = [m for m in msgs if m["role"] == "user"][-1]["content"]
check("stored with the source block in front", owner_text.startswith(G.BLOCK_PREFIX + " ChatGPT."), owner_text[:120])
check("source_of reads the source back", G.source_of(owner_text) == "ChatGPT")
check("a message the owner typed has no source", G.source_of("Làm trang web bán nước mắm giúp anh") == "")
check("the answer is stored", msgs[-1]["role"] == "assistant" and "DONE" in msgs[-1]["content"])
check("the turn is logged for self-learning", any("trang giỏ hàng" in u for u, _ in LOG), LOG[-1:])
ext = [e for e in EVENTS if e.get("type") == "external_message"]
first_text = next((i for i, e in enumerate(EVENTS) if e.get("type") in ("stream", "response")), len(EVENTS))
check("the open tab gets external_message with the source, before the answer streams",
      ext and ext[0]["session_id"] == WEB and ext[0]["source"] == "ChatGPT" and EVENTS.index(ext[0]) < first_text,
      [e.get("type") for e in EVENTS][:8])
check("the open tab sees the turn finish", any(e.get("type") == "turn_done" and e.get("session_id") == WEB
                                               for e in EVENTS), sorted({str(e.get("type")) for e in EVENTS}))
check("an old main-chat row (empty channel) takes messages too",
      run(G.send_chat(OLD, BRAIN, "Tóm tắt lại giúp anh.", "Claude")).get("mode") == "started")
run(G.chat_result(OLD, BRAIN, 0, 10))

# ============================================================
# 2. A chat already answering takes it as a message typed meanwhile
# ============================================================
DELAY["s"] = 0.6


async def _two():
    r1 = await G.send_chat(WEB, BRAIN, "Việc A: viết mô tả sản phẩm.", "Claude")
    await asyncio.sleep(0.1)
    r2 = await G.send_chat(WEB, BRAIN, "Việc B: thêm nút đặt hàng.", "Claude")
    out = await G.chat_result(WEB, BRAIN, r1["after_id"], 20)
    return r1, r2, out
r1, r2, out = run(_two())
check("second message while answering: taken as a message typed meanwhile",
      r1.get("mode") == "started" and r2.get("mode") == "queued", (r1, r2))
check("waiting through the follow-up turn: both got an answer", out.get("status") == "done"
      and "Việc B" in out.get("answer", ""), out)
DELAY["s"] = 0.02

# A result asked with no wait while a turn runs says "running" and what is written so far.
DELAY["s"] = 0.8
r3 = run(G.send_chat(WEB, BRAIN, "Việc C: kiểm tra chính tả.", "ChatGPT"))
mid = run(G.chat_result(WEB, BRAIN, r3["after_id"], 0))
check("result with no wait during the turn: status running", mid.get("status") == "running", mid)
check("later result: done", run(G.chat_result(WEB, BRAIN, r3["after_id"], 10)).get("status") == "done")
DELAY["s"] = 0.02

# ============================================================
# 3. Only the main chat takes messages
# ============================================================
before = {s: len(ss.get_messages(s)) for s in (AGENT, TG, BOT, TEAM, ELSEWHERE)}
check("partner chat: read-only, refused", "Trò chuyện chính" in refused(G.send_chat(AGENT, BRAIN, "x", "ChatGPT")))
check("Telegram talk: refused", refused(G.send_chat(TG, BRAIN, "x", "ChatGPT")) != "")
check("customer chat: refused like a missing one", "Không có hội thoại này" in refused(G.send_chat(BOT, BRAIN, "x", "ChatGPT")))
check("Team chat: refused", "Không có hội thoại này" in refused(G.send_chat(TEAM, BRAIN, "x", "ChatGPT")))
check("a chat of another brain: refused", "Không có hội thoại này" in refused(G.send_chat(ELSEWHERE, BRAIN, "x", "ChatGPT")))
check("a missing chat: refused", refused(G.send_chat("no-such-id", BRAIN, "x", "ChatGPT")) != "")
check("empty message: refused", refused(G.send_chat(WEB, BRAIN, "   ", "ChatGPT")) != "")
check("too long: refused", refused(G.send_chat(WEB, BRAIN, "a" * (G.SEND_CHARS + 1), "ChatGPT")) != "")
check("refused sends store nothing", before == {s: len(ss.get_messages(s)) for s in before})
check("result of a customer chat: refused", refused(G.chat_result(BOT, BRAIN, 0, 0)) != "")
check("can_send: main chat only", G.can_send("web") and G.can_send("") and not G.can_send("agent:x")
      and not G.can_send("telegram") and not G.can_send("bot:x") and not G.can_send("team:x"))
check("source names normalise to ChatGPT or Claude", G.source_name("CLAUDE") == "Claude"
      and G.source_name("Evil] [x") == "ChatGPT")

# ============================================================
# 4. A mistyped /ext/ address answers 404 before the sign-in wall
# ============================================================
from fastapi.testclient import TestClient  # noqa: E402


class _Lp:
    slug = "demo-gate"
    http = [{"path": "mcp", "methods": ("POST",), "public": True, "no_cookie": True, "handler": None},
            {"path": "", "methods": ("GET",), "public": False, "no_cookie": False, "handler": None}]
    well_known = {}


_real_plugin_http = plugins_host._plugin_http
plugins_host._plugin_http = lambda: [_Lp()]
main.cfgmod.gate_active = lambda: True
try:
    cl = TestClient(main.app)
    r = cl.post("/ext/demo-gat/mcp", json={})
    check("mistyped extension name: 404, not the sign-in wall", r.status_code == 404, (r.status_code, r.text))
    check("the 404 says there is no such extension", "not_found" in r.text)
    r = cl.post("/ext/Bad Slug!/mcp", json={})
    check("an invalid extension name: 404 too", r.status_code == 404, r.status_code)
    r = cl.get("/ext/demo-gate/")
    check("a real extension's private page still asks to sign in (401)", r.status_code == 401, (r.status_code, r.text))
    r = cl.get("/sessions")
    check("core pages still ask to sign in (401)", r.status_code == 401, r.status_code)
    check("http_slug_known: real name yes, typo no", plugins_host.http_slug_known("/ext/demo-gate/mcp")
          and not plugins_host.http_slug_known("/ext/demo-gat/mcp"))


    def _boom():
        raise RuntimeError("plugin load failed")
    plugins_host._plugin_http = _boom
    check("on doubt (plugin list fails) the wall behaves as before",
          plugins_host.http_slug_known("/ext/anything/mcp") is True)
finally:
    plugins_host._plugin_http = _real_plugin_http
    main.cfgmod.gate_active = lambda: False

print()
if _fails:
    print(f"FAIL {len(_fails)}: {_fails}")
    sys.exit(1)
print("OK - test_gate_send_chat_0446: all pass")
