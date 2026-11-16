/* 0.452.0: Settings block "Schedule machine" (dashboard/may-chay-lich.js).
 *
 *     node tests/js/test_may_chay_lich_0452.js
 *
 * The block shows this machine, the machine that runs schedules, and the link between the home PC and the VPS. Locks:
 * the banner text only when this machine does not run schedules; the VPS offers a link code, an unlinked home PC a
 * password field to paste it, a linked one its status; everything from the server is escaped. */
var fails = [];
function check(name, cond, extra) {
  console.log((cond ? "ok   " : "FAIL ") + name + (!cond && extra ? "  [" + extra + "]" : ""));
  if (!cond) fails.push(name);
}

var box = { innerHTML: "", contains: function () { return true; } };
var nodes = { mclBox: box };
global.window = { t: function (k, v) { return k + (v ? JSON.stringify(v) : ""); } };
global.document = {
  readyState: "complete",
  getElementById: function (id) { return nodes[id] || null; },
  createElement: function () { return {}; },
  head: { appendChild: function (el) { nodes.mclCss = el; } },
  addEventListener: function () {},
};
var answers = [];
global.fetch = function () { return Promise.resolve({ json: function () { return Promise.resolve(answers.shift()); } }); };
var M = require("../../dashboard/may-chay-lich.js");

(async function () {
  var vps = { machine: { id: "a", kind: "vps", label: "jin.unihq.vn" }, runner: "vps", is_runner: true, runner_label: "jin.unihq.vn",
    linked: false, peers: [{ id: "b", kind: "home", label: "nguyen-huan" }], pair_codes: 1, pending: 0 };
  answers.push(vps);
  await M.load();
  check("the VPS that runs schedules shows no banner", M.bannerText() === "");
  check("the VPS offers a link code and lets the owner revoke old ones",
    box.innerHTML.indexOf('data-mcl="code"') >= 0 && box.innerHTML.indexOf('data-mcl="revoke"') >= 0);
  check("both choices drawn as pressed/unpressed buttons",
    box.innerHTML.indexOf('data-v="vps" aria-pressed="true"') >= 0 && box.innerHTML.indexOf('data-v="home" aria-pressed="false"') >= 0);
  check("machines seen are listed", box.innerHTML.indexOf("nguyen-huan") >= 0);

  var home = { machine: { id: "b", kind: "home", label: "<img src=x>" }, runner: "vps", is_runner: false, runner_label: "jin.unihq.vn",
    linked: false, peers: [{ id: "a", kind: "vps", label: "jin.unihq.vn" }], pair_codes: 0, pending: 0 };
  answers.push(home);
  await M.load();
  check("home that does not run schedules gets the banner naming where they run",
    M.bannerText().indexOf("mcl.banner") === 0 && M.bannerText().indexOf("jin.unihq.vn") > 0);
  check("unlinked home: a password field to paste the code, and a Link button",
    box.innerHTML.indexOf('id="mclCode" type="password" autocomplete="off"') >= 0 && box.innerHTML.indexOf('data-mcl="link"') >= 0);
  check("labels from the server are escaped", box.innerHTML.indexOf("<img src=x>") < 0 && box.innerHTML.indexOf("&lt;img") >= 0);

  answers.push(Object.assign({}, home, { linked: true, link_url: "https://jin.unihq.vn", link_ok: false, link_error: "HTTP 401", pending: 2 }));
  await M.load();
  check("linked home shows the VPS address, the failure, the waiting runs and Unlink",
    box.innerHTML.indexOf("https://jin.unihq.vn") >= 0 && box.innerHTML.indexOf("HTTP 401") >= 0
    && box.innerHTML.indexOf("mcl.pending") >= 0 && box.innerHTML.indexOf('data-mcl="unlink"') >= 0
    && box.innerHTML.indexOf("mclCode") < 0);

  console.log();
  if (fails.length) { console.log("FAIL " + fails.length + ": " + fails.join(" | ")); process.exit(1); }
  console.log("OK - test_may_chay_lich_0452.js: all pass");
})();
