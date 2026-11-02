/* Khung trình duyệt cạnh khung chat (0.430.0).
 *
 * Chủ repo 02/11/2026: muốn một cửa sổ trình duyệt ngay trong UNI MATE, như khung "Duyệt web với Claude". Trình duyệt
 * thật chạy trên MÁY CHỦ UNI MATE (server/browser_pane.py, Chromium ẩn); khung này chỉ là màn hình và bàn phím của nó:
 * - nhận khung hình JPEG qua WS /ws/browser (tin nhị phân), vẽ lên <canvas>;
 * - gửi ngược chuột, cuộn, phím, chữ; ô địa chỉ, lùi/tiến/tải lại, tab.
 * Vì trình duyệt nằm trên máy chủ nên trên VPS khung vẫn chạy y như máy nhà, và AI dùng chung đúng trình duyệt này.
 *
 * Gõ tiếng Việt: phím chữ gửi thành phím thật (keyDown kèm chữ), bộ gõ kiểu Unikey (gửi lùi rồi chữ có dấu) đi
 * đúng đường đó; bộ gõ dùng "composition" (Microsoft Vietnamese, bàn phím điện thoại) thì gom chữ ở compositionend rồi
 * chèn một lần. Ô <textarea> trong suốt phủ lên canvas là chỗ nhận bàn phím, nên bộ gõ của hệ điều hành hoạt động.
 */
(function () {
  "use strict";

  function t(k, v) { return (typeof window !== "undefined" && window.t) ? window.t(k, v) : k; }
  function icon(n) { return (window.ic ? window.ic(n) : ""); }
  function esc(s) {
    return String(s == null ? "" : s).replace(/[&<>"']/g, function (c) {
      return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c];
    });
  }
  function doc(k) { try { return localStorage.getItem(k); } catch (e) { return null; } }
  function ghi(k, v) { try { if (v == null) localStorage.removeItem(k); else localStorage.setItem(k, String(v)); } catch (e) {} }
  function brain() { try { return (window.currentBrainPath && window.currentBrainPath()) || "brain"; } catch (e) { return "brain"; } }

  var WS_GOC = (location.protocol === "https:" ? "wss://" : "ws://") + location.host;
  var KHOA_MO = "uni.bp.open";
  var KHOA_RONG = "uni.bp.w";
  var RONG_MIN = 360, RONG_MAC_DINH = 640;

  var pane, btn, view, canvas, ctx, ime, urlIn, tabsEl, msgEl, dlgEl, toastEl, backBtn, fwdBtn, reloadBtn, fullBtn;
  var ws = null, mo = false, ketNoi = false, thuLai = 0, henNoi = null, henToast = null;
  var kich = [1280, 800], tabs = [], active = "", dangVe = false, khungCho = null;
  var phimDangGiu = {};

  // ---------- dựng khung ----------

  function dung() {
    pane = document.getElementById("browserPane");
    btn = document.getElementById("browserPaneBtn");
    if (!pane || !btn) return false;
    pane.innerHTML =
      '<div class="bp-resize" id="bpResize" role="separator" aria-orientation="vertical" title="' + esc(t("bp.resize")) + '"></div>' +
      '<div class="bp-top">' +
        '<div class="bp-tabs" id="bpTabs" role="tablist"></div>' +
        '<button type="button" class="bp-ic" id="bpNewTab" title="' + esc(t("bp.new_tab")) + '" aria-label="' + esc(t("bp.new_tab")) + '">' + icon("plus") + '</button>' +
        '<span class="bp-sp"></span>' +
        '<button type="button" class="bp-ic" id="bpFull" title="' + esc(t("bp.full")) + '" aria-label="' + esc(t("bp.full")) + '">' + icon("maximize") + '</button>' +
        '<button type="button" class="bp-ic" id="bpClose" title="' + esc(t("bp.close")) + '" aria-label="' + esc(t("bp.close")) + '">' + icon("x") + '</button>' +
      '</div>' +
      '<div class="bp-bar">' +
        '<button type="button" class="bp-ic" id="bpBack" title="' + esc(t("bp.back")) + '" aria-label="' + esc(t("bp.back")) + '">' + icon("arrow-left") + '</button>' +
        '<button type="button" class="bp-ic bp-fwd" id="bpFwd" title="' + esc(t("bp.forward")) + '" aria-label="' + esc(t("bp.forward")) + '">' + icon("arrow-left") + '</button>' +
        '<button type="button" class="bp-ic" id="bpReload" title="' + esc(t("bp.reload")) + '" aria-label="' + esc(t("bp.reload")) + '">' + icon("rotate-cw") + '</button>' +
        '<input type="text" class="bp-url" id="bpUrl" spellcheck="false" autocomplete="off" data-esc placeholder="' + esc(t("bp.url_ph")) + '">' +
      '</div>' +
      '<div class="bp-view" id="bpView">' +
        '<canvas class="bp-canvas" id="bpCanvas"></canvas>' +
        '<textarea class="bp-ime" id="bpIme" autocomplete="off" autocorrect="off" autocapitalize="off" spellcheck="false" aria-label="' + esc(t("bp.title")) + '"></textarea>' +
        '<div class="bp-msg" id="bpMsg" hidden></div>' +
        // Hộp thoại của trang (alert/confirm/prompt) NỔI trên hình chứ không chen vào bố cục: chen vào là khung hình
        // đổi cỡ, ảnh bị kéo giãn và toạ độ chuột lệch đúng lúc người dùng bấm nút trả lời.
        '<div class="bp-dialog" id="bpDialog" hidden></div>' +
      '</div>' +
      '<div class="bp-toast" id="bpToast" hidden></div>';
    view = document.getElementById("bpView");
    canvas = document.getElementById("bpCanvas");
    ctx = canvas.getContext("2d");
    ime = document.getElementById("bpIme");
    urlIn = document.getElementById("bpUrl");
    tabsEl = document.getElementById("bpTabs");
    msgEl = document.getElementById("bpMsg");
    dlgEl = document.getElementById("bpDialog");
    toastEl = document.getElementById("bpToast");
    backBtn = document.getElementById("bpBack");
    fwdBtn = document.getElementById("bpFwd");
    reloadBtn = document.getElementById("bpReload");
    fullBtn = document.getElementById("bpFull");

    btn.addEventListener("click", function () { if (mo) dong(); else moKhung(); });
    document.getElementById("bpClose").addEventListener("click", dong);
    document.getElementById("bpNewTab").addEventListener("click", function () { gui({ type: "tab_new" }); });
    fullBtn.addEventListener("click", function () { phongTo(!pane.classList.contains("bp-full")); });
    backBtn.addEventListener("click", function () { gui({ type: "back" }); });
    fwdBtn.addEventListener("click", function () { gui({ type: "forward" }); });
    reloadBtn.addEventListener("click", function () {
      var tab = tabDangXem();
      gui({ type: tab && tab.loading ? "stop" : "reload" });
    });
    urlIn.addEventListener("keydown", function (e) {
      if (e.key === "Enter") {
        e.preventDefault();
        var s = urlIn.value.trim();
        if (s) { gui({ type: "nav", url: s }); urlIn.blur(); ime.focus({ preventScroll: true }); }
      } else if (e.key === "Escape") {
        e.preventDefault();
        capNhatThanh(true);
        urlIn.blur();
      }
    });
    urlIn.addEventListener("focus", function () { setTimeout(function () { try { urlIn.select(); } catch (e) {} }, 0); });
    tabsEl.addEventListener("click", function (e) {
      var x = e.target.closest("[data-close]");
      if (x) { e.stopPropagation(); gui({ type: "tab_close", id: x.getAttribute("data-close") }); return; }
      var c = e.target.closest("[data-tab]");
      if (c) gui({ type: "tab_select", id: c.getAttribute("data-tab") });
    });
    tabsEl.addEventListener("auxclick", function (e) {
      var c = e.target.closest("[data-tab]");
      if (c && e.button === 1) { e.preventDefault(); gui({ type: "tab_close", id: c.getAttribute("data-tab") }); }
    });
    msgEl.addEventListener("click", function () { if (!ketNoi && mo) noi(); });
    ganChuot();
    ganPhim();
    ganKeoRong();
    var w0 = parseInt(doc(KHOA_RONG), 10);
    if (w0 >= RONG_MIN) document.documentElement.style.setProperty("--bp-w", w0 + "px");
    // Màn Đồ thị không có trình duyệt (CSS ẩn khung): rời sang Đồ thị thì ngắt luồng hình, quay lại màn khác thì nối lại.
    // console.js bật/tắt lớp in-console trên <body> khi đổi màn.
    if (window.MutationObserver) {
      new MutationObserver(theoMan).observe(document.body, { attributes: true, attributeFilter: ["class"] });
    }
    if (window.ResizeObserver) {
      var hen = null;
      new ResizeObserver(function () {
        clearTimeout(hen);
        hen = setTimeout(baoKichThuoc, 200);
      }).observe(view);
    }
    if (doc(KHOA_MO) === "1") moKhung();
    return true;
  }

  function phongTo(on) {
    pane.classList.toggle("bp-full", !!on);
    document.body.classList.toggle("bp-full-on", !!on);
    fullBtn.title = t(on ? "bp.exit_full" : "bp.full");
    fullBtn.setAttribute("aria-label", fullBtn.title);
  }

  function oManDoThi() { return !document.body.classList.contains("in-console"); }

  /** Đổi màn: Đồ thị không có trình duyệt (chủ repo 02/11/2026), nên ngắt luồng hình khi sang đó và nối lại khi về. */
  function theoMan() {
    if (!mo) return;
    if (oManDoThi()) { if (ws) { clearTimeout(henNoi); ngat(); } }
    else if (!ws) noi();
  }

  function moKhung() {
    mo = true;
    ghi(KHOA_MO, "1");
    document.body.classList.add("bp-on");
    pane.hidden = false;
    btn.classList.add("active");
    btn.setAttribute("aria-pressed", "true");
    if (!ws && !oManDoThi()) noi();
    setTimeout(function () { try { ime.focus({ preventScroll: true }); } catch (e) {} }, 50);
  }

  function dong() {
    mo = false;
    ghi(KHOA_MO, null);
    document.body.classList.remove("bp-on");
    phongTo(false);
    pane.hidden = true;
    btn.classList.remove("active");
    btn.setAttribute("aria-pressed", "false");
    clearTimeout(henNoi);
    ngat();
  }

  // ---------- kết nối ----------

  function kichThuocKhung() {
    var r = view.getBoundingClientRect();
    return [Math.max(320, Math.round(r.width)), Math.max(240, Math.round(r.height))];
  }

  function noi() {
    ngat();
    var k = kichThuocKhung();
    baoTin(t("bp.connecting"), false);
    var s = ws = new WebSocket(WS_GOC + "/ws/browser?brain=" + encodeURIComponent(brain()) + "&w=" + k[0] + "&h=" + k[1]);
    s.binaryType = "blob";
    s.onopen = function () { ketNoi = true; thuLai = 0; };
    s.onmessage = function (ev) {
      if (typeof ev.data !== "string") { nhanKhung(ev.data); return; }
      var m;
      try { m = JSON.parse(ev.data); } catch (e) { return; }
      xuLyTin(m);
    };
    s.onclose = function () {
      if (ws !== s) return;
      ws = null;
      ketNoi = false;
      if (!mo) return;
      if (msgEl.getAttribute("data-err") === "1") return;   // lỗi cứng (chưa có trình duyệt): không tự nối lại
      thuLai = Math.min(thuLai + 1, 6);
      baoTin(t("bp.lost"), true);
      henNoi = setTimeout(function () { if (mo && !ws && !oManDoThi()) noi(); }, 800 * thuLai);
    };
  }

  function ngat() {
    var s = ws;
    ws = null;
    ketNoi = false;
    if (!s) return;
    s.onclose = null; s.onmessage = null; s.onerror = null;
    try { s.close(); } catch (e) {}
  }

  function gui(o) {
    if (ws && ws.readyState === 1) { ws.send(JSON.stringify(o)); return true; }
    return false;
  }

  function baoKichThuoc() {
    if (!mo || pane.hidden) return;
    var k = kichThuocKhung();
    if (k[0] === kich[0] && k[1] === kich[1]) return;
    gui({ type: "resize", w: k[0], h: k[1] });
  }

  // ---------- tin từ máy chủ ----------

  function xuLyTin(m) {
    if (m.type === "tabs") {
      tabs = m.tabs || [];
      active = m.active || "";
      if (m.view) datKich(m.view);
      veTabs();
      capNhatThanh(false);
      anTin();
      return;
    }
    if (m.type === "view") { datKich(m.view); return; }
    if (m.type === "dialog") { veHopThoai(m); return; }
    if (m.type === "dialog_closed") { dlgEl.hidden = true; dlgEl.innerHTML = ""; return; }
    if (m.type === "download") {
      var k = m.state === "begin" ? "bp.dl_begin" : (m.state === "completed" ? "bp.dl_done" : "bp.dl_cancel");
      toast(t(k, { name: m.name || "" }));
      return;
    }
    if (m.type === "closed") { baoTin(t("bp.closed"), true); return; }
    if (m.type === "notice") { if (m.error) toast(m.error); return; }
    if (m.type === "error") {
      baoTin(m.error || t("bp.lost"), true);
      msgEl.setAttribute("data-err", "1");
    }
  }

  function datKich(v) {
    if (!v || v.length < 2) return;
    kich = [v[0], v[1]];
    if (canvas.width !== v[0] || canvas.height !== v[1]) { canvas.width = v[0]; canvas.height = v[1]; }
  }

  function nhanKhung(blob) {
    if (dangVe) { khungCho = blob; return; }
    dangVe = true;
    var ve = function (b) {
      (window.createImageBitmap ? createImageBitmap(b) : Promise.reject()).then(function (img) {
        ctx.drawImage(img, 0, 0, canvas.width, canvas.height);
        if (img.close) img.close();
      }).catch(function () {}).then(function () {
        if (khungCho) { var n = khungCho; khungCho = null; ve(n); } else dangVe = false;
      });
    };
    ve(blob);
  }

  function tabDangXem() {
    for (var i = 0; i < tabs.length; i++) if (tabs[i].id === active) return tabs[i];
    return null;
  }

  // Tab "chưa có gì": hồ sơ mới của Chromium mở trang tab mới riêng của nó, không cho người dùng thấy địa chỉ nội bộ đó.
  var TRANG_TRANG = { "": 1, "about:blank": 1, "chrome://newtab/": 1, "chrome://new-tab-page/": 1 };
  function laTrang(url) { return !!TRANG_TRANG[url || ""]; }

  function tenTab(tb) {
    if (laTrang(tb.url)) return t("bp.empty_tab");
    if (tb.title && tb.title !== tb.url) return tb.title;
    return tb.url || t("bp.empty_tab");
  }

  function veTabs() {
    tabsEl.innerHTML = tabs.map(function (tb) {
      var ten = tenTab(tb);
      return '<div class="bp-tab' + (tb.id === active ? " active" : "") + '" role="tab" aria-selected="' + (tb.id === active) +
        '" data-tab="' + esc(tb.id) + '" title="' + esc(ten) + '">' +
        (tb.loading ? '<span class="bp-spin"></span>' : "") +
        '<span class="bp-tab-ten">' + esc(ten) + '</span>' +
        '<button type="button" class="bp-tab-x" data-close="' + esc(tb.id) + '" title="' + esc(t("bp.close_tab")) + '" aria-label="' + esc(t("bp.close_tab")) + '">' + icon("x") + '</button>' +
        '</div>';
    }).join("");
  }

  function capNhatThanh(epUrl) {
    var tb = tabDangXem();
    if (tb && (epUrl || document.activeElement !== urlIn)) urlIn.value = laTrang(tb.url) ? "" : (tb.url || "");
    var dangTai = !!(tb && tb.loading);
    reloadBtn.innerHTML = icon(dangTai ? "x" : "rotate-cw");
    reloadBtn.title = t(dangTai ? "bp.stop" : "bp.reload");
    reloadBtn.setAttribute("aria-label", reloadBtn.title);
  }

  function veHopThoai(m) {
    var laPrompt = m.kind === "prompt";
    var coHuy = m.kind !== "alert";
    dlgEl.innerHTML = '<div class="bp-dlg-msg">' + esc(m.message || "") + '</div>' +
      (laPrompt ? '<input type="text" class="bp-dlg-in" value="' + esc(m["default"] || "") + '">' : "") +
      '<div class="bp-dlg-btns">' +
        (coHuy ? '<button type="button" class="gcard-btn ghost" data-dlg="0">' + esc(t("bp.dialog_cancel")) + '</button>' : "") +
        '<button type="button" class="gcard-btn" data-dlg="1">' + esc(t("bp.dialog_ok")) + '</button>' +
      '</div>';
    dlgEl.hidden = false;
    dlgEl.querySelectorAll("[data-dlg]").forEach(function (b) {
      b.addEventListener("click", function () {
        var o = { type: "dialog", accept: b.getAttribute("data-dlg") === "1" };
        var inp = dlgEl.querySelector(".bp-dlg-in");
        if (inp) o.text = inp.value;
        gui(o);
        dlgEl.hidden = true;
      });
    });
  }

  function baoTin(s, bam) {
    msgEl.textContent = s;
    msgEl.hidden = false;
    msgEl.classList.toggle("bp-msg-click", !!bam);
    msgEl.removeAttribute("data-err");
  }
  function anTin() { msgEl.hidden = true; msgEl.removeAttribute("data-err"); }

  function toast(s) {
    toastEl.textContent = s;
    toastEl.hidden = false;
    clearTimeout(henToast);
    henToast = setTimeout(function () { toastEl.hidden = true; }, 5000);
  }

  // ---------- kéo rộng hẹp ----------

  function datRong(w) {
    var tran = Math.max(RONG_MIN, window.innerWidth - 420);
    w = Math.round(Math.max(RONG_MIN, Math.min(tran, w)));
    document.documentElement.style.setProperty("--bp-w", w + "px");
    return w;
  }

  function ganKeoRong() {
    var tay = document.getElementById("bpResize");
    if (!tay) return;
    tay.addEventListener("mousedown", function (e) {
      if (e.button !== 0) return;
      e.preventDefault();
      var phai = pane.getBoundingClientRect().right;
      var w = pane.getBoundingClientRect().width;
      tay.classList.add("dang-keo");
      document.body.classList.add("bp-keo");
      function di(ev) { w = datRong(phai - ev.clientX); }
      function tha() {
        document.removeEventListener("mousemove", di);
        document.removeEventListener("mouseup", tha);
        tay.classList.remove("dang-keo");
        document.body.classList.remove("bp-keo");
        ghi(KHOA_RONG, w);
      }
      document.addEventListener("mousemove", di);
      document.addEventListener("mouseup", tha);
    });
    tay.addEventListener("dblclick", function () { ghi(KHOA_RONG, datRong(RONG_MAC_DINH)); });
  }

  // ---------- chuột ----------

  function toaDo(e) {
    var r = canvas.getBoundingClientRect();
    return {
      x: Math.round((e.clientX - r.left) * kich[0] / Math.max(1, r.width)),
      y: Math.round((e.clientY - r.top) * kich[1] / Math.max(1, r.height))
    };
  }
  function phimBo(e) { return (e.altKey ? 1 : 0) | (e.ctrlKey ? 2 : 0) | (e.metaKey ? 4 : 0) | (e.shiftKey ? 8 : 0); }
  var TEN_NUT = ["left", "middle", "right"];

  function ganChuot() {
    var cho = false, cuoi = null;
    ime.addEventListener("mousedown", function (e) {
      e.preventDefault();
      try { ime.focus({ preventScroll: true }); } catch (x) {}
      var p = toaDo(e);
      gui({ type: "mouse", ev: "down", x: p.x, y: p.y, button: TEN_NUT[e.button] || "left", buttons: e.buttons, clicks: e.detail || 1, mods: phimBo(e) });
    });
    ime.addEventListener("mouseup", function (e) {
      var p = toaDo(e);
      gui({ type: "mouse", ev: "up", x: p.x, y: p.y, button: TEN_NUT[e.button] || "left", buttons: e.buttons, clicks: e.detail || 1, mods: phimBo(e) });
    });
    ime.addEventListener("mousemove", function (e) {
      cuoi = e;
      if (cho) return;
      cho = true;
      requestAnimationFrame(function () {
        cho = false;
        var ev = cuoi;
        if (!ev) return;
        var p = toaDo(ev);
        gui({ type: "mouse", ev: "move", x: p.x, y: p.y, held: ev.buttons > 0, button: ev.buttons & 1 ? "left" : (ev.buttons & 2 ? "right" : "none"), buttons: ev.buttons, mods: phimBo(ev) });
      });
    });
    ime.addEventListener("wheel", function (e) {
      e.preventDefault();
      var he = e.deltaMode === 1 ? 40 : (e.deltaMode === 2 ? kich[1] : 1);
      var p = toaDo(e);
      gui({ type: "wheel", x: p.x, y: p.y, dx: e.deltaX * he, dy: e.deltaY * he, mods: phimBo(e) });
    }, { passive: false });
    ime.addEventListener("contextmenu", function (e) { e.preventDefault(); });
  }

  // ---------- bàn phím ----------

  var PHIM_DAC_BIET = {
    Enter: 1, Backspace: 1, Tab: 1, Escape: 1, Delete: 1, Insert: 1, Home: 1, End: 1, PageUp: 1, PageDown: 1,
    ArrowUp: 1, ArrowDown: 1, ArrowLeft: 1, ArrowRight: 1, F1: 1, F2: 1, F3: 1, F4: 1, F5: 1, F6: 1, F7: 1, F8: 1,
    F9: 1, F10: 1, F11: 1, F12: 1
  };

  function guiPhim(e, ev, text) {
    gui({ type: "key", ev: ev, key: e.key, code: e.code, keyCode: e.keyCode || 0, mods: phimBo(e), text: text || "" });
  }

  function ganPhim() {
    ime.addEventListener("keydown", function (e) {
      if (e.isComposing || e.keyCode === 229) return;          // bộ gõ đang ghép chữ: chờ compositionend
      var tat = e.ctrlKey || e.metaKey;
      if (tat && !e.altKey && (e.key === "v" || e.key === "V")) return;   // để sự kiện paste mang chữ sang
      if (e.key === "F5" || (tat && (e.key === "r" || e.key === "R"))) {
        e.preventDefault(); gui({ type: "reload" }); return;
      }
      if (tat && (e.key === "l" || e.key === "L")) { e.preventDefault(); urlIn.focus(); return; }
      if (PHIM_DAC_BIET[e.key] || tat) {
        e.preventDefault();
        phimDangGiu[e.code || e.key] = 1;
        guiPhim(e, "down", e.key === "Enter" ? "\r" : "");
        return;
      }
      if (e.key && e.key.length === 1 && !e.altKey) {
        e.preventDefault();
        phimDangGiu[e.code || e.key] = 1;
        guiPhim(e, "down", e.key);
        return;
      }
      if (e.key === "Shift" || e.key === "Control" || e.key === "Alt" || e.key === "Meta") {
        phimDangGiu[e.code || e.key] = 1;
        guiPhim(e, "down", "");
      }
    });
    ime.addEventListener("keyup", function (e) {
      var ma = e.code || e.key;
      if (!phimDangGiu[ma]) return;
      delete phimDangGiu[ma];
      guiPhim(e, "up", "");
    });
    ime.addEventListener("compositionend", function (e) {
      if (e.data) gui({ type: "text", text: e.data });
      ime.value = "";
    });
    ime.addEventListener("input", function (e) {
      if (e.isComposing || e.inputType === "insertCompositionText") return;
      if (ime.value) { gui({ type: "text", text: ime.value }); ime.value = ""; }
    });
    ime.addEventListener("paste", function (e) {
      e.preventDefault();
      var s = (e.clipboardData || window.clipboardData).getData("text");
      if (s) gui({ type: "text", text: s });
    });
    ime.addEventListener("blur", function () {
      // Rời khung khi đang giữ phím (Alt+Tab) thì nhả hết, không để trang tưởng Ctrl còn bị giữ.
      Object.keys(phimDangGiu).forEach(function (ma) {
        gui({ type: "key", ev: "up", key: ma, code: ma, keyCode: 0, mods: 0, text: "" });
      });
      phimDangGiu = {};
    });
  }

  function khoiDong() {
    if (!dung()) return;
    window.UniBrowserPane = { open: moKhung, close: dong, isOpen: function () { return mo; } };
  }

  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", khoiDong);
  else khoiDong();
})();
