"""Voice messages and videos a customer sends to the personal Zalo bot (0.449.0).

Owner's plan 05/11/2026 (item 8). Before this the bot skipped both: a voice message or a video simply got no answer.

  - Voice message: the file is downloaded (https only, every redirect checked, `AUDIO_MAX` bytes), turned into 16 kHz
    mono MP3 with ffmpeg (Zalo sends AAC/M4A some speech services refuse) and handed to `STT` (main.py `_stt_nghe`:
    the Groq key, then the OpenAI key). The words reach the bot as what the customer said, with a line saying it was
    heard by machine. Nothing heard: the bot is told to say so and ask the customer to type, never to guess.
  - Video: downloaded up to `VIDEO_MAX` bytes, `FRAMES` frames spread over its length are cut with ffmpeg and given to
    the bot like photos; the first `AUDIO_SECONDS` seconds of sound go to `STT` when a listener is set up.
  - Memory: the frames and words of the last video stay `KEEP_S` seconds for that chat, so "can you check it?" right
    after still shows the bot the video. Older frames are deleted.

Where things live: downloads in a temp folder deleted at once; frames in `STATE_DIR/media_tmp/zalo/`, deleted after
`KEEP_S`; only the words heard are kept, on the inbox message (`conversations.set_message_meta`). Logs carry sizes and
reasons, never what was said.
"""
from __future__ import annotations

import asyncio
import os
import shutil
import sys
import tempfile
import time
from pathlib import Path
from typing import Any, Awaitable, Callable, Dict, List, Optional

from config import STATE_DIR

AUDIO_MAX = 25 * 1024 * 1024
VIDEO_MAX = 60 * 1024 * 1024
AUDIO_SECONDS = 600
FRAMES = 4
KEEP_S = 600
FFMPEG_TIMEOUT = 90
FETCH_TIMEOUT = 90
MAX_REDIRECTS = 3

# async (bytes, file name) -> {"ok", "text", "ly_do"}; wired by main.py to `_stt_nghe`. None = no listener.
STT: Optional[Callable[[bytes, str], Awaitable[dict]]] = None

_RECENT: Dict[tuple, dict] = {}     # (conn_id, thread) -> {"ts", "frames": [...], "heard": "", "kind"}


def _frames_root() -> Path:
    return Path(STATE_DIR) / "media_tmp" / "zalo"


def ffmpeg() -> str:
    return shutil.which("ffmpeg") or ""


async def fetch(url: str, max_bytes: int) -> tuple:
    """(bytes, "") or (None, reason in Vietnamese for the bot). Same rails as photos: https on a public hostname, each
    redirect checked before it is followed, a size cap while streaming."""
    import httpx
    from image_vision import url_allowed
    if not url_allowed(url):
        return None, "đường dẫn file không phải https hợp lệ"
    buf = bytearray()
    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(FETCH_TIMEOUT, connect=15), follow_redirects=False) as c:
            for _ in range(MAX_REDIRECTS + 1):
                async with c.stream("GET", url) as r:
                    if r.status_code in (301, 302, 303, 307, 308):
                        nxt = str(r.url.join(r.headers.get("location") or ""))
                        if not url_allowed(nxt):
                            return None, "đường dẫn file chuyển sang địa chỉ không an toàn"
                        url = nxt
                        continue
                    if r.status_code != 200:
                        return None, f"máy chủ Zalo trả HTTP {r.status_code} (đường dẫn có thể đã hết hạn)"
                    async for chunk in r.aiter_bytes():
                        buf.extend(chunk)
                        if len(buf) > max_bytes:
                            return None, f"file lớn hơn {max_bytes // (1024 * 1024)} MB"
                    break
            else:
                return None, "đường dẫn file chuyển hướng quá nhiều lần"
    except Exception as e:  # noqa: BLE001
        return None, f"tải file lỗi ({type(e).__name__})"
    if not buf:
        return None, "file rỗng"
    return bytes(buf), ""


async def _run(args: List[str], timeout: int = FFMPEG_TIMEOUT) -> tuple:
    """Run ffmpeg/ffprobe at low priority. (returncode, stdout, stderr)."""
    pre = ["nice", "-n", "10"] if shutil.which("nice") else []
    try:
        p = await asyncio.create_subprocess_exec(*pre, *args, stdout=asyncio.subprocess.PIPE,
                                                 stderr=asyncio.subprocess.PIPE)
        out, err = await asyncio.wait_for(p.communicate(), timeout)
        return p.returncode, out, err
    except asyncio.TimeoutError:
        try:
            p.kill()
        except Exception:
            pass
        return -1, b"", b"timeout"
    except Exception as e:  # noqa: BLE001
        return -1, b"", str(e).encode()


async def duration(path: Path) -> float:
    probe = shutil.which("ffprobe")
    if not probe:
        return 0.0
    rc, out, _ = await _run([probe, "-v", "error", "-show_entries", "format=duration", "-of",
                             "default=noprint_wrappers=1:nokey=1", str(path)], 30)
    try:
        return float(out.decode().strip()) if rc == 0 else 0.0
    except ValueError:
        return 0.0


async def to_speech_mp3(src: Path, dst: Path, seconds: int = AUDIO_SECONDS) -> bool:
    """Any audio or video -> 16 kHz mono MP3 of at most `seconds`. False when there is no sound track or no ffmpeg."""
    ff = ffmpeg()
    if not ff:
        return False
    rc, _, _ = await _run([ff, "-y", "-v", "error", "-i", str(src), "-t", str(int(seconds)), "-vn", "-ac", "1",
                           "-ar", "16000", "-b:a", "32k", str(dst)])
    return rc == 0 and dst.is_file() and dst.stat().st_size > 1000


async def cut_frames(src: Path, out_dir: Path, n: int = FRAMES) -> List[str]:
    """`n` JPEG frames spread evenly over the video (never the very first or last instant)."""
    ff = ffmpeg()
    if not ff:
        return []
    total = await duration(src)
    out_dir.mkdir(parents=True, exist_ok=True)
    points = [total * (i + 1) / (n + 1) for i in range(n)] if total > 0 else [0.0]
    paths = []
    for i, at in enumerate(points):
        dst = out_dir / f"frame-{i + 1}.jpg"
        rc, _, _ = await _run([ff, "-y", "-v", "error", "-ss", f"{at:.2f}", "-i", str(src), "-frames:v", "1",
                               "-vf", "scale='min(1280,iw)':-2", "-q:v", "4", str(dst)], 60)
        if rc == 0 and dst.is_file() and dst.stat().st_size > 0:
            paths.append(str(dst))
    return paths


async def listen(path: Path, name: str) -> dict:
    """Words in an audio/video file -> {"ok", "text", "why"}. Converts first; sends the original when ffmpeg is missing."""
    if STT is None:
        return {"ok": False, "text": "", "why": "chua_co_bo_nghe"}
    mp3 = path.with_suffix(".speech.mp3")
    if await to_speech_mp3(path, mp3):
        data, fname = mp3.read_bytes(), "voice.mp3"
    elif not ffmpeg():
        data, fname = path.read_bytes(), name
    else:
        return {"ok": False, "text": "", "why": "khong_co_tieng"}
    try:
        r = await STT(data, fname)
    except Exception as e:  # noqa: BLE001
        print(f"[zalo-media] listen failed: {type(e).__name__}", file=sys.stderr)
        return {"ok": False, "text": "", "why": "loi_nghe"}
    text = str((r or {}).get("text") or "").strip()
    if (r or {}).get("ok") and text:
        return {"ok": True, "text": text, "why": ""}
    return {"ok": False, "text": "", "why": str((r or {}).get("ly_do") or "khong_nghe_ro")}


_WHY = {
    "chua_co_bo_nghe": "UNI MATE chưa được cài bộ nghe giọng",
    "thieu_key": "UNI MATE chưa được cài bộ nghe giọng",
    "khong_co_tieng": "video không có tiếng",
    "khong_nghe_ro": "không nghe ra lời nào (có thể im lặng hoặc quá ồn)",
    "loi_nghe": "bộ nghe giọng đang trục trặc",
    "chua_cai_offline": "bộ nghe trên máy chưa được cài",
}


def _why(code: str) -> str:
    return _WHY.get(code, code or "lỗi không rõ")


def _sweep(now: float) -> None:
    for k, v in list(_RECENT.items()):
        if now - v["ts"] > KEEP_S:
            _RECENT.pop(k, None)
    root = _frames_root()
    if root.is_dir():
        for d in root.glob("*/*/*"):
            try:
                if d.is_dir() and now - d.stat().st_mtime > KEEP_S:
                    shutil.rmtree(d, ignore_errors=True)
            except OSError:
                pass


def _safe(s: str) -> str:
    return "".join(ch if ch.isalnum() or ch in "-_" else "_" for ch in str(s or ""))[:64] or "x"


async def prepare(conn_id: str, thread: str, items: List[dict], now: Optional[float] = None) -> dict:
    """Turn the voice messages and videos of one turn into what the bot reads.

    `items`: [{"type": "audio"|"video", "url", "id"}]. Returns {"text": block for the bot, "frames": [jpg paths],
    "heard": {message id: words}} where "text" says, per item, what was heard or seen and what could not be."""
    now = time.time() if now is None else now
    _sweep(now)
    blocks, frames, heard = [], [], {}
    for it in items[-3:]:
        kind, url, mid = it.get("type"), str(it.get("url") or ""), str(it.get("id") or "")
        if kind not in ("audio", "video"):
            continue
        if not url:
            blocks.append(f"[Khách gửi một {'tin thoại' if kind == 'audio' else 'video'} nhưng Zalo không đưa đường dẫn "
                          "file nên UNI MATE chưa mở được. Nói thật là chưa nghe/xem được, nhờ khách gõ chữ hoặc tả lại, "
                          "không đoán nội dung.]")
            continue
        data, why = await fetch(url, AUDIO_MAX if kind == "audio" else VIDEO_MAX)
        if data is None:
            blocks.append(f"[Khách gửi một {'tin thoại' if kind == 'audio' else 'video'} nhưng UNI MATE chưa tải được "
                          f"({why}). Nói thật là chưa nghe/xem được, nhờ khách gõ chữ hoặc tả lại, không đoán nội dung.]")
            continue
        print(f"[zalo-media] {kind} {len(data) // 1024}KB", file=sys.stderr)
        with tempfile.TemporaryDirectory(prefix="unimate-zalo-media-") as tmp:
            src = Path(tmp) / ("in.m4a" if kind == "audio" else "in.mp4")
            src.write_bytes(data)
            if kind == "audio":
                r = await listen(src, "voice.m4a")
                if r["ok"]:
                    heard[mid] = r["text"]
                    blocks.append("[Khách gửi tin thoại. UNI MATE nghe thành chữ bằng máy, có thể nhầm vài từ; chỗ nào "
                                  "không chắc thì hỏi lại khách:]\n" + r["text"])
                else:
                    blocks.append(f"[Khách gửi một tin thoại nhưng UNI MATE chưa nghe được ({_why(r['why'])}). Nói thật "
                                  "là chưa nghe được, nhờ khách gõ chữ, không đoán nội dung.]")
                continue
            out_dir = _frames_root() / _safe(conn_id) / _safe(thread) / (_safe(mid) + f"-{int(now)}")
            fr = await cut_frames(src, out_dir)
            r = await listen(src, "video.mp4")
            if r["ok"]:
                heard[mid] = r["text"]
            line = (f"[Khách gửi một video. Kèm theo là {len(fr)} khung hình cắt rải đều trong video." if fr
                    else "[Khách gửi một video nhưng UNI MATE chưa cắt được khung hình nào.")
            line += (" Lời nói trong video (máy nghe, có thể nhầm):]\n" + r["text"] if r["ok"]
                     else f" Không nghe được tiếng trong video ({_why(r['why'])}); đừng đoán lời nói trong video.]")
            blocks.append(line)
            frames += fr
            _RECENT[(str(conn_id), str(thread))] = {"ts": now, "frames": fr, "heard": r["text"] if r["ok"] else "",
                                                     "kind": "video"}
    return {"text": "\n".join(blocks), "frames": frames[:FRAMES * 2], "heard": heard}


def recent_video(conn_id: str, thread: str, now: Optional[float] = None) -> dict:
    """The last video of this chat while it is still `KEEP_S` seconds fresh, with its frames still on disk; else {}."""
    now = time.time() if now is None else now
    v = _RECENT.get((str(conn_id), str(thread)))
    if not v or now - v["ts"] > KEEP_S:
        _RECENT.pop((str(conn_id), str(thread)), None)
        return {}
    fr = [p for p in v.get("frames") or [] if os.path.isfile(p)]
    return dict(v, frames=fr) if fr else {}
