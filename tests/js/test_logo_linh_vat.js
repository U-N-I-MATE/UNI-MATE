/* Logo, favicon và linh vật mặc định là CÙNG MỘT nhân vật: linh vật UNI MATE.

       node tests/js/test_logo_linh_vat.js

   Chủ dự án chốt 01/11/2026: linh vật UNI MATE là D2 "mắt long lanh" của UNI TECH (thân Tím
   công nghệ #5B2DA0, chấm vàng, má hồng, mắt tròng trắng); logo, biểu tượng app, favicon và
   linh vật mặc định đều là hình đó (thay ngôi sao cam của bản gốc). Ba thứ này nằm ở ba chỗ
   khác nhau (dashboard/logo.svg + các PNG xuất từ nó, bảng SHAPES/PALETTES trong pet.js,
   MAC_DINH), nên rất dễ lệch nhau khi một chỗ được sửa mà chỗ kia quên. Test này khoá sự trùng
   khớp đó.

   KHÔNG dùng ký tự em dash. */
const fs = require("fs");
const path = require("path");
const ROOT = path.resolve(__dirname, "..", "..");
const read = (p) => fs.readFileSync(path.join(ROOT, p), "utf8");
const fails = [];
function check(name, cond, extra) {
  console.log((cond ? "ok   " : "FAIL ") + name + (cond || extra === undefined ? "" : "  [" + extra + "]"));
  if (!cond) fails.push(name);
}

const pet = read("dashboard/pet.js");
const svg = read("dashboard/logo.svg");
const dThan = (/uni:\s+\{ key: "pet\.shape\.uni",\s+d: "([^"]+)"/.exec(pet) || [])[1] || "";
const uni = /uni:\s+\{ key: "pet\.color\.uni",\s+sun: \["(#\w{6})"/.exec(pet) || [];

check("linh vật mặc định là linh vật UNI MATE", /var MAC_DINH = \{[^}]*shape: "uni"/.test(pet));
check("linh vật mặc định dùng bảng màu UNI MATE", /var MAC_DINH = \{[^}]*palette: "uni"/.test(pet));
check("nút Đặt lại trả về đúng linh vật UNI MATE",
  /P\.setCfg\(\{ shape: "uni", palette: "uni",/.test(read("dashboard/console.js")));
check("logo.svg vẽ ĐÚNG đường thân của linh vật", dThan.length > 50 && svg.split(dThan).length - 1 === 1,
  "số lần xuất hiện: " + (svg.split(dThan).length - 1));
check("thân logo cùng màu thân bảng UNI MATE (Tím công nghệ)", uni[1] === "#5B2DA0" && svg.includes('fill="' + uni[1] + '"'), uni[1]);
check("logo có chấm vàng #C9A24B", /<circle cx="160" cy="108.5" r="15.6" fill="#C9A24B"\/>/.test(svg));
const trong = svg.match(/<ellipse [^>]*rx="14.04" ry="16.38" fill="#FFFFFF"\/>/g) || [];
const nguoi = svg.match(/fill="#1E1B33"/g) || [];
check("logo có đôi mắt tròng trắng, con ngươi tối", trong.length === 2 && nguoi.length === 2, trong.length + "/" + nguoi.length);
check("logo không có miệng (miệng chỉ hiện ở con pet khi cần)", !/stroke=/.test(svg) && (svg.match(/<ellipse/g) || []).length === 6);
check("má hồng nằm trong nhóm id=\"ma\" để favicon bỏ đi được", /<g id="ma">(<ellipse [^>]*fill="#E9A6C9"[^>]*\/>){2}<\/g>/.test(svg));
check("favicon xuất từ logo.svg nhưng bỏ má hồng", /favicon\.png", khong_ma, 64/.test(read("tools/gen_logo.py")));
check("logo nền trong suốt (không có hình nền)", !/<rect/.test(svg));

// Các PNG phải là ảnh vuông đúng cỡ (đọc thẳng header PNG, khỏi cần thư viện ảnh).
for (const [ten, px] of [["logo.png", 512], ["icon-512.png", 512], ["icon-192.png", 192], ["favicon.png", 64]]) {
  const b = fs.readFileSync(path.join(ROOT, "dashboard", ten));
  const w = b.readUInt32BE(16), h = b.readUInt32BE(20), kieuMau = b[25];
  check(ten + " là PNG " + px + "x" + px + " có kênh trong suốt", b.toString("latin1", 1, 4) === "PNG" && w === px && h === px && kieuMau === 6,
    w + "x" + h + " kieu " + kieuMau);
}

console.log(fails.length ? "\nFAIL: " + fails.join(", ") : "\nTat ca OK");
process.exit(fails.length ? 1 : 0);
