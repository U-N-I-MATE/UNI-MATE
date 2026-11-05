"""0.449.0: the personal Zalo bot hears voice messages and watches videos.

    python tests/run.py zalo_voice_video_0449      (NO network; real ffmpeg when the machine has it)

Owner's plan 05/11/2026 (item 8). Checks:
  1. Zalo messages: a voice message / video keeps its file link; a merged private turn carries them in `metadata.media`
     and counts as content.
  2. Download rails: https on a hostname only.
  3. A voice message is converted and heard; the words reach the bot marked as machine listening and are stored on the
     inbox message. No listener, a failed download, nothing heard: the bot is told to say so, never to guess.
  4. A video gives 4 frames spread over its length plus the words in its sound; frames stay 10 minutes for a follow-up
     question, then are deleted.
  5. Frames reach the bot's model only from UNI MATE's own frame folder; a remembered photo does not push them out.
  6. The listener: Groq key first, the OpenAI key when Groq has no key or fails; "nothing heard" is not asked twice.
  7. Logs carry sizes, never what was said.
"""
from _paths import ROOT, SERVER  # noqa: E402,F401
import asyncio
import contextlib
import io
import os
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

os.environ["UNIMATE_STATE_DIR"] = tempfile.mkdtemp(prefix="unimate-0449-")
try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

import conversations  # noqa: E402
import zalo_media  # noqa: E402
import zalo_personal_channel as zc  # noqa: E402

_fails = []


def check(name, cond, extra=""):
    print(("ok   " if cond else "FAIL ") + name + (("  [" + str(extra)[:300] + "]") if not cond else ""))
    if not cond:
        _fails.append(name)


def run(c):
    return asyncio.run(c)


FF = shutil.which("ffmpeg") and shutil.which("ffprobe")
WORK = Path(tempfile.mkdtemp(prefix="unimate-0449-media-"))


def make(kind):
    """A short real file: a voice note (tone), a video with sound, a video without sound."""
    if not FF:
        return b"fake-" + kind.encode()
    out = WORK / {"voice": "v.m4a", "video": "v.mp4", "mute": "m.mp4"}[kind]
    if kind == "voice":
        args = ["-f", "lavfi", "-i", "sine=frequency=440:duration=3", "-c:a", "aac"]
    elif kind == "video":
        args = ["-f", "lavfi", "-i", "testsrc=size=320x240:rate=10:duration=6", "-f", "lavfi", "-i",
                "sine=frequency=300:duration=6", "-shortest", "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac"]
    else:
        args = ["-f", "lavfi", "-i", "testsrc=size=320x240:rate=10:duration=6", "-c:v", "libx264", "-pix_fmt", "yuv420p"]
    subprocess.run(["ffmpeg", "-y", "-v", "error", *args, str(out)], check=True, timeout=60)
    return out.read_bytes()


# ---------- 1. Zalo messages ----------
conn = {"id": "zl1", "label": "Shop"}
msg = {"id": "m1", "type": "chat.voice", "threadId": "u77", "uidFrom": "u77", "dName": "Khach",
       "attachment": {"type": "voice", "url": "https://voice-cdn.zdn.vn/abc.m4a"}, "ts": time.time() * 1000}
ev = zc.chuan_hoa_tin(conn, msg, {})
check("voice message keeps its file link", ev and ev["message_type"] == "audio"
      and ev["metadata"].get("media_url") == "https://voice-cdn.zdn.vn/abc.m4a", ev)
vid = dict(msg, id="m2", type="chat.video.msg", attachment={"type": "video", "url": "https://video.zdn.vn/x.mp4"})
ev2 = zc.chuan_hoa_tin(conn, vid, {})
check("video keeps its file link", ev2["message_type"] == "video" and ev2["metadata"].get("media_url"), ev2)
check("voice and video count as content of the turn", zc._co_chu(ev) and zc._co_chu(ev2))
txt = dict(ev, message_type="text", text="xem giúp em", external_message_id="m3", metadata={})
g = zc.gop_tin([ev, ev2, txt])
check("merged turn carries voice and video, oldest first",
      [m["type"] for m in g["metadata"]["media"]] == ["audio", "video"] and g["message_type"] == "text", g)
g2 = zc.gop_tin([ev])
check("a turn with only a voice message is a voice turn", g2["message_type"] == "audio" and g2["metadata"]["media"], g2)

# ---------- 2. download rails ----------
check("plain http refused", run(zalo_media.fetch("http://voice-cdn.zdn.vn/a.m4a", 1000))[0] is None)
check("an IP address refused", run(zalo_media.fetch("https://10.0.0.5/a.m4a", 1000))[0] is None)

# ---------- 3. voice ----------
BLOBS = {"https://z/voice.m4a": make("voice"), "https://z/video.mp4": make("video"), "https://z/mute.mp4": make("mute")}


async def fake_fetch(url, max_bytes):
    b = BLOBS.get(url)
    return (b, "") if b else (None, "máy chủ Zalo trả HTTP 404 (đường dẫn có thể đã hết hạn)")


zalo_media.fetch = fake_fetch
SENT = []


async def stt_ok(data, name):
    SENT.append((len(data), name))
    return {"ok": True, "text": "Cho chị hỏi giá áo size M"}

zalo_media.STT = None
r = run(zalo_media.prepare("zl1", "u77", [{"type": "audio", "url": "https://z/voice.m4a", "id": "m1"}]))
check("no listener: the bot is told it could not hear, and not to guess",
      "chưa nghe được" in r["text"] and "không đoán" in r["text"] and not r["heard"], r)
zalo_media.STT = stt_ok
log = io.StringIO()
with contextlib.redirect_stderr(log):
    r = run(zalo_media.prepare("zl1", "u77", [{"type": "audio", "url": "https://z/voice.m4a", "id": "m1"}]))
check("voice heard: the words reach the bot, marked as machine listening",
      "Cho chị hỏi giá áo size M" in r["text"] and "nghe thành chữ bằng máy" in r["text"], r)
check("voice heard: words kept for the inbox message", r["heard"] == {"m1": "Cho chị hỏi giá áo size M"}, r)
if FF:
    check("voice converted to MP3 before listening", SENT and SENT[-1][1] == "voice.mp3", SENT)
check("log has the size, not the words", "KB" in log.getvalue() and "size M" not in log.getvalue(), log.getvalue())
r = run(zalo_media.prepare("zl1", "u77", [{"type": "audio", "url": "https://z/gone.m4a", "id": "m9"}]))
check("download failed: honest line with the reason", "chưa tải được" in r["text"] and "404" in r["text"], r)
r = run(zalo_media.prepare("zl1", "u77", [{"type": "audio", "url": "", "id": "m8"}]))
check("no link from Zalo: honest line", "không đưa đường dẫn" in r["text"], r)


async def stt_silent(data, name):
    return {"ok": False, "text": "", "ly_do": "khong_nghe_ro"}

zalo_media.STT = stt_silent
r = run(zalo_media.prepare("zl1", "u77", [{"type": "audio", "url": "https://z/voice.m4a", "id": "m1"}]))
check("nothing heard: says so", "không nghe ra lời nào" in r["text"], r)
zalo_media.STT = stt_ok

# inbox: the words go on the stored message
conversations.ghi_su_kien(dict(ev, text="[Zalo cá nhân: khách gửi audio]"))
ok = conversations.set_message_meta("zalo_personal:zl1", "u77", "m1", {"heard": "Cho chị hỏi giá áo size M"})
cid = conversations.danh_sach(channel="zalo_personal")
cid = (cid["items"] if isinstance(cid, dict) else cid)[0]["id"]
stored = conversations.tin_nhan(cid)[-1]
check("inbox message carries the words heard", ok and stored["metadata"].get("heard") == "Cho chị hỏi giá áo size M", stored)
check("unknown message: nothing written", not conversations.set_message_meta("zalo_personal:zl1", "u77", "nope", {"heard": "x"}))

# ---------- 4. video ----------
if FF:
    r = run(zalo_media.prepare("zl1", "u77", [{"type": "video", "url": "https://z/video.mp4", "id": "v1"}]))
    check("video: 4 frames cut", len(r["frames"]) == 4 and all(Path(p).is_file() for p in r["frames"]), r)
    check("video: words in the sound heard", r["heard"].get("v1") == "Cho chị hỏi giá áo size M" and "4 khung hình" in r["text"], r)
    rv = zalo_media.recent_video("zl1", "u77")
    check("video remembered for a follow-up question", rv and rv["frames"] == r["frames"], rv)
    check("another chat does not see it", zalo_media.recent_video("zl1", "u88") == {})
    r2 = run(zalo_media.prepare("zl1", "u78", [{"type": "video", "url": "https://z/mute.mp4", "id": "v2"}]))
    check("video without sound: frames, and the bot is told there is no sound",
          len(r2["frames"]) == 4 and "không có tiếng" in r2["text"] and not r2["heard"], r2)
    later = time.time() + zalo_media.KEEP_S + 5
    check("after 10 minutes the video is forgotten", zalo_media.recent_video("zl1", "u77", now=later) == {})
    for p in r["frames"]:
        os.utime(Path(p).parent, (later - zalo_media.KEEP_S - 60, later - zalo_media.KEEP_S - 60))
    zalo_media._sweep(later)
    check("and its frames are deleted", not any(Path(p).exists() for p in r["frames"]))
else:
    print("skip video checks: no ffmpeg on this machine")

# ---------- 5. frames reach the bot's model ----------
import chatbot_runtime  # noqa: E402
brain = Path(tempfile.mkdtemp(prefix="unimate-0449-brain-"))
chatbot_runtime._deps["brain_root"] = lambda b: str(brain)
fdir = zalo_media._frames_root() / "zl1" / "u90" / "v9"
fdir.mkdir(parents=True, exist_ok=True)
good = fdir / "frame-1.jpg"
good.write_bytes(b"\xff\xd8\xff\xe0" + b"0" * 100)
outside = WORK / "evil.jpg"
outside.write_bytes(b"\xff\xd8\xff\xe0" + b"0" * 100)
text, paths = run(chatbot_runtime.anh_cho_bot("xem giúp", {"video_frames": [str(good), str(outside)]}, {"brain": "b"}))
check("frames from the frame folder reach the model, a path outside it does not",
      paths == [str(good.resolve())], paths)
m = chatbot_runtime.gan_anh_cho("bot1", {"video_frames": [str(good)], "chat_id": "u90"}, "xem giúp")
check("a remembered photo does not replace the video frames", m.get("video_frames") == [str(good)] and "_anh_cho" not in m, m)

# ---------- 6. the listener chain ----------
import main  # noqa: E402
import stt  # noqa: E402
CALLS = []


async def groq(data, ten, key, model="", ngon_ngu=None, hotwords=""):
    CALLS.append(("groq", key))
    if not key:
        return {"ok": False, "ly_do": "thieu_key"}
    return GROQ_ANSWER


async def openai(data, ten, key, model="", ngon_ngu=None, hotwords=""):
    CALLS.append(("openai", key))
    return {"ok": True, "text": "nghe bằng OpenAI"}


stt.groq_nghe, stt.openai_nghe = groq, openai
SET = {"model": {}}
main.cfgmod.read_settings = lambda: SET
SET["model"] = {"openai_api_key": "sk-o"}
GROQ_ANSWER = None
res = run(main._stt_nghe(b"x" * 2000, "voice.mp3"))
check("no Groq key: the OpenAI key listens", res.get("ok") and res["text"] == "nghe bằng OpenAI"
      and CALLS == [("groq", ""), ("openai", "sk-o")], CALLS)
CALLS.clear()
SET["model"] = {"groq_api_key": "gk", "openai_api_key": "sk-o"}
GROQ_ANSWER = {"ok": False, "ly_do": "loi"}
res = run(main._stt_nghe(b"x" * 2000, "voice.mp3"))
check("Groq failing: falls back to OpenAI", res.get("ok") and [c[0] for c in CALLS] == ["groq", "openai"], CALLS)
CALLS.clear()
GROQ_ANSWER = {"ok": False, "ly_do": "khong_nghe_ro"}
res = run(main._stt_nghe(b"x" * 2000, "voice.mp3"))
check("nothing heard by Groq: not asked again elsewhere", not res.get("ok") and [c[0] for c in CALLS] == ["groq"], CALLS)
CALLS.clear()
SET["model"] = {}
res = run(main._stt_nghe(b"x" * 2000, "voice.mp3"))
check("no key at all: missing-key answer, nothing else called", res.get("ly_do") == "thieu_key" and len(CALLS) == 1, CALLS)
# the listener is a setting, not fixed (owner has not chosen yet)
SET.update({"model": {"groq_api_key": "gk", "openai_api_key": "sk-o"}})
GROQ_ANSWER = {"ok": True, "text": "nghe bằng Groq"}
for ear, want in (("groq", ["groq"]), ("openai", ["openai"]), ("auto", ["groq"])):
    CALLS.clear()
    SET["voice"] = {"chat_ear": ear}
    res = run(main._stt_nghe(b"x" * 2000, "voice.mp3"))
    check(f"chat_ear={ear}: asks {want}", res.get("ok") and [c[0] for c in CALLS] == want, CALLS)
CALLS.clear()
SET["voice"] = {"chat_ear": "offline"}
res = run(main._stt_nghe(b"x" * 2000, "voice.mp3"))
check("chat_ear=offline (not installed yet): says so, no online service called",
      not res.get("ok") and res.get("ly_do") == "chua_cai_offline" and CALLS == [], (res, CALLS))
SET["voice"] = {"chat_ear": "off"}
res = run(main._stt_nghe(b"x" * 2000, "voice.mp3"))
check("chat_ear=off: nothing called", not res.get("ok") and CALLS == [], CALLS)
check("unknown setting value falls back to auto", "}.get(ear, [\"groq\", \"openai\"])" in
      (Path(ROOT) / "server" / "main.py").read_text(encoding="utf-8"))
check("the Zalo bot is wired to the same listener at startup",
      "zalo_media.STT = _stt_nghe" in (Path(ROOT) / "server" / "main.py").read_text(encoding="utf-8"))

check("no em dash in the new module", "—" not in (Path(ROOT) / "server" / "zalo_media.py").read_text(encoding="utf-8"))
print()
if _fails:
    print(f"FAIL {len(_fails)}: {_fails}")
    sys.exit(1)
print("OK - test_zalo_voice_video_0449: all pass")
