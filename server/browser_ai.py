"""AI dùng chung khung trình duyệt (0.431.0).

Phần hai của việc chủ repo chốt 02/11/2026: "AI dùng CHUNG trình duyệt này: AI mở trang nào, khung hiện trang đó để anh
theo dõi và giành quyền bấm khi cần". Hai tool của hub, mọi engine đều gọi được:

- `unimate_browser_read` (chỉ đọc): danh sách tab, hoặc đọc trang đang mở thành chữ kèm danh sách phần tử bấm/gõ được,
  mỗi phần tử một số [n] để gọi lại.
- `unimate_browser` (hành động ra ngoài, mức quyền full): mở địa chỉ, bấm, gõ, bấm phím, cuộn, lùi/tiến, chọn/đóng tab.

Mọi thao tác đi qua ĐÚNG Chromium của khung (`browser_pane.TRINH_DUYET`), nên phiên đăng nhập là của chủ máy và người
đang mở khung thấy AI làm gì theo thời gian thực. Vì thế cả hai tool chỉ dành cho phiên của CHỦ (OWNER_ONLY_TOOLS):
bot nói chuyện với khách lạ không bao giờ được lái trình duyệt đang đăng nhập Gmail công ty.

Hai rào cứng:
- KHÔNG gõ vào ô mật khẩu. Mật khẩu do chủ máy tự gõ trong khung (chốt phạm vi 02/11/2026).
- Bấm bằng chuột thật (Input.dispatchMouseEvent) chứ không `el.click()` bằng mã: trang mở tab mới, tải tệp, chặn
  click giả... đều chạy đúng như người bấm.
"""
from __future__ import annotations

import asyncio
import json
import time
from pathlib import Path

import browser_pane

DOC_MAC_DINH = 12000
DOC_TOI_DA = 40000
PHAN_TU_TOI_DA = 200
CHO_TAI_GIAY = 15.0

_JS_DOC = r"""
(() => {
  const MAX = %d;
  document.querySelectorAll('[data-unimate-ref]').forEach(e => e.removeAttribute('data-unimate-ref'));
  const SEL = 'a[href],button,input,select,textarea,summary,[role=button],[role=link],[role=tab],[role=menuitem],' +
              '[role=checkbox],[role=radio],[role=option],[role=switch],[role=combobox],[role=textbox],' +
              '[contenteditable=""],[contenteditable=true],[onclick],[tabindex]:not([tabindex="-1"])';
  const out = [];
  let n = 0, bo = 0;
  for (const el of document.querySelectorAll(SEL)) {
    const r = el.getBoundingClientRect();
    if (r.width < 2 || r.height < 2) continue;
    const st = getComputedStyle(el);
    if (st.visibility === 'hidden' || st.display === 'none' || st.opacity === '0') continue;
    if (el.disabled || (el.tagName === 'INPUT' && el.type === 'hidden')) continue;
    if (n >= MAX) { bo++; continue; }
    n++;
    el.setAttribute('data-unimate-ref', String(n));
    const tag = el.tagName.toLowerCase();
    const type = (el.getAttribute('type') || '').toLowerCase();
    const role = el.getAttribute('role') || (tag === 'a' ? 'link' : tag === 'input' ? ('input' + (type ? ':' + type : '')) : tag);
    let ten = (el.getAttribute('aria-label') || el.innerText || el.getAttribute('placeholder') || el.title ||
               el.getAttribute('alt') || el.getAttribute('name') || '').trim().replace(/\s+/g, ' ').slice(0, 90);
    let gt = '';
    if ((tag === 'input' || tag === 'textarea') && type !== 'password' && el.value) gt = String(el.value).slice(0, 60);
    if (tag === 'select' && el.selectedOptions && el.selectedOptions[0]) gt = el.selectedOptions[0].text.slice(0, 60);
    if (type === 'checkbox' || type === 'radio') gt = el.checked ? 'checked' : 'unchecked';
    const ngoai = (r.bottom < 0 || r.top > innerHeight) ? ' (off-screen)' : '';
    out.push('[' + n + '] ' + role + ' "' + ten + '"' + (gt ? ' = "' + gt + '"' : '') +
             (tag === 'a' && el.getAttribute('href') ? ' -> ' + el.getAttribute('href').slice(0, 120) : '') + ngoai);
  }
  return JSON.stringify({title: document.title, url: location.href,
                         text: document.body ? document.body.innerText : '', elements: out, more: bo});
})()
"""

_JS_TAM = r"""
(() => {
  const el = document.querySelector('[data-unimate-ref="%d"]');
  if (!el) return JSON.stringify({err: 'missing'});
  el.scrollIntoView({block: 'center', inline: 'center'});
  const r = el.getBoundingClientRect();
  const pw = el.tagName === 'INPUT' && (el.getAttribute('type') || '').toLowerCase() === 'password';
  return JSON.stringify({x: r.left + r.width / 2, y: r.top + r.height / 2, pw: pw});
})()
"""

_JS_FOCUS = r"""
(() => {
  const el = document.querySelector('[data-unimate-ref="%d"]');
  if (!el) return 'missing';
  if (el.tagName === 'INPUT' && (el.getAttribute('type') || '').toLowerCase() === 'password') return 'password';
  el.scrollIntoView({block: 'center'});
  el.focus();
  if (%s) {
    if (typeof el.select === 'function' && (el.tagName === 'INPUT' || el.tagName === 'TEXTAREA')) el.select();
    else if (el.isContentEditable) document.execCommand('selectAll', false, null);
  }
  return 'ok';
})()
"""

# Phím người ta hay cần: tên -> (key, code, mã phím Windows, chữ sinh ra)
_PHIM = {
    "enter": ("Enter", "Enter", 13, "\r"), "tab": ("Tab", "Tab", 9, ""), "escape": ("Escape", "Escape", 27, ""),
    "backspace": ("Backspace", "Backspace", 8, ""), "delete": ("Delete", "Delete", 46, ""),
    "arrowup": ("ArrowUp", "ArrowUp", 38, ""), "arrowdown": ("ArrowDown", "ArrowDown", 40, ""),
    "arrowleft": ("ArrowLeft", "ArrowLeft", 37, ""), "arrowright": ("ArrowRight", "ArrowRight", 39, ""),
    "pageup": ("PageUp", "PageUp", 33, ""), "pagedown": ("PageDown", "PageDown", 34, ""),
    "home": ("Home", "Home", 36, ""), "end": ("End", "End", 35, ""), "space": (" ", "Space", 32, " "),
}


def _loi(s: str) -> str:
    return "ERROR: " + s


async def _san_sang(vault_root: str = "") -> browser_pane.TrinhDuyet:
    tb = browser_pane.TRINH_DUYET
    if not browser_pane.bat():
        raise RuntimeError("browser pane is turned off on this machine (UNIMATE_BROWSER_PANE=0)")
    if not tb.dang_chay():
        try:
            await tb.bat_dau()
        except RuntimeError as e:
            if str(e) == "no-browser":
                raise RuntimeError("this machine has no browser UNI MATE can drive: install Browser (Chromium) "
                                   "on the Tools page") from None
            raise
    tb.cham()
    if vault_root and not tb.nguoi_xem:
        # Không ai mở khung thì tệp AI tải về rơi vào brain đang làm việc.
        await tb.dat_thu_muc_tai(str(Path(vault_root) / "downloads"))
    for _ in range(50):
        if tb._session_dang_xem():
            break
        await asyncio.sleep(0.1)
    return tb


async def _eval(tb, expr: str, timeout: float = 15.0):
    s = tb._session_dang_xem()
    if not s:
        raise RuntimeError("no open tab")
    res = await tb.cdp.call("Runtime.evaluate", {"expression": expr, "returnByValue": True, "awaitPromise": True},
                            session=s, timeout=timeout)
    if res.get("exceptionDetails"):
        raise RuntimeError("page script failed: " + str((res["exceptionDetails"].get("exception") or {})
                                                        .get("description") or res["exceptionDetails"].get("text")))
    return (res.get("result") or {}).get("value")


async def _cho_tai(tb, giay: float = CHO_TAI_GIAY):
    """Chờ tab đang xem tải xong (hoặc hết giờ), cộng một nhịp ngắn cho trang vẽ xong phần chạy bằng mã."""
    await asyncio.sleep(0.4)
    het = time.time() + giay
    while time.time() < het:
        t = tb.tabs.get(tb.dang_xem)
        if t and not t.loading:
            break
        await asyncio.sleep(0.2)
    await asyncio.sleep(0.6)


def _tabs_text(tb) -> str:
    dong = []
    for i, tid in enumerate(tb.thu_tu, 1):
        t = tb.tabs.get(tid)
        if not t:
            continue
        dong.append(f"{i}. {'* ' if tid == tb.dang_xem else ''}{t.title or '(no title)'} - {t.url}")
    return "Tabs (* = active):\n" + ("\n".join(dong) if dong else "(none)")


def _tai_ve_text(tb) -> str:
    moi = [x for x in tb.da_tai if time.time() - x[0] < 600]
    if not moi:
        return ""
    return "\nDownloaded recently (vault folder downloads/): " + ", ".join(x[1] for x in moi[-5:])


async def _doc(tb, offset: int = 0, limit: int = DOC_MAC_DINH) -> str:
    raw = await _eval(tb, _JS_DOC % PHAN_TU_TOI_DA)
    try:
        d = json.loads(raw or "{}")
    except Exception:
        d = {}
    chu = str(d.get("text") or "")
    limit = max(500, min(int(limit or DOC_MAC_DINH), DOC_TOI_DA))
    offset = max(0, int(offset or 0))
    doan = chu[offset:offset + limit]
    con = len(chu) - (offset + len(doan))
    phan = "\n".join(d.get("elements") or [])
    if d.get("more"):
        phan += f"\n... {d['more']} more elements not listed (scroll or read again after narrowing)"
    return (f"Title: {d.get('title', '')}\nURL: {d.get('url', '')}\n\n--- Page text"
            f"{f' (from char {offset})' if offset else ''} ---\n{doan}"
            + (f"\n... {con} more characters: call again with offset={offset + len(doan)}" if con > 0 else "")
            + f"\n\n--- Clickable / typeable elements (use the number as ref) ---\n{phan or '(none)'}"
            + _tai_ve_text(tb))


async def _chuot(tb, x: float, y: float):
    s = tb._session_dang_xem()
    for loai, nut in (("mouseMoved", "none"), ("mousePressed", "left"), ("mouseReleased", "left")):
        await tb.cdp.call("Input.dispatchMouseEvent", {"type": loai, "x": x, "y": y, "button": nut,
                                                       "buttons": 1 if loai == "mousePressed" else 0,
                                                       "clickCount": 0 if loai == "mouseMoved" else 1}, session=s)


async def _phim(tb, ten: str):
    k = _PHIM.get(ten.lower().replace(" ", ""))
    if not k:
        raise RuntimeError(f"unknown key '{ten}'. Known: {', '.join(sorted(_PHIM))}")
    key, code, vk, chu = k
    s = tb._session_dang_xem()
    p = {"key": key, "code": code, "windowsVirtualKeyCode": vk, "nativeVirtualKeyCode": vk}
    await tb.cdp.call("Input.dispatchKeyEvent", dict(p, type="keyDown" if chu else "rawKeyDown",
                                                     **({"text": chu} if chu else {})), session=s)
    await tb.cdp.call("Input.dispatchKeyEvent", dict(p, type="keyUp"), session=s)


def _ref(args) -> int:
    try:
        return int(args.get("ref"))
    except (TypeError, ValueError):
        raise RuntimeError("ref must be the element number from unimate_browser_read") from None


async def doc_tool(args: dict, vault_root: str = "") -> str:
    """unimate_browser_read: op=tabs | read (mặc định)."""
    args = args or {}
    try:
        tb = await _san_sang(vault_root)
        await tb.lam_moi_tabs()
        if str(args.get("op") or "read") == "tabs":
            return _tabs_text(tb)
        return _tabs_text(tb) + "\n\n" + await _doc(tb, args.get("offset") or 0, args.get("limit") or DOC_MAC_DINH)
    except Exception as e:  # noqa: BLE001
        return _loi(f"{type(e).__name__}: {e}" if not isinstance(e, RuntimeError) else str(e))


async def lam_tool(args: dict, vault_root: str = "") -> str:
    """unimate_browser: open | click | type | press | scroll | back | forward | reload | select_tab | close_tab | wait."""
    args = args or {}
    op = str(args.get("op") or "").strip()
    try:
        tb = await _san_sang(vault_root)
        s = tb._session_dang_xem()
        if op == "open":
            url = str(args.get("url") or "").strip()
            if not url:
                return _loi("url is required")
            if args.get("new_tab", True) or not s:
                await tb.mo_tab(url)
            else:
                await tb.cdp.call("Page.navigate", {"url": browser_pane.chuan_hoa_dia_chi(url)}, session=s)
            await _cho_tai(tb)
        elif op == "click":
            if args.get("ref") is not None:
                raw = await _eval(tb, _JS_TAM % _ref(args))
                d = json.loads(raw or "{}")
                if d.get("err"):
                    return _loi("element not found: call unimate_browser_read again, the page changed")
                await asyncio.sleep(0.15)
                await _chuot(tb, float(d["x"]), float(d["y"]))
            elif args.get("x") is not None and args.get("y") is not None:
                await _chuot(tb, float(args["x"]), float(args["y"]))
            else:
                return _loi("click needs ref (or x and y)")
            await _cho_tai(tb, 8.0)
        elif op == "type":
            text = str(args.get("text") or "")
            if args.get("ref") is not None:
                kq = await _eval(tb, _JS_FOCUS % (_ref(args), "true" if args.get("clear", True) else "false"))
                if kq == "password":
                    return _loi("refused: UNI MATE never types into password fields. Ask the owner to type the "
                                "password themselves in the browser pane, then continue.")
                if kq != "ok":
                    return _loi("element not found: call unimate_browser_read again, the page changed")
            if text:
                await tb.cdp.call("Input.insertText", {"text": text[:20000]}, session=tb._session_dang_xem())
            if args.get("submit"):
                await _phim(tb, "enter")
                await _cho_tai(tb, 8.0)
            else:
                await asyncio.sleep(0.3)
        elif op == "press":
            await _phim(tb, str(args.get("key") or ""))
            await _cho_tai(tb, 5.0)
        elif op == "scroll":
            dy = int(args.get("amount") or 700) * (-1 if str(args.get("direction") or "down") == "up" else 1)
            w, h = tb.view
            await tb.cdp.call("Input.dispatchMouseEvent", {"type": "mouseWheel", "x": w / 2, "y": h / 2,
                                                           "deltaX": 0, "deltaY": dy}, session=s)
            await asyncio.sleep(0.6)
        elif op in ("back", "forward", "reload"):
            await tb.xu_ly({"type": op})
            await _cho_tai(tb)
        elif op in ("select_tab", "close_tab"):
            try:
                tid = tb.thu_tu[int(args.get("index")) - 1]
            except (TypeError, ValueError, IndexError):
                return _loi("index must be a tab number from op=tabs")
            if op == "select_tab":
                await tb.chon_tab(tid)
            else:
                await tb.dong_tab(tid)
                await asyncio.sleep(0.5)
            await tb.lam_moi_tabs()
            return _tabs_text(tb)
        elif op == "wait":
            await asyncio.sleep(max(0.5, min(float(args.get("seconds") or 2), 10.0)))
        else:
            return _loi("op must be one of: open, click, type, press, scroll, back, forward, reload, "
                        "select_tab, close_tab, wait")
        t = tb.tabs.get(tb.dang_xem)
        dau = f"Done ({op}). Active tab: {t.title if t else ''} - {t.url if t else ''}" + _tai_ve_text(tb)
        if args.get("read", True):
            return dau + "\n\n" + await _doc(tb, 0, args.get("limit") or DOC_MAC_DINH)
        return dau
    except Exception as e:  # noqa: BLE001
        return _loi(str(e) if isinstance(e, RuntimeError) else f"{type(e).__name__}: {e}")


MO_TA_DOC = ("Read the SHARED browser (the browser pane next to the chat, signed in as the owner): op='read' "
             "(default) returns the active page as text plus a numbered list of clickable/typeable elements; "
             "op='tabs' lists open tabs. Long pages: offset/limit. Use before unimate_browser click/type.")
MO_TA_LAM = ("Act in the SHARED browser the owner sees in the browser pane (signed in as the owner, e.g. company "
             "Gmail). op: open (url, new_tab default true) | click (ref from unimate_browser_read) | type (ref, text, "
             "clear default true, submit) | press (key: enter, tab, escape, arrowdown, pagedown...) | scroll "
             "(direction up/down, amount px) | back | forward | reload | select_tab / close_tab (index) | wait "
             "(seconds). Returns the page again after acting. Never types into password fields: ask the owner to "
             "sign in themselves in the pane. Files downloaded land in the vault folder downloads/.")
