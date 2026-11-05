"""0.448.0: Facebook Page comments in the inbox, read only.

    python tests/run.py fb_pages_0448      (NO network: a fake Graph API answers every call)

Owner's decision 05/11/2026. Checks, in the order of the approved plan:
  1. App settings: App ID / App Secret checked by shape; nothing secret ever comes back in `view()`.
  2. Login: HTTPS only, the three read permissions (or a Configuration ID), one-time state; the code becomes a
     long-lived user token and the Page list; no token reaches the pick page.
  3. Several Pages, one inbox account each; logging in again ADDS a Page and the Page already connected keeps its
     comments (the case of the Excel and slide Pages joining the golf Page later).
  4. Reading: posts of the last 30 days, one conversation per post; a comment without `from` is a nameless customer,
     the Page's own comment is the owner's side, replies are marked, nothing is stored twice, a new Page brings only
     the last 7 days, and only posts whose comment count went up are read again.
  5. Every Graph call carries `appsecret_proof` (the app has "Require App Secret" on), paging links included.
  6. Rate limits and tokens: usage at 80% skips cycles, error 80001 waits as long as Meta says, a dead token stops
     the Page and asks for a new login.
  7. Names: once Meta sends `from`, new comments carry the name and the stored ones get it filled in.
  8. Followed posts: a pasted link (post id or pfbid) resolves to the Page's own post; another Page's post is refused.
  9. Personal data: comments older than the retention period are deleted; disconnecting deletes everything of the Page;
     no token, secret or commenter name goes to the log.
 10. The channel registry and the routes: read only (no reply), the callback page escapes Page names.
"""
from _paths import ROOT, SERVER  # noqa: E402,F401
import asyncio
import contextlib
import io
import json
import os
import sys
import tempfile
import time
from urllib.parse import parse_qs, urlparse

os.environ["UNIMATE_STATE_DIR"] = tempfile.mkdtemp(prefix="unimate-fb-pages-")
try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

import httpx  # noqa: E402

import fb_pages  # noqa: E402
import conversations  # noqa: E402
import channels  # noqa: E402

_fails = []


def check(name, cond, extra=""):
    print(("ok   " if cond else "FAIL ") + name + (("  [" + str(extra)[:300] + "]") if not cond else ""))
    if not cond:
        _fails.append(name)


def run(c):
    return asyncio.run(c)


APP = "1304989025084991"
SECRET = "b" * 32
GOLF, EXCEL = "111111111111111", "222222222222222"
TOK = {GOLF: "EAApage-golf-" + "g" * 40, EXCEL: "EAApage-excel-" + "e" * 40}
USER_SHORT, USER_LONG = "EAAuser-short-" + "s" * 40, "EAAuser-long-" + "l" * 40
NOW = time.time()


def iso(ts):
    return time.strftime("%Y-%m-%dT%H:%M:%S+0000", time.gmtime(ts))


class Graph:
    """Fake Graph: posts and comments per Page, call log, switches for errors, usage and `from`."""

    def __init__(self):
        self.calls = []
        self.posts = {GOLF: [], EXCEL: []}
        self.comments = {}
        self.usage_pct = 0
        self.error = None            # (code, subcode) answered to the next Page call
        self.wait_min = 0
        self.with_from = False
        self.accounts = [GOLF]
        self.page_size = 100

    def add_post(self, page, num, ts, msg="Bài thử"):
        pid = f"{page}_{num}"
        self.posts[page].append({"id": pid, "message": msg, "created_time": iso(ts),
                                 "permalink_url": f"https://www.facebook.com/{page}/posts/pfbid0{num}abc"})
        self.comments.setdefault(pid, [])
        return pid

    def add_comment(self, post, cid, ts, text, who=("901", "Khach That"), parent=None):
        self.comments[post].append({"id": cid, "message": text, "created_time": iso(ts),
                                    "from_": {"id": who[0], "name": who[1]} if who else None,
                                    "parent": {"id": parent} if parent else None,
                                    "permalink_url": f"https://www.facebook.com/{post}?comment_id={cid}"})

    def _c(self, c, page):
        out = {k: v for k, v in c.items() if k != "from_" and v is not None}
        f = c.get("from_")
        if f and (self.with_from or f["id"] == page):
            out["from"] = f
        return out

    def _usage(self):
        return {"x-business-use-case-usage": json.dumps({GOLF: [{"type": "pages", "call_count": self.usage_pct,
                                                                 "total_cputime": 1, "total_time": 1,
                                                                 "estimated_time_to_regain_access": self.wait_min}]})}

    def __call__(self, request):
        u = urlparse(str(request.url))
        q = {k: v[-1] for k, v in parse_qs(u.query).items()}
        path = u.path.split("/v23.0/", 1)[-1] if "/v23.0/" in u.path else u.path.lstrip("/")
        self.calls.append((path, q))
        tok = q.get("access_token", "")
        if path == "oauth/access_token":
            if q.get("code") == "good":
                return httpx.Response(200, json={"access_token": USER_SHORT})
            if q.get("fb_exchange_token") == USER_SHORT:
                return httpx.Response(200, json={"access_token": USER_LONG})
            return httpx.Response(400, json={"error": {"code": 100, "message": "bad"}})
        if path == "debug_token":
            return httpx.Response(200, json={"data": {"is_valid": True, "data_access_expires_at": int(NOW + 80 * 86400)}})
        if path == "me/accounts":
            return httpx.Response(200, json={"data": [
                {"id": p, "name": "Golf <HaNoi>" if p == GOLF else "Excel UNI", "access_token": TOK[p], "tasks": ["MANAGE"]}
                for p in self.accounts]})
        page = next((p for p, t in TOK.items() if t == tok), None)
        if page is None:
            return httpx.Response(400, json={"error": {"code": 190, "message": "bad token"}})
        if self.error:
            code, sub = self.error
            return httpx.Response(400, json={"error": {"code": code, "error_subcode": sub, "message": "x"}},
                                  headers=self._usage())
        h = self._usage()
        if path == f"{page}/feed":
            since = float(q.get("since") or 0)
            rows = []
            for p in self.posts[page]:
                if fb_pages._ts(p["created_time"]) >= since:
                    rows.append({**p, "comments": {"data": [], "summary": {"total_count": len(self.comments[p["id"]])}}})
            return httpx.Response(200, json={"data": rows}, headers=h)
        if path in ("", "/") and q.get("ids"):
            out = {}
            for i in q["ids"].split(","):
                p = next((x for x in self.posts[page] if x["id"] == i), None)
                if p:
                    out[i] = {**p, "comments": {"data": [], "summary": {"total_count": len(self.comments[i])}}}
            return httpx.Response(200, json=out, headers=h)
        if path.endswith("/comments"):
            post = path[:-len("/comments")]
            rows = sorted(self.comments.get(post, []), key=lambda c: c["created_time"], reverse=True)
            off = int(q.get("after") or 0)
            part = rows[off:off + self.page_size]
            body = {"data": [self._c(c, page) for c in part]}
            if off + self.page_size < len(rows):
                # A paging link the way Graph writes it: with a token, without the proof.
                body["paging"] = {"next": f"https://graph.facebook.com/v23.0/{post}/comments?access_token={tok}"
                                          f"&after={off + self.page_size}&limit={self.page_size}&filter=stream"
                                          f"&order=reverse_chronological"}
            return httpx.Response(200, json=body, headers=h)
        if path == f"{page}/published_posts":
            return httpx.Response(200, json={"data": [{"id": p["id"], "permalink_url": p["permalink_url"],
                                                       "created_time": p["created_time"]} for p in self.posts[page]]})
        for p in self.posts[page]:
            if path == p["id"]:
                return httpx.Response(200, json={"id": p["id"], "created_time": p["created_time"],
                                                 "permalink_url": p["permalink_url"], "from": {"id": page}})
        return httpx.Response(400, json={"error": {"code": 100, "message": "unknown path " + path}})


G = Graph()
fb_pages._client = lambda: httpx.AsyncClient(transport=httpx.MockTransport(G), timeout=5)

# ---------- 1. app settings ----------
check("App ID must be digits", not fb_pages.set_app("abc", SECRET)["ok"])
check("App Secret must be 32 hex characters", not fb_pages.set_app(APP, "short")["ok"])
check("valid app saved", fb_pages.set_app(APP, SECRET)["ok"])
v = fb_pages.view("https://unimate.example")
check("view: secret only as a flag", v["app_secret_set"] and SECRET not in json.dumps(v), v)
check("view: redirect address on the HTTPS domain",
      v["redirect_uri"] == "https://unimate.example/facebook-pages/oauth/callback" and v["https"], v["redirect_uri"])
raw = (fb_pages._store_path()).read_text(encoding="utf-8")
check("App Secret is not stored in clear", SECRET not in raw)
check("keeping the saved secret when only the App ID is resent", fb_pages.set_app(APP, "")["ok"]
      and fb_pages.app_creds()["app_secret"] == SECRET)

# ---------- 2. login ----------
check("plain HTTP is refused", not fb_pages.login_url("http://192.168.1.5:8688")["ok"])
lu = fb_pages.login_url("https://unimate.example")
q = parse_qs(urlparse(lu["url"]).query)
check("dialog asks exactly the three read permissions",
      q.get("scope") == ["pages_show_list,pages_read_engagement,pages_read_user_content"], q)
check("dialog carries the redirect and a state", q.get("redirect_uri") == [v["redirect_uri"]] and q.get("state"), q)
fb_pages.set_app(APP, "", config_id="555666777888")
q2 = parse_qs(urlparse(fb_pages.login_url("https://unimate.example")["url"]).query)
check("with a Configuration ID the dialog uses it instead of scope", q2.get("config_id") == ["555666777888"]
      and "scope" not in q2, q2)
fb_pages.set_app(APP, "", config_id="")
check("unknown state is refused", not run(fb_pages.exchange_code("good", "forged"))["ok"])
state = q["state"][0]
r = run(fb_pages.exchange_code("good", state))
check("code -> Page list", r["ok"] and [p["id"] for p in r["pages"]] == [GOLF], r)
check("the pick list carries no token", not any(t in json.dumps(r) for t in TOK.values()) and USER_LONG not in json.dumps(r))
check("a state works only once", not run(fb_pages.exchange_code("good", state))["ok"])
check("short token exchanged for a long-lived one", any(c[1].get("fb_exchange_token") == USER_SHORT for c in G.calls))
check("me/accounts is read with the long-lived token and the proof",
      any(c[0] == "me/accounts" and c[1].get("access_token") == USER_LONG
          and c[1].get("appsecret_proof") == fb_pages.appsecret_proof(USER_LONG, SECRET) for c in G.calls))
pk = fb_pages.pick(r["nonce"], [GOLF])
check("golf Page connected", pk["ok"] and pk["added"] == [GOLF], pk)
check("a pick list works only once", not fb_pages.pick(r["nonce"], [GOLF])["ok"])
check("Page token stored encrypted", TOK[GOLF] not in fb_pages._store_path().read_text(encoding="utf-8"))

# ---------- 4. reading ----------
OLD = NOW - 20 * 86400
p1 = G.add_post(GOLF, 1001, NOW - 3600, "CHUẨN BỊ COMEBACK!")
p_old = G.add_post(GOLF, 1002, NOW - 40 * 86400, "Bài cũ")
G.add_comment(p1, "c1", NOW - 600, "😍", who=("901", "Huan Nguyen"))
G.add_comment(p1, "c2", NOW - 500, "Cảm ơn bạn", who=(GOLF, "Golf HaNoi"), parent="c1")
G.add_comment(p1, "c0", NOW - 9 * 86400, "trước khi nối")
G.add_comment(p_old, "c9", NOW - 39 * 86400, "bài ngoài 30 ngày")
G.calls.clear()
log = io.StringIO()
with contextlib.redirect_stderr(log):
    res = run(fb_pages.poll_page(GOLF))
check("first read: 2 new comments (one older than 7 days before connecting is skipped)", res["ok"] and res["new"] == 2, res)
convs = conversations.danh_sach(channel="facebook")
items = convs.get("items") if isinstance(convs, dict) else convs
check("one conversation per post, in the Page's own account",
      len(items) == 1 and conversations.count_account("facebook:" + GOLF)["conversations"] == 1, items)
cid = items[0]["id"]
msgs = conversations.tin_nhan(cid)
by = {m["external_message_id"]: m for m in msgs}
check("comment without from: customer, no name, marked anonymous",
      by["c1"]["sender_type"] == "customer" and by["c1"]["sender_name"] == "" and by["c1"]["metadata"]["fb"]["anon"], by["c1"])
check("Page's own reply: owner side, marked as a reply",
      by["c2"]["sender_type"] == "human" and by["c2"]["metadata"]["fb"]["reply"], by["c2"])
check("each comment links back to Facebook", by["c1"]["metadata"]["fb"]["permalink"].startswith("https://www.facebook.com/"))
check("post outside the 30-day window is not read", not any(c[0] == f"{p_old}/comments" for c in G.calls))
check("every Page call carries the proof", all(c[1].get("appsecret_proof") == fb_pages.appsecret_proof(TOK[GOLF], SECRET)
                                               for c in G.calls if c[1].get("access_token") == TOK[GOLF]))
G.calls.clear()
res = run(fb_pages.poll_page(GOLF))
check("second read with nothing new: nothing written, comments not fetched again",
      res["new"] == 0 and not any(c[0].endswith("/comments") for c in G.calls), G.calls)
G.add_comment(p1, "c3", NOW - 60, "Giá bao nhiêu?")
res = run(fb_pages.poll_page(GOLF))
check("a new comment is read on the next cycle", res["new"] == 1 and len(conversations.tin_nhan(cid)) == 3, res)

# paging, with the token dropped from Graph's link and ours (with the proof) put back
G.page_size = 1
G.add_comment(p1, "c4", NOW - 50, "Còn size M không?")
G.add_comment(p1, "c5", NOW - 40, "Ship Hà Nội không?")
G.calls.clear()
res = run(fb_pages.poll_page(GOLF))
check("paging: both new comments read", res["new"] == 2, res)
nxt = [c for c in G.calls if c[0].endswith("/comments") and c[1].get("after")]
check("paging link re-signed with the proof",
      nxt and all(c[1].get("appsecret_proof") == fb_pages.appsecret_proof(TOK[GOLF], SECRET) for c in nxt), nxt)
G.page_size = 100

# ---------- 3. a second Page later, the first keeps its data ----------
before = conversations.count_account("facebook:" + GOLF)
G.accounts = [GOLF, EXCEL]
lu = fb_pages.login_url("https://unimate.example")
r2 = run(fb_pages.exchange_code("good", parse_qs(urlparse(lu["url"]).query)["state"][0]))
check("second login lists the golf Page as connected", any(p["id"] == GOLF and p["connected"] for p in r2["pages"]), r2)
pk2 = fb_pages.pick(r2["nonce"], [EXCEL])
check("Excel Page added", pk2["added"] == [EXCEL] and pk2["renewed"] == [], pk2)
check("golf Page untouched: same comments, still connected",
      conversations.count_account("facebook:" + GOLF) == before and fb_pages.has_page(GOLF))
pe = G.add_post(EXCEL, 2001, NOW - 7200, "File Excel quản trị")
G.add_comment(pe, "e1", NOW - 100, "Xin file mẫu")
run(fb_pages.run_once())
check("each Page is its own inbox account",
      conversations.count_account("facebook:" + EXCEL)["messages"] == 1
      and conversations.count_account("facebook:" + GOLF) == before)
accs = channels.module("facebook").tai_khoan()
check("channel lists both Pages with their names", {a["id"]: a["label"] for a in accs} == {GOLF: "Golf <HaNoi>", EXCEL: "Excel UNI"}, accs)

# ---------- 6. rate limits and tokens ----------
G.usage_pct = 85
run(fb_pages.poll_page(GOLF))
check("usage at 85%: the Page skips the next cycles", GOLF not in fb_pages.due_pages(), fb_pages.due_pages())
G.usage_pct = 0
d = fb_pages._load(); d["pages"][GOLF]["backoff_until"] = 0; fb_pages._save(d)
G.error, G.wait_min = (80001, 0), 7
res = run(fb_pages.poll_page(GOLF))
pg = fb_pages._load()["pages"][GOLF]
check("error 80001: waits the minutes Meta reports", not res["ok"] and 6 * 60 < pg["backoff_until"] - time.time() <= 7 * 60 + 5,
      pg["backoff_until"] - time.time())
G.error, G.wait_min = (190, 460), 0
d = fb_pages._load(); d["pages"][GOLF]["backoff_until"] = 0; fb_pages._save(d)
run(fb_pages.poll_page(GOLF))
vv = {p["page_id"]: p for p in fb_pages.view()["pages"]}
check("dead token: Page stops and asks for a new login", not vv[GOLF]["token_ok"] and GOLF not in fb_pages.due_pages()
      and ("Đăng nhập" in vv[GOLF]["error"] or "Log in" in vv[GOLF]["error"]), vv[GOLF])
G.error = None
lu = fb_pages.login_url("https://unimate.example")
r3 = run(fb_pages.exchange_code("good", parse_qs(urlparse(lu["url"]).query)["state"][0]))
pk3 = fb_pages.pick(r3["nonce"], [GOLF, EXCEL])
check("logging in again renews both and the golf Page reads again",
      sorted(pk3["renewed"]) == sorted([GOLF, EXCEL]) and GOLF in fb_pages.due_pages(), pk3)

# ---------- 7. names once Meta allows them ----------
G.with_from = True
G.add_comment(p1, "c6", NOW - 30, "Đặt 2 cái", who=("902", "Lan Anh"))
run(fb_pages.poll_page(GOLF))
by = {m["external_message_id"]: m for m in conversations.tin_nhan(cid)}
check("new comment carries the name", by["c6"]["sender_name"] == "Lan Anh", by["c6"])
check("stored comments get the name filled in", by["c1"]["sender_name"] == "Huan Nguyen" and by["c3"]["sender_name"] == "Khach That",
      (by["c1"]["sender_name"], by["c3"]["sender_name"]))
check("the Page's own comment stays the owner's side", by["c2"]["sender_type"] == "human" and by["c2"]["sender_name"] == "")
check("view says names are on", {p["page_id"]: p for p in fb_pages.view()["pages"]}[GOLF]["names"])

# ---------- 8. followed posts ----------
p_ad = G.add_post(GOLF, 1003000000, NOW - 45 * 86400, "Bài cũ đang chạy quảng cáo")
G.add_comment(p_ad, "a1", NOW - 20, "Quảng cáo này còn giá cũ không?")
check("link with /posts/<id> resolves", run(fb_pages.follow(GOLF, "https://www.facebook.com/GolfShopHaNoi/posts/1003000000"))["ok"])
fb_pages.unfollow(GOLF, p_ad)
fr = run(fb_pages.follow(GOLF, "https://www.facebook.com/GolfShopHaNoi/posts/pfbid01003000000abc"))
check("pfbid link resolves through the Page's own posts", fr["ok"] and fr["post_id"] == p_ad, fr)
check("another Page's post is refused", not run(fb_pages.follow(GOLF, f"{EXCEL}_2001"))["ok"])
check("nonsense is refused with a hint", not run(fb_pages.follow(GOLF, "xin chao"))["ok"])
run(fb_pages.poll_page(GOLF))
check("followed post older than 30 days is read", conversations.count_account("facebook:" + GOLF)["conversations"] == 2)

# ---------- 9. personal data ----------
n = fb_pages.disconnect(GOLF)
check("disconnect first only counts", n["ok"] and n.get("confirm_needed") and n["comments"] > 0 and fb_pages.has_page(GOLF), n)
dd = fb_pages.disconnect(GOLF, confirm=True)
check("disconnect deletes the Page and every comment of it",
      dd["ok"] and not fb_pages.has_page(GOLF) and conversations.count_account("facebook:" + GOLF) == {"conversations": 0, "messages": 0},
      dd)
check("the other Page is untouched", fb_pages.has_page(EXCEL))
check("retention: 1 to 24 months only", not fb_pages.set_retention(0)["ok"] and not fb_pages.set_retention(25)["ok"])
fb_pages.set_retention(1)
pe_old = G.add_post(EXCEL, 2002, NOW - 3600, "Bài khác")
G.add_comment(pe_old, "e2", NOW - 1000, "cũ")
run(fb_pages.poll_page(EXCEL))
gone = fb_pages.purge(now=NOW + 40 * 86400)
check("comments older than the retention period are deleted", gone >= 2
      and conversations.count_account("facebook:" + EXCEL)["messages"] == 0, gone)
check("a conversation left empty is removed too", conversations.count_account("facebook:" + EXCEL)["conversations"] == 0)
fb_pages.set_retention(12)
out = log.getvalue()
check("log carries no token, secret or name", not any(s in out for s in list(TOK.values()) + [SECRET, USER_LONG, "Huan Nguyen"]), out)

# ---------- 10. registry and routes ----------
sp = channels.spec("facebook")
check("channel registered as an account kind, read only",
      sp and sp.kind == "account" and not sp.nl("tra_loi_tu_unimate") and not sp.nl("bot"), sp)

from fastapi import FastAPI  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
import routes.fb_pages as rt  # noqa: E402
app = FastAPI()
rt.register(app)
cl = TestClient(app, base_url="https://unimate.example")
s = cl.get("/facebook-pages/setup").json()
check("setup route: no token, no secret", s["ok"] and SECRET not in json.dumps(s) and not any(t in json.dumps(s) for t in TOK.values()))
lr = cl.get("/facebook-pages/login", follow_redirects=False)
check("login route redirects to the Facebook dialog", lr.status_code == 302 and lr.headers["location"].startswith(fb_pages.DIALOG))
st = parse_qs(urlparse(lr.headers["location"]).query)["state"][0]
G.accounts = [GOLF]
cb = cl.get(f"/facebook-pages/oauth/callback?code=good&state={st}")
check("callback page lists the Page with its name escaped", cb.status_code == 200 and "Golf &lt;HaNoi&gt;" in cb.text
      and "<HaNoi>" not in cb.text, cb.text[:300])
check("callback page carries no token", not any(t in cb.text for t in list(TOK.values()) + [USER_LONG]))
nonce = cb.text.split('name="nonce" value="', 1)[1].split('"', 1)[0]
pr = cl.post("/facebook-pages/pick", data={"nonce": nonce, "page_id": [GOLF]})
check("pick route connects the Page again", pr.status_code == 200 and fb_pages.has_page(GOLF))
ca = cl.get("/facebook-pages/oauth/callback?error=access_denied&error_description=User+denied")
check("a cancelled login says so", ca.status_code == 400 and "User denied" in ca.text)

check("no em dash in the new files", all("—" not in open(os.path.join(ROOT, p), encoding="utf-8").read()
                                          for p in ("server/fb_pages.py", "server/routes/fb_pages.py",
                                                    "server/channels/facebook.py", "dashboard/fb-pages.js")))
print()
if _fails:
    print(f"FAIL {len(_fails)}: {_fails}")
    sys.exit(1)
print("OK - test_fb_pages_0448: all pass")
