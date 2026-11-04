"""A small, stable surface for an outside AI gate (store pack `unimate.unimate-trong-chatgpt`), 0.441.0.

Why a module of its own. The pack lets ChatGPT or Claude.ai call UNI MATE's tools through OAuth + MCP. Owner's
decision 03/11/2026 (idea from Javis OS 0.440-0.441, written fresh): the outside AI may also read the owner's
conversations and record what was decided over there as a conversation of its own here. A pack must not reach into
`main.py` privates (they move between releases), so this file is the contract: plain functions, owner chats only,
nothing that runs a model.

Which conversations. Only the owner's own chats: the dashboard (`web`, or empty on old rows), Telegram, Zalo and CLI
talks with UNI MATE, and chats with a partner agent (`agent:`). Never a customer conversation (`bot:`, the chatbot
inbox lives in another store anyway), a Team chat (`team:`, `teammate:`), nor internal runs (`workflow:`, `coding:`).

Levels are the pack's job (it knows the level the owner chose): reading needs any level, `record_note` needs Draft or
Full, `send_chat` needs Full.

Sending (0.446.0, owner's decision 04/11/2026). `send_chat` puts a message into ONE conversation as if the owner typed
it: it runs through the web chat loop (`main._chat_socket`) over an in-process stand-in connection, so the turn streams
to every open tab, has a Stop button, is saved and learned from like any turn. A conversation already answering gets it
as a message typed meanwhile (steer). Only the main chat (`web`, or empty on old rows) takes messages: partner-agent
chats stay read-only for now, Telegram/Zalo/CLI talks answer on their own channel, and customer, group and Team
conversations are never reachable at all. `chat_result` waits a bounded time and returns what UNI MATE wrote.

Never use the em dash character in this file.
"""
from __future__ import annotations

import asyncio
import json
import re
import sys
import time
from typing import Any, List, Optional

OWNER_CHANNELS = ("", "web", "telegram", "zalo", "cli")
OWNER_PREFIXES = ("agent:",)
MSG_CHARS = 4000          # one message as read by the outside AI
NOTE_CHARS = 20000        # a recorded note
TITLE_CHARS = 120
SOURCES = ("ChatGPT", "Claude")
SEND_CHANNELS = ("", "web")   # only the main chat takes messages from outside (owner, 04/11/2026)
SEND_CHARS = 7000             # steer_inbox.MAX_CHARS is 8000; room for the source block
RESULT_CHARS = 14000          # all the answer text returned in one call
WAIT_DEFAULT = 25             # seconds; an MCP client does not wait long on one call
WAIT_MAX = 50
# The block every gate message starts with. The dashboard strips it (app.js `_KHOI_NGU_CANH`) and shows "from <source>";
# the model reads it as the source of the message. Prompt text, so it stays Vietnamese.
BLOCK_PREFIX = "[GỬI QUA CỔNG UNI MATE:"
_BLOCK_SOURCE = re.compile(r"^\s*\[GỬI QUA CỔNG UNI MATE: ([^.\]\n]{1,40})")


class GateError(ValueError):
    """A request the gate refuses; the message is safe to show the outside AI."""


def _main():
    m = sys.modules.get("main")
    if m is None:
        import main as m  # noqa: F811 - only outside the running server (tests)
    return m


def is_owner_channel(channel: Any) -> bool:
    ch = str(channel or "")
    return ch in OWNER_CHANNELS or ch.startswith(OWNER_PREFIXES)


def _brain_match(row: dict, brain: str) -> bool:
    if not brain:
        return True
    return str(row.get("brain") or "") in set(_main()._brain_keys(brain))


def list_chats(brain: str, limit: int = 20, query: str = "") -> list:
    """The owner's most recent conversations in `brain`, newest first: id, title, channel, updated_at, messages."""
    from sessions import get_store
    limit = max(1, min(int(limit or 20), 50))
    q = str(query or "").strip().casefold()
    rows = get_store().list_sessions(limit=200, brain=_main()._brain_keys(brain) if brain else None, channel="*")
    out = []
    for r in rows:
        if not is_owner_channel(r.get("channel")):
            continue
        title = str(r.get("title") or "")
        if q and q not in title.casefold() and q not in str(r.get("preview") or "").casefold():
            continue
        out.append({"id": r["id"], "title": title, "channel": r.get("channel") or "web",
                    "updated_at": r.get("updated_at"), "messages": int(r.get("msg_count") or 0)})
        if len(out) >= limit:
            break
    return out


def read_chat(session_id: str, brain: str, limit: int = 30) -> dict:
    """The last `limit` messages (oldest first) of one owner conversation in `brain`."""
    from sessions import get_store
    store = get_store()
    row = store.get_session(str(session_id or "")) if session_id else None
    if not row or not is_owner_channel(row.get("channel")) or not _brain_match(row, brain):
        # One answer for "missing", "not yours" and "other brain": the gate never tells which ids exist.
        raise GateError("Không có hội thoại này trong brain đang mở, hoặc đây không phải hội thoại của chủ.")
    page = store.get_messages_page(row["id"], limit=max(1, min(int(limit or 30), 100)))
    msgs = [{"id": m.get("id"), "role": m.get("role"), "ts": m.get("ts"),
             "content": str(m.get("content") or "")[:MSG_CHARS]} for m in page.get("messages") or []]
    return {"id": row["id"], "title": row.get("title") or "", "channel": row.get("channel") or "web",
            "messages": msgs, "has_more": bool(page.get("has_more"))}


async def record_note(brain: str, source: str, title: str, note: str, asked: str = "") -> dict:
    """Record what the owner settled in ChatGPT/Claude as a conversation of its own, "Từ <source>: <title>".

    No model runs (no plan allowance spent). It is saved through the same step as a normal turn (`_persist_turn`), so it
    reaches the chat history, the brain's conversation log and the self-learning queue like any chat."""
    src = next((s for s in SOURCES if s.casefold() == str(source or "").strip().casefold()), SOURCES[0])
    title = " ".join(str(title or "").split())[:TITLE_CHARS]
    note = str(note or "").strip()[:NOTE_CHARS]
    if not title or not note:
        raise GateError("Cần cả tiêu đề (title) và nội dung đã chốt (note).")
    m = _main()
    from sessions import get_store
    store = get_store()
    full_title = f"Từ {src}: {title}"
    sid = store.create_session(brain=m._brain_key(brain), title=full_title, channel="web")
    asked = str(asked or "").strip()[:NOTE_CHARS]
    user_text = asked or f"(Ghi lại từ {src}) {title}"
    started = time.time()
    store.append_message(sid, "user", user_text)
    mid = await m._persist_turn(store, sid, brain, user_text, note, turn_started=started)
    return {"session_id": sid, "title": full_title, "message_id": mid}


# ---------------------------------------------------------------- sending (0.446.0)

def can_send(channel: Any) -> bool:
    return str(channel or "") in SEND_CHANNELS


def source_name(source: Any) -> str:
    """The pack's source name, normalised to one of SOURCES (it comes from the client's redirect address)."""
    return next((s for s in SOURCES if s.casefold() == str(source or "").strip().casefold()), SOURCES[0])


def block(source: Any) -> str:
    n = source_name(source)
    return (f"{BLOCK_PREFIX} {n}. Chủ trao đổi với {n} rồi nhờ {n} gửi tin này vào hội thoại. "
            f"Làm như chủ vừa gõ và trả lời ngay tại đây.]\n\n")


def source_of(content: Any) -> str:
    """The source name when a stored message came through the gate, else empty."""
    m = _BLOCK_SOURCE.match(str(content or ""))
    return m.group(1).strip() if m else ""


def _owner_row(session_id: str, brain: str) -> dict:
    from sessions import get_store
    row = get_store().get_session(str(session_id or "")) if session_id else None
    if not row or not is_owner_channel(row.get("channel")) or not _brain_match(row, brain):
        raise GateError("Không có hội thoại này trong brain đang mở, hoặc đây không phải hội thoại của chủ.")
    return row


def _running(session_id: str) -> bool:
    try:
        return _main()._CHAT_RUNTIME.get_job(session_id) is not None
    except Exception:
        return False


def _last_id(store, session_id: str) -> int:
    return max((int(m.get("id") or 0) for m in store.get_messages(session_id)), default=0)


class _StandInSocket:
    """An in-process stand-in for the browser socket: hands `_chat_socket` ONE frame, then disconnects.

    Disconnecting at once is intended: the chat loop treats a socket as a viewer only, the turn lives in `_CHAT_RUNTIME`
    and runs to the end. `received` keeps what the server sent while connected, to catch a refusal on the spot."""

    def __init__(self, frame: dict):
        self._frames = [json.dumps(frame, ensure_ascii=False)]
        self.received: List[dict] = []
        self.cookies: dict = {}

    async def accept(self):
        return None

    async def receive_text(self):
        if self._frames:
            return self._frames.pop(0)
        from starlette.websockets import WebSocketDisconnect
        raise WebSocketDisconnect()

    async def send_text(self, text):
        try:
            self.received.append(json.loads(text))
        except Exception:
            pass

    async def close(self, code: int = 1000):
        return None


async def send_chat(session_id: str, brain: str, text: str, source: str) -> dict:
    """Put `text` into the owner's main-chat conversation `session_id` as if the owner typed it.

    Returns {"chat_id", "title", "mode": "started"|"queued", "after_id"}; `after_id` is the last message id before this
    one, for `chat_result`. Raises GateError for anything the gate refuses."""
    m = _main()
    from sessions import get_store
    store = get_store()
    row = _owner_row(session_id, brain)
    if not can_send(row.get("channel")):
        raise GateError("Chỉ gửi được vào hội thoại ở khung Trò chuyện chính. Hội thoại với Cộng sự, Telegram, Zalo, "
                        "dòng lệnh thì chỉ đọc.")
    text = str(text or "").strip()
    if not text:
        raise GateError("Tin nhắn trống.")
    if len(text) > SEND_CHARS:
        raise GateError(f"Tin quá dài ({len(text)} ký tự, tối đa {SEND_CHARS}).")
    sid = row["id"]
    content = block(source) + text
    before = _last_id(store, sid)
    busy = _running(sid)
    if busy:
        frame = {"action": "steer", "session_id": sid, "message": content, "client_id": "gate"}
    else:
        frame = {"message": content, "brain": row.get("brain") or "brain", "session_id": sid}
    # Tell the open tabs first: a tab showing this chat draws the bubble (with its source label) before the answer
    # starts streaming.
    try:
        await m._CHAT_RUNTIME.publish({"type": "external_message", "session_id": sid, "content": content,
                                       "source": source_name(source)})
    except Exception:
        pass
    sock = _StandInSocket(frame)
    await m._chat_socket(sock)
    refused = next((e for e in sock.received if e.get("type") == "error" and e.get("session_id") == sid), None)
    if refused:
        raise GateError(str(refused.get("content") or "UNI MATE từ chối tin này."))
    if not busy and not _running(sid) and _last_id(store, sid) <= before:
        raise GateError("UNI MATE chưa nhận tin này. Thử lại sau ít phút.")
    return {"chat_id": sid, "title": row.get("title") or "", "mode": "queued" if busy else "started",
            "after_id": before}


def _clip(s: str, n: int) -> str:
    s = str(s or "")
    return s if len(s) <= n else s[:n] + "\n...(cắt bớt)"


async def chat_result(session_id: str, brain: str, after_id: int = 0, wait: Any = WAIT_DEFAULT) -> dict:
    """Wait up to `wait` seconds for the turn to finish, then return what UNI MATE wrote after message `after_id`.

    status: "done" (answer), "running" (answer so far + what is being written now; call again with the same after_id),
    "no_answer" (the turn ended without a reply: stopped or failed)."""
    from sessions import get_store
    store = get_store()
    row = _owner_row(session_id, brain)
    sid = row["id"]
    try:
        wait = float(wait if wait is not None else WAIT_DEFAULT)
    except (TypeError, ValueError):
        wait = WAIT_DEFAULT
    deadline = time.monotonic() + max(0.0, min(wait, WAIT_MAX))
    while True:
        running = _running(sid)
        if running and time.monotonic() < deadline:
            await asyncio.sleep(0.5)
            continue
        if not running:
            # A message typed meanwhile runs as its OWN turn right after the current one, a short beat later. Look
            # once more so "done" is never reported between the two turns.
            await asyncio.sleep(1.0)
            running = _running(sid)
            if running and time.monotonic() < deadline:
                continue
        break
    try:
        after_id = int(after_id or 0)
    except (TypeError, ValueError):
        after_id = 0
    parts = [str(x.get("content") or "").strip() for x in store.get_messages(sid)
             if x.get("role") == "assistant" and int(x.get("id") or 0) > after_id]
    answer = _clip("\n\n".join(p for p in parts if p), RESULT_CHARS)
    if running:
        job = _main()._CHAT_RUNTIME.get_job(sid)
        now_text = _clip(str(getattr(job, "text", "") or "")[-3000:], 3000)
        return {"status": "running", "answer_so_far": answer, "writing_now": now_text,
                "hint": "UNI MATE vẫn đang làm. Gọi lại với cùng after_id để lấy tiếp."}
    if not answer:
        return {"status": "no_answer",
                "hint": "Lượt đã kết thúc mà không có câu trả lời (bị dừng hoặc lỗi). Đọc lại hội thoại để xem."}
    return {"status": "done", "answer": answer}
