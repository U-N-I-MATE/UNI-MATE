/* 0.446.0: a message sent through the outside AI gate shows clean text plus "Sent from <source>".

       node tests/js/test_gate_bubble_0446.js

   The server stores the message with a "[GỬI QUA CỔNG UNI MATE: <source>. ...]" block in front (server/gate_api.py
   `block`), so the model knows where it came from. The bubble must show only what was asked, and say who sent it.
   Runs the real `gateSource` and `chuNguoiGo` taken from app.js. */
const fs = require("fs");
const path = require("path");

const ROOT = path.join(__dirname, "..", "..");
const D = (f) => fs.readFileSync(path.join(ROOT, "dashboard", f), "utf8");
const APP = D("app.js");
const CSS = D("style.css");
const LANG = {};
for (const l of ["vi", "en", "de"]) LANG[l] = JSON.parse(D(path.join("i18n", l + ".json")));

const fails = [];
const check = (name, cond, extra) => {
  console.log((cond ? "ok   " : "FAIL ") + name + (!cond && extra ? "  [" + extra + "]" : ""));
  if (!cond) fails.push(name);
};

function grab(name) {
  const i = APP.indexOf("function " + name + "(");
  if (i < 0) throw new Error("no function " + name + " in app.js");
  const j = APP.indexOf("\n}\n", i);
  return APP.slice(i, j + 3);
}
const consts = (APP.match(/const _KHOI_NGU_CANH = \[[^\n]*\];/) || [""])[0]
  + "\n" + (APP.match(/const _KHOI_CONG = [^\n]*;/) || [""])[0];
const fn = new Function(consts + "\n" + grab("gateSource") + "\n" + grab("chuNguoiGo")
  + "\nreturn { gateSource, chuNguoiGo };")();

// The exact block the server writes (kept in step with gate_api.block).
const block = (src) => `[GỬI QUA CỔNG UNI MATE: ${src}. Chủ trao đổi với ${src} rồi nhờ ${src} gửi tin này vào hội thoại. `
  + "Làm như chủ vừa gõ và trả lời ngay tại đây.]\n\n";
const GATE_PY = fs.readFileSync(path.join(ROOT, "server", "gate_api.py"), "utf8");
check("the block in this test matches server/gate_api.py",
  GATE_PY.includes('BLOCK_PREFIX = "[GỬI QUA CỔNG UNI MATE:"')
  && GATE_PY.includes("Chủ trao đổi với {n} rồi nhờ {n} gửi tin này vào hội thoại. ")
  && GATE_PY.includes("Làm như chủ vừa gõ và trả lời ngay tại đây.]\\n\\n"));

const sent = block("ChatGPT") + "Làm tiếp trang giỏ hàng.";
check("source read back: ChatGPT", fn.gateSource(sent) === "ChatGPT", fn.gateSource(sent));
check("source read back: Claude", fn.gateSource(block("Claude") + "x") === "Claude");
check("the bubble shows only what was asked", fn.chuNguoiGo(sent) === "Làm tiếp trang giỏ hàng.", fn.chuNguoiGo(sent));
check("a message the owner typed has no source", fn.gateSource("Làm tiếp trang giỏ hàng.") === "");
check("a message merely mentioning the block later has no source",
  fn.gateSource("xem lại [GỬI QUA CỔNG UNI MATE: ChatGPT. ...]") === "");
check("the gate block is the last known block (gateSource reads it from there)",
  /"\[GỬI QUA CỔNG UNI MATE:"\];/.test(APP));

// The bubble and the live frame.
check("appendUserMessage marks a gate message and draws the 'Sent from' line",
  APP.includes('const via = gateSource(text);') && APP.includes('" msg-gate"')
  && APP.includes('window.t("app.gate_from").replace("{src}", via)'));
check("the open tab draws the bubble on external_message",
  /data\.type === "external_message"\)[\s\S]{0,600}appendUserMessage\(data\.content/.test(APP));
check("style for the 'Sent from' line", CSS.includes(".msg-user .gate-from"));
for (const l of ["vi", "en", "de"]) {
  check(`${l}.json has app.gate_from with {src}`, String(LANG[l]["app.gate_from"] || "").includes("{src}"));
}

console.log();
if (fails.length) {
  console.log("FAIL " + fails.length + ": " + fails.join(" | "));
  process.exit(1);
}
console.log("OK - test_gate_bubble_0446: all pass");
