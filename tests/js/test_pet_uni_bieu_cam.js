/* Bộ biểu cảm của linh vật UNI MATE (mặc định). NẠP THẬT pet.js rồi gọi API công khai, soi mặt
   được vẽ.

       node tests/js/test_pet_uni_bieu_cam.js

   Chủ dự án chốt 01/11/2026 (bản vẽ Phuongan_Linhvat_UNIMATE_Bieucam):
     - mắt tròng trắng, nhắm mắt là nét trắng;
     - MẶC ĐỊNH KHÔNG CÓ MIỆNG, miệng chỉ hiện ở 04 lúc: Đang nói, Cười nhẹ (xong việc), Rất vui
       (người dùng thả tim), Ngạc nhiên (micro bắt được giọng);
     - miệng màu TRẮNG (miệng tối chìm vào thân tím ở giao diện sáng), to gấp 1,5 lần bản vẽ;
     - Rất vui là nửa vầng trăng có lưỡi hồng, KHÔNG phải tam giác (trông như miệng mèo);
     - chấm vàng bật lên trên đầu khi có việc mới, hạ xuống khi buồn ngủ;
     - logo, chân dung tĩnh không có miệng.

   KHÔNG dùng ký tự em dash. */
const fs = require("fs");
const path = require("path");
const ROOT = path.resolve(__dirname, "..", "..");
const fails = [];
function check(name, cond, extra) {
  console.log((cond ? "ok   " : "FAIL ") + name + (cond || extra === undefined ? "" : "  [" + extra + "]"));
  if (!cond) fails.push(name);
}
const nghe = {};

function nut() {
  return {
    _html: "", dataset: {}, hidden: false, classList: { add() {}, remove() {}, contains: () => false },
    style: { setProperty() {} }, setAttribute() {}, addEventListener() {}, appendChild() {},
    querySelector: () => nut(), querySelectorAll: () => [], getBoundingClientRect: () => ({ width: 72, height: 72, top: 0, left: 0 }),
    get innerHTML() { return this._html; }, set innerHTML(v) { this._html = String(v); },
  };
}
let now = 1000;
const hangRaf = [];
// Đồng hồ giả: setTimeout chạy khi nhip() đẩy thời gian qua mốc của nó (chớp mắt 130ms,
// gỡ hoạt ảnh 900ms), giống hệt trình duyệt chứ không chạy ngay hay không bao giờ chạy.
let hangHen = [];
const henGio = (cb, ms) => { hangHen.push({ luc: now + (ms || 0), cb }); return hangHen.length; };
const created = [];
const win = {
  matchMedia: () => ({ matches: false, addEventListener() {} }), addEventListener(ten, cb) { (nghe[ten] = nghe[ten] || []).push(cb); }, dispatchEvent() {},
  innerWidth: 1280, innerHeight: 800, unimateTheme: { isLight: () => true, on() {} },
};
const doc = {
  readyState: "complete", addEventListener() {}, querySelectorAll: () => [], querySelector: () => nut(),
  getElementById: () => null, body: nut(), activeElement: null,
  createElement: () => {
    const e = nut();
    // Giữ đúng MỘT đối tượng cho từng phần con, như DOM thật, để soi lại được sau này.
    const con = {};
    e.querySelector = (sel) => (con[sel] = con[sel] || nut());
    created.push(e);
    return e;
  },
};
new Function("window", "document", "localStorage", "fetch", "requestAnimationFrame", "cancelAnimationFrame",
  "performance", "CustomEvent", "FormData", "setTimeout", "clearTimeout",
  fs.readFileSync(path.join(ROOT, "dashboard", "pet.js"), "utf8"))(
  win, doc, { getItem: () => null, setItem() {} }, () => Promise.reject(new Error("offline")),
  (cb) => { hangRaf.push(cb); return hangRaf.length; }, () => {}, { now: () => now },
  function () {}, function () { this.append = () => {}; }, henGio, () => {});
const P = win.UniMatePet;
const el = created[0];
const mat = () => el.querySelector(".pet-eyes").innerHTML;
// Chạy vòng vẽ MỘT nhịp ở thời điểm `t` (không chạy mãi: mỗi nhịp tự xin nhịp sau).
function nhip(t) {
  now = t;
  const den = hangHen.filter(h => h.luc <= t);
  hangHen = hangHen.filter(h => h.luc > t);
  den.forEach(h => h.cb());
  const ds = hangRaf.splice(0); ds.forEach(cb => cb(t));
}
function hetChop() {
  const t = now + 140;
  now = t;
  const den = hangHen.filter(h => h.luc <= t);
  hangHen = hangHen.filter(h => h.luc > t);
  den.forEach(h => h.cb());
}
const coMieng = () => /class="pet-mieng"/.test(mat());

// ---- 0. Mặc định là linh vật UNI MATE, mắt tròng trắng, không miệng ----
check("mặc định là linh vật UNI MATE", P.get().shape === "uni" && P.get().palette === "uni");
P.setState("idle"); hetChop();
check("nghỉ: mắt tròng trắng, có con ngươi và đốm sáng", /pet-trong/.test(mat()) && /pet-nguoi/.test(mat()) && /pet-dom/.test(mat()));
check("nghỉ: KHÔNG có miệng", !coMieng(), mat());
check("đánh dấu kiểu mắt long lanh cho CSS (nét nhắm màu trắng)", el.dataset.kieuMat === "longlanh");

// ---- 1. Đang nói: mắt vẫn mở, miệng mấp máy ----
P.setState("speaking"); hetChop();
check("đang nói: có miệng mấp máy", /pet-mieng-noi/.test(mat()), mat());
check("đang nói: mắt vẫn mở (không phải ^^)", /pet-trong/.test(mat()));

// ---- 2. Ngạc nhiên khi micro bắt được giọng ----
P.setState("hearing"); hetChop();
check("micro bắt được giọng: miệng tròn ngạc nhiên", coMieng() && /<ellipse cx="0" cy="46" rx="9" ry="10"/.test(mat()), mat());
P.setState("listening"); hetChop();
check("đang chờ nghe: không miệng", !coMieng());

// ---- 3. Xong việc: cười nhẹ, mắt mở ----
P.setState("idle"); hetChop();
P.react("xong"); hetChop();
check("trả lời xong: mắt mở, miệng cười nhẹ", /pet-trong/.test(mat()) && /M-11 42 Q0 52 11 42/.test(mat()), mat());
for (let i = 1; i <= 15; i++) nhip(now + 200);
hetChop();
check("hết phản ứng thì miệng biến mất", !coMieng(), mat());

// ---- 4. Thả tim: rất vui, nửa vầng trăng có lưỡi hồng ----
check("pet nghe sự kiện thả tim unimate:react-positive", (nghe["unimate:react-positive"] || []).length === 1);
(nghe["unimate:react-positive"] || []).forEach((cb) => cb());
hetChop();
check("thả tim: mắt cười ^^ (nét trắng)", /M-12\.5 6\.2 Q0 -10\.9 12\.5 6\.2/.test(mat()), mat());
check("thả tim: miệng nửa vầng trăng có lưỡi hồng", /M-17 37 H17 Q17 58 0 58 Q-17 58 -17 37 Z/.test(mat()) && /fill:#f28db8/.test(mat()), mat());
check("không còn miệng tam giác (giống miệng mèo)", !/M-16 38 Q0 64 16 38 Z/.test(fs.readFileSync(path.join(ROOT, "dashboard", "pet.js"), "utf8")));
for (let i = 1; i <= 15; i++) nhip(now + 200);

// ---- 5. Miệng trắng, to gấp 1,5 lần, nằm giữa hai mắt ----
P.setState("speaking"); hetChop();
check("miệng màu trắng", /style="fill:#ffffff"/.test(mat()));
check("miệng to gấp 1,5 lần bản vẽ", /class="pet-mieng" transform="[^"]*scale\(1\.5\)/.test(mat()));
check("miệng nằm giữa hai mắt (cùng nhóm mắt nên liếc theo)", /<g transform="translate\(160 160\)"><g class="pet-mieng"/.test(mat()) || /translate\(\d+(\.\d+)? 160\)"><g class="pet-mieng"/.test(mat()), mat());

// ---- 6. Chấm vàng: có việc mới thì bật lên, buồn ngủ thì hạ xuống ----
P.setState("idle"); hetChop();
P.react("viecmoi");
check("có việc mới: chấm vàng bật lên trên đầu", el.dataset.cham === "len", el.dataset.cham);
check("app.js báo có việc mới khi việc nền trả kết quả", /UniMatePet\.react\("viecmoi"\)/.test(fs.readFileSync(path.join(ROOT, "dashboard", "app.js"), "utf8")));
now += 4100; hangHen.filter(h => h.luc <= now).forEach(h => h.cb()); hangHen = hangHen.filter(h => h.luc > now);
check("hết giờ thì chấm vàng hạ về", el.dataset.cham === undefined, el.dataset.cham);
P.setState("paused"); hetChop();
check("buồn ngủ: chấm vàng hạ xuống, mắt nhắm cong", el.dataset.cham === "xuong" && /M-12\.5 -1\.6 Q0 10\.9 12\.5 -1\.6/.test(mat()), el.dataset.cham);
const css = fs.readFileSync(path.join(ROOT, "dashboard", "style.css"), "utf8");
check("CSS dời chấm vàng lên / xuống", /\.pet\[data-cham="len"\] \.pet-cham \{ transform: translateY\(-70px\)/.test(css) && /\.pet\[data-cham="xuong"\] \.pet-cham/.test(css));
check("người tắt chuyển động: miệng đứng yên", /prefers-reduced-motion: reduce\) \{ \.pet-cham \{ transition: none; \} \.pet-mieng-noi \{ animation: none/.test(css));

// ---- 6b. Lỗi: mắt buồn đuôi cụp, không trông như mắt cười ----
P.setState("error"); hetChop();
check("lỗi: mắt buồn đuôi cụp (hai mắt đối xứng, không phải ^^)",
  /M-12\.5 4\.5 Q1 0\.5 12\.5 -3\.5/.test(mat()) && /M-12\.5 -3\.5 Q-1 0\.5 12\.5 4\.5/.test(mat()) && !coMieng(), mat());

// ---- 7. Chân dung tĩnh (avatar, dấu ấn thanh bên) không có miệng ----
const cd = P.previewSvg("uni", "uni", {});
check("chân dung tĩnh: thân, chấm vàng, má hồng, mắt tròng trắng, KHÔNG miệng",
  /fill="#C9A24B"/.test(cd) && /fill="#e9a6c9"/.test(cd) && /fill="#1e1b33"/.test(cd) && !/pet-mieng|f28db8/.test(cd));

if (fails.length) { console.log("\nFAIL: " + fails.length, fails); process.exit(1); }
console.log("\nOK - bộ biểu cảm linh vật UNI MATE");
