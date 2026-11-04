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
Full. Sending into a conversation is the second step of the gate and is not here.

Never use the em dash character in this file.
"""
from __future__ import annotations

import sys
import time
from typing import Any, Optional

OWNER_CHANNELS = ("", "web", "telegram", "zalo", "cli")
OWNER_PREFIXES = ("agent:",)
MSG_CHARS = 4000          # one message as read by the outside AI
NOTE_CHARS = 20000        # a recorded note
TITLE_CHARS = 120
SOURCES = ("ChatGPT", "Claude")


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
