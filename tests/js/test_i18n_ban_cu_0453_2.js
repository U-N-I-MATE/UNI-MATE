/* 0.453.2: right after an update the Settings blocks "Schedule machine" and "Continue when background work ends" showed
   raw keys (mcl.this, nt.on...). The server was still starting, sw.js handed back the kept OLD vi.json (no new keys),
   and nothing asked again because the dictionary was not empty.

    node tests/js/test_i18n_ban_cu_0453_2.js

   Checks: sw.js marks a kept copy; i18n/index.js uses it for now, asks again until the server answers, then loads the
   fresh one and announces it (unimate:i18n); both blocks draw again on that event. Loads the REAL index.js with fakes. */
const fs = require("fs");
const path = require("path");

const ROOT = path.resolve(__dirname, "..", "..");
const INDEX = path.join(ROOT, "dashboard/i18n/index.js");
const fails = [];
function check(name, cond, extra) {
  console.log((cond ? "ok   " : "FAIL ") + name + (cond || extra === undefined ? "" : "  [" + extra + "]"));
  if (!cond) fails.push(name);
}

const OLD = { "common.save": "Lưu" };
const NEW = { "common.save": "Lưu", "mcl.this": "Máy này" };
let serveOld = true, events = 0, fetches = 0;
global.localStorage = { getItem: () => "vi", setItem() {} };
global.sessionStorage = { getItem: () => String(Date.now()), setItem() {} };   // never reload the page in the test
global.document = { documentElement: { setAttribute() {} }, querySelectorAll: () => [], getElementById: () => null };
global.window = { addEventListener() {}, dispatchEvent() { events++; } };
global.CustomEvent = function () {};
global.location = { reload() { throw new Error("no reload in test"); } };
global.fetch = (url) => {
  fetches++;
  const old = serveOld;
  return Promise.resolve({
    ok: true,
    headers: { get: (h) => (old && h === "X-UniMate-Cu" ? "1" : null) },
    json: () => Promise.resolve(old ? OLD : NEW),
  });
};
require(INDEX);
const I = global.window.UniMateI18n;
const wait = (ms) => new Promise((r) => setTimeout(r, ms));

(async () => {
  await I.init("vi");
  check("the kept copy is used for now (page still readable)", I.t("common.save") === "Lưu");
  check("a key missing from the kept copy shows raw for now", I.t("mcl.this") === "mcl.this");
  const before = fetches;
  await wait(1200);
  check("while the server still hands the kept copy, UNI MATE asks again", fetches > before, fetches);
  serveOld = false;
  const ev = events;
  await wait(2600);
  check("once the server answers, the fresh dictionary is loaded", I.t("mcl.this") === "Máy này", I.t("mcl.this"));
  check("and announced so blocks draw again", events > ev);

  const sw = fs.readFileSync(path.join(ROOT, "dashboard/sw.js"), "utf8");
  check("sw.js marks both fallbacks (server error and no network)", (sw.match(/return danhDauCu\(cu\)/g) || []).length === 2
    && /h\.set\("X-UniMate-Cu", "1"\)/.test(sw));
  const mcl = fs.readFileSync(path.join(ROOT, "dashboard/may-chay-lich.js"), "utf8");
  const nt = fs.readFileSync(path.join(ROOT, "dashboard/noi-tiep.js"), "utf8");
  check("Schedule machine block draws again when the dictionary arrives",
    /addEventListener\("unimate:i18n", function \(\) \{ if \(_st\) render\(\); \}\)/.test(mcl));
  check("Follow-up block draws again when the dictionary arrives", /addEventListener\("unimate:i18n", draw\)/.test(nt));
  const html = fs.readFileSync(path.join(ROOT, "dashboard/index.html"), "utf8");
  check("script versions bumped so browsers take the new files",
    html.includes("/static/i18n/index.js?v=3") && html.includes("/static/may-chay-lich.js?v=5")
    && html.includes("/static/noi-tiep.js?v=2"));

  console.log();
  if (fails.length) { console.log("FAIL " + fails.length + ": " + fails.join(" | ")); process.exit(1); }
  console.log("OK - test_i18n_ban_cu_0453_2.js: all pass");
  process.exit(0);
})();
