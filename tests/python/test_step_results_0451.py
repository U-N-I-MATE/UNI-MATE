"""0.451.0: what each progress step produced, like Claude's steps (owner 2026-11-13).

    python tests/run.py step_results_0451

The owner's rule: pictures (screenshots, made or read pictures) show inside the step, Word/Excel/PDF/PowerPoint show as
a file card that opens in the viewer, code and commands get a few lines of text only. Checks:
  - server/step_media.build: pictures from every result shape (Anthropic block, MCP block, MCP JSON line in a text
    result), document cards, brain pictures, the shell/code rule, previews, secret masking, limits, no SVG;
  - the owner-only picture route and its name check, pictures deleted with the conversation;
  - every engine branch of the owner's chat sends tool_result with the step id (Claude Code, Codex, Grok Build,
    Antigravity, API engines), and the API loops only do it behind the opt-in switch.
"""
from _paths import ROOT, SERVER  # noqa: E402,F401
import asyncio
import base64
import json
import os
import re
import sys
import tempfile
import time
from pathlib import Path

STATE = tempfile.mkdtemp(prefix="unimate-step-results-")
os.environ["UNIMATE_STATE_DIR"] = STATE
try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

import step_media as sm  # noqa: E402

fails = []


def check(name, cond, extra=""):
    print(("ok   " if cond else "FAIL ") + name + ("" if cond or not extra else f"  [{extra}]"))
    if not cond:
        fails.append(name)


def read(rel):
    return (ROOT / rel).read_text(encoding="utf-8")


PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 64
B64 = base64.b64encode(PNG).decode()

# ---------------------------------------------------------------- pictures in results
b = sm.new_budget()
r = sm.build("mcp__playwright__browser_take_screenshot", {},
             [{"type": "text", "text": "Took a screenshot"},
              {"type": "image", "source": {"type": "base64", "media_type": "image/png", "data": B64}}],
             sid="sess1", budget=b)
check("screenshot (Anthropic block) becomes a picture of the step",
      len(r["imgs"]) == 1 and re.match(r"^/step-media/sess1/[0-9a-f]{32}\.png$", r["imgs"][0]["src"]), r)
check("its text stays as the step text", r["text"] == "Took a screenshot")
name = r["imgs"][0]["src"].rsplit("/", 1)[1]
p = sm.media_path("sess1", name)
check("picture written under STATE_DIR/step_media/<session>", p is not None and p.read_bytes() == PNG
      and str(p).startswith(STATE))

r2 = sm.build("browser_screenshot", {}, [{"type": "image", "data": B64, "mimeType": "image/png"}], sid="sess1", budget=b)
check("MCP picture block too", len(r2["imgs"]) == 1)
txt = "Saved\n" + json.dumps({"type": "image", "data": B64, "mimeType": "image/png"}) + "\nDone"
r3 = sm.build("browser_screenshot", {}, txt, sid="sess1", budget=sm.new_budget())
check("API engines: an MCP picture that arrived as a JSON line is a picture, and leaves the text",
      len(r3["imgs"]) == 1 and r3["text"] == "Saved\nDone", r3)
r4 = sm.build("codex", {}, {"type": "mcp_tool_call", "result": {"content": [
    {"type": "image", "data": B64, "mimeType": "image/png"}, {"type": "text", "text": "ok"}]}},
    sid="sess1", budget=sm.new_budget())
check("Codex MCP item: picture and text found inside result.content", len(r4["imgs"]) == 1 and r4["text"] == "ok", r4)

svg = base64.b64encode(b"<svg onload=alert(1)>").decode()
r5 = sm.build("x", {}, [{"type": "image", "data": svg, "mimeType": "image/svg+xml"}], sid="sess1",
              budget=sm.new_budget())
check("SVG is never accepted (it can carry script)", r5["imgs"] == [])
big = base64.b64encode(b"\x00" * (sm.MAX_IMG_BYTES + 1)).decode()
check("a picture over 5 MB is left out",
      sm.build("x", {}, [{"type": "image", "data": big, "mimeType": "image/png"}], sid="sess1",
               budget=sm.new_budget())["imgs"] == [])
bud = sm.new_budget()
for i in range(sm.MAX_IMGS_TURN + 3):
    one = base64.b64encode(PNG + bytes([i])).decode()
    sm.build("x", {}, [{"type": "image", "data": one, "mimeType": "image/png"}], sid="sess2", budget=bud)
check("at most 12 pictures per turn", bud["imgs"] == sm.MAX_IMGS_TURN and
      len(list((Path(STATE) / "step_media" / "sess2").iterdir())) == sm.MAX_IMGS_TURN)

# ---------------------------------------------------------------- documents and brain pictures
brain = Path(tempfile.mkdtemp(prefix="brain-"))
(brain / "exports").mkdir()
(brain / "attachments").mkdir()
doc = brain / "exports" / "De_xuat_mua_hang.docx"
doc.write_bytes(b"x")
(brain / "attachments" / "anh.png").write_bytes(PNG)
(brain / "exports" / "cu.pdf").write_bytes(b"x")
old = time.time() - 3 * 3600
os.utime(brain / "exports" / "cu.pdf", (old, old))

w = sm.build("Write", {"file_path": str(doc)}, "File created successfully", sid="s", brain_root=brain)
check("a Word file the step wrote becomes a card (name, kind, brain path)",
      w["files"] == [{"name": "De_xuat_mua_hang.docx", "path": "exports/De_xuat_mua_hang.docx", "kind": "Word"}], w)
rd = sm.build("Read", {"file_path": "exports/cu.pdf"}, "...", sid="s", brain_root=brain)
check("a PDF the step read is a card too, whatever its age", rd["files"] and rd["files"][0]["kind"] == "PDF")
sh_new = sm.build("Bash", {"command": "python make_doc.py"}, "Saved exports/De_xuat_mua_hang.docx", sid="s",
                  brain_root=brain)
check("a command that just wrote a document shows its card", len(sh_new["files"]) == 1)
sh_old = sm.build("Bash", {"command": "ls exports"}, "exports/cu.pdf", sid="s", brain_root=brain)
check("a command that only mentions an old document shows no card", sh_old["files"] == [])
gen = sm.build("unimate_generate_image", {"prompt": "x"}, "Đã tạo ảnh: attachments/anh.png", sid="s",
               brain_root=brain)
check("a picture made in the brain shows from the brain itself (no copy)",
      len(gen["imgs"]) == 1 and gen["imgs"][0]["src"].startswith("/files/raw?brain=")
      and gen["imgs"][0]["path"] == "attachments/anh.png", gen)
check("commands and code edits never get pictures guessed from paths (owner's rule)",
      sm.build("Bash", {"command": "cp a attachments/anh.png"}, "attachments/anh.png", sid="s", brain_root=brain)["imgs"]
      == [] and sm.build("Edit", {"file_path": "attachments/anh.png"}, "", sid="s", brain_root=brain)["imgs"] == [])
out = sm.build("Read", {"file_path": "../../etc/passwd.pdf"}, "", sid="s", brain_root=brain)
check("nothing outside the brain becomes a card", out["files"] == [])
check("a code file gets no card at all",
      sm.build("Write", {"file_path": str(brain / "a.py")}, "", sid="s", brain_root=brain)["files"] == [])

# ---------------------------------------------------------------- text
many = "\n".join("dòng %d" % i for i in range(20))
pv = sm.build("Bash", {"command": "x"}, many, sid="s")
check("text preview keeps the first 6 lines and counts the rest", pv["text"].count("\n") == 5 and pv["more"] == 14, pv)
check("preview capped at 600 characters", len(sm.build("x", {}, "a" * 5000, sid="s")["text"]) <= sm.PREVIEW_CHARS)
key = "sk-ant-api03-" + "A" * 40
sec = sm.build("Bash", {}, "TOKEN=" + key, sid="s")
check("keys and passwords are masked before the text leaves the server", key not in sec["text"], sec["text"])
check("ANSI colour codes stripped", sm.build("x", {}, "\x1b[31mred\x1b[0m", sid="s")["text"] == "red")
check("an error result is flagged", sm.build("x", {}, "ERROR: tool failed", sid="s")["err"] is True
      and sm.build("x", {}, "ok", sid="s", is_error=True)["err"] is True)
check("Codex: a silent command shows nothing, a file change one line per file",
      sm.build("command_execution", {}, {"type": "command_execution", "aggregated_output": ""}, sid="s")["text"] == ""
      and sm.build("file_change", {}, {"changes": [{"path": "a.py", "kind": "update"}]}, sid="s")["text"]
      == "a.py (update)"
      and sm.build("pos", {}, {"id": "i2", "type": "mcp_tool_call", "tool": "pos"}, sid="s")["text"] == "")

# ---------------------------------------------------------------- route and deletion
check("route name check: only 32 hex + a picture extension",
      sm.media_path("sess1", "../../settings.json") is None and sm.media_path("sess1", name.upper()) is None
      and sm.media_path("../x", name) is None and sm.media_path("sess1", name[:-4] + ".svg") is None)
main_src = read("server/main.py")
route = main_src[main_src.index('@app.get("/step-media/{session_id}/{name}")'):]
check("route serves only through media_path, with nosniff, no SVG type",
      "step_media.media_path(session_id, name)" in route and "nosniff" in route and "svg" not in route[:900])
check("route is not on the public list (sign-in wall applies)",
      "/step-media" not in main_src[main_src.index("_AUTH_PUBLIC_EXACT"):main_src.index("_AUTH_PUBLIC_EXACT") + 3000])
sm.drop("sess1")
check("drop() deletes a conversation's pictures", not (Path(STATE) / "step_media" / "sess1").exists())
check("deleting a conversation drops its pictures",
      "step_media.drop(session_id)" in read("server/sessions.py"))

# ---------------------------------------------------------------- engines
for label, marker in [("Grok Build", "kcli.query(_k_prompt)"), ("Antigravity", "acli.query(_a_prompt)"),
                      ("Codex", "ccli.query(prompt)"), ("Claude Code", "claude_warm.query(cli, prompt, conv_sid)"),
                      ("API engines", "async for ev in _with_step_results(gen)")]:
    i = main_src.index(marker)
    seg = main_src[i - 400:i + 6000]
    check(f"{label}: step state per turn, tool_call carries the step id, tool_result frame built",
          "_step_state()" in seg and '"id": _step_call(_st, ' in seg and "_step_result_frame(" in seg)
eng = read("server/engine.py")
yields = [m.start() for m in re.finditer(r'^\s+yield \{"type": "tool_result"', eng, re.M)]
check("API loops: tool_result yielded in all three loops, each behind STEP_RESULTS",
      len(yields) == 3 and all("if STEP_RESULTS.get():" in eng[y - 120:y] for y in yields))
check("API loops: tool_call carries the provider's call id",
      eng.count('"id": str(tc.get("id") or "")}') >= 1 and '"id": str(fc.get("call_id") or "")}' in eng
      and '"id": str(tu.get("id") or "")}' in eng)
import hashlib  # noqa: E402
pin = json.loads(read("docs/superpowers/evidence/2026-11-01-unimate01b-native-qualification-cli310.json"))
check("claude_sdk_engine.py is untouched (pinned by the native qualification evidence)",
      hashlib.sha256((ROOT / "server/claude_sdk_engine.py").read_bytes()).hexdigest()
      == pin["source_hashes"]["claude_sdk_engine.py"])

# Claude Code: the wrapper in claude_cli adds `raw` from the SDK's ToolResultBlock, run here on fake SDK objects.
import types  # noqa: E402
import claude_cli  # noqa: E402


class ToolResultBlock:
    def __init__(self, tid, content):
        self.tool_use_id, self.content, self.is_error = tid, content, False


class UserMessage:
    def __init__(self, content):
        self.content = content


def _orig_map(msg):
    return [{"type": "tool_result", "content": "short", "tool_use_id": b.tool_use_id} for b in msg.content], None


fake = types.ModuleType("claude_sdk_engine")
fake.map_message = _orig_map
_real = sys.modules.get("claude_sdk_engine")
sys.modules["claude_sdk_engine"] = fake
try:
    claude_cli._cai_ket_qua_buoc()
    claude_cli._cai_ket_qua_buoc()
    depth, f = 0, fake.map_message
    while f is not None:
        depth, f = depth + 1, getattr(f, "__wrapped__", None)
    evs, _ = fake.map_message(UserMessage([
        ToolResultBlock("u1", [{"type": "text", "text": "z" * 9000},
                               {"type": "image", "source": {"type": "base64", "media_type": "image/png", "data": B64}}]),
        ToolResultBlock("u2", "plain")]))
finally:
    if _real is not None:
        sys.modules["claude_sdk_engine"] = _real
    else:
        sys.modules.pop("claude_sdk_engine", None)
check("Claude Code wrapper: installed once even when called twice", depth == 2, depth)
check("Claude Code wrapper: `raw` keeps the picture block and 4000 characters, `content` untouched",
      evs[0]["content"] == "short" and len(evs[0]["raw"][0]["text"]) == 4000 and evs[0]["raw"][1]["type"] == "image"
      and evs[1]["raw"] == "plain", evs)
cli_src = read("server/claude_cli.py")
check("Claude Code wrapper goes on before plan_limits, like the cache counter",
      cli_src.index("_cai_dem_cache()\n") < cli_src.index("_cai_ket_qua_buoc()\n") < cli_src.index("plan_limits.cai_vao_claude_sdk()"))

# The switch and the frame helper, run for real without importing the whole server.
import engine  # noqa: E402
ns = {"engine": engine, "step_media": sm, "_brain_root": lambda b: b}
src = main_src[main_src.index("async def _with_step_results(gen):"):main_src.index("def _step_result_frame(")]
src += main_src[main_src.index("def _step_result_frame("):main_src.index("\nimport ", main_src.index("def _step_result_frame("))]
exec(src, ns)  # noqa: S102 - our own source


async def inner():
    yield engine.STEP_RESULTS.get()
    yield engine.STEP_RESULTS.get()


async def run():
    seen = []
    async for v in ns["_with_step_results"](inner()):
        seen.append((v, engine.STEP_RESULTS.get()))
    return seen

got = asyncio.run(run())
check("switch is on inside the engine stream and off again in the caller between steps",
      got == [(True, False), (True, False)], got)

st = ns["_step_state"]()
a = ns["_step_call"](st, {"name": "Read", "id": "t1", "input": {}})
c = ns["_step_call"](st, {"name": "Bash", "input": {"command": "ls"}})
f1 = ns["_step_result_frame"](st, {"type": "tool_result"}, "first out", "s", None)
check("a result without id closes the oldest open step", f1["id"] == "t1" and f1["res"]["text"] == "first out")
f2 = ns["_step_result_frame"](st, {"type": "tool_result", "id": c}, "x" * 900, "s", None)
check("a result with an id closes that step; `content` stays 200 characters for old dashboards",
      f2["id"] == c and len(f2["content"]) == 200 and st["open"] == [])

print()
if fails:
    print(f"FAIL {len(fails)}: " + " | ".join(fails))
    sys.exit(1)
print("OK - test_step_results_0451: all pass")
