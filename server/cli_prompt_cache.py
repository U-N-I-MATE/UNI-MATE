"""Keep the Claude Code system prompt identical across new chats, so it is read back from the prompt cache (0.437.0).

Why. The system prompt UNI MATE hands to Claude Code is ~43,000 characters (CLAUDE.md, memory, skills, agentic
paths, channel contract). Measured 03/11/2026: two new chats built one minute apart differed in four lines only, the
clock line and three lines carrying the chat's session id; on a day with usage there is also the "usage today" block,
which changes after every turn. Claude Code marks the end of the system prompt as a cache point, so one changed
character anywhere in it means the whole prompt is written to the cache again on every new chat instead of read
from it. On a subscription plan a cache write costs the 5-hour allowance far more than a cache read.

The fix keeps every rule where it is and moves only the values that change:
- the clock line becomes a fixed sentence pointing at the first line of the owner's newest message;
- the session id becomes a fixed reference; the real id rides on the first message of the chat;
- the usage block becomes a fixed sentence; today's numbers ride on the first message of the chat.

Claude Code keeps the first turn's messages when it resumes a chat (--resume), so the id and numbers given on the
first message stay in view for the rest of the chat; later turns only add the short clock line (as before 0.437.0).

Pure functions, no I/O. Note: never use the em dash character in this file.
"""
from __future__ import annotations

import re

# "\n\n# === BÂY GIỜ ===\n" + one clock line (main_prompt_rendering.render_clock_language); the language block
# that follows starts with a blank line and stays.
_CLOCK = re.compile(r"(\n\n# === BÂY GIỜ ===\n)[^\n]*")
# main_prompt_rendering.render_usage_block: a header line and one paragraph line.
_USAGE = re.compile(r"\n\n# === MỨC DÙNG HÔM NAY[^\n]*===\n[^\n]*")

CLOCK_NOTE = ("Giờ THẬT nằm ở dòng đầu tin nhắn mới nhất của chủ, dạng [Giờ gửi tin này: ...]: dùng thẳng giờ đó khi "
              "cần biết hôm nay/bây giờ, không đoán và không cần gọi tool.")
SESSION_REF = "<mã phiên ở dòng [Phiên chat] đầu cuộc>"
USAGE_NOTE = ("\n\n# === MỨC DÙNG HÔM NAY (UNI MATE tự đo) ===\n"
              "Số token UNI MATE tự đo hôm nay (nếu có) nằm ở dòng [Phiên chat] đầu cuộc. Đây là token UNI MATE "
              "TỰ ĐO, KHÔNG phải hạn mức gói thuê bao. Chi tiết từng nhà cung cấp ở panel 'Mức dùng' trên dashboard.")


def stable_prompt(sysprompt: str, session_id: str = "") -> str:
    """`sysprompt` with the per-chat values replaced by fixed text. Anything unexpected returns it unchanged."""
    if not isinstance(sysprompt, str) or not sysprompt:
        return sysprompt
    try:
        out = _CLOCK.sub(lambda m: m.group(1) + CLOCK_NOTE, sysprompt, count=1)
        out = _USAGE.sub("", out, count=1)
        out += USAGE_NOTE
        sid = (session_id or "").strip()
        if len(sid) >= 8:   # a real id; a short one could match ordinary words
            out = out.replace(sid, SESSION_REF)
        return out
    except Exception:  # noqa: BLE001 - a prompt that is merely uncached must never break the turn
        return sysprompt


def session_line(session_id: str = "", usage_today: dict | None = None) -> str:
    """The line sent on the FIRST message of a chat: the values `stable_prompt` took out ("" when there is none)."""
    parts = []
    sid = (session_id or "").strip()
    if sid:
        parts.append(f"mã phiên chat `{sid}` (dùng ở chỗ hướng dẫn ghi {SESSION_REF})")
    t = usage_today if isinstance(usage_today, dict) else {}
    if t.get("in") or t.get("out"):
        cost = f", ~${t.get('cost', 0):.4f}" if t.get("cost") else ""
        parts.append(f"mức dùng hôm nay {int(t.get('in') or 0):,} token vào + {int(t.get('out') or 0):,} token ra "
                     f"qua {int(t.get('turns') or 0)} lượt{cost}")
    return f"[Phiên chat: {'; '.join(parts)}]" if parts else ""
