// Test logic dọn folder ngoài (📁) của brains-ui.js - mock DOM tối thiểu + fetch + localStorage.
// Chạy: node dashboard/test_brains_ui.mjs
// Kịch bản = đúng bug thật: 📁 "brain" (đã xoá khỏi đĩa) + 📁 trùng path 1 não thật phải bị dọn,
// 📁 folder ngoài hợp lệ (D:\My Bullet Journal) phải GIỮ.
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const SRC = fs.readFileSync(path.join(__dirname, "../../dashboard/brains-ui.js"), "utf8");

const fails = [];
const check = (name, cond) => { console.log((cond ? "ok   " : "FAIL ") + name); if (!cond) fails.push(name); };

const REAL = [
  { name: "Brain Default", path: "D:\\Project\\UNI-MATE\\brains\\Brain Default", notes: 90, is_default: true },
  { name: "My Bullet Journal", path: "D:\\Project\\UNI-MATE\\brains\\My Bullet Journal", notes: 576 },
  { name: "Ngọc Thu Phạm", path: "D:\\Project\\UNI-MATE\\brains\\Ngọc Thu Phạm", notes: 111 },
];
// Server: path nào còn là thư mục.
const EXISTS = {
  "D:\\Project\\UNI-MATE\\brain": { exists: false, is_dir: false },          // 📁 brain: đã xoá
  "D:\\My Bullet Journal": { exists: true, is_dir: true },                    // 📁 ngoài hợp lệ
};

// ---- Mock Option ----
class Opt {
  constructor(value = "", text = "") { this.value = value; this.textContent = text; this.dataset = {}; this._parent = null; }
  get nextSibling() { const a = this._parent?._kids; if (!a) return null; const i = a.indexOf(this); return i >= 0 && i + 1 < a.length ? a[i + 1] : null; }
  remove() { const a = this._parent?._kids; if (a) { const i = a.indexOf(this); if (i >= 0) a.splice(i, 1); } this._parent = null; }
}
class Frag { constructor() { this._kids = []; } appendChild(o) { this._kids.push(o); return o; } }

// ---- Mock Select ----
class Select {
  constructor() { this._kids = []; this._value = "brain"; }
  _all() { return this._kids; }
  _match(o, sel) {
    if (sel === "option[data-brain]") return o.dataset.brain !== undefined;
    if (sel === "option[data-custom]") return o.dataset.custom !== undefined;
    if (sel === 'option[value="brain"]') return o.value === "brain";
    // Thư mục ngoài giờ nằm trong <optgroup> (thẻ <option> không nhận được icon
    // nên dùng nhóm để phân biệt). Mock này chỉ dựng Opt phẳng, không dựng
    // optgroup, nên đúng là không khớp gì - trả false thay vì ném lỗi.
    if (sel === "optgroup" || sel === "optgroup[data-custom-group]") return false;
    throw new Error("selector chưa mock: " + sel);
  }
  querySelectorAll(sel) { return this._kids.filter((o) => this._match(o, sel)); }
  querySelector(sel) { return this._kids.find((o) => this._match(o, sel)) || null; }
  appendChild(node) {
    const kids = node instanceof Frag ? node._kids : [node];
    for (const k of kids) { k._parent = this; this._kids.push(k); }
    if (node instanceof Frag) node._kids = [];
    return node;
  }
  insertBefore(node, ref) {
    const kids = node instanceof Frag ? node._kids : [node];
    let idx = ref ? this._kids.indexOf(ref) : -1;
    if (idx < 0) idx = this._kids.length;
    for (const k of kids) k._parent = this;
    this._kids.splice(idx, 0, ...kids);
    if (node instanceof Frag) node._kids = [];
    return node;
  }
  get options() { return this._kids; }
  get selectedIndex() { return this._kids.findIndex((o) => o.value === this._value); }
  get value() { return this._value; }
  set value(v) { this._value = v; }
  dispatchEvent(e) { (this._ls[e && e.type] || []).forEach((f) => f(e)); return true; }
  addEventListener(t, f) { (this._ls[t] = this._ls[t] || []).push(f); }
  get _ls() { return this.__ls || (this.__ls = {}); }
}

const sel = new Select();
// Trạng thái khởi đầu: default + 2 option 📁 (như app.js đã render từ localStorage).
const def = new Opt("brain", "🧠 Brain Default"); sel.appendChild(def);
const c1 = new Opt("path:D:\\Project\\UNI-MATE\\brain", "📁 brain"); c1.dataset.custom = "1"; sel.appendChild(c1);
const c2 = new Opt("path:D:\\My Bullet Journal", "📁 My Bullet Journal"); c2.dataset.custom = "1"; sel.appendChild(c2);
const c3 = new Opt("path:D:\\Project\\UNI-MATE\\brains\\My Bullet Journal", "📁 My Bullet Journal"); c3.dataset.custom = "1"; sel.appendChild(c3); // TRÙNG não thật

// localStorage khởi đầu (3 entry, có 1 trùng não thật)
const store = {
  "unimate.brains": JSON.stringify([
    { name: "brain", path: "D:\\Project\\UNI-MATE\\brain" },
    { name: "My Bullet Journal", path: "D:\\My Bullet Journal" },
    { name: "My Bullet Journal", path: "D:\\Project\\UNI-MATE\\brains\\My Bullet Journal" },
  ]),
  "unimate.graphSource": "brain",
};

// ---- Globals ----
const btns = {};
global.document = {
  getElementById: (id) => id === "graphSource" ? sel : (btns[id] || (btns[id] = { addEventListener() {} })),
  createElement: () => new Opt(),
  createDocumentFragment: () => new Frag(),
};
global.localStorage = { getItem: (k) => (k in store ? store[k] : null), setItem: (k, v) => { store[k] = String(v); } };
const winLs = {};
global.window = {
  t: (k) => (global.__i18nReady ? "T:" + k : k),
  addEventListener: (t, f) => { (winLs[t] = winLs[t] || []).push(f); },
};
global.Event = class { constructor(t) { this.type = t; } };
global.fetch = async (url) => {
  if (url === "/brains") return { json: async () => ({ dir: "D:\\...", brains: REAL }) };
  if (url.startsWith("/path/exists?path=")) {
    const p = decodeURIComponent(url.split("path=")[1]);
    const r = EXISTS[p] || { exists: false, is_dir: false };
    return { ok: true, json: async () => ({ path: p, ...r }) };
  }
  throw new Error("fetch chưa mock: " + url);
};

// ---- Nạp module (IIFE tự chạy loadBrains(null,true)) ----
eval(SRC);

// loadBrains async → chờ microtask lắng
await new Promise((r) => setTimeout(r, 50));

// ---- Assert ----
const customVals = sel.querySelectorAll("option[data-custom]").map((o) => o.value);
const brainNames = sel.querySelectorAll("option[data-brain]").map((o) => o.dataset.brainName);
const stored = JSON.parse(store["unimate.brains"]);

check("📁 'brain' (đã xoá) bị gỡ khỏi menu", !customVals.includes("path:D:\\Project\\UNI-MATE\\brain"));
check("📁 trùng não thật bị gỡ khỏi menu", !customVals.includes("path:D:\\Project\\UNI-MATE\\brains\\My Bullet Journal"));
check("📁 folder ngoài hợp lệ được GIỮ", customVals.includes("path:D:\\My Bullet Journal"));
check("chỉ còn ĐÚNG 1 option 📁", customVals.length === 1);
check("localStorage còn ĐÚNG 1 entry", stored.length === 1 && stored[0].path === "D:\\My Bullet Journal");
check("🧠 não thật (không default) render đủ 2", brainNames.length === 2 && brainNames.includes("My Bullet Journal") && brainNames.includes("Ngọc Thu Phạm"));
check("option default cập nhật nhãn kèm note", def.textContent.includes("Brain Default") && def.textContent.includes("90"));

// ---- Test 2: fail-safe khi endpoint 404 (server chưa restart) → KHÔNG xoá gì ----
const sel2 = new Select();
sel2.appendChild(new Opt("brain", "🧠 Brain Default"));
const d1 = new Opt("path:D:\\mot\\folder", "📁 folder"); d1.dataset.custom = "1"; sel2.appendChild(d1);
const store2 = { "unimate.brains": JSON.stringify([{ name: "folder", path: "D:\\mot\\folder" }]), "unimate.graphSource": "brain" };
global.document.getElementById = (id) => id === "graphSource" ? sel2 : (btns[id] || (btns[id] = { addEventListener() {} }));
global.localStorage = { getItem: (k) => (k in store2 ? store2[k] : null), setItem: (k, v) => { store2[k] = String(v); } };
global.fetch = async (url) => {
  if (url === "/brains") return { json: async () => ({ brains: [REAL[0]] }) };
  if (url.startsWith("/path/exists")) return { ok: false, status: 404, json: async () => ({ error: "not found" }) };
  throw new Error("fetch chưa mock: " + url);
};
eval(SRC);
await new Promise((r) => setTimeout(r, 50));
const stored2 = JSON.parse(store2["unimate.brains"]);
check("fail-safe: endpoint 404 → GIỮ nguyên entry (không xoá nhầm)", stored2.length === 1 && sel2.querySelectorAll("option[data-custom]").length === 1);

// ---- Test 3 (0.442.0): não là LỐI TẮT trong thư mục brains, thư mục ngoài trỏ thẳng tới thư mục thật ----
// Đúng cảnh máy chủ dự án 04/11/2026: brains/Bonao_AI -> D:\9. AI\...\Bonao_AI, menu hiện Bonao_AI hai lần.
const LINKED = [
  { name: "Brain Default", path: "D:\\U\\brains\\Brain Default", real: "D:\\U\\brains\\Brain Default", notes: 21, is_default: true },
  { name: "Bonao_AI", path: "D:\\U\\brains\\Bonao_AI", real: "D:\\9. AI\\01. BRAIN PROJECT\\Bonao_AI", notes: 1136 },
];
function moi(customs, chon) {
  const s3 = new Select();
  s3.appendChild(new Opt("brain", "Brain Default"));
  customs.forEach((c) => { const o = new Opt("path:" + c, c); o.dataset.custom = "1"; s3.appendChild(o); });
  s3.value = chon;
  const st = { "unimate.brains": JSON.stringify(customs.map((c) => ({ name: "x", path: c }))), "unimate.graphSource": chon };
  const b3 = {};
  global.document.getElementById = (id) => id === "graphSource" ? s3 : (b3[id] || (b3[id] = { hidden: false, addEventListener() {} }));
  global.localStorage = { getItem: (k) => (k in st ? st[k] : null), setItem: (k, v) => { st[k] = String(v); } };
  return { s3, st, b3 };
}
// Thư mục ngoài viết khác chữ (gạch chéo xuôi, chữ thường): /path/exists trả `real` đã đi theo lối tắt.
const EX3 = {
  "D:\\9. AI\\01. BRAIN PROJECT\\Bonao_AI": { exists: true, is_dir: true, real: "D:\\9. AI\\01. BRAIN PROJECT\\Bonao_AI" },
  "E:\\lien-ket\\bonao": { exists: true, is_dir: true, real: "D:\\9. AI\\01. BRAIN PROJECT\\Bonao_AI" },
  "D:\\Ghi chu": { exists: true, is_dir: true, real: "D:\\Ghi chu" },
};
global.fetch = async (url) => {
  if (url === "/brains") return { json: async () => ({ brains: LINKED }) };
  if (url.startsWith("/path/exists?path=")) {
    const p = decodeURIComponent(url.split("path=")[1]);
    return { ok: true, json: async () => ({ path: p, ...(EX3[p] || { exists: false, is_dir: false }) }) };
  }
  throw new Error("fetch chưa mock: " + url);
};
let t3 = moi(["D:\\9. AI\\01. BRAIN PROJECT\\Bonao_AI\\", "E:\\lien-ket\\bonao", "D:\\Ghi chu"],
             "path:D:\\9. AI\\01. BRAIN PROJECT\\Bonao_AI\\");
eval(SRC);
await new Promise((r) => setTimeout(r, 50));
let cv3 = t3.s3.querySelectorAll("option[data-custom]").map((o) => o.value);
check("lối tắt: thư mục ngoài trùng ĐƯỜNG DẪN THẬT của não (khác chữ, có / cuối) bị gỡ", !cv3.some((v) => v.includes("Bonao_AI")));
check("lối tắt: thư mục ngoài là một lối tắt khác tới cùng thư mục cũng bị gỡ", !cv3.includes("path:E:\\lien-ket\\bonao"));
check("lối tắt: thư mục ngoài khác vẫn GIỮ", cv3.length === 1 && cv3[0] === "path:D:\\Ghi chu");
check("đang chọn thư mục trùng: chuyển sang CHÍNH não đó, không về Brain mặc định",
      t3.s3.value === "path:D:\\U\\brains\\Bonao_AI" && t3.st["unimate.graphSource"] === t3.s3.value);
const lf = await global.window.UniMateBrains.linkedFor("e:/lien-ket/bonao/");
const lf2 = await global.window.UniMateBrains.linkedFor("E:\\lien-ket\\bonao");
const lf3 = await global.window.UniMateBrains.linkedFor("D:\\Ghi chu");
check("linkedFor: chọn thư mục là não đã kết nối -> trả option của não", lf2 === "path:D:\\U\\brains\\Bonao_AI");
check("linkedFor: thư mục không phải não -> null", lf3 === null && lf === null);

// ---- Test 4: nút Gỡ thư mục ngoài + nhãn nhóm sau khi từ điển về ----
t3 = moi(["D:\\Ghi chu"], "brain");
eval(SRC);
await new Promise((r) => setTimeout(r, 50));
check("chọn não: ẩn nút Gỡ, hiện Đổi tên + Xoá",
      t3.b3.removeFolderBtn.hidden === true && t3.b3.renameBrainBtn.hidden === false && t3.b3.delBrainBtn.hidden === false);
t3.s3.value = "path:D:\\Ghi chu";
t3.s3.dispatchEvent(new Event("change"));
check("chọn thư mục ngoài: hiện nút Gỡ, ẩn Đổi tên + Xoá",
      t3.b3.removeFolderBtn.hidden === false && t3.b3.renameBrainBtn.hidden === true && t3.b3.delBrainBtn.hidden === true);
const SRC_I18N_OK = SRC.includes('window.addEventListener("unimate:i18n", relabel)') && SRC.includes('g.label = window.t("app.external_folder")');
check("nhãn nhóm thư mục ngoài vẽ lại khi từ điển về (unimate:i18n)", SRC_I18N_OK && (winLs["unimate:i18n"] || []).length > 0);
const HTML = fs.readFileSync(path.join(__dirname, "../../dashboard/index.html"), "utf8");
check("index.html có nút removeFolderBtn, ẩn sẵn, có khoá dịch",
      /id="removeFolderBtn" hidden[^>]*data-i18n-title="top.brain_remove_folder"/.test(HTML));
for (const l of ["vi", "en", "de"]) {
  const d = JSON.parse(fs.readFileSync(path.join(__dirname, `../../dashboard/i18n/${l}.json`), "utf8"));
  check(`${l}.json có top.brain_remove_folder`, typeof d["top.brain_remove_folder"] === "string");
}

console.log();
if (fails.length) { console.log(`${fails.length} FAIL: ${fails.join(", ")}`); process.exit(1); }
console.log("TẤT CẢ PASS");
