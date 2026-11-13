"""What one progress step produced, in a shape the chat can draw (0.451.0).

The owner asked (2026-11-13) for the progress block to behave like Claude's: open a step and see what it produced. Only
two kinds of output get something visual, in his words "ảnh, file biểu mẫu, tài liệu":
- a PICTURE (a browser screenshot, a picture an MCP tool returned, a picture made or read in the brain) shows as a small
  image inside the step, which the chat's existing lightbox enlarges;
- a DOCUMENT (Word, Excel, PDF, PowerPoint) the step made, changed or read shows as a file card that opens in the app's
  file viewer, like Claude's file cards.
Code edits and commands get a few lines of text and nothing else.

`build()` is pure apart from writing pictures that only existed inside a tool result (base64) to
STATE_DIR/step_media/<session>/, served owner-only by GET /step-media/<session>/<name> and deleted with the conversation
(sessions.delete calls `drop`). Pictures and documents that already live in the brain are referenced, never copied.

Safety: the text is passed through secret_redact before it leaves the server (the browser keeps it in its local
history), the dashboard escapes everything it draws, SVG is never accepted (it can carry script), and only the owner's
own chat socket receives these frames.
"""
from __future__ import annotations

import base64
import binascii
import hashlib
import json
import os
import re
import shutil
import time
from pathlib import Path
from urllib.parse import quote

STATE_DIR = Path(os.getenv("UNIMATE_STATE_DIR", str(Path(__file__).parent)))
ROOT_NAME = "step_media"

PREVIEW_LINES = 6
PREVIEW_CHARS = 600
LINE_CHARS = 200
MAX_IMG_BYTES = 5 * 1024 * 1024
MAX_IMGS_TURN = 12
MAX_FILES_STEP = 4
# A shell step may mention a document it did not make (an `ls`, a path in an error). Only a file changed this recently
# counts as the step's own output.
RECENT_S = 15 * 60

IMG_MIME = {"image/png": ".png", "image/jpeg": ".jpg", "image/jpg": ".jpg", "image/webp": ".webp",
            "image/gif": ".gif"}
IMG_EXT = {".png", ".jpg", ".jpeg", ".webp", ".gif"}
DOC_KIND = {".pdf": "PDF", ".doc": "Word", ".docx": "Word", ".xls": "Excel", ".xlsx": "Excel", ".xlsm": "Excel",
            ".ppt": "PowerPoint", ".pptx": "PowerPoint"}
# Tools whose job is code or a command: no pictures guessed from paths (the owner: "code hay lệnh làm việc thì không
# cần ảnh"). Documents they produce still get a card, see `_paths`.
SHELL_RE = re.compile(r"^(bash|shell|run_shell_command|command_execution|local_shell_call|run_terminal_command|"
                      r"run_command|exec|unimate_terminal)$", re.I)
CODE_RE = re.compile(r"^(edit|multiedit|notebookedit|str_replace|str_replace_editor|apply_patch|edit_file|replace|"
                     r"patch|grep|search_file_content|grep_search|codebase_search|glob|ls|list_directory|list_dir|"
                     r"find|find_by_name|todowrite|todo_write|update_plan|file_change)$", re.I)
SID_RE = re.compile(r"^[A-Za-z0-9_.:-]{1,80}$")
NAME_RE = re.compile(r"^[0-9a-f]{32}\.(png|jpg|webp|gif)$")
_ANSI = re.compile(r"\x1b\[[0-9;?]*[A-Za-z]")
_PATH_TOKEN = re.compile(r"[^\s\"'`<>|()\[\]{},]+\.(?:pdf|docx?|xlsx?|xlsm|pptx?|png|jpe?g|webp|gif)\b", re.I)


def new_budget() -> dict:
    """Per-turn counters: pictures written so far."""
    return {"imgs": 0}


def _redact(text: str) -> str:
    try:
        import secret_redact
        return secret_redact.redact_secrets(text)
    except Exception:  # noqa: BLE001 - never block a step on the masker
        return text


def _safe_sid(sid: str) -> str:
    s = str(sid or "").strip()
    return s if SID_RE.match(s) else "nosession"


def media_dir(sid: str) -> Path:
    return STATE_DIR / ROOT_NAME / _safe_sid(sid)


def media_path(sid: str, name: str):
    """The file behind GET /step-media/<sid>/<name>, or None for anything not ours."""
    if not SID_RE.match(str(sid or "")) or not NAME_RE.match(str(name or "")):
        return None
    p = media_dir(sid) / name
    return p if p.is_file() else None


def drop(sid: str) -> None:
    """Delete a conversation's step pictures (called when the conversation is deleted)."""
    if not SID_RE.match(str(sid or "")):
        return
    shutil.rmtree(media_dir(sid), ignore_errors=True)


# ---------------------------------------------------------------- pictures inside a tool result
def _img_from_block(b: dict):
    """(mime, base64 data) from an Anthropic block {type:image, source:{type:base64,...}} or an MCP block
    {type:image, data, mimeType}; None otherwise."""
    if not isinstance(b, dict) or b.get("type") != "image":
        return None
    src = b.get("source") if isinstance(b.get("source"), dict) else None
    if src and src.get("type") == "base64":
        return str(src.get("media_type") or ""), str(src.get("data") or "")
    if b.get("data"):
        return str(b.get("mimeType") or b.get("mime_type") or b.get("media_type") or ""), str(b.get("data") or "")
    return None


def _split(content):
    """(text, [(mime, b64)]) from whatever an engine hands over: a string, a list of blocks, or a dict with `content`.

    MCP results reach the API engines as text where every non-text block is one JSON line (mcp_client._format_result),
    so a line that parses as an image block is a picture too, and is left out of the text."""
    texts, imgs = [], []

    def walk(x, depth=0):
        if depth > 5 or x is None:
            return
        if isinstance(x, str):
            for line in x.splitlines() or [x]:
                s = line.strip()
                if s.startswith("{") and '"image"' in s[:200]:
                    try:
                        got = _img_from_block(json.loads(s))
                    except ValueError:
                        got = None
                    if got:
                        imgs.append(got)
                        continue
                texts.append(line)
            return
        if isinstance(x, (list, tuple)):
            for y in x:
                walk(y, depth + 1)
            return
        if isinstance(x, dict):
            got = _img_from_block(x)
            if got:
                imgs.append(got)
                return
            if x.get("type") == "text" and isinstance(x.get("text"), str):
                texts.append(x["text"])
                return
            if isinstance(x.get("changes"), list):          # a Codex file change: one line per file
                for c in x["changes"]:
                    if isinstance(c, dict) and c.get("path"):
                        texts.append(("%s (%s)" % (c.get("path"), c.get("kind"))) if c.get("kind") else str(c["path"]))
                return
            keys = ("content", "result", "output", "aggregated_output", "structuredContent", "error", "message",
                    "query")
            for k in keys:
                if x.get(k) not in (None, "", [], {}):
                    walk(x[k], depth + 1)
                    return
            if any(k in x for k in keys) or x.get("type"):
                return          # a known or typed shape that produced nothing (a silent command, a bare Codex item)
            texts.append(json.dumps(x, ensure_ascii=False)[:2000])
            return
        texts.append(str(x))

    walk(content)
    return "\n".join(texts), imgs


def raw_result(c):
    """A Claude Code tool result kept for `build`: picture blocks whole, text up to 4000 characters, 20 items."""
    if isinstance(c, list):
        out = []
        for x in c[:20]:
            if isinstance(x, dict) and x.get("type") == "image":
                out.append(x)
            elif isinstance(x, dict):
                out.append({"type": "text", "text": str(x.get("text", ""))[:4000]})
            else:
                out.append({"type": "text", "text": str(x)[:4000]})
        return out
    return str(c or "")[:4000]


def _save_img(sid: str, mime: str, data: str, budget: dict):
    ext = IMG_MIME.get(str(mime or "").lower())
    if not ext or budget.get("imgs", 0) >= MAX_IMGS_TURN:
        return None
    try:
        raw = base64.b64decode(data, validate=False)
    except (binascii.Error, ValueError):
        return None
    if not raw or len(raw) > MAX_IMG_BYTES:
        return None
    name = hashlib.sha256(raw).hexdigest()[:32] + ext
    d = media_dir(sid)
    try:
        d.mkdir(parents=True, exist_ok=True)
        p = d / name
        if not p.exists():
            p.write_bytes(raw)
    except OSError:
        return None
    budget["imgs"] = budget.get("imgs", 0) + 1
    return "/step-media/%s/%s" % (quote(_safe_sid(sid)), name)


# ---------------------------------------------------------------- files in the brain
def _in_brain(brain_root, cand: str):
    """(path, relative path) when `cand` names an existing file inside the brain, else None."""
    if not brain_root or not cand:
        return None
    try:
        root = Path(brain_root).resolve()
        p = Path(cand)
        p = (p if p.is_absolute() else root / p).resolve()
        rel = p.relative_to(root)
    except (OSError, ValueError, RuntimeError):
        return None
    return (p, rel.as_posix()) if p.is_file() else None


def _paths(tool: str, inp, text: str) -> list:
    """Candidate paths of the step: from its arguments and from its result text."""
    out = []
    try:
        import channel_context
        out += channel_context.candidate_paths_from_tool(inp or {})
    except Exception:  # noqa: BLE001
        pass
    out += _PATH_TOKEN.findall(text or "")
    seen, uniq = set(), []
    for c in out:
        c = str(c).strip().strip("'\"`").rstrip(".,;:")
        if c and c not in seen:
            seen.add(c)
            uniq.append(c)
    return uniq[:40]


def _brain_url(brain_root, rel: str) -> str:
    return "/files/raw?brain=%s&path=%s" % (quote(str(brain_root), safe=""), quote(rel, safe=""))


# ---------------------------------------------------------------- the step
def preview(text: str):
    """(first lines, how many lines are left) of a step's text, secrets masked."""
    t = _ANSI.sub("", _redact(str(text or ""))).replace("\r\n", "\n").replace("\r", "\n")
    lines = [ln.rstrip() for ln in t.split("\n")]
    while lines and not lines[0].strip():
        lines.pop(0)
    while lines and not lines[-1].strip():
        lines.pop()
    keep, used = [], 0
    for ln in lines:
        if len(keep) >= PREVIEW_LINES or used >= PREVIEW_CHARS:
            break
        ln = ln if len(ln) <= LINE_CHARS else ln[:LINE_CHARS - 1] + "…"
        ln = ln[:max(0, PREVIEW_CHARS - used)]
        keep.append(ln)
        used += len(ln) + 1
    return "\n".join(keep), max(0, len(lines) - len(keep))


def build(tool: str, inp, content, *, sid: str, brain_root=None, budget: dict | None = None,
          is_error: bool = False, now: float | None = None) -> dict:
    """The `res` of a tool_result frame: {text, more, err, imgs:[{src}], files:[{name, path, kind}]}."""
    budget = budget if budget is not None else new_budget()
    now = now if now is not None else time.time()
    name = str(tool or "")
    text, blocks = _split(content)
    res = {"text": "", "more": 0, "err": bool(is_error), "imgs": [], "files": []}
    res["text"], res["more"] = preview(text)
    if not is_error and re.match(r"^\s*(error|lỗi)\b", text or "", re.I):
        res["err"] = True
    for mime, data in blocks:
        url = _save_img(sid, mime, data, budget)
        if url:
            res["imgs"].append({"src": url})
    shell = bool(SHELL_RE.match(name))
    code = bool(CODE_RE.match(name))
    seen = set()
    for cand in _paths(name, inp, text):
        hit = _in_brain(brain_root, cand)
        if not hit:
            continue
        p, rel = hit
        if rel in seen:
            continue
        seen.add(rel)
        ext = p.suffix.lower()
        try:
            recent = (now - p.stat().st_mtime) <= RECENT_S
        except OSError:
            recent = False
        if ext in DOC_KIND:
            # A command or a code edit only "has" a document it just wrote; a reading or writing tool always does.
            if (shell or code) and not recent:
                continue
            if len(res["files"]) < MAX_FILES_STEP:
                res["files"].append({"name": p.name, "path": rel, "kind": DOC_KIND[ext]})
        elif ext in IMG_EXT and not (shell or code):
            if budget.get("imgs", 0) < MAX_IMGS_TURN:
                budget["imgs"] = budget.get("imgs", 0) + 1
                res["imgs"].append({"src": _brain_url(brain_root, rel), "path": rel})
    return res
