/* 0.448.0: Facebook Page comments card and its comments in the inbox.

       node tests/js/test_fb_pages_0448.js

   Runs the real render helpers of dashboard/fb-pages.js (no browser) and reads conversations.js for the inbox side. */
const fs = require("fs");
const path = require("path");

const ROOT = path.join(__dirname, "..", "..");
const D = (f) => fs.readFileSync(path.join(ROOT, "dashboard", f), "utf8");
const FB = require(path.join(ROOT, "dashboard", "fb-pages.js"));
const VI = JSON.parse(D("i18n/vi.json"));
const EN = JSON.parse(D("i18n/en.json"));

const fails = [];
const check = (name, cond, extra) => {
  console.log((cond ? "ok   " : "FAIL ") + name + (!cond && extra ? "  [" + extra + "]" : ""));
  if (!cond) fails.push(name);
};

const now = 1_800_000_000;
const base = { page_id: "111", name: "Golf <HaNoi>", watch: true, token_ok: true, error: "", last_at: now - 60,
  comments: 3, names: false, relogin_soon: false, slowed_until: 0, followed: [] };
check("reading Page shows as reading", FB.statusOf(base, now).text === "fbp.st_reading");
check("dead login comes first", FB.statusOf({ ...base, token_ok: false, error: "x", watch: false }, now).cls === "bad");
check("paused Page", FB.statusOf({ ...base, watch: false }, now).text === "fbp.st_paused");
check("login running out soon is a warning", FB.statusOf({ ...base, relogin_soon: true }, now).cls === "warn");
check("Facebook slowing reads is a warning", FB.statusOf({ ...base, slowed_until: now + 300 }, now).text === "fbp.st_slowed");

const card = FB.pageHtml({ ...base, followed: [{ post_id: "111_9", url: "https://www.facebook.com/x/posts/9" }] }, now);
check("Page name escaped", card.includes("Golf &lt;HaNoi&gt;") && !card.includes("<HaNoi>"));
check("no-name note while Meta hides names", card.includes("fbp.no_names"));
check("no-name note gone once names arrive", !FB.pageHtml({ ...base, names: true }, now).includes("fbp.no_names"));
check("read now, pause, disconnect, follow buttons",
  ["read", "watch", "disconnect", "follow", "unfollow"].every((a) => card.includes('data-act="' + a + '"')));

check("no card in Connected while no Page is connected", FB.groupHtml({ pages: [] }) === "");
const grp = FB.groupHtml({ pages: [base, { ...base, page_id: "222", token_ok: false }] });
check("connected card counts Pages and those needing a login", grp.includes("fbp.pages_n") && grp.includes("fbp.need_login_n"));
check("connected card can add Pages straight to the login", grp.includes("data-fbp-add"));
check("available card opens the settings", FB.catCard("chat").includes('data-fbp-open="1"'));

const noHttps = FB.setupHtml({ app_id: "1", app_secret_set: true, https: false, redirect_uri: "http://x/cb" });
check("login button disabled without HTTPS", /data-f="login" disabled/.test(noHttps) && noHttps.includes("fbp.need_https"));
const ready = FB.setupHtml({ app_id: "1", app_secret_set: true, https: true, redirect_uri: "https://x/cb", retention_months: 12 });
check("login button enabled once the app is saved on HTTPS", !/data-f="login" disabled/.test(ready));
check("secret field never prefilled", !/data-f="app_secret"[^>]*value=/.test(ready));
check("retention defaults to 12 months", /<option value="12" selected>/.test(ready));

const JS = D("fb-pages.js");
const keys = new Set((JS.match(/"fbp\.[a-z_]+"/g) || []).map((k) => k.slice(1, -1)));
const missing = [...keys].filter((k) => !(k in VI) || !(k in EN));
check("every fbp.* key exists in vi.json and en.json", missing.length === 0, missing.join(", "));
check("inbox labels exist", ["ht.fb_anon", "ht.fb_open"].every((k) => k in VI && k in EN));

const CONV = D("conversations.js");
check("inbox: nameless commenter reads 'Facebook user'", CONV.includes('fb && fb.anon ? window.t("ht.fb_anon")'));
check("inbox: link back to the comment, https only", CONV.includes("ht-fb-link") && CONV.includes("/^https:\\/\\//.test(fb.permalink"));
check("inbox: replies indented", CONV.includes("ht-fb-reply") && D("style.css").includes(".ht-msg.ht-fb-reply"));
check("card loaded by the dashboard", D("index.html").includes('/static/fb-pages.js'));
check("card mounted on the Connections page", D("console.js").includes('UniMateFbPages.mount(document.getElementById("mcpFbPages"))'));
check("channel logo is drawn", D("icons.js").includes("facebook: {"));

console.log();
if (fails.length) {
  console.log("FAIL " + fails.length + ": " + fails.join(" | "));
  process.exit(1);
}
console.log("OK - test_fb_pages_0448: all pass");
