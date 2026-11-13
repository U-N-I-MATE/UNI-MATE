/* 0.451.0: what each progress step produced, drawn inside the step (like Claude's steps).
 *
 *     node tests/js/test_step_results_0451.js
 *
 * Locks the dashboard half of the feature (dashboard/chat-steps.js):
 *   - a tool_result closes the step with the SAME id, not just the last open one (engines run steps in parallel);
 *   - what the server sent is cleaned again before it is drawn or kept: only our own picture addresses, only
 *     Word/Excel/PDF/PowerPoint cards, short text;
 *   - the copy kept in the browser history is capped (localStorage is small);
 *   - pictures and file cards use the chat's existing lightbox and file viewer classes, everything escaped. */
function theMoi(ten) {
  return {
    tagName: ten, className: "", textContent: "", _html: "", _sel: {},
    get innerHTML() { return this._html; },
    set innerHTML(v) { this._html = String(v); },
    querySelector(sel) { return (this._sel[sel] = this._sel[sel] || theMoi("div")); },
    addEventListener(loai, fn) { this["on" + loai] = fn; },
    setAttribute(k, v) { this["attr_" + k] = v; },
    classList: {
      _t: new Set(),
      add(c) { this._t.add(c); }, remove(c) { this._t.delete(c); },
      toggle(c, tren) { if (tren === undefined) { if (this._t.has(c)) this._t.delete(c); else this._t.add(c); } else if (tren) this._t.add(c); else this._t.delete(c); },
      contains(c) { return this._t.has(c); },
    },
  };
}
global.document = { createElement: (t) => theMoi(t) };
const S = require("../../dashboard/chat-steps.js");

const fails = [];
function check(name, cond, them) {
  console.log((cond ? "ok   " : "FAIL ") + name + (!cond && them ? "  [" + them + "]" : ""));
  if (!cond) fails.push(name);
}

const IMG = "/step-media/abc123/" + "0123456789abcdef0123456789abcdef" + ".png";
const call = (tool, id) => ({ type: "tool_call", tool, id, detail: "x" });

// ---- matching by id
let st = S.nhan(null, call("Read", "t1"));
st = S.nhan(st, call("Bash", "t2"));
st = S.nhan(st, { type: "tool_result", id: "t1", res: { text: "nội dung tệp", more: 0 } });
check("a result with an id closes that step, not the last one",
  st.ds[0].xong && st.ds[0].res.text === "nội dung tệp" && !st.ds[1].xong, JSON.stringify(st.ds));
st = S.nhan(st, { type: "tool_result", res: { text: "ok" } });
check("a result without id still closes the last open step (older servers)", st.ds[1].xong && st.ds[1].res.text === "ok");
check("the step keeps its id", st.ds[0].id === "t1" && st.ds[1].id === "t2");
let st2 = S.nhan(S.nhan(null, call("Bash", "a")), { type: "tool_result", id: "a", res: { text: "" } });
check("a step that produced nothing gets no result part", st2.ds[0].xong && !st2.ds[0].res);

// ---- cleaning
const r = S.gonRes({
  text: "x".repeat(2000), more: "3", err: 0,
  imgs: [{ src: IMG }, { src: "https://evil.example/a.png" }, { src: "javascript:alert(1)" },
         { src: "/files/raw?brain=b&path=attachments%2Fa.png", path: "attachments/a.png" },
         { src: "/step-media/abc/0123456789abcdef0123456789abcdef.svg" }],
  files: [{ name: "a.docx", path: "exports/a.docx", kind: "Word" }, { name: "x.sh", path: "x.sh", kind: "Shell" },
          { name: "p.pdf", path: "../etc/p.pdf", kind: "PDF" }],
});
check("only our own picture addresses survive (no outside URL, no script, no SVG)",
  r.imgs.length === 2 && r.imgs[0].src === IMG && r.imgs[1].path === "attachments/a.png", JSON.stringify(r.imgs));
check("only document cards of the four kinds, no path climbing out of the brain",
  r.files.length === 1 && r.files[0].kind === "Word", JSON.stringify(r.files));
check("text capped at 600 characters, `more` a number", r.text.length === 600 && r.more === 3);
check("an empty result is nothing", S.gonRes({ text: "", imgs: [], files: [] }) === null && S.gonRes(null) === null);
check("an error with no text is still kept (the step shows Lỗi)", S.gonRes({ err: true }).err === true);
const many = S.gonRes({ text: "", imgs: Array.from({ length: 9 }, () => ({ src: IMG })) });
check("at most 4 pictures per step", many.imgs.length === 4);

// ---- what goes into the browser history
let big = null;
for (let i = 0; i < 20; i++) {
  big = S.nhan(big, call("Bash", "b" + i));
  big = S.nhan(big, { type: "tool_result", id: "b" + i, res: { text: "y".repeat(600), imgs: [{ src: IMG }] } });
}
const kept = S.gon(big);
const total = kept.ds.reduce((n, b) => n + (b.res ? b.res.text.length : 0), 0);
check("history copy: at most 300 characters per step and 4000 per turn",
  kept.ds.every((b) => !b.res || b.res.text.length <= 300) && total <= 4000, String(total));
check("history copy keeps the pictures, ids and step count",
  kept.ds[19].res.imgs.length === 1 && kept.ds[0].id === "b0" && kept.so === 20);
check("a cut text counts as more lines left", kept.ds[0].res.more >= 1);
const back = S.nhan(kept, { type: "tool_call", tool: "Read", id: "z" });
check("a history copy reads back as a normal step state", back.ds.length === 21 && back.so === 21);

// ---- drawing
const h = S.veRes({ text: "<b>a</b>", more: 2, err: false, imgs: [{ src: IMG }],
                    files: [{ name: 'a"><img src=x>.docx', path: "exports/a b.docx", kind: "Word" }] });
check("pictures use the chat lightbox link and the broken-picture handler",
  h.includes('class="jv-img-link" href="' + IMG + '"') && h.includes('class="chat-img step-img"') &&
  h.includes('onerror="jvImgGone(this)"'));
check("documents are file cards that open in the app viewer",
  h.includes('class="jv-floc step-file" href="#open=exports%2Fa%20b.docx"') &&
  h.includes('data-vault-path="exports/a b.docx"') && h.includes(">Word</span>"));
check("everything from the server is escaped",
  !h.includes("<b>a</b>") && h.includes("&lt;b&gt;") && !h.includes('a"><img src=x>'));
check("the text part says how many lines are left", h.includes('class="step-more"') && /2/.test(h));
check("an error step is marked", S.veRes({ text: "", err: true, imgs: [], files: [] }).includes("step-out-err"));

const el = S.ve(null, st, false);
const html = el.querySelector(".steps-list").innerHTML;
check("a step with text is clickable (button role, folded by default)",
  html.includes('has-text') && html.includes('role="button"') && html.includes('aria-expanded="false"') &&
  !html.includes("step-open"));
check("the steps block itself stays folded by default", el.classList.contains("steps-fold"));
el._moBuoc = { "i:t1": true };
const html2 = S.ve(el, st, false).querySelector(".steps-list").innerHTML;
check("a step the owner opened stays open when the block is drawn again",
  html2.includes('data-k="i:t1"') && /step-done has-text step-open" data-k="i:t1"/.test(html2), html2.slice(0, 300));
const plain = S.ve(null, S.nhan(null, call("Read", "q")), true).querySelector(".steps-list").innerHTML;
check("a running step with no result is drawn as before (no button)", !plain.includes('role="button"'));

console.log();
if (fails.length) { console.log("FAIL " + fails.length + ": " + fails.join(" | ")); process.exit(1); }
console.log("OK - test_step_results_0451.js: all pass");
