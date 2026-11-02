"""Khung trình duyệt cạnh khung chat (0.430.0).

    python tests/run.py browser_pane

Hai phần:
1. TĨNH (luôn chạy): các bất biến mà vi phạm là hỏng thật hoặc hở bảo mật - websocket tự kiểm đăng nhập trước khi
   accept (trình duyệt giữ phiên đăng nhập thật của chủ máy), cổng DevTools chỉ nghe 127.0.0.1, lệnh bật Chromium
   không bung cửa sổ console trên Windows, ô địa chỉ không chạy được `javascript:`, dashboard có đủ nút/khung/chữ.
2. CHẠY THẬT (khi máy có Chrome/Chromium, như máy chạy CI của GitHub): bật trình duyệt bằng chính lớp TrinhDuyet,
   mở trang, nhận khung hình, gõ chữ có dấu vào ô nhập, mở tab mới bằng liên kết target=_blank, tắt. Máy không có
   trình duyệt thì phần này báo bỏ qua chứ không đỏ.
"""
from _paths import ROOT, SERVER  # noqa: E402,F401
import asyncio
import os
import re
import sys
import tempfile

os.environ.setdefault("UNIMATE_STATE_DIR", tempfile.mkdtemp(prefix="unimate-bptest-"))

_fails = []


def check(ten, cond, them=""):
    print(("ok   " if cond else "FAIL ") + ten + (("  [" + str(them) + "]") if them and not cond else ""))
    if not cond:
        _fails.append(ten)


SRV = (ROOT / "server" / "browser_pane.py").read_text(encoding="utf-8")
RT = (ROOT / "server" / "routes" / "browser.py").read_text(encoding="utf-8")
MAIN = (ROOT / "server" / "main.py").read_text(encoding="utf-8")
JS = (ROOT / "dashboard" / "browser-pane.js").read_text(encoding="utf-8")
HTML = (ROOT / "dashboard" / "index.html").read_text(encoding="utf-8")
CSS = (ROOT / "dashboard" / "style.css").read_text(encoding="utf-8")

# ---- 1. Bảo mật và bất biến phía máy chủ ----
i_gate = RT.find("cfgmod.gate_active()")
i_accept = RT.find("await ws.accept()")
check("CANARY: /ws/browser kiểm đăng nhập TRƯỚC khi accept (trình duyệt giữ phiên đăng nhập thật)",
      0 < i_gate < i_accept and "valid_session" in RT[i_gate:i_accept])
check("cổng DevTools ngẫu nhiên, chỉ đọc qua DevToolsActivePort, nối qua 127.0.0.1",
      '"--remote-debugging-port=0"' in SRV and "ws://127.0.0.1:" in SRV and "DevToolsActivePort" in SRV)
check("không mở cổng DevTools ra mọi địa chỉ", "--remote-debugging-address" not in SRV)
check("bật Chromium không bung cửa sổ console trên Windows", "creationflags=winproc.no_window()" in SRV)
check("hồ sơ riêng trong STATE_DIR (đăng nhập sống qua cập nhật)", 'PROFILE_DIR = cfgmod.STATE_DIR / "browser-profile"' in SRV)
check("file chạy lấy từ cùng nguồn sự thật với trang Công cụ", "optional_tools.duong_dan_chrome()" in SRV)
check("tắt được bằng UNIMATE_BROWSER_PANE=0", "UNIMATE_BROWSER_PANE" in SRV and "browser_pane.bat()" in RT)
check("main đăng ký routes/browser", "browser_routes.register(app, browser_routes.BrowserDeps(" in MAIN)
HUB = (ROOT / "server" / "mcp_hub.py").read_text(encoding="utf-8")
_owner = HUB[HUB.index("OWNER_ONLY_TOOLS = frozenset("):HUB.index("})", HUB.index("OWNER_ONLY_TOOLS = frozenset("))]
check("CANARY: tool lái trình duyệt chỉ dành cho phiên của chủ (bot của khách không bao giờ thấy)",
      '"unimate_browser_read"' in _owner and '"unimate_browser"' in _owner)
check("tool hành động ở mức quyền full, tool đọc ở mức chỉ đọc",
      re.search(r'add\("unimate_browser", browser_ai\.MO_TA_LAM,.*?effect="full"\)', HUB, re.S) is not None
      and re.search(r'add\("unimate_browser_read", browser_ai\.MO_TA_DOC,[^)]*\], _browser_read\)', HUB) is not None)
check("thao tác chuột/phím đi làn riêng, không đứng sau việc chậm", "hang.put_nowait(m)" in RT and "NHANH" in RT)

sys.path.insert(0, str(ROOT / "server"))
import browser_pane as bp  # noqa: E402

cases = {
    "example.com": "https://example.com",
    "mail.google.com/mail/u/0": "https://mail.google.com/mail/u/0",
    "localhost:8688": "http://localhost:8688",
    "127.0.0.1:8791/a.html": "http://127.0.0.1:8791/a.html",
    "https://ecoditas.vn": "https://ecoditas.vn",
    "about:blank": "about:blank",
    "": "about:blank",
}
for vao, ra in cases.items():
    check(f"địa chỉ {vao!r} -> {ra}", bp.chuan_hoa_dia_chi(vao) == ra, bp.chuan_hoa_dia_chi(vao))
check("gõ cụm từ thì tìm Google", bp.chuan_hoa_dia_chi("doanh số MT").startswith("https://www.google.com/search?q="))
check("CANARY: javascript: ở ô địa chỉ KHÔNG chạy mã, thành tìm kiếm",
      bp.chuan_hoa_dia_chi("javascript:alert(1)").startswith("https://www.google.com/search?q="))
check("chrome:// (trang nội bộ trình duyệt) không mở từ ô địa chỉ",
      bp.chuan_hoa_dia_chi("chrome://settings").startswith("https://www.google.com/search?q="))

# ---- 2. Dashboard ----
check("có nút bật khung trên thanh trên cùng", 'id="browserPaneBtn"' in HTML and 'data-ic="globe"' in HTML)
check("có khung trong khoang giữa", 'id="browserPane"' in HTML)
check("nạp browser-pane.js", "/static/browser-pane.js" in HTML)
check("khung nằm DƯỚI trình sửa note (mở note thì note nổi lên)",
      re.search(r"\.browser-pane \{[^}]*z-index: 11", CSS) is not None and ".note-editor { position: absolute; inset: 0; z-index: 12" in CSS)
check("ô nhận bàn phím trong suốt phủ canvas (bộ gõ tiếng Việt gõ vào đây)", ".bp-ime {" in CSS and "compositionend" in JS)
check("dán chữ đi qua sự kiện paste", '"paste"' in JS and 'type: "text"' in JS)
check("hộp thoại của trang nổi trên hình, không chen bố cục", re.search(r"\.bp-dialog \{ position: absolute", CSS) is not None)
check("chữ trên màn hình qua t(), không gõ tiếng Việt trần trong mã chạy",
      not re.search(r"['\"][^'\"\n]*[ăâđêôơưạảấầẩẫậắằẳẵặẹẻẽếềểễệỉịọỏốồổỗộớờởỡợụủứừửữựỳỵỷỹ][^'\"\n]*['\"]",
                    "\n".join(ln for ln in JS.splitlines() if not ln.strip().startswith(("//", "*", "/*")))))
import json  # noqa: E402
vi = json.loads((ROOT / "dashboard" / "i18n" / "vi.json").read_text(encoding="utf-8"))
en = json.loads((ROOT / "dashboard" / "i18n" / "en.json").read_text(encoding="utf-8"))
khoa = sorted(set(re.findall(r't\("(bp\.[a-z_]+)"', JS)) | set(re.findall(r'"(bp\.[a-z_]+)"', HTML)))
thieu = [k for k in khoa if k not in vi or k not in en]
check("mọi khoá bp.* có đủ vi và en", khoa and not thieu, thieu)
for ten, s in (("browser_pane.py", SRV), ("routes/browser.py", RT), ("browser-pane.js", JS)):
    check(f"{ten} không dùng em dash", "—" not in s)


# ---- 3. Chạy thật khi máy có trình duyệt ----
async def chay_that():
    tb = bp.TRINH_DUYET
    if not tb.file_chay():
        print("bỏ qua phần chạy thật: máy này không có Chrome/Chromium")
        return
    nhan = {"khung": 0, "tin": []}

    async def gui_chu(s):
        nhan["tin"].append(json.loads(s))

    async def gui_anh(b):
        nhan["khung"] += 1

    # Trang thử phục vụ từ một máy chủ HTTP tại chỗ: Chromium chặn trang mở tab mới tới địa chỉ data:.
    import http.server
    import threading

    TRANG = {
        "/": "<meta charset=utf-8><title>Trang thu</title><input id=q>"
             "<a id=l href='/hai' target=_blank style='display:block;position:absolute;left:0;top:100px;"
             "width:300px;height:60px'>mo</a>",
        "/hai": "<meta charset=utf-8><title>Hai</title>hai",
        "/form": "<meta charset=utf-8><title>Dang nhap</title><input id=u placeholder='Ten dang nhap'>"
                 "<input id=p type=password placeholder='Mat khau'><button onclick=\"document.title='Gui '+u.value\">Gui</button>",
    }

    class H(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            body = TRANG.get(self.path, "").encode("utf-8")
            self.send_response(200 if body else 404)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *a):
            pass

    may = http.server.ThreadingHTTPServer(("127.0.0.1", 0), H)
    threading.Thread(target=may.serve_forever, daemon=True).start()
    trang = f"http://127.0.0.1:{may.server_address[1]}/"
    try:
        await asyncio.wait_for(tb.bat_dau(), 40)
        check("bật được trình duyệt", tb.dang_chay())
        nx = bp.NguoiXem(gui_chu, gui_anh)
        tb.them_nguoi_xem(nx)
        await tb.xu_ly({"type": "nav", "url": trang})
        for _ in range(50):
            await asyncio.sleep(0.2)
            t = tb.tabs.get(tb.dang_xem)
            if t and t.title == "Trang thu" and nhan["khung"]:
                break
        t = tb.tabs.get(tb.dang_xem)
        check("tab nhận đúng tiêu đề trang", bool(t) and t.title == "Trang thu", t and t.title)
        check("có khung hình gửi về", nhan["khung"] > 0)
        s = tb._session_dang_xem()
        await tb.cdp.call("Runtime.evaluate", {"expression": "document.getElementById('q').focus()"}, session=s)
        await tb.xu_ly({"type": "text", "text": "Việt Nam "})
        await tb.xu_ly({"type": "key", "ev": "down", "key": "a", "code": "KeyA", "keyCode": 65, "text": "a"})
        await tb.xu_ly({"type": "key", "ev": "up", "key": "a", "code": "KeyA", "keyCode": 65})
        await asyncio.sleep(0.6)
        r = await tb.cdp.call("Runtime.evaluate", {"expression": "document.getElementById('q').value",
                                                   "returnByValue": True}, session=s)
        gt = (r.get("result") or {}).get("value")
        check("gõ chữ có dấu và phím thường vào ô nhập", gt == "Việt Nam a", gt)
        so_tab = len(tb.tabs)
        for ev in ("down", "up"):
            await tb.xu_ly({"type": "mouse", "ev": ev, "x": 50, "y": 120, "button": "left",
                            "buttons": 1 if ev == "down" else 0, "clicks": 1})
        for _ in range(40):
            await asyncio.sleep(0.2)
            if len(tb.tabs) > so_tab and tb.tabs.get(tb.dang_xem) and tb.tabs[tb.dang_xem].title == "Hai":
                break
        check("liên kết target=_blank mở tab mới và chọn ngay", len(tb.tabs) > so_tab
              and tb.tabs.get(tb.dang_xem) is not None and tb.tabs[tb.dang_xem].title == "Hai",
              [(x.title, x.url[:30]) for x in tb.tabs.values()])
        moi = tb.dang_xem
        await tb.dong_tab(moi)
        for _ in range(20):
            await asyncio.sleep(0.2)
            if moi not in tb.tabs and tb.dang_xem:
                break
        check("đóng tab thì quay về tab đã mở ra nó", moi not in tb.tabs and tb.tabs.get(tb.dang_xem) is not None
              and tb.tabs[tb.dang_xem].title == "Trang thu")
        tb.bo_nguoi_xem(nx)

        # ---- AI dùng chung trình duyệt (browser_ai) ----
        import browser_ai
        kq = await browser_ai.lam_tool({"op": "open", "url": trang + "form"})
        check("AI mở trang ở tab mới và đọc lại được trang", "Title: Dang nhap" in kq and "[1] input" in kq, kq[:300])
        so = {ln.split(']')[0][1:]: ln for ln in kq.splitlines() if ln.startswith("[")}
        ref_u = next((k for k, v in so.items() if "Ten dang nhap" in v), None)
        ref_p = next((k for k, v in so.items() if "Mat khau" in v), None)
        ref_b = next((k for k, v in so.items() if '"Gui"' in v), None)
        kq = await browser_ai.lam_tool({"op": "type", "ref": int(ref_p or 0), "text": "bimat"})
        check("CANARY: AI không gõ vào ô mật khẩu", kq.startswith("ERROR: refused"), kq[:200])
        await browser_ai.lam_tool({"op": "type", "ref": int(ref_u or 0), "text": "Huấn"})
        kq = await browser_ai.lam_tool({"op": "click", "ref": int(ref_b or 0)})
        check("AI gõ chữ có dấu rồi bấm nút bằng chuột thật", "Title: Gui Huấn" in kq, kq[:200])
        kq = await browser_ai.doc_tool({"op": "tabs"})
        check("AI liệt kê tab, đánh dấu tab đang xem", "* Gui Huấn" in kq, kq)
    finally:
        await tb.tat()
        may.shutdown()
    check("tắt sạch", not tb.dang_chay() and tb.proc is None)


asyncio.run(chay_that())

print()
if _fails:
    print(f"{len(_fails)} test HỎNG: " + ", ".join(_fails))
    sys.exit(1)
print("Tất cả test browser_pane đã qua.")
