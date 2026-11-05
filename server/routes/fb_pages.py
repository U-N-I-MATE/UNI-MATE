"""Routes of the Facebook Page comments card (0.448.0). The logic lives in `fb_pages`; this file is HTTP only.

    GET  /facebook-pages/setup            what the card shows (no token, no secret)
    POST /facebook-pages/app              save App ID, App Secret, optional Configuration ID
    GET  /facebook-pages/login            redirect to the Facebook login dialog
    GET  /facebook-pages/oauth/callback   Facebook sends the owner back here: list the Pages to tick
    POST /facebook-pages/pick             connect the ticked Pages
    POST /facebook-pages/watch            record a Page to the inbox or pause it
    POST /facebook-pages/read-now         read one Page now
    POST /facebook-pages/follow           follow an older post (an ad running on it)
    POST /facebook-pages/unfollow
    POST /facebook-pages/retention        how many months comments are kept
    POST /facebook-pages/disconnect       first call counts, `confirm: true` deletes

The callback and the pick page are plain server pages: Facebook sends the browser to a fixed address, and the owner
only has to tick Pages there. Every route sits behind the sign-in wall like the rest of the dashboard.
"""
from __future__ import annotations

import html

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse

import fb_pages
import localefmt
import web_security

router = APIRouter()


def _base(request: Request) -> str:
    return web_security.external_base(request.url.scheme, request.url.netloc,
                                      request.headers.get("x-forwarded-proto", ""),
                                      request.headers.get("x-forwarded-host", ""))


async def _body(request: Request) -> dict:
    try:
        b = await request.json()
    except Exception:
        b = {}
    return b if isinstance(b, dict) else {}


def _res(r: dict):
    return r if r.get("ok") else JSONResponse(r, status_code=400)


def _page(title: str, inner: str, status: int = 200) -> HTMLResponse:
    css = ("body{font-family:system-ui,-apple-system,Segoe UI,Roboto,sans-serif;background:#f6f7f9;color:#1c1e21;"
           "margin:0;padding:24px 16px}main{max-width:520px;margin:0 auto;background:#fff;border-radius:14px;"
           "padding:22px 20px;box-shadow:0 1px 3px rgba(0,0,0,.08)}h1{font-size:19px;margin:0 0 12px}"
           "p{line-height:1.5}label{display:flex;gap:10px;align-items:center;padding:10px 0;border-top:1px solid #eee}"
           ".tag{font-size:12px;color:#65676b}button{margin-top:16px;background:#1877F2;color:#fff;border:0;"
           "border-radius:8px;padding:10px 18px;font-size:15px;cursor:pointer}a{color:#1877F2}"
           "@media (prefers-color-scheme:dark){body{background:#18191a;color:#e4e6eb}main{background:#242526}"
           "label{border-color:#3a3b3c}.tag{color:#b0b3b8}}")
    doc = (f'<!doctype html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,'
           f'initial-scale=1"><title>{html.escape(title)}</title><style>{css}</style></head><body><main>'
           f'<h1>{html.escape(title)}</h1>{inner}</main></body></html>')
    return HTMLResponse(doc, status_code=status)


def _back() -> str:
    return f'<p><a href="/">{html.escape(localefmt.chu("Quay về UNI MATE", "Back to UNI MATE"))}</a></p>'


def register(app) -> None:
    @router.get("/facebook-pages/setup")
    async def fb_setup(request: Request):
        return fb_pages.view(_base(request))

    @router.post("/facebook-pages/app")
    async def fb_app(request: Request):
        b = await _body(request)
        return _res(fb_pages.set_app(b.get("app_id"), b.get("app_secret") or "", b.get("config_id")))

    @router.get("/facebook-pages/login")
    async def fb_login(request: Request):
        r = fb_pages.login_url(_base(request))
        if not r.get("ok"):
            return _page(localefmt.chu("Chưa đăng nhập Facebook được", "Cannot log in with Facebook yet"),
                         f"<p>{html.escape(r.get('error') or '')}</p>" + _back(), 400)
        return RedirectResponse(r["url"], status_code=302)

    @router.get("/facebook-pages/oauth/callback")
    async def fb_callback(request: Request, code: str = "", state: str = "", error: str = "",
                          error_description: str = ""):
        if error or not code:
            why = error_description or localefmt.chu("Đã huỷ đăng nhập hoặc Facebook từ chối.", "You cancelled or Facebook refused.")
            return _page(localefmt.chu("Chưa nối được trang", "No Page connected"),
                         f"<p>{html.escape(why)}</p>" + _back(), 400)
        r = await fb_pages.exchange_code(code, state)
        if not r.get("ok"):
            return _page(localefmt.chu("Chưa nối được trang", "No Page connected"),
                         f"<p>{html.escape(r.get('error') or '')}</p>" + _back(), 400)
        rows = []
        for p in r["pages"]:
            tag = html.escape(localefmt.chu("đã nối, nối lại để làm mới đăng nhập", "connected, ticking renews the login")) \
                if p["connected"] else ""
            rows.append(f'<label><input type="checkbox" name="page_id" value="{html.escape(p["id"])}"'
                        f'{" checked" if p["connected"] else ""}><span>{html.escape(p["name"])}'
                        + (f'<br><span class="tag">{tag}</span>' if tag else "") + "</span></label>")
        note = localefmt.chu("Chọn trang để đọc bình luận vào Hộp thư. Trang không chọn giữ nguyên như cũ.",
                             "Tick the Pages whose comments go to the inbox. Pages left unticked stay as they are.")
        inner = (f"<p>{html.escape(note)}</p><form method=\"post\" action=\"/facebook-pages/pick\">"
                 f'<input type="hidden" name="nonce" value="{html.escape(r["nonce"])}">' + "".join(rows)
                 + f'<button type="submit">{html.escape(localefmt.chu("Nối các trang đã chọn", "Connect the ticked Pages"))}'
                 "</button></form>")
        return _page(localefmt.chu("Chọn trang Facebook", "Pick your Facebook Pages"), inner)

    @router.post("/facebook-pages/pick")
    async def fb_pick(request: Request):
        form = await request.form()
        r = fb_pages.pick(str(form.get("nonce") or ""), [str(x) for x in form.getlist("page_id")])
        if not r.get("ok"):
            return _page(localefmt.chu("Chưa nối được trang", "No Page connected"),
                         f"<p>{html.escape(r.get('error') or '')}</p>" + _back(), 400)
        msg = localefmt.chu("Đã nối {a} trang mới, làm mới đăng nhập {b} trang. Bình luận về Hộp thư trong vài phút.",
                            "Connected {a} new Page(s), renewed the login of {b}. Comments reach the inbox within minutes.",
                            a=len(r["added"]), b=len(r["renewed"]))
        return _page(localefmt.chu("Đã nối", "Connected"), f"<p>{html.escape(msg)}</p>" + _back())

    @router.post("/facebook-pages/watch")
    async def fb_watch(request: Request):
        b = await _body(request)
        return _res(fb_pages.set_watch(str(b.get("page_id") or ""), bool(b.get("on"))))

    @router.post("/facebook-pages/read-now")
    async def fb_read_now(request: Request):
        b = await _body(request)
        pid = str(b.get("page_id") or "")
        if not fb_pages.has_page(pid):
            return JSONResponse({"ok": False, "error": localefmt.chu("Không có trang này.", "No such Page.")}, status_code=400)
        r = await fb_pages.poll_page(pid)
        return {"ok": bool(r.get("ok")), "new": r.get("new", 0), "error": r.get("error", "")}

    @router.post("/facebook-pages/follow")
    async def fb_follow(request: Request):
        b = await _body(request)
        return _res(await fb_pages.follow(str(b.get("page_id") or ""), str(b.get("url") or "")))

    @router.post("/facebook-pages/unfollow")
    async def fb_unfollow(request: Request):
        b = await _body(request)
        return _res(fb_pages.unfollow(str(b.get("page_id") or ""), str(b.get("post_id") or "")))

    @router.post("/facebook-pages/retention")
    async def fb_retention(request: Request):
        b = await _body(request)
        return _res(fb_pages.set_retention(b.get("months")))

    @router.post("/facebook-pages/disconnect")
    async def fb_disconnect(request: Request):
        b = await _body(request)
        return _res(fb_pages.disconnect(str(b.get("page_id") or ""), bool(b.get("confirm"))))

    app.include_router(router)
