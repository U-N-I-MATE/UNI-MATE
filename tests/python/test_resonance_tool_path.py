"""Resonance: unimate_goal phải tới được tay bộ não theo ĐÚNG đường mà prompt chỉ, trên từng engine.

    python tests/run.py resonance_tool_path

Lỗi thật, tìm ra khi kiểm bằng mã sau pilot lần 2 (07/10/2026): dòng gợi ý trong system prompt bảo
"chưa thấy tool thì tìm bằng unimate_search_tools". Trên engine Claude Code, plugin đi bằng MCP in-process
"unimate-plugins" và hub bị báo bỏ nhóm plugin (X-UniMate-No-Plugins), nên unimate_search_tools không bao giờ
trả về unimate_goal ở đó. Gợi ý đúng cho mọi engine trừ engine dùng nhiều nhất.

Test chỉ kiểm cơ chế (đăng ký, danh sách tới engine, đường tìm, nguồn tin người dùng). Nó KHÔNG chứng
minh model sẽ chọn đúng; việc đó chỉ pilot thật mới trả lời được. Không gọi model, không đọc settings thật.
"""
from _paths import ROOT, SERVER  # noqa: E402,F401
import asyncio
import json
import os
import tempfile
from pathlib import Path

os.environ["UNIMATE_STATE_DIR"] = tempfile.mkdtemp(prefix="unimate-res-toolpath-")

import claude_agent_sdk  # noqa: E402
import claude_sdk_engine  # noqa: E402
import luot_dang_chay  # noqa: E402
import main  # noqa: E402
import mcp_hub  # noqa: E402
import plugins_host  # noqa: E402

_fails = []


def check(name, cond):
    print(("ok   " if cond else "FAIL ") + name)
    if not cond:
        _fails.append(name)


import resonance_store as RS  # noqa: E402
import turn_context  # noqa: E402
import _resonance_agent as RA  # noqa: E402


def _brain():
    d = Path(tempfile.mkdtemp(prefix="brain-toolpath-")).resolve()
    (d / "UNI MATE").mkdir()
    return str(d)


# A1: "bật" là lượt của một agent đã bật Cộng hưởng (ngữ cảnh lượt), không còn là công tắc brain.
ON, OFF = _brain(), _brain()
AG = RA.enable(RS.GoalStore(), ON)


def _names(vault):
    return {t["fn"] for t in plugins_host.plugin_tools("full", vault, scope_vault=False)[0]}


def _in_agent_turn(fn):
    with RA.turn(AG, "sess-tp", 1, "x", ON):
        return fn()


def _in_plain_turn(fn):
    tok = turn_context.bind(turn_context.make("dashboard", chat_id="sess-plain", la_chu=True,
                                              session_id="sess-plain", message_id=1))
    try:
        return fn()
    finally:
        turn_context.reset(tok)


# 1. Đăng ký theo đúng lượt và brain
check("lượt của agent đã bật: plugin_tools có unimate_goal", "unimate_goal" in _in_agent_turn(lambda: _names(ON)))
check("lượt chat thường cùng brain: plugin_tools không có unimate_goal",
      "unimate_goal" not in _in_plain_turn(lambda: _names(ON)))
check("ngoài lượt (danh sách hub dùng chung), brain có agent bật: có unimate_goal (chỉ gợi ý)", "unimate_goal" in _names(ON))
check("brain không có agent nào bật: không có unimate_goal", "unimate_goal" not in _names(OFF))
check("không biết brain: không có unimate_goal", "unimate_goal" not in _names(None))

# 2. Danh sách tới engine Claude: server in-process "unimate-plugins", hub được báo bỏ plugin
_seen = {}
_real = claude_agent_sdk.create_sdk_mcp_server


def _spy(name, tools=None, **kw):
    _seen[name] = {getattr(t, "name", None): getattr(t, "description", "") for t in (tools or [])}
    return _real(name, tools=tools, **kw)


claude_agent_sdk.create_sdk_mcp_server = _spy
_cfg = Path(tempfile.mkdtemp(prefix="cfg-toolpath-")) / "mcp.json"
_cfg.write_text(json.dumps({"mcpServers": {"unimate": {"type": "http", "url": "http://127.0.0.1:1/mcp/hub",
                                                     "headers": {"X-UniMate-Engine": "claude"}}}}), encoding="utf-8")


def _servers(vault):
    _seen.clear()
    _desc_seen.clear()
    e = claude_sdk_engine.ClaudeSDK(cwd=vault or ON)
    e.mcp_config = str(_cfg)
    e.unimate_vault = vault
    out = e._mcp_servers()[0] or {}
    _desc_seen.update(_seen.get("unimate-plugins") or {})
    return out


_desc_seen = {}


try:
    s_on = _in_agent_turn(lambda: _servers(ON))
    desc_on = dict(_desc_seen)
    check("Claude: có server unimate-plugins", "unimate-plugins" in s_on)
    check("Claude: unimate-plugins mang unimate_goal", "unimate_goal" in _seen.get("unimate-plugins", []))
    check("Claude: hub nhận X-UniMate-No-Plugins=1",
          (s_on.get("unimate", {}).get("headers") or {}).get("X-UniMate-No-Plugins") == "1")
    _servers(OFF)
    desc_off = dict(_desc_seen)
    check("Claude, brain tắt: unimate-plugins không mang unimate_goal", "unimate_goal" not in _seen.get("unimate-plugins", []))
    _servers(None)
    check("Claude, chưa đặt unimate_vault: không mang unimate_goal (main._apply_mcp phải đặt)",
          "unimate_goal" not in _seen.get("unimate-plugins", []))
finally:
    claude_agent_sdk.create_sdk_mcp_server = _real


# 3. Đường tìm: hub tìm ra unimate_goal khi có plugin (engine API/Codex), KHÔNG khi đi đường Claude
async def _search(include_plugins):
    _, route = await mcp_hub.discover_all("full", vault_root=ON, include_plugins=include_plugins,
                                          include_ambient=not include_plugins, force_refresh=True, force_lazy=True)
    res = await route[mcp_hub._LAZY_SEARCH]["call"]({"query": "unimate_goal mục tiêu"})
    return "unimate_goal" in str(res)


check("hub có plugin (engine API/Codex): unimate_search_tools tìm ra unimate_goal", asyncio.run(_search(True)))
check("hub đường Claude (No-Plugins): unimate_search_tools KHÔNG tìm ra unimate_goal", not asyncio.run(_search(False)))

# 4. Prompt chỉ đúng đường cho từng engine (dòng gợi ý chỉ có trong lượt của agent đã bật)
p_on = _in_agent_turn(lambda: main.build_system_prompt(ON))
p_off = main.build_system_prompt(OFF)
check("lượt chat thường cùng brain: prompt không nhắc unimate_goal",
      "unimate_goal" not in _in_plain_turn(lambda: main.build_system_prompt(ON)))
_full = "mcp__unimate-plugins__unimate_goal"
check("prompt nêu ToolSearch kèm tên đầy đủ đúng server in-process",
      "ToolSearch" in p_on and _full in p_on and _full == "mcp__" + "unimate-plugins" + "__unimate_goal")
check("prompt vẫn nêu unimate_search_tools cho engine khác", "unimate_search_tools" in p_on)
check("prompt nêu đủ ranh giới: làm luôn, unimate_task, unimate_schedule, unimate_goal",
      all(x in p_on for x in ("làm luôn", "unimate_task", "unimate_schedule", "unimate_goal op=create")))
check("brain tắt: prompt không nhắc unimate_goal hay ToolSearch",
      "unimate_goal" not in p_off and _full not in p_off)

# 5. Mô tả tool THẬT SỰ tới engine Claude (metadata của server in-process), brain bật và tắt.
# Brain tắt Resonance không được nhận chỉ dẫn mới nào: mô tả unimate_task giữ nguyên, không nhắc unimate_goal
# (review PR #579, P2). Ranh giới chỉ nằm ở mô tả unimate_goal và dòng gợi ý, hai thứ chỉ có khi bật.
check("unimate_task: mô tả tới engine giống hệt nhau khi bật và khi tắt",
      bool(desc_on.get("unimate_task")) and desc_on.get("unimate_task") == desc_off.get("unimate_task"))
check("unimate_task: mô tả không nhắc unimate_goal hay ranh giới Resonance",
      "unimate_goal" not in desc_off.get("unimate_task", "") and "hết trách nhiệm" not in desc_off.get("unimate_task", ""))
check("brain tắt: engine không nhận unimate_goal", "unimate_goal" not in desc_off)
check("unimate_goal (brain bật): nhắc sửa theo phản hồi và chỉ việc một lần sang unimate_task",
      "sửa theo phản hồi" in desc_on.get("unimate_goal", "") and "unimate_task" in desc_on.get("unimate_goal", ""))

# 6. Nguồn tin người dùng: tool đọc đúng lượt đang chạy của brain
k = luot_dang_chay.bat_dau("web:sess-tp", ON, msg_id=11, user_text="lời thật của người dùng")
lu = luot_dang_chay.doan_luot(ON) or {}
check("lượt đang chạy: đúng phiên, id tin, lời người dùng",
      lu.get("chat_id") == "web:sess-tp" and int(lu.get("msg_id") or 0) == 11
      and lu.get("user_text") == "lời thật của người dùng")
check("A1: đọc lời theo ĐÚNG khoá (phiên, id tin) của ngữ cảnh lượt",
      luot_dang_chay.loi_cua_luot("web:sess-tp", 11, ON) == "lời thật của người dùng"
      and luot_dang_chay.loi_cua_luot("web:sess-tp", 12, ON) is None
      and luot_dang_chay.loi_cua_luot("web:khac", 11, ON) is None)
luot_dang_chay.ket_thuc(k)
check("hết lượt: không còn lượt để đoán", not luot_dang_chay.doan_luot(ON))
check("hết lượt: khoá chính xác cũng không còn", luot_dang_chay.loi_cua_luot("web:sess-tp", 11, ON) is None)

print(f"\n{'FAIL' if _fails else 'OK'}: {len(_fails)} lỗi")
raise SystemExit(1 if _fails else 0)
