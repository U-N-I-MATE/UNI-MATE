"""Facebook Page comments in the inbox, read only (0.448.0).

Owner's decision 05/11/2026 (UNI-PV-01, three Pages: Excel files, slides, golf products). The app stays in Meta's
development mode, so:

  - Webhooks only carry events made by people with a role on the app, so a customer's comment is never pushed. UNI MATE
    READS each Page on a timer instead (`INTERVAL_S`, 3 minutes).
  - Graph leaves out `from` (who commented) for people without a role on the app. A comment comes in as
    "Facebook user". Once Meta grants Advanced Access to Business Asset User Profile Access, `from` starts to arrive:
    new comments carry the name and one pass re-reads the posts still in the window to fill the old ones in.

What is read: posts created in the last `WINDOW_DAYS` days, plus "followed" posts the owner pasted (an older post
being advertised). Each cycle costs one call for the post list (with comment counts), one for the followed posts, and
one per post whose count went up. The Page's Business Use Case header is read on every call: at `USAGE_SLOW_PCT`
the Page skips cycles, on a rate-limit error it waits as long as Meta says.

Connecting is a Facebook login (`login_url` -> callback -> `exchange_code`): the owner's long-lived user token gives a
non-expiring Page token for every Page they tick. Logging in again adds Pages; Pages already connected keep their data
and only get a fresh token. Disconnecting a Page deletes everything stored for it.

Personal data: comments older than `retention_months` (default 12) are deleted daily. Names stay in the inbox: they
never go into logs or notifications. No token or secret is ever returned by `view()` or written to a log.

Storage: `STATE_DIR/fb_pages.json`; the App Secret and Page tokens are encrypted with `secrets_store`. Comments go into
the shared conversation store (`conversations`), one conversation per post, channel `facebook`, account = Page id.
"""
from __future__ import annotations

import asyncio
import hashlib
import hmac
import json
import os
import re
import secrets as _secrets
import sys
import threading
import time
from pathlib import Path
from typing import Any, Dict, List, Optional
from urllib.parse import urlencode, urlparse, parse_qs

import localefmt
import secrets_store
from config import STATE_DIR

CHANNEL = "facebook"
GRAPH_VERSION = os.getenv("UNIMATE_FB_GRAPH_VERSION", os.getenv("UNIMATE_MESSENGER_GRAPH_VERSION", "v23.0"))
GRAPH = f"https://graph.facebook.com/{GRAPH_VERSION}"
DIALOG = f"https://www.facebook.com/{GRAPH_VERSION}/dialog/oauth"
SCOPES = ("pages_show_list", "pages_read_engagement", "pages_read_user_content")
CALLBACK_PATH = "/facebook-pages/oauth/callback"

INTERVAL_S = 180            # one read of every Page each 3 minutes
WINDOW_DAYS = 30            # posts created in the last 30 days are read
FIRST_DAYS = 7              # a newly connected Page brings comments from the last 7 days
FOLLOW_MAX = 20             # followed (older, advertised) posts per Page
COMMENT_PAGES_MAX = 10      # 100 comments per call, at most 10 calls per post per cycle
FEED_PAGES_MAX = 5          # 100 posts per call
USAGE_SLOW_PCT = 80         # Meta's usage header at or above this: skip the next cycle of that Page
RATE_WAIT_S = 1800          # rate limited without an estimate: wait 30 minutes
RELOGIN_WARN_S = 14 * 86400
RETENTION_DEFAULT = 12
RETENTION_CHOICES = tuple(range(1, 25))
STATE_TTL_S = 600           # an OAuth state or a pick list lives 10 minutes

_RATE_CODES = {4, 17, 32, 613, 80001}
_TOKEN_CODES = {102, 190}
_TOKEN_SUBCODES = {458, 459, 460, 463, 464, 467, 492}

_lock = threading.RLock()
_states: Dict[str, dict] = {}       # OAuth state -> {"ts", "redirect_uri"}
_picks: Dict[str, dict] = {}        # pick nonce -> {"ts", "pages": [...], "data_access_expires_at"}
_task: Optional[asyncio.Task] = None
_wake: Optional[asyncio.Event] = None


def _store_path() -> Path:
    return Path(STATE_DIR) / "fb_pages.json"


def _now() -> float:
    return time.time()


# ============================================================
# Store
# ============================================================
def _load() -> dict:
    with _lock:
        try:
            d = json.loads(_store_path().read_text(encoding="utf-8"))
        except (OSError, ValueError):
            d = {}
        if not isinstance(d, dict):
            d = {}
        d.setdefault("app", {})
        d.setdefault("pages", {})
        d.setdefault("retention_months", RETENTION_DEFAULT)
        return d


def _save(d: dict) -> None:
    with _lock:
        p = _store_path()
        p.parent.mkdir(parents=True, exist_ok=True)
        tmp = p.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(d, ensure_ascii=False, indent=1), encoding="utf-8")
        os.replace(tmp, p)
        try:
            os.chmod(p, 0o600)
        except OSError:
            pass


def _page_token(pg: dict) -> str:
    return secrets_store.decrypt(str(pg.get("token") or ""))


def app_creds() -> dict:
    a = _load().get("app") or {}
    return {"app_id": str(a.get("app_id") or ""), "app_secret": secrets_store.decrypt(str(a.get("app_secret") or "")),
            "config_id": str(a.get("config_id") or "")}


def set_app(app_id: str, app_secret: str = "", config_id: Optional[str] = None) -> dict:
    """Save the app the owner made. An empty `app_secret` keeps the one already saved."""
    app_id = str(app_id or "").strip()
    if not re.fullmatch(r"\d{5,25}", app_id):
        return {"ok": False, "error": localefmt.chu("App ID là một dãy số, chép ở Cài đặt ứng dụng > Thông tin cơ bản.",
                                                    "The App ID is a number, copy it from App settings > Basic.")}
    app_secret = str(app_secret or "").strip()
    if app_secret and not re.fullmatch(r"[0-9a-fA-F]{32}", app_secret):
        return {"ok": False, "error": localefmt.chu("App Secret là 32 ký tự chữ và số, bấm Hiện ở Cài đặt ứng dụng > Thông tin cơ bản.",
                                                    "The App Secret is 32 letters and digits, click Show in App settings > Basic.")}
    with _lock:
        d = _load()
        a = d["app"]
        if a.get("app_id") and a.get("app_id") != app_id and not app_secret:
            return {"ok": False, "error": localefmt.chu("Đổi App ID thì dán luôn App Secret của ứng dụng mới.",
                                                        "A new App ID needs that app's App Secret too.")}
        a["app_id"] = app_id
        if app_secret:
            a["app_secret"] = secrets_store.encrypt(app_secret)
        if config_id is not None:
            cid = str(config_id or "").strip()
            if cid and not re.fullmatch(r"\d{5,25}", cid):
                return {"ok": False, "error": localefmt.chu("Configuration ID là một dãy số.", "The Configuration ID is a number.")}
            a["config_id"] = cid
        _save(d)
    return {"ok": True}


def set_retention(months: Any) -> dict:
    try:
        m = int(months)
    except (TypeError, ValueError):
        m = 0
    if m not in RETENTION_CHOICES:
        return {"ok": False, "error": localefmt.chu("Thời hạn lưu từ 1 đến 24 tháng.", "Keep comments for 1 to 24 months.")}
    with _lock:
        d = _load()
        d["retention_months"] = m
        _save(d)
    return {"ok": True, "retention_months": m}


def has_page(page_id: str) -> bool:
    return str(page_id or "") in (_load().get("pages") or {})


def _account_key(page_id: str) -> str:
    return f"{CHANNEL}:{page_id}"


def view(base_url: str = "") -> dict:
    """What the dashboard card shows. Never a token, never the App Secret, never a commenter's name."""
    d = _load()
    a = d.get("app") or {}
    now = _now()
    pages = []
    for pid, pg in (d.get("pages") or {}).items():
        exp = int(pg.get("data_access_expires_at") or 0)
        pages.append({
            "page_id": pid, "name": pg.get("name") or pid, "watch": bool(pg.get("watch", True)),
            "token_ok": bool(pg.get("token_ok", True)), "error": pg.get("error") or "",
            "last_at": pg.get("last_at") or 0, "comments": int(pg.get("comments") or 0),
            "added_at": pg.get("added_at") or 0, "names": bool(pg.get("names_ok")),
            "data_access_expires_at": exp,
            "relogin_soon": bool(exp and exp - now < RELOGIN_WARN_S),
            "slowed_until": pg.get("backoff_until") or 0,
            "followed": [{"post_id": k, "url": v.get("url") or "", "added_at": v.get("added_at") or 0}
                         for k, v in (pg.get("followed") or {}).items()],
        })
    pages.sort(key=lambda x: x.get("added_at") or 0)
    redirect = (base_url.rstrip("/") + CALLBACK_PATH) if base_url else ""
    return {"ok": True, "app_id": a.get("app_id") or "", "app_secret_set": bool(a.get("app_secret")),
            "config_id": a.get("config_id") or "", "redirect_uri": redirect,
            "https": redirect.startswith("https://"), "retention_months": int(d.get("retention_months") or RETENTION_DEFAULT),
            "interval_min": INTERVAL_S // 60, "window_days": WINDOW_DAYS, "follow_max": FOLLOW_MAX,
            "scopes": list(SCOPES), "pages": pages}


# ============================================================
# Graph calls
# ============================================================
def appsecret_proof(token: str, app_secret: str) -> str:
    return hmac.new(str(app_secret).encode(), str(token).encode(), hashlib.sha256).hexdigest()


def _client():
    import httpx
    return httpx.AsyncClient(timeout=20)


class GraphError(Exception):
    def __init__(self, code=0, subcode=0, message="", usage=None):
        super().__init__(message)
        self.code, self.subcode, self.message, self.usage = int(code or 0), int(subcode or 0), str(message or ""), usage


def _usage(headers) -> dict:
    """Meta's Business Use Case header -> {"pct": highest share used, "wait_min": minutes until access returns}."""
    raw = ""
    try:
        raw = headers.get("x-business-use-case-usage") or ""
    except Exception:
        raw = ""
    pct, wait = 0, 0
    if raw:
        try:
            for rows in (json.loads(raw) or {}).values():
                for r in rows or []:
                    pct = max(pct, int(r.get("call_count") or 0), int(r.get("total_cputime") or 0), int(r.get("total_time") or 0))
                    wait = max(wait, int(r.get("estimated_time_to_regain_access") or 0))
        except (ValueError, TypeError, AttributeError):
            pass
    return {"pct": pct, "wait_min": wait}


async def _get(client, path: str, params: dict, token: str = "", app_secret: str = "") -> tuple:
    """GET a Graph path. Returns (json, usage). Raises GraphError with Meta's code on an error answer."""
    q: dict = {}
    if path.startswith("https://"):
        # A `paging.next` link from Graph. Its own token is dropped and ours (with the proof) put back, because the
        # app requires `appsecret_proof` on every call and the link does not always carry it.
        u = urlparse(path)
        url = f"{u.scheme}://{u.netloc}{u.path}"
        q = {k: v[-1] for k, v in parse_qs(u.query).items() if k not in ("access_token", "appsecret_proof")}
    else:
        url = f"{GRAPH}/{path.lstrip('/')}"
    q.update(params or {})
    if token:
        q["access_token"] = token
        if app_secret:
            q["appsecret_proof"] = appsecret_proof(token, app_secret)
    try:
        r = await client.get(url, params=q)
    except Exception as e:  # noqa: BLE001 - network: no token in the message
        raise GraphError(0, 0, f"{type(e).__name__}")
    use = _usage(r.headers)
    try:
        body = r.json()
    except ValueError:
        body = {}
    if not isinstance(body, dict):
        body = {}
    err = body.get("error")
    if err or r.status_code >= 400:
        e = err or {}
        raise GraphError(e.get("code") or r.status_code, e.get("error_subcode") or 0, e.get("message") or "", use)
    return body, use


def _next_url(body: dict) -> str:
    return str(((body or {}).get("paging") or {}).get("next") or "")


def explain(e: GraphError) -> str:
    if e.code in _TOKEN_CODES or e.subcode in _TOKEN_SUBCODES:
        return localefmt.chu("Phiên đăng nhập Facebook đã hết hiệu lực (đổi mật khẩu, mất quyền quản trị hoặc kiểm tra bảo mật). Bấm Đăng nhập Facebook để nối lại.",
                             "The Facebook login stopped working (password changed, admin role removed or a security check). Click Log in with Facebook to reconnect.")
    if e.code in _RATE_CODES:
        return localefmt.chu("Facebook đang giới hạn lượt đọc của trang này, UNI MATE tạm nghỉ rồi đọc tiếp.",
                             "Facebook is limiting reads for this Page, UNI MATE pauses and then continues.")
    if e.code in (10, 200):
        return localefmt.chu("Thiếu quyền đọc bình luận. Đăng nhập lại và cấp đủ quyền pages_read_engagement, pages_read_user_content.",
                             "Missing permission to read comments. Log in again and grant pages_read_engagement and pages_read_user_content.")
    if e.code == 0:
        return localefmt.chu("Không gọi được Facebook (mạng).", "Could not reach Facebook (network).")
    return localefmt.chu(f"Facebook báo lỗi {e.code}", f"Facebook answered error {e.code}")


# ============================================================
# Login
# ============================================================
def _gc(store: dict) -> None:
    cut = _now() - STATE_TTL_S
    for k in [k for k, v in store.items() if v.get("ts", 0) < cut]:
        store.pop(k, None)


def login_url(base_url: str) -> dict:
    """The Facebook login dialog address. Needs the App ID saved and an HTTPS address Meta can send the owner back to."""
    c = app_creds()
    if not c["app_id"] or not c["app_secret"]:
        return {"ok": False, "error": localefmt.chu("Lưu App ID và App Secret trước.", "Save the App ID and App Secret first.")}
    redirect = base_url.rstrip("/") + CALLBACK_PATH
    if not redirect.startswith("https://"):
        return {"ok": False, "error": localefmt.chu("Facebook chỉ cho đăng nhập qua địa chỉ HTTPS. Mở UNI MATE bằng tên miền HTTPS (VPS) rồi bấm lại.",
                                                    "Facebook login needs an HTTPS address. Open UNI MATE on its HTTPS domain (VPS) and try again.")}
    state = _secrets.token_urlsafe(24)
    with _lock:
        _gc(_states)
        _states[state] = {"ts": _now(), "redirect_uri": redirect}
    q = {"client_id": c["app_id"], "redirect_uri": redirect, "state": state, "response_type": "code"}
    if c["config_id"]:
        q["config_id"] = c["config_id"]
    else:
        q["scope"] = ",".join(SCOPES)
    return {"ok": True, "url": DIALOG + "?" + urlencode(q)}


async def exchange_code(code: str, state: str) -> dict:
    """Callback: code -> long-lived user token -> the Pages the owner granted. Keeps the list 10 minutes under a
    one-time nonce for the pick page. Tokens stay on the server."""
    with _lock:
        _gc(_states)
        st = _states.pop(str(state or ""), None)
    if not st:
        return {"ok": False, "error": localefmt.chu("Phiên đăng nhập đã hết hạn hoặc không hợp lệ. Bấm Đăng nhập Facebook lại.",
                                                    "This login expired or is not valid. Click Log in with Facebook again.")}
    c = app_creds()
    if not code or not c["app_id"] or not c["app_secret"]:
        return {"ok": False, "error": localefmt.chu("Thiếu mã đăng nhập hoặc App Secret.", "Missing login code or App Secret.")}
    async with _client() as client:
        try:
            short, _ = await _get(client, "oauth/access_token", {
                "client_id": c["app_id"], "redirect_uri": st["redirect_uri"], "client_secret": c["app_secret"], "code": code})
            user = str(short.get("access_token") or "")
            longd, _ = await _get(client, "oauth/access_token", {
                "grant_type": "fb_exchange_token", "client_id": c["app_id"], "client_secret": c["app_secret"],
                "fb_exchange_token": user})
            user = str(longd.get("access_token") or user)
            dbg, _ = await _get(client, "debug_token", {"input_token": user,
                                                       "access_token": f"{c['app_id']}|{c['app_secret']}"})
            exp = int(((dbg or {}).get("data") or {}).get("data_access_expires_at") or 0)
            pages, url = [], "me/accounts"
            params = {"fields": "id,name,access_token,tasks", "limit": 100}
            for _ in range(5):
                body, _ = await _get(client, url, params, user, c["app_secret"])
                for p in body.get("data") or []:
                    if p.get("id") and p.get("access_token"):
                        pages.append({"id": str(p["id"]), "name": str(p.get("name") or p["id"]),
                                      "token": str(p["access_token"]), "tasks": list(p.get("tasks") or [])})
                url = _next_url(body)
                params = {}
                if not url:
                    break
        except GraphError as e:
            return {"ok": False, "error": explain(e) if e.code else localefmt.chu("Không gọi được Facebook.", "Could not reach Facebook.")}
    if not pages:
        return {"ok": False, "error": localefmt.chu("Facebook không trả trang nào. Khi đăng nhập, chọn đúng trang và cấp đủ quyền.",
                                                    "Facebook returned no Page. When logging in, pick the Page and grant every permission.")}
    nonce = _secrets.token_urlsafe(24)
    with _lock:
        _gc(_picks)
        _picks[nonce] = {"ts": _now(), "pages": pages, "data_access_expires_at": exp}
    connected = set((_load().get("pages") or {}).keys())
    return {"ok": True, "nonce": nonce,
            "pages": [{"id": p["id"], "name": p["name"], "connected": p["id"] in connected} for p in pages]}


def pick(nonce: str, page_ids: List[str]) -> dict:
    """Connect the ticked Pages. A Page already connected keeps its comments and settings; only its token is renewed.
    Pages not ticked are left exactly as they are (disconnecting is its own button)."""
    with _lock:
        _gc(_picks)
        pk = _picks.pop(str(nonce or ""), None)
    if not pk:
        return {"ok": False, "error": localefmt.chu("Danh sách trang đã hết hạn. Bấm Đăng nhập Facebook lại.",
                                                    "The Page list expired. Click Log in with Facebook again.")}
    want = {str(x) for x in (page_ids or [])}
    added, renewed = [], []
    with _lock:
        d = _load()
        for p in pk["pages"]:
            if p["id"] not in want:
                continue
            old = d["pages"].get(p["id"])
            if old:
                old.update({"name": p["name"], "token": secrets_store.encrypt(p["token"]), "token_ok": True, "error": "",
                            "data_access_expires_at": pk.get("data_access_expires_at") or 0})
                renewed.append(p["id"])
            else:
                now = _now()
                d["pages"][p["id"]] = {"name": p["name"], "token": secrets_store.encrypt(p["token"]), "watch": True,
                                       "token_ok": True, "error": "", "added_at": now, "first_floor": now - FIRST_DAYS * 86400,
                                       "data_access_expires_at": pk.get("data_access_expires_at") or 0,
                                       "posts": {}, "followed": {}, "comments": 0, "last_at": 0}
                added.append(p["id"])
        _save(d)
    wake()
    return {"ok": True, "added": added, "renewed": renewed}


def set_watch(page_id: str, on: bool) -> dict:
    with _lock:
        d = _load()
        pg = d["pages"].get(str(page_id))
        if not pg:
            return {"ok": False, "error": localefmt.chu("Không có trang này.", "No such Page.")}
        pg["watch"] = bool(on)
        _save(d)
    if on:
        wake()
    return {"ok": True, "watch": bool(on)}


def disconnect(page_id: str, confirm: bool = False) -> dict:
    """Without `confirm`: how much would be deleted. With it: the Page, its token and every comment stored for it."""
    import conversations
    pid = str(page_id or "")
    d = _load()
    if pid not in d["pages"]:
        return {"ok": False, "error": localefmt.chu("Không có trang này.", "No such Page.")}
    key = _account_key(pid)
    if not confirm:
        n = conversations.count_account(key)
        return {"ok": True, "confirm_needed": True, "comments": n["messages"], "posts": n["conversations"]}
    gone = conversations.delete_account_data(key)
    with _lock:
        d = _load()
        d["pages"].pop(pid, None)
        _save(d)
    return {"ok": True, "deleted": gone}


# ============================================================
# Followed posts (an older post being advertised)
# ============================================================
_ID_RE = re.compile(r"^\d{5,25}(?:_\d{5,25})?$")


def _candidate_ids(page_id: str, raw: str) -> tuple:
    """(post ids to try, pfbid token or ""). Accepts a bare id, "<page>_<post>", and the usual post/video links."""
    s = str(raw or "").strip()
    if _ID_RE.match(s):
        return ([s] if "_" in s else [f"{page_id}_{s}", s]), ""
    try:
        u = urlparse(s if "://" in s else "https://" + s)
    except ValueError:
        return [], ""
    q = parse_qs(u.query)
    out = []
    for k in ("story_fbid", "fbid", "v"):
        v = (q.get(k) or [""])[0]
        if re.fullmatch(r"\d{5,25}", v):
            out += [f"{page_id}_{v}", v]
    for m in re.finditer(r"/(?:posts|videos|photos|reel|permalink)/(?:[^/]+/)?(\d{5,25})", u.path):
        out += [f"{page_id}_{m.group(1)}", m.group(1)]
    pf = re.search(r"(pfbid[0-9A-Za-z]+)", s)
    return list(dict.fromkeys(out)), (pf.group(1) if pf else "")


async def follow(page_id: str, raw: str) -> dict:
    pid = str(page_id or "")
    d = _load()
    pg = d["pages"].get(pid)
    if not pg:
        return {"ok": False, "error": localefmt.chu("Không có trang này.", "No such Page.")}
    if len(pg.get("followed") or {}) >= FOLLOW_MAX:
        return {"ok": False, "error": localefmt.chu(f"Mỗi trang theo dõi thêm tối đa {FOLLOW_MAX} bài.",
                                                    f"At most {FOLLOW_MAX} followed posts per Page.")}
    ids, pfbid = _candidate_ids(pid, raw)
    if not ids and not pfbid:
        return {"ok": False, "error": localefmt.chu("Dán đường dẫn của bài trên trang (nút Chia sẻ > Sao chép liên kết).",
                                                    "Paste the post's link (Share > Copy link).")}
    token, secret = _page_token(pg), app_creds()["app_secret"]
    found = None
    async with _client() as client:
        for cid in ids:
            try:
                body, _ = await _get(client, cid, {"fields": "id,created_time,permalink_url,from"}, token, secret)
            except GraphError:
                continue
            if str(body.get("id") or "").startswith(pid + "_") or str((body.get("from") or {}).get("id") or "") == pid:
                found = body
                break
        if not found and pfbid:
            url, params = f"{pid}/published_posts", {"fields": "id,created_time,permalink_url", "limit": 100}
            for _ in range(10):
                try:
                    body, _ = await _get(client, url, params, token, secret)
                except GraphError:
                    break
                hit = next((p for p in body.get("data") or [] if pfbid in str(p.get("permalink_url") or "")), None)
                if hit:
                    found = hit
                    break
                url, params = _next_url(body), {}
                if not url:
                    break
    if not found:
        return {"ok": False, "error": localefmt.chu("Không tìm thấy bài này trên trang. Kiểm tra đường dẫn là bài của chính trang.",
                                                    "This post was not found on the Page. Check the link is one of the Page's own posts.")}
    post_id = str(found["id"])
    with _lock:
        d = _load()
        pg = d["pages"].get(pid)
        if pg is None:
            return {"ok": False, "error": localefmt.chu("Không có trang này.", "No such Page.")}
        pg.setdefault("followed", {})[post_id] = {"url": str(found.get("permalink_url") or raw)[:500], "added_at": _now(),
                                                   "last_comment_at": 0}
        _save(d)
    wake()
    return {"ok": True, "post_id": post_id}


def unfollow(page_id: str, post_id: str) -> dict:
    with _lock:
        d = _load()
        pg = d["pages"].get(str(page_id))
        if not pg or str(post_id) not in (pg.get("followed") or {}):
            return {"ok": False, "error": localefmt.chu("Không có bài này trong danh sách.", "This post is not in the list.")}
        pg["followed"].pop(str(post_id), None)
        _save(d)
    return {"ok": True}


# ============================================================
# Reading
# ============================================================
def _ts(s: Any) -> float:
    from datetime import datetime
    try:
        return datetime.strptime(str(s), "%Y-%m-%dT%H:%M:%S%z").timestamp()
    except (TypeError, ValueError):
        return 0.0


def _post_title(post: dict) -> str:
    msg = re.sub(r"\s+", " ", str(post.get("message") or "")).strip()
    if msg:
        return msg[:60] + ("…" if len(msg) > 60 else "")
    ts = _ts(post.get("created_time"))
    when = time.strftime("%d/%m/%Y", time.localtime(ts)) if ts else ""
    return localefmt.chu("Bài đăng " + when, "Post " + when).strip()


def comment_event(page_id: str, page_name: str, post: dict, cm: dict) -> dict:
    """One Graph comment -> one inbox event. A comment with no `from` (Meta hides who wrote it) is a customer with no
    name; the Page's own comment is the owner's side."""
    frm = cm.get("from") or {}
    fid = str(frm.get("id") or "")
    own = fid == str(page_id)
    text = str(cm.get("message") or "")
    att = cm.get("attachment") or {}
    if att and not text:
        text = localefmt.chu("(ảnh hoặc tệp đính kèm)", "(photo or attachment)")
    return {
        "channel": CHANNEL, "account_id": str(page_id), "account_name": page_name,
        "external_chat_id": str(post.get("id") or ""), "chat_type": "group", "chat_title": _post_title(post),
        "sender_type": "human" if own else "customer",
        "sender_id": "" if own else fid, "sender_name": "" if own else str(frm.get("name") or ""),
        "message_type": "text", "text": text, "external_message_id": str(cm.get("id") or ""),
        "created_at": _ts(cm.get("created_time")) or _now(),
        "metadata": {"fb": {"permalink": str(cm.get("permalink_url") or "")[:500], "post_id": str(post.get("id") or ""),
                            "reply": bool((cm.get("parent") or {}).get("id")), "anon": not fid}},
    }


_POST_FIELDS = "id,message,created_time,permalink_url,comments.filter(stream).limit(0).summary(true)"
_COMMENT_FIELDS = "id,message,created_time,from,parent{id},permalink_url,attachment{type}"


async def _posts_of(client, page_id: str, pg: dict, token: str, secret: str, now: float) -> tuple:
    """Posts to look at this cycle: the last WINDOW_DAYS days plus followed ones. Returns (posts, worst usage)."""
    posts, worst = {}, {"pct": 0, "wait_min": 0}
    url, params = f"{page_id}/feed", {"fields": _POST_FIELDS, "since": int(now - WINDOW_DAYS * 86400), "limit": 100}
    for _ in range(FEED_PAGES_MAX):
        body, use = await _get(client, url, params, token, secret)
        worst = max(worst, use, key=lambda u: u["pct"])
        for p in body.get("data") or []:
            if p.get("id"):
                posts[str(p["id"])] = p
        url, params = _next_url(body), {}
        if not url:
            break
    fol = [k for k in (pg.get("followed") or {}) if k not in posts]
    if fol:
        body, use = await _get(client, "", {"ids": ",".join(fol[:50]), "fields": _POST_FIELDS}, token, secret)
        worst = max(worst, use, key=lambda u: u["pct"])
        for k, p in (body or {}).items():
            if isinstance(p, dict) and p.get("id"):
                posts[str(p["id"])] = p
    return posts, worst


async def _new_comments(client, post_id: str, newest: float, floor: float, token: str, secret: str) -> tuple:
    """Comments newer than `newest` (and not older than `floor`), oldest first. Returns (comments, usage)."""
    got, worst = [], {"pct": 0, "wait_min": 0}
    url = f"{post_id}/comments"
    params = {"fields": _COMMENT_FIELDS, "filter": "stream", "order": "reverse_chronological", "limit": 100}
    for _ in range(COMMENT_PAGES_MAX):
        body, use = await _get(client, url, params, token, secret)
        worst = max(worst, use, key=lambda u: u["pct"])
        stop = False
        for cm in body.get("data") or []:
            ts = _ts(cm.get("created_time"))
            if ts and (ts < newest or ts < floor):
                stop = True
                break
            got.append(cm)
        url, params = _next_url(body), {}
        if stop or not url:
            break
    got.reverse()
    return got, worst


def _write(events: List[dict]) -> int:
    import conversations
    n = 0
    for ev in events:
        try:
            r = conversations.ghi_su_kien(ev, dem_chua_doc=ev.get("sender_type") == "customer")
        except Exception as e:  # noqa: BLE001 - one bad comment must not stop the Page
            print(f"[fb-pages] write failed: {type(e).__name__}", file=sys.stderr)
            continue
        if r.get("ok") and not r.get("trung"):
            n += 1
    return n


async def poll_page(page_id: str) -> dict:
    """One read of one Page. Returns {"ok", "new", "error"}; the result is also kept on the Page for the card."""
    d = _load()
    pg = d["pages"].get(page_id)
    if not pg:
        return {"ok": False, "error": "gone"}
    token, secret = _page_token(pg), app_creds()["app_secret"]
    now = _now()
    floor = float(pg.get("first_floor") or 0)
    known = dict(pg.get("posts") or {})
    new_total, events, worst, err, names_seen = 0, [], {"pct": 0, "wait_min": 0}, None, False
    try:
        async with _client() as client:
            posts, use = await _posts_of(client, page_id, pg, token, secret, now)
            worst = max(worst, use, key=lambda u: u["pct"])
            for post_id, post in posts.items():
                total = int((((post.get("comments") or {}).get("summary")) or {}).get("total_count") or 0)
                k = known.get(post_id) or {}
                if total <= int(k.get("count") or 0):
                    known[post_id] = {"count": total, "newest": k.get("newest") or 0, "created": _ts(post.get("created_time"))}
                    continue
                cms, use = await _new_comments(client, post_id, float(k.get("newest") or 0), floor, token, secret)
                worst = max(worst, use, key=lambda u: u["pct"])
                for cm in cms:
                    ev = comment_event(page_id, pg.get("name") or page_id, post, cm)
                    if ev["sender_type"] == "customer" and ev["sender_id"]:
                        names_seen = True
                    events.append(ev)
                newest = max([float(k.get("newest") or 0)] + [_ts(c.get("created_time")) for c in cms])
                known[post_id] = {"count": total, "newest": newest, "created": _ts(post.get("created_time"))}
                if post_id in (pg.get("followed") or {}) and cms:
                    pg["followed"][post_id]["last_comment_at"] = newest
    except GraphError as e:
        err = e
        worst = max(worst, e.usage or worst, key=lambda u: u["pct"])
    new_total = _write(events)
    with _lock:
        d = _load()
        cur = d["pages"].get(page_id)
        if cur is None:
            return {"ok": False, "error": "gone"}
        win = now - WINDOW_DAYS * 86400
        cur["posts"] = {k: v for k, v in known.items()
                        if (v.get("created") or 0) >= win or k in (cur.get("followed") or {})}
        # A followed post leaves the list after WINDOW_DAYS days with no new comment.
        for k, v in list((cur.get("followed") or {}).items()):
            last = max(float(v.get("last_comment_at") or 0), float(v.get("added_at") or 0))
            if last < win:
                cur["followed"].pop(k, None)
        for k, v in (pg.get("followed") or {}).items():
            if k in (cur.get("followed") or {}):
                cur["followed"][k]["last_comment_at"] = v.get("last_comment_at") or 0
        cur["comments"] = int(cur.get("comments") or 0) + new_total
        cur["last_at"] = now
        if names_seen and not cur.get("names_ok"):
            cur["names_ok"] = True
            cur["names_backfill"] = True
        if err is not None:
            cur["error"] = explain(err)
            if err.code in _TOKEN_CODES or err.subcode in _TOKEN_SUBCODES:
                cur["token_ok"] = False
            elif err.code in _RATE_CODES:
                cur["backoff_until"] = now + (worst["wait_min"] * 60 if worst["wait_min"] else RATE_WAIT_S)
            else:
                cur["backoff_until"] = now + INTERVAL_S
        else:
            cur["error"] = ""
            if worst["wait_min"]:
                cur["backoff_until"] = now + worst["wait_min"] * 60
            elif worst["pct"] >= USAGE_SLOW_PCT:
                cur["backoff_until"] = now + INTERVAL_S * 2
            else:
                cur["backoff_until"] = 0
        _save(d)
    if err is None and d["pages"].get(page_id, {}).get("names_backfill"):
        await backfill_names(page_id)
    return {"ok": err is None, "new": new_total, "error": explain(err) if err is not None else ""}


async def backfill_names(page_id: str) -> int:
    """Meta started sending `from`: re-read the posts still in the window and put the name on comments stored
    without one. Runs once per Page."""
    import conversations
    d = _load()
    pg = d["pages"].get(page_id)
    if not pg:
        return 0
    token, secret = _page_token(pg), app_creds()["app_secret"]
    fixed = 0
    try:
        async with _client() as client:
            for post_id in list((pg.get("posts") or {}).keys()):
                cms, _ = await _new_comments(client, post_id, 0, 0, token, secret)
                for cm in cms:
                    frm = cm.get("from") or {}
                    if frm.get("id") and str(frm["id"]) != page_id:
                        if conversations.set_message_sender(_account_key(page_id), post_id, str(cm.get("id") or ""),
                                                            str(frm["id"]), str(frm.get("name") or "")):
                            fixed += 1
    except GraphError:
        return fixed
    with _lock:
        d = _load()
        if page_id in d["pages"]:
            d["pages"][page_id]["names_backfill"] = False
            _save(d)
    return fixed


def purge(now: Optional[float] = None) -> int:
    """Delete comments older than the retention period, for every Page. Once a day from the loop."""
    import conversations
    d = _load()
    months = int(d.get("retention_months") or RETENTION_DEFAULT)
    cut = (now or _now()) - months * 30.44 * 86400
    n = 0
    for pid in (d.get("pages") or {}):
        n += conversations.purge_before(_account_key(pid), cut)
    return n


def due_pages(now: Optional[float] = None) -> List[str]:
    now = now or _now()
    out = []
    for pid, pg in (_load().get("pages") or {}).items():
        if pg.get("watch", True) and pg.get("token_ok", True) and float(pg.get("backoff_until") or 0) <= now:
            out.append(pid)
    return out


async def run_once() -> dict:
    res = {}
    for pid in due_pages():
        try:
            res[pid] = await poll_page(pid)
        except Exception as e:  # noqa: BLE001
            print(f"[fb-pages] read failed: {type(e).__name__}", file=sys.stderr)
    day = time.strftime("%Y-%m-%d")
    with _lock:
        d = _load()
        if d.get("last_purge_day") != day:
            d["last_purge_day"] = day
            _save(d)
            purge_due = True
        else:
            purge_due = False
    if purge_due:
        try:
            purge()
        except Exception as e:  # noqa: BLE001
            print(f"[fb-pages] purge failed: {type(e).__name__}", file=sys.stderr)
    return res


def wake() -> None:
    try:
        if _wake is not None:
            _wake.set()
    except Exception:
        pass


async def _loop() -> None:
    global _wake
    _wake = asyncio.Event()
    while True:
        try:
            if (_load().get("pages") or {}):
                await run_once()
        except asyncio.CancelledError:
            raise
        except Exception as e:  # noqa: BLE001
            print(f"[fb-pages] loop: {type(e).__name__}", file=sys.stderr)
        try:
            await asyncio.wait_for(_wake.wait(), timeout=INTERVAL_S)
        except asyncio.TimeoutError:
            pass
        _wake.clear()


def start() -> bool:
    global _task
    if _task and not _task.done():
        return True
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        return False
    _task = loop.create_task(_loop())
    return True


def stop() -> None:
    global _task
    if _task and not _task.done():
        _task.cancel()
    _task = None


# ---- for the channel registry (channels/facebook.py) ----
def accounts() -> List[dict]:
    out = []
    for p in view().get("pages") or []:
        out.append({"id": p["page_id"], "label": p["name"], "channel": CHANNEL, "theo_doi": p["watch"],
                    "lan_cuoi": p["last_at"], "loi": p["error"], "so_tin": p["comments"]})
    return out
