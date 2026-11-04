// ============================================================
// brains-ui.js - Nhiều second brain trong 1 thư mục (BRAINS_DIR), nạp TỪ SERVER.
// Bổ sung cho app.js, KHÔNG sửa app.js (file UTF-16 dễ hỏng). Chỉ thao tác DOM:
//   - Đổ dropdown #graphSource từ GET /brains (thay vì localStorage).
//   - Nút #newBrainBtn → POST /brains/new tạo brain mới.
//   - Nút #delBrainBtn → POST /brains/delete xoá brain ĐANG CHỌN (xác nhận gõ đúng tên).
// Vẫn giữ "chọn folder ngoài bất kỳ" (option data-custom do app.js thêm).
// ============================================================
(function () {
  const sel = document.getElementById("graphSource");
  if (!sel) return;

  function label(b) {
    // notes_capped = server dừng đếm ở trần, con số là SÀN chứ không phải tổng thật.
    // Thêm dấu + để không nói dối; brain thường không bao giờ chạm trần này.
    const n = b.notes ? " · " + b.notes + (b.notes_capped ? "+" : "") : "";
    // Không gắn icon: <option> chỉ nhận chữ. Thư mục ngoài được app.js xếp vào
    // <optgroup> riêng nên vẫn phân biệt được mà không cần ký hiệu nào.
    // 0.219.0: tên hiển thị (label) tách khỏi thư mục; server luôn trả label, bản cũ chưa có thì dùng tên thư mục.
    return (b.label || b.name) + n;
  }

  // Chuẩn hoá path để so trùng: bỏ dấu phân cách cuối, \ -> /, thường hoá (Windows không phân biệt hoa/thường).
  function normPath(p) {
    return (p || "").replace(/[\\/]+$/, "").replace(/\\/g, "/").toLowerCase();
  }

  // Hỏi server 1 path còn là thư mục không. FAIL-SAFE: mọi trường hợp không CHẮC CHẮN (lỗi
  // mạng, endpoint thiếu/404 vì server chưa restart, JSON méo) → {is_dir:null} = CHƯA xác định
  // → GIỮ entry. Chỉ dọn khi server trả rõ is_dir=false. Tránh xoá nhầm folder ngoài hợp lệ.
  async function pathExists(p) {
    try {
      const resp = await fetch("/path/exists?path=" + encodeURIComponent(p));
      if (!resp.ok) return { exists: null, is_dir: null };
      const j = await resp.json();
      if (!j || typeof j.is_dir === "undefined") return { exists: null, is_dir: null };
      return j;
    } catch (e) {
      return { exists: null, is_dir: null };
    }
  }

  // Não đã kết nối, khoá theo đường dẫn ĐÃ CHUẨN HOÁ (cả `path` lẫn `real`) -> giá trị option của nó.
  // 0.442.0: so cả `real` (server đã đi theo lối tắt). Một não thường là lối tắt trong thư mục brains
  // trỏ tới kho ghi chú ở nơi khác (máy chủ dự án: brains/Bonao_AI -> D:/9. AI/.../Bonao_AI). Chỉ so
  // `path` thì thư mục ngoài trỏ thẳng tới D:/... không khớp, và menu hiện cùng một thư mục hai lần.
  let _lastBrains = [];
  function linkedMap(realBrains) {
    const m = new Map();
    (realBrains || []).forEach((b) => {
      const v = b.is_default ? "brain" : "path:" + b.path;
      [b.path, b.real].forEach((p) => { if (p) m.set(normPath(p), v); });
    });
    return m;
  }

  // Thư mục ngoài `p` có chính là một não đã kết nối không. Trả giá trị option của não đó, hoặc null.
  async function linkedFor(p, realBrains) {
    const m = linkedMap(realBrains || _lastBrains);
    if (m.has(normPath(p))) return m.get(normPath(p));
    const chk = await pathExists(p);
    if (chk && chk.real && m.has(normPath(chk.real))) return m.get(normPath(chk.real));
    return null;
  }

  // Dọn danh sách thư mục ngoài (localStorage) đã hỏng: bỏ entry TRÙNG với 1 não thật (kể cả
  // trùng qua lối tắt), và entry mà path KHÔNG còn là thư mục (đã xoá khỏi ổ đĩa). Giữ folder
  // ngoài hợp lệ + entry chưa xác định được (tránh xoá nhầm khi server chớp lỗi). Nguồn sự thật
  // là localStorage nên dọn cả nó → lần app.js render sau vẫn đúng, không "sống lại" qua update.
  // Đang chọn đúng thư mục ngoài trùng thì chuyển sang chính não đó, không về Brain mặc định.
  async function pruneCustomBrains(realBrains) {
    let list;
    try { list = JSON.parse(localStorage.getItem("unimate.brains") || "[]"); }
    catch (e) { list = []; }
    if (!Array.isArray(list)) list = [];
    const m = linkedMap(realBrains);
    const thay = new Map();   // "path:<thư mục ngoài>" -> option của não trùng
    const kept = [];
    for (const b of list) {
      if (!b || !b.path) continue;
      if (m.has(normPath(b.path))) { thay.set("path:" + b.path, m.get(normPath(b.path))); continue; }
      const chk = await pathExists(b.path);
      if (chk && chk.real && m.has(normPath(chk.real))) { thay.set("path:" + b.path, m.get(normPath(chk.real))); continue; }
      if (chk && chk.is_dir === true) { kept.push(b); continue; }   // còn thư mục → giữ
      if (chk && chk.exists === null) { kept.push(b); continue; }   // chưa xác định → giữ
      // còn lại: đã bị xoá / không phải thư mục → loại
    }
    if (kept.length !== list.length) {
      localStorage.setItem("unimate.brains", JSON.stringify(kept));
    }
    // Gỡ các option thư mục ngoài (do app.js đã render) không còn trong danh sách giữ lại.
    const keepVals = new Set(kept.map((b) => "path:" + b.path));
    [...sel.querySelectorAll("option[data-custom]")].forEach((o) => {
      if (keepVals.has(o.value)) return;
      if (sel.value === o.value) {           // đang chọn đúng cái bị gỡ → về não trùng, không có thì brain mặc định
        const ve = thay.get(o.value) || "brain";
        o.remove();
        sel.value = [...sel.options].some((x) => x.value === ve) ? ve : "brain";
        localStorage.setItem("unimate.graphSource", sel.value);
        sel.dispatchEvent(new Event("change"));
        return;
      }
      o.remove();
    });
    // Gỡ hết option trong nhóm thì gỡ luôn nhóm, kẻo menu còn trơ lại cái nhãn
    // "Thư mục ngoài" không có gì bên dưới.
    [...sel.querySelectorAll("optgroup")].forEach((g) => {
      if (!g.querySelector || !g.querySelector("option")) g.remove();
    });
    relabel();
    syncButtons();
  }

  // Nhãn nhóm "Thư mục ngoài". app.js vẽ nhóm này ngay lúc nạp trang, có khi TRƯỚC khi từ điển về,
  // nên nhãn ra mã khoá `app.external_folder` (chủ dự án gặp 04/11/2026). Vẽ lại khi từ điển về.
  function relabel() {
    const g = sel.querySelector("optgroup[data-custom-group]");
    if (g) g.label = window.t("app.external_folder");
  }
  window.addEventListener("unimate:i18n", relabel);

  // Nút theo loại đang chọn. Thư mục ngoài: hiện nút Gỡ khỏi danh sách, ẩn Đổi tên và Xoá (hai nút đó
  // chỉ dành cho não trong thư mục brains). Não: ngược lại.
  const removeBtn = document.getElementById("removeFolderBtn");
  function syncButtons() {
    const opt = sel.options[sel.selectedIndex];
    const ngoai = !!(opt && opt.dataset && opt.dataset.custom);
    if (removeBtn) removeBtn.hidden = !ngoai;
    ["renameBrainBtn", "delBrainBtn"].forEach((id) => {
      const b = document.getElementById(id);
      if (b) b.hidden = ngoai;
    });
  }
  sel.addEventListener("change", syncButtons);

  async function loadBrains(selectPath, restoreSaved) {
    let data;
    try {
      data = await (await fetch("/brains")).json();
    } catch (e) {
      return; // server chưa sẵn sàng → giữ nguyên dropdown, thử lại lần sau
    }
    const brains = (data && data.brains) || [];
    _lastBrains = brains;
    [...sel.querySelectorAll("option[data-brain]")].forEach((o) => o.remove());

    const defOpt = sel.querySelector('option[value="brain"]');
    const frag = document.createDocumentFragment();
    brains.forEach((b) => {
      if (b.is_default) {
        if (defOpt) { defOpt.textContent = label(b); defOpt.dataset.brainLabel = b.label || b.name; }
        return; // default đã có sẵn option value="brain"
      }
      const opt = document.createElement("option");
      opt.value = "path:" + b.path;
      opt.textContent = label(b);
      opt.dataset.brain = "1";
      opt.dataset.brainName = b.name; // tên folder để xoá chính xác
      opt.dataset.brainLabel = b.label || b.name;
      frag.appendChild(opt);
    });
    if (defOpt && defOpt.nextSibling) sel.insertBefore(frag, defOpt.nextSibling);
    else sel.appendChild(frag);

    // Dọn folder ngoài hỏng/trùng TRƯỚC khi khôi phục lựa chọn (đừng khôi phục về path đã chết).
    await pruneCustomBrains(brains);

    if (selectPath) {
      const want = "path:" + selectPath;
      if ([...sel.options].some((o) => o.value === want)) {
        sel.value = want;
        localStorage.setItem("unimate.graphSource", want);
        sel.dispatchEvent(new Event("change"));
      }
    } else if (restoreSaved) {
      const saved = localStorage.getItem("unimate.graphSource");
      if (saved && saved !== sel.value && [...sel.options].some((o) => o.value === saved)) {
        sel.value = saved;
        sel.dispatchEvent(new Event("change"));
      }
    }
  }

  async function newBrain() {
    const name = (window.prompt(window.t("brains.new_prompt")) || "").trim();
    if (!name) return;
    const fd = new FormData();
    fd.append("name", name);
    let r;
    try { r = await (await fetch("/brains/new", { method: "POST", body: fd })).json(); }
    catch (e) { alert(window.t("brains.create_net_err")); return; }
    if (!r || !r.ok) { alert((r && r.error) || window.t("brains.create_failed")); return; }
    await loadBrains(r.path, false);
  }

  // Gỡ 1 thư mục ngoài khỏi danh sách - CHỈ khỏi menu + localStorage, KHÔNG đụng ổ đĩa.
  function removeCustomFromList(opt) {
    const name = opt.textContent.trim();
    if (!window.confirm(window.t("brains.confirm_remove_custom", { ten: name }))) return;
    let list;
    try { list = JSON.parse(localStorage.getItem("unimate.brains") || "[]"); } catch (e) { list = []; }
    if (!Array.isArray(list)) list = [];
    list = list.filter((b) => b && ("path:" + b.path) !== opt.value);
    localStorage.setItem("unimate.brains", JSON.stringify(list));
    if (sel.value === opt.value) {
      sel.value = "brain";
      localStorage.setItem("unimate.graphSource", "brain");
    }
    opt.remove();
    [...sel.querySelectorAll("optgroup")].forEach((g) => {
      if (!g.querySelector("option")) g.remove();
    });
    sel.dispatchEvent(new Event("change"));
    alert(window.t("brains.removed_custom", { ten: name }));
  }

  // Nút Gỡ thư mục ngoài (0.442.0): trước đây chỉ gỡ được bằng nút Xoá brain, mà nút đó ghi "Xoá
  // brain đang chọn" nên không ai đoán ra.
  function removeSelectedFolder() {
    const opt = sel.options[sel.selectedIndex];
    if (opt && opt.dataset.custom) removeCustomFromList(opt);
  }

  async function deleteBrain() {
    const opt = sel.options[sel.selectedIndex];
    if (sel.value === "brain") { alert(window.t("brains.cannot_delete_default")); return; }
    if (!opt || !opt.dataset.brain) {
      // Thư mục ngoài: cho GỠ khỏi danh sách (không xoá ổ đĩa). Trước đây chỉ báo lỗi mà
      // không có cách gỡ nào → entry kẹt vĩnh viễn kể cả sau khi folder đã bị xoá.
      if (opt && opt.dataset.custom) { removeCustomFromList(opt); return; }
      alert(window.t("brains.only_listed"));
      return;
    }
    const name = opt.dataset.brainName;
    // Xác nhận KỸ: gõ đúng tên - vì đây là TOÀN BỘ tri thức trong não này, mất là không lấy lại được.
    const typed = window.prompt(window.t("brains.delete_prompt", { ten: name }));
    if (typed === null) return;
    if (typed.trim() !== name) { alert(window.t("brains.name_mismatch")); return; }
    const fd = new FormData();
    fd.append("name", name);
    fd.append("confirm", typed.trim());
    let r;
    try { r = await (await fetch("/brains/delete", { method: "POST", body: fd })).json(); }
    catch (e) { alert(window.t("brains.delete_net_err")); return; }
    if (!r || !r.ok) { alert((r && r.error) || window.t("brains.delete_failed")); return; }
    // Về brain mặc định rồi nạp lại danh sách
    sel.value = "brain";
    localStorage.setItem("unimate.graphSource", "brain");
    await loadBrains(null, false);
    sel.dispatchEvent(new Event("change"));
    alert(window.t("brains.deleted", { ten: name }));
  }

  // Đổi tên (0.219.0): chỉ đổi TÊN HIỂN THỊ, lưu trong chính brain (UniMate/brain.json). Thư mục giữ nguyên nên mọi
  // lựa chọn đã lưu, bot, nhắc việc, việc nền và link /brains/<thư mục>/... trong note vẫn trỏ đúng. Đổi được cả Brain
  // mặc định (trước đây không có cách nào đổi tên não nào).
  async function renameBrain() {
    const opt = sel.options[sel.selectedIndex];
    if (!opt || (sel.value !== "brain" && !opt.dataset.brain)) { alert(window.t("brains.only_listed")); return; }
    const cu = opt.dataset.brainLabel || opt.textContent.trim();
    const moi = window.prompt(window.t("brains.rename_prompt"), cu);
    if (moi === null || moi.trim() === cu) return;
    const fd = new FormData();
    fd.append("brain", sel.value);
    fd.append("label", moi.trim());
    let r;
    try { r = await (await fetch("/brains/label", { method: "POST", body: fd })).json(); }
    catch (e) { alert(window.t("brains.rename_net_err")); return; }
    if (!r || !r.ok) { alert((r && r.error) || window.t("brains.rename_failed")); return; }
    await loadBrains(null, false);
    // Báo các phần khác (tiêu đề, sidebar) vẽ lại tên mà không đổi brain đang chọn.
    try { window.dispatchEvent(new CustomEvent("unimate:brain-renamed", { detail: { brain: sel.value, label: r.label } })); } catch (e) {}
  }

  const rb = document.getElementById("renameBrainBtn");
  if (rb) rb.addEventListener("click", renameBrain);
  const nb = document.getElementById("newBrainBtn");
  if (nb) nb.addEventListener("click", newBrain);
  const db = document.getElementById("delBrainBtn");
  if (db) db.addEventListener("click", deleteBrain);
  if (removeBtn) removeBtn.addEventListener("click", removeSelectedFolder);

  syncButtons();
  loadBrains(null, true);

  // linkedFor: app.js hỏi trước khi thêm một thư mục vừa chọn, để chọn thẳng não đã kết nối khi trùng.
  window.UniMateBrains = { reload: () => loadBrains(null, false), linkedFor: (p) => linkedFor(p) };
})();
