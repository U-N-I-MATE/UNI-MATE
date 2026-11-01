"""0.206.0: send more while UNI MATE is working.

Covers: the inbox (nothing held when no turn runs, held while one runs, read once, leftovers returned at the end, the
read callback, the pending cap), the API engines' tool loop reading a message sent while a tool was running (a fake
OpenAI-compatible endpoint: the second request carries the note in the last tool result), the Claude Code PostToolUse
hook (main thread only), the one-shot engines marked as "after", and the main.py wiring.

Run:
    python tests/run.py steer
"""
from _paths import ROOT, SERVER  # noqa: E402,F401
import asyncio
import os
import tempfile

os.environ["UNIMATE_STATE_DIR"] = tempfile.mkdtemp(prefix="unimate-steer-")

import steer_inbox as si  # noqa: E402

fails = []


def check(name, cond):
    print(("ok   " if cond else "FAIL ") + name)
    if not cond:
        fails.append(name)


_b = si.SteerInbox()
_b.open("st", "tag", bind=False)
check("bind=False leaves the context unbound", si.current_sid() == "")
_b.put("st", "dừng và báo")
_g = _b.stop_gen("st")
check("Stop returns what waited and moves the generation",
      [i["text"] for i in _b.stop("st")] == ["dừng và báo"] and _b.stop_gen("st") == _g + 1)
check("nothing is left to run after Stop", _b.close("st", "tag") == [])
_src = open(os.path.join(str(SERVER), "main.py"), encoding="utf8").read()
check("both workflow generators cancel the run when closed", _src.count("await asyncio.wait({task}, timeout=15)") == 2)
check("a waiting follow-up turn checks Stop", "stop_gen(conv_sid) != _gen" in _src)
# "Send now" (Gửi ngay): the server cuts the turn only when a message really waits, and the leftovers of that cut
# turn open the next one with triage_prompt; a mark with nothing left ends with the turn.
_n = si.SteerInbox()
_n.open("sn", "tn")
check("nothing waits before a message is sent", not _n.waiting("sn"))
_n.put("sn", "đổi hướng")
check("a held message waits", _n.waiting("sn"))
_n.mark_now("sn")
check("Send now leftovers keep the mark for the next turn", len(_n.close("sn", "tn")) == 1 and _n.pop_now("sn") and not _n.pop_now("sn"))
_n.open("sn", "tn2"); _n.mark_now("sn")
check("a mark with nothing left ends with the turn", _n.close("sn", "tn2") == [] and not _n.pop_now("sn"))
check("triage prompt asks to read the message first", "Gửi ngay" in si.triage_prompt(["x"]) and "<<<\nx\n>>>" in si.triage_prompt(["x"]))
check("websocket action steer_now cuts the turn only when a message waits",
      'if action == "steer_now":' in _src and "steer_inbox.INBOX.waiting(_sid)" in _src
      and '"type": "steer_now_ack"' in _src)
check("the next turn after Send now opens with triage_prompt",
      "steer_inbox.triage_prompt if now else steer_inbox.followup_prompt" in _src
      and _src.count("now=steer_inbox.INBOX.pop_now(conv_sid)") == 2)
check("Stop (button and HTTP) drops what waited", _src.count("steer_inbox.INBOX.stop(") == 2)

box = si.SteerInbox()
reads = []
box.on_read = lambda sid, ids: reads.append((sid, ids))
check("nothing is held when no turn runs", box.put("s1", "thêm cái này") is None)
tok = box.open("s1", "chat:s1:aaa")
check("a running turn can take input by default", box.running("s1") and box.live("s1"))
a = box.put("s1", "  làm thêm bản tiếng Anh  ")
b = box.put("s1", "và gửi cho chị Lan")
check("messages held, trimmed, numbered", a["text"] == "làm thêm bản tiếng Anh" and b["id"] > a["id"])
note = box.take_note_for_tag("chat:s1:aaa")
check("the turn reads both at once, in order", note.index("làm thêm bản tiếng Anh") < note.index("chị Lan")
      and "2 tin" in note and note.count("<<<") == 2)
check("read callback names the messages", reads == [("s1", [a["id"], b["id"]])])
check("read once", box.take_note_for_tag("chat:s1:aaa") == "")
box.put("s1", "câu cuối")
box.set_live("s1", False)
check("an engine can say it cannot read mid-way", not box.live("s1") and box.running("s1"))
left = box.close("s1", "chat:s1:aaa", tok)
check("leftovers come back at the end", [x["text"] for x in left] == ["câu cuối"] and not box.running("s1"))
check("after the end nothing is held", box.put("s1", "x") is None)
box.open("s2")
for i in range(si.MAX_PENDING):
    box.put("s2", f"tin {i}")
check("the pending cap holds", box.put("s2", "một tin nữa") is None)
box.close("s2")
check("empty text refused", box.put("s3", "   ") is None)
check("follow-up prompt keeps the owner's words", "gửi báo giá" in si.followup_prompt(["gửi báo giá"])
      and "2 tin" in si.followup_prompt(["a", "b"]))

# ---- the API engines' tool loop reads a message sent while a tool ran ----
import engine  # noqa: E402
import mcp_client  # noqa: E402

requests = []


class _Resp:
    def __init__(self, data):
        self._d = data
        self.status_code = 200
        self.text = ""

    def json(self):
        return self._d

    def raise_for_status(self):
        return None


class _Client:
    def __init__(self, *a, **k):
        pass

    async def __aenter__(self):
        return self

    async def __aexit__(self, *a):
        return False

    async def post(self, url, headers=None, json=None):
        requests.append(json)
        if len(requests) == 1:
            return _Resp({"choices": [{"message": {"role": "assistant", "content": None, "tool_calls": [
                {"id": "c1", "type": "function", "function": {"name": "doc_so", "arguments": "{}"}}]}}]})
        return _Resp({"choices": [{"message": {"role": "assistant", "content": "Xong cả hai việc."}}]})


async def _call_route(route, name, args):
    # the owner types while this tool is running
    si.INBOX.put("web1", "nhân tiện tóm tắt luôn cho anh")
    return "kết quả công cụ"

engine.httpx.AsyncClient = _Client
mcp_client.call_route = _call_route
tools = [{"fn": "doc_so", "description": "đọc số", "schema": {"type": "object", "properties": {}}}]


async def run_loop():
    tok = si.INBOX.open("web1", "chat:web1:x")
    out = []
    try:
        async for ev in engine._cc_tool_loop("http://x", {}, "m", [{"role": "user", "content": "đọc số giúp anh"}],
                                             tools, "route", {}, "test"):
            out.append(ev)
    finally:
        left = si.INBOX.close("web1", "chat:web1:x", tok)
    return out, left

out, left = asyncio.run(run_loop())
tool_msgs = [m for m in (requests[1]["messages"] if len(requests) > 1 else []) if m.get("role") == "tool"]
check("the next round carries the note in the last tool result",
      len(requests) == 2 and tool_msgs and "nhân tiện tóm tắt luôn cho anh" in tool_msgs[-1]["content"]
      and tool_msgs[-1]["content"].startswith("kết quả công cụ"))
check("a message read mid-turn is not run again after it", left == [])
check("the turn still finishes normally", any(e.get("type") == "text" and "Xong" in e.get("content", "") for e in out))
check("outside a chat turn the loop reads nothing", si.INBOX.take_note_current() == "")

# ---- Claude Code: the PostToolUse hook ----
import claude_sdk_engine as cse  # noqa: E402

eng = cse.ClaudeSDK.__new__(cse.ClaudeSDK)
eng.tag = "chat:web2:y"


async def hook_checks():
    si.INBOX.open("web2", "chat:web2:y")
    si.INBOX.put("web2", "đổi sang giọng thân mật")
    sub = await eng._steer_hook({"hook_event_name": "PostToolUse", "agent_id": "a1"}, "t1", None)
    main_ = await eng._steer_hook({"hook_event_name": "PostToolUse"}, "t2", None)
    empty = await eng._steer_hook({"hook_event_name": "PostToolUse"}, "t3", None)
    si.INBOX.close("web2", "chat:web2:y")
    return sub, main_, empty

sub, main_, empty = asyncio.run(hook_checks())
check("a sub-agent's tool call is left alone", sub == {})
check("the main thread gets the note as additional context",
      main_.get("hookSpecificOutput", {}).get("additionalContext", "").find("giọng thân mật") >= 0
      and main_["hookSpecificOutput"]["hookEventName"] == "PostToolUse")
check("nothing pending, nothing added", empty == {})
src_sdk = (SERVER / "claude_sdk_engine.py").read_text(encoding="utf-8")
# 0.213.0 moved the tag test into _steer_on (chat turns, plus channel turns whose gateway opened an inbox).
check("the hook is attached for chat turns only", 'if tag.startswith("chat:"):' in src_sdk
      and 'if "hooks" in fields and self._steer_on():' in src_sdk
      and '"PostToolUse": [HookMatcher(matcher=None, hooks=[self._steer_hook])]' in src_sdk)

# ---- main.py wiring ----
src = (SERVER / "main.py").read_text(encoding="utf-8")
check("websocket action steer stores the message and answers with steer_ack",
      'if action == "steer":' in src and '"type": "steer_ack"' in src)
check("every chat turn opens and closes the inbox", "_steer_tok = steer_inbox.INBOX.open(conv_sid, turn_tag)" in src
      and "_steer_left = steer_inbox.INBOX.close(conv_sid, turn_tag, _steer_tok)" in src)
check("leftovers run as the next turn", "asyncio.create_task(_start_steer_turn(conv_sid, [i[\"text\"] for i in _steer_left]" in src)
check("one-shot engines (Grok, Antigravity, Codex, the one-call path) and workflow runs say after",
      src.count("steer_inbox.INBOX.set_live(conv_sid, False)") == 5)
check("three API loops read pending messages",
      (SERVER / "engine.py").read_text(encoding="utf-8").count("steer_inbox.INBOX.take_note_current()") == 3)
for f in ("steer_inbox.py",):
    check(f"no long dashes in {f}", not any(c in (SERVER / f).read_text(encoding="utf-8") for c in "–—"))

print()
print("FAIL" if fails else "PASS", f"({len(fails)} failed)")
raise SystemExit(1 if fails else 0)
