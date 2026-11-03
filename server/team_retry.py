"""Team turns retry a passing engine hiccup on their own (0.436.0).

Before: one 503, "overloaded" or dropped connection in the middle of a team job failed the step and blocked the job
until the owner pressed Run again, even though the same call a few seconds later would have worked.

The rules, all here so the runner stays a loop:

1. Only TRANSIENT failures are retried: overload, 429 throttling, 5xx, a dropped or reset connection, an engine-side
   timeout. A plan limit ("usage limit", "5-hour limit", quota), a login or access error, a bad request, our own
   wall-clock timeout and anything we cannot classify are NOT: waiting seconds will not fix them, and a retry only
   burns turns.
2. NEVER a second send or post. A step WITH TOOLS that already reached the model may have sent a message, posted,
   paid or written before it failed. Its outside actions cannot be checked from here, so it is not retried; the step
   fails with a note saying why, and the owner decides. A text-only turn (chat replies, plan, summary) posts nothing
   until it succeeds, so retrying it can never post twice. A turn that failed BEFORE reaching the model did nothing,
   so it is always safe.
3. Bounded: at most MAX_RETRIES extra attempts, with growing waits plus jitter. A "retry after N seconds" hint from
   the provider is honoured when it fits under MAX_WAIT_S; a longer one means the provider is not coming back soon.
   Each retry is a real turn and counts against the team's turn caps like any other.

Pure module: no I/O, no clock of its own. Note: never use the em dash character in this file.
"""
from __future__ import annotations

import random
import re
from typing import Optional

MAX_RETRIES = 2
BACKOFF_S = (6.0, 20.0)      # wait before retry 1, retry 2
JITTER = 0.25                # + up to 25%
MAX_WAIT_S = 28.0            # stays under a third of the job lease (JOB_LEASE_S 90 s), so the job is never lost meanwhile

# A plan or account limit: retrying in seconds cannot help (checked FIRST, "rate limit" text can ride along).
_PLAN = re.compile(r"usage limit|limit reached|5-hour|five.hour|weekly limit|quota|resource_exhausted|insufficient|"
                   r"credit balance|billing|hết lượt|hết hạn mức|giới hạn 5 giờ", re.I)
# Access, login or a request the provider will refuse every time.
_FATAL = re.compile(r"\b(400|401|403|404|413|422)\b|unauthori[sz]ed|forbidden|permission|invalid[ _]api[ _]key|"
                    r"not logged in|log ?in again|mất đăng nhập|model_not_found|does not exist|not found|"
                    r"context length|too long|invalid_request", re.I)
_TRANSIENT = re.compile(r"\b(408|425|429|500|502|503|504|520|522|524|529)\b|overloaded|at capacity|over capacity|"
                        r"temporarily unavailable|service unavailable|bad gateway|gateway time-?out|internal server error|"
                        r"too many requests|rate.?limit|throttl|try again|please retry|connection (?:reset|aborted|"
                        r"refused|closed|error)|econnreset|econnrefused|etimedout|socket hang up|broken pipe|"
                        r"network (?:error|is unreachable)|remote ?protocol|stream (?:disconnected|ended|closed)|"
                        r"timed out|read timeout|connect timeout|server disconnected|không phản hồi", re.I)
_RETRY_AFTER = re.compile(r"(?:retry|try again|thử lại)[^0-9]{0,20}(\d+(?:\.\d+)?)\s*"
                          r"(ms|millisecond|s|sec|second|giây|m|min|minute|phút|h|hour|giờ)?", re.I)
_UNIT = {"ms": 0.001, "millisecond": 0.001, "m": 60.0, "min": 60.0, "minute": 60.0, "phút": 60.0,
         "h": 3600.0, "hour": 3600.0, "giờ": 3600.0}


def _text(out: dict) -> str:
    return " ".join(str(out.get(k) or "") for k in ("error", "detail"))


def classify(out: dict) -> str:
    """'transient', 'plan', 'fatal' or '' (not an error, or one we do not know) for a `_turn` outcome."""
    if not isinstance(out, dict) or out.get("status") != "error":
        return ""
    if out.get("reason") in ("auth", "timeout") or out.get("internal"):
        # Login errors need the owner; our own time limit already waited minutes; an internal (store) error is ours.
        return "fatal"
    t = _text(out)
    if _PLAN.search(t):
        return "plan"
    if _FATAL.search(t):
        return "fatal"
    return "transient" if _TRANSIENT.search(t) else ""


def may_have_acted(out: dict) -> bool:
    """True when the failed turn may already have done something outside: a tool turn that reached the model."""
    return bool(out.get("tool_turn")) and not out.get("before_engine")


def wait_s(out: dict, retry_no: int, rng: Optional[random.Random] = None) -> Optional[float]:
    """Seconds to wait before retry `retry_no` (1-based), or None when the outcome must not be retried."""
    if retry_no < 1 or retry_no > MAX_RETRIES or classify(out) != "transient" or may_have_acted(out):
        return None
    m = _RETRY_AFTER.search(_text(out))
    if m:
        hint = float(m.group(1)) * _UNIT.get((m.group(2) or "s").lower(), 1.0)
        if hint > MAX_WAIT_S:
            return None    # the provider itself says it is not coming back within a retry window
        if hint > 0:
            return max(1.0, hint)
    base = BACKOFF_S[min(retry_no, len(BACKOFF_S)) - 1]
    jitter = (rng or random).uniform(0, JITTER * base)
    return min(MAX_WAIT_S, base + jitter)


def not_retried_note(out: dict) -> str:
    """Why a transient failure was left to the owner (shown on the failed step), or "" when there is nothing to say."""
    if classify(out) == "transient" and may_have_acted(out):
        import localefmt
        return localefmt.chu("không tự thử lại: bước có công cụ có thể đã gửi, đăng hay ghi trước khi lỗi; "
                             "kiểm tra rồi bấm Chạy lại để tránh làm hai lần",
                             "not retried on its own: a step with tools may have sent, posted or written before it "
                             "failed; check, then press Run again so nothing happens twice")
    return ""
