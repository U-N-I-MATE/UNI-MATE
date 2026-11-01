"""Send more while UNI MATE is working (0.206.0).

Before this, a message typed while a turn was running was silently dropped by the dashboard (and refused by the
server). Claude Code folds a message sent mid-turn into the work at its next step; Codex calls it "steer" (Enter) and
also has "queue" (Tab, runs after). UNI MATE does both, whatever brain is in use:

- A turn that can take input mid-way (Claude Code: after each tool call, through a PostToolUse hook; the API engines:
  before the next model round, appended to the last tool result) reads the pending messages at its next step.
- Anything not read by the end of the turn (a one-shot CLI engine, or the turn was already writing its final answer)
  runs as the next turn of the same chat, right after this one ends. Nothing is lost.

The owner's message is stored as a normal user message when it arrives; this module only holds it until a turn reads
it. In memory only: a restart loses pending notes, but their user messages are already in the chat history.
"""
from __future__ import annotations

import contextvars
import itertools
import threading
import time
from typing import Callable, Dict, List, Optional

MAX_PENDING = 10
MAX_CHARS = 8000

_CURRENT: contextvars.ContextVar[str] = contextvars.ContextVar("unimate_steer_sid", default="")


def note_for(texts: List[str]) -> str:
    """The text a running turn reads: the owner's own words, fenced, and what to do with them. Model prompt: Vietnamese."""
    if not texts:
        return ""
    body = "\n\n".join(f"<<<\n{t}\n>>>" for t in texts)
    return ("\n\n[UNI MATE] Người dùng vừa gửi thêm "
            + ("một tin" if len(texts) == 1 else f"{len(texts)} tin")
            + " trong lúc bạn đang làm. Đây là lời của chính họ:\n" + body + "\n"
            "Nếu đó là sửa hướng hay bổ sung cho việc đang làm, áp dụng ngay từ bước kế tiếp. Nếu là một việc mới, "
            "độc lập, hãy nhận luôn: làm song song (giao việc nền hoặc sub-agent nếu có) hoặc làm ngay sau phần đang dở, "
            "rồi trả lời cả hai trong câu trả lời cuối. Đừng bỏ qua tin này.\n")


def followup_prompt(texts: List[str]) -> str:
    """The message of the turn that runs the leftovers after a turn ended. Model prompt: Vietnamese."""
    body = "\n\n".join(texts)
    if len(texts) == 1:
        return ("[UNI MATE] Tin dưới đây người dùng gửi trong lúc lượt trước còn đang chạy; lượt trước đã xong. "
                "Giờ làm theo tin này:\n\n" + body)
    return (f"[UNI MATE] {len(texts)} tin dưới đây người dùng gửi trong lúc lượt trước còn đang chạy; lượt trước đã xong. "
            "Giờ làm theo các tin này, theo đúng thứ tự:\n\n" + body)


def triage_prompt(texts: List[str]) -> str:
    """The turn after the owner pressed "Send now": the running turn was cut, read the message before anything else.
    Model prompt: Vietnamese."""
    body = "\n\n".join(f"<<<\n{t}\n>>>" for t in texts)
    return ("[UNI MATE] Người dùng vừa bấm Gửi ngay nên việc đang làm dở đã bị cắt. Đây là lời của chính họ:\n" + body + "\n"
            "Xử lý tin này trước, theo thứ tự:\n"
            "1. Xác định tin nói gì: sửa hướng, bổ sung, câu hỏi hay việc mới độc lập.\n"
            "2. Đối chiếu với việc đang dở: có phải đổi cách làm không, phần đã làm có phải bỏ hoặc sửa không.\n"
            "3. Có chỗ chưa hiểu, hoặc cần họ quyết định mới làm tiếp đúng được: DỪNG tại đây, không gọi thêm tool. "
            "Nói ngắn mình hiểu tin thế nào, việc cũ đã tới đâu, rồi hỏi đúng điều cần xác nhận.\n"
            "4. Đã rõ: nói một câu kết luận rồi làm theo hướng đó, tiếp từ chỗ dở chứ không làm lại từ đầu. "
            "Kiểm tra phần có thể bị cắt giữa chừng (tệp ghi dở, lệnh chưa xong) trước khi làm tiếp.")


class SteerInbox:
    def __init__(self, clock: Callable[[], float] = time.time):
        self._lock = threading.Lock()
        self._pending: Dict[str, List[dict]] = {}
        self._live: Dict[str, bool] = {}
        self._tags: Dict[str, str] = {}
        self._stops: Dict[str, int] = {}
        self._now: set = set()
        self._ids = itertools.count(1)
        self._clock = clock
        self.on_read: Optional[Callable[[str, List[int]], None]] = None
        # Per-turn: where a read message is written into the chat history (0.213.0, chat channels). The web dashboard
        # stores the owner's message when it arrives; a channel turn only knows its stored session once it has started.
        self._sinks: Dict[str, Callable[[List[str]], None]] = {}

    # -- one turn's lifetime --
    def open(self, sid: str, tag: str = "", bind: bool = True) -> Optional[contextvars.Token]:
        """A turn of this chat starts: it can take input mid-way until an engine says otherwise (set_live).
        bind=False: nothing running in this context may read the messages (a workflow's steps are not this chat)."""
        with self._lock:
            self._live[sid] = True
            if tag:
                self._tags[tag] = sid
        return _CURRENT.set(sid) if bind else None

    def set_live(self, sid: str, live: bool) -> None:
        with self._lock:
            if sid in self._live:
                self._live[sid] = bool(live)

    def close(self, sid: str, tag: str = "", token: Optional[contextvars.Token] = None) -> List[dict]:
        """The turn ended: returns what it never read (to run as the next turn) and forgets the turn."""
        with self._lock:
            self._live.pop(sid, None)
            self._sinks.pop(sid, None)
            if tag:
                self._tags.pop(tag, None)
            left = self._pending.pop(sid, [])
            if not left:
                self._now.discard(sid)   # "Send now" with nothing left to hand on: the mark ends with this turn
        if token is not None:
            try:
                _CURRENT.reset(token)
            except ValueError:
                pass
        return left

    def set_sink(self, sid: str, sink: Optional[Callable[[List[str]], None]]) -> None:
        """While the turn of `sid` runs, `sink(texts)` gets every message it reads (0.213.0)."""
        with self._lock:
            if sid in self._live and sink is not None:
                self._sinks[sid] = sink

    def drop(self, sid: str) -> List[dict]:
        """Forget what is waiting for the turn of `sid` without ending it (a /stop on a chat channel)."""
        with self._lock:
            return self._pending.pop(sid, [])

    def stop(self, sid: str) -> List[dict]:
        """The owner pressed Stop: nothing sent earlier may start by itself afterwards. Returns what was waiting and
        moves stop_gen, which a follow-up turn still waiting for this chat checks before it starts."""
        with self._lock:
            self._stops[sid] = self._stops.get(sid, 0) + 1
            return self._pending.pop(sid, [])

    def stop_gen(self, sid: str) -> int:
        with self._lock:
            return self._stops.get(sid, 0)

    def mark_now(self, sid: str) -> None:
        """The owner pressed "Send now": the turn about to be cut hands its leftovers on with triage_prompt."""
        with self._lock:
            self._now.add(sid)

    def pop_now(self, sid: str) -> bool:
        """Was the turn of `sid` cut by "Send now"? Forgets the mark (one turn only)."""
        with self._lock:
            if sid in self._now:
                self._now.discard(sid)
                return True
            return False

    def requeue(self, sid: str, items: List[dict]) -> bool:
        """Put back messages an engine took but could not hand over (Codex refused a steer because its turn had just
        ended): ahead of anything newer, so the next turn runs them in order. False once the turn is over."""
        with self._lock:
            if sid not in self._live or not items:
                return False
            self._pending[sid] = list(items) + self._pending.get(sid, [])
            return True

    def running(self, sid: str) -> bool:
        with self._lock:
            return sid in self._live

    def live(self, sid: str) -> bool:
        with self._lock:
            return bool(self._live.get(sid))

    def waiting(self, sid: str) -> bool:
        """At least one message waits for the running turn of `sid` (what "Send now" acts on)."""
        with self._lock:
            return bool(self._pending.get(sid))

    # -- the owner sends --
    def put(self, sid: str, text: str) -> Optional[dict]:
        """Hold one message for the running turn of `sid`. None when no turn is running or too many are waiting."""
        text = str(text or "").strip()[:MAX_CHARS]
        if not text:
            return None
        with self._lock:
            if sid not in self._live:
                return None
            q = self._pending.setdefault(sid, [])
            if len(q) >= MAX_PENDING:
                return None
            item = {"id": next(self._ids), "text": text, "at": self._clock()}
            q.append(item)
            return dict(item)

    # -- a running turn reads --
    def take(self, sid: str) -> List[dict]:
        with self._lock:
            items = self._pending.pop(sid, [])
            sink = self._sinks.get(sid) if items else None
        if sink is not None:
            try:
                sink([i["text"] for i in items])
            except Exception:
                pass
        if items and self.on_read:
            try:
                self.on_read(sid, [i["id"] for i in items])
            except Exception:
                pass
        return items

    def take_note(self, sid: str) -> str:
        return note_for([i["text"] for i in self.take(sid)]) if sid else ""

    def take_note_current(self) -> str:
        """For the API engines' tool loops: the note for the chat turn running in this context, "" outside one."""
        return self.take_note(_CURRENT.get())

    def take_note_for_tag(self, tag: str) -> str:
        """For the Claude Code hook: the engine knows its turn tag, not the chat id."""
        with self._lock:
            sid = self._tags.get(tag or "", "")
        return self.take_note(sid)


def current_sid() -> str:
    """The chat whose turn runs in this context ("" outside one)."""
    return _CURRENT.get()


INBOX = SteerInbox()
